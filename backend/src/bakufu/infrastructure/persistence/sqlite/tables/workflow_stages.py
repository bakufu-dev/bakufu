"""``workflow_stages`` table — Workflow ↔ Stage child rows.

Stores :class:`bakufu.domain.workflow.entities.Stage` values as a side
table of the Workflow Aggregate. ``stage_id`` is **intentionally not** a
foreign key onto ``workflows.entry_stage_id`` (§確定 J in
``docs/features/workflow-repository/detailed-design.md``); the
Aggregate-level ``_validate_entry_in_stages`` already enforces the
reference invariant.

Cascade: deleting a Workflow row purges its stage rows
(``ON DELETE CASCADE``). The ``UNIQUE(workflow_id, stage_id)`` constraint
mirrors :func:`bakufu.domain.workflow.dag_validators._validate_stage_id_unique`
at the row level.

Per-column secret-handling (§確定 H + 申し送り #6 of M2 persistence
foundation):

* ``notify_channels_json`` is a :class:`MaskedJSONEncoded` column. The
  ``process_bind_param`` hook re-routes every nested ``target`` field
  through :func:`bakufu.infrastructure.security.masking.mask_in` so the
  Discord webhook ``token`` segment never reaches disk in plaintext.
  Defense-in-depth: ``NotifyChannel.field_serializer(when_used='json')``
  already masks at ``model_dump(mode='json')`` time, but the
  TypeDecorator is the *gate* that fires for both ORM and Core
  ``insert(table).values(...)`` paths (BUG-PF-001 contract).
* ``completion_policy_json`` is a plain :class:`JSONEncoded` column —
  the VO carries no secret-bearing values per the Schneier申し送り #6
  six-category scan, so ``MaskedJSONEncoded`` would be **over-masking**
  (banned by §確定 I of the detailed design).
* The remaining columns hold UUIDs / enums / CEO-authored Markdown
  templates; none qualify as the six masking categories.

The CI three-layer defense pins exactly one
``MaskedJSONEncoded`` column on this table (positive contract on
``notify_channels_json``, no-mask on every other column).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    JSONEncoded,
    MaskedJSONEncoded,
    UUIDStr,
)


class WorkflowStageRow(Base):
    """ORM mapping for the ``workflow_stages`` table."""

    __tablename__ = "workflow_stages"

    workflow_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("workflows.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    stage_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    roles_csv: Mapped[str] = mapped_column(String(255), nullable=False)
    deliverable_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    completion_policy_json: Mapped[Any] = mapped_column(JSONEncoded, nullable=False)
    # Default ``[]`` is enforced at the SQL level by the ``server_default``
    # in 0003_workflow_aggregate.py; ORM-side defaulting is unnecessary
    # because the Repository always passes an explicit list.
    notify_channels_json: Mapped[Any] = mapped_column(MaskedJSONEncoded, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "stage_id",
            name="uq_workflow_stages_pair",
        ),
    )


__all__ = ["WorkflowStageRow"]
