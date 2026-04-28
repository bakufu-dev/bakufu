"""``external_review_audit_entries`` table — AuditEntry child rows.

Stores the append-only audit trail for each :class:`ExternalReviewGate`.
Every ``approve`` / ``reject`` / ``cancel`` / ``record_view`` call on the
domain Gate appends exactly one :class:`AuditEntry`; the Repository persists
all entries on each ``save()`` via the §確定 R1-B DELETE-then-INSERT flow.

``gate_id`` carries an ``ON DELETE CASCADE`` foreign key onto
``external_review_gates.id`` — when a Gate is removed, its audit entries
go with it.

``actor_id`` intentionally has **no FK** — Owner Aggregate is not yet
implemented in M2 scope (§設計決定 ERGR-001). Reference integrity is the
application layer's responsibility (``GateService``).

``id`` is taken directly from :class:`AuditEntry.id` (domain-assigned UUID),
**not** regenerated on save. Unlike attachment rows (which use save-internal
PKs), audit entries carry their own stable identity so the Repository can
reconstruct the exact :class:`AuditEntry` instances the domain produced.

**masking 対象カラム**: ``comment`` (MaskedText) — CEO-authored free-form
text in the same input path as ``feedback_text``; can carry webhook URLs /
API keys (§確定 R1-E 3-column CI defense).
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


class ExternalReviewAuditEntryRow(Base):
    """ORM mapping for the ``external_review_audit_entries`` table."""

    __tablename__ = "external_review_audit_entries"

    # id: taken directly from AuditEntry.id (domain UUID, NOT regenerated).
    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    gate_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("external_review_gates.id", ondelete="CASCADE"),
        nullable=False,
    )
    # actor_id: intentionally NO FK onto owners/agents — Owner Aggregate not
    # yet implemented (§設計決定 ERGR-001). GateService validates existence.
    actor_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    # comment: MaskedText — CEO-authored text in approve/reject/cancel/view
    # input path; can carry webhook URLs / API keys (§確定 R1-E). NOT NULL:
    # AuditEntry.comment defaults to "" on VIEWED entries.
    comment: Mapped[str] = mapped_column(MaskedText, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


__all__ = ["ExternalReviewAuditEntryRow"]
