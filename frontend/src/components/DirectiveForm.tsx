// DirectiveForm — Room 選択 + Directive テキスト入力フォーム
// 詳細設計書 §確定 E: Room 未選択・テキスト空のクライアントバリデーション
// 詳細設計書 §確定 H: Tab 順序（select → textarea → submit）

import type React from "react";
import { useState } from "react";
import type { ApiError, RoomResponse } from "../api/types";
import { InlineError } from "./InlineError";

interface DirectiveFormProps {
  rooms: RoomResponse[];
  onSubmit: (roomId: string, text: string) => { validationError: string } | null;
  isSubmitting: boolean;
  error: ApiError | null | undefined;
}

export function DirectiveForm({
  rooms,
  onSubmit,
  isSubmitting,
  error,
}: DirectiveFormProps): React.ReactElement {
  const [selectedRoomId, setSelectedRoomId] = useState("");
  const [text, setText] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValidationError(null);

    // Room 未選択バリデーション（§確定 E / MSG-CD-UI-003）
    if (!selectedRoomId) {
      setValidationError("Room を選択してください。");
      return;
    }

    // テキスト空バリデーション（§確定 E / MSG-CD-UI-004）
    if (!text.trim()) {
      setValidationError("Directive テキストを入力してください。");
      return;
    }

    const result = onSubmit(selectedRoomId, text.trim());
    if (result) {
      setValidationError(result.validationError);
    }
  }

  const isDisabled = isSubmitting;
  const buttonAriaProps = isDisabled
    ? { "aria-disabled": true as const, "aria-busy": true as const }
    : {};

  return (
    <form onSubmit={handleSubmit} className="space-y-5" noValidate>
      {/* エラー表示 */}
      {(error || validationError) && <InlineError error={validationError ?? error} />}

      {/* Room 選択（§確定 H: Tab 順序 ①）*/}
      <div>
        <label htmlFor="directive-room" className="block text-sm font-medium text-gray-700 mb-1">
          Room
          <span className="text-red-600 ml-1" aria-hidden="true">
            *
          </span>
        </label>
        <select
          id="directive-room"
          value={selectedRoomId}
          onChange={(e) => setSelectedRoomId(e.target.value)}
          disabled={isDisabled}
          required
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed bg-white"
        >
          <option value="">-- Room を選択してください --</option>
          {rooms.map((room) => (
            <option key={room.id} value={room.id}>
              {room.name}
            </option>
          ))}
        </select>
      </div>

      {/* テキストエリア（§確定 H: Tab 順序 ②）*/}
      <div>
        <label htmlFor="directive-text" className="block text-sm font-medium text-gray-700 mb-1">
          Directive テキスト
          <span className="text-red-600 ml-1" aria-hidden="true">
            *
          </span>
        </label>
        <textarea
          id="directive-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={isDisabled}
          placeholder="CEO の指示を入力してください..."
          rows={6}
          required
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed resize-y"
        />
      </div>

      {/* 送信ボタン（§確定 H: Tab 順序 ③）*/}
      <button
        type="submit"
        disabled={isDisabled}
        {...buttonAriaProps}
        className="w-full px-4 py-2 text-sm font-semibold text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {isSubmitting ? "送信中..." : "Directive を投入する"}
      </button>
    </form>
  );
}
