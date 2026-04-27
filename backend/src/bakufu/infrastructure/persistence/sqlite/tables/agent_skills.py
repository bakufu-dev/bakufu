"""``agent_skills`` table — Agent ↔ SkillRef child rows.

Stores :class:`bakufu.domain.agent.value_objects.SkillRef` values as
a side table of the Agent aggregate. ``ON DELETE CASCADE`` purges
skill rows when the parent Agent is deleted; UNIQUE(agent_id,
skill_id) mirrors the ``_validate_skill_id_unique`` aggregate
invariant at the row level.

``path`` is stored as a plain ``String(500)`` — the H1〜H10
traversal-defense pipeline runs at VO construction time
(:func:`bakufu.domain.agent.path_validators._validate_skill_path`) so
hydration through :meth:`SqliteAgentRepository.find_by_id` re-runs
the validators automatically when ``SkillRef.model_validate`` is
called inside ``_from_row``. The Repository never re-checks the
contract directly.

No ``Masked*`` TypeDecorator on any column. Skill names / paths /
ids are operational metadata with no secret semantics; the CI
three-layer defense's *no-mask* contract registers this table.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class AgentSkillRow(Base):
    """ORM mapping for the ``agent_skills`` table."""

    __tablename__ = "agent_skills"

    agent_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    skill_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "skill_id",
            name="uq_agent_skills_pair",
        ),
    )


__all__ = ["AgentSkillRow"]
