"""``directives`` table — Directive Aggregate root row.

Holds the five scalar columns of the Directive aggregate. Directive is a
flat aggregate with no child tables — every attribute maps to a single row
in this table.

``target_room_id`` carries an ``ON DELETE CASCADE`` foreign key onto
``rooms.id`` — when a Room is removed, its associated Directives go with it.

``task_id`` is nullable and carries **no FK** at this migration level.
``tasks.id`` does not exist yet; the FK closure is deferred to the
task-repository PR via ``op.batch_alter_table('directives', recreate='always')``
(§BUG-DRR-001 申し送り, same pattern as BUG-EMR-001 in 0005_room_aggregate).

``text`` is a :class:`MaskedText` column (§確定 R1-E). ``MaskingGateway``
replaces embedded API keys / OAuth tokens / Discord webhook secrets etc. with
``<REDACTED:*>`` *before* the row hits SQLite — preventing DB-dump / SQL-log
secret leaks. The masking is irreversible; see
:mod:`...repositories.directive_repository` for the full contract.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class DirectiveRow(Base):
    """ORM mapping for the ``directives`` table."""

    __tablename__ = "directives"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    text: Mapped[str] = mapped_column(MaskedText, nullable=False)
    target_room_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    # task_id intentionally has NO FK onto tasks.id — tasks table does not
    # exist at this migration level. FK closure is deferred to the
    # task-repository PR (§BUG-DRR-001 / BUG-EMR-001 pattern).
    task_id: Mapped[UUID | None] = mapped_column(UUIDStr, nullable=True)

    __table_args__ = (
        # §確定 R1-D: composite index for Room-scoped find_by_room lookup.
        # Left-prefix optimises ``WHERE target_room_id = ?`` and the full
        # ``WHERE target_room_id = ? ORDER BY created_at DESC`` query shape.
        # ``id`` (PK) acts as tiebreaker in-engine; no additional index needed.
        Index("ix_directives_target_room_id_created_at", "target_room_id", "created_at"),
    )


__all__ = ["DirectiveRow"]
