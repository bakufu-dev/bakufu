// StageProgressList — Gate 一覧を Stage 進行状況として時系列表示
// 各 Gate の decision を StatusBadge で色分け表示
// PENDING Gate はリンクとして表示（Task 詳細 §確定 A）

import type React from "react";
import { Link } from "react-router";
import type { GateDetailResponse } from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface StageProgressListProps {
  gates: GateDetailResponse[];
  /** 現在の Stage ID（AWAITING_EXTERNAL_REVIEW 判定に使用）*/
  currentStageId: string;
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

export function StageProgressList({
  gates,
  currentStageId,
}: StageProgressListProps): React.ReactElement {
  if (gates.length === 0) {
    return <p className="text-sm text-gray-500 italic">Gate の記録はありません。</p>;
  }

  // created_at 昇順でソート（API 側でソートされていない場合の保険）
  const sorted = [...gates].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );

  return (
    <ol className="space-y-2">
      {sorted.map((gate, index) => {
        const isCurrentStage = gate.stage_id === currentStageId;
        const isPending = gate.decision === "PENDING";

        return (
          <li
            key={gate.id}
            className={`flex items-center justify-between gap-3 rounded-md border p-3 ${
              isCurrentStage ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white"
            }`}
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="shrink-0 w-6 h-6 rounded-full bg-gray-200 text-xs font-bold text-gray-700 flex items-center justify-center">
                {index + 1}
              </span>
              <div className="min-w-0">
                <p className="text-xs text-gray-500 font-mono break-all">
                  Stage: {gate.stage_id.slice(0, 8)}…
                </p>
                <p className="text-xs text-gray-400">作成: {formatDateTime(gate.created_at)}</p>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <StatusBadge status={gate.decision} />
              {isPending && (
                <Link
                  to={`/gates/${gate.id}`}
                  className="text-xs font-medium text-blue-600 hover:text-blue-800 underline focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
                >
                  レビューへ →
                </Link>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
