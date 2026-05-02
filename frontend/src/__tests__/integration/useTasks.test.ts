// TC-IT-CD-001: useTasks 正常系
// TC-IT-CD-002: useTasks 異常系（500 エラー）
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { TaskResponse } from "../../api/types";
import { useTasks } from "../../hooks/useTasks";
import { createWrapper } from "../helpers/test-utils";
import { server } from "../msw/server";

const TASK_A1: TaskResponse = {
  id: "task-a1",
  status: "PENDING",
  room_id: "room-a",
  directive_id: "dir-1",
  current_stage_id: "stage-1",
  directive_text: "Task A1",
  last_error: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const TASK_A2: TaskResponse = {
  id: "task-a2",
  status: "IN_PROGRESS",
  room_id: "room-a",
  directive_id: "dir-2",
  current_stage_id: "stage-1",
  directive_text: "Task A2",
  last_error: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("TC-IT-CD-001: useTasks — 正常系", () => {
  it("MSW が 200 を返す場合、Task 一覧が取得される（REQ-CD-UI-001）", async () => {
    server.use(
      // BUG-E2E-003: バックエンドは {items: [...], total: N} を返す（PaginatedList<T>）
      http.get("http://localhost:8000/api/rooms/room-a/tasks", () =>
        HttpResponse.json({ items: [TASK_A1, TASK_A2], total: 2 }),
      ),
    );

    const { Wrapper } = createWrapper();
    const { result } = renderHook(() => useTasks("room-a"), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(2);
    expect(result.current.data?.[0].id).toBe("task-a1");
    expect(result.current.data?.[0].room_id).toBe("room-a");
    expect(result.current.data?.[1].status).toBe("IN_PROGRESS");
  });
});

describe("TC-IT-CD-002: useTasks — 異常系", () => {
  it("MSW が 500 を返す場合、isError=true になり他 Room に影響しない", async () => {
    server.use(
      http.get("http://localhost:8000/api/rooms/room-b/tasks", () =>
        HttpResponse.json(
          { error: { code: "INTERNAL_ERROR", message: "Server error" } },
          { status: 500 },
        ),
      ),
      http.get("http://localhost:8000/api/rooms/room-a/tasks", () =>
        HttpResponse.json({ items: [TASK_A1], total: 1 }),
      ),
    );

    const { Wrapper: WrapperB } = createWrapper();
    const { result: resultB } = renderHook(() => useTasks("room-b"), { wrapper: WrapperB });
    await waitFor(() => expect(resultB.current.isError).toBe(true));
    expect(resultB.current.data).toBeUndefined();

    // room-a は独立して成功する
    const { Wrapper: WrapperA } = createWrapper();
    const { result: resultA } = renderHook(() => useTasks("room-a"), { wrapper: WrapperA });
    await waitFor(() => expect(resultA.current.isSuccess).toBe(true));
    expect(resultA.current.data).toHaveLength(1);
  });
});
