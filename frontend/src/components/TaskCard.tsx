// TaskCard — Task 一覧用カード。StatusBadge + directive テキスト + 更新日時を表示
// 詳細設計書 §確定 H: Tab で順次フォーカス / Enter で Task 詳細へ遷移

import type React from "react";
import { Link } from "react-router";
import type { TaskResponse } from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface TaskCardProps {
  task: TaskResponse;
}

function formatDateTime(isoString: string): string {
  try {
    return new Date(isoString).toLocaleString("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

/** directive テキストの先頭 80 文字を抜粋する */
function truncateText(text: string, maxLength = 80): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}…`;
}

export function TaskCard({ task }: TaskCardProps): React.ReactElement {
  return (
    <Link
      to={`/tasks/${task.id}`}
      className="block rounded-lg border border-gray-200 bg-white p-4 shadow-sm hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500 transition-shadow"
      aria-label={`Task: ${truncateText(task.directive_text, 40)} — ${task.status}`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-gray-900 font-medium flex-1 min-w-0 break-words">
          {truncateText(task.directive_text)}
        </p>
        <StatusBadge status={task.status} />
      </div>

      <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
        <span>
          Stage:{" "}
          <code className="font-mono text-gray-700">{task.current_stage_id.slice(0, 8)}…</code>
        </span>
        <span>更新: {formatDateTime(task.updated_at)}</span>
      </div>

      {task.status === "BLOCKED" && task.last_error && (
        <p className="mt-2 text-xs text-red-600 break-words">エラー: {task.last_error}</p>
      )}
    </Link>
  );
}
