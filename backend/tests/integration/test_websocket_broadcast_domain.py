"""websocket-broadcast / domain 結合テスト（TC-IT-WSB-001〜004）。

設計書: docs/features/websocket-broadcast/domain/test-design.md
対象: REQ-WSB-008（ApplicationService 統合 — M4 スコープ）
対象 Service: TaskService（cancel）/ ExternalReviewGateService（approve）
Issue: #158

前提:
- DB: tmp_path ベースの SQLite 実接続（create_all_tables）
- EventBus: InMemoryEventBus() に SpyHandler を登録（実実装を使用）
- 各 Service は event_bus: EventBusPort を DI 注入した状態でインスタンス化する

M4 対象: TaskService.cancel() のみ + ExternalReviewGateService.approve()
（unblock_retry / commit_deliverable は同様のパターンなので TC-IT-WSB-001/003 で代表検証）
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# SpyEventBus: InMemoryEventBus に SpyHandler を登録したテスト用ラッパ
# ---------------------------------------------------------------------------


class _SpyHandler:
    """受け取った DomainEvent を記録する spy ハンドラ。"""

    def __init__(self) -> None:
        self.received: list[object] = []

    async def __call__(self, event: object) -> None:
        self.received.append(event)


class _FailingHandler:
    """常に例外を発火する ハンドラ（TC-IT-WSB-003 用）。"""

    async def __call__(self, event: object) -> None:
        raise RuntimeError("synthetic handler failure for TC-IT-WSB-003")


# ---------------------------------------------------------------------------
# masking 初期化フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _init_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    """masking モジュールを初期化する。

    ExternalReviewGateService.approve が masking.mask() を呼ぶため必要。
    """
    for env_key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "OAUTH_CLIENT_SECRET",
        "BAKUFU_DISCORD_BOT_TOKEN",
    ):
        monkeypatch.delenv(env_key, raising=False)
    from bakufu.infrastructure.security import masking

    masking.init()


# ---------------------------------------------------------------------------
# DB セットアップフィクスチャ
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def session_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """create_all でスキーマ作成済みの session_factory を提供する。"""
    engine = make_test_engine(tmp_path / "wsb_it_test.db")
    await create_all_tables(engine)
    sf = make_test_session_factory(engine)
    try:
        yield sf
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# シードヘルパー
# ---------------------------------------------------------------------------


async def _seed_task_with_deps(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    task_id: UUID | None = None,
) -> tuple[UUID, UUID, UUID, UUID, UUID]:
    """Empire → Workflow → Room → Directive → Task の FK チェーンを全てシードする。

    Returns:
        (empire_id, workflow_id, room_id, directive_id, task_id) のタプル。
    """
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
        SqliteEmpireRepository,
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

    _task_id = task_id if task_id is not None else uuid4()

    empire = make_empire()
    workflow = make_workflow()
    room = make_room(workflow_id=workflow.id, members=[])
    directive = make_directive(
        target_room_id=room.id,
        task_id=_task_id,
    )
    task = make_task(
        task_id=_task_id,
        room_id=room.id,
        directive_id=directive.id,
    )

    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
        await SqliteWorkflowRepository(session).save(workflow)
        await SqliteRoomRepository(session).save(room, empire.id)
        await SqliteDirectiveRepository(session).save(directive)
        await SqliteTaskRepository(session).save(task)

    return empire.id, workflow.id, room.id, directive.id, _task_id


# ---------------------------------------------------------------------------
# TC-IT-WSB-001: TaskService.cancel() → InMemoryEventBus.publish()
# ---------------------------------------------------------------------------


class TestTaskServiceCancelPublishesEvent:
    """TC-IT-WSB-001: TaskService.cancel() 成功後に EventBus へ TaskStateChangedEvent が配信される。

    M4 REQ-WSB-008: DB コミット後に publish が呼ばれることの結合検証。
    """

    async def test_cancel_publishes_task_state_changed_event(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        from bakufu.application.services.task_service import TaskService
        from bakufu.domain.events import TaskStateChangedEvent
        from bakufu.infrastructure.event_bus import InMemoryEventBus
        from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
            SqliteAgentRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
            SqliteRoomRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )

        _, _, _, _, task_id = await _seed_task_with_deps(session_factory)

        spy = _SpyHandler()
        event_bus = InMemoryEventBus()
        event_bus.subscribe(spy)

        async with session_factory() as session:
            task_service = TaskService(
                task_repo=SqliteTaskRepository(session),
                room_repo=SqliteRoomRepository(session),
                agent_repo=SqliteAgentRepository(session),
                session=session,
                event_bus=event_bus,
            )
            await task_service.cancel(task_id)

        # SpyHandler が TaskStateChangedEvent を 1 件受け取っている
        assert len(spy.received) == 1
        event = spy.received[0]
        assert isinstance(event, TaskStateChangedEvent)
        assert event.event_type == "task.state_changed"


# ---------------------------------------------------------------------------
# TC-IT-WSB-002: TaskService.cancel() 失敗時に publish() が呼ばれない
# ---------------------------------------------------------------------------


class TestTaskServiceCancelFailureDoesNotPublish:
    """TC-IT-WSB-002: 存在しない task_id で cancel() すると例外が発火し publish() は呼ばれない。"""

    async def test_cancel_invalid_id_raises_and_does_not_publish(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        from bakufu.application.exceptions.task_exceptions import TaskNotFoundError
        from bakufu.application.services.task_service import TaskService
        from bakufu.infrastructure.event_bus import InMemoryEventBus
        from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
            SqliteAgentRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
            SqliteRoomRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )

        spy = _SpyHandler()
        event_bus = InMemoryEventBus()
        event_bus.subscribe(spy)

        invalid_task_id = uuid4()

        async with session_factory() as session:
            task_service = TaskService(
                task_repo=SqliteTaskRepository(session),
                room_repo=SqliteRoomRepository(session),
                agent_repo=SqliteAgentRepository(session),
                session=session,
                event_bus=event_bus,
            )
            with pytest.raises(TaskNotFoundError):
                await task_service.cancel(invalid_task_id)

        # 例外発火のため publish() は呼ばれず spy の受信件数は 0
        assert len(spy.received) == 0


# ---------------------------------------------------------------------------
# TC-IT-WSB-003: EventBus handler 例外が業務結果をブロックしない
# ---------------------------------------------------------------------------


class TestTaskServiceCancelHandlerExceptionDoesNotPropagate:
    """TC-IT-WSB-003: EventBus handler が例外を発火しても cancel() 結果は呼び出し元に返る。

    InMemoryEventBus の Fail Soft 設計（asyncio.gather return_exceptions=True）の
    結合レベル検証。
    """

    async def test_cancel_returns_result_even_when_handler_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        from bakufu.application.services.task_service import TaskService
        from bakufu.domain.task.task import Task
        from bakufu.infrastructure.event_bus import InMemoryEventBus
        from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
            SqliteAgentRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
            SqliteRoomRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )

        _, _, _, _, task_id = await _seed_task_with_deps(session_factory)

        failing = _FailingHandler()
        event_bus = InMemoryEventBus()
        event_bus.subscribe(failing)

        async with session_factory() as session:
            task_service = TaskService(
                task_repo=SqliteTaskRepository(session),
                room_repo=SqliteRoomRepository(session),
                agent_repo=SqliteAgentRepository(session),
                session=session,
                event_bus=event_bus,
            )
            # handler が例外を発火しても TaskService.cancel() は例外を呼び出し元に伝播させない
            result = await task_service.cancel(task_id)

        # Task が返されており、業務結果がブロックされていない
        assert isinstance(result, Task)


# ---------------------------------------------------------------------------
# TC-IT-WSB-004: ExternalReviewGateService.approve() → masking 適用確認
# ---------------------------------------------------------------------------


class TestExternalReviewGateServiceApprovePublishesEvent:
    """TC-IT-WSB-004: approve() 成功後に reviewer_comment が masking 適用済みで publish される。

    §確定 F: reviewer_comment は masking.mask() 適用済みの値を publish する。
    通常のコメント "LGTM" はシークレットパターンに一致しないため masking 後も同値。
    """

    async def test_approve_publishes_event_with_masked_reviewer_comment(self) -> None:
        from unittest.mock import AsyncMock

        from bakufu.application.security import masking
        from bakufu.application.services.external_review_gate_service import (
            ExternalReviewGateService,
        )
        from bakufu.domain.events import ExternalReviewGateStateChangedEvent
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        from tests.factories.external_review_gate import make_gate

        reviewer_id = uuid4()
        comment = "LGTM"
        gate = make_gate(reviewer_id=reviewer_id)

        spy = _SpyHandler()
        event_bus = InMemoryEventBus()
        event_bus.subscribe(spy)

        # ExternalReviewGateService.approve() はリポジトリを使わない（gate 引数をそのまま受け取る）
        service = ExternalReviewGateService(
            repo=AsyncMock(),
            template_repo=AsyncMock(),
            event_bus=event_bus,
        )
        await service.approve(
            gate=gate,
            reviewer_id=reviewer_id,
            comment=comment,
            decided_at=datetime.now(UTC),
        )

        # SpyHandler が ExternalReviewGateStateChangedEvent を 1 件受け取っている
        assert len(spy.received) == 1
        event = spy.received[0]
        assert isinstance(event, ExternalReviewGateStateChangedEvent)
        assert event.event_type == "external_review_gate.state_changed"

        # reviewer_comment は masking.mask() 適用済みの値
        expected_comment = masking.mask(comment)
        assert event.reviewer_comment == expected_comment
