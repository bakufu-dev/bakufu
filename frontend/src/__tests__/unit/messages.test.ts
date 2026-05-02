import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// TC-UT-CD-018~023: 確定文言照合テスト
// MSG-CD-UI-001~006 の文言を DOM レンダリングで検証する
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { GateDetailResponse, RoomResponse } from "../../api/types";
import { ConnectionIndicator } from "../../components/ConnectionIndicator";
import { DirectiveForm } from "../../components/DirectiveForm";
import { GateActionForm } from "../../components/GateActionForm";
import { InlineError } from "../../components/InlineError";

const PENDING_GATE: GateDetailResponse = {
  id: "gate-1",
  task_id: "task-1",
  stage_id: "stage-1",
  decision: "PENDING",
  deliverable_snapshot: {
    id: "snap-1",
    body_markdown: "",
    acceptance_criteria: "",
    created_at: "2024-01-01T00:00:00Z",
  },
  audit_trail: [],
  required_gate_roles: [],
  created_at: "2024-01-01T00:00:00Z",
};

const ROOMS: RoomResponse[] = [{ id: "r1", name: "Room A", workflow_id: "wf-1" }];

// TC-UT-CD-018: MSG-CD-UI-001 = VITE_EMPIRE_ID 未設定メッセージ
describe("TC-UT-CD-018: MSG-CD-UI-001 — VITE_EMPIRE_ID 未設定文言", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("VITE_EMPIRE_ID", "");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    cleanup();
  });

  it("完全一致文言: VITE_EMPIRE_ID が設定されていません。frontend/.env に VITE_EMPIRE_ID=<uuid> を追加してください。", async () => {
    const { DirectiveNewPage } = await import("../../pages/DirectiveNewPage");
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      React.createElement(
        QueryClientProvider,
        { client: qc },
        React.createElement(MemoryRouter, null, React.createElement(DirectiveNewPage)),
      ),
    );

    expect(
      screen.getByText(
        "VITE_EMPIRE_ID が設定されていません。frontend/.env に VITE_EMPIRE_ID=<uuid> を追加してください。",
      ),
    ).toBeInTheDocument();
  });
});

// TC-UT-CD-019: MSG-CD-UI-002 = 差し戻し理由必須
describe("TC-UT-CD-019: MSG-CD-UI-002 — 差し戻し理由入力必須文言", () => {
  it("完全一致文言: 差し戻し理由を入力してください。", async () => {
    const user = userEvent.setup();
    const onReject = vi
      .fn()
      .mockReturnValue({ validationError: "差し戻し理由を入力してください。" });

    render(
      React.createElement(GateActionForm, {
        gate: PENDING_GATE,
        deliverableContainerId: "del",
        onApprove: vi.fn(),
        onReject,
        onCancel: vi.fn(),
        isSubmitting: false,
        error: null,
      }),
    );

    const btn = screen.getByRole("button", { name: "差し戻す" });
    await user.click(btn);

    expect(screen.getByText("差し戻し理由を入力してください。")).toBeInTheDocument();
  });
});

// TC-UT-CD-020: MSG-CD-UI-003 = Room 未選択警告
describe("TC-UT-CD-020: MSG-CD-UI-003 — Room 未選択文言", () => {
  it("完全一致文言: Room を選択してください。", async () => {
    const user = userEvent.setup();

    render(
      React.createElement(DirectiveForm, {
        rooms: ROOMS,
        onSubmit: vi.fn(),
        isSubmitting: false,
        error: null,
      }),
    );

    // Room 未選択のまま送信
    await user.click(screen.getByRole("button", { name: /Directive を投入する/ }));

    expect(screen.getByText("Room を選択してください。")).toBeInTheDocument();
  });
});

// TC-UT-CD-021: MSG-CD-UI-004 = テキスト空警告
describe("TC-UT-CD-021: MSG-CD-UI-004 — Directive テキスト空文言", () => {
  it("完全一致文言: Directive テキストを入力してください。", async () => {
    const user = userEvent.setup();

    render(
      React.createElement(DirectiveForm, {
        rooms: ROOMS,
        onSubmit: vi.fn(),
        isSubmitting: false,
        error: null,
      }),
    );

    // Room を選択してテキストを空のまま送信
    await user.selectOptions(screen.getByLabelText(/Room/), "r1");
    await user.click(screen.getByRole("button", { name: /Directive を投入する/ }));

    expect(screen.getByText("Directive テキストを入力してください。")).toBeInTheDocument();
  });
});

// TC-UT-CD-022: MSG-CD-UI-005 = 再接続中 ariaLabel
describe("TC-UT-CD-022: MSG-CD-UI-005 — 再接続中 ariaLabel 文言", () => {
  it("完全一致文言: サーバーとの接続が切断されました。再接続中...", () => {
    const { container } = render(
      React.createElement(ConnectionIndicator, { state: "reconnecting" }),
    );

    const output = container.querySelector("output");
    expect(output?.getAttribute("aria-label")).toBe(
      "サーバーとの接続が切断されました。再接続中...",
    );
  });
});

// TC-UT-CD-023: MSG-CD-UI-006 = ネットワーク不達メッセージ
describe("TC-UT-CD-023: MSG-CD-UI-006 — ネットワーク不達文言", () => {
  it("完全一致文言: サーバーに接続できません。バックエンドが起動しているか確認してください。", () => {
    // InlineError に Error オブジェクトを渡すと MSG-CD-UI-006 が表示される
    render(
      React.createElement(InlineError, {
        error: new Error("Network error"),
      }),
    );

    expect(
      screen.getByText("サーバーに接続できません。バックエンドが起動しているか確認してください。"),
    ).toBeInTheDocument();
  });
});
