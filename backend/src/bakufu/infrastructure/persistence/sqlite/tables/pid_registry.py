"""``bakufu_pid_registry`` テーブル（オーファン プロセス追跡）。

Bootstrap stage 4 がこのテーブルをスイープし、前回実行から残った claude /
codex 等のサブプロセスを kill する。``cmd`` カラムはシークレット
（``--api-key=sk-ant-...``）を含む CLI 引数を保持し得るため、マスキング
ゲートウェイは必須 — Schneier 申し送り #5 を参照。
シークレット カラムのマスキングは
:mod:`bakufu.infrastructure.persistence.sqlite.base` の :class:`MaskedText`
TypeDecorator で強制する。その ``process_bind_param`` フックは ORM の
``Session.add()`` と Core の ``insert(table).values(...)`` の両経路で発火する
ため、ゲートウェイは端から端まで尊重される（BUG-PF-001 修正、設計根拠は
``docs/features/persistence-foundation/requirements-analysis.md`` §確定 R1-D
を参照）。
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
    """``bakufu_pid_registry`` テーブルの ORM マッピング。

    ``cmd`` は :class:`MaskedText` を使うため、CLI フラグ（``--api-key=sk-ant-...``）
    内のシークレットがすべての永続化経路で伏字化される（BUG-PF-001 修正）。
    """

    __tablename__ = "bakufu_pid_registry"

    pid: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_pid: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    cmd: Mapped[str] = mapped_column(MaskedText, nullable=False)
    task_id: Mapped[UUID | None] = mapped_column(UUIDStr, nullable=True)
    stage_id: Mapped[UUID | None] = mapped_column(UUIDStr, nullable=True)


__all__ = ["PidRegistryRow"]
