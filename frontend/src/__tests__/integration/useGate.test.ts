// TC-IT-CD-004: useGate — Gate 詳細を取得する（REQ-CD-UI-003）
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { GateDetailResponse } from "../../api/types";
import { useGate } from "../../hooks/useGate";
import { createWrapper } from "../helpers/test-utils";
import { server } from "../msw/server";

const GATE_RESPONSE: GateDetailResponse = {
  id: "gate-uuid-1",
  task_id: "task-uuid-1",
  stage_id: "stage-1",
  decision: "PENDING",
  deliverable_snapshot: {
    id: "snap-1",
    body_markdown: "# Deliverable\nContent here",
    acceptance_criteria: "Must do X",
    created_at: "2024-01-01T00:00:00Z",
  },
  audit_trail: [
    {
      action: "created",
      reviewer_id: "reviewer-1",
      comment: null,
      feedback_text: null,
      decided_at: "2024-01-01T00:00:00Z",
    },
  ],
  required_gate_roles: ["CEO"],
  created_at: "2024-01-01T00:00:00Z",
};

describe("TC-IT-CD-004: useGate — Gate 詳細取得", () => {
  it("PENDING の Gate と deliverable_snapshot, audit_trail が取得される", async () => {
    server.use(
      http.get("http://localhost:8000/api/gates/gate-uuid-1", () =>
        HttpResponse.json(GATE_RESPONSE),
      ),
    );

    const { Wrapper } = createWrapper();
    const { result } = renderHook(() => useGate("gate-uuid-1"), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.decision).toBe("PENDING");
    expect(result.current.data?.deliverable_snapshot.body_markdown).toBeTruthy();
    expect(result.current.data?.audit_trail).toHaveLength(1);
    expect(result.current.data?.required_gate_roles).toContain("CEO");
  });
});
