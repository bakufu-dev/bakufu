"""room / http-api 結合テスト — Agent 割り当て系 (TC-IT-RM-HTTP-010/011/012/015/016/020).

Covers:
  TC-IT-RM-HTTP-010  POST /api/rooms/{room_id}/agents → 201 (assign_agent)
  TC-IT-RM-HTTP-011  POST assign_agent アーカイブ済み → 409 conflict
  TC-IT-RM-HTTP-012  DELETE .../agents/{agent_id}/roles/{role} → 204 (unassign_agent)
  TC-IT-RM-HTTP-015  POST assign_agent Agent 不在 → 404 not_found (MSG-RM-HTTP-004)
  TC-IT-RM-HTTP-016  DELETE unassign_agent membership 不在 → 404 (MSG-RM-HTTP-005)
  TC-IT-RM-HTTP-020  DELETE unassign_agent アーカイブ済み → 409 conflict

Issue: #57
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from tests.integration.test_room_http_api.helpers import (
    RoomTestCtx,
    _create_empire,
    _create_room,
    _seed_agent,
    _seed_workflow,
)

pytestmark = pytest.mark.asyncio


class TestAssignAgent:
    """TC-IT-RM-HTTP-010: POST /rooms/{room_id}/agents → 201 (REQ-RM-HTTP-006)."""

    async def test_assign_returns_201(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "LEADER"},  # type: ignore[attr-defined]
        )
        assert resp.status_code == 201

    async def test_assign_response_contains_member(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        agent_id_str = str(agent.id)  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": agent_id_str, "role": "LEADER"},
        )
        members = resp.json()["members"]
        assert len(members) == 1
        assert members[0]["agent_id"] == agent_id_str

    async def test_assign_response_role_matches(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "LEADER"},  # type: ignore[attr-defined]
        )
        assert resp.json()["members"][0]["role"] == "LEADER"

    async def test_assign_response_joined_at_is_iso8601(self, room_ctx: RoomTestCtx) -> None:
        """joined_at は ISO 8601 str (MemberResponse._coerce_joined_at 検証)."""
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "LEADER"},  # type: ignore[attr-defined]
        )
        joined_at = resp.json()["members"][0]["joined_at"]
        assert "T" in joined_at


class TestAssignAgentArchivedRoom:
    """TC-IT-RM-HTTP-011: POST agents on archived Room → 409 (REQ-RM-HTTP-006)."""

    async def test_assign_archived_returns_409(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(uuid4()), "role": "LEADER"},
        )
        assert resp.status_code == 409

    async def test_assign_archived_error_code(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(uuid4()), "role": "LEADER"},
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_assign_archived_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(uuid4()), "role": "LEADER"},
        )
        assert resp.json()["error"]["message"] == "Room is archived and cannot be modified."


class TestUnassignAgent:
    """TC-IT-RM-HTTP-012: DELETE unassign_agent → 204; GET members empty (REQ-RM-HTTP-007)."""

    async def test_unassign_returns_204(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        agent_id_str = str(agent.id)  # type: ignore[attr-defined]
        await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": agent_id_str, "role": "LEADER"},
        )
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{agent_id_str}/roles/LEADER"
        )
        assert resp.status_code == 204

    async def test_unassign_response_has_no_body(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        agent_id_str = str(agent.id)  # type: ignore[attr-defined]
        await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": agent_id_str, "role": "LEADER"},
        )
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{agent_id_str}/roles/LEADER"
        )
        assert resp.content == b""

    async def test_after_unassign_get_shows_empty_members(self, room_ctx: RoomTestCtx) -> None:
        """unassign 後 GET → members=[] (membership 削除確認)."""
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        agent_id_str = str(agent.id)  # type: ignore[attr-defined]
        await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": agent_id_str, "role": "LEADER"},
        )
        await room_ctx.client.delete(f"/api/rooms/{room['id']}/agents/{agent_id_str}/roles/LEADER")
        get_resp = await room_ctx.client.get(f"/api/rooms/{room['id']}")
        assert get_resp.json()["members"] == []


class TestAssignAgentNotFound:
    """TC-IT-RM-HTTP-015: POST agents Agent 不在 → 404 (AgentNotFoundError)."""

    async def test_agent_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(uuid4()), "role": "REVIEWER"},
        )
        assert resp.status_code == 404

    async def test_agent_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(uuid4()), "role": "REVIEWER"},
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_agent_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(uuid4()), "role": "REVIEWER"},
        )
        assert resp.json()["error"]["message"] == "Agent not found."


class TestUnassignAgentMembershipNotFound:
    """TC-IT-RM-HTTP-016: unassign 未割り当て membership → 404.

    RoomInvariantViolation kind=member_not_found
    """

    async def test_membership_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        """有効 role、未割り当て agent_id → 404."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/LEADER"
        )
        assert resp.status_code == 404

    async def test_membership_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/LEADER"
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_membership_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/LEADER"
        )
        assert resp.json()["error"]["message"] == "Agent membership not found in this room."

    async def test_invalid_role_string_returns_404(self, room_ctx: RoomTestCtx) -> None:
        """無効 role 文字列 → service が ValueError を RoomInvariantViolation に変換 → 404."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/not_a_role"
        )
        assert resp.status_code == 404


class TestUnassignAgentArchivedRoom:
    """TC-IT-RM-HTTP-020: unassign_agent on archived Room → 409 (RoomArchivedError)."""

    async def test_unassign_archived_returns_409(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/LEADER"
        )
        assert resp.status_code == 409

    async def test_unassign_archived_error_code(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/LEADER"
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_unassign_archived_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/LEADER"
        )
        assert resp.json()["error"]["message"] == "Room is archived and cannot be modified."
