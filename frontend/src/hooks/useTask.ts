// Task 単件取得 Hook
// 詳細設計書 §確定 A: GET /api/tasks/{taskId}

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import type { ApiError, TaskResponse } from "../api/types";

export function useTask(taskId: string) {
  return useQuery<TaskResponse, ApiError>({
    queryKey: ["task", taskId],
    queryFn: () => apiGet<TaskResponse>(`/api/tasks/${taskId}`),
    enabled: !!taskId,
  });
}
