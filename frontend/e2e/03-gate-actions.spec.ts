/**
 * TC-E2E-CD-005: Gate 承認（受入基準 #5 #7）— P0 必須
 * TC-E2E-CD-006: Gate 差し戻し（受入基準 #8 #9）— P0 必須
 * TC-E2E-CD-007: 二重送信防止（受入基準 #10）
 */
import { expect, test } from "@playwright/test";
import {
  API_BASE,
  GATE_APPROVE_ID,
  GATE_REJECT_ID,
  GATE_REVIEW_ID,
  TASK_APPROVE_ID,
  TASK_REJECT_ID,
} from "./helpers";

test.describe("TC-E2E-CD-005: Gate 承認 (P0)", () => {
  test("Gate 詳細画面で承認すると decision が APPROVED になりページが遷移する", async ({
    page,
  }) => {
    // Task 詳細 → Gate リンク経由でナビゲートすることで navigate(-1) が動作する
    await page.goto(`/tasks/${TASK_APPROVE_ID}`);
    await page.waitForLoadState("networkidle");

    // Gate レビューへのリンクをクリック
    await page.getByRole("link", { name: "Gate レビューへ →" }).click();
    await page.waitForLoadState("networkidle");

    // Gate 詳細ページが表示される
    await expect(page.getByRole("heading", { name: "外部レビュー Gate" })).toBeVisible();

    // Deliverable スナップショット本文が表示される（受入基準 #7: Markdown 確認後に承認）
    await expect(page.getByText("E2E Test Deliverable")).toBeVisible();

    // 現在 decision は PENDING
    await expect(page.getByLabel("PENDING")).toBeVisible();

    // 承認する ボタンをクリック
    await page.getByRole("button", { name: "承認する" }).click();

    // navigate(-1) で Task 詳細ページに戻る
    await page.waitForURL(/\/tasks\//);
    await page.waitForLoadState("networkidle");

    // Task 詳細ページが表示される
    await expect(page.getByRole("heading", { name: "Task 詳細" })).toBeVisible();

    // API で Gate の decision が APPROVED になっているか確認
    const resp = await page.request.get(`${API_BASE}/api/gates/${GATE_APPROVE_ID}`);
    expect(resp.ok()).toBe(true);
    const gate = (await resp.json()) as { decision: string };
    expect(gate.decision).toBe("APPROVED");
  });
});

test.describe("TC-E2E-CD-006: Gate 差し戻し (P0)", () => {
  test("feedback_text 入力後に差し戻すと decision が REJECTED になる", async ({ page }) => {
    await page.goto(`/tasks/${TASK_REJECT_ID}`);
    await page.waitForLoadState("networkidle");

    await page.getByRole("link", { name: "Gate レビューへ →" }).click();
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "外部レビュー Gate" })).toBeVisible();

    // feedback_text を textarea に入力（id="reject-feedback"）
    await page.locator("#reject-feedback").fill("E2E テスト: 差し戻し理由");

    // 差し戻す ボタンをクリック
    await page.getByRole("button", { name: "差し戻す" }).click();

    // navigate(-1) で Task 詳細ページに戻る
    await page.waitForURL(/\/tasks\//);
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "Task 詳細" })).toBeVisible();

    // API で Gate の decision が REJECTED になっているか確認
    const resp = await page.request.get(`${API_BASE}/api/gates/${GATE_REJECT_ID}`);
    expect(resp.ok()).toBe(true);
    const gate = (await resp.json()) as { decision: string };
    expect(gate.decision).toBe("REJECTED");
  });

  test("feedback_text が空のまま差し戻しを試みると UI エラーが表示されサブミットされない", async ({
    page,
  }) => {
    // GATE_REVIEW_ID は PENDING のまま残しておく（gate_approve/reject とは別ゲート）
    await page.goto(`/gates/${GATE_REVIEW_ID}`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "外部レビュー Gate" })).toBeVisible();

    // textarea を空のままにして差し戻すボタンをクリック
    await page.getByRole("button", { name: "差し戻す" }).click();

    // バリデーションエラーが表示される（InlineError コンポーネント）
    await expect(page.getByText("差し戻し理由を入力してください")).toBeVisible();
    // URL は /gates/ のまま（ページ遷移しない）
    expect(page.url()).toContain("/gates/");
  });
});

test.describe("TC-E2E-CD-007: 二重送信防止", () => {
  test("承認ボタンクリック後は isSubmitting=true でボタンが disabled になる", async ({ page }) => {
    // GATE_REVIEW_ID は PENDING のまま (005, 006 では approve/reject に使っていない)
    // navigate(-1) が機能するよう Task 詳細 → Gate リンク経由でナビゲート
    await page.goto(`/tasks/${TASK_APPROVE_ID}`);
    await page.waitForLoadState("networkidle");

    // Wait for gate to be in PENDING state (it's APPROVED after test 005 — need reset)
    // Note: Tests 005 already APPROVED GATE_APPROVE_ID. TASK_APPROVE_ID gate was used there.
    // Here we use TASK_REVIEW_ID which has GATE_REVIEW_ID (still PENDING)
    // TASK_REVIEW_ID = TASK_APPROVE_ID: same task? No. Let's check helpers.
    // TASK_APPROVE_ID = ...000055, TASK_REVIEW_ID = ...000054
    // Using TASK_REVIEW_ID which links to GATE_REVIEW_ID (still PENDING after tests 005/006)

    // Actually TASK_APPROVE_ID was already used by TC-E2E-CD-005 — its gate is APPROVED.
    // Navigate to TASK_REVIEW_ID (task ...000054) which has GATE_REVIEW_ID (PENDING)
    await page.goto("/tasks/e2e00000-0000-0000-0000-000000000054");
    await page.waitForLoadState("networkidle");

    // ローカル API は高速すぎて isPending=true の瞬間を捕捉できないため、
    // page.route() で approve レスポンスを 1 秒遅延させる
    await page.route(`**/api/gates/${GATE_REVIEW_ID}/approve`, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await route.continue();
    });

    // Gate レビューへのリンクをクリック（navigate(-1) の履歴を作る）
    await page.getByRole("link", { name: "Gate レビューへ →" }).click();
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "外部レビュー Gate" })).toBeVisible();

    const approveBtn = page.getByRole("button", { name: "承認する" });
    await expect(approveBtn).toBeEnabled();

    // ボタンをクリック（遅延 route が適用されるため isPending が続く）
    await approveBtn.click();

    // isSubmitting=true → 全ボタンが "処理中..." かつ disabled になる（GateActionForm §確定 D）
    // NOTE: isSubmitting は approveMutation|rejectMutation|cancelMutation で共有されるため
    // 全ボタンが同時に "処理中..." になる。承認ボタン（bg-green-600）を特定して確認する
    const submittingApproveBtn = page.locator("button.bg-green-600");
    await expect(submittingApproveBtn).toBeVisible();
    await expect(submittingApproveBtn).toBeDisabled();
    // aria-busy=true を確認（二重送信防止の追加検証）
    await expect(submittingApproveBtn).toHaveAttribute("aria-busy", "true");

    // 遅延後に承認完了 → navigate(-1) で Task 詳細ページへ遷移
    await page.waitForURL(/\/tasks\//, { timeout: 15000 });
  });
});
