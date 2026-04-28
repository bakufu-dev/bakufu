"""``room_members`` table — AgentMembership child rows of the Room Aggregate.

Stores each :class:`bakufu.domain.room.value_objects.AgentMembership` as a
DB row. A Room can host multiple members; each entry is identified by the
``(room_id, agent_id, role)`` triplet.

Design contracts (§確定 R1-D):

* ``room_id`` FK → ``rooms.id`` ON DELETE CASCADE: removing the Room
  purges all its membership rows.
* ``agent_id`` has **no FK** onto ``agents.id``. Room §確定 freezes Agent
  existence checking as the application-layer's responsibility
  (``RoomService.add_member`` calls ``AgentRepository.find_by_id``). A FK
  CASCADE would silently delete memberships when the Agent row disappears;
  FK RESTRICT would block clean removal of archived Agents from Rooms.
  Neither is correct for the MVP model — application-layer check only.
* Composite PK ``(room_id, agent_id, role)`` plus an explicit named
  ``UniqueConstraint`` for CI Layer 2 arch-test detectability. The PK
  implies UNIQUE but ``__table_args__`` scanning in the arch test only
  catches explicit constraint declarations (agent_providers pattern,
  detailed-design §確定 R1-D rationale).
* ``joined_at`` uses ``DateTime(timezone=True)`` so aiosqlite preserves
  the UTC ``tzinfo`` on read — the hydrated ``AgentMembership.joined_at``
  is always tz-aware as frozen in room/detailed-design.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class RoomMemberRow(Base):
    """ORM mapping for the ``room_members`` table."""

    __tablename__ = "room_members"

    room_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        primary_key=True,
        nullable=False,
        # Intentionally no FK onto agents.id — see module docstring.
    )
    role: Mapped[str] = mapped_column(String(32), primary_key=True, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # §確定 R1-D: explicit UniqueConstraint mirrors the composite PK so the
        # CI Layer 2 arch test can assert UNIQUE-constraint existence by scanning
        # ``__table_args__``. PK-derived implicit UNIQUE is invisible to that
        # scan, so the redundancy is load-bearing for the Defense-in-Depth floor.
        UniqueConstraint(
            "room_id",
            "agent_id",
            "role",
            name="uq_room_members_triplet",
        ),
    )


__all__ = ["RoomMemberRow"]
