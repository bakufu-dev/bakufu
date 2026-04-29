"""Directive + Task HTTP API E2E tests for Issue #60.

Covers:
  TC-E2E-DR-003  Directive issue + Task creation + archived/missing Room rejection
  TC-E2E-TS-003  Task lifecycle via public HTTP API
  TC-E2E-TS-004  BLOCKED Task unblock via public HTTP API

The lifecycle scenario observes state only through public HTTP responses. Workflow
and Agent setup are test preconditions for APIs outside this feature slice, so
they are seeded through the real repositories.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.test_room_http_api.helpers import (
    RoomTestCtx,
    _create_empire,
    _create_room,
    _seed_agent,
    _seed_workflow,
)

pytestmark = pytest.mark.asyncio

_RAW_ANTHROPIC_TOKEN = "sk-ant-api03-" + "A" * 40
_RAW_GITHUB_PAT = "ghp_" + "B" * 36


async def _build_room_with_agent(ctx: RoomTestCtx) -> tuple[dict[str, Any], str, str]:
    """Create an Empire/Room through HTTP and seed one Agent precondition."""
    empire = await _create_empire(ctx.client, name=f"Issue60 E2E 幕府 {uuid4()}")
    empire_id = str(empire["id"])
    workflow = await _seed_workflow(ctx.session_factory)
    room = await _create_room(ctx.client, empire_id, str(workflow.id))  # type: ignore[attr-defined]
    agent = await _seed_agent(ctx.session_factory, empire_id=UUID(empire_id))
    assigned = await ctx.client.post(
        f"/api/rooms/{room['id']}/agents",
        json={"agent_id": str(agent.id), "role": "DEVELOPER"},  # type: ignore[attr-defined]
    )
    assert assigned.status_code == 201, assigned.text
    return room, str(agent.id), empire_id  # type: ignore[attr-defined]


async def _seed_blocked_task(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    room_id: UUID,
    current_stage_id: UUID,
    agent_id: UUID,
) -> str:
    """Seed a BLOCKED Task precondition through real repositories."""
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )

    from tests.factories.directive import make_directive
    from tests.factories.task import make_blocked_task

    directive_id = uuid4()
    task_id = uuid4()
    directive = make_directive(
        directive_id=directive_id,
        target_room_id=room_id,
        task_id=task_id,
    )
    task = make_blocked_task(
        task_id=task_id,
        room_id=room_id,
        directive_id=directive_id,
        current_stage_id=current_stage_id,
        assigned_agent_ids=[agent_id],
        last_error=f"GITHUB_PAT={_RAW_GITHUB_PAT}",
    )
    async with session_factory() as session, session.begin():
        await SqliteDirectiveRepository(session).save(directive)
        await SqliteTaskRepository(session).save(task)
    return str(task_id)


class TestDirectiveTaskHttpE2E:
    async def test_directive_issue_creates_task_and_task_lifecycle_is_observable(
        self, room_e2e_ctx: RoomTestCtx
    ) -> None:
        """TC-E2E-DR-003 / TC-E2E-TS-003: public API lifecycle."""
        client = room_e2e_ctx.client
        room, agent_id, _empire_id = await _build_room_with_agent(room_e2e_ctx)
        room_id = str(room["id"])

        issue = await client.post(
            f"/api/rooms/{room_id}/directives",
            json={"text": f"ANTHROPIC_API_KEY={_RAW_ANTHROPIC_TOKEN} ブログ分析機能を作って"},
        )
        assert issue.status_code == 201, issue.text
        issue_body = issue.json()
        assert _RAW_ANTHROPIC_TOKEN not in issue_body["directive"]["text"]
        assert issue_body["directive"]["target_room_id"] == room_id
        assert issue_body["directive"]["task_id"] == issue_body["task"]["id"]
        assert issue_body["task"]["status"] == "PENDING"

        task_id = issue_body["task"]["id"]
        stage_id = issue_body["task"]["current_stage_id"]

        fetched = await client.get(f"/api/tasks/{task_id}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["status"] == "PENDING"

        listed = await client.get(f"/api/rooms/{room_id}/tasks")
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["id"] == task_id

        assigned = await client.post(
            f"/api/tasks/{task_id}/assign",
            json={"agent_ids": [agent_id]},
        )
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["status"] == "IN_PROGRESS"

        delivered = await client.post(
            f"/api/tasks/{task_id}/deliverables/{stage_id}",
            json={
                "body_markdown": f"GITHUB_PAT={_RAW_GITHUB_PAT}",
                "submitted_by": agent_id,
                "attachments": [],
            },
        )
        assert delivered.status_code == 200, delivered.text
        body_markdown = delivered.json()["deliverables"][stage_id]["body_markdown"]
        assert _RAW_GITHUB_PAT not in body_markdown
        assert "<REDACTED:" in body_markdown

        after_roundtrip = await client.get(f"/api/tasks/{task_id}")
        assert after_roundtrip.status_code == 200, after_roundtrip.text
        assert after_roundtrip.json()["status"] == "IN_PROGRESS"
        assert (
            _RAW_GITHUB_PAT
            not in (after_roundtrip.json()["deliverables"][stage_id]["body_markdown"])
        )

        cancelled = await client.patch(f"/api/tasks/{task_id}/cancel")
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "CANCELLED"

        terminal_retry = await client.patch(f"/api/tasks/{task_id}/cancel")
        assert terminal_retry.status_code == 409

        missing_task = await client.get(f"/api/tasks/{uuid4()}")
        assert missing_task.status_code == 404

    async def test_task_assignment_rejects_agent_outside_room(
        self, room_e2e_ctx: RoomTestCtx
    ) -> None:
        """Task assign rejects arbitrary Agent UUIDs outside Room.members."""
        client = room_e2e_ctx.client
        room, _agent_id, empire_id = await _build_room_with_agent(room_e2e_ctx)
        outsider = await _seed_agent(
            room_e2e_ctx.session_factory,
            empire_id=UUID(empire_id),
        )

        issue = await client.post(
            f"/api/rooms/{room['id']}/directives",
            json={"text": "未所属Agent拒否"},
        )
        assert issue.status_code == 201, issue.text

        rejected = await client.post(
            f"/api/tasks/{issue.json()['task']['id']}/assign",
            json={"agent_ids": [str(outsider.id)]},  # type: ignore[attr-defined]
        )
        assert rejected.status_code == 403

    async def test_deliverable_rejects_unassigned_submitter(
        self, room_e2e_ctx: RoomTestCtx
    ) -> None:
        """Deliverable commit rejects a Room member who is not assigned to the Task."""
        client = room_e2e_ctx.client
        room, assigned_agent_id, empire_id = await _build_room_with_agent(room_e2e_ctx)
        second_agent = await _seed_agent(
            room_e2e_ctx.session_factory,
            empire_id=UUID(empire_id),
        )
        room_assign = await client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(second_agent.id), "role": "TESTER"},  # type: ignore[attr-defined]
        )
        assert room_assign.status_code == 201, room_assign.text

        issue = await client.post(
            f"/api/rooms/{room['id']}/directives",
            json={"text": "未担当Agent提出拒否"},
        )
        assert issue.status_code == 201, issue.text
        task_id = issue.json()["task"]["id"]
        stage_id = issue.json()["task"]["current_stage_id"]

        assigned = await client.post(
            f"/api/tasks/{task_id}/assign",
            json={"agent_ids": [assigned_agent_id]},
        )
        assert assigned.status_code == 200, assigned.text

        rejected = await client.post(
            f"/api/tasks/{task_id}/deliverables/{stage_id}",
            json={
                "body_markdown": "別Agentからの提出",
                "submitted_by": str(second_agent.id),  # type: ignore[attr-defined]
                "attachments": [],
            },
        )
        assert rejected.status_code == 403

    async def test_directive_issue_rejects_missing_and_archived_room(
        self, room_e2e_ctx: RoomTestCtx
    ) -> None:
        """TC-E2E-DR-003: missing Room is 404 and archived Room is 409."""
        client = room_e2e_ctx.client

        missing = await client.post(
            f"/api/rooms/{uuid4()}/directives",
            json={"text": "テスト指令"},
        )
        assert missing.status_code == 404

        room, _agent_id, _empire_id = await _build_room_with_agent(room_e2e_ctx)
        room_id = str(room["id"])
        archived = await client.delete(f"/api/rooms/{room_id}")
        assert archived.status_code == 204, archived.text

        rejected = await client.post(
            f"/api/rooms/{room_id}/directives",
            json={"text": "アーカイブ済みRoomへの指令"},
        )
        assert rejected.status_code == 409

    async def test_blocked_task_can_be_unblocked_through_public_api(
        self, room_e2e_ctx: RoomTestCtx
    ) -> None:
        """TC-E2E-TS-004: BLOCKED Task unblock and invalid retry conflict."""
        client = room_e2e_ctx.client
        room, agent_id, _empire_id = await _build_room_with_agent(room_e2e_ctx)
        task_id = await _seed_blocked_task(
            room_e2e_ctx.session_factory,
            room_id=UUID(str(room["id"])),
            current_stage_id=UUID(str(room["workflow_id"])),
            agent_id=UUID(agent_id),
        )

        before = await client.get(f"/api/tasks/{task_id}")
        assert before.status_code == 200, before.text
        assert before.json()["status"] == "BLOCKED"
        assert _RAW_GITHUB_PAT not in before.json()["last_error"]

        unblocked = await client.patch(f"/api/tasks/{task_id}/unblock")
        assert unblocked.status_code == 200, unblocked.text
        assert unblocked.json()["status"] == "IN_PROGRESS"
        assert unblocked.json()["last_error"] is None

        retry = await client.patch(f"/api/tasks/{task_id}/unblock")
        assert retry.status_code == 409
