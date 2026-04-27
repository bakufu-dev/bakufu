"""Workflow Repository: Protocol surface + basic CRUD coverage.

TC-IT-WFR-001 / 002 / 003 / 004 / 005 / 006 / 007 / 019 — the
entry-point behaviors empire-repository (PR #25) froze and that this
PR inherits 100%, plus the Workflow-specific ``ORDER BY stage_id`` /
``ORDER BY transition_id`` SQL log observation (BUG-EMR-001 from-day-1
contract per detailed-design.md L51).

Per ``docs/features/workflow-repository/test-design.md`` matrix.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from bakufu.application.ports.workflow_repository import WorkflowRepository
from bakufu.domain.value_objects import WorkflowId
from bakufu.domain.workflow import Workflow
from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
    SqliteWorkflowRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflow_stages import (
    WorkflowStageRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflow_transitions import (
    WorkflowTransitionRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflows import WorkflowRow
from sqlalchemy import event, select

from tests.factories.workflow import make_stage, make_transition, make_workflow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# REQ-WFR-001: Protocol definition + 充足 (§確定 A)
# ---------------------------------------------------------------------------
class TestWorkflowRepositoryProtocol:
    """TC-IT-WFR-001 / 002: Protocol surface + duck-typing 充足."""

    async def test_protocol_declares_three_async_methods(self) -> None:
        """TC-IT-WFR-001: ``WorkflowRepository`` has find_by_id / count / save."""
        # Protocol classes don't expose the methods at instance level
        # but at class level. Marked ``async`` purely so the
        # module-level ``pytestmark = asyncio`` does not warn.
        assert hasattr(WorkflowRepository, "find_by_id")
        assert hasattr(WorkflowRepository, "count")
        assert hasattr(WorkflowRepository, "save")

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-002: ``SqliteWorkflowRepository`` is assignable to ``WorkflowRepository``.

        The variable annotation acts as a static-type assertion; pyright
        strict will reject the assignment if any Protocol method is
        missing or has a wrong signature. Duck-typing at runtime
        confirms the three methods exist on the instance too.
        """
        async with session_factory() as session:
            repo: WorkflowRepository = SqliteWorkflowRepository(session)
            assert hasattr(repo, "find_by_id")
            assert hasattr(repo, "count")
            assert hasattr(repo, "save")


# ---------------------------------------------------------------------------
# REQ-WFR-002: find_by_id / count / save 基本 CRUD
# ---------------------------------------------------------------------------
class TestFindById:
    """TC-IT-WFR-003 / 004: find_by_id retrieves saved Workflows; None for unknown."""

    async def test_find_by_id_returns_saved_workflow(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-003: ``find_by_id(workflow.id)`` returns a structurally-equal Workflow.

        Uses ``make_workflow()`` default (single ``WORK`` stage, no
        ``EXTERNAL_REVIEW`` → no notify_channels) so §確定 H §不可逆性
        does not bite. Round-trip equality of the irreversible-masking
        path lives in :mod:`...test_masking`.
        """
        workflow = make_workflow()
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            fetched = await SqliteWorkflowRepository(session).find_by_id(workflow.id)

        assert fetched is not None
        assert fetched == workflow

    async def test_find_by_id_returns_none_for_unknown(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-004: ``find_by_id(uuid4())`` returns ``None`` without raising."""
        unknown_id = uuid4()
        async with session_factory() as session:
            fetched = await SqliteWorkflowRepository(session).find_by_id(unknown_id)
        assert fetched is None


# ---------------------------------------------------------------------------
# REQ-WFR-002 (ORDER BY contract per BUG-EMR-001 inherited from day 1)
# ---------------------------------------------------------------------------
class TestFindByIdOrderByContract:
    """TC-IT-WFR-005 / 006: ``ORDER BY stage_id`` / ``ORDER BY transition_id`` are emitted.

    The empire-repository BUG-EMR-001 closure froze the ORDER BY
    contract; the workflow Repository adopts it from PR #1. Without
    these clauses, SQLite returns rows in internal-scan order which
    would break ``Workflow == Workflow`` round-trip equality (the
    Aggregate compares list-by-list).

    We attach a ``before_cursor_execute`` listener on the **sync**
    engine and observe the actual SQL strings the dialect emits so a
    silent removal of ``ORDER BY`` is caught even if the round-trip
    test happens to pass via row-order coincidence.
    """

    async def _build_multi_stage_workflow(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> tuple[Workflow, WorkflowId]:
        """Build + save a 3-stage / 2-transition Workflow without EXTERNAL_REVIEW.

        Returns the constructed workflow plus its id so the caller can
        round-trip it. ``WORK`` stages do not require notify_channels,
        so no §確定 H §不可逆性 trap.
        """
        stage_a = make_stage(name="ステージA")
        stage_b = make_stage(name="ステージB")
        stage_c = make_stage(name="ステージC")
        transition_ab = make_transition(
            from_stage_id=stage_a.id,
            to_stage_id=stage_b.id,
        )
        transition_bc = make_transition(
            from_stage_id=stage_b.id,
            to_stage_id=stage_c.id,
        )
        workflow = make_workflow(
            stages=[stage_a, stage_b, stage_c],
            transitions=[transition_ab, transition_bc],
            entry_stage_id=stage_a.id,
        )
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)
        return workflow, workflow.id

    async def test_find_by_id_emits_order_by_stage_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-005: ``find_by_id`` emits ``ORDER BY workflow_stages.stage_id``."""
        _, workflow_id = await self._build_multi_stage_workflow(session_factory)

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
                await SqliteWorkflowRepository(session).find_by_id(workflow_id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        # The Workflow's stage SELECT must carry an ``ORDER BY`` on the
        # stage_id column. We accept any whitespace / fully-qualified
        # variation that SQLAlchemy chooses to emit.
        stage_selects = [
            stmt for stmt in captured if "FROM workflow_stages" in stmt and "SELECT" in stmt.upper()
        ]
        assert stage_selects, "find_by_id must SELECT from workflow_stages"
        assert any("ORDER BY" in stmt.upper() and "stage_id" in stmt for stmt in stage_selects), (
            "find_by_id must issue ``ORDER BY ... stage_id`` per "
            "detailed-design.md L51 (BUG-EMR-001 from day 1). "
            f"Captured stage SELECTs: {stage_selects}"
        )

    async def test_find_by_id_emits_order_by_transition_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-006: ``find_by_id`` emits ``ORDER BY workflow_transitions.transition_id``."""
        _, workflow_id = await self._build_multi_stage_workflow(session_factory)

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
                await SqliteWorkflowRepository(session).find_by_id(workflow_id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        transition_selects = [
            stmt
            for stmt in captured
            if "FROM workflow_transitions" in stmt and "SELECT" in stmt.upper()
        ]
        assert transition_selects, "find_by_id must SELECT from workflow_transitions"
        assert any(
            "ORDER BY" in stmt.upper() and "transition_id" in stmt for stmt in transition_selects
        ), (
            "find_by_id must issue ``ORDER BY ... transition_id`` per "
            "detailed-design.md L51 (BUG-EMR-001 from day 1). "
            f"Captured transition SELECTs: {transition_selects}"
        )


# ---------------------------------------------------------------------------
# REQ-WFR-002 (count() must issue SQL-level COUNT(*))
# ---------------------------------------------------------------------------
class TestCountIssuesScalarCount:
    """TC-IT-WFR-007: ``count()`` issues ``SELECT COUNT(*)``, not a full row scan."""

    async def test_count_emits_select_count_not_full_load(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-007: SQL log shows ``SELECT count(*)`` for ``count()``.

        Empire-repository §確定 D 補強: ``count()`` must not stream
        every row back to Python and call ``len()``. With Workflow
        preset libraries we expect hundreds of rows, so the SQL-level
        COUNT(*) pattern matters even more than for Empire.
        """
        # Save two workflows so a hypothetical full-row scan would
        # materialize at least 2 rows — we'd see them in the log.
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(make_workflow())
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(make_workflow())

        captured: list[str] = []

        def _on_execute(
            _conn: object,
            _cursor: object,
            statement: str,
            _params: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            captured.append(statement.strip())

        sync_engine = app_engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _on_execute)
        try:
            async with session_factory() as session:
                count = await SqliteWorkflowRepository(session).count()
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        assert count == 2
        # Workflow SELECTs touched during count() must all be
        # ``count(*)`` shapes — never a full ``SELECT id FROM workflows``
        # row stream that the Repository would then ``len()``.
        workflow_selects = [s for s in captured if "FROM workflows" in s]
        assert workflow_selects, "count() must issue at least one SELECT against workflows"
        for stmt in workflow_selects:
            assert "count(" in stmt.lower(), (
                f"[FAIL] count() emitted a non-COUNT SELECT: {stmt!r}\n"
                f"Next: ensure count() uses select(func.count()).select_from(WorkflowRow) "
                f"per detailed-design.md §確定 D 補強."
            )


# ---------------------------------------------------------------------------
# §確定 D: Repository never enforces singleton invariants
# ---------------------------------------------------------------------------
class TestRepositoryDoesNotEnforceSingleton:
    """TC-IT-WFR-019: Repository accepts multiple Workflow saves."""

    async def test_two_workflows_saved_without_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-019: 2 distinct Workflows save successfully; ``count()`` reports 2.

        Singleton enforcement (e.g. "only one preset Workflow per
        empire") is the application service's job; the Repository
        itself reports facts via ``count()`` and never raises just
        because the cardinality grew above 1.
        """
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(make_workflow())
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(make_workflow())

        async with session_factory() as session:
            count = await SqliteWorkflowRepository(session).count()
        assert count == 2


# ---------------------------------------------------------------------------
# REQ-WFR-002: save inserts into all 3 tables (TC-IT-WFR-008)
# ---------------------------------------------------------------------------
class TestSaveInsertsAllThreeTables:
    """TC-IT-WFR-008: ``save`` writes the 3 Workflow tables.

    ``workflows`` + ``workflow_stages`` + ``workflow_transitions`` all
    receive rows in a single ``save`` call.
    """

    async def test_save_populates_three_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-008: 3 stages + 2 transitions land in their respective side tables.

        We deliberately avoid V-model payload here because that has
        EXTERNAL_REVIEW stages and would conflate this test with the
        notify_channels masking concern (covered in test_masking).
        """
        stage_a = make_stage(name="A")
        stage_b = make_stage(name="B")
        stage_c = make_stage(name="C")
        transition_ab = make_transition(from_stage_id=stage_a.id, to_stage_id=stage_b.id)
        transition_bc = make_transition(from_stage_id=stage_b.id, to_stage_id=stage_c.id)
        workflow = make_workflow(
            stages=[stage_a, stage_b, stage_c],
            transitions=[transition_ab, transition_bc],
            entry_stage_id=stage_a.id,
        )
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            workflow_rows = (
                await session.execute(select(WorkflowRow).where(WorkflowRow.id == workflow.id))
            ).all()
            stage_rows = (
                await session.execute(
                    select(WorkflowStageRow).where(WorkflowStageRow.workflow_id == workflow.id)
                )
            ).all()
            transition_rows = (
                await session.execute(
                    select(WorkflowTransitionRow).where(
                        WorkflowTransitionRow.workflow_id == workflow.id
                    )
                )
            ).all()

        assert len(workflow_rows) == 1
        assert len(stage_rows) == 3
        assert len(transition_rows) == 2
