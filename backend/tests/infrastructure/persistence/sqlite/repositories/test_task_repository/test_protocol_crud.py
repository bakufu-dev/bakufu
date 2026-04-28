"""Task Repository: Protocol surface + basic CRUD + 9-stage save + Lifecycle.

TC-UT-TR-001〜009 + TC-IT-TR-LIFECYCLE.

REQ-TR-001 / REQ-TR-002 — 6-method Protocol (§確定 R1-A / §確定 R1-D) +
CRUD (find_by_id / count / save / Tx boundary) + 9-stage semantics + Lifecycle.

Per ``docs/features/task-repository/test-design.md``.
Issue #35 — M2 0007.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
    SqliteTaskRepository,
)
from bakufu.domain.value_objects import TaskStatus
from sqlalchemy import event

from tests.factories.task import (
    make_blocked_task,
    make_deliverable,
    make_done_task,
    make_in_progress_task,
    make_task,
)
from tests.infrastructure.persistence.sqlite.repositories.test_task_repository.conftest import (
    seed_task_context,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-TR-001: Protocol definition + 6-method surface (§確定 R1-A / §確定 R1-D)
# ---------------------------------------------------------------------------
class TestTaskRepositoryProtocol:
    """TC-UT-TR-001: Protocol declares 6 async methods."""

    async def test_protocol_declares_six_async_methods(self) -> None:
        """TC-UT-TR-001: TaskRepository has all 6 required methods."""
        for method_name in (
            "find_by_id",
            "count",
            "save",
            "count_by_status",
            "count_by_room",
            "find_blocked",
        ):
            assert hasattr(TaskRepository, method_name), (
                f"[FAIL] TaskRepository.{method_name} missing.\n"
                f"Protocol requires 6 methods per §確定 R1-D."
            )

    async def test_protocol_does_not_have_yagni_methods(self) -> None:
        """TC-UT-TR-001: YAGNI methods (find_by_room, find_by_directive) absent.

        §確定 R1-D YAGNI 拒否済み: find_by_room requires pagination spec
        (未確定), find_by_directive has no callers. If these reappear, the
        YAGNI decision in requirements-analysis §確定 R1-D was reversed
        without updating the design doc first.
        """
        for banned_method in ("find_by_room", "find_by_directive"):
            assert not hasattr(TaskRepository, banned_method), (
                f"[FAIL] TaskRepository.{banned_method} must not exist (YAGNI).\n"
                f"Next: remove from Protocol, or update §確定 R1-D YAGNI 拒否 first."
            )

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-TR-001: SqliteTaskRepository satisfies TaskRepository Protocol."""
        async with session_factory() as session:
            repo: TaskRepository = SqliteTaskRepository(session)
            for method_name in (
                "find_by_id",
                "count",
                "save",
                "count_by_status",
                "count_by_room",
                "find_blocked",
            ):
                assert hasattr(repo, method_name)

    async def test_sqlite_repository_duck_typing_6_methods(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-TR-001: duck-typing confirms all 6 methods present on impl."""
        async with session_factory() as session:
            repo = SqliteTaskRepository(session)
            for method_name in (
                "find_by_id",
                "count",
                "save",
                "count_by_status",
                "count_by_room",
                "find_blocked",
            ):
                assert hasattr(repo, method_name), (
                    f"[FAIL] SqliteTaskRepository.{method_name} missing."
                )


# ---------------------------------------------------------------------------
# TC-UT-TR-002: find_by_id (REQ-TR-002)
# ---------------------------------------------------------------------------
class TestFindById:
    """TC-UT-TR-002: find_by_id retrieves saved Tasks; None for unknown."""

    async def test_find_by_id_returns_saved_task(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """save(task) → find_by_id(task.id) returns the Task."""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            fetched = await SqliteTaskRepository(session).find_by_id(task.id)
        assert fetched is not None
        assert fetched.id == task.id

    async def test_find_by_id_returns_none_for_unknown(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """find_by_id with unknown TaskId returns None."""
        async with session_factory() as session:
            result = await SqliteTaskRepository(session).find_by_id(uuid4())  # type: ignore[arg-type]
        assert result is None


# ---------------------------------------------------------------------------
# TC-UT-TR-003: save round-trip — all attributes (§確定 R1-H / §確定 R1-J)
# ---------------------------------------------------------------------------
class TestSaveRoundTrip:
    """TC-UT-TR-003: save → find_by_id round-trips all Task attributes."""

    async def test_save_find_by_id_round_trip_all_attributes(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """All scalar + child attributes survive save → find_by_id round-trip.

        §確定 R1-J: _from_rows reconstructs assigned_agent_ids (order_index order)
        and deliverables (dict[StageId, Deliverable]). conversations are empty
        because the Task domain model has no conversations attribute yet.
        """
        room_id, directive_id = seeded_task_context
        agent1_id = uuid4()
        agent2_id = uuid4()
        stage_id = uuid4()
        deliverable = make_deliverable(stage_id=stage_id, body_markdown="# 成果物本文")

        task = make_task(
            room_id=room_id,
            directive_id=directive_id,
            status=TaskStatus.IN_PROGRESS,
            assigned_agent_ids=[agent1_id, agent2_id],
            deliverables={stage_id: deliverable},  # type: ignore[dict-item]
            last_error=None,
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(task.id)

        assert restored is not None
        assert restored.id == task.id
        assert restored.room_id == task.room_id
        assert restored.directive_id == task.directive_id
        assert restored.current_stage_id == task.current_stage_id
        assert restored.status == task.status
        assert restored.last_error == task.last_error
        assert restored.created_at.tzinfo is not None, (
            "[FAIL] created_at lost timezone info in round-trip."
        )
        assert restored.updated_at.tzinfo is not None, (
            "[FAIL] updated_at lost timezone info in round-trip."
        )
        # §確定 R1-J: assigned_agent_ids preserved in order_index order
        assert restored.assigned_agent_ids == [agent1_id, agent2_id], (
            f"[FAIL] assigned_agent_ids order not preserved.\n"
            f"Expected: {[agent1_id, agent2_id]}\nGot: {restored.assigned_agent_ids}"
        )
        # §確定 R1-J: deliverables dict keyed by stage_id
        assert stage_id in restored.deliverables, (  # type: ignore[operator]
            f"[FAIL] deliverables dict missing stage_id={stage_id}"
        )
        restored_deliv = restored.deliverables[stage_id]  # type: ignore[index]
        assert restored_deliv.body_markdown == deliverable.body_markdown

    async def test_created_at_is_utc_timezone_aware_after_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """created_at / updated_at are UTC tz-aware after find_by_id."""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(task.id)

        assert restored is not None
        assert restored.created_at.tzinfo is not None
        assert restored.updated_at.tzinfo is not None

    async def test_last_error_none_survives_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """PENDING task with last_error=None round-trips as None."""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id, last_error=None)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(task.id)

        assert restored is not None
        assert restored.last_error is None

    async def test_empty_assigned_agents_survives_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Task with no assigned agents round-trips with empty list."""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id, assigned_agent_ids=[])
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(task.id)

        assert restored is not None
        assert restored.assigned_agent_ids == []

    async def test_empty_deliverables_survives_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Task with no deliverables round-trips with empty dict."""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id, deliverables={})
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(task.id)

        assert restored is not None
        assert restored.deliverables == {}


# ---------------------------------------------------------------------------
# TC-UT-TR-004: count() SQL COUNT(*) (empire §確定 D 踏襲)
# ---------------------------------------------------------------------------
class TestCountScalar:
    """TC-UT-TR-004: count() issues SELECT COUNT(*) without full row load."""

    async def test_count_emits_select_count_not_full_load(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """count() SQL log contains COUNT(*); full-row SELECT is absent."""
        room_id, directive_id = seeded_task_context
        for _ in range(3):
            async with session_factory() as session, session.begin():
                await SqliteTaskRepository(session).save(
                    make_task(room_id=room_id, directive_id=directive_id)
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
                result = await SqliteTaskRepository(session).count()
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        assert result == 3
        count_stmts = [s for s in captured if "count" in s.lower() and "tasks" in s.lower()]
        assert count_stmts, (
            f"[FAIL] count() did not emit SELECT count(*) FROM tasks.\n"
            f"Captured: {captured}"
        )
        # Full-row load path must NOT appear
        full_load_stmts = [
            s for s in captured
            if "FROM tasks" in s and "SELECT" in s.upper() and "count" not in s.lower()
        ]
        assert not full_load_stmts, (
            f"[FAIL] count() emitted a full-row SELECT instead of COUNT(*).\n"
            f"Full-load stmts: {full_load_stmts}"
        )


# ---------------------------------------------------------------------------
# TC-UT-TR-005: save() 9-stage DELETE+UPSERT+INSERT semantics (§確定 R1-B)
# ---------------------------------------------------------------------------
class TestSave9StageSemantics:
    """TC-UT-TR-005: save() 9-stage order and re-save UPSERT semantics."""

    async def test_resave_updates_scalar_fields(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Re-saving a Task updates mutable scalar fields (ON CONFLICT DO UPDATE).

        Tests stage 4 (UPSERT): current_stage_id / status / last_error / updated_at
        are updated; room_id / directive_id / created_at are NOT updated.
        """
        room_id, directive_id = seeded_task_context
        original = make_task(room_id=room_id, directive_id=directive_id)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(original)

        # Re-save with different status (PENDING → IN_PROGRESS via factory bypass)
        updated = make_in_progress_task(
            task_id=original.id,
            room_id=room_id,
            directive_id=directive_id,
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(updated)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(original.id)

        assert restored is not None
        assert restored.status == TaskStatus.IN_PROGRESS
        # room_id / directive_id / created_at remain from original (immutable)
        assert restored.room_id == original.room_id
        assert restored.directive_id == original.directive_id

    async def test_resave_does_not_duplicate_task_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Re-saving same task_id does not duplicate the tasks row (UPSERT)."""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            count = await SqliteTaskRepository(session).count()
        assert count == 1, (
            f"[FAIL] Re-saving a Task duplicated the row. count={count}"
        )

    async def test_resave_reinsertes_child_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Re-save with different assigned_agents re-inserts task_assigned_agents.

        Tests stages 3 (DELETE task_assigned_agents) + 5 (INSERT new agents).
        Original agents are cleared, new agents are written.
        """
        room_id, directive_id = seeded_task_context
        agent_a = uuid4()
        agent_b = uuid4()
        agent_c = uuid4()

        original = make_task(
            room_id=room_id, directive_id=directive_id, assigned_agent_ids=[agent_a]
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(original)

        # Re-save with different agents
        updated = make_in_progress_task(
            task_id=original.id,
            room_id=room_id,
            directive_id=directive_id,
            assigned_agent_ids=[agent_b, agent_c],
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(updated)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(original.id)

        assert restored is not None
        assert restored.assigned_agent_ids == [agent_b, agent_c], (
            f"[FAIL] assigned_agent_ids not updated after re-save.\n"
            f"Expected: {[agent_b, agent_c]}\nGot: {restored.assigned_agent_ids}"
        )

    async def test_resave_deliverable_unique_constraint_no_duplicate(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-005b: re-saving same stage_id deliverable does not violate UNIQUE.

        UNIQUE(task_id, stage_id) constraint: stage 1 DELETEs old deliverable
        rows, stage 8 INSERTs fresh ones. No UNIQUE violation occurs because
        DELETE happens before INSERT.
        """
        room_id, directive_id = seeded_task_context
        stage_id = uuid4()
        deliv_v1 = make_deliverable(stage_id=stage_id, body_markdown="# バージョン1")
        task_v1 = make_task(
            room_id=room_id,
            directive_id=directive_id,
            deliverables={stage_id: deliv_v1},  # type: ignore[dict-item]
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task_v1)

        deliv_v2 = make_deliverable(stage_id=stage_id, body_markdown="# バージョン2")
        task_v2 = make_task(
            task_id=task_v1.id,
            room_id=room_id,
            directive_id=directive_id,
            deliverables={stage_id: deliv_v2},  # type: ignore[dict-item]
        )
        # Must not raise IntegrityError (UNIQUE constraint)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task_v2)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(task_v1.id)

        assert restored is not None
        assert restored.deliverables[stage_id].body_markdown == "# バージョン2", (  # type: ignore[index]
            "[FAIL] Deliverable body_markdown not updated after re-save."
        )

    async def test_resave_empty_to_full_task_all_child_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-005c: empty task → full task (agents + deliverables) on re-save."""
        room_id, directive_id = seeded_task_context
        # Initially empty
        empty_task = make_task(
            room_id=room_id,
            directive_id=directive_id,
            assigned_agent_ids=[],
            deliverables={},
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(empty_task)

        # Re-save with agents + deliverables
        stage_id = uuid4()
        deliv = make_deliverable(stage_id=stage_id)
        full_task = make_in_progress_task(
            task_id=empty_task.id,
            room_id=room_id,
            directive_id=directive_id,
            assigned_agent_ids=[uuid4(), uuid4()],
            deliverables={stage_id: deliv},  # type: ignore[dict-item]
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(full_task)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(empty_task.id)

        assert restored is not None
        assert len(restored.assigned_agent_ids) == 2
        assert stage_id in restored.deliverables  # type: ignore[operator]


# ---------------------------------------------------------------------------
# TC-UT-TR-009: Tx boundary (empire §確定 B 踏襲)
# ---------------------------------------------------------------------------
class TestTxBoundary:
    """TC-UT-TR-009: Repository does not auto-commit; caller owns UoW boundary."""

    async def test_save_within_begin_persists(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """save inside async with session.begin() persists the row."""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            fetched = await SqliteTaskRepository(session).find_by_id(task.id)
        assert fetched is not None

    async def test_save_without_begin_does_not_persist(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """save without session.begin() leaves row absent after session close.

        Without begin(), SQLAlchemy async session auto-rolls back on exit.
        """
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id)
        async with session_factory() as session:
            # No session.begin() → auto-rollback on __aexit__
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            fetched = await SqliteTaskRepository(session).find_by_id(task.id)
        assert fetched is None, (
            "[FAIL] Repository auto-committed without session.begin().\n"
            "Next: verify save() does not call session.commit()."
        )


# ---------------------------------------------------------------------------
# TC-IT-TR-LIFECYCLE: 6-method full lifecycle
# ---------------------------------------------------------------------------
class TestLifecycleIntegration:
    """TC-IT-TR-LIFECYCLE: 6-method full lifecycle integration."""

    async def test_full_lifecycle_6_method(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """6-method lifecycle: save×2 → count_by_status → find_blocked → count_by_room → count → re-save → verify."""
        room_id, directive_id = seeded_task_context

        # Step 1: save a PENDING task and a BLOCKED task
        pending = make_task(room_id=room_id, directive_id=directive_id)
        blocked = make_blocked_task(
            room_id=room_id,
            directive_id=directive_id,
            last_error="AuthExpired: service token expired",
        )
        async with session_factory() as session, session.begin():
            repo = SqliteTaskRepository(session)
            await repo.save(pending)
            await repo.save(blocked)

        # Step 2: count_by_status
        async with session_factory() as session:
            blocked_count = await SqliteTaskRepository(session).count_by_status(
                TaskStatus.BLOCKED
            )
        assert blocked_count == 1

        # Step 3: find_blocked returns the blocked task
        async with session_factory() as session:
            blocked_tasks = await SqliteTaskRepository(session).find_blocked()
        assert len(blocked_tasks) == 1
        assert blocked_tasks[0].id == blocked.id

        # Step 4: count_by_room
        async with session_factory() as session:
            room_count = await SqliteTaskRepository(session).count_by_room(room_id)  # type: ignore[arg-type]
        assert room_count == 2

        # Step 5: count
        async with session_factory() as session:
            total = await SqliteTaskRepository(session).count()
        assert total == 2

        # Step 6: re-save blocked with updated status (DONE)
        done = make_done_task(
            task_id=blocked.id,
            room_id=room_id,
            directive_id=directive_id,
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(done)

        # Step 7: find_blocked returns [] now
        async with session_factory() as session:
            blocked_after = await SqliteTaskRepository(session).find_blocked()
        assert blocked_after == []

        # Step 8: count_by_status(BLOCKED) == 0
        async with session_factory() as session:
            blocked_count_after = await SqliteTaskRepository(session).count_by_status(
                TaskStatus.BLOCKED
            )
        assert blocked_count_after == 0
