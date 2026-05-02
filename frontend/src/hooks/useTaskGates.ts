// Task に紐づく Gate 一覧取得 Hook
// 詳細設計書 §確定 A: GET /api/tasks/{taskId}/gates

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import type { ApiError, GateDetailResponse, PaginatedList } from "../api/types";

export function useTaskGates(taskId: string) {
  return useQuery<GateDetailResponse[], ApiError>({
    queryKey: ["taskGates", taskId],
    // BUG-E2E-003: バックエンドは {items: [...], total: N} を返す
    queryFn: () =>
      apiGet<PaginatedList<GateDetailResponse>>(`/api/tasks/${taskId}/gates`).then((r) => r.items),
    enabled: !!taskId,
  });
}
