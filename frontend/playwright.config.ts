// Playwright E2E テスト設定
// TC-E2E-CD-001~011: ceo-dashboard feature E2E
// 実行環境: bakufu-frontend-1 コンテナ内（chromium /usr/bin/chromium + socat port-forward localhost:8000→backend）

import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  retries: 0,
  workers: 1, // シリアル実行（DB 共有のため並列禁止）
  reporter: [
    ["list"],
    [
      "html",
      {
        open: "never",
        outputFolder: "playwright-report",
      },
    ],
    [
      "json",
      {
        outputFile: "playwright-results.json",
      },
    ],
  ],
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    // system Chromium（/usr/bin/chromium）を使用。Playwright bundled browsers は使わない
    launchOptions: {
      executablePath: "/usr/bin/chromium",
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    },
  },
  projects: [
    {
      name: "chromium",
      use: {},
    },
  ],
});
