"""ExternalReviewGate Repository: find_pending_by_reviewer / find_by_task_id.

TC-UT-ERGR-006/006b/006c/006d/007/007b/007c — §確定 R1-D / §確定 R1-H ORDER BY.

Tests ORDER BY determinism (BUG-EMR-001 準拠) for both query methods:
* find_pending_by_reviewer: created_at DESC, id DESC tiebreaker
* find_by_task_id: created_at ASC, id ASC (chronological review history)

Per ``docs/features/external-review-gate-repository/test-design.md``
TC-UT-ERGR-006〜007c.
Issue #36 — M2 0008.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
# TC-UT-ERGR-006: find_pending_by_reviewer returns PENDING only
# ---------------------------------------------------------------------------
class TestFindPendingByReviewer:
    """TC-UT-ERGR-006: find_pending_by_reviewer returns only PENDING Gates."""

    async def test_returns_only_pending_gates(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-006: PENDING Gates for reviewer returned; APPROVED excluded."""
        task_id, stage_id, reviewer_id = seeded_gate_context

        gate_pending1 = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)
        gate_pending2 = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)
        gate_approved = make_approved_gate(
            task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id
        )

        async with session_factory() as session, session.begin():
            repo = SqliteExternalReviewGateRepository(session)
            await repo.save(gate_pending1)
            await repo.save(gate_pending2)
            await repo.save(gate_approved)

        async with session_factory() as session:
            results = await SqliteExternalReviewGateRepository(session).find_pending_by_reviewer(
                reviewer_id
            )

        assert len(results) == 2, f"[FAIL] Expected 2 PENDING, got {len(results)}"
        for g in results:
            assert g.decision == ReviewDecision.PENDING, "[FAIL] Non-PENDING gate in results"
        ids = {g.id for g in results}
        assert gate_approved.id not in ids, "[FAIL] APPROVED gate appeared in PENDING results"


# ---------------------------------------------------------------------------
# TC-UT-ERGR-006b: find_pending_by_reviewer returns [] when no PENDING gates
# ---------------------------------------------------------------------------
class TestFindPendingByReviewerEmpty:
    """TC-UT-ERGR-006b: Returns [] (not None) when no PENDING gates exist."""

    async def test_returns_empty_list_when_no_pending(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-006b: No PENDING gates → [] not None."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        approved = make_approved_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)
        rejected = make_rejected_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)

        async with session_factory() as session, session.begin():
            repo = SqliteExternalReviewGateRepository(session)
            await repo.save(approved)
            await repo.save(rejected)

        async with session_factory() as session:
            results = await SqliteExternalReviewGateRepository(session).find_pending_by_reviewer(
                reviewer_id
            )

        assert results == [], f"[FAIL] Expected [] but got {results!r}"


# ---------------------------------------------------------------------------
# TC-UT-ERGR-006c: SQL ログに ORDER BY created_at + reviewer_id filter 含まれる
# ---------------------------------------------------------------------------
class TestFindPendingByReviewerSqlLog:
    """TC-UT-ERGR-006c: SQL log confirms WHERE reviewer_id + decision + ORDER BY."""

    async def test_sql_contains_reviewer_and_decision_filters(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-006c: Raw SQL includes reviewer_id filter + ORDER BY created_at."""
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
            def _capture(conn, cursor, statement: str, params, context, executemany):  # type: ignore[no-untyped-def]
                sql_log.append(statement.upper())

            await SqliteExternalReviewGateRepository(session).find_pending_by_reviewer(reviewer_id)

        combined = " ".join(sql_log)
        assert "ORDER BY" in combined, f"[FAIL] ORDER BY missing.\nSQL: {sql_log}"
        assert "CREATED_AT" in combined, f"[FAIL] created_at ORDER BY missing.\nSQL: {sql_log}"


# ---------------------------------------------------------------------------
# TC-UT-ERGR-006d: id DESC tiebreaker (BUG-EMR-001 準拠)
# ---------------------------------------------------------------------------
class TestFindPendingByReviewerTiebreaker:
    """TC-UT-ERGR-006d: id DESC tiebreaker for same-timestamp PENDING gates."""

    async def test_same_timestamp_ordered_by_id_desc(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-006d: Gates with identical created_at ordered by id DESC."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        fixed_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

        gate_a = make_gate(
            task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id, created_at=fixed_time
        )
        gate_b = make_gate(
            task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id, created_at=fixed_time
        )
        gate_c = make_gate(
            task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id, created_at=fixed_time
        )

        async with session_factory() as session, session.begin():
            repo = SqliteExternalReviewGateRepository(session)
            for g in [gate_a, gate_b, gate_c]:
                await repo.save(g)

        async with session_factory() as session:
            results = await SqliteExternalReviewGateRepository(session).find_pending_by_reviewer(
                reviewer_id
            )

        assert len(results) == 3
        result_ids = [g.id for g in results]
        expected_ids = sorted([gate_a.id, gate_b.id, gate_c.id], key=lambda u: u.hex, reverse=True)
        assert result_ids == expected_ids, (
            f"[FAIL] id DESC tiebreaker not applied.\nExpected: {expected_ids}\nGot: {result_ids}"
        )


# ---------------------------------------------------------------------------
# TC-UT-ERGR-007: find_by_task_id returns all Gates for a task
# ---------------------------------------------------------------------------
class TestFindByTaskId:
    """TC-UT-ERGR-007: find_by_task_id returns all Gates for the given task."""

    async def test_returns_all_gates_for_task(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-007: Both PENDING + REJECTED gates for same task returned."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        gate_pending = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)
        gate_rejected = make_rejected_gate(
            task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id
        )

        async with session_factory() as session, session.begin():
            repo = SqliteExternalReviewGateRepository(session)
            await repo.save(gate_pending)
            await repo.save(gate_rejected)

        async with session_factory() as session:
            results = await SqliteExternalReviewGateRepository(session).find_by_task_id(task_id)

        assert len(results) == 2
        ids = {g.id for g in results}
        assert gate_pending.id in ids
        assert gate_rejected.id in ids


# ---------------------------------------------------------------------------
# TC-UT-ERGR-007b: created_at ASC ordering for multi-round review history
# ---------------------------------------------------------------------------
class TestFindByTaskIdChronologicalOrder:
    """TC-UT-ERGR-007b: find_by_task_id returns gates in created_at ASC order."""

    async def test_multiple_rounds_returned_in_chronological_order(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-007b: REJECTED → PENDING → PENDING returned oldest-first."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)

        gate_round1 = make_rejected_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            decided_at=base + timedelta(hours=1),
            created_at=base,
        )
        gate_round2 = make_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            created_at=base + timedelta(hours=2),
        )
        gate_round3 = make_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            created_at=base + timedelta(hours=4),
        )

        async with session_factory() as session, session.begin():
            repo = SqliteExternalReviewGateRepository(session)
            for g in [gate_round1, gate_round2, gate_round3]:
                await repo.save(g)

        async with session_factory() as session:
            results = await SqliteExternalReviewGateRepository(session).find_by_task_id(task_id)

        assert len(results) == 3
        assert results[0].id == gate_round1.id, "[FAIL] Oldest gate not first (ASC)."
        assert results[-1].id == gate_round3.id, "[FAIL] Newest gate not last (ASC)."


# ---------------------------------------------------------------------------
# TC-UT-ERGR-007c: find_by_task_id does not return other task's gates
# ---------------------------------------------------------------------------
class TestFindByTaskIdIsolation:
    """TC-UT-ERGR-007c: Cross-task isolation — gates of task_B excluded."""

    async def test_cross_task_isolation(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-007c: find_by_task_id(task_a) does not include task_b gates."""
        task_id_a, stage_id_a, reviewer_id_a = seeded_gate_context
        task_id_b, stage_id_b, reviewer_id_b = await seed_gate_context(session_factory)

        gate_a1 = make_gate(task_id=task_id_a, stage_id=stage_id_a, reviewer_id=reviewer_id_a)
        gate_a2 = make_gate(task_id=task_id_a, stage_id=stage_id_a, reviewer_id=reviewer_id_a)
        gate_b = make_gate(task_id=task_id_b, stage_id=stage_id_b, reviewer_id=reviewer_id_b)

        async with session_factory() as session, session.begin():
            repo = SqliteExternalReviewGateRepository(session)
            await repo.save(gate_a1)
            await repo.save(gate_a2)
            await repo.save(gate_b)

        async with session_factory() as session:
            results_a = await SqliteExternalReviewGateRepository(session).find_by_task_id(task_id_a)

        assert len(results_a) == 2
        ids = {g.id for g in results_a}
        assert gate_b.id not in ids, "[FAIL] task_B gate appeared in task_A results."
