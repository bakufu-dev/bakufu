"""workflow / http-api 結合テスト共有ヘルパー。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass
class WfTestCtx:
    """Workflow 結合テスト用コンテキスト。"""

    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]


async def _create_empire(client: AsyncClient, name: str = "テスト幕府") -> dict[str, object]:
    """POST /api/empires → 201 を assert → JSON を返す。"""
    resp = await client.post("/api/empires", json={"name": name})
    assert resp.status_code == 201, f"Empire creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


async def _seed_workflow_direct(
    session_factory: async_sessionmaker[AsyncSession],
    workflow_id: UUID | None = None,
) -> object:
    """Workflow をテスト DB に直接 INSERT して返す（モック禁止原則準拠）。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    from tests.factories.workflow import make_workflow

    wf = make_workflow(workflow_id=workflow_id)
    async with session_factory() as session, session.begin():
        repo = SqliteWorkflowRepository(session)
        await repo.save(wf)
    return wf


async def _create_room(
    client: AsyncClient,
    empire_id: str,
    workflow_id: str,
    name: str = "テスト開発室",
) -> dict[str, object]:
    """POST /api/empires/{empire_id}/rooms → 201 を assert → JSON を返す。"""
    resp = await client.post(
        f"/api/empires/{empire_id}/rooms",
        json={
            "name": name,
            "workflow_id": workflow_id,
            "description": "",
            "prompt_kit_prefix_markdown": "",
        },
    )
    assert resp.status_code == 201, f"Room creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


def _minimal_stage_payload(stage_id: UUID | None = None) -> dict[str, object]:
    """最小限の有効な StageCreate ペイロードを返す。"""
    return {
        "id": str(stage_id or uuid4()),
        "name": "テストステージ",
        "kind": "WORK",
        "required_role": ["DEVELOPER"],
        "completion_policy": None,
        "notify_channels": [],
        "deliverable_template": "",
    }


def _external_review_stage_payload(
    stage_id: UUID | None = None,
    notify_url: str = "https://discord.com/api/webhooks/123456789012345678/SyntheticToken_-abcXYZ",
) -> dict[str, object]:
    """EXTERNAL_REVIEW StageCreate ペイロードを返す。"""
    return {
        "id": str(stage_id or uuid4()),
        "name": "外部レビュー",
        "kind": "EXTERNAL_REVIEW",
        "required_role": ["REVIEWER"],
        "completion_policy": None,
        "notify_channels": [notify_url],
        "deliverable_template": "",
    }


__all__ = [
    "WfTestCtx",
    "_create_empire",
    "_create_room",
    "_external_review_stage_payload",
    "_minimal_stage_payload",
    "_seed_workflow_direct",
]
