import { vi } from "vitest";

type WsEventListener = (event: Event | MessageEvent | CloseEvent) => void;

export class MockWebSocket {
  static instances: MockWebSocket[] = [];

  static reset() {
    MockWebSocket.instances = [];
  }

  url: string;
  readyState: number = WebSocket.CONNECTING;

  private listeners: Map<string, WsEventListener[]> = new Map();

  // Simulate callbacks (also support .onopen etc.)
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  // Captured messages
  sentMessages: unknown[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  addEventListener(type: string, listener: WsEventListener) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type)?.push(listener);
  }

  removeEventListener(type: string, listener: WsEventListener) {
    const arr = this.listeners.get(type) ?? [];
    this.listeners.set(
      type,
      arr.filter((l) => l !== listener),
    );
  }

  send(data: unknown) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = WebSocket.CLOSED;
  }

  // --- Test helpers to fire events ---

  /** Simulate connection established */
  simulateOpen() {
    this.readyState = WebSocket.OPEN;
    const event = new Event("open");
    this.onopen?.(event);
    for (const l of this.listeners.get("open") ?? []) l(event);
  }

  /** Simulate server message */
  simulateMessage(data: unknown) {
    const event = new MessageEvent("message", {
      data: typeof data === "string" ? data : JSON.stringify(data),
    });
    this.onmessage?.(event);
    for (const l of this.listeners.get("message") ?? []) l(event);
  }

  /** Simulate connection closed */
  simulateClose(code = 1000, reason = "") {
    this.readyState = WebSocket.CLOSED;
    const event = new CloseEvent("close", { code, reason, wasClean: code === 1000 });
    this.onclose?.(event);
    for (const l of this.listeners.get("close") ?? []) l(event);
  }

  /** Simulate error */
  simulateError() {
    const event = new Event("error");
    this.onerror?.(event);
    for (const l of this.listeners.get("error") ?? []) l(event);
  }
}

/** Install MockWebSocket as global.WebSocket for a test */
export function installMockWebSocket() {
  MockWebSocket.reset();
  vi.stubGlobal("WebSocket", MockWebSocket);
}

/** Restore original WebSocket */
export function uninstallMockWebSocket() {
  vi.unstubAllGlobals();
  MockWebSocket.reset();
}
