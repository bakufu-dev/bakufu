"""``conversations`` table — Conversation child rows for Task Aggregate.

Each row represents one conversation thread belonging to a Task. A Task may
accumulate multiple conversations over its lifecycle (e.g. one conversation
per Stage execution attempt).

``task_id`` carries an ``ON DELETE CASCADE`` foreign key onto ``tasks.id`` —
when a Task is removed all its conversation rows are removed too.
``conversation_messages`` rows are removed transitively via the
``conversations.id → conversation_messages.conversation_id CASCADE`` chain.

``created_at`` is the UTC timestamp when the conversation was opened; it
serves as the ORDER BY anchor (``ORDER BY created_at ASC, id ASC``) so
repository hydration reconstructs conversations in chronological order
(§確定 R1-H BUG-EMR-001 準拠).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UTCDateTime, UUIDStr


class ConversationRow(Base):
    """ORM mapping for the ``conversations`` table."""

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


__all__ = ["ConversationRow"]
