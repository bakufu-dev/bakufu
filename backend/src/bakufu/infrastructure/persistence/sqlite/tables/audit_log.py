"""``audit_log`` テーブル（追記専用 Admin CLI 監査証跡）。

DDL レベルの追記専用コントラクト（DELETE は拒否、UPDATE は ``result`` /
``error_text`` の NULL → 値遷移に限定）は最初の Alembic リビジョン由来の
SQLite トリガで強制する。``alembic/versions/0001_init_audit_pid_outbox.py``
を参照。シークレット カラムのマスキングは
:mod:`bakufu.infrastructure.persistence.sqlite.base` の :class:`MaskedJSONEncoded` /
:class:`MaskedText` TypeDecorator で強制する。それらの ``process_bind_param``
フックは ORM ``Session.add()`` と Core ``insert(table).values(...)`` の両経路で
発火する（BUG-PF-001 修正、設計根拠は
``docs/features/persistence-foundation/requirements-analysis.md`` §確定 R1-D
を参照）。
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
    """追記専用 ``audit_log`` テーブルの ORM マッピング。

    ``args_json`` と ``error_text`` は ``Masked*`` カラム型を使うため、行が ORM
    ``Session.add`` 経由で到達するか Core
    ``session.execute(insert(...).values(...))`` 経由で到達するかに関わらず、
    全バインド値がマスキング ゲートウェイを通る（BUG-PF-001 修正）。
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
