"""ExternalReviewGate HTTP API integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio

_TOKEN = "owner-api-token-32-bytes-minimum-value"
_RAW_SECRET = "GITHUB_PAT=ghp_" + "A" * 36


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
        return {"Authorization": f"Bearer {_TOKEN}"}


@pytest_asyncio.fixture
async def external_review_gate_http_ctx(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[ExternalReviewGateHttpCtx]:
    """実 SQLite と実 FastAPI app を配線する。"""
    from bakufu.interfaces.http.app import create_app

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    reviewer_id = uuid4()
    monkeypatch.setenv("BAKUFU_OWNER_API_TOKEN", _TOKEN)
    monkeypatch.setenv("BAKUFU_OWNER_ID", str(reviewer_id))

    app = create_app()
    engine = make_test_engine(tmp_path / "test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield ExternalReviewGateHttpCtx(client, session_factory, reviewer_id)

    await engine.dispose()


async def _seed_gate(
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
    from tests.integration.test_room_http_api.helpers import (
        _create_empire,
        _create_room,
        _seed_workflow,
    )

    task_id = uuid4()
    stage_id = uuid4()
    directive_id = uuid4()
    empire = await _create_empire(ctx.client, name=f"ERG HTTP 幕府 {uuid4()}")
    workflow = await _seed_workflow(ctx.session_factory)
    room = await _create_room(
        ctx.client,
        str(empire["id"]),
        str(workflow.id),  # type: ignore[attr-defined]
        name=f"ERG HTTP Room {uuid4()}",
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
            body_markdown=_RAW_SECRET,
        ),
    )
    async with ctx.session_factory() as session, session.begin():
        await SqliteDirectiveRepository(session).save(directive)
        await SqliteTaskRepository(session).save(task)
        await SqliteExternalReviewGateRepository(session).save(gate)
    return {"gate_id": str(gate.id), "task_id": str(task_id), "stage_id": str(stage_id)}


class TestExternalReviewGateHttpApi:
    async def test_reviewer_flow_uses_public_http_only(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """一覧、詳細閲覧、承認、履歴を HTTP レスポンスだけで観測する。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)

        listed = await ctx.client.get("/api/gates", headers=ctx.headers)
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["id"] == ids["gate_id"]
        assert _RAW_SECRET not in listed.text

        viewed = await ctx.client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)
        assert viewed.status_code == 200, viewed.text
        assert _action_names(viewed.json()) == ["VIEWED"]

        approved = await ctx.client.post(
            f"/api/gates/{ids['gate_id']}/approve",
            headers=ctx.headers,
            json={"comment": "承認します"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["decision"] == "APPROVED"
        assert _action_names(approved.json()) == ["VIEWED", "APPROVED"]

        history = await ctx.client.get(
            f"/api/tasks/{ids['task_id']}/gates",
            headers=ctx.headers,
        )
        assert history.status_code == 200, history.text
        assert history.json()["total"] == 1
        assert history.json()["items"][0]["decision"] == "APPROVED"

    async def test_other_reviewer_cannot_read_or_decide_gate(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """subject と Gate reviewer が一致しなければ 403。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx, reviewer_id=uuid4())

        read = await ctx.client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)
        assert read.status_code == 403

        decided = await ctx.client.post(
            f"/api/gates/{ids['gate_id']}/approve",
            headers=ctx.headers,
            json={"comment": None},
        )
        assert decided.status_code == 403

    async def test_authentication_and_property_injection_are_rejected(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """Bearer token と extra='forbid' の境界を確認する。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)

        missing = await ctx.client.get(f"/api/gates/{ids['gate_id']}")
        assert missing.status_code == 401

        injected = await ctx.client.post(
            f"/api/gates/{ids['gate_id']}/reject",
            headers=ctx.headers,
            json={"feedback_text": "直して", "actor_id": str(ctx.reviewer_id)},
        )
        assert injected.status_code == 422

    async def test_already_decided_gate_returns_conflict(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """PENDING 以外への再判断は 409。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)

        first = await ctx.client.post(
            f"/api/gates/{ids['gate_id']}/cancel",
            headers=ctx.headers,
            json={"reason": "取り消し"},
        )
        assert first.status_code == 200, first.text

        second = await ctx.client.post(
            f"/api/gates/{ids['gate_id']}/approve",
            headers=ctx.headers,
            json={"comment": "再承認"},
        )
        assert second.status_code == 409


def _action_names(body: dict[str, Any]) -> list[str]:
    return [entry["action"] for entry in body["audit_trail"]]
