"""``domain_event_outbox`` テーブル（Outbox パターン、§確定 K）。

Outbox はドメイン イベントの発行を外部副作用（Discord 通知、LLM Adapter 呼び出し
等）から疎結合化する。各行は Aggregate の振る舞いが生成した ``payload_json`` blob
を保持する。raw ペイロードは webhook URL、API キー、ファイルシステム パス等を
埋め込む可能性があるため、ディスクに到達する前に **必ず** 伏字化する。

シークレット カラムのマスキングは
:mod:`bakufu.infrastructure.persistence.sqlite.base` の :class:`MaskedJSONEncoded` /
:class:`MaskedText` TypeDecorator で強制される。それらの ``process_bind_param``
フックは ORM ``Session.add()`` フラッシュと Core
``session.execute(insert(table).values(...))`` 経路の両方で発火するため、
「raw SQL 経路もマスクされる」という約束（Confirmation B / Confirmation R1-D /
Schneier #6）が端から端まで尊重される（BUG-PF-001 修正、設計根拠は
``docs/features/persistence-foundation/requirements-analysis.md`` §確定 R1-D
を、物理回帰テストは TC-IT-PF-020 を参照）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedJSONEncoded,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class OutboxRow(Base):
    """``domain_event_outbox`` テーブルの ORM マッピング。

    ``payload_json`` と ``last_error`` は ``Masked*`` カラム型を使うため、行が ORM
    ``Session.add`` 経由で到達するか Core
    ``session.execute(insert(...).values(...))`` 経由で到達するかに関わらず、
    全バインド値がマスキング ゲートウェイを通る（BUG-PF-001 修正）。
    """

    __tablename__ = "domain_event_outbox"

    event_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    event_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    payload_json: Mapped[Any] = mapped_column(MaskedJSONEncoded, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    last_error: Mapped[str | None] = mapped_column(MaskedText, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    # ポーリング SQL フィルタ: `WHERE status = ? AND next_attempt_at <= ?`。
    __table_args__ = (Index("ix_outbox_status_next_attempt", "status", "next_attempt_at"),)


__all__ = ["OutboxRow"]
