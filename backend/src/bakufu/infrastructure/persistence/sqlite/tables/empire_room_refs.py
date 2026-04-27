"""``empire_room_refs`` table — Empire ↔ Room relationship rows.

Stores :class:`bakufu.domain.value_objects.RoomRef` values as a side
table of the Empire Aggregate. ``room_id`` is **intentionally not** a
foreign key onto ``rooms.id`` because the ``rooms`` table arrives in
``feature/room-repository`` (separate PR). The future migration adds
the FK constraint via ``op.create_foreign_key(...)`` once the target
exists.

Cascade: when an Empire row is deleted, its room-ref rows go with it
(``ON DELETE CASCADE``). The ``UNIQUE(empire_id, room_id)`` index is
the row-level uniqueness contract that mirrors the Aggregate Root's
``Empire`` invariant on ``rooms``.

No ``Masked*`` TypeDecorator: see :mod:`...tables.empires` and the
storage.md §逆引き表 explicit "no masking targets" entry.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class EmpireRoomRefRow(Base):
    """ORM mapping for the ``empire_room_refs`` table."""

    __tablename__ = "empire_room_refs"

    empire_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("empires.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    room_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint("empire_id", "room_id", name="uq_empire_room_refs_pair"),)


__all__ = ["EmpireRoomRefRow"]
