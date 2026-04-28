"""``conversation_messages`` table — Message child rows for Conversation.

Each row represents one message within a conversation. Messages carry a
``speaker_kind`` discriminator ('AGENT' / 'SYSTEM' / 'USER'), a
``body_markdown`` content field, and a UTC ``timestamp``.

``conversation_id`` carries an ``ON DELETE CASCADE`` foreign key onto
``conversations.id`` — when a Conversation is removed all its messages go
with it.

``body_markdown`` is a :class:`MaskedText` column (§確定 R1-E). Subprocess
output, LLM responses, and system messages may contain API keys / auth tokens
embedded in error traces. The masking gateway replaces them with
``<REDACTED:*>`` *before* the row hits SQLite.

``timestamp`` is the UTC moment the speaker sent the message; it serves as
the ORDER BY anchor (``ORDER BY timestamp ASC, id ASC``) so repository
hydration reconstructs messages in chronological order (§確定 R1-H).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class ConversationMessageRow(Base):
    """ORM mapping for the ``conversation_messages`` table."""

    __tablename__ = "conversation_messages"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    speaker_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # body_markdown: MaskedText — subprocess output and LLM replies may contain
    # embedded secrets. MaskedText.process_bind_param redacts them before
    # SQLite storage (§確定 R1-E, irreversible masking).
    body_markdown: Mapped[str] = mapped_column(MaskedText, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


__all__ = ["ConversationMessageRow"]
