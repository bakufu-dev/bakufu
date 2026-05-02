// TC-IT-CD-007: onopen → state=connected
// TC-IT-CD-008: onclose → state=reconnecting + backoff タイマー起動
// TC-IT-CD-009: 再接続成功 → state=connected + invalidateQueries
// TC-IT-CD-010: Task event → ["task", id] + ["tasks"] invalidate
// TC-IT-CD-011: ExternalReviewGate event → ["gate", id] + ["task", taskId] invalidate
// TC-IT-CD-018: backoff 境界値: 6 回目以降 30000ms 固定（§確定 C）
// TC-IT-CD-019: Agent event → ["tasks"] invalidate
// TC-IT-CD-020: Directive event → ["tasks"] invalidate
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WebSocketProvider, useWebSocketState } from "../../hooks/useWebSocketBus";
import {
  MockWebSocket,
  installMockWebSocket,
  uninstallMockWebSocket,
} from "../helpers/MockWebSocket";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function makeWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      React.createElement(WebSocketProvider, null, children),
    );
  };
}

describe("TC-IT-CD-007: onopen → state=connected", () => {
  beforeEach(() => {
    installMockWebSocket();
  });
  afterEach(() => {
    uninstallMockWebSocket();
  });

  it("WebSocket onopen を dispatch すると state が connected になる", async () => {
    const qc = makeQueryClient();
    const { result } = renderHook(() => useWebSocketState(), {
      wrapper: makeWrapper(qc),
    });

    // WebSocketProvider が mount → connect() → new MockWebSocket
    const ws = MockWebSocket.instances[0];
    expect(ws).toBeDefined();

    act(() => {
      ws.simulateOpen();
    });

    await waitFor(() => expect(result.current).toBe("connected"));
  });
});

describe("TC-IT-CD-008: onclose → reconnecting + backoff タイマー", () => {
  beforeEach(() => {
    installMockWebSocket();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    uninstallMockWebSocket();
  });

  it("onclose 直後に reconnecting になり 1000ms 後に新規 WebSocket が作成される", () => {
    const qc = makeQueryClient();
    const { result } = renderHook(() => useWebSocketState(), {
      wrapper: makeWrapper(qc),
    });

    const ws0 = MockWebSocket.instances[0];

    // open → connected（fake timers 環境では act() 内で同期的にアサート）
    act(() => ws0.simulateOpen());
    expect(result.current).toBe("connected");

    // onclose → reconnecting 状態へ遷移
    act(() => ws0.simulateClose(1001, "server gone"));
    expect(result.current).toBe("reconnecting");

    // 999ms 経過 → 新インスタンス未作成
    act(() => vi.advanceTimersByTime(999));
    expect(MockWebSocket.instances).toHaveLength(1);

    // あと 1ms → 2 番目のインスタンス作成（1 回目の再接続試行）
    act(() => vi.advanceTimersByTime(1));
    expect(MockWebSocket.instances).toHaveLength(2);
  });
});

describe("TC-IT-CD-009: 再接続成功 → state=connected + invalidateQueries", () => {
  beforeEach(() => {
    installMockWebSocket();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    uninstallMockWebSocket();
  });

  it("再接続後 onopen → state=connected かつ invalidateQueries が呼ばれる", () => {
    const qc = makeQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useWebSocketState(), {
      wrapper: makeWrapper(qc),
    });

    // 初回接続（fake timers 環境では act() 内で同期アサート）
    const ws0 = MockWebSocket.instances[0];
    act(() => ws0.simulateOpen());
    expect(result.current).toBe("connected");

    // invalidateSpy をリセット（初回 onopen での呼び出しを除外）
    invalidateSpy.mockClear();

    // 切断 → reconnecting
    act(() => ws0.simulateClose());
    expect(result.current).toBe("reconnecting");

    // 1000ms 経過 → 再接続
    act(() => vi.advanceTimersByTime(1000));
    const ws1 = MockWebSocket.instances[1];
    expect(ws1).toBeDefined();

    // 再接続成功
    act(() => ws1.simulateOpen());
    expect(result.current).toBe("connected");

    // 再接続後に全キャッシュを再検証
    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: [] }));
  });
});

describe('TC-IT-CD-010: Task event → ["task", id] + ["tasks"] invalidate', () => {
  beforeEach(() => {
    installMockWebSocket();
  });
  afterEach(() => {
    uninstallMockWebSocket();
  });

  it("TaskStateChangedEvent → ['task', id] と ['tasks'] の 2 回 invalidate", async () => {
    const qc = makeQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useWebSocketState(), {
      wrapper: makeWrapper(qc),
    });

    const ws = MockWebSocket.instances[0];
    act(() => ws.simulateOpen());
    await waitFor(() => expect(result.current).toBe("connected"));

    invalidateSpy.mockClear();

    act(() => {
      ws.simulateMessage({
        event_type: "TaskStateChangedEvent",
        aggregate_type: "Task",
        aggregate_id: "task-abc",
        payload: {},
      });
    });

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["task", "task-abc"] }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ["tasks"] }));
  });
});

describe('TC-IT-CD-011: ExternalReviewGate event → ["gate", id] + ["task", taskId]', () => {
  beforeEach(() => {
    installMockWebSocket();
  });
  afterEach(() => {
    uninstallMockWebSocket();
  });

  it("ExternalReviewGateStateChangedEvent → ['gate', id] と ['task', taskId] の 2 回 invalidate", async () => {
    const qc = makeQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useWebSocketState(), {
      wrapper: makeWrapper(qc),
    });

    const ws = MockWebSocket.instances[0];
    act(() => ws.simulateOpen());
    await waitFor(() => expect(result.current).toBe("connected"));

    invalidateSpy.mockClear();

    act(() => {
      ws.simulateMessage({
        event_type: "ExternalReviewGateStateChangedEvent",
        aggregate_type: "ExternalReviewGate",
        aggregate_id: "gate-xyz",
        payload: { task_id: "task-abc" },
      });
    });

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["gate", "gate-xyz"] }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["task", "task-abc"] }),
    );
  });
});

describe("TC-IT-CD-018: backoff 境界値 — 6 回目以降 30000ms 固定（§確定 C）", () => {
  beforeEach(() => {
    installMockWebSocket();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    uninstallMockWebSocket();
  });

  it("backoff 配列 [1000,2000,4000,8000,16000,30000] を使い切った後 30000ms で固定される", async () => {
    const qc = makeQueryClient();
    renderHook(() => useWebSocketState(), { wrapper: makeWrapper(qc) });

    // instance[0] が mount 時に作成済み
    expect(MockWebSocket.instances).toHaveLength(1);

    // 5 回の切断・再接続サイクル（attempt 0~4）
    const backoffSequence = [1000, 2000, 4000, 8000, 16000];
    for (const delay of backoffSequence) {
      const current = MockWebSocket.instances[MockWebSocket.instances.length - 1];
      act(() => current.simulateClose());
      act(() => vi.advanceTimersByTime(delay));
      // 新インスタンスが生成されていることを確認
      expect(MockWebSocket.instances.length).toBeGreaterThan(backoffSequence.indexOf(delay) + 1);
    }

    // この時点で 6 インスタンス（instance[0..5]）
    expect(MockWebSocket.instances).toHaveLength(6);

    // attempt=5 → getBackoffMs(5) = BACKOFF_MS[5] = 30000ms（配列末尾・上限）
    const ws5 = MockWebSocket.instances[5];
    act(() => ws5.simulateClose());

    // 29999ms 経過 → まだ instance[6] は未作成
    act(() => vi.advanceTimersByTime(29999));
    expect(MockWebSocket.instances).toHaveLength(6);

    // あと 1ms → instance[6] 作成
    act(() => vi.advanceTimersByTime(1));
    expect(MockWebSocket.instances).toHaveLength(7);

    // attempt=6 も 30000ms 固定（上限なし継続）
    const ws6 = MockWebSocket.instances[6];
    act(() => ws6.simulateClose());

    act(() => vi.advanceTimersByTime(29999));
    expect(MockWebSocket.instances).toHaveLength(7);

    act(() => vi.advanceTimersByTime(1));
    expect(MockWebSocket.instances).toHaveLength(8);
  });
});

describe('TC-IT-CD-019: Agent event → ["tasks"] invalidate', () => {
  beforeEach(() => {
    installMockWebSocket();
  });
  afterEach(() => {
    uninstallMockWebSocket();
  });

  it("AgentStateChangedEvent → ['tasks'] prefix invalidate のみ呼ばれる", async () => {
    const qc = makeQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useWebSocketState(), {
      wrapper: makeWrapper(qc),
    });

    const ws = MockWebSocket.instances[0];
    act(() => ws.simulateOpen());
    await waitFor(() => expect(result.current).toBe("connected"));

    invalidateSpy.mockClear();

    act(() => {
      ws.simulateMessage({
        event_type: "AgentStateChangedEvent",
        aggregate_type: "Agent",
        aggregate_id: "agent-abc",
        payload: {},
      });
    });

    // ["tasks"] で invalidate される（全 Room の Task 一覧キャッシュ再検証）
    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ["tasks"] }));

    // ["gate"] 系は呼ばれない
    const calls = invalidateSpy.mock.calls;
    const gateCall = calls.find((c) => {
      const arg = c[0] as { queryKey?: unknown[] };
      return Array.isArray(arg.queryKey) && arg.queryKey[0] === "gate";
    });
    expect(gateCall).toBeUndefined();
  });
});

describe('TC-IT-CD-020: Directive event → ["tasks"] invalidate', () => {
  beforeEach(() => {
    installMockWebSocket();
  });
  afterEach(() => {
    uninstallMockWebSocket();
  });

  it("DirectiveCompletedEvent → ['tasks'] invalidate / 特定 Task ID では呼ばれない", async () => {
    const qc = makeQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useWebSocketState(), {
      wrapper: makeWrapper(qc),
    });

    const ws = MockWebSocket.instances[0];
    act(() => ws.simulateOpen());
    await waitFor(() => expect(result.current).toBe("connected"));

    invalidateSpy.mockClear();

    act(() => {
      ws.simulateMessage({
        event_type: "DirectiveCompletedEvent",
        aggregate_type: "Directive",
        aggregate_id: "directive-xyz",
        payload: {},
      });
    });

    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ["tasks"] }));

    // ["task", <specific-id>] では呼ばれない（Directive は特定 Task ID を持たない）
    const calls = invalidateSpy.mock.calls;
    const specificTaskCall = calls.find((c) => {
      const arg = c[0] as { queryKey?: unknown[] };
      return Array.isArray(arg.queryKey) && arg.queryKey[0] === "task" && arg.queryKey.length > 1;
    });
    expect(specificTaskCall).toBeUndefined();
  });
});
