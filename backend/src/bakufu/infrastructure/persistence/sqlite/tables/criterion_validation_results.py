"""``criterion_validation_results`` テーブル — CriterionValidationResult 子行。

DeliverableRecord の LLM 評価結果を AcceptanceCriterion 単位で保持する子テーブル。

``deliverable_record_id`` は ``deliverable_records.id`` への
``ON DELETE CASCADE`` 外部キー — DeliverableRecord が削除されると
関連評価結果も一緒に削除される。

``criterion_id`` は AcceptanceCriterion.id（DeliverableTemplate Aggregate 境界）
のため **FK を持たない** — Template 削除 CASCADE が評価履歴スナップショットを
破壊しないよう（task-repository §設計決定 TR-001 / ERGR-001 と同論理）。

``masking 対象なし``（ai-validation §確定 E、SEC-1 解消）:
``reason`` は LLM が出力した評価根拠テキストであり、DeliverableRecord.content と
異なりエージェント生成の PII・シークレットは含まれないと業務判定済み。
CI 三層防衛 Layer 1/2 で過剰 masking を物理保証する。

2 つのインデックス（§確定 R1-K）:

* ``ix_criterion_validation_results_record_id`` — 単一カラム ``(deliverable_record_id)``。
  子テーブル SELECT の ``WHERE deliverable_record_id = :id`` を最適化する。
* ``ix_criterion_validation_results_criterion_id`` — 単一カラム ``(criterion_id)``。
  criterion 単位での評価照会を最適化する。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    UTCDateTime,
    UUIDStr,
)


class CriterionValidationResultRow(Base):
    """``criterion_validation_results`` テーブルの ORM マッピング。"""

    __tablename__ = "criterion_validation_results"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    deliverable_record_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("deliverable_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    # criterion_id: AcceptanceCriterion.id（DeliverableTemplate Aggregate 境界）— FK なし。
    # Template 削除 CASCADE が評価履歴スナップショットを破壊しないよう FK を張らない。
    criterion_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # status: ValidationStatus StrEnum 値（PASSED / FAILED / UNCERTAIN。PENDING は不可）。
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # reason: LLM が出力した評価根拠（0〜1000 文字）。masking 対象なし（業務判定済み）。
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # required: AcceptanceCriterion.required のスナップショット（§確定 R1-G）。
    # True の場合のみ DeliverableRecord.derive_status() の overall status 計算に使用。
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    __table_args__ = (
        # §確定 R1-K: 子テーブル SELECT の WHERE deliverable_record_id = :id を最適化。
        Index("ix_criterion_validation_results_record_id", "deliverable_record_id"),
        # §確定 R1-K: criterion 単位での評価照会を最適化。
        Index("ix_criterion_validation_results_criterion_id", "criterion_id"),
    )


__all__ = ["CriterionValidationResultRow"]
