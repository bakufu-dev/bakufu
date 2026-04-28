"""ExternalReviewGate Repository: Protocol surface + basic CRUD + Lifecycle.

TC-UT-ERGR-001〜004/009 + TC-IT-ERGR-LIFECYCLE.

RQ-ERGR-001 / RQ-ERGR-002 — 6-method Protocol (§確定 R1-A / §確定 R1-D) +
CRUD (find_by_id / count / save / Tx boundary) + Lifecycle.

save() 5-step child-table semantics (TC-UT-ERGR-005/005b/005c) live in
``test_save_child_tables.py``.  find_pending_by_reviewer + find_by_task_id
(TC-UT-ERGR-006/007) live in ``test_find_methods.py``.
count_by_decision (TC-UT-ERGR-008) lives in ``test_count_by_decision.py``.
masking (TC-IT-ERGR-020-masking-*) lives in ``test_masking_fields.py``.

Per ``docs/features/external-review-gate-repository/test-design.md``.
Issue #36 — M2 0008.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.application.ports.external_review_gate_repository import (
    ExternalReviewGateRepository,
)
from bakufu.domain.value_objects import (
    Attachment,
    AuditAction,
    Deliverable,
    ReviewDecision,
)
from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (
    SqliteExternalReviewGateRepository,
)
from sqlalchemy import event

from tests.factories.external_review_gate import (
    make_approved_gate,
    make_audit_entry,
    make_gate,
)
from tests.factories.task import make_deliverable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-ERGR-001: Protocol definition + 6-method surface (§確定 R1-A / §確定 R1-D)
# ---------------------------------------------------------------------------
class TestExternalReviewGateRepositoryProtocol:
    """TC-UT-ERGR-001: Protocol declares 6 async methods."""

    async def test_protocol_declares_six_async_methods(self) -> None:
        """TC-UT-ERGR-001: ExternalReviewGateRepository has all 6 required methods."""
        for method_name in (
            "find_by_id",
            "count",
            "save",
            "find_pending_by_reviewer",
            "find_by_task_id",
            "count_by_decision",
        ):
            assert hasattr(ExternalReviewGateRepository, method_name), (
                f"[FAIL] ExternalReviewGateRepository.{method_name} missing.\n"
                f"Protocol requires 6 methods per §確定 R1-D."
            )

    async def test_protocol_does_not_have_yagni_methods(self) -> None:
        """TC-UT-ERGR-001: YAGNI methods absent from Protocol.

        §確定 R1-D YAGNI 拒否済み: find_all_pending / find_by_id_all_including_decided.
        """
        for banned_method in ("find_all_pending", "find_by_id_all_including_decided"):
            assert not hasattr(ExternalReviewGateRepository, banned_method), (
                f"[FAIL] ExternalReviewGateRepository.{banned_method} must not exist (YAGNI).\n"
                f"Update §確定 R1-D YAGNI 拒否 before adding."
            )

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-ERGR-001: SqliteExternalReviewGateRepository satisfies Protocol."""
        async with session_factory() as session:
            repo: ExternalReviewGateRepository = SqliteExternalReviewGateRepository(session)
            for method_name in (
                "find_by_id",
                "count",
                "save",
                "find_pending_by_reviewer",
                "find_by_task_id",
                "count_by_decision",
            ):
                assert hasattr(repo, method_name)

    async def test_sqlite_repository_duck_typing_6_methods(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-ERGR-001: duck-typing confirms all 6 methods present on impl."""
        async with session_factory() as session:
            repo = SqliteExternalReviewGateRepository(session)
            for method_name in (
                "find_by_id",
                "count",
                "save",
                "find_pending_by_reviewer",
                "find_by_task_id",
                "count_by_decision",
            ):
                assert hasattr(repo, method_name), (
                    f"SqliteExternalReviewGateRepository missing method: {method_name}"
                )


# ---------------------------------------------------------------------------
# TC-UT-ERGR-002: find_by_id 存在 / 不在
# ---------------------------------------------------------------------------
class TestFindById:
    """TC-UT-ERGR-002: find_by_id returns Gate or None correctly."""

    async def test_find_by_id_returns_saved_gate(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-002: find_by_id returns the Gate after save."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        gate = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        async with session_factory() as session:
            result = await SqliteExternalReviewGateRepository(session).find_by_id(gate.id)

        assert result is not None
        assert result.id == gate.id

    async def test_find_by_id_returns_none_for_missing_gate(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-ERGR-002: find_by_id returns None for a non-existent id."""
        async with session_factory() as session:
            result = await SqliteExternalReviewGateRepository(session).find_by_id(uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# TC-UT-ERGR-003: save → find_by_id round-trip 全属性 (§確定 R1-C)
# ---------------------------------------------------------------------------
class TestSaveRoundTrip:
    """TC-UT-ERGR-003: Full attribute round-trip including child tables."""

    async def test_roundtrip_all_scalar_fields(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-003: save + find_by_id restores all Gate scalar fields."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        snapshot_stage_id = uuid4()
        committed_by = uuid4()
        now = datetime.now(UTC)
        snapshot = Deliverable(
            stage_id=snapshot_stage_id,
            body_markdown="# 設計書完成\n詳細は別途。",
            attachments=[],
            committed_by=committed_by,
            committed_at=now,
        )
        gate = make_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            deliverable_snapshot=snapshot,
            feedback_text="",
            created_at=now,
        )

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        async with session_factory() as session:
            restored = await SqliteExternalReviewGateRepository(session).find_by_id(gate.id)

        assert restored is not None
        assert restored.id == gate.id
        assert restored.task_id == task_id
        assert restored.stage_id == stage_id
        assert restored.reviewer_id == reviewer_id
        assert restored.decision == ReviewDecision.PENDING
        assert restored.feedback_text == ""
        assert restored.decided_at is None
        assert restored.deliverable_snapshot.stage_id == snapshot_stage_id
        assert restored.deliverable_snapshot.committed_by == committed_by
        assert restored.created_at.tzinfo is not None  # UTC tz-aware

    async def test_roundtrip_with_attachments_and_audit_trail(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-003: Attachment + AuditEntry child tables survive round-trip."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        sha256 = "a" * 64
        attachment = Attachment(
            sha256=sha256,
            filename="spec.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
        )
        snapshot = make_deliverable(attachments=[attachment])
        audit = make_audit_entry(action=AuditAction.VIEWED)
        gate = make_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            deliverable_snapshot=snapshot,
            audit_trail=[audit],
        )

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        async with session_factory() as session:
            restored = await SqliteExternalReviewGateRepository(session).find_by_id(gate.id)

        assert restored is not None
        assert len(restored.deliverable_snapshot.attachments) == 1
        assert restored.deliverable_snapshot.attachments[0].sha256 == sha256
        assert len(restored.audit_trail) == 1
        assert restored.audit_trail[0].action == AuditAction.VIEWED
        assert restored.audit_trail[0].id == audit.id


# ---------------------------------------------------------------------------
# TC-UT-ERGR-004: count() SQL COUNT(*) 契約
# ---------------------------------------------------------------------------
class TestCount:
    """TC-UT-ERGR-004: count() issues SELECT COUNT(*) without full-row load."""

    async def test_count_returns_correct_total(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-004: count() returns the total number of gates."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        gate1 = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)
        gate2 = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)

        async with session_factory() as session, session.begin():
            repo = SqliteExternalReviewGateRepository(session)
            await repo.save(gate1)
            await repo.save(gate2)

        async with session_factory() as session:
            total = await SqliteExternalReviewGateRepository(session).count()

        assert total == 2

    async def test_count_issues_sql_count_star(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-004: count() SQL ログに COUNT(*) が含まれ全行ロードパスなし."""
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

            await SqliteExternalReviewGateRepository(session).count()

        assert any("COUNT" in s for s in sql_log), (
            f"[FAIL] count() did not issue COUNT(*) SQL.\nCaptured SQL: {sql_log}"
        )
        # No SELECT * or full-row load
        assert not any("SELECT external_review_gate" in s.lower() for s in sql_log), (
            f"[FAIL] count() triggered full-row load.\nCaptured SQL: {sql_log}"
        )


# ---------------------------------------------------------------------------
# TC-UT-ERGR-009: Tx 境界の責務分離 (empire §確定 B 踏襲)
# ---------------------------------------------------------------------------
class TestTransactionBoundary:
    """TC-UT-ERGR-009: Repository never commits; caller-side UoW owns the boundary."""

    async def test_save_within_begin_is_committed(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-009: save inside session.begin() is visible across sessions."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        gate = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        async with session_factory() as session:
            restored = await SqliteExternalReviewGateRepository(session).find_by_id(gate.id)

        assert restored is not None, "[FAIL] Gate not found after commit."

    async def test_save_without_begin_is_not_committed(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-UT-ERGR-009: save without session.begin() → not persisted (no auto-commit)."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        gate = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)

        async with session_factory() as session:
            # No session.begin() — no explicit transaction context
            await SqliteExternalReviewGateRepository(session).save(gate)
            # Session closed without commit

        async with session_factory() as session:
            restored = await SqliteExternalReviewGateRepository(session).find_by_id(gate.id)

        assert restored is None, (
            "[FAIL] Gate visible without explicit transaction begin — auto-commit active?."
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-LIFECYCLE: 6 method 全経路連携
# ---------------------------------------------------------------------------
class TestLifecycle:
    """TC-IT-ERGR-LIFECYCLE: All 6 Protocol methods interact correctly end-to-end."""

    async def test_full_lifecycle_six_methods(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """TC-IT-ERGR-LIFECYCLE: save → find_pending → find_by_task_id → find_by_id
        → count_by_decision → approve → re-save → verify counts updated."""
        from tests.infrastructure.persistence.sqlite.repositories.test_external_review_gate_repository.conftest import (  # noqa: E501
            seed_gate_context,
        )

        task_id, stage_id, reviewer_id = seeded_gate_context
        # Second task for isolation
        task_id2, stage_id2, reviewer_id2 = await seed_gate_context(session_factory)

        gate1 = make_gate(task_id=task_id, stage_id=stage_id, reviewer_id=reviewer_id)
        gate2 = make_gate(task_id=task_id2, stage_id=stage_id2, reviewer_id=reviewer_id2)

        # (1) save both gates
        async with session_factory() as session, session.begin():
            repo = SqliteExternalReviewGateRepository(session)
            await repo.save(gate1)
            await repo.save(gate2)

        # (2) find_pending_by_reviewer: only gate1 for reviewer
        async with session_factory() as session:
            pending = await SqliteExternalReviewGateRepository(session).find_pending_by_reviewer(
                reviewer_id
            )
        assert len(pending) == 1
        assert pending[0].id == gate1.id

        # (3) find_by_task_id
        async with session_factory() as session:
            by_task = await SqliteExternalReviewGateRepository(session).find_by_task_id(task_id)
        assert len(by_task) == 1
        assert by_task[0].id == gate1.id

        # (4) find_by_id
        async with session_factory() as session:
            single = await SqliteExternalReviewGateRepository(session).find_by_id(gate1.id)
        assert single is not None
        assert single.id == gate1.id

        # (5) count_by_decision: 2 PENDING total
        async with session_factory() as session:
            pending_count = await SqliteExternalReviewGateRepository(session).count_by_decision(
                ReviewDecision.PENDING
            )
        assert pending_count == 2

        # (6) approve gate1 → re-save
        approved_gate1 = make_approved_gate(
            gate_id=gate1.id,
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            decided_at=datetime.now(UTC),
        )
        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(approved_gate1)

        # (7) counts updated
        async with session_factory() as session:
            repo = SqliteExternalReviewGateRepository(session)
            pending_count_after = await repo.count_by_decision(ReviewDecision.PENDING)
            approved_count = await repo.count_by_decision(ReviewDecision.APPROVED)
            pending_list = await repo.find_pending_by_reviewer(reviewer_id)

        assert pending_count_after == 1, "[FAIL] PENDING count should drop to 1 after approve."
        assert approved_count == 1, "[FAIL] APPROVED count should be 1."
        assert pending_list == [], "[FAIL] find_pending_by_reviewer should return [] after approve."
