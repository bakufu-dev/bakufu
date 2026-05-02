// エントリポイント — AppRoot
// 基本設計: AppRoot = QueryClientProvider + WebSocketProvider + RouterProvider
// 詳細設計書 §確定 A (RouterProvider), §確定 C (WebSocketProvider)
//
// Provider ツリーの順序:
//   QueryClientProvider（queryClient を全体に提供）
//   └─ WebSocketProvider（useQueryClient() で QueryClient を取得し、
//                        接続状態を Context で全体に提供）
//      └─ RouterProvider（全ルートコンポーネントを描画）
//
// WebSocketProvider は useQueryClient() を呼ぶため QueryClientProvider の子に配置する。
// RouterProvider の外に置くことで全ページから useWebSocketState() が参照可能となる。

import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router";
import { WebSocketProvider } from "./hooks/useWebSocketBus";
import { queryClient, router } from "./router";

// biome-ignore lint/style/noNonNullAssertion: #root は index.html で定義済み
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <WebSocketProvider>
        <RouterProvider router={router} />
      </WebSocketProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
