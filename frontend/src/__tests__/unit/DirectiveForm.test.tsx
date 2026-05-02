// TC-UT-CD-013: Room 未選択 → MSG-CD-UI-003（R1-7 / §確定 E）
// TC-UT-CD-014: テキスト空 → MSG-CD-UI-004（§確定 E）
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { RoomResponse } from "../../api/types";
import { DirectiveForm } from "../../components/DirectiveForm";

const ROOMS: RoomResponse[] = [
  { id: "room-1", name: "Room Alpha", workflow_id: "wf-1" },
  { id: "room-2", name: "Room Beta", workflow_id: "wf-1" },
];

describe("TC-UT-CD-013: DirectiveForm — Room 未選択バリデーション（MSG-CD-UI-003）", () => {
  it("Room 未選択のまま送信 → onSubmit 未呼び出し + MSG-CD-UI-003 表示", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<DirectiveForm rooms={ROOMS} onSubmit={onSubmit} isSubmitting={false} error={null} />);

    // テキストを入力（Room は未選択のまま）
    const textarea = screen.getByLabelText(/Directive テキスト/);
    await user.type(textarea, "CEO の指示内容");

    // 送信ボタンをクリック
    const submitBtn = screen.getByRole("button", { name: /Directive を投入する/ });
    await user.click(submitBtn);

    // onSubmit が呼ばれない
    expect(onSubmit).not.toHaveBeenCalled();

    // エラーメッセージ表示（MSG-CD-UI-003）
    expect(screen.getByText("Room を選択してください。")).toBeInTheDocument();
  });
});

describe("TC-UT-CD-014: DirectiveForm — テキスト空バリデーション（MSG-CD-UI-004）", () => {
  it("Room 選択済み・テキスト未入力で送信 → onSubmit 未呼び出し + MSG-CD-UI-004 表示", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<DirectiveForm rooms={ROOMS} onSubmit={onSubmit} isSubmitting={false} error={null} />);

    // Room を選択
    const select = screen.getByLabelText(/Room/);
    await user.selectOptions(select, "room-1");

    // テキストは未入力のまま送信
    const submitBtn = screen.getByRole("button", { name: /Directive を投入する/ });
    await user.click(submitBtn);

    expect(onSubmit).not.toHaveBeenCalled();

    // エラーメッセージ表示（MSG-CD-UI-004）
    expect(screen.getByText("Directive テキストを入力してください。")).toBeInTheDocument();
  });

  it("Room 選択 + テキスト入力で送信 → onSubmit が呼ばれる", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockReturnValue(null);

    render(<DirectiveForm rooms={ROOMS} onSubmit={onSubmit} isSubmitting={false} error={null} />);

    const select = screen.getByLabelText(/Room/);
    await user.selectOptions(select, "room-1");

    const textarea = screen.getByLabelText(/Directive テキスト/);
    await user.type(textarea, "CEO の重要指示");

    const submitBtn = screen.getByRole("button", { name: /Directive を投入する/ });
    await user.click(submitBtn);

    expect(onSubmit).toHaveBeenCalledWith("room-1", "CEO の重要指示");
  });
});
