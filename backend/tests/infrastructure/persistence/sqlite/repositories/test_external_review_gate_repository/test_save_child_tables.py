"""ExternalReviewGate Repository: 5-step save() physical verification.

TC-UT-ERGR-005 / 005b / 005c — §確定 R1-B save() 5段階の物理確認.

Tests that:
* DELETE child tables (steps 1+2) prevent duplicate rows on re-save.
* UPSERT gate (step 3) + INSERT attachments (step 4) + INSERT audit_entries (step 5).
* UNIQUE(gate_id, sha256) constraint satisfied on every re-save cycle.
* Empty gate upgraded to full gate (all 5 steps exercised).

Per ``docs/features/external-review-gate-repository/test-design.md``
TC-UT-ERGR-005/005b/005c.
Issue #36 — M2 0008.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from bakufu.domain.value_objects import Attachment, AuditAction, ReviewDecision
from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (
    SqliteExternalReviewGateRepository,
)
from sqlalchemy import text

from tests.factories.external_review_gate import (
    make_approved_gate,
    make_audit_entry,
    make_gate,
)
from tests.factories.task import make_deliverable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


async def _count_attachments(
    session_factory: async_sessionmaker[AsyncSession],
    gate_id: UUID,
) -> int:
    """Count external_review_gate_attachments rows for gate_id via raw SQL."""
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM external_review_gate_attachments WHERE gate_id = :gate_id"
                ),
                {"gate_id": gate_id.hex},
            )
        ).first()
    return row[0] if row else 0


async def _count_audit_entries(
    session_factory: async_sessionmaker[AsyncSession],
    gate_id: UUID,
) -> int:
    """Count external_review_audit_entries rows for gate_id via raw SQL."""
    async with session_factory() as session:
        row = (
            await session.execute(
                text("SELECT COUNT(*) FROM external_review_audit_entries WHERE gate_id = :gate_id"),
                {"gate_id": gate_id.hex},
            )
        ).first()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# TC-UT-ERGR-005: audit_entries DELETE + re-INSERT on re-save
# ---------------------------------------------------------------------------
class TestSaveChildTableSemantics:
    """TC-UT-ERGR-005: §確定 R1-B DELETE → UPSERT → INSERT 5-step order."""

    async def test_resave_updates_decision_and_replaces_audit_entries(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-005: re-save after approve replaces audit_entries (DELETE + re-INSERT)."""
        task_id, stage_id, reviewer_id = seeded_gate_context

        # First save: PENDING gate, no audit entries
        gate = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)
        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        count_before = await _count_audit_entries(session_factory, gate.id)
        assert count_before == 0

        # Re-save as APPROVED with 1 audit entry
        decided_at = datetime.now(UTC)
        approved = make_approved_gate(
            gate_id=gate.id,
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            decided_at=decided_at,
        )
        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(approved)

        count_after = await _count_audit_entries(session_factory, gate.id)
        assert count_after == 1, f"[FAIL] expected 1 audit entry after re-save, got {count_after}"

        # Decision updated via UPSERT
        async with session_factory() as session:
            restored = await SqliteExternalReviewGateRepository(session).find_by_id(gate.id)

        assert restored is not None
        assert restored.decision == ReviewDecision.APPROVED
        assert len(restored.audit_trail) == 1
        assert restored.audit_trail[0].action == AuditAction.APPROVED

    async def test_resave_does_not_duplicate_gate_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-005: UPSERT ensures only 1 row in external_review_gates per id."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        gate = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)
        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        async with session_factory() as session:
            row = (
                await session.execute(
                    text("SELECT COUNT(*) FROM external_review_gates WHERE id = :id"),
                    {"id": gate.id.hex},
                )
            ).first()
        assert row[0] == 1, f"[FAIL] UPSERT produced {row[0]} rows, expected 1."


# ---------------------------------------------------------------------------
# TC-UT-ERGR-005b: UNIQUE(gate_id, sha256) no duplicate on re-save
# ---------------------------------------------------------------------------
class TestAttachmentUniqueConstraintOnReSave:
    """TC-UT-ERGR-005b: Step 1 DELETE prevents UNIQUE(gate_id, sha256) violation."""

    async def test_resave_with_same_attachments_no_unique_violation(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-005b: re-save with same sha256 attachment does not raise IntegrityError."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        sha256 = "b" * 64
        attachment = Attachment(
            sha256=sha256,
            filename="report.pdf",
            mime_type="application/pdf",
            size_bytes=2048,
        )
        snapshot = make_deliverable(attachments=[attachment])
        gate = make_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            deliverable_snapshot=snapshot,
        )

        # First save
        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)
        count_after_first = await _count_attachments(session_factory, gate.id)
        assert count_after_first == 1

        # Re-save (step 1 DELETE + step 4 INSERT — must not fail)
        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)
        count_after_second = await _count_attachments(session_factory, gate.id)

        assert count_after_second == 1, (
            f"[FAIL] Expected 1 attachment after re-save, got {count_after_second}. "
            f"Duplicate row created — step 1 DELETE not working."
        )

    async def test_resave_with_two_attachments_count_is_correct(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-005b: re-save with 2 attachments yields exactly 2 rows."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        att1 = Attachment(
            sha256="c" * 64, filename="a.pdf", mime_type="application/pdf", size_bytes=100
        )
        att2 = Attachment(
            sha256="d" * 64, filename="b.pdf", mime_type="application/pdf", size_bytes=200
        )
        snapshot = make_deliverable(attachments=[att1, att2])
        gate = make_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            deliverable_snapshot=snapshot,
        )

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)
        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        count = await _count_attachments(session_factory, gate.id)
        assert count == 2, f"[FAIL] Expected 2 attachments, got {count}."


# ---------------------------------------------------------------------------
# TC-UT-ERGR-005c: Empty gate → full gate update (all 5 steps)
# ---------------------------------------------------------------------------
class TestEmptyToFullGateUpdate:
    """TC-UT-ERGR-005c: Empty gate (no children) → gate with audit_trail (steps 3-5)."""

    async def test_resave_empty_to_full_gate_all_child_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-005c: Empty gate upgraded to APPROVED gate with audit entries."""
        task_id, stage_id, reviewer_id = seeded_gate_context

        # Save empty gate (PENDING, no audit_trail)
        gate = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)
        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        assert await _count_audit_entries(session_factory, gate.id) == 0

        # Re-save as APPROVED with 1 entry
        decided = datetime.now(UTC)
        audit_entry = make_audit_entry(action=AuditAction.APPROVED, occurred_at=decided)
        approved = make_approved_gate(
            gate_id=gate.id,
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            audit_trail=[audit_entry],
            decided_at=decided,
        )
        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(approved)

        assert await _count_audit_entries(session_factory, gate.id) == 1

        async with session_factory() as session:
            restored = await SqliteExternalReviewGateRepository(session).find_by_id(gate.id)

        assert restored is not None
        assert restored.decision == ReviewDecision.APPROVED
        assert len(restored.audit_trail) == 1
        assert restored.audit_trail[0].action == AuditAction.APPROVED
