"""``deliverable_attachments`` table — Attachment metadata for Deliverables.

Each row represents one file attachment associated with a Deliverable. Only
the metadata (sha256 hash, filename, MIME type, size) is stored here; the
physical file bytes are managed by the separate ``feature/attachment-storage``
feature (§確定 R1-I metadata-only scope).

``deliverable_id`` carries an ``ON DELETE CASCADE`` foreign key onto
``deliverables.id`` — when a Deliverable is removed all its attachment
metadata rows go with it.

``UNIQUE(deliverable_id, sha256)`` prevents duplicate attachment entries for
the same file content within a single Deliverable. The sha256 hex string also
provides a deterministic ``ORDER BY sha256 ASC`` sort anchor so repository
hydration reconstructs attachment lists in stable order (§確定 R1-H).

All four metadata columns are validated by the domain-layer
:class:`bakufu.domain.value_objects.Attachment` VO before reaching the
Repository, so DB-level constraints are Defense-in-Depth only.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class DeliverableAttachmentRow(Base):
    """ORM mapping for the ``deliverable_attachments`` table."""

    __tablename__ = "deliverable_attachments"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    deliverable_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("deliverables.id", ondelete="CASCADE"),
        nullable=False,
    )
    # sha256: 64-character lowercase hex; validated by Attachment VO.
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        # UNIQUE(deliverable_id, sha256): prevents duplicate file content
        # within one Deliverable. Also provides stable ORDER BY sha256 ASC
        # sort for deterministic hydration (§確定 R1-H).
        UniqueConstraint("deliverable_id", "sha256", name="uq_deliverable_attachments_sha256"),
    )


__all__ = ["DeliverableAttachmentRow"]
