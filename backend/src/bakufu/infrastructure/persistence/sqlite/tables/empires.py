"""``empires`` table — Empire Aggregate root row.

The Empire holds two scalar columns (``id`` / ``name``); reference
collections (``rooms`` / ``agents``) live in the side tables
:mod:`...tables.empire_room_refs` /
:mod:`...tables.empire_agent_refs` to keep the row width bounded and
the foreign-key cascade target obvious.

No ``Masked*`` TypeDecorator on any column: per
``docs/design/domain-model/storage.md`` §逆引き表 the Empire
schema carries no secret-bearing values. The CI three-layer defense
(grep guard + arch test + reverse-lookup table) registers this
explicit absence so a future PR cannot silently swap a column to a
secret-bearing semantic.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class EmpireRow(Base):
    """ORM mapping for the ``empires`` table."""

    __tablename__ = "empires"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")


__all__ = ["EmpireRow"]
