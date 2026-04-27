"""``agent_providers`` table — Agent ↔ ProviderConfig child rows.

Stores :class:`bakufu.domain.agent.value_objects.ProviderConfig` values
as a side table of the Agent aggregate. ``ON DELETE CASCADE`` purges
provider rows when the parent Agent is deleted; UNIQUE(agent_id,
provider_kind) mirrors the
``_validate_provider_kind_unique`` aggregate invariant at the row
level.

The interesting constraint is the **partial unique index**
``WHERE is_default = 1`` — see
``docs/features/agent-repository/detailed-design.md`` §確定 G. This
gives the "exactly one default provider per Agent" invariant a
**Defense-in-Depth** floor: the Aggregate-level helper
``_validate_default_provider_count`` already enforces it, but if a
future PR introduces a corrupted SQL path (raw INSERT, hand-rolled
migration) the DB still refuses to host two ``is_default=1`` rows on
the same Agent. SQLite ships partial indexes natively
(https://www.sqlite.org/partialindex.html); the same construct ports
to PostgreSQL with identical syntax.

No ``Masked*`` TypeDecorator on any column. ``provider_kind`` is an
enum string, ``model`` is an LLM model identifier with no secret
semantics, and ``is_default`` is a boolean flag.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class AgentProviderRow(Base):
    """ORM mapping for the ``agent_providers`` table."""

    __tablename__ = "agent_providers"

    agent_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    provider_kind: Mapped[str] = mapped_column(String(32), primary_key=True, nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "provider_kind",
            name="uq_agent_providers_pair",
        ),
        # Partial unique index — at most one row per agent_id may have
        # ``is_default = 1``. SQLite / PostgreSQL syntax is the same.
        # detailed-design §確定 G: Defense-in-Depth alongside the
        # Aggregate-level ``_validate_default_provider_count`` check.
        Index(
            "uq_agent_providers_default",
            "agent_id",
            unique=True,
            sqlite_where=text("is_default = 1"),
        ),
    )


__all__ = ["AgentProviderRow"]
