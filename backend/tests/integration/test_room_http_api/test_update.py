"""room / http-api 結合テスト — UPDATE 系 (TC-IT-RM-HTTP-007/008/018).

Covers:
  TC-IT-RM-HTTP-007  PATCH /api/rooms/{room_id} → 200 更新済み
  TC-IT-RM-HTTP-008  PATCH アーカイブ済み → 409 conflict (MSG-RM-HTTP-003)
  TC-IT-RM-HTTP-018  PATCH Room 不在 → 404 not_found

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


class TestUpdateRoom:
    """TC-IT-RM-HTTP-007: PATCH /api/rooms/{room_id} → 200 更新済み (REQ-RM-HTTP-004)."""

    async def test_patch_returns_200(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.patch(
            f"/api/rooms/{room['id']}", json={"name": "新Vモデル開発室"}
        )
        assert resp.status_code == 200

    async def test_patch_name_updated(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.patch(
            f"/api/rooms/{room['id']}", json={"name": "新Vモデル開発室"}
        )
        assert resp.json()["name"] == "新Vモデル開発室"

    async def test_patch_id_unchanged(self, room_ctx: RoomTestCtx) -> None:
        """PATCH 後も room_id は変わらない."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.patch(
            f"/api/rooms/{room['id']}", json={"name": "新Vモデル開発室"}
        )
        assert resp.json()["id"] == room["id"]


class TestUpdateArchivedRoom:
    """TC-IT-RM-HTTP-008: PATCH archived Room → 409 conflict (RoomArchivedError)."""

    async def test_patch_archived_returns_409(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.patch(f"/api/rooms/{room['id']}", json={"name": "変更試み"})
        assert resp.status_code == 409

    async def test_patch_archived_error_code(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.patch(f"/api/rooms/{room['id']}", json={"name": "変更試み"})
        assert resp.json()["error"]["code"] == "conflict"

    async def test_patch_archived_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.patch(f"/api/rooms/{room['id']}", json={"name": "変更試み"})
        assert resp.json()["error"]["message"] == "Room is archived and cannot be modified."


class TestUpdateRoomNotFound:
    """TC-IT-RM-HTTP-018: PATCH Room 不在 → 404 (RoomNotFoundError)."""

    async def test_room_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.patch(f"/api/rooms/{uuid4()}", json={"name": "変更試み"})
        assert resp.status_code == 404

    async def test_room_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.patch(f"/api/rooms/{uuid4()}", json={"name": "変更試み"})
        assert resp.json()["error"]["code"] == "not_found"

    async def test_room_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.patch(f"/api/rooms/{uuid4()}", json={"name": "変更試み"})
        assert resp.json()["error"]["message"] == "Room not found."
