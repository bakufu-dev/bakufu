// Directive 投入 Hook
// 詳細設計書 §確定 E に従って実装

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { apiPost } from "../api/client";
import type { ApiError, DirectiveWithTaskResponse } from "../api/types";

interface DirectivePayload {
  text: string;
}

export function useDirectiveSubmit(roomId: string) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const mutation = useMutation<DirectiveWithTaskResponse, ApiError, DirectivePayload>({
    mutationFn: (payload: DirectivePayload) =>
      apiPost<DirectiveWithTaskResponse>(`/api/rooms/${roomId}/directives`, payload),
    onSuccess: () => {
      // プレフィックス一致で全 Room の Task 一覧を再検証（詳細設計書 §確定 E）
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void navigate("/");
    },
  });

  function submit(text: string): { validationError: string } | null {
    if (!text.trim()) {
      return { validationError: "Directive テキストを入力してください。" };
    }
    mutation.mutate({ text });
    return null;
  }

  return {
    submit,
    isSubmitting: mutation.isPending,
    error: mutation.error,
  };
}
