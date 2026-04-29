"""``empires`` テーブル — Empire Aggregate ルート行。

Empire は 2 個のスカラー カラム（``id`` / ``name``）を保持する。参照コレクション
（``rooms`` / ``agents``）は :mod:`...tables.empire_room_refs` /
:mod:`...tables.empire_agent_refs` の関連テーブルに置き、行幅を抑え外部キー
カスケード対象を明確にする。

どのカラムにも ``Masked*`` TypeDecorator は付けない:
``docs/design/domain-model/storage.md`` §逆引き表 によれば、Empire スキーマは
シークレットを保持する値を持たない。CI 3 層防御（grep ガード + アーキ テスト
+ 逆引き表）はこの明示的な不在を登録するため、将来の PR がカラムをサイレントに
シークレット保持の意味へ置き換えることはできない。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class EmpireRow(Base):
    """``empires`` テーブルの ORM マッピング。"""

    __tablename__ = "empires"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")


__all__ = ["EmpireRow"]
