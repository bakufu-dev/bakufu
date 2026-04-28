"""``external_review_gate_attachments`` table — snapshot Attachment child rows.

Stores per-attachment metadata for the ``deliverable_snapshot`` inline copy
inside each :class:`ExternalReviewGate`. Physical file bytes are out of scope
for this feature (``feature/attachment-storage``).

``gate_id`` carries an ``ON DELETE CASCADE`` foreign key onto
``external_review_gates.id`` — when a Gate is removed, its snapshot
attachment rows go with it.

``id`` is a **save-internal** primary key regenerated via ``uuid4()`` on
every :meth:`SqliteExternalReviewGateRepository.save` call (DELETE-then-INSERT
pattern). External code must not reference this PK; the business key is
``UNIQUE(gate_id, sha256)``.

**masking 対象カラム**: なし (全カラム masking 対象外)。Attachment metadata
(sha256 / filename / mime_type / size_bytes) carries no Schneier #6 secret
semantics; the content hash identifies a file but reveals nothing about its
contents.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class ExternalReviewGateAttachmentRow(Base):
    """ORM mapping for the ``external_review_gate_attachments`` table."""

    __tablename__ = "external_review_gate_attachments"

    # id: internal PK regenerated on each save(); external code must use
    # UNIQUE(gate_id, sha256) as the business key (§確定 R1-B).
    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    gate_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("external_review_gates.id", ondelete="CASCADE"),
        nullable=False,
    )
    # sha256: 64-char lowercase hex; validated by Attachment VO.
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        # UNIQUE(gate_id, sha256): prevents duplicate content within one Gate;
        # sha256 provides deterministic ORDER BY anchor (§確定 R1-H).
        UniqueConstraint("gate_id", "sha256", name="uq_erg_attachments_gate_sha256"),
    )


__all__ = ["ExternalReviewGateAttachmentRow"]
