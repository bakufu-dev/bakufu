"""agent / http-api 結合テスト共有ヘルパー。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass
class AgTestCtx:
    """Agent 結合テスト用コンテキスト.

    ``client``: HTTP リクエスト送信 (FastAPI ASGI)
    ``session_factory``: Agent の直接 DB シード用セッションファクトリ（TC-IT-AGH-013 用）
    """

    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]


async def _create_empire(client: AsyncClient, name: str = "テスト幕府") -> dict[str, object]:
    """POST /api/empires → 201 を assert → JSON を返す。"""
    resp = await client.post("/api/empires", json={"name": name})
    assert resp.status_code == 201, f"Empire creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


def _minimal_agent_payload(name: str = "テストエージェント") -> dict[str, object]:
    """最小妥当 Agent POST ペイロードを返す。"""
    return {
        "name": name,
        "persona": {
            "display_name": "ダリオ",
            "archetype": "CEO",
            "prompt_body": "You are a helpful assistant.",
        },
        "role": "DEVELOPER",
        "providers": [
            {
                "provider_kind": "CLAUDE_CODE",
                "model": "claude-sonnet-4-5",
                "is_default": True,
            }
        ],
        "skills": [],
    }


async def _create_agent_via_http(
    client: AsyncClient,
    empire_id: str,
    name: str = "テストエージェント",
) -> dict[str, object]:
    """POST /api/empires/{empire_id}/agents → 201 を assert → JSON を返す。"""
    resp = await client.post(
        f"/api/empires/{empire_id}/agents",
        json=_minimal_agent_payload(name),
    )
    assert resp.status_code == 201, f"Agent creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


async def _seed_agent_direct(
    session_factory: async_sessionmaker[AsyncSession],
    empire_id: UUID,
    agent_id: UUID | None = None,
    name: str = "テストエージェント",
    archived: bool = False,
) -> object:
    """Agent をテスト DB に直接 INSERT して返す（モック禁止原則準拠）。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
        SqliteAgentRepository,
    )

    from tests.factories.agent import make_agent

    agent = make_agent(empire_id=empire_id, agent_id=agent_id, name=name, archived=archived)
    async with session_factory() as session, session.begin():
        repo = SqliteAgentRepository(session)
        await repo.save(agent)
    return agent


async def _seed_agent_with_raw_prompt_body(
    session_factory: async_sessionmaker[AsyncSession],
    empire_id: UUID,
    prompt_body: str,
    agent_id: UUID | None = None,
) -> object:
    """raw token を含む prompt_body を持つ Agent を直接 DB に INSERT する（TC-IT-AGH-013 用）。

    R1-8 バイパス経路: HTTP POST を経由しないため、masking が R1-9 の
    field_serializer に独立して委ねられる。
    """
    from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
        SqliteAgentRepository,
    )

    from tests.factories.agent import make_agent, make_persona

    persona = make_persona(prompt_body=prompt_body)
    agent = make_agent(empire_id=empire_id, agent_id=agent_id, persona=persona)
    async with session_factory() as session, session.begin():
        repo = SqliteAgentRepository(session)
        await repo.save(agent)
    return agent


__all__ = [
    "AgTestCtx",
    "_create_agent_via_http",
    "_create_empire",
    "_minimal_agent_payload",
    "_seed_agent_direct",
    "_seed_agent_with_raw_prompt_body",
]
