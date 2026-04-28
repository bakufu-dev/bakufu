"""``rooms`` table — Room Aggregate root row.

Holds the seven scalar columns of the Room aggregate root. The member
collection (``room_members``) lives in the companion module
:mod:`...tables.room_members` so the root row width stays bounded and
CASCADE targets are obvious.

``empire_id`` carries an ``ON DELETE CASCADE`` foreign key onto
``empires.id`` — when an Empire is removed, its Rooms go with it.

``workflow_id`` carries an ``ON DELETE RESTRICT`` foreign key onto
``workflows.id`` — Workflow is a reference target, not an owner, so
deleting a Workflow while Rooms still reference it is a hard failure
(§確定 R1-I: Defense-in-Depth alongside the application-layer check).

``name`` is intentionally **not** declared UNIQUE at the DB level. The
"name unique within an Empire" invariant is enforced by the application
layer via :meth:`RoomRepository.find_by_name` (agent §R1-B same logic)
so MSG-RM-NNN wording stays in the application layer's voice rather than
being preempted by ``IntegrityError``.

``prompt_kit_prefix_markdown`` is a :class:`MaskedText` column (room
§確定 G 実適用). ``MaskingGateway`` replaces embedded API keys / OAuth
tokens / Discord webhook secrets etc. with ``<REDACTED:*>`` *before* the
row hits SQLite — preventing DB-dump / SQL-log secret leaks. The masking
is irreversible; see §確定 R1-J and :mod:`...repositories.room_repository`
for the full contract.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UUIDStr,
)


class RoomRow(Base):
    """ORM mapping for the ``rooms`` table."""

    __tablename__ = "rooms"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    empire_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("empires.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("workflows.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    prompt_kit_prefix_markdown: Mapped[str] = mapped_column(MaskedText, nullable=False, default="")
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        # §確定 R1-F: non-UNIQUE composite index for Empire-scoped find_by_name
        # lookup. Left-prefix optimises both ``WHERE empire_id = ?`` and
        # ``WHERE empire_id = ? AND name = ?`` queries.
        Index("ix_rooms_empire_id_name", "empire_id", "name", unique=False),
    )


__all__ = ["RoomRow"]
