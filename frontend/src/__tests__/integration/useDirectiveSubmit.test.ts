// TC-IT-CD-016: useDirectiveSubmit — POST 成功 → invalidate + navigate("/")
// TC-IT-CD-017: useDirectiveSubmit — API エラー → isError / 遷移なし
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDirectiveSubmit } from "../../hooks/useDirectiveSubmit";
import { createTestQueryClient, createWrapper } from "../helpers/test-utils";
import { server } from "../msw/server";

// useNavigate をモック
const mockNavigate = vi.fn();
vi.mock("react-router", async (importOriginal) => {
  const mod = await importOriginal<typeof import("react-router")>();
  return { ...mod, useNavigate: () => mockNavigate };
});

describe("TC-IT-CD-016: useDirectiveSubmit — POST 成功", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it("POST 201 成功 → ['tasks'] invalidate + navigate('/') が呼ばれる", async () => {
    server.use(
      http.post("http://localhost:8000/api/rooms/room-1/directives", () =>
        HttpResponse.json({ directive_id: "dir-new", task_id: "task-new" }, { status: 201 }),
      ),
    );

    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { Wrapper } = createWrapper({ queryClient });
    const { result } = renderHook(() => useDirectiveSubmit("room-1"), { wrapper: Wrapper });

    act(() => {
      result.current.submit("CEO の重要指示");
    });

    await waitFor(() => expect(result.current.isSubmitting).toBe(false));

    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ["tasks"] }));
    expect(mockNavigate).toHaveBeenCalledWith("/");
  });

  it("submit — 空テキストはクライアントバリデーションで弾かれ API は呼ばれない", async () => {
    const { Wrapper } = createWrapper();
    const { result } = renderHook(() => useDirectiveSubmit("room-1"), { wrapper: Wrapper });

    // biome-ignore lint/style/noNonNullAssertion: initial value overwritten in act()
    let validationResult: { validationError: string } | null = undefined!;
    act(() => {
      validationResult = result.current.submit("");
    });

    expect(validationResult).toEqual({
      validationError: "Directive テキストを入力してください。",
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});

describe("TC-IT-CD-017: useDirectiveSubmit — API エラー", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("POST 422 → isError=true / 遷移なし", async () => {
    server.use(
      http.post("http://localhost:8000/api/rooms/room-1/directives", () =>
        HttpResponse.json(
          { error: { code: "INVALID_INPUT", message: "text is required" } },
          { status: 422 },
        ),
      ),
    );

    const { Wrapper } = createWrapper();
    const { result } = renderHook(() => useDirectiveSubmit("room-1"), { wrapper: Wrapper });

    act(() => {
      // 非空テキストを送るがサーバーが 422 を返す
      result.current.submit("valid text that server rejects");
    });

    await waitFor(() => expect(result.current.error).toBeTruthy());

    expect(result.current.error?.code).toBe("INVALID_INPUT");
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
