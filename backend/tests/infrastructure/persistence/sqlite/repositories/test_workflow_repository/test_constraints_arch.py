"""Workflow Repository: DB constraints + arch-test partial-mask template.

TC-IT-WFR-017 / 018 / 023 — FK CASCADE, UNIQUE pair enforcement, and
the **partial-mask** CI three-layer-defense template the Workflow PR
introduces (empire-repo froze the *no-mask* template; this PR freezes
the *partial-mask* template — exactly one masked column on a table,
every other column un-masked).

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
from bakufu.infrastructure.persistence.sqlite.tables.workflow_transitions import (
    WorkflowTransitionRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflows import WorkflowRow
from sqlalchemy import delete, select, text

from tests.factories.workflow import make_stage, make_transition, make_workflow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-IT-WFR-017: FK CASCADE
# ---------------------------------------------------------------------------
class TestForeignKeyCascade:
    """TC-IT-WFR-017: ``DELETE FROM workflows`` cascades to side tables."""

    async def test_delete_workflow_cascades_to_side_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-017: FK ON DELETE CASCADE empties workflow_stages / workflow_transitions."""
        stage_a = make_stage(name="A")
        stage_b = make_stage(name="B")
        transition_ab = make_transition(from_stage_id=stage_a.id, to_stage_id=stage_b.id)
        workflow = make_workflow(
            stages=[stage_a, stage_b],
            transitions=[transition_ab],
            entry_stage_id=stage_a.id,
        )
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session, session.begin():
            await session.execute(delete(WorkflowRow).where(WorkflowRow.id == workflow.id))

        async with session_factory() as session:
            stage_rows = list(
                (
                    await session.execute(
                        select(WorkflowStageRow).where(WorkflowStageRow.workflow_id == workflow.id)
                    )
                ).scalars()
            )
            transition_rows = list(
                (
                    await session.execute(
                        select(WorkflowTransitionRow).where(
                            WorkflowTransitionRow.workflow_id == workflow.id
                        )
                    )
                ).scalars()
            )
        assert stage_rows == []
        assert transition_rows == []


# ---------------------------------------------------------------------------
# TC-IT-WFR-018: UNIQUE constraints on (workflow_id, stage_id) and
#                                       (workflow_id, transition_id)
# ---------------------------------------------------------------------------
class TestUniqueConstraintViolation:
    """TC-IT-WFR-018: duplicate (workflow_id, stage_id) / (..., transition_id) raises."""

    async def test_duplicate_stage_pair_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-018a: same (workflow_id, stage_id) inserted twice → DB rejects.

        The Repository's delete-then-insert flow always wipes the side
        tables before INSERT, so the constraint is never tripped
        through the Repository API. To exercise the **DB-level**
        UNIQUE contract we issue raw SQL that bypasses the Repository.
        """
        from sqlalchemy.exc import IntegrityError

        workflow = make_workflow()
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        stage_id = uuid4()
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO workflow_stages "
                    "(workflow_id, stage_id, name, kind, roles_csv, "
                    "deliverable_template, completion_policy_json, "
                    "notify_channels_json) "
                    "VALUES (:workflow_id, :stage_id, :name, :kind, :roles_csv, "
                    ":deliverable, :policy, :channels)"
                ),
                {
                    "workflow_id": workflow.id.hex,
                    "stage_id": stage_id.hex,
                    "name": "first",
                    "kind": "WORK",
                    "roles_csv": "DEVELOPER",
                    "deliverable": "",
                    "policy": '{"kind": "approved_by_reviewer", "description": ""}',
                    "channels": "[]",
                },
            )

        with pytest.raises(IntegrityError):
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        "INSERT INTO workflow_stages "
                        "(workflow_id, stage_id, name, kind, roles_csv, "
                        "deliverable_template, completion_policy_json, "
                        "notify_channels_json) "
                        "VALUES (:workflow_id, :stage_id, :name, :kind, :roles_csv, "
                        ":deliverable, :policy, :channels)"
                    ),
                    {
                        "workflow_id": workflow.id.hex,
                        "stage_id": stage_id.hex,
                        "name": "duplicate",
                        "kind": "WORK",
                        "roles_csv": "DEVELOPER",
                        "deliverable": "",
                        "policy": '{"kind": "approved_by_reviewer", "description": ""}',
                        "channels": "[]",
                    },
                )

    async def test_duplicate_transition_pair_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-018b: same (workflow_id, transition_id) inserted twice → DB rejects."""
        from sqlalchemy.exc import IntegrityError

        # A 2-stage Workflow gives us legitimate from_stage_id / to_stage_id
        # values for the raw INSERT that follows.
        stage_a = make_stage(name="A")
        stage_b = make_stage(name="B")
        transition_ab = make_transition(from_stage_id=stage_a.id, to_stage_id=stage_b.id)
        workflow = make_workflow(
            stages=[stage_a, stage_b],
            transitions=[transition_ab],
            entry_stage_id=stage_a.id,
        )
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        transition_id = uuid4()
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO workflow_transitions "
                    "(workflow_id, transition_id, from_stage_id, to_stage_id, "
                    "condition, label) "
                    "VALUES (:workflow_id, :transition_id, :from_id, :to_id, "
                    ":cond, :label)"
                ),
                {
                    "workflow_id": workflow.id.hex,
                    "transition_id": transition_id.hex,
                    "from_id": stage_a.id.hex,
                    "to_id": stage_b.id.hex,
                    "cond": "APPROVED",
                    "label": "first",
                },
            )

        with pytest.raises(IntegrityError):
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        "INSERT INTO workflow_transitions "
                        "(workflow_id, transition_id, from_stage_id, to_stage_id, "
                        "condition, label) "
                        "VALUES (:workflow_id, :transition_id, :from_id, :to_id, "
                        ":cond, :label)"
                    ),
                    {
                        "workflow_id": workflow.id.hex,
                        "transition_id": transition_id.hex,
                        "from_id": stage_a.id.hex,
                        "to_id": stage_b.id.hex,
                        "cond": "APPROVED",
                        "label": "duplicate",
                    },
                )


# ---------------------------------------------------------------------------
# TC-IT-WFR-023: Layer 2 arch-test partial-mask template structure
# ---------------------------------------------------------------------------
class TestPartialMaskTemplateStructure:
    """TC-IT-WFR-023: arch-test exposes the partial-mask parametrize structure.

    The Workflow PR introduces the **partial-mask** pattern alongside
    empire-repository's no-mask pattern: ``workflow_stages`` carries
    exactly one masked column (``notify_channels_json``) and zero on
    every other column. The arch-test parametrizes
    ``_PARTIAL_MASK_TABLES`` to assert this — a future PR that swaps
    another column to a Masked* type without updating §逆引き表 first
    must trip the arch-test.

    Future Repository PRs add their own "partial-mask" rows for their
    Aggregate's tables; the structural shape lets them extend without
    rewriting the harness.
    """

    async def test_arch_test_module_imports_partial_mask_table_list(self) -> None:
        """TC-IT-WFR-023: ``_PARTIAL_MASK_TABLES`` lists ``workflow_stages``."""
        from tests.architecture.test_masking_columns import (
            _NO_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
            _PARTIAL_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
        )

        # workflow_stages is the partial-mask table.
        partial_mask_table_names = {tbl for tbl, _ in _PARTIAL_MASK_TABLES}
        assert "workflow_stages" in partial_mask_table_names, (
            "[FAIL] workflow_stages must be registered in _PARTIAL_MASK_TABLES.\n"
            "Next: add ('workflow_stages', 'notify_channels_json') per "
            "detailed-design.md §確定 H."
        )
        # The allowed column on workflow_stages is exactly notify_channels_json.
        allowed_columns = [col for tbl, col in _PARTIAL_MASK_TABLES if tbl == "workflow_stages"]
        assert allowed_columns == ["notify_channels_json"], (
            f"[FAIL] workflow_stages partial-mask declared {allowed_columns!r}, "
            f"expected ['notify_channels_json'].\n"
            f"Next: §逆引き表 freezes notify_channels_json as the sole masked column."
        )

        # workflows / workflow_transitions live in the no-mask list.
        assert "workflows" in _NO_MASK_TABLES, (
            "[FAIL] workflows must be registered in _NO_MASK_TABLES."
        )
        assert "workflow_transitions" in _NO_MASK_TABLES, (
            "[FAIL] workflow_transitions must be registered in _NO_MASK_TABLES."
        )
