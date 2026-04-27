"""``domain_event_outbox`` table (Outbox pattern, §確定 K).

The Outbox decouples domain event emission from external side effects
(Discord notifier, LLM Adapter call, etc.). Each row carries a
``payload_json`` blob — produced by an Aggregate's behavior — that
**must** be redacted before it lands on disk because raw payloads can
embed webhook URLs, API keys, or filesystem paths.

Secret-column masking is wired at the engine ``before_execute`` level
in :mod:`bakufu.infrastructure.persistence.sqlite.masking_listener`.
That listener fires for both ORM ``Session.add()`` flushes and Core
``session.execute(insert(table).values(...))`` paths, so the
"raw-SQL path is masked too" promise (Confirmation B / Confirmation
R1-D / Schneier #6) is now honored end-to-end (BUG-PF-001 fix).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedJSONEncoded,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class OutboxRow(Base):
    """ORM mapping for the ``domain_event_outbox`` table.

    ``payload_json`` and ``last_error`` use the ``Masked*`` column
    types so every bind value passes through the masking gateway
    regardless of whether the row arrives via ORM ``Session.add`` or
    Core ``session.execute(insert(...).values(...))`` (BUG-PF-001 fix).
    """

    __tablename__ = "domain_event_outbox"

    event_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    event_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    payload_json: Mapped[Any] = mapped_column(MaskedJSONEncoded, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    last_error: Mapped[str | None] = mapped_column(MaskedText, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    # Polling SQL filter: `WHERE status = ? AND next_attempt_at <= ?`.
    __table_args__ = (Index("ix_outbox_status_next_attempt", "status", "next_attempt_at"),)


__all__ = ["OutboxRow"]
