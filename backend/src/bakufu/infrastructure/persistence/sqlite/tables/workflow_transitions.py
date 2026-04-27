"""``workflow_transitions`` table — Workflow ↔ Transition child rows.

Stores :class:`bakufu.domain.workflow.entities.Transition` values as a
side table of the Workflow Aggregate. ``from_stage_id`` /
``to_stage_id`` are **intentionally not** foreign keys (§確定 J in
``docs/features/workflow-repository/detailed-design.md``); the
Aggregate-level ``_validate_transition_refs`` already enforces that
both ends live inside the Workflow's ``stages`` collection at
construction time.

Cascade: deleting a Workflow row purges its transition rows
(``ON DELETE CASCADE``). The ``UNIQUE(workflow_id, transition_id)``
constraint mirrors
:func:`bakufu.domain.workflow.dag_validators._validate_transition_id_unique`
at the row level.

No ``Masked*`` TypeDecorator on any column — neither the source /
target stage IDs nor the enum-string ``condition`` / human label fall
into the Schneier 申し送り #6 secret categories. Registered with the
CI three-layer defense's no-mask contract.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class WorkflowTransitionRow(Base):
    """ORM mapping for the ``workflow_transitions`` table."""

    __tablename__ = "workflow_transitions"

    workflow_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("workflows.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    transition_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    from_stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    to_stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    condition: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False, default="")

    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "transition_id",
            name="uq_workflow_transitions_pair",
        ),
    )


__all__ = ["WorkflowTransitionRow"]
