// TC-IT-CD-013: useGateAction.approve — 成功 → invalidate + navigate(-1)
// TC-IT-CD-014: useGateAction.reject — feedback_text 付き成功
// TC-IT-CD-015: useGateAction.approve — API エラー → isError + navigate 未呼び出し
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { GateDetailResponse } from "../../api/types";
import { useGateAction } from "../../hooks/useGateAction";
import { createTestQueryClient, createWrapper } from "../helpers/test-utils";
import { server } from "../msw/server";

// useNavigate をモック（react-router の他の export は維持）
const mockNavigate = vi.fn();
vi.mock("react-router", async (importOriginal) => {
  const mod = await importOriginal<typeof import("react-router")>();
  return { ...mod, useNavigate: () => mockNavigate };
});

const APPROVED_GATE: GateDetailResponse = {
  id: "gate-1",
  task_id: "task-1",
  stage_id: "stage-1",
  decision: "APPROVED",
  deliverable_snapshot: {
    id: "snap-1",
    body_markdown: "# Deliverable",
    acceptance_criteria: "",
    created_at: "2024-01-01T00:00:00Z",
  },
  audit_trail: [],
  required_gate_roles: [],
  created_at: "2024-01-01T00:00:00Z",
};

const REJECTED_GATE: GateDetailResponse = {
  ...APPROVED_GATE,
  decision: "REJECTED",
};

describe("TC-IT-CD-013: useGateAction.approve — 成功", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it("approve 成功 → invalidateQueries(['gate', gateId]) + navigate(-1) が呼ばれる", async () => {
    server.use(
      http.post("http://localhost:8000/api/gates/gate-1/approve", () =>
        HttpResponse.json(APPROVED_GATE),
      ),
    );

    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { Wrapper } = createWrapper({ queryClient });
    const { result } = renderHook(() => useGateAction("gate-1"), { wrapper: Wrapper });

    act(() => {
      result.current.approve("LGTM");
    });

    await waitFor(() => expect(result.current.isSubmitting).toBe(false));

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["gate", "gate-1"] }),
    );
    expect(mockNavigate).toHaveBeenCalledWith(-1);
  });
});

describe("TC-IT-CD-014: useGateAction.reject — feedback_text 付き成功", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it("reject 成功 → feedback_text が API に送信され navigate(-1) が呼ばれる", async () => {
    let capturedBody: unknown;
    server.use(
      http.post("http://localhost:8000/api/gates/gate-1/reject", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json(REJECTED_GATE);
      }),
    );

    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { Wrapper } = createWrapper({ queryClient });
    const { result } = renderHook(() => useGateAction("gate-1"), { wrapper: Wrapper });

    let validationResult: { validationError: string } | null = null;
    act(() => {
      validationResult = result.current.reject("要修正: XYZ");
    });

    // クライアントバリデーションはパスする（非空文字列）
    expect(validationResult).toBeNull();

    await waitFor(() => expect(result.current.isSubmitting).toBe(false));

    expect(capturedBody).toEqual({ feedback_text: "要修正: XYZ" });
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["gate", "gate-1"] }),
    );
    expect(mockNavigate).toHaveBeenCalledWith(-1);
  });

  it("reject — feedback_text が空 → validationError が返され API は呼ばれない", async () => {
    const { Wrapper } = createWrapper();
    const { result } = renderHook(() => useGateAction("gate-1"), { wrapper: Wrapper });

    // biome-ignore lint/style/noNonNullAssertion: initial value overwritten in act()
    let validationResult: { validationError: string } | null = undefined!;
    act(() => {
      validationResult = result.current.reject("");
    });

    expect(validationResult).toEqual({ validationError: "差し戻し理由を入力してください。" });
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});

describe("TC-IT-CD-015: useGateAction.approve — API エラー", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("approve で 409 → isError=true / navigate は呼ばれない", async () => {
    server.use(
      http.post("http://localhost:8000/api/gates/gate-1/approve", () =>
        HttpResponse.json(
          { error: { code: "GATE_ALREADY_DECIDED", message: "already approved" } },
          { status: 409 },
        ),
      ),
    );

    const { Wrapper } = createWrapper();
    const { result } = renderHook(() => useGateAction("gate-1"), { wrapper: Wrapper });

    act(() => {
      result.current.approve("comment");
    });

    await waitFor(() => expect(result.current.error).toBeTruthy());

    expect(result.current.error?.code).toBe("GATE_ALREADY_DECIDED");
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
