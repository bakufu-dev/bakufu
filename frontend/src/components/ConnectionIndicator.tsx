// ConnectionIndicator — WebSocket 接続状態を色付き dot + テキストで表示
// 詳細設計書 §確定 H: role="status" + aria-live="polite"
// 3 値: connected / disconnected / reconnecting

import type React from "react";
import type { WebSocketConnectionState } from "../hooks/useWebSocketBus";

interface ConnectionIndicatorProps {
  state: WebSocketConnectionState;
}

const STATE_CONFIG: Record<
  WebSocketConnectionState,
  { dotClass: string; text: string; ariaLabel: string }
> = {
  connected: {
    dotClass: "bg-green-500",
    text: "接続済み",
    ariaLabel: "サーバーと接続済み",
  },
  reconnecting: {
    dotClass: "bg-yellow-500",
    text: "再接続中...",
    ariaLabel: "サーバーとの接続が切断されました。再接続中...",
  },
  disconnected: {
    dotClass: "bg-red-500",
    text: "切断中",
    ariaLabel: "サーバーとの接続が切断されました",
  },
};

export function ConnectionIndicator({ state }: ConnectionIndicatorProps): React.ReactElement {
  const config = STATE_CONFIG[state];

  return (
    <output
      aria-live="polite"
      aria-label={config.ariaLabel}
      className="flex items-center gap-1.5 text-sm text-gray-600"
    >
      <span className={`inline-block w-2 h-2 rounded-full ${config.dotClass}`} aria-hidden="true" />
      <span className="text-xs">{config.text}</span>
    </output>
  );
}
