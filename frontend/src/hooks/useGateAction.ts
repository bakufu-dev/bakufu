// Gate 操作 Hook（approve / reject / cancel）
// 詳細設計書 §確定 D に従って実装
//
// Authorization ヘッダー:
//   §確定 B 追記に従い、Gate action POST 3本のみで VITE_REVIEWER_ID を付与する。
//   GET リクエスト（useQuery 等）には一切送信しない（最小権限原則）。
//   VITE_REVIEWER_ID は VITE_* として Vite ビルド時にバンドルに平文埋め込みされる。
//   MVP ではローカルホスト限定運用のため現実的リスクは低いが、
//   本番 OAuth 化の際は Phase 2 で実 JWT 認証に切り替えること（feature-spec.md §11 Q-OPEN-3）。

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { apiPost } from "../api/client";
import type { ApiError, GateDetailResponse } from "../api/types";

interface ApprovePayload {
  comment?: string;
}

interface RejectPayload {
  feedback_text: string;
}

interface CancelPayload {
  reason?: string;
}

// Gate action POST に付与する Authorization ヘッダーを構築する。
// VITE_REVIEWER_ID 未設定時はヘッダーなし（バックエンドが UUID フォーマット検証のみで弾く）。
function buildGateAuthHeaders(): Record<string, string> {
  const reviewerId = import.meta.env.VITE_REVIEWER_ID as string | undefined;
  if (!reviewerId) return {};
  return { Authorization: `Bearer ${reviewerId}` };
}

export function useGateAction(gateId: string) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Gate action 用 Authorization ヘッダー（approve / reject / cancel の3本のみ使用）
  const gateAuthHeaders = buildGateAuthHeaders();

  const invalidateAndNavigateBack = async () => {
    await queryClient.invalidateQueries({ queryKey: ["gate", gateId] });
    void navigate(-1);
  };

  const approveMutation = useMutation<GateDetailResponse, ApiError, ApprovePayload>({
    mutationFn: (payload: ApprovePayload) =>
      apiPost<GateDetailResponse>(`/api/gates/${gateId}/approve`, payload, gateAuthHeaders),
    onSuccess: () => {
      void invalidateAndNavigateBack();
    },
  });

  const rejectMutation = useMutation<GateDetailResponse, ApiError, RejectPayload>({
    mutationFn: (payload: RejectPayload) =>
      apiPost<GateDetailResponse>(`/api/gates/${gateId}/reject`, payload, gateAuthHeaders),
    onSuccess: () => {
      void invalidateAndNavigateBack();
    },
  });

  const cancelMutation = useMutation<GateDetailResponse, ApiError, CancelPayload>({
    mutationFn: (payload: CancelPayload) =>
      apiPost<GateDetailResponse>(`/api/gates/${gateId}/cancel`, payload, gateAuthHeaders),
    onSuccess: () => {
      void invalidateAndNavigateBack();
    },
  });

  const isSubmitting =
    approveMutation.isPending || rejectMutation.isPending || cancelMutation.isPending;

  const error = approveMutation.error ?? rejectMutation.error ?? cancelMutation.error;

  function approve(comment?: string) {
    approveMutation.mutate({ comment });
  }

  function reject(feedbackText: string): { validationError: string } | null {
    if (!feedbackText.trim()) {
      // クライアントバリデーション（詳細設計書 §確定 D: reject フロー 1）
      return { validationError: "差し戻し理由を入力してください。" };
    }
    rejectMutation.mutate({ feedback_text: feedbackText });
    return null;
  }

  function cancel(reason?: string) {
    cancelMutation.mutate({ reason });
  }

  return {
    approve,
    reject,
    cancel,
    isSubmitting,
    error,
  };
}
