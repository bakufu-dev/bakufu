"""``external_review_gates`` table — ExternalReviewGate Aggregate root row.

Holds all twelve scalar columns of the ExternalReviewGate aggregate root,
including the inline ``deliverable_snapshot`` copy (four columns prefixed
``snapshot_``). Child collections (attachments / audit entries) live in
companion modules so the root row width stays bounded and CASCADE targets
are obvious.

``task_id`` carries an ``ON DELETE CASCADE`` foreign key onto ``tasks.id`` —
when a Task is removed, its associated Gates go with it.

``stage_id`` and ``reviewer_id`` and ``snapshot_committed_by`` intentionally
have **no FK** (§設計決定 ERGR-001):
- ``stage_id``: Workflow Aggregate boundary; Gate must not depend on
  workflow_stages directly.
- ``reviewer_id``: Owner Aggregate not yet implemented (M2 scope).
- ``snapshot_committed_by``: Agent deletion with CASCADE would destroy the
  audit-frozen snapshot (task-repository §設計決定 TR-001 同論理).

Two masking columns (§設計決定 ERGR-002, §確定 R1-E, 3-column CI defense):

* ``feedback_text`` — MaskedText: CEO-authored review comment; ``approve`` /
  ``reject`` / ``cancel`` input paths can carry webhook URLs / API keys.
* ``snapshot_body_markdown`` — MaskedText: Agent-authored deliverable body;
  LLM output may contain API keys / auth tokens embedded in code blocks.

Three indexes (§確定 R1-K):

* ``ix_external_review_gates_task_id_created`` — composite ``(task_id,
  created_at)`` for ``find_by_task_id`` WHERE + ORDER BY in one B-tree scan.
* ``ix_external_review_gates_reviewer_decision`` — composite
  ``(reviewer_id, decision)`` for ``find_pending_by_reviewer`` WHERE
  reviewer_id + decision = 'PENDING' filter.
* ``ix_external_review_gates_decision`` — single-column ``(decision)`` for
  ``count_by_decision`` WHERE filter (prefix coverage of the composite index
  above is insufficient for a full COUNT(*) scan).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class ExternalReviewGateRow(Base):
    """ORM mapping for the ``external_review_gates`` table."""

    __tablename__ = "external_review_gates"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    # stage_id: intentionally NO FK onto workflow_stages.id —
    # Aggregate boundary (§設計決定 ERGR-001). GateService validates existence.
    stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # reviewer_id: intentionally NO FK — Owner Aggregate not yet implemented
    # (§設計決定 ERGR-001). MVP: CEO = single system owner with fixed UUID.
    reviewer_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    # feedback_text: MaskedText — CEO review comment; approve / reject / cancel
    # input paths can carry webhook URLs / API keys (§設計決定 ERGR-002,
    # §確定 R1-E). MaskedText.process_bind_param redacts secrets before SQLite
    # storage. NOT NULL: domain Gate.feedback_text defaults to "" on PENDING.
    feedback_text: Mapped[str] = mapped_column(MaskedText, nullable=False)
    # ---- inline deliverable_snapshot copy (§確定 R1-C) ---------------------
    # snapshot_stage_id: NO FK onto workflow_stages.id — same rationale as
    # stage_id above (Aggregate boundary).
    snapshot_stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # snapshot_body_markdown: MaskedText — Agent-authored deliverable body;
    # LLM output may contain secrets embedded in code blocks (§確定 R1-E).
    snapshot_body_markdown: Mapped[str] = mapped_column(MaskedText, nullable=False)
    # snapshot_committed_by: intentionally NO FK onto agents.id —
    # Agent deletion with CASCADE would destroy audit-frozen snapshot
    # (§設計決定 ERGR-001, TR-001 同論理).
    snapshot_committed_by: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    snapshot_committed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    # ---- lifecycle timestamps -----------------------------------------------
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    # decided_at: NULL iff decision == PENDING (domain invariant).
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    __table_args__ = (
        # §確定 R1-K: composite (task_id, created_at) index for find_by_task_id.
        # WHERE task_id + ORDER BY created_at ASC covered by one B-tree scan.
        Index("ix_external_review_gates_task_id_created", "task_id", "created_at"),
        # §確定 R1-K: composite (reviewer_id, decision) for find_pending_by_reviewer.
        # WHERE reviewer_id + decision = 'PENDING' covered without full-table scan.
        Index(
            "ix_external_review_gates_reviewer_decision",
            "reviewer_id",
            "decision",
        ),
        # §確定 R1-K: single-column (decision) for count_by_decision.
        # The composite above does not cover COUNT(*) over all reviewers.
        Index("ix_external_review_gates_decision", "decision"),
    )


__all__ = ["ExternalReviewGateRow"]
