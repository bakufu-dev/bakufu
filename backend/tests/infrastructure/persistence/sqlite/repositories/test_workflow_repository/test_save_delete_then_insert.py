"""Workflow Repository: save() — delete-then-insert + SQL order + isolation.

TC-IT-WFR-009 / 010 — the §確定 B contract that backs the ``save()``
flow's wholesale row replacement and the 5-step DML sequence, plus
the isolation-between-Workflows smoke (``DELETE`` is scoped to a
single ``workflow_id``).

Split out of ``test_save_semantics.py`` per Norman 500-line rule
(file would land at 502 lines after BUG-WFR-001 fix). The two
companion files cover the round-trip + Tx-boundary contracts:

* :mod:`...test_workflow_repository.test_save_round_trip` —
  ``roles_csv`` determinism + structural equality + Tx commit /
  rollback.

Per ``docs/features/workflow-repository/test-design.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
    SqliteWorkflowRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflow_stages import (
    WorkflowStageRow,
)
from sqlalchemy import event, select

from tests.factories.workflow import (
    build_v_model_payload,
    make_stage,
    make_transition,
    make_workflow,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# §確定 B: delete-then-insert replacement semantics (TC-IT-WFR-009)
# ---------------------------------------------------------------------------
class TestSaveDeleteThenInsert:
    """TC-IT-WFR-009: ``save`` replaces side-table rows wholesale (§確定 B)."""

    async def test_save_replaces_stage_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-009: 3 stages → 1 stage is reflected as 1 row in workflow_stages.

        We construct a fresh single-stage Workflow with the **same
        workflow_id** and re-save. The §確定 B contract says the side
        tables must end up reflecting only the new state; old stages
        must not survive as residue.
        """
        stage_a = make_stage(name="A")
        stage_b = make_stage(name="B")
        stage_c = make_stage(name="C")
        transition_ab = make_transition(from_stage_id=stage_a.id, to_stage_id=stage_b.id)
        transition_bc = make_transition(from_stage_id=stage_b.id, to_stage_id=stage_c.id)
        original = make_workflow(
            stages=[stage_a, stage_b, stage_c],
            transitions=[transition_ab, transition_bc],
            entry_stage_id=stage_a.id,
        )
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(original)

        # Build a new Workflow with the same id but only 1 stage.
        replacement_stage = make_stage(name="残ったステージ")
        replacement = make_workflow(
            workflow_id=original.id,
            name=original.name,
            stages=[replacement_stage],
            transitions=[],
            entry_stage_id=replacement_stage.id,
        )
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(replacement)

        # Side tables must show the new state, not the merged old + new.
        async with session_factory() as session:
            stage_rows = list(
                (
                    await session.execute(
                        select(WorkflowStageRow).where(WorkflowStageRow.workflow_id == original.id)
                    )
                ).scalars()
            )
        assert len(stage_rows) == 1
        assert stage_rows[0].name == "残ったステージ"


# ---------------------------------------------------------------------------
# §確定 B: 5-step SQL order (TC-IT-WFR-010)
# ---------------------------------------------------------------------------
class TestSaveSqlOrder:
    """TC-IT-WFR-010: ``save`` issues SQL in the §確定 B 5-step order.

    We attach a ``before_cursor_execute`` listener on the **sync**
    engine so we observe the actual SQL strings the dialect emits. The
    listener appends each statement to a captured list; we then assert
    the prefix sequence matches the design's 5 steps. The dispatcher /
    ORM may issue extra SAVEPOINT / BEGIN statements which we filter
    out — the contract is on the *DML* prefix.

    Same harness as empire-repository TC-IT-EMR-011; the next 5
    Repository PRs should re-use this template.
    """

    async def test_save_emits_upsert_then_delete_insert_pairs(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-010: 5-step DML order matches §確定 B.

        workflows UPSERT → workflow_stages DEL+INS → workflow_transitions DEL+INS.
        """
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
            # V-model payload exercises 13 stages + 15 transitions —
            # the busiest possible ``save()`` shape and the right one
            # for SQL-order observation.
            from bakufu.domain.workflow import Workflow

            workflow = Workflow.from_dict(build_v_model_payload())
            async with session_factory() as session, session.begin():
                await SqliteWorkflowRepository(session).save(workflow)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        # Filter to the 5 DML statements we care about (BEGIN /
        # SAVEPOINT / RELEASE / COMMIT noise removed).
        dml = [
            s
            for s in captured
            if any(
                s.upper().startswith(prefix)
                for prefix in (
                    "INSERT INTO WORKFLOWS",
                    "DELETE FROM WORKFLOW_",
                    "INSERT INTO WORKFLOW_",
                )
            )
        ]
        # Step 1 (UPSERT workflows) → Step 2 (DELETE workflow_stages) →
        # Step 3 (INSERT workflow_stages) → Step 4 (DELETE
        # workflow_transitions) → Step 5 (INSERT workflow_transitions).
        assert len(dml) >= 5, (
            f"[FAIL] save emitted only {len(dml)} DML statements; expected ≥5.\n"
            f"Next: verify save() executes the §確定 B 5-step sequence. "
            f"Captured DML: {dml}"
        )
        assert dml[0].upper().startswith("INSERT INTO WORKFLOWS")
        assert dml[1].upper().startswith("DELETE FROM WORKFLOW_STAGES")
        assert dml[2].upper().startswith("INSERT INTO WORKFLOW_STAGES")
        assert dml[3].upper().startswith("DELETE FROM WORKFLOW_TRANSITIONS")
        assert dml[4].upper().startswith("INSERT INTO WORKFLOW_TRANSITIONS")


# ---------------------------------------------------------------------------
# Smoke test: an unknown workflow_id never collides with an existing row
# ---------------------------------------------------------------------------
class TestSaveDistinctWorkflowsAreIndependent:
    """Side-effect isolation between Workflows."""

    async def test_save_one_does_not_disturb_another(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Saving Workflow B must not delete Workflow A's stages.

        The ``DELETE WHERE workflow_id = ?`` step in §確定 B is
        scoped to the workflow_id under save; a poorly-written
        Repository that issued an un-scoped DELETE would corrupt every
        other Workflow in the DB. We assert the scoping with a
        before / after snapshot.
        """
        workflow_a = make_workflow()
        workflow_b = make_workflow()
        # Distinct ids — sanity.
        assert workflow_a.id != workflow_b.id

        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow_a)

        # Save B → A must remain untouched.
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow_b)

        async with session_factory() as session:
            a_rows = list(
                (
                    await session.execute(
                        select(WorkflowStageRow).where(
                            WorkflowStageRow.workflow_id == workflow_a.id
                        )
                    )
                ).scalars()
            )
            b_rows = list(
                (
                    await session.execute(
                        select(WorkflowStageRow).where(
                            WorkflowStageRow.workflow_id == workflow_b.id
                        )
                    )
                ).scalars()
            )

        assert len(a_rows) == 1
        assert len(b_rows) == 1

        # Sanity: the two Workflows did not share stage rows.
        a_stage_ids = {row.stage_id for row in a_rows}
        b_stage_ids = {row.stage_id for row in b_rows}
        assert a_stage_ids.isdisjoint(b_stage_ids)

    async def test_unknown_workflow_id_returns_none_after_other_saves(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """find_by_id of an unknown id still returns None even when DB is non-empty."""
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(make_workflow())

        unknown_id = uuid4()
        async with session_factory() as session:
            fetched = await SqliteWorkflowRepository(session).find_by_id(unknown_id)
        assert fetched is None
