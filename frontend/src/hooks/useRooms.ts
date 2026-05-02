// Room 一覧取得 Hook
// 詳細設計書 §確定 A: GET /api/empires/{empireId}/rooms

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import type { ApiError, PaginatedList, RoomResponse } from "../api/types";

export function useRooms(empireId: string) {
  return useQuery<RoomResponse[], ApiError>({
    queryKey: ["rooms", empireId],
    // BUG-E2E-003: バックエンドは {items: [...], total: N} を返す
    queryFn: () =>
      apiGet<PaginatedList<RoomResponse>>(`/api/empires/${empireId}/rooms`).then((r) => r.items),
    enabled: !!empireId,
  });
}
