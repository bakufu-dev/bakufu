"""``room_role_overrides`` テーブル — RoomRoleOverride VO 行 (Issue #120)。

Room スコープのロール別 DeliverableTemplate オーバーライド。
PK は ``(room_id, role)`` — 個別の id カラムは存在しない。

``room_id`` は ``rooms.id`` への外部キーを持ち、Room 削除時に CASCADE する。

カラム別 masking ハンドリング:
* ``deliverable_template_refs_json`` は JSONEncoded カラム。
  DeliverableTemplateRef は template_id（UUID）と minimum_version（SemVer）のみを
  保持し、Schneier §6 秘密情報 6 カテゴリに該当しない。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, JSONEncoded, UUIDStr


class RoomRoleOverrideRow(Base):
    """``room_role_overrides`` テーブルの ORM マッピング。"""

    __tablename__ = "room_role_overrides"

    # rooms.id への FK（ON DELETE CASCADE）。
    room_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Role StrEnum 値（例: "DEVELOPER" / "REVIEWER"）。
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    # list[DeliverableTemplateRef] の JSON シリアライズ。
    deliverable_template_refs_json: Mapped[Any] = mapped_column(JSONEncoded, nullable=False)
    # タイムスタンプ。
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("room_id", "role", name="pk_room_role_overrides"),)


__all__ = ["RoomRoleOverrideRow"]
