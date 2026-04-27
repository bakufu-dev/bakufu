"""``audit_log`` table (append-only Admin CLI audit trail).

The DDL-level append-only contract (DELETE rejected, UPDATE limited
to NULL → value transitions on ``result`` / ``error_text``) is enforced
by the SQLite triggers from the initial Alembic revision; see
``alembic/versions/0001_init_audit_pid_outbox.py``. This file holds the
ORM mapping plus the masking listeners that ensure ``args_json`` /
``error_text`` are redacted *before* they hit the row.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import String, event
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    JSONEncoded,
    UTCDateTime,
    UUIDStr,
)
from bakufu.infrastructure.security.masking import (
    REDACT_LISTENER_ERROR,
    mask,
    mask_in,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection
    from sqlalchemy.orm import Mapper

logger = logging.getLogger(__name__)


class AuditLogRow(Base):
    """ORM mapping for the append-only ``audit_log`` table."""

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    command: Mapped[str] = mapped_column(String(64), nullable=False)
    args_json: Mapped[Any] = mapped_column(JSONEncoded, nullable=False)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    error_text: Mapped[str | None] = mapped_column(nullable=True)
    executed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


def _apply_masking(target: AuditLogRow) -> None:
    """Redact secret-bearing columns via the masking gateway.

    Confirmation F (Fail-Secure): if the gateway itself raises, replace
    the *entire* column with the listener-error sentinel rather than
    letting raw bytes hit the disk.
    """
    try:
        target.args_json = mask_in(target.args_json)
        if target.error_text is not None:
            target.error_text = mask(target.error_text)
    except Exception as exc:  # pragma: no cover — Fail-Secure
        logger.error(
            "[ERROR] audit_log masking listener failed: %r — replacing "
            "secret-bearing fields with %s",
            exc,
            REDACT_LISTENER_ERROR,
        )
        target.args_json = REDACT_LISTENER_ERROR
        target.error_text = REDACT_LISTENER_ERROR


def _before_insert(
    _mapper: Mapper[AuditLogRow],
    _connection: Connection,
    target: AuditLogRow,
) -> None:
    _apply_masking(target)


def _before_update(
    _mapper: Mapper[AuditLogRow],
    _connection: Connection,
    target: AuditLogRow,
) -> None:
    _apply_masking(target)


# Register at import time so the listeners activate before any session
# touches the table. ``event.listen`` is preferred over the decorator
# form because SQLAlchemy's decorator type stubs trigger pyright-strict
# `reportUntypedFunctionDecorator` warnings that obscure real issues.
event.listen(AuditLogRow, "before_insert", _before_insert)
event.listen(AuditLogRow, "before_update", _before_update)


__all__ = ["AuditLogRow"]
