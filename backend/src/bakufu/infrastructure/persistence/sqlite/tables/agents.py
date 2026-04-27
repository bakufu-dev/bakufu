"""``agents`` table — Agent Aggregate root row.

Holds the eight scalar columns of the Agent aggregate. The two side
collections (``providers`` / ``skills``) live in
:mod:`...tables.agent_providers` / :mod:`...tables.agent_skills` so
the row width stays bounded and CASCADE targets are obvious.

``empire_id`` carries an ``ON DELETE CASCADE`` foreign key onto
``empires.id`` — when an Empire is removed, its hired Agents go with
it. The Agent aggregate root holds the matching ``empire_id`` field
(see ``backend/src/bakufu/domain/agent/agent.py``) so
``SqliteAgentRepository.save()`` can populate this column without
asking the caller for it.

``name`` is intentionally **not** declared UNIQUE at the DB level. The
"name unique within an Empire" invariant is enforced by the
application layer via :meth:`AgentRepository.find_by_name` (per
``docs/features/agent-repository/detailed-design.md`` §設計判断補足
"なぜ agents.name に DB UNIQUE を張らないか") so MSG-AG-NNN wording
stays in the application layer's voice rather than being preempted by
``IntegrityError``.

Per-column secret-handling (§確定 H + Schneier 申し送り #3 实適用):

* ``prompt_body`` is a :class:`MaskedText` column. ``MaskingGateway``
  replaces API key / OAuth token / GitHub PAT etc. fragments with
  ``<REDACTED:*>`` *before* the row hits SQLite, so neither raw SQL
  inspection nor backups can leak a CEO-pasted secret. **The
  irreversibility** of ``MaskingGateway`` means a round-trip through
  :class:`SqliteAgentRepository.find_by_id` returns a Persona whose
  ``prompt_body`` is the masked form (§確定 H 不可逆性凍結) —
  ``feature/llm-adapter`` carries the responsibility of detecting
  ``<REDACTED:*>`` markers before dispatching the prompt.
* No other column on this table is masked. The CI three-layer
  defense's *partial-mask* contract pins exactly one masked column
  here so a future PR cannot silently widen the masking surface
  (or inadvertently revert ``prompt_body`` to plain :class:`Text`).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UUIDStr,
)


class AgentRow(Base):
    """ORM mapping for the ``agents`` table."""

    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    empire_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("empires.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    archetype: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    prompt_body: Mapped[str] = mapped_column(MaskedText, nullable=False, default="")
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


__all__ = ["AgentRow"]
