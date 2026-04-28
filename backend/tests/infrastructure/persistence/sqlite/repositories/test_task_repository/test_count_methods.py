"""Task Repository: count_by_status / count_by_room (TC-UT-TR-006/007).

REQ-TR-003 / §確定 R1-D — 2 COUNT query methods:
  * ``count_by_status(status)`` — COUNT(*) WHERE status = ?
  * ``count_by_room(room_id)``  — COUNT(*) WHERE room_id = ?

Per ``docs/features/task-repository/test-design.md``.
Issue #35 — M2 0007.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from bakufu.domain.value_objects import TaskStatus
from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
    SqliteTaskRepository,
)
from sqlalchemy import event

from tests.factories.task import (
    make_blocked_task,
    make_done_task,
    make_task,
)
from tests.infrastructure.persistence.sqlite.repositories.test_task_repository.conftest import (
    seed_task_context,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-TR-006: count_by_status (§確定 R1-D)
# ---------------------------------------------------------------------------
class TestCountByStatus:
    """TC-UT-TR-006: count_by_status counts Tasks by status; Room-isolation."""

    async def test_count_by_status_pending(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """count_by_status(PENDING) returns only PENDING count."""
        room_id, directive_id = seeded_task_context
        for _ in range(2):
            async with session_factory() as session, session.begin():
                await SqliteTaskRepository(session).save(
                    make_task(room_id=room_id, directive_id=directive_id)
                )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(
                make_blocked_task(room_id=room_id, directive_id=directive_id)
            )

        async with session_factory() as session:
            pending_count = await SqliteTaskRepository(session).count_by_status(TaskStatus.PENDING)
        assert pending_count == 2, (
            f"[FAIL] count_by_status(PENDING) expected 2, got {pending_count}"
        )

    async def test_count_by_status_blocked(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """count_by_status(BLOCKED) counts only BLOCKED tasks."""
        room_id, directive_id = seeded_task_context
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(
                make_task(room_id=room_id, directive_id=directive_id)
            )
            await SqliteTaskRepository(session).save(
                make_blocked_task(room_id=room_id, directive_id=directive_id)
            )
            await SqliteTaskRepository(session).save(
                make_done_task(room_id=room_id, directive_id=directive_id)
            )

        async with session_factory() as session:
            count = await SqliteTaskRepository(session).count_by_status(TaskStatus.BLOCKED)
        assert count == 1

    async def test_count_by_status_returns_zero_when_none(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """count_by_status returns 0 when no Tasks with that status exist."""
        room_id, directive_id = seeded_task_context
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(
                make_task(room_id=room_id, directive_id=directive_id)
            )

        async with session_factory() as session:
            blocked_count = await SqliteTaskRepository(session).count_by_status(TaskStatus.BLOCKED)
        assert blocked_count == 0

    async def test_count_by_status_emits_sql_count(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """count_by_status SQL log shows COUNT(*) WHERE status filter."""
        room_id, directive_id = seeded_task_context
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(
                make_blocked_task(room_id=room_id, directive_id=directive_id)
            )

        captured: list[str] = []

        def _on_execute(
            _conn: object,
            _cursor: object,
            statement: str,
            _params: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            captured.append(statement)

        sync_engine = app_engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _on_execute)
        try:
            async with session_factory() as session:
                await SqliteTaskRepository(session).count_by_status(TaskStatus.BLOCKED)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        count_stmts = [s for s in captured if "count" in s.lower() and "tasks" in s.lower()]
        assert count_stmts, (
            f"[FAIL] count_by_status() did not emit COUNT(*) FROM tasks.\nCaptured: {captured}"
        )


# ---------------------------------------------------------------------------
# TC-UT-TR-007: count_by_room (§確定 R1-D)
# ---------------------------------------------------------------------------
class TestCountByRoom:
    """TC-UT-TR-007: count_by_room counts Tasks per Room; cross-room isolation."""

    async def test_count_by_room_returns_correct_count(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """count_by_room returns only tasks in the specified room."""
        room_id, directive_id = seeded_task_context
        for _ in range(3):
            async with session_factory() as session, session.begin():
                await SqliteTaskRepository(session).save(
                    make_task(room_id=room_id, directive_id=directive_id)
                )

        async with session_factory() as session:
            count = await SqliteTaskRepository(session).count_by_room(room_id)  # type: ignore[arg-type]
        assert count == 3

    async def test_count_by_room_returns_zero_for_empty_room(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """count_by_room returns 0 for a room with no tasks."""
        room_id, _directive_id = seeded_task_context
        # Seed tasks in a different room
        room2_id, directive2_id = await seed_task_context(session_factory)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(
                make_task(room_id=room2_id, directive_id=directive2_id)
            )

        async with session_factory() as session:
            count = await SqliteTaskRepository(session).count_by_room(room_id)  # type: ignore[arg-type]
        assert count == 0, f"[FAIL] count_by_room leaked tasks from another room. count={count}"

    async def test_count_by_room_cross_room_isolation(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-007: count_by_room does not bleed across rooms."""
        room_a_id, directive_a_id = seeded_task_context
        room_b_id, directive_b_id = await seed_task_context(session_factory)

        # 2 tasks in room A, 3 tasks in room B
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(
                make_task(room_id=room_a_id, directive_id=directive_a_id)
            )
            await SqliteTaskRepository(session).save(
                make_task(room_id=room_a_id, directive_id=directive_a_id)
            )
        async with session_factory() as session, session.begin():
            for _ in range(3):
                await SqliteTaskRepository(session).save(
                    make_task(room_id=room_b_id, directive_id=directive_b_id)
                )

        async with session_factory() as session:
            count_a = await SqliteTaskRepository(session).count_by_room(room_a_id)  # type: ignore[arg-type]
        async with session_factory() as session:
            count_b = await SqliteTaskRepository(session).count_by_room(room_b_id)  # type: ignore[arg-type]

        assert count_a == 2, f"[FAIL] count_by_room(room_a) expected 2, got {count_a}"
        assert count_b == 3, f"[FAIL] count_by_room(room_b) expected 3, got {count_b}"
