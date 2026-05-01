"""``external_review_gate_criteria`` テーブル — ExternalReviewGate の AcceptanceCriterion 子行。

Gate 生成時に Stage.required_deliverables から引き込んだ AcceptanceCriterion の
snapshot を保持する。``required_deliverable_criteria`` フィールドは §確定 D' により
Gate 生成後に不変（``_validate_criteria_immutable`` が強制）。

``gate_id`` は ``external_review_gates.id`` への ``ON DELETE CASCADE`` 外部キーを持つ —
Gate が削除されると関連する criteria も一緒に削除される。

``criterion_id`` は DeliverableTemplate Aggregate 境界のため **FK を持たない**:
DeliverableTemplate 削除に CASCADE が伴うと監査凍結されたスナップショットを破壊する
（task-repository §設計決定 TR-001 / external_review_gates §設計決定 ERGR-001 と同論理）。

``masking 対象なし``（§確定 R1-E、REQ-ERGR-009）: description は
deliverable-template/feature-spec.md §13 で機密レベル「低」と業務判定済み
（PR #137 acceptance_criteria_json 凍結と同一業務判断）。
CI 三層防衛 Layer 1/2 で過剰 masking を物理保証する。

1 つのインデックス（§確定 R1-K）:

* ``ix_external_review_gate_criteria_gate_id`` — 単一カラム ``(gate_id)``。
  子テーブル SELECT の ``WHERE gate_id = :id`` を最適化する。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    UUIDStr,
)


class ExternalReviewGateCriterionRow(Base):
    """``external_review_gate_criteria`` テーブルの ORM マッピング。"""

    __tablename__ = "external_review_gate_criteria"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    gate_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("external_review_gates.id", ondelete="CASCADE"),
        nullable=False,
    )
    # criterion_id: DeliverableTemplate Aggregate 境界 — FK なし。
    # AcceptanceCriterion.id（Issue #115 VO）の UUID を保持するが、
    # Template 削除 CASCADE が snapshot を破壊しないよう FK を張らない。
    criterion_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # description: masking 不要（deliverable-template/feature-spec.md §13 業務判定）。
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # order_index: 元の tuple 順序を保持（INSERT 時に enumerate で付与、0-based）。
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        # §確定 R1-K: 子テーブル SELECT の WHERE gate_id = :id 最適化。
        Index("ix_external_review_gate_criteria_gate_id", "gate_id"),
    )


__all__ = ["ExternalReviewGateCriterionRow"]
