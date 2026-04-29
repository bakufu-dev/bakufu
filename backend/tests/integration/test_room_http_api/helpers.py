"""Shared helpers for room / http-api integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass
class RoomTestCtx:
    """Room 結合テスト用コンテキスト.

    ``client``: HTTP リクエスト送信 (FastAPI ASGI)
    ``session_factory``: Workflow / Agent の直接 DB シード用セッションファクトリ
    """

    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]


async def _create_empire(client: AsyncClient, name: str = "テスト幕府") -> dict[str, object]:
    """POST /api/empires → assert 201 → return parsed JSON."""
    resp = await client.post("/api/empires", json={"name": name})
    assert resp.status_code == 201, f"Empire creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


async def _seed_workflow(
    session_factory: async_sessionmaker[AsyncSession],
    workflow_id: UUID | None = None,
) -> object:
    """Workflow を tempdb に直接 INSERT して返す (assumed mock 禁止)."""
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    from tests.factories.workflow import make_workflow

    wf = make_workflow(workflow_id=workflow_id)
    async with session_factory() as session, session.begin():
        repo = SqliteWorkflowRepository(session)
        await repo.save(wf)
    return wf


async def _seed_agent(
    session_factory: async_sessionmaker[AsyncSession],
    empire_id: UUID,
    agent_id: UUID | None = None,
) -> object:
    """Agent を tempdb に直接 INSERT して返す (assumed mock 禁止)."""
    from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
        SqliteAgentRepository,
    )

    from tests.factories.agent import make_agent

    agent = make_agent(empire_id=empire_id, agent_id=agent_id)
    async with session_factory() as session, session.begin():
        repo = SqliteAgentRepository(session)
        await repo.save(agent)
    return agent


async def _create_room(
    client: AsyncClient,
    empire_id: str,
    workflow_id: str,
    name: str = "Vモデル開発室",
    description: str = "",
    prompt_kit_prefix_markdown: str = "",
) -> dict[str, object]:
    """POST /api/empires/{empire_id}/rooms → assert 201 → return parsed JSON."""
    resp = await client.post(
        f"/api/empires/{empire_id}/rooms",
        json={
            "name": name,
            "workflow_id": workflow_id,
            "description": description,
            "prompt_kit_prefix_markdown": prompt_kit_prefix_markdown,
        },
    )
    assert resp.status_code == 201, f"Room creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


__all__ = [
    "RoomTestCtx",
    "_create_empire",
    "_create_room",
    "_seed_agent",
    "_seed_workflow",
]
