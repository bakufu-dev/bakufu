// Directive 投入ページ（/directives/new）
// REQ-CD-UI-004: VITE_EMPIRE_ID チェック + Room 選択 + Directive テキスト投入
// 詳細設計書 §確定 A, §確定 E, §確定 H

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type React from "react";
import { Link, useNavigate } from "react-router";
import { apiPost } from "../api/client";
import type { ApiError, DirectiveWithTaskResponse } from "../api/types";
import { DirectiveForm } from "../components/DirectiveForm";
import { InlineError } from "../components/InlineError";
import { useRooms } from "../hooks/useRooms";

const empireId = import.meta.env.VITE_EMPIRE_ID as string | undefined;

// Room 取得と Directive 送信を組み合わせる内部コンポーネント
function DirectiveFormContainer({
  empireId,
}: {
  empireId: string;
}): React.ReactElement {
  const { data: rooms, isLoading, error: roomsError, refetch } = useRooms(empireId);

  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // roomId を mutate 変数として受け取る構造にすることで
  // State 更新タイミングの問題を回避する（§確定 E 送信フロー）
  const mutation = useMutation<
    DirectiveWithTaskResponse,
    ApiError,
    { roomId: string; text: string }
  >({
    mutationFn: ({ roomId, text }) =>
      apiPost<DirectiveWithTaskResponse>(`/api/rooms/${roomId}/directives`, {
        text,
      }),
    onSuccess: () => {
      // プレフィックス一致で全 Room の Task 一覧を再検証（§確定 E）
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void navigate("/");
    },
  });

  function handleSubmit(roomId: string, text: string): { validationError: string } | null {
    if (!text.trim()) {
      return { validationError: "Directive テキストを入力してください。" };
    }
    mutation.mutate({ roomId, text: text.trim() });
    return null;
  }

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-3">
        <div className="h-8 bg-gray-200 rounded" />
        <div className="h-24 bg-gray-200 rounded" />
        <div className="h-10 bg-gray-200 rounded" />
      </div>
    );
  }

  if (roomsError) {
    return <InlineError error={roomsError} onRetry={() => void refetch()} />;
  }

  return (
    <DirectiveForm
      rooms={rooms ?? []}
      onSubmit={handleSubmit}
      isSubmitting={mutation.isPending}
      error={mutation.error}
    />
  );
}

export function DirectiveNewPage(): React.ReactElement {
  // §確定 E: VITE_EMPIRE_ID 未設定チェック（MSG-CD-UI-001）
  if (!empireId) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-gray-900">Directive 投入</h1>
        <InlineError error="VITE_EMPIRE_ID が設定されていません。frontend/.env に VITE_EMPIRE_ID=<uuid> を追加してください。" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/"
          className="text-sm text-blue-600 hover:text-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
        >
          ← Task 一覧へ
        </Link>
        <h1 className="text-xl font-bold text-gray-900 mt-1">Directive 投入</h1>
        <p className="text-sm text-gray-500 mt-1">Room を選択し、CEO の指示を入力してください。</p>
      </div>

      <div className="rounded-md border border-gray-200 bg-white p-6">
        <DirectiveFormContainer empireId={empireId} />
      </div>
    </div>
  );
}
