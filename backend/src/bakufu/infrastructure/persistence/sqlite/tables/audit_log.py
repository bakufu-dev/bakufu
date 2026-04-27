"""``audit_log`` table (append-only Admin CLI audit trail).

The DDL-level append-only contract (DELETE rejected, UPDATE limited
to NULL → value transitions on ``result`` / ``error_text``) is enforced
by the SQLite triggers from the initial Alembic revision; see
``alembic/versions/0001_init_audit_pid_outbox.py``. Secret-column
masking is enforced via :class:`MaskedJSONEncoded` /
:class:`MaskedText` TypeDecorators in
:mod:`bakufu.infrastructure.persistence.sqlite.base`. Their
``process_bind_param`` hooks fire for both ORM ``Session.add()`` and
Core ``insert(table).values(...)`` paths (BUG-PF-001 fix; see
``docs/features/persistence-foundation/requirements-analysis.md``
§確定 R1-D for the design rationale).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedJSONEncoded,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class AuditLogRow(Base):
    """ORM mapping for the append-only ``audit_log`` table.

    ``args_json`` and ``error_text`` use the ``Masked*`` column types
    so every bind value passes through the masking gateway regardless
    of whether the row arrives via ORM ``Session.add`` or Core
    ``session.execute(insert(...).values(...))`` (BUG-PF-001 fix).
    """

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    command: Mapped[str] = mapped_column(String(64), nullable=False)
    args_json: Mapped[Any] = mapped_column(MaskedJSONEncoded, nullable=False)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    error_text: Mapped[str | None] = mapped_column(MaskedText, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


__all__ = ["AuditLogRow"]
