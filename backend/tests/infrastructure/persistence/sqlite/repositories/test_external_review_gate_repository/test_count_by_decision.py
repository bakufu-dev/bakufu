"""ExternalReviewGate Repository: count_by_decision SQL guarantee.

TC-UT-ERGR-008 — §確定 R1-D count_by_decision.

Verifies:
* count_by_decision(PENDING) returns correct count.
* SQL log contains WHERE decision = filter (not a full-table-scan aggregate).
* All decision values (PENDING / APPROVED / REJECTED / CANCELLED) isolated.

Per ``docs/features/external-review-gate-repository/test-design.md`` TC-UT-ERGR-008.
Issue #36 — M2 0008.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from bakufu.domain.value_objects import ReviewDecision
from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (
    SqliteExternalReviewGateRepository,
)
from sqlalchemy import event

from tests.factories.external_review_gate import (
    make_approved_gate,
    make_gate,
    make_rejected_gate,
)
from tests.infrastructure.persistence.sqlite.repositories.test_external_review_gate_repository.conftest import (  # noqa: E501
    seed_gate_context,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-ERGR-008: count_by_decision SQL COUNT(*) WHERE decision =
# ---------------------------------------------------------------------------
class TestCountByDecision:
    """TC-UT-ERGR-008: count_by_decision issues COUNT(*) WHERE decision = :decision."""

    async def test_count_by_decision_pending(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-008: count_by_decision(PENDING) = 2 with 2 PENDING gates saved."""
        task_id, stage_id, reviewer_id = seeded_gate_context

        gate1 = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)
        gate2 = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)
        gate_approved = make_approved_gate(
            task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id
        )
        gate_rejected = make_rejected_gate(
            task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id
        )

        async with session_factory() as session, session.begin():
            repo = SqliteExternalReviewGateRepository(session)
            await repo.save(gate1)
            await repo.save(gate2)
            await repo.save(gate_approved)
            await repo.save(gate_rejected)

        async with session_factory() as session:
            result = await SqliteExternalReviewGateRepository(session).count_by_decision(
                ReviewDecision.PENDING
            )

        assert result == 2, f"[FAIL] Expected count 2 for PENDING, got {result}"

    async def test_count_by_decision_all_values_isolated(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-008: APPROVED=1 / REJECTED=1 / CANCELLED=0 correctly isolated."""
        task_id, stage_id, reviewer_id = seeded_gate_context

        gate_pending = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)
        gate_approved = make_approved_gate(
            task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id
        )
        gate_rejected = make_rejected_gate(
            task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id
        )

        async with session_factory() as session, session.begin():
            repo = SqliteExternalReviewGateRepository(session)
            await repo.save(gate_pending)
            await repo.save(gate_approved)
            await repo.save(gate_rejected)

        async with session_factory() as session:
            repo = SqliteExternalReviewGateRepository(session)
            count_pending = await repo.count_by_decision(ReviewDecision.PENDING)
            count_approved = await repo.count_by_decision(ReviewDecision.APPROVED)
            count_rejected = await repo.count_by_decision(ReviewDecision.REJECTED)
            count_cancelled = await repo.count_by_decision(ReviewDecision.CANCELLED)

        assert count_pending == 1, f"[FAIL] PENDING={count_pending}, expected 1"
        assert count_approved == 1, f"[FAIL] APPROVED={count_approved}, expected 1"
        assert count_rejected == 1, f"[FAIL] REJECTED={count_rejected}, expected 1"
        assert count_cancelled == 0, f"[FAIL] CANCELLED={count_cancelled}, expected 0"

    async def test_count_by_decision_sql_contains_where_decision(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-008: SQL log confirms COUNT(*) WHERE decision = filter."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        gate = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        sql_log: list[str] = []

        async with session_factory() as session:
            sync_engine = session.get_bind()
            if hasattr(sync_engine, "sync_engine"):
                sync_engine = sync_engine.sync_engine  # type: ignore[union-attr]

            @event.listens_for(sync_engine, "before_cursor_execute")
            def _capture(conn, cursor, statement, params, context, executemany):  # type: ignore[no-untyped-def]
                sql_log.append(statement.upper())

            await SqliteExternalReviewGateRepository(session).count_by_decision(
                ReviewDecision.PENDING
            )

        combined = " ".join(sql_log)
        assert "COUNT" in combined, f"[FAIL] COUNT missing from SQL.\nSQL: {sql_log}"
        assert "WHERE" in combined, f"[FAIL] WHERE clause missing from SQL.\nSQL: {sql_log}"
        assert "DECISION" in combined, f"[FAIL] decision filter missing from SQL.\nSQL: {sql_log}"

    async def test_count_by_decision_cross_context_isolation(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-ERGR-008: count_by_decision aggregates across all tasks (not task-scoped)."""
        ctx1 = await seed_gate_context(session_factory)
        ctx2 = await seed_gate_context(session_factory)

        gate1 = make_gate(task_id=ctx1[0], stage_id=ctx1[1], reviewer_id=ctx1[2])
        gate2 = make_gate(task_id=ctx2[0], stage_id=ctx2[1], reviewer_id=ctx2[2])

        async with session_factory() as session, session.begin():
            repo = SqliteExternalReviewGateRepository(session)
            await repo.save(gate1)
            await repo.save(gate2)

        async with session_factory() as session:
            total_pending = await SqliteExternalReviewGateRepository(session).count_by_decision(
                ReviewDecision.PENDING
            )

        assert total_pending == 2, (
            f"[FAIL] count_by_decision should aggregate across all tasks, got {total_pending}"
        )
