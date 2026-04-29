"""ExternalReviewGate HTTP API E2E tests for Issue #61.

Covers:
  TC-E2E-ERG-001  Gate roundtrip across application restart
  TC-E2E-ERG-002  Approved Gate remains approved across application restart
  TC-E2E-ERG-003  Multi-round Gate history remains observable across restart

Gate preconditions are created through the public HTTP task flow. Assertions and
user actions use only public HTTP API responses; tests never inspect DB state.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.integration.test_agent_http_api.helpers import _create_agent_via_http
from tests.integration.test_external_review_gate_http_api.helpers import TOKEN, action_names
from tests.integration.test_room_http_api.helpers import (
    _create_empire,
    _create_room,
)
from tests.integration.test_workflow_http_api.helpers import _external_review_stage_payload

pytestmark = pytest.mark.asyncio


@dataclass(frozen=True, slots=True)
class ExternalReviewGateE2ECtx:
    db_path: Path
    reviewer_id: UUID
    session_factory: async_sessionmaker[AsyncSession]

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {TOKEN}"}


async def _make_engine_and_session(
    db_path: Path,
    *,
    create_schema: bool,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    engine = make_test_engine(db_path)
    if create_schema:
        await create_all_tables(engine)
    return engine, make_test_session_factory(engine)


@pytest_asyncio.fixture
async def external_review_gate_e2e_ctx(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[ExternalReviewGateE2ECtx]:
    reviewer_id = uuid4()
    monkeypatch.setenv("BAKUFU_OWNER_API_TOKEN", TOKEN)
    monkeypatch.setenv("BAKUFU_OWNER_ID", str(reviewer_id))

    db_path = tmp_path / "external_review_gate_e2e.db"
    engine, session_factory = await _make_engine_and_session(db_path, create_schema=True)
    try:
        yield ExternalReviewGateE2ECtx(
            db_path=db_path,
            reviewer_id=reviewer_id,
            session_factory=session_factory,
        )
    finally:
        await engine.dispose()


@asynccontextmanager
async def _running_app(
    ctx: ExternalReviewGateE2ECtx,
) -> AsyncGenerator[AsyncClient, None]:
    from bakufu.interfaces.http.app import HttpApplicationFactory

    engine, session_factory = await _make_engine_and_session(
        ctx.db_path,
        create_schema=False,
    )
    app = HttpApplicationFactory.create()
    app.state.engine = engine
    app.state.session_factory = session_factory
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await engine.dispose()


def _observed_business_attributes(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": body["id"],
        "task_id": body["task_id"],
        "stage_id": body["stage_id"],
        "reviewer_id": body["reviewer_id"],
        "decision": body["decision"],
        "feedback_text": body["feedback_text"],
        "deliverable_snapshot": body["deliverable_snapshot"],
        "created_at": body["created_at"],
        "decided_at": body["decided_at"],
    }


async def _create_gate_through_public_http(
    client: AsyncClient,
    ctx: ExternalReviewGateE2ECtx,
    *,
    body_markdown: str = "public HTTP deliverable",
) -> dict[str, str]:
    unique = uuid4().hex[:12]
    empire = await _create_empire(client, name=f"ERG E2E {unique}")
    placeholder_workflow = await client.post("/api/workflows", json={"preset_name": "v-model"})
    assert placeholder_workflow.status_code == 201, placeholder_workflow.text
    room = await _create_room(
        client,
        str(empire["id"]),
        placeholder_workflow.json()["id"],
        name=f"ERG E2E Room {unique}",
    )
    stage_id = uuid4()
    workflow = await client.post(
        f"/api/rooms/{room['id']}/workflows",
        json={
            "name": f"ERG E2E Workflow {unique}",
            "stages": [_external_review_stage_payload(stage_id)],
            "transitions": [],
            "entry_stage_id": str(stage_id),
        },
    )
    assert workflow.status_code == 201, workflow.text
    agent = await _create_agent_via_http(client, str(empire["id"]), name=f"ERG Agent {unique}")
    room_assign = await client.post(
        f"/api/rooms/{room['id']}/agents",
        json={"agent_id": str(agent["id"]), "role": "DEVELOPER"},
    )
    assert room_assign.status_code == 201, room_assign.text

    issued = await client.post(
        f"/api/rooms/{room['id']}/directives",
        json={"text": f"ERG E2E directive {unique}"},
    )
    assert issued.status_code == 201, issued.text
    task = issued.json()["task"]

    assigned = await client.post(
        f"/api/tasks/{task['id']}/assign",
        json={"agent_ids": [agent["id"]]},
    )
    assert assigned.status_code == 200, assigned.text

    committed = await client.post(
        f"/api/tasks/{task['id']}/deliverables/{task['current_stage_id']}",
        json={
            "body_markdown": body_markdown,
            "submitted_by": agent["id"],
            "attachments": [],
        },
    )
    assert committed.status_code == 200, committed.text

    listed = await client.get("/api/gates?decision=PENDING", headers=ctx.headers)
    assert listed.status_code == 200, listed.text
    gate = listed.json()["items"][0]
    return {
        "gate_id": gate["id"],
        "task_id": gate["task_id"],
        "stage_id": gate["stage_id"],
        "agent_id": str(agent["id"]),
    }


async def test_gate_roundtrip_is_observable_across_application_restart(
    external_review_gate_e2e_ctx: ExternalReviewGateE2ECtx,
) -> None:
    """TC-E2E-ERG-001 / UC-ERG-005 / R1-C / R1-E / R1-I."""
    ctx = external_review_gate_e2e_ctx

    async with _running_app(ctx) as client:
        ids = await _create_gate_through_public_http(client, ctx)

        listed = await client.get("/api/gates?decision=PENDING", headers=ctx.headers)
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["id"] == ids["gate_id"]

        before = await client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)
        assert before.status_code == 200, before.text
        before_body = before.json()
        before_attrs = _observed_business_attributes(before_body)
        before_audit = before_body["audit_trail"]
        assert action_names(before_body) == ["VIEWED"]

    async with _running_app(ctx) as restarted_client:
        after = await restarted_client.get(
            f"/api/gates/{ids['gate_id']}",
            headers=ctx.headers,
        )

    assert after.status_code == 200, after.text
    after_body = after.json()
    assert _observed_business_attributes(after_body) == before_attrs
    assert after_body["audit_trail"][: len(before_audit)] == before_audit
    assert action_names(after_body) == ["VIEWED", "VIEWED"]


async def test_approved_gate_remains_approved_across_application_restart(
    external_review_gate_e2e_ctx: ExternalReviewGateE2ECtx,
) -> None:
    """TC-E2E-ERG-002 / UC-ERG-002 / UC-ERG-005 / R1-B / R1-I."""
    ctx = external_review_gate_e2e_ctx
    comment = "CEO approval survives restart"

    async with _running_app(ctx) as client:
        ids = await _create_gate_through_public_http(client, ctx)

        approve = await client.post(
            f"/api/gates/{ids['gate_id']}/approve",
            headers=ctx.headers,
            json={"comment": comment},
        )
        assert approve.status_code == 200, approve.text
        approve_body = approve.json()
        assert approve_body["decision"] == "APPROVED"
        assert approve_body["decided_at"] is not None
        assert action_names(approve_body) == ["APPROVED"]

    async with _running_app(ctx) as restarted_client:
        detail = await restarted_client.get(
            f"/api/gates/{ids['gate_id']}",
            headers=ctx.headers,
        )
        history = await restarted_client.get(
            f"/api/tasks/{ids['task_id']}/gates",
            headers=ctx.headers,
        )
        pending = await restarted_client.get("/api/gates?decision=PENDING", headers=ctx.headers)

    assert detail.status_code == 200, detail.text
    detail_body = detail.json()
    assert detail_body["decision"] == "APPROVED"
    assert detail_body["decided_at"] == approve_body["decided_at"]
    assert detail_body["feedback_text"] == comment
    assert action_names(detail_body) == ["APPROVED", "VIEWED"]

    assert history.status_code == 200, history.text
    history_item = history.json()["items"][0]
    assert history_item["id"] == ids["gate_id"]
    assert history_item["decision"] == "APPROVED"
    assert history_item["feedback_text"] == comment
    assert action_names(history_item) == ["APPROVED", "VIEWED"]

    assert pending.status_code == 200, pending.text
    assert ids["gate_id"] not in {item["id"] for item in pending.json()["items"]}


async def test_rejected_gate_and_new_pending_round_survive_application_restart(
    external_review_gate_e2e_ctx: ExternalReviewGateE2ECtx,
) -> None:
    """TC-E2E-ERG-003 / UC-ERG-003 / UC-ERG-005 / R1-A / R1-C / R1-I."""
    ctx = external_review_gate_e2e_ctx
    feedback = "CEO requests another review round"

    async with _running_app(ctx) as client:
        first = await _create_gate_through_public_http(client, ctx)

        rejected = await client.post(
            f"/api/gates/{first['gate_id']}/reject",
            headers=ctx.headers,
            json={"feedback_text": feedback},
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["decision"] == "REJECTED"

        recommitted = await client.post(
            f"/api/tasks/{first['task_id']}/deliverables/{first['stage_id']}",
            json={
                "body_markdown": "public HTTP follow-up deliverable",
                "submitted_by": first["agent_id"],
                "attachments": [],
            },
        )
        assert recommitted.status_code == 200, recommitted.text

        pending_before_restart = await client.get(
            "/api/gates?decision=PENDING",
            headers=ctx.headers,
        )
        assert pending_before_restart.status_code == 200, pending_before_restart.text
        second = pending_before_restart.json()["items"][0]
        assert second["task_id"] == first["task_id"]
        assert second["id"] != first["gate_id"]

    async with _running_app(ctx) as restarted_client:
        history = await restarted_client.get(
            f"/api/tasks/{first['task_id']}/gates",
            headers=ctx.headers,
        )
        pending = await restarted_client.get("/api/gates?decision=PENDING", headers=ctx.headers)

    assert history.status_code == 200, history.text
    body = history.json()
    assert body["total"] == 2
    old_gate, new_gate = body["items"]
    assert old_gate["id"] == first["gate_id"]
    assert old_gate["decision"] == "REJECTED"
    assert old_gate["feedback_text"] == feedback
    assert action_names(old_gate) == ["REJECTED"]
    assert new_gate["id"] == second["id"]
    assert new_gate["decision"] == "PENDING"
    assert new_gate["id"] != old_gate["id"]

    assert pending.status_code == 200, pending.text
    assert second["id"] in {item["id"] for item in pending.json()["items"]}
