"""``empire_agent_refs`` table — Empire ↔ Agent relationship rows.

Stores :class:`bakufu.domain.value_objects.AgentRef` values. As with
``empire_room_refs``, ``agent_id`` is intentionally not a foreign key
onto ``agents.id`` because the ``agents`` table arrives in
``feature/agent-repository`` (separate PR); that PR adds the FK via
``op.create_foreign_key(...)``.

Cascade: deleting an Empire row purges its agent refs.
``UNIQUE(empire_id, agent_id)`` mirrors the aggregate-level
duplicate-agent invariant.

No ``Masked*`` TypeDecorator: ``role`` is an enum string and ``name``
is bounded to 40 chars; neither is a secret-bearing column per
storage.md §逆引き表.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class EmpireAgentRefRow(Base):
    """ORM mapping for the ``empire_agent_refs`` table."""

    __tablename__ = "empire_agent_refs"

    empire_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("empires.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (UniqueConstraint("empire_id", "agent_id", name="uq_empire_agent_refs_pair"),)


__all__ = ["EmpireAgentRefRow"]
