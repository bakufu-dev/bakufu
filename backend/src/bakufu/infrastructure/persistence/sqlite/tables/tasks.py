"""``tasks`` table — Task Aggregate root row.

Holds the eight scalar columns of the Task aggregate root. Child
collections (assigned agents / conversations / messages / deliverables /
attachments) live in companion modules so the root row width stays bounded
and CASCADE targets are obvious.

``room_id`` carries an ``ON DELETE CASCADE`` foreign key onto ``rooms.id`` —
when a Room is removed, its associated Tasks go with it.

``directive_id`` carries an ``ON DELETE CASCADE`` foreign key onto
``directives.id`` — when a Directive is removed, its associated Tasks go
with it.

``current_stage_id`` intentionally has **no FK** onto ``workflow_stages.id``
— Task and Workflow are separate Aggregates; adding a FK would create an
Aggregate boundary violation and cause ON DELETE ambiguity (§確定 R1-G).
Existence validation is the application layer's responsibility
(``TaskService``).

``last_error`` is a :class:`MaskedText` column (§確定 R1-E). The masking
gateway replaces embedded API keys / OAuth tokens / LLM error secrets with
``<REDACTED:*>`` *before* the row hits SQLite — preventing DB-dump / SQL-log
secret leaks. Nullable: only BLOCKED Tasks carry a ``last_error`` value.

Two indexes are created (§確定 R1-K):

* ``ix_tasks_room_id`` — non-UNIQUE single-column index on ``room_id`` for
  ``count_by_room`` WHERE filters.
* ``ix_tasks_status_updated_id`` — composite ``(status, updated_at, id)``
  non-UNIQUE index that optimises ``find_blocked``
  ``WHERE status = 'BLOCKED' ORDER BY updated_at DESC, id DESC`` with a
  single B-tree scan. The status prefix also accelerates
  ``count_by_status``.
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


class TaskRow(Base):
    """ORM mapping for the ``tasks`` table."""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    room_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    directive_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("directives.id", ondelete="CASCADE"),
        nullable=False,
    )
    # current_stage_id: intentionally NO FK onto workflow_stages.id.
    # Task and Workflow are separate Aggregates; Aggregate boundary dictates
    # that Task must not depend on Workflow's internal stage table directly.
    # Existence validation is TaskService's responsibility (§確定 R1-G).
    current_stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # last_error: MaskedText — LLM error messages may contain API keys /
    # auth tokens. MaskedText.process_bind_param redacts secrets before
    # SQLite storage (§確定 R1-E, masking is irreversible).
    last_error: Mapped[str | None] = mapped_column(MaskedText, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    __table_args__ = (
        # §確定 R1-K: non-UNIQUE single-column index for count_by_room.
        Index("ix_tasks_room_id", "room_id"),
        # §確定 R1-K: composite (status, updated_at, id) index.
        # WHERE status = 'BLOCKED' in find_blocked uses the leading prefix;
        # ORDER BY updated_at DESC, id DESC uses the trailing columns.
        # count_by_status also benefits from the status prefix.
        Index("ix_tasks_status_updated_id", "status", "updated_at", "id"),
    )


__all__ = ["TaskRow"]
