"""Workflow Repository: save() — roles_csv determinism + round-trip + Tx boundary.

TC-IT-WFR-011 / 012 / 015 / 016 — the §確定 G "sorted CSV"
determinism, the §確定 C round-trip structural equality, and the
§確定 B Tx-boundary responsibility separation.

Split out of ``test_save_semantics.py`` per Norman 500-line rule.
The companion file
:mod:`...test_workflow_repository.test_save_delete_then_insert` covers
the delete-then-insert + 5-step DML order + cross-workflow isolation
smoke.

Per ``docs/features/workflow-repository/test-design.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from bakufu.domain.value_objects import Role
from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
    SqliteWorkflowRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflow_stages import (
    WorkflowStageRow,
)
from sqlalchemy import select, text

from tests.factories.workflow import (
    make_stage,
    make_transition,
    make_workflow,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# §確定 G: roles_csv sorted CSV determinism (TC-IT-WFR-011 / 012)
# ---------------------------------------------------------------------------
class TestRolesCsvSortedDeterminism:
    """TC-IT-WFR-011 / 012: ``roles_csv`` is sorted; equal frozensets → equal CSV.

    §確定 G freezes "sorted CSV" specifically because Python
    ``frozenset`` iteration order is implementation-defined. Without
    sorting, two save() calls of the same Workflow could produce
    different ``roles_csv`` byte sequences and trigger spurious
    delete-then-insert diff noise (the row would *look* changed even
    though the domain value is identical).

    We exercise:

    1. **Round-trip restore** — frozenset → CSV → frozenset preserves
       the role set (no roles dropped, no extras introduced).
    2. **Byte-determinism** — two Workflows whose Stage's
       ``required_role`` was constructed with **different insertion
       order** (e.g. ``frozenset({DEVELOPER, REVIEWER})`` vs.
       ``frozenset({REVIEWER, DEVELOPER})``) produce byte-identical
       ``roles_csv`` rows in DB.
    """

    async def test_required_role_round_trips_via_roles_csv(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-011: ``frozenset[Role]`` survives the CSV round-trip."""
        roles = frozenset({Role.DEVELOPER, Role.TESTER, Role.REVIEWER})
        stage = make_stage(required_role=roles)
        workflow = make_workflow(stages=[stage], entry_stage_id=stage.id)

        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            restored = await SqliteWorkflowRepository(session).find_by_id(workflow.id)

        assert restored is not None
        assert len(restored.stages) == 1
        assert restored.stages[0].required_role == roles
        assert isinstance(restored.stages[0].required_role, frozenset)

    async def test_same_role_set_yields_byte_identical_csv(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-012: Same ``frozenset`` produces byte-identical ``roles_csv``.

        Build two stages whose ``required_role`` was constructed from
        differently-ordered iterables but yield the same ``frozenset``.
        The persisted ``roles_csv`` strings must match byte-for-byte —
        otherwise delete-then-insert would re-write the same row over
        and over (diff noise) on every save.
        """
        roles_forward = frozenset({Role.DEVELOPER, Role.REVIEWER, Role.TESTER})
        roles_reverse = frozenset([Role.TESTER, Role.REVIEWER, Role.DEVELOPER])
        # frozenset equality is set equality — sanity check our setup.
        assert roles_forward == roles_reverse

        stage_a = make_stage(required_role=roles_forward)
        stage_b = make_stage(required_role=roles_reverse)
        workflow_a = make_workflow(stages=[stage_a], entry_stage_id=stage_a.id)
        workflow_b = make_workflow(stages=[stage_b], entry_stage_id=stage_b.id)

        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow_a)
            await SqliteWorkflowRepository(session).save(workflow_b)

        # Raw-SQL fetch of the two ``roles_csv`` cells; SQLAlchemy
        # would hide the literal byte content behind type decorators
        # (it doesn't here, but the explicit raw form documents the
        # intent for follow-up Repository PRs).
        async with session_factory() as session:
            stmt = text(
                "SELECT roles_csv FROM workflow_stages "
                "WHERE workflow_id IN (:wf_a, :wf_b) ORDER BY workflow_id"
            )
            result = await session.execute(
                stmt,
                {"wf_a": workflow_a.id.hex, "wf_b": workflow_b.id.hex},
            )
            csv_values = sorted(row[0] for row in result)

        assert len(csv_values) == 2
        assert csv_values[0] == csv_values[1], (
            f"[FAIL] sorted-CSV determinism violated: {csv_values[0]!r} != {csv_values[1]!r}.\n"
            f"Next: verify _to_row uses ``sorted(role.value for role in stage.required_role)`` "
            f"per detailed-design.md §確定 G."
        )


# ---------------------------------------------------------------------------
# §確定 C: round-trip structural equality (TC-IT-WFR-015)
# ---------------------------------------------------------------------------
class TestRoundTripStructuralEquality:
    """TC-IT-WFR-015: save → find_by_id round-trip preserves Workflow identity.

    The Workflow Repository inherits empire-repository's ``ORDER BY
    stage_id`` / ``ORDER BY transition_id`` contract from PR #1
    (BUG-EMR-001 lesson applied at design time, not after the fact).
    We sort the *expected* lists by the same key the Repository
    sorted on so list-order equality is the contract.

    We deliberately avoid ``EXTERNAL_REVIEW`` stages in this round-trip
    test because §確定 H §不可逆性 makes ``find_by_id`` raise on those;
    the irreversibility is verified separately in
    :mod:`...test_masking`.
    """

    async def test_multi_stage_workflow_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-015: 3 stages + 2 transitions round-trip with list-order equality."""
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
            restored = await SqliteWorkflowRepository(session).find_by_id(workflow.id)

        assert restored is not None
        assert restored.id == workflow.id
        assert restored.name == workflow.name
        assert restored.entry_stage_id == workflow.entry_stage_id
        # ORDER BY stage_id / transition_id 物理保証: restored side-table
        # lists are deterministic, so list-order equality is the
        # contract.
        assert restored.stages == sorted(workflow.stages, key=lambda s: s.id)
        assert restored.transitions == sorted(workflow.transitions, key=lambda t: t.id)

    async def test_single_stage_workflow_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-015: a single-stage Workflow (entry == sink) round-trips with full ``==``."""
        workflow = make_workflow()  # default = 1 WORK stage, 0 transitions
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            restored = await SqliteWorkflowRepository(session).find_by_id(workflow.id)
        assert restored is not None
        # No list-order ambiguity — full ``==`` is fine.
        assert restored == workflow


# ---------------------------------------------------------------------------
# §確定 B: Tx boundary responsibility separation (TC-IT-WFR-016)
# ---------------------------------------------------------------------------
class TestTxBoundaryRespectedByRepository:
    """TC-IT-WFR-016: Repository never calls commit / rollback (§確定 B)."""

    async def test_commit_path_persists_via_outer_block(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-016 (commit): outer ``async with session.begin()`` commits the save."""
        workflow = make_workflow()
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            fetched = await SqliteWorkflowRepository(session).find_by_id(workflow.id)
        assert fetched is not None

    async def test_rollback_path_drops_save_atomically(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-016 (rollback): an exception inside ``begin()`` rolls back the save.

        The Workflow row + its (potentially non-empty) stages /
        transitions all participate in the same caller-managed
        transaction. A single uncaught exception inside the ``begin()``
        block must purge **all** of them — Repository did not commit
        anything itself.
        """

        class _BoomError(Exception):
            """Synthetic exception used to drive the rollback path."""

        # Use a 3-stage Workflow so rollback has stages + transitions
        # to demonstrably purge alongside the workflow row.
        stage_a = make_stage(name="A")
        stage_b = make_stage(name="B")
        transition_ab = make_transition(from_stage_id=stage_a.id, to_stage_id=stage_b.id)
        workflow = make_workflow(
            stages=[stage_a, stage_b],
            transitions=[transition_ab],
            entry_stage_id=stage_a.id,
        )

        with pytest.raises(_BoomError):
            async with session_factory() as session, session.begin():
                await SqliteWorkflowRepository(session).save(workflow)
                raise _BoomError

        async with session_factory() as session:
            fetched = await SqliteWorkflowRepository(session).find_by_id(workflow.id)
        # Rollback must have been atomic — no row survives.
        assert fetched is None

        # Side tables also empty — the §確定 B contract is that the
        # 5-step sequence is **one** logical operation under the
        # caller's UoW, not five separate persistences.
        async with session_factory() as session:
            stage_count = (
                await session.execute(
                    select(WorkflowStageRow).where(WorkflowStageRow.workflow_id == workflow.id)
                )
            ).all()
        assert stage_count == []

    async def test_repository_does_not_commit_implicitly(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-016 補強: ``save`` outside ``begin()`` does not auto-commit.

        If the Repository contained a stray ``await session.commit()``,
        a save without ``async with session.begin()`` would still
        persist — and a subsequent fresh-session read would see it.
        SQLAlchemy AsyncSession default is autobegin=True with a
        transactional SELECT, so we open a session and call save
        directly without an outer ``begin()`` block, then expire +
        re-read in a fresh session. The Repository's contract is that
        the row does **not** persist, because no commit fired.
        """
        workflow = make_workflow()
        async with session_factory() as session:
            await SqliteWorkflowRepository(session).save(workflow)
            # Intentionally exit without ``commit()`` — AsyncSession's
            # ``__aexit__`` will rollback any in-flight transaction.

        async with session_factory() as session:
            fetched = await SqliteWorkflowRepository(session).find_by_id(workflow.id)
        # The Repository must NOT have committed implicitly.
        assert fetched is None, (
            "[FAIL] Workflow row persisted without an outer commit.\n"
            "Next: SqliteWorkflowRepository.save() must not call "
            "session.commit() per §確定 B Tx 境界責務分離."
        )
