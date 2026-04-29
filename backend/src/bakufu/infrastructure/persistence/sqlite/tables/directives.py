"""``directives`` テーブル — Directive Aggregate ルート行。

Directive Aggregate の 5 個のスカラー カラムを保持する。Directive は子テーブルを
持たないフラットな Aggregate である — 全属性がこのテーブルの 1 行にマップされる。

``target_room_id`` は ``rooms.id`` への ``ON DELETE CASCADE`` 外部キーを持つ —
Room が削除されると関連 Directive も一緒に削除される。

``task_id`` は nullable で、このマイグレーション レベルでは **FK を持たない**。
``tasks.id`` がまだ存在しないため。FK の確定は task-repository PR で
``op.batch_alter_table('directives', recreate='always')`` により延期される
（§BUG-DRR-001 申し送り、0005_room_aggregate の BUG-EMR-001 と同パターン）。

``text`` は :class:`MaskedText` カラム（§確定 R1-E）。``MaskingGateway`` が、行が
SQLite に到達する *前* に埋め込まれた API キー / OAuth トークン / Discord webhook
シークレット等を ``<REDACTED:*>`` に置換する — DB ダンプ / SQL ログからのシークレット
漏洩を防ぐ。マスキングは不可逆。完全なコントラクトは
:mod:`...repositories.directive_repository` を参照。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class DirectiveRow(Base):
    """``directives`` テーブルの ORM マッピング。"""

    __tablename__ = "directives"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    text: Mapped[str] = mapped_column(MaskedText, nullable=False)
    target_room_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    # task_id は tasks.id への FK を意図的に持たない — このマイグレーション レベル
    # では tasks テーブルがまだ存在しない。FK の確定は task-repository PR で延期
    # される（§BUG-DRR-001 / BUG-EMR-001 パターン）。
    task_id: Mapped[UUID | None] = mapped_column(UUIDStr, nullable=True)

    __table_args__ = (
        # §確定 R1-D: Room スコープの find_by_room ルックアップ用の複合インデックス。
        # 左プレフィックスが ``WHERE target_room_id = ?`` を最適化し、完全な
        # ``WHERE target_room_id = ? ORDER BY created_at DESC`` クエリ形状にも
        # 効く。``id``（PK）はエンジン内で同点決着に使われる — 追加インデックス不要。
        Index("ix_directives_target_room_id_created_at", "target_room_id", "created_at"),
    )


__all__ = ["DirectiveRow"]
