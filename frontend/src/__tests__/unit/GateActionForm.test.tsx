// TC-UT-CD-010: reject — feedback_text 空 → バリデーションエラー（R1-3 / MSG-CD-UI-002）
// TC-UT-CD-011: isSubmitting=true → 全ボタン disabled（R1-2）
// TC-UT-CD-012: decision != PENDING → readonly 表示（§確定 D）
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { GateDetailResponse } from "../../api/types";
import { GateActionForm } from "../../components/GateActionForm";

const PENDING_GATE: GateDetailResponse = {
  id: "gate-1",
  task_id: "task-1",
  stage_id: "stage-1",
  decision: "PENDING",
  deliverable_snapshot: {
    id: "snap-1",
    body_markdown: "# Deliverable",
    acceptance_criteria: "Must do X",
    created_at: "2024-01-01T00:00:00Z",
  },
  audit_trail: [],
  required_gate_roles: [],
  created_at: "2024-01-01T00:00:00Z",
};

const APPROVED_GATE: GateDetailResponse = {
  ...PENDING_GATE,
  decision: "APPROVED",
};

function renderForm(overrides: Partial<Parameters<typeof GateActionForm>[0]> = {}) {
  const props = {
    gate: PENDING_GATE,
    deliverableContainerId: "deliverable",
    onApprove: vi.fn(),
    onReject: vi.fn().mockReturnValue(null),
    onCancel: vi.fn(),
    isSubmitting: false,
    error: null,
    ...overrides,
  };
  render(<GateActionForm {...props} />);
  return props;
}

describe("TC-UT-CD-010: GateActionForm — reject 空入力バリデーション（R1-3 / MSG-CD-UI-002）", () => {
  it("feedback_text 未入力で reject ボタンをクリック → onReject 未呼び出し + エラーメッセージ表示", async () => {
    const user = userEvent.setup();
    const onReject = vi
      .fn()
      .mockReturnValue({ validationError: "差し戻し理由を入力してください。" });

    render(
      <GateActionForm
        gate={PENDING_GATE}
        deliverableContainerId="deliverable"
        onApprove={vi.fn()}
        onReject={onReject}
        onCancel={vi.fn()}
        isSubmitting={false}
        error={null}
      />,
    );

    const rejectButton = screen.getByRole("button", { name: "差し戻す" });
    await user.click(rejectButton);

    // onReject は呼ばれる（空テキストで呼んでバリデーションエラーを返す）
    expect(onReject).toHaveBeenCalledWith("");

    // DOM にエラーメッセージが表示される
    expect(screen.getByText("差し戻し理由を入力してください。")).toBeInTheDocument();
  });
});

describe("TC-UT-CD-011: GateActionForm — isSubmitting=true → 全ボタン disabled（R1-2）", () => {
  it("isSubmitting=true のとき approve / reject / cancel ボタン全てが disabled", () => {
    renderForm({ isSubmitting: true });

    const buttons = screen.getAllByRole("button");
    for (const btn of buttons) {
      expect(btn).toBeDisabled();
    }
  });

  it("isSubmitting=true のとき aria-disabled と aria-busy が付与される", () => {
    renderForm({ isSubmitting: true });

    const buttons = screen.getAllByRole("button");
    for (const btn of buttons) {
      expect(btn).toHaveAttribute("aria-disabled", "true");
      expect(btn).toHaveAttribute("aria-busy", "true");
    }
  });
});

describe("TC-UT-CD-012: GateActionForm — decision != PENDING → readonly 表示", () => {
  it("decision=APPROVED のとき操作ボタンが DOM に存在しない", () => {
    render(
      <GateActionForm
        gate={APPROVED_GATE}
        deliverableContainerId="deliverable"
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onCancel={vi.fn()}
        isSubmitting={false}
        error={null}
      />,
    );

    // ボタンが存在しない
    expect(screen.queryByRole("button", { name: /承認/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /差し戻/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /キャンセル/ })).toBeNull();

    // readonly 表示: "APPROVED" テキストが表示される
    expect(screen.getByText("APPROVED")).toBeInTheDocument();
  });

  it("decision=REJECTED のとき操作ボタンが DOM に存在しない", () => {
    render(
      <GateActionForm
        gate={{ ...PENDING_GATE, decision: "REJECTED" }}
        deliverableContainerId="deliverable"
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onCancel={vi.fn()}
        isSubmitting={false}
        error={null}
      />,
    );

    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("REJECTED")).toBeInTheDocument();
  });
});
