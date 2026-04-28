"""Task Repository: save() child-table semantics (TC-UT-TR-005/005b/005c).

REQ-TR-001 / §確定 R1-B — 6-stage save() DELETE+UPSERT+INSERT semantics:
  Stage 1: DELETE deliverables WHERE task_id = ?
  Stage 2: DELETE task_assigned_agents WHERE task_id = ?
  Stage 3: UPSERT tasks (ON CONFLICT DO UPDATE mutable fields)
  Stage 4: INSERT task_assigned_agents (order_index)
  Stage 5: INSERT deliverables
  Stage 6: INSERT deliverable_attachments

Child tables are fully replaced on every save() call.
UNIQUE(task_id, stage_id) on deliverables is safe because DELETE precedes INSERT.

Per ``docs/features/task-repository/test-design.md`` TC-UT-TR-005/005b/005c.
Issue #35 — M2 0007.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.domain.value_objects import TaskStatus
from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
    SqliteTaskRepository,
)

from tests.factories.task import (
    make_deliverable,
    make_in_progress_task,
    make_task,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-TR-005: save() 6-stage DELETE+UPSERT+INSERT semantics (§確定 R1-B)
# ---------------------------------------------------------------------------
class TestSaveChildTableSemantics:
    """TC-UT-TR-005/005b/005c: save() 6-stage order and re-save UPSERT semantics."""

    async def test_resave_updates_scalar_fields(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Re-saving a Task updates mutable scalar fields (ON CONFLICT DO UPDATE).

        Tests stage 3 (UPSERT): current_stage_id / status / last_error / updated_at
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
        assert count == 1, f"[FAIL] Re-saving a Task duplicated the row. count={count}"

    async def test_resave_reinsertes_child_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Re-save with different assigned_agents re-inserts task_assigned_agents.

        Tests stages 2 (DELETE task_assigned_agents) + 4 (INSERT new agents).
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
        rows, stage 5 INSERTs fresh ones. No UNIQUE violation occurs because
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
