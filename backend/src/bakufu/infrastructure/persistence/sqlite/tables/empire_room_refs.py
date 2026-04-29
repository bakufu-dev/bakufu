"""``empire_room_refs`` テーブル — Empire ↔ Room 関係行。

:class:`bakufu.domain.value_objects.RoomRef` の値を Empire Aggregate の関連
テーブルとして保存する。``room_id`` は ``rooms.id`` への外部キーを **意図的に
持たない**。``rooms`` テーブルは ``feature/room-repository``（別 PR）で投入される
ため。将来のマイグレーションが対象テーブル存在後に
``op.create_foreign_key(...)`` 経由で FK 制約を追加する。

カスケード: Empire 行を削除すると、その room 参照行も一緒に削除される
（``ON DELETE CASCADE``）。``UNIQUE(empire_id, room_id)`` インデックスは Aggregate
Root の ``Empire`` の ``rooms`` 不変条件をミラーする行レベル一意性コントラクト。

``Masked*`` TypeDecorator は付けない: :mod:`...tables.empires` および storage.md
§逆引き表 の明示的な「マスキング対象なし」エントリを参照。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class EmpireRoomRefRow(Base):
    """``empire_room_refs`` テーブルの ORM マッピング。"""

    __tablename__ = "empire_room_refs"

    empire_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("empires.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    room_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint("empire_id", "room_id", name="uq_empire_room_refs_pair"),)


__all__ = ["EmpireRoomRefRow"]
