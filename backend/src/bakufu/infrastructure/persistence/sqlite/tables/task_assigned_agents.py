"""``task_assigned_agents`` table — AgentId list for Task Aggregate.

Each row represents one assigned agent for a given Task. The list order is
preserved via ``order_index`` (0-indexed, matching the Aggregate's
``assigned_agent_ids: list[AgentId]`` position).

``agent_id`` intentionally has **no FK** onto ``agents.id`` — this is a
permanent Aggregate boundary design decision (§設計決定 TR-001). Adding a FK
would risk CASCADE deletion of assigned-agent rows when an Agent is archived,
corrupting IN_PROGRESS Tasks. The room-repository ``room_members.agent_id``
establishes the same precedent.

UNIQUE(task_id, agent_id) prevents duplicate assignment of the same Agent to
one Task, mirroring the Aggregate-level
``_validate_assigned_agents_unique`` invariant at the database level for
defense-in-depth.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class TaskAssignedAgentRow(Base):
    """ORM mapping for the ``task_assigned_agents`` table."""

    __tablename__ = "task_assigned_agents"

    task_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    # agent_id: intentionally NO FK onto agents.id.
    # Aggregate boundary: agent deletion must not cascade-delete assigned-agent
    # rows (§設計決定 TR-001, room_members.agent_id 前例同方針).
    agent_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        # Defense-in-Depth: explicit UNIQUE mirrors Aggregate invariant
        # _validate_assigned_agents_unique at the DB level.
        UniqueConstraint("task_id", "agent_id", name="uq_task_assigned_agents"),
    )


__all__ = ["TaskAssignedAgentRow"]
