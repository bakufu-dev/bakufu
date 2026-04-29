"""room / http-api 結合テスト — ARCHIVE 系 (TC-IT-RM-HTTP-009/019).

Covers:
  TC-IT-RM-HTTP-009  DELETE /api/rooms/{room_id} → 204 + archived=true
  TC-IT-RM-HTTP-019  DELETE Room 不在 → 404 not_found

Issue: #57
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration.test_room_http_api.helpers import (
    RoomTestCtx,
    _create_empire,
    _create_room,
    _seed_workflow,
)

pytestmark = pytest.mark.asyncio


class TestArchiveRoom:
    """TC-IT-RM-HTTP-009: DELETE → 204 論理削除; GET → archived=true (REQ-RM-HTTP-005)."""

    async def test_archive_returns_204(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        assert resp.status_code == 204

    async def test_archive_response_has_no_body(self, room_ctx: RoomTestCtx) -> None:
        """204 No Content は body を持たない (物理保証)."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        assert resp.content == b""

    async def test_after_archive_get_shows_archived_true(self, room_ctx: RoomTestCtx) -> None:
        """論理削除後 GET → archived=true (物理保証)."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.get(f"/api/rooms/{room['id']}")
        assert resp.json()["archived"] is True


class TestArchiveRoomNotFound:
    """TC-IT-RM-HTTP-019: DELETE Room 不在 → 404 (RoomNotFoundError)."""

    async def test_room_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.delete(f"/api/rooms/{uuid4()}")
        assert resp.status_code == 404

    async def test_room_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.delete(f"/api/rooms/{uuid4()}")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_room_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.delete(f"/api/rooms/{uuid4()}")
        assert resp.json()["error"]["message"] == "Room not found."
