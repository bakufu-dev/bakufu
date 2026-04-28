"""``deliverables`` table — Deliverable child rows for Task Aggregate.

Each row represents one per-Stage deliverable snapshot. The Task Aggregate
keeps ``deliverables: dict[StageId, Deliverable]`` so only the latest commit
for a given Stage survives (dict key uniqueness). The ``UNIQUE(task_id,
stage_id)`` constraint enforces the same invariant at the database level.

``task_id`` carries an ``ON DELETE CASCADE`` foreign key onto ``tasks.id``.
``deliverable_attachments`` rows are removed transitively via the
``deliverables.id → deliverable_attachments.deliverable_id CASCADE`` chain.

``stage_id`` intentionally has **no FK** onto ``workflow_stages.id`` — same
Aggregate boundary rationale as ``tasks.current_stage_id`` (§確定 R1-G).

``committed_by`` intentionally has **no FK** onto ``agents.id`` — same
Aggregate boundary rationale as ``task_assigned_agents.agent_id``
(§設計決定 TR-001).

``body_markdown`` is a :class:`MaskedText` column (§確定 R1-E). Agent output
submitted as a deliverable may contain embedded API keys / auth tokens.
The masking gateway replaces them with ``<REDACTED:*>`` *before* the row hits
SQLite (irreversible masking, §確定 R1-G 不可逆性凍結).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class DeliverableRow(Base):
    """ORM mapping for the ``deliverables`` table."""

    __tablename__ = "deliverables"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    # stage_id: intentionally NO FK onto workflow_stages.id.
    # Aggregate boundary: Workflow and Task are independent Aggregates;
    # Stage deletion must not cascade-delete deliverables (§確定 R1-G).
    stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # body_markdown: MaskedText — Agent-submitted output may contain secrets.
    # MaskedText.process_bind_param redacts before SQLite storage (§確定 R1-E).
    body_markdown: Mapped[str] = mapped_column(MaskedText, nullable=False)
    # committed_by: intentionally NO FK onto agents.id.
    # Aggregate boundary (§設計決定 TR-001, room_members.agent_id 前例同方針).
    committed_by: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    committed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    __table_args__ = (
        # UNIQUE(task_id, stage_id): mirrors the Aggregate's
        # ``deliverables: dict[StageId, Deliverable]`` key-uniqueness invariant
        # at the DB level. Also ensures the save() §確定 R1-B step-1 DELETE +
        # step-8 INSERT pattern never hits a UNIQUE violation.
        UniqueConstraint("task_id", "stage_id", name="uq_deliverables_task_stage"),
    )


__all__ = ["DeliverableRow"]
