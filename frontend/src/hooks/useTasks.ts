// Task 一覧取得 Hook
// 詳細設計書 §確定 A: GET /api/rooms/{roomId}/tasks

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import type { ApiError, TaskResponse } from "../api/types";

export function useTasks(roomId: string) {
  return useQuery<TaskResponse[], ApiError>({
    queryKey: ["tasks", roomId],
    queryFn: () => apiGet<TaskResponse[]>(`/api/rooms/${roomId}/tasks`),
    enabled: !!roomId,
  });
}
