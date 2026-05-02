// TC-IT-CD-005: apiClient 正常系（§確定 B / T2 CORS）
// TC-IT-CD-006: apiClient 非 2xx → ApiError（§確定 B / R1-5 / MSG-CD-UI-006）
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { apiGet, apiPost } from "../../api/client";
import { server } from "../msw/server";

describe("TC-IT-CD-005: apiClient — 正常系", () => {
  it("GET 200 → JSON オブジェクトが返る / Content-Type: application/json ヘッダを送信", async () => {
    let capturedContentType: string | null = null;
    let capturedUrl: string | null = null;

    server.use(
      http.get("http://localhost:8000/api/tasks/test-id", ({ request }) => {
        capturedContentType = request.headers.get("Content-Type");
        capturedUrl = request.url;
        return HttpResponse.json({ id: "test-id", status: "PENDING" });
      }),
    );

    const result = await apiGet<{ id: string; status: string }>("/api/tasks/test-id");

    // JSON レスポンスが正しく解析される
    expect(result.id).toBe("test-id");
    expect(result.status).toBe("PENDING");

    // T2: CORS 対策 — ベース URL は VITE_API_BASE_URL 固定
    expect(capturedUrl).toBe("http://localhost:8000/api/tasks/test-id");

    // Content-Type: application/json ヘッダが送信されている
    expect(capturedContentType).toBe("application/json");
  });

  it("POST 201 → JSON レスポンスが返る", async () => {
    server.use(
      http.post("http://localhost:8000/api/rooms/room-1/directives", () =>
        HttpResponse.json({ directive_id: "dir-new", task_id: "task-new" }, { status: 201 }),
      ),
    );

    const result = await apiPost<{ directive_id: string; task_id: string }>(
      "/api/rooms/room-1/directives",
      { text: "New directive" },
    );

    expect(result.directive_id).toBe("dir-new");
    expect(result.task_id).toBe("task-new");
  });
});

describe("TC-IT-CD-006: apiClient — 非 2xx → ApiError throw", () => {
  it("GET 404 → ApiError がスローされる（code / message / status が一致）", async () => {
    server.use(
      http.get("http://localhost:8000/api/gates/nonexistent", () =>
        HttpResponse.json(
          { error: { code: "GATE_NOT_FOUND", message: "Gate not found" } },
          { status: 404 },
        ),
      ),
    );

    await expect(apiGet("/api/gates/nonexistent")).rejects.toMatchObject({
      status: 404,
      code: "GATE_NOT_FOUND",
      message: "Gate not found",
    });
  });

  it("POST 422 → ApiError がスローされる（MSG-CD-UI-006 の code）", async () => {
    server.use(
      http.post("http://localhost:8000/api/rooms/room-1/directives", () =>
        HttpResponse.json(
          { error: { code: "INVALID_INPUT", message: "text is required" } },
          { status: 422 },
        ),
      ),
    );

    await expect(apiPost("/api/rooms/room-1/directives", { text: "" })).rejects.toMatchObject({
      status: 422,
      code: "INVALID_INPUT",
    });
  });

  it("非 JSON レスポンス → UNKNOWN_ERROR コードで ApiError がスローされる", async () => {
    server.use(
      http.get(
        "http://localhost:8000/api/tasks/bad-response",
        () =>
          new HttpResponse("Internal Server Error", {
            status: 500,
            headers: { "Content-Type": "text/plain" },
          }),
      ),
    );

    await expect(apiGet("/api/tasks/bad-response")).rejects.toMatchObject({
      status: 500,
      code: "UNKNOWN_ERROR",
    });
  });
});
