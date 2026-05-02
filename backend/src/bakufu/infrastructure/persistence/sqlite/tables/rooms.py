"""``rooms`` テーブル — Room Aggregate ルート行。

Room Aggregate ルートの 7 個のスカラー カラムを保持する。メンバ コレクション
（``room_members``）はコンパニオン モジュール :mod:`...tables.room_members` に
置き、ルート行の幅を抑え CASCADE 対象を明確にする。

``empire_id`` は ``empires.id`` への ``ON DELETE CASCADE`` 外部キーを持つ —
Empire が削除されると Room も一緒に削除される。

``workflow_id`` は ``workflows.id`` への ``ON DELETE RESTRICT`` 外部キーを持つ —
Workflow は所有者ではなく参照対象であるため、Room がまだ参照している状態で
Workflow を削除しようとすると hard failure する（§確定 R1-I: アプリケーション層
チェックと並ぶ多層防御）。

``name`` は意図的に DB レベルで UNIQUE として **宣言しない**。「Empire 内で名前
一意」の不変条件は :meth:`RoomRepository.find_by_name` 経由でアプリケーション層
が強制する（agent §R1-B と同じロジック）。これにより、``IntegrityError`` に
先取りされず、MSG-RM-NNN 文言がアプリケーション層の声で出る。

``prompt_kit_prefix_markdown`` は :class:`MaskedText` カラム（room §確定 G 実適用）。
``MaskingGateway`` が、行が SQLite に到達する *前* に埋め込まれた API キー /
OAuth トークン / Discord webhook シークレット等を ``<REDACTED:*>`` に置換する —
DB ダンプ / SQL ログのシークレット漏洩を防ぐ。マスキングは不可逆。完全な
コントラクトは §確定 R1-J および :mod:`...repositories.room_repository` を参照。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UUIDStr,
)


class RoomRow(Base):
    """``rooms`` テーブルの ORM マッピング。"""

    __tablename__ = "rooms"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    empire_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("empires.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_id: Mapped[UUID | None] = mapped_column(
        UUIDStr,
        ForeignKey("workflows.id", ondelete="RESTRICT"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    prompt_kit_prefix_markdown: Mapped[str] = mapped_column(MaskedText, nullable=False, default="")
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        # §確定 R1-F: Empire スコープの find_by_name ルックアップ用の非 UNIQUE
        # 複合インデックス。左プレフィックスが ``WHERE empire_id = ?`` と
        # ``WHERE empire_id = ? AND name = ?`` の両方のクエリを最適化する。
        Index("ix_rooms_empire_id_name", "empire_id", "name", unique=False),
    )


__all__ = ["RoomRow"]
