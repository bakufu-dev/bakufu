// Task に紐づく Gate 一覧取得 Hook
// 詳細設計書 §確定 A: GET /api/tasks/{taskId}/gates

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import type { ApiError, GateDetailResponse } from "../api/types";

export function useTaskGates(taskId: string) {
  return useQuery<GateDetailResponse[], ApiError>({
    queryKey: ["taskGates", taskId],
    queryFn: () => apiGet<GateDetailResponse[]>(`/api/tasks/${taskId}/gates`),
    enabled: !!taskId,
  });
}
