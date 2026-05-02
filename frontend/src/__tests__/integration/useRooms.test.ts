// TC-IT-CD-012: useRooms — Empire に属する Room 一覧を取得する（REQ-CD-UI-004）
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { RoomResponse } from "../../api/types";
import { useRooms } from "../../hooks/useRooms";
import { createWrapper } from "../helpers/test-utils";
import { server } from "../msw/server";

const ROOMS: RoomResponse[] = [
  { id: "room-1", name: "Room Alpha", workflow_id: "workflow-1" },
  { id: "room-2", name: "Room Beta", workflow_id: "workflow-1" },
  { id: "room-3", name: "Room Gamma", workflow_id: "workflow-2" },
];

describe("TC-IT-CD-012: useRooms — Room 一覧取得", () => {
  it("Empire に属する 3 件の Room が取得される", async () => {
    server.use(
      // BUG-E2E-003: バックエンドは {items: [...], total: N} を返す（PaginatedList<T>）
      http.get("http://localhost:8000/api/empires/empire-1/rooms", () =>
        HttpResponse.json({ items: ROOMS, total: ROOMS.length }),
      ),
    );

    const { Wrapper } = createWrapper();
    const { result } = renderHook(() => useRooms("empire-1"), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(3);
    expect(result.current.data?.[0].id).toBe("room-1");
    expect(result.current.data?.[0].name).toBe("Room Alpha");
    expect(result.current.data?.[2].name).toBe("Room Gamma");
  });

  it("empireId が空文字の場合、クエリが無効化されデータが取得されない", async () => {
    const { Wrapper } = createWrapper();
    const { result } = renderHook(() => useRooms(""), { wrapper: Wrapper });

    // enabled: false なのでクエリは実行されない
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeUndefined();
  });
});
