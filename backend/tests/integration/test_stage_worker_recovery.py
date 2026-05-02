"""StageWorker 起動時リカバリスキャン 結合テスト（§確定 J）。

設計書: docs/features/admin-cli/application/test-design.md
      docs/features/stage-executor/application/detailed-design.md §確定 J

テスト戦略:
  - StageWorker._recovery_scan() に実 SQLite session_factory を渡す
  - IN_PROGRESS Task → Queue に投入される
  - 他ステータス（PENDING / BLOCKED / DONE）は Queue に投入されない
  - LLM / EventBus は MagicMock（_recovery_scan はこれらを使わない）
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import MagicMock
from uuid import UUID

import pytest
import pytest_asyncio
from bakufu.domain.value_objects import TaskStatus
from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
    SqliteTaskRepository,
)
from bakufu.infrastructure.worker.stage_worker import StageWorker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory
from tests.factories.directive import make_directive
from tests.factories.empire import make_empire
from tests.factories.room import make_room
from tests.factories.task import (
    make_blocked_task,
    make_in_progress_task,
    make_task,
)
from tests.factories.workflow import make_workflow

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _init_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "OAUTH_CLIENT_SECRET",
        "BAKUFU_DISCORD_BOT_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    from bakufu.infrastructure.security import masking

    masking.init()


@pytest.fixture(autouse=True)
def _bakufu_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAKUFU_DATA_DIR", "/tmp/bakufu-recovery-test")


@pytest_asyncio.fixture
async def session_factory(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = make_test_engine(tmp_path / "recovery_test.db")
    await create_all_tables(engine)
    sf = make_test_session_factory(engine)
    try:
        yield sf
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def seeded_task_ctx(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[UUID, UUID]:
    """empire → workflow → room → directive をシードして (room_id, directive_id) を返す。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
        SqliteEmpireRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    empire = make_empire()
    workflow = make_workflow()
    room = make_room(workflow_id=workflow.id)
    directive = make_directive(target_room_id=room.id)

    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
    async with session_factory() as session, session.begin():
        await SqliteWorkflowRepository(session).save(workflow)
    async with session_factory() as session, session.begin():
        await SqliteRoomRepository(session).save(room, empire.id)
    async with session_factory() as session, session.begin():
        await SqliteDirectiveRepository(session).save(directive)

    return room.id, directive.id


def _make_stage_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> StageWorker:
    """LLM / EventBus を MagicMock とした StageWorker を構築する。"""
    return StageWorker(
        session_factory=session_factory,
        llm_provider=MagicMock(),
        event_bus=MagicMock(),
        max_concurrent=1,
    )


# ---------------------------------------------------------------------------
# TC-J-001: IN_PROGRESS Task が Queue に再投入される（§確定 J）
# ---------------------------------------------------------------------------


class TestRecoveryScan:
    """StageWorker._recovery_scan() の §確定 J テスト。"""

    async def test_in_progress_tasks_enqueued_on_recovery(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_ctx: tuple[UUID, UUID],
    ) -> None:
        """§確定 J: IN_PROGRESS × 2 + PENDING × 1 → 2件が Queue に投入される。

        admin-cli の retry-task (BLOCKED → IN_PROGRESS) 後にサーバーが再起動した場合、
        StageWorker 起動時に IN_PROGRESS Task が自動的にピックアップされる。
        """
        room_id, directive_id = seeded_task_ctx

        ip1 = make_in_progress_task(room_id=room_id, directive_id=directive_id)
        ip2 = make_in_progress_task(room_id=room_id, directive_id=directive_id)
        pending = make_task(room_id=room_id, directive_id=directive_id, status=TaskStatus.PENDING)

        async with session_factory() as session, session.begin():
            repo = SqliteTaskRepository(session)
            await repo.save(ip1)
            await repo.save(ip2)
            await repo.save(pending)

        worker = _make_stage_worker(session_factory)

        # _recovery_scan を直接呼び出す（start() は asyncio.create_task を使うためここでは不要）
        await worker._recovery_scan()

        # Queue に 2 件の IN_PROGRESS Task が投入されている
        assert worker._queue.qsize() == 2

        queued_items = []
        while not worker._queue.empty():
            queued_items.append(worker._queue.get_nowait())

        queued_task_ids = {item[0] for item in queued_items if item is not None}
        assert ip1.id in queued_task_ids
        assert ip2.id in queued_task_ids
        # PENDING Task は投入されていない
        assert pending.id not in queued_task_ids

    async def test_no_in_progress_tasks_queue_stays_empty(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_ctx: tuple[UUID, UUID],
    ) -> None:
        """§確定 J: IN_PROGRESS 0件 → Queue は空のまま（ログ出力のみ）。"""
        room_id, directive_id = seeded_task_ctx

        pending = make_task(room_id=room_id, directive_id=directive_id)
        blocked = make_blocked_task(room_id=room_id, directive_id=directive_id)

        async with session_factory() as session, session.begin():
            repo = SqliteTaskRepository(session)
            await repo.save(pending)
            await repo.save(blocked)

        worker = _make_stage_worker(session_factory)
        await worker._recovery_scan()

        assert worker._queue.qsize() == 0

    async def test_stage_id_enqueued_with_task_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_ctx: tuple[UUID, UUID],
    ) -> None:
        """§確定 J: キューアイテムが (task_id, current_stage_id) タプルで投入される。"""
        room_id, directive_id = seeded_task_ctx
        ip = make_in_progress_task(room_id=room_id, directive_id=directive_id)

        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(ip)

        worker = _make_stage_worker(session_factory)
        await worker._recovery_scan()

        assert worker._queue.qsize() == 1
        item = worker._queue.get_nowait()
        assert item is not None
        task_id, stage_id = item
        assert task_id == ip.id
        assert stage_id == ip.current_stage_id

    async def test_recovery_scan_is_idempotent_on_empty_db(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """§確定 J: 空 DB での _recovery_scan は例外を発生させない（冪等性）。"""
        worker = _make_stage_worker(session_factory)
        # 例外なく完了することを確認
        await worker._recovery_scan()
        assert worker._queue.qsize() == 0
