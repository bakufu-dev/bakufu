/**
 * TC-E2E-CD-009: WebSocket リアルタイム更新（受入基準 #12）— P0 必須
 * TC-E2E-CD-010: WebSocket 切断 / 再接続（受入基準 #13）
 *
 * BUG-E2E-002 修正済み:
 *   - バックエンドコンテナに ws.py / connection_manager.py / event_bus.py を配備
 *   - app.py の lifespan に ConnectionManager・InMemoryEventBus 初期化を追加
 *   - /ws エンドポイントが ws://localhost:8000/ws で正常動作することを確認
 *
 * TC-E2E-CD-009 戦略:
 *   1. page.routeWebSocket で実 WS サーバーへ転送しつつ注入口を確保
 *   2. WS 接続済みを確認後、GET .../tasks の後続リクエストを傍受して status 改変
 *   3. 合成 task.state_changed WS メッセージを注入
 *   4. フロントエンドが QueryClient.invalidateQueries → 再フェッチ → StatusBadge 更新を
 *      ページリロードなしに行うことを aria-label で検証
 *
 * TC-E2E-CD-010 戦略:
 *   1. 実 WS 接続後に page.context().setOffline(true) で強制切断
 *   2. ConnectionIndicator が「再接続中...」に遷移することを確認
 *   3. setOffline(false) で回線復旧 → 再接続バックオフ 1000ms 後に「接続済み」を確認
 */
import { expect, test } from "@playwright/test";
import type { WebSocketRoute } from "@playwright/test";
import { ROOM_ID, TASK_PENDING_ID } from "./helpers";

test.describe("TC-E2E-CD-009: WebSocket リアルタイム更新 (P0)", () => {
  test("WS task.state_changed イベント受信 → StatusBadge aria-label がページリロードなしで更新される", async ({
    page,
  }) => {
    // -------------------------------------------------------------------
    // Step 1: WS ルートを設定（実サーバーへ転送 + 注入口を取得）
    // connectToServer() を呼ぶと双方向自動転送が有効になる。
    // ws.send() で「サーバーから」クライアントへの合成メッセージを追加注入できる。
    // -------------------------------------------------------------------
    let wsClientRoute: WebSocketRoute | null = null;

    await page.routeWebSocket("ws://localhost:8000/ws", (ws: WebSocketRoute) => {
      ws.connectToServer(); // 実 WS サーバーへ双方向転送
      wsClientRoute = ws;
    });

    // -------------------------------------------------------------------
    // Step 2: ページ遷移（loader が初回タスク一覧をフェッチ）
    // -------------------------------------------------------------------
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // -------------------------------------------------------------------
    // Step 3: WebSocket 接続済みを確認
    // ConnectionIndicator: <output aria-label="サーバーと接続済み">
    // -------------------------------------------------------------------
    await expect(page.locator('output[aria-label="サーバーと接続済み"]')).toBeVisible({
      timeout: 10_000,
    });

    // wsClientRoute はこの時点で必ず設定済み（WS 接続が完了しているため）
    expect(wsClientRoute).not.toBeNull();

    // -------------------------------------------------------------------
    // Step 4: TASK_PENDING_ID の初期ステータスが PENDING であることを確認
    // TaskCard は <a href="/tasks/{id}"> で識別する
    // StatusBadge は <span aria-label="{status}">
    // -------------------------------------------------------------------
    const taskLink = page.locator(`a[href="/tasks/${TASK_PENDING_ID}"]`);
    await expect(taskLink).toBeVisible();
    await expect(taskLink.locator("span[aria-label]")).toHaveAttribute("aria-label", "PENDING");

    // -------------------------------------------------------------------
    // Step 5: WS メッセージ注入後の再フェッチを傍受し、PENDING → IN_PROGRESS に改変
    // useWebSocketBus handleMessage("Task") → invalidateQueries(["tasks"])
    // → useTasks が GET /api/rooms/{roomId}/tasks を再実行する
    // ここで route を設定（初回ロードには適用しない）
    // -------------------------------------------------------------------
    await page.route(`**/api/rooms/${ROOM_ID}/tasks*`, async (route) => {
      const response = await route.fetch();
      const json = (await response.json()) as {
        items: Array<{ id: string; status: string }>;
        total: number;
      };
      // TASK_PENDING_ID の status だけ IN_PROGRESS に差し替える
      json.items = json.items.map((t) =>
        t.id === TASK_PENDING_ID ? { ...t, status: "IN_PROGRESS" } : t,
      );
      await route.fulfill({ json });
    });

    // -------------------------------------------------------------------
    // Step 6: 合成 task.state_changed WS メッセージを注入
    // フロントエンドの handleMessage が aggregate_type="Task" を検知して
    // queryClient.invalidateQueries(["tasks"]) を呼び出す
    // -------------------------------------------------------------------
    (wsClientRoute as WebSocketRoute).send(
      JSON.stringify({
        event_type: "task.state_changed",
        aggregate_id: TASK_PENDING_ID,
        aggregate_type: "Task",
        occurred_at: new Date().toISOString(),
        payload: {
          old_status: "PENDING",
          new_status: "IN_PROGRESS",
          directive_id: "dir-seed-001",
          room_id: ROOM_ID,
        },
      }),
    );

    // -------------------------------------------------------------------
    // Step 7: ページリロードなしに StatusBadge が IN_PROGRESS へ更新される（REQ-CD-UI-006）
    // expect(...).toHaveAttribute で aria-label 更新を検証（ヘルスバーグ要求仕様）
    // -------------------------------------------------------------------
    await expect(taskLink.locator("span[aria-label]")).toHaveAttribute(
      "aria-label",
      "IN_PROGRESS",
      { timeout: 8_000 },
    );
  });
});

test.describe("TC-E2E-CD-010: WebSocket 切断/再接続", () => {
  test("WS 切断 → ConnectionIndicator「再接続中...」→ 再接続 → 「接続済み」の状態遷移を確認", async ({
    page,
  }) => {
    // -------------------------------------------------------------------
    // Step 1: WS ルートを設定（実サーバーへ転送 + close() で強制切断可能に）
    // page.context().setOffline(true) は既存 WS を即断しないため、
    // wsClientRoute.close() で明示的に閉じる。
    // 再接続時にルートハンドラが再発火し、新規接続が自動転送される。
    // -------------------------------------------------------------------
    let wsClientRoute: WebSocketRoute | null = null;

    await page.routeWebSocket("ws://localhost:8000/ws", (ws: WebSocketRoute) => {
      ws.connectToServer(); // 実 WS サーバーへ双方向転送
      wsClientRoute = ws; // 最新のルートを追跡（再接続時に更新される）
    });

    // -------------------------------------------------------------------
    // Step 2: ページ遷移と初期 WS 接続待ち
    // -------------------------------------------------------------------
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // -------------------------------------------------------------------
    // Step 3: 初期状態「接続済み」を確認
    // ConnectionIndicator: <output aria-label="サーバーと接続済み">
    // -------------------------------------------------------------------
    await expect(page.locator('output[aria-label="サーバーと接続済み"]')).toBeVisible({
      timeout: 10_000,
    });

    // wsClientRoute は WS 接続完了後に設定済み
    expect(wsClientRoute).not.toBeNull();

    // -------------------------------------------------------------------
    // Step 4: WS ルートを強制 close（code 1001 = Going Away）
    // ブラウザ側の WebSocket に close イベントが届く
    // useWebSocketBus: onclose → setConnectionState("reconnecting") → scheduleReconnect(1000ms)
    // -------------------------------------------------------------------
    await (wsClientRoute as WebSocketRoute).close({ code: 1001, reason: "E2E test disconnect" });

    // -------------------------------------------------------------------
    // Step 5: ConnectionIndicator が「再接続中...」に遷移することを確認
    // aria-label="サーバーとの接続が切断されました。再接続中..."
    // -------------------------------------------------------------------
    await expect(page.locator('output[aria-label*="再接続中"]')).toBeVisible({ timeout: 8_000 });

    // -------------------------------------------------------------------
    // Step 6: ConnectionIndicator が「接続済み」に戻ることを確認
    // 再接続バックオフ BACKOFF_MS[0]=1000ms 後に routeWebSocket ハンドラが再発火し
    // 実 WS サーバーへ接続 → onopen → setConnectionState("connected")
    // -------------------------------------------------------------------
    await expect(page.locator('output[aria-label="サーバーと接続済み"]')).toBeVisible({
      timeout: 15_000,
    });
  });
});
