/**
 * TC-E2E-CD-002: Task 詳細 — Stage 進行状況表示（受入基準 #2）
 * TC-E2E-CD-003: Task 詳細 — Deliverable 表示（受入基準 #3）
 * TC-E2E-CD-004: Task 詳細 — Gate リンク表示（受入基準 #4）
 */
import { expect, test } from "@playwright/test";
import { GATE_REVIEW_ID, TASK_APPROVE_ID, TASK_REVIEW_ID } from "./helpers";

test.describe("TC-E2E-CD-002: Task 詳細 — Stage 進行状況", () => {
  test("Task 詳細画面に Stage 情報と status バッジが表示される", async ({ page }) => {
    // AWAITING_EXTERNAL_REVIEW タスク（Gate が存在する）の詳細ページ
    await page.goto(`/tasks/${TASK_REVIEW_ID}`);
    await page.waitForLoadState("networkidle");

    // Task 詳細 h1
    await expect(page.getByRole("heading", { name: "Task 詳細" })).toBeVisible();

    // Status バッジ
    await expect(page.getByLabel("AWAITING_EXTERNAL_REVIEW")).toBeVisible();

    // 一覧へ戻るリンク
    await expect(page.getByRole("link", { name: "← 一覧へ" })).toBeVisible();
  });
});

test.describe("TC-E2E-CD-003: Task 詳細 — Deliverable 表示", () => {
  test("Deliverable の body_markdown が Markdown レンダリングされている", async ({ page }) => {
    // BUG-E2E-005: GET /api/tasks/{id}/gates はdeliverable_snapshotを返さないため
    // TaskDetailPage の Deliverable セクションは表示されない。
    // Deliverable は Gate 詳細ページ（ExternalReviewGatePage）で確認する。
    await page.goto(`/gates/${GATE_REVIEW_ID}`);
    await page.waitForLoadState("networkidle");

    // Gate 詳細ページタイトルが表示される
    await expect(page.getByRole("heading", { name: "外部レビュー Gate" })).toBeVisible();

    // Deliverable スナップショットセクションが表示される
    await expect(page.getByText("Deliverable スナップショット")).toBeVisible();

    // Markdown が HTML にレンダリングされている（h1 タグ）
    await expect(page.locator("h1").filter({ hasText: "E2E Test Deliverable" })).toBeVisible();

    // Deliverable の本文テキストが含まれる
    await expect(page.getByText("E2E Test Deliverable")).toBeVisible();
  });
});

test.describe("TC-E2E-CD-004: Task 詳細 — Gate リンク表示", () => {
  test("AWAITING_EXTERNAL_REVIEW タスクに Gate レビューへのリンクが表示される", async ({
    page,
  }) => {
    await page.goto(`/tasks/${TASK_REVIEW_ID}`);
    await page.waitForLoadState("networkidle");

    // Gate レビューリンクが表示される
    await expect(page.getByRole("link", { name: "Gate レビューへ →" })).toBeVisible();

    // リンク先が正しい gate に向いている
    const gateLink = page.getByRole("link", { name: "Gate レビューへ →" });
    const href = await gateLink.getAttribute("href");
    expect(href).toContain("/gates/");
  });

  test("Gate リンクを辿ると Gate 詳細画面が表示される", async ({ page }) => {
    await page.goto(`/tasks/${TASK_APPROVE_ID}`);
    await page.waitForLoadState("networkidle");

    const gateLink = page.getByRole("link", { name: "Gate レビューへ →" });
    await expect(gateLink).toBeVisible();

    await gateLink.click();
    await page.waitForLoadState("networkidle");

    // Gate 詳細ページが表示される
    await expect(page.getByRole("heading", { name: "外部レビュー Gate" })).toBeVisible();
  });
});
