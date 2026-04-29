"""room / http-api 結合テスト — UUID バリデーション (TC-IT-RM-HTTP-013).

Covers:
  TC-IT-RM-HTTP-013  不正 UUID パスパラメータ → 422 (R1-10 / BUG-EM-SEC-001)

Issue: #57
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration.test_room_http_api.helpers import RoomTestCtx

pytestmark = pytest.mark.asyncio


class TestInvalidUuidPath:
    """TC-IT-RM-HTTP-013: 不正 UUID → 422 (FastAPI UUID path validation / R1-10)."""

    async def test_get_room_invalid_uuid_returns_422(self, room_ctx: RoomTestCtx) -> None:
        """(a) GET /api/rooms/not-a-uuid → 422 (500 でないことを確認)."""
        resp = await room_ctx.client.get("/api/rooms/not-a-uuid")
        assert resp.status_code == 422

    async def test_patch_room_invalid_uuid_returns_422(self, room_ctx: RoomTestCtx) -> None:
        """(b) PATCH /api/rooms/not-a-uuid → 422."""
        resp = await room_ctx.client.patch("/api/rooms/not-a-uuid", json={"name": "x"})
        assert resp.status_code == 422

    async def test_delete_room_invalid_uuid_returns_422(self, room_ctx: RoomTestCtx) -> None:
        """(c) DELETE /api/rooms/not-a-uuid → 422."""
        resp = await room_ctx.client.delete("/api/rooms/not-a-uuid")
        assert resp.status_code == 422

    async def test_get_list_invalid_empire_uuid_returns_422(self, room_ctx: RoomTestCtx) -> None:
        """(d) GET /api/empires/not-a-uuid/rooms → 422."""
        resp = await room_ctx.client.get("/api/empires/not-a-uuid/rooms")
        assert resp.status_code == 422

    async def test_post_room_invalid_empire_uuid_returns_422(self, room_ctx: RoomTestCtx) -> None:
        """(e) POST /api/empires/not-a-uuid/rooms → 422."""
        resp = await room_ctx.client.post(
            "/api/empires/not-a-uuid/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.status_code == 422

    async def test_delete_agent_invalid_agent_uuid_returns_422(self, room_ctx: RoomTestCtx) -> None:
        """(f) DELETE .../agents/not-a-uuid/roles/LEADER → 422 (agent_id が invalid UUID)."""
        resp = await room_ctx.client.delete(f"/api/rooms/{uuid4()}/agents/not-a-uuid/roles/LEADER")
        assert resp.status_code == 422
