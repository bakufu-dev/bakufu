"""workflow / http-api 結合テスト — LIST 系 (TC-IT-WFH-003/017).

Covers:
  TC-IT-WFH-003  GET /api/rooms/{room_id}/workflows → 200 WorkflowListResponse
  TC-IT-WFH-017  GET Room 不在 → 404 not_found

Issue: #58
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration.test_workflow_http_api.helpers import (
    WfTestCtx,
    _create_empire,
    _create_room,
    _seed_workflow_direct,
)

pytestmark = pytest.mark.asyncio


class TestListWorkflows:
    """TC-IT-WFH-003: GET /api/rooms/{room_id}/workflows → 200 WorkflowListResponse."""

    async def test_list_returns_200(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.get(f"/api/rooms/{room['id']}/workflows")
        assert resp.status_code == 200

    async def test_list_total_is_1(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.get(f"/api/rooms/{room['id']}/workflows")
        assert resp.json()["total"] == 1

    async def test_list_items_has_one_element(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.get(f"/api/rooms/{room['id']}/workflows")
        assert len(resp.json()["items"]) == 1

    async def test_list_item_has_stages(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.get(f"/api/rooms/{room['id']}/workflows")
        assert "stages" in resp.json()["items"][0]

    async def test_list_item_has_entry_stage_id(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.get(f"/api/rooms/{room['id']}/workflows")
        assert "entry_stage_id" in resp.json()["items"][0]


class TestListWorkflowsRoomNotFound:
    """TC-IT-WFH-017: GET Room 不在 → 404 not_found (RoomNotFoundError)."""

    async def test_room_not_found_returns_404(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get(f"/api/rooms/{uuid4()}/workflows")
        assert resp.status_code == 404

    async def test_room_not_found_error_code(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get(f"/api/rooms/{uuid4()}/workflows")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_room_not_found_error_message(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get(f"/api/rooms/{uuid4()}/workflows")
        assert resp.json()["error"]["message"] == "Room not found."
