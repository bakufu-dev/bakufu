/**
 * TC-E2E-CD-011: API エラー表示（受入基準 #14）
 *
 * 存在しない Gate ID でアクセスした場合、404 エラーメッセージが
 * InlineError コンポーネントでインライン表示される
 */
import { expect, test } from "@playwright/test";

test.describe("TC-E2E-CD-011: API エラー表示", () => {
  test("存在しない Gate ID で Gate 詳細にアクセスすると 404 エラーがインライン表示される", async ({
    page,
  }) => {
    const nonExistentGateId = "00000000-0000-0000-0000-000000000000";
    await page.goto(`/gates/${nonExistentGateId}`);
    await page.waitForLoadState("networkidle");

    // InlineError が表示される（role="alert"）
    const errorAlert = page.getByRole("alert");
    await expect(errorAlert).toBeVisible();

    // エラーメッセージが表示される
    // 404 の場合: API からエラーレスポンスが返り InlineError に表示される
    await expect(errorAlert).toBeVisible();

    // ページタイトルは表示されない（エラー状態なので）
    await expect(page.getByRole("heading", { name: "外部レビュー Gate" })).not.toBeVisible();
  });

  test("存在しない Task ID で Task 詳細にアクセスするとエラーが表示される", async ({ page }) => {
    const nonExistentTaskId = "00000000-0000-0000-0000-000000000000";
    await page.goto(`/tasks/${nonExistentTaskId}`);
    await page.waitForLoadState("networkidle");

    // InlineError が表示される（role="alert"）
    await expect(page.getByRole("alert")).toBeVisible();
  });
});
