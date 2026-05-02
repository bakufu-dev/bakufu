"""room-matching 結合テスト共有フィクスチャ・ヘルパー群。

TC-IT-RMM-001〜012 で使用する共通セットアップを提供する。
DBは tmp_path 配下のテスト用 SQLite。全外部 I/O は実接続（モックなし）。

Issue: #120
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass
class RmmTestCtx:
    """Room-matching 結合テスト用コンテキスト。"""

    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]


@pytest_asyncio.fixture
async def rmm_ctx(tmp_path: Path) -> AsyncIterator[RmmTestCtx]:
    """Room-matching テスト用 AsyncClient + session_factory。"""
    from bakufu.interfaces.http.app import create_app
    from httpx import ASGITransport

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    app = create_app()
    engine = make_test_engine(tmp_path / "rmm_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    from bakufu.infrastructure.event_bus import InMemoryEventBus

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.event_bus = InMemoryEventBus()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield RmmTestCtx(client=client, session_factory=session_factory)

    await engine.dispose()


# ---------------------------------------------------------------------------
# HTTP ヘルパー
# ---------------------------------------------------------------------------


async def _create_empire(client: AsyncClient, name: str = "マッチングテスト幕府") -> dict[str, Any]:
    resp = await client.post("/api/empires", json={"name": name})
    assert resp.status_code == 201, f"Empire creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


async def _create_deliverable_template(
    client: AsyncClient, name: str = "必須テンプレ"
) -> dict[str, Any]:
    """POST /api/deliverable-templates → 201 → JSON。RoleProfile 登録時に実在テンプレが必要。"""
    body: dict[str, Any] = {
        "name": name,
        "description": "",
        "type": "MARKDOWN",
        "schema": "## guide",
        "version": {"major": 1, "minor": 0, "patch": 0},
        "acceptance_criteria": [],
        "composition": [],
    }
    resp = await client.post("/api/deliverable-templates", json=body)
    assert resp.status_code == 201, f"Template creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


async def _create_room(
    client: AsyncClient,
    empire_id: str,
    workflow_id: str,
    name: str = "マッチング検証室",
) -> dict[str, Any]:
    resp = await client.post(
        f"/api/empires/{empire_id}/rooms",
        json={"name": name, "workflow_id": workflow_id, "description": ""},
    )
    assert resp.status_code == 201, f"Room creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


async def _seed_workflow_with_required_deliverable(
    session_factory: async_sessionmaker[AsyncSession],
    template_id: UUID,
    optional: bool = False,
) -> Any:
    """必須成果物を持つ Workflow を直接 DB にシードして返す。

    ``template_id`` を参照する :class:`DeliverableRequirement` を 1 件持つ Stage
    を含む Workflow を作成する。``optional`` は §確定 E テスト（TC-IT-RMM-005 等）用。
    """
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    from tests.factories.workflow import make_deliverable_requirement, make_stage, make_workflow

    dr = make_deliverable_requirement(template_id=template_id, optional=optional)
    stage = make_stage(required_deliverables=(dr,))
    wf = make_workflow(stages=[stage])
    async with session_factory() as session, session.begin():
        repo = SqliteWorkflowRepository(session)
        await repo.save(wf)
    return wf


async def _seed_agent(
    session_factory: async_sessionmaker[AsyncSession],
    empire_id: UUID,
    agent_id: UUID | None = None,
) -> Any:
    from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
        SqliteAgentRepository,
    )

    from tests.factories.agent import make_agent

    agent = make_agent(empire_id=empire_id, agent_id=agent_id)
    async with session_factory() as session, session.begin():
        repo = SqliteAgentRepository(session)
        await repo.save(agent)
    return agent


async def _put_role_profile(
    client: AsyncClient,
    empire_id: str,
    role: str,
    template_id: str,
) -> None:
    """PUT /api/empires/{empire_id}/role-profiles/{role} → 200 を assert。"""
    resp = await client.put(
        f"/api/empires/{empire_id}/role-profiles/{role}",
        json={
            "deliverable_template_refs": [
                {
                    "template_id": template_id,
                    "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                }
            ]
        },
    )
    assert resp.status_code == 200, f"RoleProfile upsert failed: {resp.text}"


def _make_min_version() -> dict[str, int]:
    return {"major": 1, "minor": 0, "patch": 0}


__all__ = [
    "RmmTestCtx",
    "_create_deliverable_template",
    "_create_empire",
    "_create_room",
    "_make_min_version",
    "_put_role_profile",
    "_seed_agent",
    "_seed_workflow_with_required_deliverable",
    "rmm_ctx",
]
