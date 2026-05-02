// Gate 単件取得 Hook
// 詳細設計書 §確定 A: GET /api/gates/{gateId}

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import type { ApiError, GateDetailResponse } from "../api/types";

export function useGate(gateId: string) {
  return useQuery<GateDetailResponse, ApiError>({
    queryKey: ["gate", gateId],
    queryFn: () => apiGet<GateDetailResponse>(`/api/gates/${gateId}`),
    enabled: !!gateId,
  });
}
