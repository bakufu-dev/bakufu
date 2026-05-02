// External Review Gate ページ（/gates/:gateId）
// REQ-CD-UI-003: Gate 詳細 + approve/reject/cancel フォーム + Audit Trail
// 詳細設計書 §確定 A, §確定 D, §確定 F, §確定 H

import type React from "react";
import { Link, useParams } from "react-router";
import { AuditTrailList } from "../components/AuditTrailList";
import { DeliverableViewer } from "../components/DeliverableViewer";
import { GateActionForm } from "../components/GateActionForm";
import { InlineError } from "../components/InlineError";
import { StatusBadge } from "../components/StatusBadge";
import { useGate } from "../hooks/useGate";
import { useGateAction } from "../hooks/useGateAction";

const DELIVERABLE_CONTAINER_ID = "gate-deliverable";

export function ExternalReviewGatePage(): React.ReactElement {
  const { gateId } = useParams<{ gateId: string }>();

  const { data: gate, isLoading, error, refetch } = useGate(gateId ?? "");

  const { approve, reject, cancel, isSubmitting, error: actionError } = useGateAction(gateId ?? "");

  if (!gateId) {
    return <InlineError error="Gate ID が指定されていません。" />;
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="animate-pulse h-8 bg-gray-200 rounded w-1/3" />
        <div className="animate-pulse h-40 bg-gray-200 rounded" />
        <div className="animate-pulse h-32 bg-gray-200 rounded" />
      </div>
    );
  }

  if (error) {
    return <InlineError error={error} onRetry={() => void refetch()} />;
  }

  if (!gate) {
    return <InlineError error="Gate が見つかりません。" />;
  }

  const snapshot = gate.deliverable_snapshot;

  return (
    <div className="space-y-6">
      {/* ヘッダー */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to={`/tasks/${gate.task_id}`}
            className="text-sm text-blue-600 hover:text-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
          >
            ← Task 詳細へ
          </Link>
          <h1 className="text-xl font-bold text-gray-900 mt-1">外部レビュー Gate</h1>
        </div>
        <StatusBadge status={gate.decision} />
      </div>

      {/* Deliverable Snapshot（§確定 F: rehype-sanitize 適用）*/}
      {snapshot?.body_markdown ? (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-gray-700">Deliverable スナップショット</h2>
          <DeliverableViewer
            bodyMarkdown={snapshot.body_markdown}
            sectionId={DELIVERABLE_CONTAINER_ID}
          />

          {snapshot.acceptance_criteria && (
            <div className="rounded-md border border-gray-200 bg-gray-50 p-3">
              <h3 className="text-xs font-semibold text-gray-600 mb-1">受入基準</h3>
              <p className="text-xs text-gray-700 whitespace-pre-wrap">
                {snapshot.acceptance_criteria}
              </p>
            </div>
          )}
        </section>
      ) : (
        <p className="text-sm text-gray-400 italic">Deliverable スナップショットがありません。</p>
      )}

      {/* 必要な GateRole
          BUG-E2E-004: APIは required_gate_roles を返さない（required_deliverable_criteria）
          null-safe に修正 */}
      {(gate.required_gate_roles ?? []).length > 0 && (
        <section className="space-y-1">
          <h2 className="text-sm font-semibold text-gray-700">必要な Gate ロール</h2>
          <ul className="flex flex-wrap gap-2">
            {(gate.required_gate_roles ?? []).map((role) => (
              <li
                key={role}
                className="px-2 py-0.5 rounded-full bg-gray-100 text-xs text-gray-700 font-mono"
              >
                {role}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Gate 操作フォーム（§確定 D / §確定 H）*/}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-gray-700">Gate 操作</h2>
        <GateActionForm
          gate={gate}
          deliverableContainerId={DELIVERABLE_CONTAINER_ID}
          onApprove={approve}
          onReject={reject}
          onCancel={cancel}
          isSubmitting={isSubmitting}
          error={actionError}
        />
      </section>

      {/* Audit Trail */}
      {(gate.audit_trail ?? []).length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-gray-700">操作履歴</h2>
          <AuditTrailList entries={gate.audit_trail ?? []} />
        </section>
      )}
    </div>
  );
}
