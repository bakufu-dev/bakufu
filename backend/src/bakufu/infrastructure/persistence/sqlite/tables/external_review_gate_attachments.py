"""``external_review_gate_attachments`` テーブル — スナップショット Attachment 子行。

各 :class:`ExternalReviewGate` 内の ``deliverable_snapshot`` インライン コピー用
の attachment ごとのメタデータを保存する。物理ファイル バイトは本機能の範囲外
（``feature/attachment-storage`` の責務）。

``gate_id`` は ``external_review_gates.id`` への ``ON DELETE CASCADE`` 外部キーを
持つ — Gate が削除されるとそのスナップショット attachment 行も一緒に削除される。

``id`` は :meth:`SqliteExternalReviewGateRepository.save` 呼び出しごとに ``uuid4()``
で再生成される **保存内部** の主キー（DELETE-then-INSERT パターン）。外部コードは
この PK を参照してはならない。ビジネス キーは ``UNIQUE(gate_id, sha256)``。

**マスキング対象カラム**: なし（全カラム マスキング対象外）。Attachment メタ
データ（sha256 / filename / mime_type / size_bytes）は Schneier #6 のシークレット
意味を持たない。コンテンツ ハッシュはファイルを識別するが、その内容については
何も明かさない。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class ExternalReviewGateAttachmentRow(Base):
    """``external_review_gate_attachments`` テーブルの ORM マッピング。"""

    __tablename__ = "external_review_gate_attachments"

    # id: save() ごとに再生成される内部 PK。外部コードは UNIQUE(gate_id, sha256) を
    # ビジネス キーとして使うこと（§確定 R1-B）。
    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    gate_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("external_review_gates.id", ondelete="CASCADE"),
        nullable=False,
    )
    # sha256: 64 文字小文字 hex。Attachment VO で検証される。
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        # UNIQUE(gate_id, sha256): 1 つの Gate 内のコンテンツ重複を防ぐ。
        # sha256 は決定的な ORDER BY アンカーを提供する（§確定 R1-H）。
        UniqueConstraint("gate_id", "sha256", name="uq_erg_attachments_gate_sha256"),
    )


__all__ = ["ExternalReviewGateAttachmentRow"]
