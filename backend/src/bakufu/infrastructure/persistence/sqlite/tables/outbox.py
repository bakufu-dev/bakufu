"""``domain_event_outbox`` table (Outbox pattern, §確定 K).

The Outbox decouples domain event emission from external side effects
(Discord notifier, LLM Adapter call, etc.). Each row carries a
``payload_json`` blob — produced by an Aggregate's behavior — that
**must** be redacted before it lands on disk because raw payloads can
embed webhook URLs, API keys, or filesystem paths.

The masking listener applies on both ``before_insert`` and
``before_update``; raw-SQL paths (``session.execute(insert(...))``)
trigger the same listener, so masking is enforced even for code that
bypasses the ORM mapper. See Confirmation B in
``triggers.md``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Index, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    JSONEncoded,
    UTCDateTime,
    UUIDStr,
)
from bakufu.infrastructure.security.masking import (
    REDACT_LISTENER_ERROR,
    mask,
    mask_in,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection
    from sqlalchemy.orm import Mapper

logger = logging.getLogger(__name__)


class OutboxRow(Base):
    """ORM mapping for the ``domain_event_outbox`` table."""

    __tablename__ = "domain_event_outbox"

    event_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    event_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    payload_json: Mapped[Any] = mapped_column(JSONEncoded, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True
    )

    # Polling SQL filter: `WHERE status = ? AND next_attempt_at <= ?`.
    __table_args__ = (
        Index("ix_outbox_status_next_attempt", "status", "next_attempt_at"),
    )


def _apply_masking(target: OutboxRow) -> None:
    """Redact ``payload_json`` and ``last_error``.

    Confirmation F (Fail-Secure): on listener failure, both columns
    are replaced with the sentinel — never leak raw payload bytes.
    """
    try:
        target.payload_json = mask_in(target.payload_json)
        if target.last_error is not None:
            target.last_error = mask(target.last_error)
    except Exception as exc:  # pragma: no cover — Fail-Secure
        logger.error(
            "[ERROR] domain_event_outbox masking listener failed: %r — "
            "replacing secret-bearing fields with %s",
            exc,
            REDACT_LISTENER_ERROR,
        )
        target.payload_json = REDACT_LISTENER_ERROR
        target.last_error = REDACT_LISTENER_ERROR


def _before_insert(
    _mapper: Mapper[OutboxRow],
    _connection: Connection,
    target: OutboxRow,
) -> None:
    _apply_masking(target)


def _before_update(
    _mapper: Mapper[OutboxRow],
    _connection: Connection,
    target: OutboxRow,
) -> None:
    _apply_masking(target)


event.listen(OutboxRow, "before_insert", _before_insert)
event.listen(OutboxRow, "before_update", _before_update)


__all__ = ["OutboxRow"]
