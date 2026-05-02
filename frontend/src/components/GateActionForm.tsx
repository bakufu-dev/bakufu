// GateActionForm — approve / reject / cancel の操作フォーム
// 詳細設計書 §確定 D: isSubmitting, クライアントバリデーション
// 詳細設計書 §確定 H: aria-disabled, aria-busy, aria-describedby

import type React from "react";
import { useState } from "react";
import type { ApiError, GateDetailResponse } from "../api/types";
import { InlineError } from "./InlineError";

interface GateActionFormProps {
  gate: GateDetailResponse;
  /** deliverable コンテナの ID（aria-describedby で参照する）*/
  deliverableContainerId: string;
  onApprove: (comment?: string) => void;
  onReject: (feedbackText: string) => { validationError: string } | null;
  onCancel: (reason?: string) => void;
  isSubmitting: boolean;
  error: ApiError | null | undefined;
}

export function GateActionForm({
  gate,
  deliverableContainerId,
  onApprove,
  onReject,
  onCancel,
  isSubmitting,
  error,
}: GateActionFormProps): React.ReactElement {
  const [comment, setComment] = useState("");
  const [feedbackText, setFeedbackText] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  // PENDING でない Gate は readonly 表示（§確定 D 凍結）
  if (gate.decision !== "PENDING") {
    return (
      <div className="rounded-md border border-gray-200 bg-gray-50 p-4">
        <p className="text-sm font-medium text-gray-700">
          この Gate は既に操作済みです（
          <strong>{gate.decision}</strong>）。
        </p>
      </div>
    );
  }

  function handleApprove() {
    setValidationError(null);
    onApprove(comment.trim() || undefined);
  }

  function handleReject() {
    setValidationError(null);
    const result = onReject(feedbackText);
    if (result) {
      setValidationError(result.validationError);
    }
  }

  function handleCancel() {
    setValidationError(null);
    onCancel(cancelReason.trim() || undefined);
  }

  const isDisabled = isSubmitting;
  const buttonAriaProps = isDisabled
    ? { "aria-disabled": true as const, "aria-busy": true as const }
    : {};

  return (
    <div className="space-y-5">
      {/* エラー表示 */}
      {(error || validationError) && <InlineError error={validationError ?? error} />}

      {/* 承認セクション */}
      <section className="rounded-md border border-green-200 bg-green-50 p-4 space-y-3">
        <h3 className="text-sm font-semibold text-green-800">承認</h3>
        <div>
          <label htmlFor="approve-comment" className="block text-xs font-medium text-gray-700 mb-1">
            コメント（任意）
          </label>
          <textarea
            id="approve-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={isDisabled}
            placeholder="承認コメントを入力（省略可）"
            rows={2}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>
        <button
          type="button"
          onClick={handleApprove}
          disabled={isDisabled}
          aria-describedby={deliverableContainerId}
          {...buttonAriaProps}
          className="px-4 py-2 text-sm font-semibold text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-green-500"
        >
          {isSubmitting ? "処理中..." : "承認する"}
        </button>
      </section>

      {/* 差し戻しセクション */}
      <section className="rounded-md border border-orange-200 bg-orange-50 p-4 space-y-3">
        <h3 className="text-sm font-semibold text-orange-800">差し戻し</h3>
        <div>
          <label htmlFor="reject-feedback" className="block text-xs font-medium text-gray-700 mb-1">
            差し戻し理由
            <span className="text-red-600 ml-1" aria-hidden="true">
              *
            </span>
          </label>
          <textarea
            id="reject-feedback"
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            disabled={isDisabled}
            placeholder="差し戻し理由を入力してください（必須）"
            rows={3}
            required
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>
        <button
          type="button"
          onClick={handleReject}
          disabled={isDisabled}
          aria-describedby={deliverableContainerId}
          {...buttonAriaProps}
          className="px-4 py-2 text-sm font-semibold text-white bg-orange-600 rounded-md hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-orange-500"
        >
          {isSubmitting ? "処理中..." : "差し戻す"}
        </button>
      </section>

      {/* キャンセルセクション */}
      <section className="rounded-md border border-gray-200 bg-gray-50 p-4 space-y-3">
        <h3 className="text-sm font-semibold text-gray-700">キャンセル</h3>
        <div>
          <label htmlFor="cancel-reason" className="block text-xs font-medium text-gray-700 mb-1">
            キャンセル理由（任意）
          </label>
          <input
            id="cancel-reason"
            type="text"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            disabled={isDisabled}
            placeholder="キャンセル理由を入力（省略可）"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-500 disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>
        <button
          type="button"
          onClick={handleCancel}
          disabled={isDisabled}
          aria-describedby={deliverableContainerId}
          {...buttonAriaProps}
          className="px-4 py-2 text-sm font-semibold text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-gray-500"
        >
          {isSubmitting ? "処理中..." : "キャンセルする"}
        </button>
      </section>
    </div>
  );
}
