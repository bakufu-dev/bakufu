"""Task Repository: count_by_status / count_by_room / find_blocked.

TC-UT-TR-006 / TC-UT-TR-007 / TC-UT-TR-008〜008e.

REQ-TR-003 / §確定 R1-D — 3 query methods:
  * ``count_by_status(status)`` — COUNT(*) WHERE status = ?
  * ``count_by_room(room_id)``  — COUNT(*) WHERE room_id = ?
  * ``find_blocked()``          — SELECT BLOCKED ORDER BY updated_at DESC, id DESC

Per ``docs/features/task-repository/test-design.md``.
Issue #35 — M2 0007.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.domain.value_objects import TaskStatus
from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
    SqliteTaskRepository,
)
from sqlalchemy import event

from tests.factories.task import (
    make_blocked_task,
    make_deliverable,
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


# ---------------------------------------------------------------------------
# TC-UT-TR-008: find_blocked returns only BLOCKED Tasks (§確定 R1-D)
# ---------------------------------------------------------------------------
class TestFindBlocked:
    """TC-UT-TR-008: find_blocked returns only BLOCKED Tasks; empty → []; tiebreaker."""

    async def test_find_blocked_returns_only_blocked(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-008: find_blocked returns BLOCKED tasks; skips PENDING/DONE."""
        room_id, directive_id = seeded_task_context
        pending = make_task(room_id=room_id, directive_id=directive_id)
        blocked = make_blocked_task(
            room_id=room_id,
            directive_id=directive_id,
            last_error="AuthExpired: token expired",
        )
        done = make_done_task(room_id=room_id, directive_id=directive_id)

        async with session_factory() as session, session.begin():
            repo = SqliteTaskRepository(session)
            await repo.save(pending)
            await repo.save(blocked)
            await repo.save(done)

        async with session_factory() as session:
            results = await SqliteTaskRepository(session).find_blocked()

        assert len(results) == 1, (
            f"[FAIL] find_blocked returned {len(results)} tasks; expected 1 (only BLOCKED)."
        )
        assert results[0].id == blocked.id
        assert results[0].status == TaskStatus.BLOCKED

    async def test_find_blocked_returns_empty_when_none_blocked(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-008b: find_blocked returns [] when no BLOCKED Tasks exist."""
        room_id, directive_id = seeded_task_context
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(
                make_task(room_id=room_id, directive_id=directive_id)
            )

        async with session_factory() as session:
            results = await SqliteTaskRepository(session).find_blocked()

        assert results == [], f"[FAIL] find_blocked returned {results!r} but expected []."

    async def test_find_blocked_returns_empty_from_empty_db(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-TR-008b: find_blocked on empty DB returns []."""
        async with session_factory() as session:
            results = await SqliteTaskRepository(session).find_blocked()
        assert results == []

    async def test_find_blocked_emits_status_filter_sql(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-008c: find_blocked SQL log shows WHERE status = 'BLOCKED' ORDER BY."""
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
                await SqliteTaskRepository(session).find_blocked()
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        # The find_blocked statement must include tasks table with ORDER BY
        status_stmts = [s for s in captured if "tasks" in s.lower() and "status" in s.lower()]
        assert status_stmts, (
            f"[FAIL] find_blocked() did not emit SQL with tasks + status filter.\n"
            f"Captured: {captured}"
        )
        # ORDER BY must be present (DESC ordering for recency-first)
        order_stmts = [s for s in status_stmts if "order by" in s.lower() or "ORDER BY" in s]
        assert order_stmts, (
            f"[FAIL] find_blocked() SQL lacks ORDER BY clause.\nstatus_stmts: {status_stmts}"
        )

    async def test_find_blocked_restores_full_attributes(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-008d: find_blocked hydrates complete BLOCKED task attributes.

        Includes assigned_agent_ids, deliverables, and all scalar fields.
        """
        room_id, directive_id = seeded_task_context
        agent_id = uuid4()
        stage_id = uuid4()
        deliv = make_deliverable(stage_id=stage_id, body_markdown="# ブロック時成果物")

        blocked = make_blocked_task(
            room_id=room_id,
            directive_id=directive_id,
            last_error="AuthExpired: service token expired after rate limit",
            assigned_agent_ids=[agent_id],
            deliverables={stage_id: deliv},  # type: ignore[dict-item]
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(blocked)

        async with session_factory() as session:
            results = await SqliteTaskRepository(session).find_blocked()

        assert len(results) == 1
        restored = results[0]
        assert restored.id == blocked.id
        assert restored.status == TaskStatus.BLOCKED
        assert restored.room_id == blocked.room_id
        assert restored.directive_id == blocked.directive_id
        assert len(restored.assigned_agent_ids) == 1
        assert restored.assigned_agent_ids[0] == agent_id
        assert stage_id in restored.deliverables  # type: ignore[operator]
        assert restored.last_error is not None  # last_error was masked at save time
        assert restored.created_at.tzinfo is not None
        assert restored.updated_at.tzinfo is not None

    async def test_find_blocked_tiebreaker_id_desc(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-008e: BUG-EMR-001規約 — same updated_at → ORDER BY id DESC tiebreaker.

        Two BLOCKED Tasks with identical updated_at timestamps must be
        ordered id DESC. The task with the hex-greater UUID must appear
        first in find_blocked() results.

        This test physically asserts the tiebreaker from §確定 R1-K
        ``ORDER BY updated_at DESC, id DESC`` by controlling both IDs and
        timestamps at construction time.
        """
        room_id, directive_id = seeded_task_context

        # Pin a shared updated_at so the tiebreaker kicks in.
        fixed_ts = datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC)

        # UUID hex: "ffffffff..." > "00000000..." lexicographically.
        id_high = UUID("ffffffff-ffff-4000-8000-000000000001")
        id_low = UUID("00000000-0000-4000-8000-000000000001")

        task_low = make_blocked_task(
            task_id=id_low,
            room_id=room_id,
            directive_id=directive_id,
            last_error="error low",
            updated_at=fixed_ts,
        )
        task_high = make_blocked_task(
            task_id=id_high,
            room_id=room_id,
            directive_id=directive_id,
            last_error="error high",
            updated_at=fixed_ts,
        )

        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task_low)
            await SqliteTaskRepository(session).save(task_high)

        async with session_factory() as session:
            results = await SqliteTaskRepository(session).find_blocked()

        assert len(results) == 2, f"[FAIL] Expected 2 BLOCKED tasks, got {len(results)}"
        # id DESC: id_high must come before id_low
        assert results[0].id == id_high, (
            f"[FAIL] Tiebreaker ORDER BY id DESC violated.\n"
            f"Expected first: {id_high!r}\n"
            f"Got first:      {results[0].id!r}\n"
            f"BUG-EMR-001規約: find_blocked ORDER BY updated_at DESC, id DESC must "
            f"produce deterministic ordering when updated_at is equal."
        )
        assert results[1].id == id_low
