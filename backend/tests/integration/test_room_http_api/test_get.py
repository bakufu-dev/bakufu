"""room / http-api 結合テスト — GET 系 (TC-IT-RM-HTTP-005/006).

Covers:
  TC-IT-RM-HTTP-005  GET /api/rooms/{room_id} → 200 RoomResponse
  TC-IT-RM-HTTP-006  GET Room 不在 → 404 not_found (MSG-RM-HTTP-002)

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


class TestGetRoom:
    """TC-IT-RM-HTTP-005: GET /api/rooms/{room_id} → 200 (REQ-RM-HTTP-003)."""

    async def test_get_room_returns_200(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.get(f"/api/rooms/{room['id']}")
        assert resp.status_code == 200

    async def test_get_room_name_matches(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.get(f"/api/rooms/{room['id']}")
        assert resp.json()["name"] == "Vモデル開発室"

    async def test_get_room_archived_is_false(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.get(f"/api/rooms/{room['id']}")
        assert resp.json()["archived"] is False


class TestGetRoomNotFound:
    """TC-IT-RM-HTTP-006: GET /api/rooms/{random_uuid} → 404 (RoomNotFoundError)."""

    async def test_room_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.get(f"/api/rooms/{uuid4()}")
        assert resp.status_code == 404

    async def test_room_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.get(f"/api/rooms/{uuid4()}")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_room_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.get(f"/api/rooms/{uuid4()}")
        assert resp.json()["error"]["message"] == "Room not found."
