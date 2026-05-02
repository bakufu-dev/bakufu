// StatusBadge — Task status / Gate decision を色付きバッジで表示する
// REQ-CD-UI-006: WCAG AA コントラスト比基準（4.5:1 以上）に準拠
// 詳細設計書 §確定 H: aria-label 付与必須

import type React from "react";

type BadgeStatus =
  | "PENDING"
  | "IN_PROGRESS"
  | "AWAITING_EXTERNAL_REVIEW"
  | "DONE"
  | "BLOCKED"
  | "CANCELLED"
  | "APPROVED"
  | "REJECTED";

interface StatusBadgeProps {
  status: BadgeStatus;
}

// 色定義（REQ-CD-UI-006 凍結）
const STATUS_STYLES: Record<BadgeStatus, { bg: string; text: string; label: string }> = {
  PENDING: {
    bg: "bg-gray-500",
    text: "text-white",
    label: "PENDING",
  },
  IN_PROGRESS: {
    bg: "bg-blue-600",
    text: "text-white",
    label: "IN_PROGRESS",
  },
  AWAITING_EXTERNAL_REVIEW: {
    bg: "bg-yellow-600",
    text: "text-white",
    label: "AWAITING_EXTERNAL_REVIEW",
  },
  DONE: {
    // green-700 (#15803d) white 比: ~5.0:1 ✅ (green-600 は 3.22:1 で WCAG AA 未達)
    bg: "bg-green-700",
    text: "text-white",
    label: "DONE",
  },
  BLOCKED: {
    bg: "bg-red-600",
    text: "text-white",
    label: "BLOCKED",
  },
  CANCELLED: {
    bg: "bg-gray-400",
    text: "text-gray-900",
    label: "CANCELLED",
  },
  APPROVED: {
    // DONE と同色統一（green-700 ~5.0:1 ✅）
    bg: "bg-green-700",
    text: "text-white",
    label: "APPROVED",
  },
  REJECTED: {
    bg: "bg-red-600",
    text: "text-white",
    label: "REJECTED",
  },
};

export function StatusBadge({ status }: StatusBadgeProps): React.ReactElement {
  const style = STATUS_STYLES[status] ?? {
    bg: "bg-gray-500",
    text: "text-white",
    label: status,
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${style.bg} ${style.text}`}
      aria-label={style.label}
    >
      {status}
    </span>
  );
}
