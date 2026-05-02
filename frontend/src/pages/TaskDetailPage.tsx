// Task 詳細ページ（/tasks/:taskId）
// REQ-CD-UI-002: Task 詳細 + Stage 進行状況 + Deliverable Markdown
// 詳細設計書 §確定 A

import type React from "react";
import { Link, useParams } from "react-router";
import type { GateDetailResponse } from "../api/types";
import { DeliverableViewer } from "../components/DeliverableViewer";
import { InlineError } from "../components/InlineError";
import { StageProgressList } from "../components/StageProgressList";
import { StatusBadge } from "../components/StatusBadge";
import { useTask } from "../hooks/useTask";
import { useTaskGates } from "../hooks/useTaskGates";

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

/** 最新の deliverable snapshot を持つ Gate を返す */
function findLatestGateWithDeliverable(gates: GateDetailResponse[]): GateDetailResponse | null {
  const withDeliverable = gates.filter((g) => g.deliverable_snapshot?.body_markdown);
  if (withDeliverable.length === 0) return null;
  return withDeliverable.reduce((latest, g) =>
    new Date(g.created_at) > new Date(latest.created_at) ? g : latest,
  );
}

export function TaskDetailPage(): React.ReactElement {
  const { taskId } = useParams<{ taskId: string }>();

  const {
    data: task,
    isLoading: taskLoading,
    error: taskError,
    refetch: refetchTask,
  } = useTask(taskId ?? "");

  const {
    data: gates,
    isLoading: gatesLoading,
    error: gatesError,
    refetch: refetchGates,
  } = useTaskGates(taskId ?? "");

  if (!taskId) {
    return <InlineError error="Task ID が指定されていません。" />;
  }

  if (taskLoading || gatesLoading) {
    return (
      <div className="space-y-4">
        <div className="animate-pulse h-8 bg-gray-200 rounded w-1/3" />
        <div className="animate-pulse space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-gray-200 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (taskError) {
    return <InlineError error={taskError} onRetry={() => void refetchTask()} />;
  }

  if (!task) {
    return <InlineError error="Task が見つかりません。" />;
  }

  const gateList: GateDetailResponse[] = gates ?? [];
  const latestGate = findLatestGateWithDeliverable(gateList);
  const pendingGate = gateList.find((g) => g.decision === "PENDING");

  return (
    <div className="space-y-6">
      {/* ヘッダー */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Link
              to="/"
              className="text-sm text-blue-600 hover:text-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
            >
              ← 一覧へ
            </Link>
          </div>
          <h1 className="text-xl font-bold text-gray-900 break-words">Task 詳細</h1>
        </div>
        <StatusBadge status={task.status} />
      </div>

      {/* Task 基本情報 */}
      <section className="rounded-md border border-gray-200 bg-white p-4 space-y-2">
        <h2 className="text-sm font-semibold text-gray-700">指示内容</h2>
        <p className="text-sm text-gray-900 whitespace-pre-wrap break-words">
          {task.directive_text}
        </p>
        <div className="flex items-center gap-4 text-xs text-gray-500 pt-1">
          <span>起票: {formatDateTime(task.created_at)}</span>
          <span>更新: {formatDateTime(task.updated_at)}</span>
        </div>
        {task.status === "BLOCKED" && task.last_error && (
          <div className="mt-2 rounded-md bg-red-50 border border-red-200 p-2">
            <p className="text-xs text-red-700 font-semibold">エラー情報</p>
            <p className="text-xs text-red-600 break-words">{task.last_error}</p>
          </div>
        )}
      </section>

      {/* AWAITING_EXTERNAL_REVIEW 時: 承認待ち Gate リンク */}
      {task.status === "AWAITING_EXTERNAL_REVIEW" && pendingGate && (
        <div className="rounded-md border border-yellow-400 bg-yellow-50 p-4">
          <p className="text-sm font-medium text-yellow-800 mb-2">
            外部レビュー待ちです。以下からレビューを行ってください。
          </p>
          <Link
            to={`/gates/${pendingGate.id}`}
            className="inline-block px-4 py-2 text-sm font-semibold text-white bg-yellow-600 rounded-md hover:bg-yellow-700 focus:outline-none focus:ring-2 focus:ring-yellow-500"
          >
            Gate レビューへ →
          </Link>
        </div>
      )}

      {/* Gate エラー */}
      {gatesError && <InlineError error={gatesError} onRetry={() => void refetchGates()} />}

      {/* Stage 進行状況 */}
      {gateList.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-gray-700">Gate 履歴 / Stage 進行状況</h2>
          <StageProgressList gates={gateList} currentStageId={task.current_stage_id} />
        </section>
      )}

      {/* Deliverable（最新 Gate のスナップショット）*/}
      {latestGate?.deliverable_snapshot?.body_markdown && (
        <section className="space-y-2" id="deliverable-section">
          <h2 className="text-sm font-semibold text-gray-700">
            Deliverable
            {latestGate.decision !== "PENDING" && (
              <span className="ml-2 text-xs text-gray-400 font-normal">
                （{latestGate.decision}）
              </span>
            )}
          </h2>
          <DeliverableViewer
            bodyMarkdown={latestGate.deliverable_snapshot.body_markdown}
            sectionId="deliverable-section"
          />

          {latestGate.deliverable_snapshot.acceptance_criteria && (
            <div className="rounded-md border border-gray-200 bg-gray-50 p-3 mt-2">
              <h3 className="text-xs font-semibold text-gray-600 mb-1">受入基準</h3>
              <p className="text-xs text-gray-700 whitespace-pre-wrap">
                {latestGate.deliverable_snapshot.acceptance_criteria}
              </p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
