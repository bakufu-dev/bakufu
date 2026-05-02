// AuditTrailList — Gate の audit_trail を時系列で表示
// reviewer_id / action / decided_at / comment を表示

import type React from "react";
import type { AuditEntryResponse } from "../api/types";

interface AuditTrailListProps {
  entries: AuditEntryResponse[];
}

function formatDateTime(isoString: string): string {
  try {
    return new Date(isoString).toLocaleString("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoString;
  }
}

const ACTION_LABELS: Record<string, string> = {
  VIEW: "閲覧",
  APPROVE: "承認",
  REJECT: "差し戻し",
  CANCEL: "キャンセル",
};

export function AuditTrailList({ entries }: AuditTrailListProps): React.ReactElement {
  if (entries.length === 0) {
    return <p className="text-sm text-gray-500 italic">操作履歴はありません。</p>;
  }

  return (
    <ol className="space-y-3">
      {entries.map((entry, index) => (
        // audit エントリには安定した ID がないため index を使用（表示専用リスト）
        // biome-ignore lint/suspicious/noArrayIndexKey: audit エントリは immutable リスト
        <li key={index} className="rounded-md border border-gray-200 bg-gray-50 p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold text-gray-800">
              {ACTION_LABELS[entry.action] ?? entry.action}
            </span>
            <time dateTime={entry.decided_at} className="text-xs text-gray-500 shrink-0">
              {formatDateTime(entry.decided_at)}
            </time>
          </div>

          <p className="mt-1 text-xs text-gray-600 font-mono break-all">
            操作者: {entry.reviewer_id}
          </p>

          {entry.comment && <p className="mt-1 text-sm text-gray-700">コメント: {entry.comment}</p>}
          {entry.feedback_text && (
            <p className="mt-1 text-sm text-orange-700">差し戻し理由: {entry.feedback_text}</p>
          )}
        </li>
      ))}
    </ol>
  );
}
