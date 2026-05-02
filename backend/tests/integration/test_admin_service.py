"""AdminService 結合テスト（TC-ST-AC-001〜010 + TC-IT-AC-001〜013）。

システムテスト設計書: docs/features/admin-cli/system-test-design.md
結合テスト設計書:    docs/features/admin-cli/application/test-design.md

テスト戦略:
  - AdminService + 実 SQLite（create_all_tables）
  - AuditLogWriter / OutboxEventRepository / TaskRepository はすべて実装クラス
  - FAIL audit_log 検証: 例外を session.begin() 内部でキャッチして commit を許可
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bakufu.application.exceptions.task_exceptions import IllegalTaskStateError, TaskNotFoundError
from bakufu.application.services.admin_service import AdminService
from bakufu.domain.exceptions.outbox import IllegalOutboxStateError, OutboxEventNotFoundError
from bakufu.infrastructure.persistence.sqlite.repositories.audit_log_writer import (
    SqliteAuditLogWriter,
)
from bakufu.infrastructure.persistence.sqlite.repositories.outbox_event_repository import (
    SqliteOutboxEventRepository,
)
from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
    SqliteTaskRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.audit_log import AuditLogRow
from bakufu.infrastructure.persistence.sqlite.tables.outbox import OutboxRow

from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory
from tests.factories.directive import make_directive
from tests.factories.empire import make_empire
from tests.factories.persistence_rows import make_outbox_row
from tests.factories.room import make_room
from tests.factories.task import (
    make_awaiting_review_task,
    make_blocked_task,
    make_done_task,
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
    """masking 初期化（MaskedText TypeDecorator 動作保証）。"""
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
    monkeypatch.setenv("BAKUFU_DATA_DIR", "/tmp/bakufu-admin-it-test")


@pytest_asyncio.fixture
async def session_factory(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """create_all でスキーマ作成済みの session_factory を提供する。"""
    engine = make_test_engine(tmp_path / "admin_service_test.db")
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_admin_service(
    session: AsyncSession,
    actor: str = "test_actor",
) -> AdminService:
    """AdminService を組み立てる（実 SQLite 実装クラス経由）。"""
    return AdminService(
        task_repo=SqliteTaskRepository(session),
        outbox_event_repo=SqliteOutboxEventRepository(session),
        audit_log_writer=SqliteAuditLogWriter(session),
        actor=actor,
    )


async def _get_last_audit_log(
    session_factory: async_sessionmaker[AsyncSession],
) -> AuditLogRow | None:
    """最後に書き込まれた audit_log レコードを返す（executed_at DESC LIMIT 1）。"""
    async with session_factory() as session:
        result = await session.execute(
            select(AuditLogRow).order_by(AuditLogRow.executed_at.desc()).limit(1)
        )
        return result.scalars().first()


async def _get_task_status(
    session_factory: async_sessionmaker[AsyncSession],
    task_id: UUID,
) -> str | None:
    """DB から task の status を直接取得する。

    UUIDStr TypeDecorator は UUID を 32 文字 hex（ハイフンなし）で保存するため、
    task_id.hex で検索する。
    """
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT status FROM tasks WHERE id = :id"),
            {"id": task_id.hex},  # 32 文字 hex（ハイフンなし）
        )
        row = result.fetchone()
        return row[0] if row else None


async def _get_outbox_row(
    session_factory: async_sessionmaker[AsyncSession],
    event_id: UUID,
) -> OutboxRow | None:
    """DB から OutboxRow を取得する。"""
    async with session_factory() as session:
        return await session.get(OutboxRow, str(event_id))


# ---------------------------------------------------------------------------
# TC-ST-AC-001 + TC-IT-AC-001: list_blocked_tasks — 正常系
# ---------------------------------------------------------------------------


class TestListBlockedTasks:
    """TC-ST-AC-001 / TC-IT-AC-001: list_blocked_tasks() の正常系テスト。"""

    async def test_returns_only_blocked_tasks(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_ctx: tuple[UUID, UUID],
    ) -> None:
        """TC-ST-AC-001 / TC-IT-AC-001: BLOCKED×3 + IN_PROGRESS×1 → 3件の BlockedTaskSummary。

        受入基準 #11 検証。
        """
        room_id, directive_id = seeded_task_ctx

        b1 = make_blocked_task(room_id=room_id, directive_id=directive_id, last_error="error 1")
        b2 = make_blocked_task(room_id=room_id, directive_id=directive_id, last_error="error 2")
        b3 = make_blocked_task(room_id=room_id, directive_id=directive_id, last_error="error 3")
        ip = make_in_progress_task(room_id=room_id, directive_id=directive_id)

        async with session_factory() as session, session.begin():
            repo = SqliteTaskRepository(session)
            await repo.save(b1)
            await repo.save(b2)
            await repo.save(b3)
            await repo.save(ip)

        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            result = await service.list_blocked_tasks()

        assert len(result) == 3
        returned_ids = {s.task_id for s in result}
        assert b1.id in returned_ids
        assert b2.id in returned_ids
        assert b3.id in returned_ids
        assert ip.id not in returned_ids

        # BlockedTaskSummary フィールド確認
        first = next(s for s in result if s.task_id == b1.id)
        assert first.room_id == room_id
        assert "error 1" in first.last_error
        assert isinstance(first.blocked_at, datetime)

    async def test_returns_empty_list_when_no_blocked(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_ctx: tuple[UUID, UUID],
    ) -> None:
        """TC-ST-AC-010 / TC-IT-AC-013: BLOCKED 0件 → [] + audit_log OK。"""
        room_id, directive_id = seeded_task_ctx
        ip = make_in_progress_task(room_id=room_id, directive_id=directive_id)

        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(ip)

        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            result = await service.list_blocked_tasks()

        assert result == []

        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.command == "list-blocked"
        assert audit.result == "OK"

    async def test_audit_log_recorded_with_ok(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-ST-AC-009: 空 DB で list_blocked → audit_log に OK が記録される（受入基準 #14）。"""
        async with session_factory() as session, session.begin():
            service = _make_admin_service(session, actor="ceo_user")
            result = await service.list_blocked_tasks()

        assert result == []

        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.command == "list-blocked"
        assert audit.result == "OK"
        assert audit.actor == "ceo_user"
        assert audit.error_text is None


# ---------------------------------------------------------------------------
# TC-ST-AC-002/003 + TC-IT-AC-002~004: retry_task
# ---------------------------------------------------------------------------


class TestRetryTask:
    """TC-ST-AC-002/003 + TC-IT-AC-002~004: retry_task() テスト。"""

    async def test_retry_blocked_task_to_in_progress(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_ctx: tuple[UUID, UUID],
    ) -> None:
        """TC-ST-AC-002 / TC-IT-AC-002: BLOCKED → IN_PROGRESS + audit_log OK（受入基準 #12 / #14）。"""
        room_id, directive_id = seeded_task_ctx
        blocked = make_blocked_task(room_id=room_id, directive_id=directive_id)

        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(blocked)

        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            await service.retry_task(blocked.id)

        # DB 確認: status が IN_PROGRESS に変わっている
        status = await _get_task_status(session_factory, blocked.id)
        assert status == "IN_PROGRESS"

        # audit_log 確認（受入基準 #14）
        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.command == "retry-task"
        assert audit.result == "OK"
        assert audit.error_text is None

    async def test_retry_task_not_found_raises_and_audit_fail(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-AC-003: 存在しない task_id → TaskNotFoundError + audit_log FAIL。"""
        nonexistent_id = uuid4()

        caught_exc: TaskNotFoundError | None = None
        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            try:
                await service.retry_task(nonexistent_id)
            except TaskNotFoundError as exc:
                caught_exc = exc

        assert caught_exc is not None, "TaskNotFoundError が送出されるべき"
        assert str(nonexistent_id) in str(caught_exc)

        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.command == "retry-task"
        assert audit.result == "FAIL"

    async def test_retry_non_blocked_task_raises_and_audit_fail(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_ctx: tuple[UUID, UUID],
    ) -> None:
        """TC-ST-AC-003 / TC-IT-AC-004: 非BLOCKED → IllegalTaskStateError + audit_log FAIL（§確定B/R1-2）。"""
        room_id, directive_id = seeded_task_ctx
        ip = make_in_progress_task(room_id=room_id, directive_id=directive_id)

        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(ip)

        caught_exc: IllegalTaskStateError | None = None
        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            try:
                await service.retry_task(ip.id)
            except IllegalTaskStateError as exc:
                caught_exc = exc

        assert caught_exc is not None
        # メッセージに BLOCKED キーワードが含まれる（MSG-AC-002）
        assert "BLOCKED" in str(caught_exc)

        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.command == "retry-task"
        assert audit.result == "FAIL"


# ---------------------------------------------------------------------------
# TC-ST-AC-004/005 + TC-IT-AC-005~008: cancel_task
# ---------------------------------------------------------------------------


class TestCancelTask:
    """TC-ST-AC-004/005 + TC-IT-AC-005~008: cancel_task() テスト。"""

    async def test_cancel_blocked_task_succeeds(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_ctx: tuple[UUID, UUID],
    ) -> None:
        """TC-ST-AC-004 / TC-IT-AC-005: BLOCKED → CANCELLED + audit_log OK（受入基準 #12b）。"""
        room_id, directive_id = seeded_task_ctx
        blocked = make_blocked_task(room_id=room_id, directive_id=directive_id)

        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(blocked)

        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            await service.cancel_task(blocked.id, reason="admin cancel")

        status = await _get_task_status(session_factory, blocked.id)
        assert status == "CANCELLED"

        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.command == "cancel-task"
        assert audit.result == "OK"

    async def test_cancel_in_progress_task_succeeds(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_ctx: tuple[UUID, UUID],
    ) -> None:
        """TC-IT-AC-006: IN_PROGRESS → CANCELLED + audit_log OK（R1-3 正常系）。"""
        room_id, directive_id = seeded_task_ctx
        ip = make_in_progress_task(room_id=room_id, directive_id=directive_id)

        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(ip)

        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            await service.cancel_task(ip.id, reason="admin cancel in_progress")

        status = await _get_task_status(session_factory, ip.id)
        assert status == "CANCELLED"

        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.result == "OK"

    async def test_cancel_awaiting_external_review_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_ctx: tuple[UUID, UUID],
    ) -> None:
        """TC-ST-AC-005 / TC-IT-AC-007: AWAITING_EXTERNAL_REVIEW → IllegalTaskStateError + FAIL（R1-3）。"""
        room_id, directive_id = seeded_task_ctx
        ar = make_awaiting_review_task(room_id=room_id, directive_id=directive_id)

        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(ar)

        caught_exc: IllegalTaskStateError | None = None
        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            try:
                await service.cancel_task(ar.id, reason="test")
            except IllegalTaskStateError as exc:
                caught_exc = exc

        assert caught_exc is not None

        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.command == "cancel-task"
        assert audit.result == "FAIL"

    async def test_cancel_done_task_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_ctx: tuple[UUID, UUID],
    ) -> None:
        """TC-IT-AC-008: DONE → IllegalTaskStateError + audit_log FAIL（R1-3）。"""
        room_id, directive_id = seeded_task_ctx
        done = make_done_task(room_id=room_id, directive_id=directive_id)

        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(done)

        caught_exc: IllegalTaskStateError | None = None
        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            try:
                await service.cancel_task(done.id, reason="test")
            except IllegalTaskStateError as exc:
                caught_exc = exc

        assert caught_exc is not None

        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.result == "FAIL"


# ---------------------------------------------------------------------------
# TC-ST-AC-006 + TC-IT-AC-009: list_dead_letters
# ---------------------------------------------------------------------------


class TestListDeadLetters:
    """TC-ST-AC-006 + TC-IT-AC-009: list_dead_letters() テスト。"""

    async def test_returns_only_dead_letters(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-ST-AC-006 / TC-IT-AC-009: DEAD_LETTER×2 + PENDING×1 → 2件（受入基準 #13a）。"""
        dl1 = make_outbox_row(status="DEAD_LETTER", attempt_count=3, last_error="timeout")
        dl2 = make_outbox_row(status="DEAD_LETTER", attempt_count=5, last_error="connection error")
        pending = make_outbox_row(status="PENDING")

        async with session_factory() as session, session.begin():
            session.add(dl1)
            session.add(dl2)
            session.add(pending)

        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            result = await service.list_dead_letters()

        assert len(result) == 2
        returned_ids = {s.event_id for s in result}
        assert dl1.event_id in returned_ids
        assert dl2.event_id in returned_ids
        assert pending.event_id not in returned_ids

        # フィールド確認
        s1 = next(s for s in result if s.event_id == dl1.event_id)
        assert s1.attempt_count == 3
        assert s1.last_error == "timeout"

    async def test_audit_log_recorded_for_list_dead_letters(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """list_dead_letters 後に audit_log OK が記録される（受入基準 #14）。"""
        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            await service.list_dead_letters()

        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.command == "list-dead-letters"
        assert audit.result == "OK"


# ---------------------------------------------------------------------------
# TC-ST-AC-007/008 + TC-IT-AC-010~012: retry_event
# ---------------------------------------------------------------------------


class TestRetryEvent:
    """TC-ST-AC-007/008 + TC-IT-AC-010~012: retry_event() テスト。"""

    async def test_reset_dead_letter_to_pending(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-ST-AC-007 / TC-IT-AC-010: DEAD_LETTER → PENDING + attempt_count=0 + audit_log OK（受入基準 #13b）。"""
        dl = make_outbox_row(status="DEAD_LETTER", attempt_count=5)

        async with session_factory() as session, session.begin():
            session.add(dl)

        before = datetime.now(UTC)

        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            await service.retry_event(dl.event_id)

        after = datetime.now(UTC)

        # DB 確認
        row = await _get_outbox_row(session_factory, dl.event_id)
        assert row is not None
        assert row.status == "PENDING"
        assert row.attempt_count == 0
        # next_attempt_at が now(UTC) 付近に設定される
        assert before <= row.next_attempt_at <= after

        # audit_log 確認
        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.command == "retry-event"
        assert audit.result == "OK"
        assert audit.error_text is None

    async def test_retry_event_not_found_raises_and_audit_fail(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-AC-011: 存在しない event_id → OutboxEventNotFoundError + audit_log FAIL。"""
        nonexistent_id = uuid4()

        caught_exc: OutboxEventNotFoundError | None = None
        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            try:
                await service.retry_event(nonexistent_id)
            except OutboxEventNotFoundError as exc:
                caught_exc = exc

        assert caught_exc is not None
        assert "[FAIL]" in str(caught_exc)

        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.command == "retry-event"
        assert audit.result == "FAIL"

    async def test_retry_event_not_dead_letter_raises_and_audit_fail(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-ST-AC-008 / TC-IT-AC-012: 非DEAD_LETTER → IllegalOutboxStateError + audit_log FAIL（§確定C/R1-5）。"""
        pending = make_outbox_row(status="PENDING")

        async with session_factory() as session, session.begin():
            session.add(pending)

        caught_exc: IllegalOutboxStateError | None = None
        async with session_factory() as session, session.begin():
            service = _make_admin_service(session)
            try:
                await service.retry_event(pending.event_id)
            except IllegalOutboxStateError as exc:
                caught_exc = exc

        assert caught_exc is not None
        assert "DEAD_LETTER" in str(caught_exc)

        audit = await _get_last_audit_log(session_factory)
        assert audit is not None
        assert audit.command == "retry-event"
        assert audit.result == "FAIL"
