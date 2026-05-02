// WebSocket 接続管理 Hook
// 詳細設計書 §確定 C に従って実装。Singleton WebSocket 接続を管理する。

import { useQueryClient } from "@tanstack/react-query";
import React, { createContext, useContext, useEffect, useRef } from "react";
import { create } from "zustand";

// 接続状態の型
export type WebSocketConnectionState = "connected" | "disconnected" | "reconnecting";

// Zustand ストア（接続状態のクライアント UI 状態管理）
interface WebSocketStore {
  connectionState: WebSocketConnectionState;
  setConnectionState: (state: WebSocketConnectionState) => void;
}

const useWebSocketStore = create<WebSocketStore>((set) => ({
  connectionState: "disconnected",
  setConnectionState: (state) => set({ connectionState: state }),
}));

// バックオフ配列（詳細設計書 §確定 C 凍結）
const BACKOFF_MS = [1000, 2000, 4000, 8000, 16000, 30000];

function getBackoffMs(attempt: number): number {
  return BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)];
}

// WebSocket メッセージの型
interface WebSocketMessage {
  event_type: string;
  aggregate_type: string;
  aggregate_id: string;
  payload: Record<string, unknown>;
}

// WebSocket URL の構築（http -> ws, https -> wss + /ws パス付加）
function buildWebSocketUrl(apiBaseUrl: string): string {
  return `${apiBaseUrl.replace(/^http(s?):\/\//, "ws$1://")}/ws`;
}

// Context
const WebSocketContext = createContext<WebSocketConnectionState>("disconnected");

interface WebSocketProviderProps {
  children: React.ReactNode;
}

export function WebSocketProvider({ children }: WebSocketProviderProps): React.ReactElement {
  const queryClient = useQueryClient();
  const setConnectionState = useWebSocketStore((s) => s.setConnectionState);
  const connectionState = useWebSocketStore((s) => s.connectionState);
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  useEffect(() => {
    unmountedRef.current = false;
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
    if (!apiBaseUrl) {
      return;
    }

    const wsUrl = buildWebSocketUrl(apiBaseUrl);

    function connect() {
      if (unmountedRef.current) return;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (unmountedRef.current) {
          ws.close();
          return;
        }
        attemptRef.current = 0;
        setConnectionState("connected");
        // 再接続成功後は全クエリを再検証（設計書 §確定 C）
        void queryClient.invalidateQueries({ queryKey: [] });
      };

      ws.onmessage = (event: MessageEvent) => {
        if (unmountedRef.current) return;
        try {
          const msg = JSON.parse(event.data as string) as WebSocketMessage;
          handleMessage(msg);
        } catch {
          // JSON パース失敗は無視
        }
      };

      ws.onclose = () => {
        if (unmountedRef.current) return;
        setConnectionState("reconnecting");
        scheduleReconnect();
      };

      ws.onerror = () => {
        if (unmountedRef.current) return;
        setConnectionState("reconnecting");
        // onclose も続けて呼ばれるため、再接続スケジュールは onclose に委譲
      };
    }

    function handleMessage(msg: WebSocketMessage) {
      const { aggregate_type, aggregate_id, payload } = msg;

      switch (aggregate_type) {
        case "Task":
          void queryClient.invalidateQueries({
            queryKey: ["task", aggregate_id],
          });
          void queryClient.invalidateQueries({ queryKey: ["tasks"] });
          break;
        case "ExternalReviewGate":
          void queryClient.invalidateQueries({
            queryKey: ["gate", aggregate_id],
          });
          if (typeof payload.task_id === "string") {
            void queryClient.invalidateQueries({
              queryKey: ["task", payload.task_id],
            });
          }
          break;
        case "Agent":
          void queryClient.invalidateQueries({ queryKey: ["tasks"] });
          break;
        case "Directive":
          void queryClient.invalidateQueries({ queryKey: ["tasks"] });
          break;
        default:
          break;
      }
    }

    function scheduleReconnect() {
      if (unmountedRef.current) return;
      const delay = getBackoffMs(attemptRef.current);
      attemptRef.current += 1;
      timeoutRef.current = setTimeout(() => {
        if (!unmountedRef.current) {
          connect();
        }
      }, delay);
    }

    connect();

    return () => {
      unmountedRef.current = true;
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      if (wsRef.current !== null) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [queryClient, setConnectionState]);

  return React.createElement(WebSocketContext.Provider, { value: connectionState }, children);
}

// 接続状態取得フック
export function useWebSocketState(): WebSocketConnectionState {
  return useContext(WebSocketContext);
}
