"""``bakufu_pid_registry`` table (orphan-process tracking).

Bootstrap stage 4 sweeps this table to kill leftover claude/codex/etc.
subprocesses from a previous run. The ``cmd`` column may carry CLI
arguments containing secrets (``--api-key=sk-ant-...``) so the masking
listener is mandatory — see Schneier 申し送り #5.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Integer, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    UTCDateTime,
    UUIDStr,
)
from bakufu.infrastructure.security.masking import REDACT_LISTENER_ERROR, mask

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection
    from sqlalchemy.orm import Mapper

logger = logging.getLogger(__name__)


class PidRegistryRow(Base):
    """ORM mapping for the ``bakufu_pid_registry`` table."""

    __tablename__ = "bakufu_pid_registry"

    pid: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_pid: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    cmd: Mapped[str] = mapped_column(Text, nullable=False)
    task_id: Mapped[UUID | None] = mapped_column(UUIDStr, nullable=True)
    stage_id: Mapped[UUID | None] = mapped_column(UUIDStr, nullable=True)


def _apply_masking(target: PidRegistryRow) -> None:
    """Redact ``cmd`` (may contain CLI flags with secrets)."""
    try:
        target.cmd = mask(target.cmd)
    except Exception as exc:  # pragma: no cover — Fail-Secure
        logger.error(
            "[ERROR] bakufu_pid_registry masking listener failed: %r — "
            "replacing cmd with %s",
            exc,
            REDACT_LISTENER_ERROR,
        )
        target.cmd = REDACT_LISTENER_ERROR


def _before_insert(
    _mapper: Mapper[PidRegistryRow],
    _connection: Connection,
    target: PidRegistryRow,
) -> None:
    _apply_masking(target)


def _before_update(
    _mapper: Mapper[PidRegistryRow],
    _connection: Connection,
    target: PidRegistryRow,
) -> None:
    _apply_masking(target)


event.listen(PidRegistryRow, "before_insert", _before_insert)
event.listen(PidRegistryRow, "before_update", _before_update)


__all__ = ["PidRegistryRow"]
