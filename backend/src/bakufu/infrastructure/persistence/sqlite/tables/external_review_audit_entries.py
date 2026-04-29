"""``external_review_audit_entries`` テーブル — AuditEntry 子行。

各 :class:`ExternalReviewGate` の追記専用監査証跡を保存する。ドメイン Gate に対する
``approve`` / ``reject`` / ``cancel`` / ``record_view`` 呼び出しは厳密に 1 つの
:class:`AuditEntry` を追記する。リポジトリは §確定 R1-B の DELETE-then-INSERT
フローにより ``save()`` のたびに全エントリを永続化する。

``gate_id`` は ``external_review_gates.id`` への ``ON DELETE CASCADE`` 外部キーを
持つ — Gate が削除されると監査エントリも一緒に削除される。

``actor_id`` は意図的に **FK を持たない** — Owner Aggregate は M2 範囲では未実装
（§設計決定 ERGR-001）。参照整合性はアプリケーション層（``GateService``）の責務。

``id`` は :class:`AuditEntry.id`（ドメイン側で割り当てられた UUID）から直接取得し、
保存時に **再生成しない**。attachment 行（保存内部の PK を使う）とは異なり、監査
エントリは独自の安定 ID を持つため、リポジトリはドメインが生成した
:class:`AuditEntry` インスタンスを正確に再構築できる。

**マスキング対象カラム**: ``comment``（MaskedText） — ``feedback_text`` と同じ入力
経路を持つ CEO 著作の自由形式テキスト。webhook URL / API キーを持ち得る
（§確定 R1-E、3-column CI 防御）。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class ExternalReviewAuditEntryRow(Base):
    """``external_review_audit_entries`` テーブルの ORM マッピング。"""

    __tablename__ = "external_review_audit_entries"

    # id: AuditEntry.id から直接取得（ドメイン UUID、再生成しない）。
    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    gate_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("external_review_gates.id", ondelete="CASCADE"),
        nullable=False,
    )
    # actor_id: owners / agents への FK は意図的に持たない — Owner Aggregate は
    # 未実装（§設計決定 ERGR-001）。GateService が存在性を検証する。
    actor_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    # comment: MaskedText — approve/reject/cancel/view 入力経路を通る CEO 著作
    # テキスト。webhook URL / API キーを持ち得る（§確定 R1-E）。NOT NULL:
    # AuditEntry.comment は VIEWED エントリでは "" がデフォルト。
    comment: Mapped[str] = mapped_column(MaskedText, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


__all__ = ["ExternalReviewAuditEntryRow"]
