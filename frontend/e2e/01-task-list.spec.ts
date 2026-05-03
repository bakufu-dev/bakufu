/**
 * TC-E2E-CD-001: Task 一覧表示（受入基準 #1）
 *
 * 前提: Room に PENDING / IN_PROGRESS / DONE の各 status Task が存在する
 * 期待: 3 件以上のタスクカードが表示され、status バッジが表示される
 *
 * NOTE BUG-E2E-001: バックエンド GET /api/rooms/{id}/tasks は directive_text を
 * 返さない（frontend の TaskResponse 型との乖離）。TaskCard.truncateText(undefined)
 * が TypeError を発生させていた。修正: types.ts で directive_text を optional
 * にし、truncateText を null-safe に変更した。
 */
import { expect, test } from "@playwright/test";
import { TASK_DONE_ID, TASK_INPROG_ID, TASK_PENDING_ID } from "./helpers";

test.describe("TC-E2E-CD-001: Task 一覧表示", () => {
  test("Task 一覧に PENDING / IN_PROGRESS / DONE の Task カードが表示される", async ({ page }) => {
    await page.goto("/");
    // ローディング完了を待つ
    await page.waitForLoadState("networkidle");

    // Task 一覧 h1 が表示される
    await expect(page.getByRole("heading", { name: "Task 一覧" })).toBeVisible();

    // StatusBadge の aria-label 確認（span 限定で strict mode 回避）
    // NOTE: getByText は複数タスク存在時に strict mode 違反になるため aria-label locator を使用
    await expect(page.locator('span[aria-label="PENDING"]').first()).toBeVisible();
    await expect(page.locator('span[aria-label="IN_PROGRESS"]').first()).toBeVisible();
    await expect(page.locator('span[aria-label="DONE"]').first()).toBeVisible();

    // Task カードがリンク要素として存在する
    const taskHrefPending = `/tasks/${TASK_PENDING_ID}`;
    await expect(page.locator(`a[href="${taskHrefPending}"]`)).toBeVisible();
  });
});
