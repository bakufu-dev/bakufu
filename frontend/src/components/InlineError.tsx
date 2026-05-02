// InlineError — API エラーをインライン表示するコンポーネント
// 詳細設計書 §確定 H: role="alert" + aria-live="assertive"

import type React from "react";
import type { ApiError } from "../api/types";

interface InlineErrorProps {
  error: ApiError | Error | string | null | undefined;
  onRetry?: () => void;
}

function formatErrorMessage(error: ApiError | Error | string): string {
  if (typeof error === "string") {
    return error;
  }
  if ("code" in error) {
    // ApiError
    return error.message;
  }
  // Error（ネットワークエラー等）
  return "サーバーに接続できません。バックエンドが起動しているか確認してください。";
}

export function InlineError({ error, onRetry }: InlineErrorProps): React.ReactElement | null {
  if (!error) return null;

  const message = formatErrorMessage(error);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="rounded-md bg-red-50 border border-red-300 p-4"
    >
      <div className="flex items-start gap-3">
        <span className="text-red-600 text-lg leading-none" aria-hidden="true">
          ⚠
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-red-800 break-words">{message}</p>
          {"code" in (error as object) && (error as ApiError).code && (
            <p className="mt-1 text-xs text-red-600 font-mono">
              コード: {(error as ApiError).code}
            </p>
          )}
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="shrink-0 text-sm font-medium text-red-700 hover:text-red-900 underline"
          >
            再試行
          </button>
        )}
      </div>
    </div>
  );
}
