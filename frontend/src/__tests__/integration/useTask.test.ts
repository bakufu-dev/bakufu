// TC-IT-CD-003: useTask — Task 詳細を取得する（REQ-CD-UI-002）
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useTask } from "../../hooks/useTask";
import { createWrapper } from "../helpers/test-utils";
import { server } from "../msw/server";

describe("TC-IT-CD-003: useTask — Task 詳細取得", () => {
  it("AWAITING_EXTERNAL_REVIEW の Task 詳細が取得される", async () => {
    server.use(
      http.get("http://localhost:8000/api/tasks/task-uuid-1", () =>
        HttpResponse.json({
          id: "task-uuid-1",
          status: "AWAITING_EXTERNAL_REVIEW",
          room_id: "room-1",
          directive_id: "dir-1",
          current_stage_id: "stage-review",
          directive_text: "Review this deliverable",
          last_error: null,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-02T00:00:00Z",
        }),
      ),
    );

    const { Wrapper } = createWrapper();
    const { result } = renderHook(() => useTask("task-uuid-1"), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.status).toBe("AWAITING_EXTERNAL_REVIEW");
    expect(result.current.data?.current_stage_id).toBe("stage-review");
    expect(result.current.data?.directive_text).toBe("Review this deliverable");
  });
});
