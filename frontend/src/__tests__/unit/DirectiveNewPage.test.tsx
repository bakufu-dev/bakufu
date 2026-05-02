import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// TC-UT-CD-015: VITE_EMPIRE_ID 未設定 → MSG-CD-UI-001 表示（§確定 E / R1-7）
// DirectiveNewPage は module level で empireId を読む → vi.resetModules() + 動的 import 必須
import { cleanup, render, screen } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("TC-UT-CD-015: DirectiveNewPage — VITE_EMPIRE_ID 未設定（MSG-CD-UI-001）", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("VITE_EMPIRE_ID", "");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    cleanup();
  });

  it("VITE_EMPIRE_ID が空のとき MSG-CD-UI-001 が表示され、フォームが非表示になる", async () => {
    // module reset 後に動的 import → module level の empireId が空で評価される
    const { DirectiveNewPage } = await import("../../pages/DirectiveNewPage");

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });

    render(
      React.createElement(
        QueryClientProvider,
        { client: qc },
        React.createElement(
          MemoryRouter,
          { initialEntries: ["/directives/new"] },
          React.createElement(DirectiveNewPage),
        ),
      ),
    );

    // MSG-CD-UI-001 の冒頭文字列が DOM に存在する
    expect(screen.getByText(/VITE_EMPIRE_ID が設定されていません。/)).toBeInTheDocument();

    // フォームは存在しない
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });
});
