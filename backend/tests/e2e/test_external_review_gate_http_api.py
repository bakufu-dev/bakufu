"""ExternalReviewGate HTTP API E2E テスト (TC-E2E-ERG-HTTP-001~004).

Covers:
  TC-E2E-HTTP-001  approve flow — seed PENDING via DB → POST approve → GET → APPROVED
  TC-E2E-HTTP-002  reject flow — seed PENDING via DB → POST reject → GET → REJECTED + feedback_text
  TC-E2E-HTTP-003  double-decide — seed PENDING → POST approve → POST approve again → 409
  TC-E2E-HTTP-004  reviewer filter — seed 2 gates for R + 1 for other → GET?reviewer_id=R → total=2

Issue: #61
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


@dataclass
class GateE2ECtx:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]


@pytest_asyncio.fixture
async def gate_e2e_ctx(tmp_path: Path) -> AsyncIterator[GateE2ECtx]:
    """Gate E2E テスト用 AsyncClient + session_factory."""
    from bakufu.interfaces.http.app import create_app

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    app = create_app()
    from bakufu.infrastructure.security import masking as masking_mod

    masking_mod.init()
    engine = make_test_engine(tmp_path / "gate_e2e_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    from bakufu.infrastructure.event_bus import InMemoryEventBus

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.event_bus = InMemoryEventBus()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield GateE2ECtx(client=client, session_factory=session_factory)
    await engine.dispose()


async def _seed_gate_with_deps(
    session_factory: async_sessionmaker[AsyncSession],
    gate: object,
) -> object:
    """Empire → Workflow → Room → Directive → Task → Gate の FK チェーンを全てシードする。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
        SqliteEmpireRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (
        SqliteExternalReviewGateRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    from tests.factories.directive import make_directive
    from tests.factories.empire import make_empire
    from tests.factories.room import make_room
    from tests.factories.task import make_task
    from tests.factories.workflow import make_workflow

    g = gate  # type: ignore[assignment]
    empire = make_empire()
    workflow = make_workflow()
    room = make_room(workflow_id=workflow.id, members=[])
    directive = make_directive(
        target_room_id=room.id,
        task_id=g.task_id,  # type: ignore[attr-defined]
    )
    task = make_task(
        task_id=g.task_id,  # type: ignore[attr-defined]
        room_id=room.id,
        directive_id=directive.id,
    )

    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
        await SqliteWorkflowRepository(session).save(workflow)
        await SqliteRoomRepository(session).save(room, empire.id)
        await SqliteDirectiveRepository(session).save(directive)
        await SqliteTaskRepository(session).save(task)
        await SqliteExternalReviewGateRepository(session).save(g)  # type: ignore[arg-type]

    return gate


class TestApproveFlowE2E:
    """TC-E2E-HTTP-001: 承認フロー一気通貫."""

    async def test_approve_flow(self, gate_e2e_ctx: GateE2ECtx) -> None:
        """seed PENDING via DB → POST approve → GET → APPROVED + decided_at + audit_trail."""
        from tests.factories.external_review_gate import make_gate

        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await _seed_gate_with_deps(gate_e2e_ctx.session_factory, gate)

        # POST approve
        approve_resp = await gate_e2e_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert approve_resp.status_code == 200, f"approve failed: {approve_resp.text}"

        # GET gate to confirm persisted state
        get_resp = await gate_e2e_ctx.client.get(f"/api/gates/{gate.id}")
        assert get_resp.status_code == 200, f"get failed: {get_resp.text}"
        body = get_resp.json()

        assert body["decision"] == "APPROVED"
        assert body["decided_at"] is not None
        assert len(body["audit_trail"]) == 1
        assert body["audit_trail"][0]["action"] == "APPROVED"


class TestRejectFlowE2E:
    """TC-E2E-HTTP-002: 差し戻しフロー一気通貫."""

    async def test_reject_flow(self, gate_e2e_ctx: GateE2ECtx) -> None:
        """seed PENDING via DB → POST reject → GET → REJECTED + feedback_text."""
        from tests.factories.external_review_gate import make_gate

        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await _seed_gate_with_deps(gate_e2e_ctx.session_factory, gate)

        # POST reject
        reject_resp = await gate_e2e_ctx.client.post(
            f"/api/gates/{gate.id}/reject",
            json={"feedback_text": "要修正: テストが不足しています"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert reject_resp.status_code == 200, f"reject failed: {reject_resp.text}"

        # GET gate to confirm persisted state
        get_resp = await gate_e2e_ctx.client.get(f"/api/gates/{gate.id}")
        assert get_resp.status_code == 200, f"get failed: {get_resp.text}"
        body = get_resp.json()

        assert body["decision"] == "REJECTED"
        assert body["feedback_text"] == "要修正: テストが不足しています"


class TestDoubleDecideE2E:
    """TC-E2E-HTTP-003: 二重決定は 409 を返す."""

    async def test_double_approve_returns_409(self, gate_e2e_ctx: GateE2ECtx) -> None:
        """seed PENDING → POST approve → POST approve again → 409 [FAIL]+Next: in body."""
        from tests.factories.external_review_gate import make_gate

        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await _seed_gate_with_deps(gate_e2e_ctx.session_factory, gate)

        # First approve — should succeed
        first_resp = await gate_e2e_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert first_resp.status_code == 200, f"first approve failed: {first_resp.text}"

        # Second approve — should return 409
        second_resp = await gate_e2e_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM again"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert second_resp.status_code == 409, f"expected 409, got: {second_resp.text}"
        message = second_resp.json()["error"]["message"]
        assert "[FAIL]" in message
        assert "Next:" in message


class TestReviewerFilterE2E:
    """TC-E2E-HTTP-004: reviewer_id フィルター."""

    async def test_reviewer_filter_returns_only_matching_gates(
        self, gate_e2e_ctx: GateE2ECtx
    ) -> None:
        """2 gates for reviewer R + 1 gate for other reviewer → GET?reviewer_id=R → total=2."""
        from tests.factories.external_review_gate import make_gate

        reviewer_r = uuid4()
        other_reviewer = uuid4()

        gate1 = make_gate(reviewer_id=reviewer_r)
        gate2 = make_gate(reviewer_id=reviewer_r)
        gate3 = make_gate(reviewer_id=other_reviewer)

        await _seed_gate_with_deps(gate_e2e_ctx.session_factory, gate1)
        await _seed_gate_with_deps(gate_e2e_ctx.session_factory, gate2)
        await _seed_gate_with_deps(gate_e2e_ctx.session_factory, gate3)

        resp = await gate_e2e_ctx.client.get("/api/gates", params={"reviewer_id": str(reviewer_r)})
        assert resp.status_code == 200, f"list failed: {resp.text}"
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
