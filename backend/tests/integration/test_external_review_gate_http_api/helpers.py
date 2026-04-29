"""Shared helpers for ExternalReviewGate HTTP API integration tests."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

TOKEN = "owner-api-token-32-bytes-minimum-value"
RAW_SECRET = "GITHUB_PAT=ghp_" + "A" * 36


class ExternalReviewGateHttpCtx:
    """ExternalReviewGate HTTP API integration context."""

    def __init__(
        self,
        client: AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
        reviewer_id: UUID,
    ) -> None:
        self.client = client
        self.session_factory = session_factory
        self.reviewer_id = reviewer_id

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {TOKEN}"}


async def seed_gate(
    ctx: ExternalReviewGateHttpCtx,
    *,
    reviewer_id: UUID | None = None,
) -> dict[str, str]:
    """Repository 経由で Gate 事前条件を保存する。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (  # noqa: E501
        SqliteExternalReviewGateRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )

    from tests.factories.directive import make_directive
    from tests.factories.external_review_gate import make_gate
    from tests.factories.task import make_deliverable, make_task
    from tests.integration.test_room_http_api.helpers import _create_empire, _create_room

    task_id = uuid4()
    stage_id = uuid4()
    directive_id = uuid4()
    workflow_stage_id = uuid4()
    unique_suffix = uuid4().hex[:12]
    empire = await _create_empire(ctx.client, name=f"ERG-{unique_suffix}")
    workflow = await ctx.client.post(
        "/api/workflows",
        json={
            "name": f"ERG Workflow {unique_suffix}",
            "stages": [
                {
                    "id": str(workflow_stage_id),
                    "name": "外部レビュー前提",
                    "kind": "WORK",
                    "required_role": ["DEVELOPER"],
                    "completion_policy": None,
                    "notify_channels": [],
                    "deliverable_template": "",
                }
            ],
            "transitions": [],
            "entry_stage_id": str(workflow_stage_id),
        },
    )
    assert workflow.status_code == 201, workflow.text
    room = await _create_room(
        ctx.client,
        str(empire["id"]),
        str(workflow.json()["id"]),
        name=f"ERG Room {unique_suffix}",
    )
    directive = make_directive(
        directive_id=directive_id,
        target_room_id=UUID(str(room["id"])),
        task_id=task_id,
    )
    task = make_task(
        task_id=task_id,
        room_id=UUID(str(room["id"])),
        directive_id=directive_id,
        current_stage_id=stage_id,
    )
    gate = make_gate(
        task_id=task_id,
        stage_id=stage_id,
        reviewer_id=reviewer_id or ctx.reviewer_id,
        deliverable_snapshot=make_deliverable(
            stage_id=stage_id,
            body_markdown=RAW_SECRET,
        ),
    )
    async with ctx.session_factory() as session, session.begin():
        await SqliteDirectiveRepository(session).save(directive)
        await SqliteTaskRepository(session).save(task)
        await SqliteExternalReviewGateRepository(session).save(gate)
    return {"gate_id": str(gate.id), "task_id": str(task_id), "stage_id": str(stage_id)}


async def seed_gate_with_awaiting_approved_transition(
    ctx: ExternalReviewGateHttpCtx,
    *,
    reviewer_id: UUID | None = None,
) -> dict[str, str]:
    """AWAITING Task と APPROVED transition を持つ Gate 事前条件を保存する。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (  # noqa: E501
        SqliteExternalReviewGateRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )

    from tests.factories.directive import make_directive
    from tests.factories.external_review_gate import make_gate
    from tests.factories.task import make_awaiting_review_task, make_deliverable
    from tests.integration.test_room_http_api.helpers import _create_empire, _create_room

    task_id = uuid4()
    review_stage_id = uuid4()
    approved_stage_id = uuid4()
    transition_id = uuid4()
    directive_id = uuid4()
    unique_suffix = uuid4().hex[:12]
    empire = await _create_empire(ctx.client, name=f"ERG-ADV-{unique_suffix}")
    workflow = await ctx.client.post(
        "/api/workflows",
        json={
            "name": f"ERG Advancement Workflow {unique_suffix}",
            "stages": [
                {
                    "id": str(review_stage_id),
                    "name": "外部レビュー",
                    "kind": "WORK",
                    "required_role": ["REVIEWER"],
                    "completion_policy": None,
                    "notify_channels": [],
                    "deliverable_template": "",
                },
                {
                    "id": str(approved_stage_id),
                    "name": "承認後作業",
                    "kind": "WORK",
                    "required_role": ["DEVELOPER"],
                    "completion_policy": None,
                    "notify_channels": [],
                    "deliverable_template": "",
                },
            ],
            "transitions": [
                {
                    "id": str(transition_id),
                    "from_stage_id": str(review_stage_id),
                    "to_stage_id": str(approved_stage_id),
                    "condition": "APPROVED",
                    "label": "承認",
                }
            ],
            "entry_stage_id": str(review_stage_id),
        },
    )
    assert workflow.status_code == 201, workflow.text
    room = await _create_room(
        ctx.client,
        str(empire["id"]),
        str(workflow.json()["id"]),
        name=f"ERG Advancement Room {unique_suffix}",
    )
    directive = make_directive(
        directive_id=directive_id,
        target_room_id=UUID(str(room["id"])),
        task_id=task_id,
    )
    task = make_awaiting_review_task(
        task_id=task_id,
        room_id=UUID(str(room["id"])),
        directive_id=directive_id,
        current_stage_id=review_stage_id,
    )
    gate = make_gate(
        task_id=task_id,
        stage_id=review_stage_id,
        reviewer_id=reviewer_id or ctx.reviewer_id,
        deliverable_snapshot=make_deliverable(
            stage_id=review_stage_id,
            body_markdown=RAW_SECRET,
        ),
    )
    async with ctx.session_factory() as session, session.begin():
        await SqliteDirectiveRepository(session).save(directive)
        await SqliteTaskRepository(session).save(task)
        await SqliteExternalReviewGateRepository(session).save(gate)
    return {
        "approved_stage_id": str(approved_stage_id),
        "gate_id": str(gate.id),
        "review_stage_id": str(review_stage_id),
        "task_id": str(task_id),
        "transition_id": str(transition_id),
    }


async def seed_gate_for_existing_task(
    ctx: ExternalReviewGateHttpCtx,
    *,
    task_id: UUID,
    stage_id: UUID,
    reviewer_id: UUID | None = None,
) -> dict[str, str]:
    """既存 Task に追加 Gate だけを保存する。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (  # noqa: E501
        SqliteExternalReviewGateRepository,
    )

    from tests.factories.external_review_gate import make_gate
    from tests.factories.task import make_deliverable

    gate = make_gate(
        task_id=task_id,
        stage_id=stage_id,
        reviewer_id=reviewer_id or ctx.reviewer_id,
        deliverable_snapshot=make_deliverable(
            stage_id=stage_id,
            body_markdown=RAW_SECRET,
        ),
    )
    async with ctx.session_factory() as session, session.begin():
        await SqliteExternalReviewGateRepository(session).save(gate)
    return {"gate_id": str(gate.id), "task_id": str(task_id), "stage_id": str(stage_id)}


def action_names(body: dict[str, Any]) -> list[str]:
    return [entry["action"] for entry in body["audit_trail"]]


def error_message(response: Any) -> str:
    return str(response.json()["error"]["message"])
