"""room / http-api 結合テスト — CREATE 系 (TC-IT-RM-HTTP-001/002/003/014).

Per ``docs/features/room/http-api/test-design.md`` §結合テストケース.

Covers:
  TC-IT-RM-HTTP-001  POST /api/empires/{empire_id}/rooms → 201 RoomResponse
  TC-IT-RM-HTTP-002  POST 重複 name → 409 conflict (MSG-RM-HTTP-001)
  TC-IT-RM-HTTP-003  POST Empire 不在 → 404 not_found
  TC-IT-RM-HTTP-014  POST Workflow 不在 → 404 not_found (MSG-RM-HTTP-006)

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


class TestCreateRoom:
    """TC-IT-RM-HTTP-001: POST /api/empires/{empire_id}/rooms → 201 (REQ-RM-HTTP-001)."""

    async def test_create_returns_201(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.status_code == 201

    async def test_create_response_id_is_str(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert isinstance(resp.json()["id"], str)

    async def test_create_response_name_matches(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["name"] == "Vモデル開発室"

    async def test_create_response_workflow_id_matches(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        wf_id_str = str(wf.id)  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": wf_id_str,
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["workflow_id"] == wf_id_str

    async def test_create_response_members_is_empty(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["members"] == []

    async def test_create_response_archived_is_false(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["archived"] is False

    async def test_create_response_prompt_kit_prefix_markdown_empty(
        self, room_ctx: RoomTestCtx
    ) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["prompt_kit_prefix_markdown"] == ""

    async def test_csrf_evil_origin_returns_403(self, room_ctx: RoomTestCtx) -> None:
        """T1 CSRF: POST with evil Origin → 403 (room router に CSRF ミドルウェアが適用される)."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "CSRF室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
            headers={"Origin": "http://evil.example.com"},
        )
        assert resp.status_code == 403


class TestCreateRoomNameConflict:
    """TC-IT-RM-HTTP-002: POST 同名 Room → 409 conflict (REQ-RM-HTTP-001 / MSG-RM-HTTP-001)."""

    async def test_duplicate_name_returns_409(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.status_code == 409

    async def test_duplicate_name_error_code_is_conflict(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_duplicate_name_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["error"]["message"] == "Room name already exists in this empire."


class TestCreateRoomEmpireNotFound:
    """TC-IT-RM-HTTP-003: POST に存在しない empire_id → 404 (EmpireNotFoundError)."""

    async def test_empire_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.post(
            f"/api/empires/{uuid4()}/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.status_code == 404

    async def test_empire_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.post(
            f"/api/empires/{uuid4()}/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_empire_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.post(
            f"/api/empires/{uuid4()}/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["error"]["message"] == "Empire not found."


class TestCreateRoomWorkflowNotFound:
    """TC-IT-RM-HTTP-014: POST Workflow 不在 → 404 (WorkflowNotFoundError)."""

    async def test_workflow_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.status_code == 404

    async def test_workflow_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_workflow_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["error"]["message"] == "Workflow not found."
