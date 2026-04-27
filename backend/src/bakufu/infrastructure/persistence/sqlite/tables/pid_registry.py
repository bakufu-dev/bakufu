"""``bakufu_pid_registry`` table (orphan-process tracking).

Bootstrap stage 4 sweeps this table to kill leftover claude/codex/etc.
subprocesses from a previous run. The ``cmd`` column may carry CLI
arguments containing secrets (``--api-key=sk-ant-...``) so the masking
gateway is mandatory — see Schneier 申し送り #5.
Secret-column masking is wired at the engine ``before_execute`` level
in :mod:`bakufu.infrastructure.persistence.sqlite.masking_listener`,
so both ORM and Core SQL paths route through the gateway (BUG-PF-001
fix).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class PidRegistryRow(Base):
    """ORM mapping for the ``bakufu_pid_registry`` table.

    ``cmd`` uses :class:`MaskedText` so secrets in CLI flags
    (``--api-key=sk-ant-...``) are redacted on every persist path
    (BUG-PF-001 fix).
    """

    __tablename__ = "bakufu_pid_registry"

    pid: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_pid: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    cmd: Mapped[str] = mapped_column(MaskedText, nullable=False)
    task_id: Mapped[UUID | None] = mapped_column(UUIDStr, nullable=True)
    stage_id: Mapped[UUID | None] = mapped_column(UUIDStr, nullable=True)


__all__ = ["PidRegistryRow"]
