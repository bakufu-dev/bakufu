"""``deliverable_attachments`` テーブル — Deliverable 用 Attachment メタデータ。

各行は Deliverable に紐づく 1 つのファイル添付を表す。ここに保存されるのは
メタデータ（sha256 ハッシュ、ファイル名、MIME タイプ、サイズ）のみで、物理
ファイル バイトは別の ``feature/attachment-storage`` 機能が管理する
（§確定 R1-I メタデータのみの範囲）。

``deliverable_id`` は ``deliverables.id`` への ``ON DELETE CASCADE`` 外部キーを持つ
— Deliverable が削除されると、その attachment メタデータ行も一緒に削除される。

``UNIQUE(deliverable_id, sha256)`` は単一 Deliverable 内で同じファイル コンテンツ
の重複エントリを防ぐ。sha256 hex 文字列は決定的な ``ORDER BY sha256 ASC`` ソート
アンカーも提供するため、リポジトリ水和は attachment リストを安定順で再構築する
（§確定 R1-H）。

4 つのメタデータ カラムは全てドメイン層の :class:`bakufu.domain.value_objects.Attachment`
VO がリポジトリに到達する前に検証する。よって DB レベル制約は多層防御のみが目的。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class DeliverableAttachmentRow(Base):
    """``deliverable_attachments`` テーブルの ORM マッピング。"""

    __tablename__ = "deliverable_attachments"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    deliverable_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("deliverables.id", ondelete="CASCADE"),
        nullable=False,
    )
    # sha256: 64 文字の小文字 hex。Attachment VO で検証される。
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        # UNIQUE(deliverable_id, sha256): 単一 Deliverable 内の重複ファイル
        # コンテンツを防ぐ。決定的水和のため安定した ORDER BY sha256 ASC ソート
        # も提供する（§確定 R1-H）。
        UniqueConstraint("deliverable_id", "sha256", name="uq_deliverable_attachments_sha256"),
    )


__all__ = ["DeliverableAttachmentRow"]
