"""ExternalReviewGate HTTP API 結合テスト共有フィクスチャ。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest_asyncio
from bakufu.domain.external_review_gate.gate import ExternalReviewGate
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass
class GateTestCtx:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]


@pytest_asyncio.fixture
async def gate_ctx(tmp_path: Path) -> AsyncIterator[GateTestCtx]:
    from bakufu.interfaces.http.app import create_app

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    app = create_app()
    engine = make_test_engine(tmp_path / "gate_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield GateTestCtx(client=client, session_factory=session_factory)
    await engine.dispose()


async def seed_gate(
    session_factory: async_sessionmaker[AsyncSession],
    gate: ExternalReviewGate,
) -> ExternalReviewGate:
    """Gate を DB にシードする。

    gate.task_id が tasks テーブルに存在しない場合は FK 違反になるため、
    呼び出し元は先に依存エンティティをシードするか、
    seed_gate_with_deps を使うこと。
    """
    from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (  # noqa: E501
        SqliteExternalReviewGateRepository,
    )

    async with session_factory() as session, session.begin():
        repo = SqliteExternalReviewGateRepository(session)
        await repo.save(gate)
    return gate


async def seed_gate_with_deps(
    session_factory: async_sessionmaker[AsyncSession],
    gate: ExternalReviewGate,
) -> ExternalReviewGate:
    """Empire → Workflow → Room → Directive → Task → Gate の FK チェーンを全てシードする。

    ``gate.task_id`` を使って Task FK を満たすよう、同じ task_id でタスクを先に
    作成してから Gate を保存する。テストでは gate ファクトリが生成した gate を
    そのまま渡せる。
    """
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
        SqliteEmpireRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (  # noqa: E501
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

    empire = make_empire()
    workflow = make_workflow()
    room = make_room(workflow_id=workflow.id, members=[])
    directive = make_directive(
        target_room_id=room.id,
        task_id=gate.task_id,
    )
    task = make_task(
        task_id=gate.task_id,
        room_id=room.id,
        directive_id=directive.id,
    )

    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
        await SqliteWorkflowRepository(session).save(workflow)
        await SqliteRoomRepository(session).save(room, empire.id)
        await SqliteDirectiveRepository(session).save(directive)
        await SqliteTaskRepository(session).save(task)
        await SqliteExternalReviewGateRepository(session).save(gate)

    return gate
