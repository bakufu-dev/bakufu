"""``role_profiles`` テーブル — RoleProfile Aggregate ルート行。

RoleProfile は `deliverable_template_refs` を JSONEncoded カラムに集約する
（子テーブルなし、YAGNI）。

``empire_id`` は ``empires.id`` への外部キーを持ち、Empire 削除時に CASCADE する。
``UNIQUE(empire_id, role)`` 制約は業務ルール R1-D「同一 Empire 内で同 Role の
RoleProfile は 1 件のみ」を DB レベルで物理保証する（§確定 H）。

カラム別 masking ハンドリング（feature-spec §13 業務判断「機密レベル低」）:

* `deliverable_template_refs_json` は :class:`JSONEncoded` カラム。
  DeliverableTemplateRef は template_id（UUID）と minimum_version（SemVer）のみを
  保持し、Schneier §6 秘密情報 6 カテゴリに該当しない。
* 残りのカラムは UUIDStr / String を保持し、masking カテゴリには該当しない。

CI 三層防衛（REQ-DTR-006）: Layer 1 grep guard + Layer 2 arch test が本テーブルに
``Masked*`` TypeDecorator が存在しないことを物理保証する。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, JSONEncoded, UUIDStr


class RoleProfileRow(Base):
    """``role_profiles`` テーブルの ORM マッピング。"""

    __tablename__ = "role_profiles"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    # empires.id への FK（ON DELETE CASCADE）。
    # RoleProfile は Empire スコープ内に存在するため、Empire 削除時に連鎖削除する。
    empire_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("empires.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Role StrEnum 値（例: "DEVELOPER" / "REVIEWER"）。
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    # §確定 G: list[DeliverableTemplateRef] の JSON シリアライズ。
    # DEFAULT '[]' は 0012_deliverable_template_aggregate.py の server_default で強制。
    deliverable_template_refs_json: Mapped[Any] = mapped_column(JSONEncoded, nullable=False)

    __table_args__ = (
        # §確定 H: 同一 Empire 内で同 Role 値の RoleProfile は 1 件のみ（R1-D）。
        UniqueConstraint(
            "empire_id",
            "role",
            name="uq_role_profiles_empire_role",
        ),
    )


__all__ = ["RoleProfileRow"]
