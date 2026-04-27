"""``bakufu_pid_registry`` table (orphan-process tracking).

Bootstrap stage 4 sweeps this table to kill leftover claude/codex/etc.
subprocesses from a previous run. The ``cmd`` column may carry CLI
arguments containing secrets (``--api-key=sk-ant-...``) so the masking
gateway is mandatory — see Schneier 申し送り #5.
Secret-column masking is enforced via the :class:`MaskedText`
TypeDecorator in
:mod:`bakufu.infrastructure.persistence.sqlite.base`. Its
``process_bind_param`` hook fires for both ORM ``Session.add()`` and
Core ``insert(table).values(...)`` paths so the gateway is honored
end-to-end (BUG-PF-001 fix; see
``docs/features/persistence-foundation/requirements-analysis.md``
§確定 R1-D for the design rationale).
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
