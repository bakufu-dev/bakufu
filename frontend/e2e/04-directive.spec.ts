/**
 * TC-E2E-CD-008: Directive 投入（受入基準 #11）— P0 必須
 *
 * VITE_EMPIRE_ID が設定済みで Empire に Room が存在する状態で
 * /directives/new にアクセスし Room 選択 → テキスト入力 → 送信すると
 * Task 一覧に新規 Task が追加される
 */
import { expect, test } from "@playwright/test";
import { API_BASE, ROOM_ID } from "./helpers";

test.describe("TC-E2E-CD-008: Directive 投入 (P0)", () => {
  test("Directive 投入フォームで Room 選択・テキスト入力・送信すると Task 一覧に遷移する", async ({
    page,
  }) => {
    await page.goto("/directives/new");
    await page.waitForLoadState("networkidle");

    // Directive 投入ページのタイトル
    await expect(page.getByRole("heading", { name: "Directive 投入" })).toBeVisible();

    // Room 選択ドロップダウン（E2E Test Room が選択肢に含まれる）
    const roomSelect = page.locator("#directive-room");
    await expect(roomSelect).toBeVisible();

    // E2E Test Room を選択
    await roomSelect.selectOption({ label: "E2E Test Room" });

    // Directive テキストを入力
    const directiveText = `E2E: Playwright 自動投入テスト ${Date.now()}`;
    await page.locator("#directive-text").fill(directiveText);

    // 送信前に Task 数を記録
    const tasksBefore = await page.request.get(
      `${API_BASE}/api/rooms/${ROOM_ID}/tasks`,
    );
    const taskCountBefore = (
      (await tasksBefore.json()) as { total: number }
    ).total;

    // Directive を投入する ボタンをクリック
    await page.getByRole("button", { name: "Directive を投入する" }).click();

    // 送信成功 → Task 一覧（/）に遷移する
    await page.waitForURL("/");
    await page.waitForLoadState("networkidle");

    // Task 一覧ページが表示される
    await expect(page.getByRole("heading", { name: "Task 一覧" })).toBeVisible();

    // API で Task 数が増えているか確認
    const tasksAfter = await page.request.get(
      `${API_BASE}/api/rooms/${ROOM_ID}/tasks`,
    );
    const taskCountAfter = (
      (await tasksAfter.json()) as { total: number }
    ).total;

    expect(taskCountAfter).toBeGreaterThan(taskCountBefore);
  });

  test("Room 未選択のまま送信するとバリデーションエラーが表示される", async ({ page }) => {
    await page.goto("/directives/new");
    await page.waitForLoadState("networkidle");

    // Room を選択せずにテキストだけ入力
    await page.locator("#directive-text").fill("テスト指示");

    // 送信
    await page.getByRole("button", { name: "Directive を投入する" }).click();

    // Room 選択エラーが表示される（InlineError: "Room を選択してください。" — strict mode対策でピリオド付き）
    await expect(page.getByText("Room を選択してください。")).toBeVisible();
    // ページ遷移しない
    expect(page.url()).toContain("/directives/new");
  });

  test("テキスト空のまま送信するとバリデーションエラーが表示される", async ({ page }) => {
    await page.goto("/directives/new");
    await page.waitForLoadState("networkidle");

    const roomSelect = page.locator("#directive-room");
    await roomSelect.selectOption({ label: "E2E Test Room" });

    // テキスト空のまま送信
    await page.getByRole("button", { name: "Directive を投入する" }).click();

    // テキスト空エラーが表示される
    await expect(page.getByText("Directive テキストを入力してください")).toBeVisible();
    expect(page.url()).toContain("/directives/new");
  });
});
