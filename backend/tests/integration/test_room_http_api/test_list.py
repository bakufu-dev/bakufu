"""room / http-api 結合テスト — LIST 系 (TC-IT-RM-HTTP-004/017).

Covers:
  TC-IT-RM-HTTP-004  GET /api/empires/{empire_id}/rooms → 200 (空 / 2件)
  TC-IT-RM-HTTP-017  GET list Empire 不在 → 404 not_found

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


class TestListRooms:
    """TC-IT-RM-HTTP-004: GET list → 200 (空 / 2件) (REQ-RM-HTTP-002)."""

    async def test_empty_list_returns_200(self, room_ctx: RoomTestCtx) -> None:
        """(a) Empire 存在 / Room 0件 → 200, items=[], total=0."""
        empire = await _create_empire(room_ctx.client)
        resp = await room_ctx.client.get(f"/api/empires/{empire['id']}/rooms")
        assert resp.status_code == 200

    async def test_empty_list_items_is_empty(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        resp = await room_ctx.client.get(f"/api/empires/{empire['id']}/rooms")
        assert resp.json()["items"] == []

    async def test_empty_list_total_is_zero(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        resp = await room_ctx.client.get(f"/api/empires/{empire['id']}/rooms")
        assert resp.json()["total"] == 0

    async def test_two_rooms_returns_200(self, room_ctx: RoomTestCtx) -> None:
        """(b) Empire 存在 / Room 2件 → 200, items=[2 rooms], total=2."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id), name="部屋A")  # type: ignore[attr-defined]
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id), name="部屋B")  # type: ignore[attr-defined]
        resp = await room_ctx.client.get(f"/api/empires/{empire['id']}/rooms")
        assert resp.status_code == 200

    async def test_two_rooms_total_is_two(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id), name="部屋A")  # type: ignore[attr-defined]
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id), name="部屋B")  # type: ignore[attr-defined]
        resp = await room_ctx.client.get(f"/api/empires/{empire['id']}/rooms")
        assert resp.json()["total"] == 2

    async def test_two_rooms_items_contains_names(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id), name="部屋A")  # type: ignore[attr-defined]
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id), name="部屋B")  # type: ignore[attr-defined]
        resp = await room_ctx.client.get(f"/api/empires/{empire['id']}/rooms")
        names = {item["name"] for item in resp.json()["items"]}
        assert names == {"部屋A", "部屋B"}


class TestListRoomsEmpireNotFound:
    """TC-IT-RM-HTTP-017: GET list Empire 不在 → 404 (EmpireNotFoundError)."""

    async def test_empire_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.get(f"/api/empires/{uuid4()}/rooms")
        assert resp.status_code == 404

    async def test_empire_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.get(f"/api/empires/{uuid4()}/rooms")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_empire_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.get(f"/api/empires/{uuid4()}/rooms")
        assert resp.json()["error"]["message"] == "Empire not found."
