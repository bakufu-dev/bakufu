"""``deliverable_records`` テーブル — DeliverableRecord 集約ルート行。

LLM 受入基準評価の結果を保持する Aggregate の永続化。

``content`` カラムは ``MaskedText`` 適用（Agent 出力に secret 混入の可能性）。
DeliverableRecord は Agent が生成した成果物テキストを保持するため、
Schneier 申し送り #3 に準じてマスキングゲートを通す。
CI 三層防衛の *partial-mask* コントラクトに登録し、
``content`` のみ MaskedText であることを強制する。

``template_ref`` は ``DeliverableTemplateRef`` VO をインライン展開する
（template_ref_template_id / template_ref_version_major / _minor / _patch）。
DeliverableTemplate Aggregate 境界のため FK を持たない —
Template 削除 CASCADE が評価履歴スナップショットを破壊しないよう
（task-repository §設計決定 TR-001 / external_review_gates §設計決定 ERGR-001
と同論理）。

``deliverable_id`` は Task Deliverable 参照だが Task Aggregate 境界のため FK なし。
``task_id`` も同様（Task Aggregate 境界のためFK なし、§設計決定 TR-001）。
``produced_by`` は AgentId だが Agent Aggregate 境界のため FK なし。

3 つのインデックス（§確定 R1-K）:

* ``ix_deliverable_records_deliverable_id`` — 単一カラム ``(deliverable_id)``。
  ``find_by_deliverable_id`` の ``WHERE deliverable_id = :id ORDER BY created_at DESC``
  を最適化する。
* ``ix_deliverable_records_task_id`` — 単一カラム ``(task_id)``。
  タスク単位での評価一覧照会を最適化する。
* ``ix_deliverable_records_validation_status`` — 単一カラム ``(validation_status)``。
  ステータス別フィルタリングを最適化する。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class DeliverableRecordRow(Base):
    """``deliverable_records`` テーブルの ORM マッピング。"""

    __tablename__ = "deliverable_records"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    # deliverable_id: Task Aggregate 境界 — FK なし。
    # Task Deliverable の UUID を保持するが、Task 削除 CASCADE が
    # 評価履歴を破壊しないよう FK を張らない（§設計決定 TR-001）。
    deliverable_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # template_ref インライン展開（DeliverableTemplateRef VO）。
    # FK なし — Template 削除 CASCADE がスナップショットを破壊しないよう（§設計決定 ERGR-001）。
    template_ref_template_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    template_ref_version_major: Mapped[int] = mapped_column(Integer, nullable=False)
    template_ref_version_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    template_ref_version_patch: Mapped[int] = mapped_column(Integer, nullable=False)
    # content: MaskedText 適用（Agent 出力に secret 混入の可能性）。
    # MaskedText.process_bind_param がバインド時にシークレットを伏字化する。
    content: Mapped[str] = mapped_column(MaskedText, nullable=False)
    # task_id: Task Aggregate 境界 — FK なし（§設計決定 TR-001）。
    task_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # validation_status: ValidationStatus StrEnum 値（PENDING / PASSED / FAILED / UNCERTAIN）。
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False)
    # produced_by: nullable（業務シナリオ詳細は §確定 F 参照）。
    # Agent Aggregate 境界のため FK なし。
    produced_by: Mapped[UUID | None] = mapped_column(UUIDStr, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    # validated_at: PENDING 時は NULL。derive_status() 呼び出し後に UTC 日時をセット。
    validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    __table_args__ = (
        # §確定 R1-K: find_by_deliverable_id の WHERE + ORDER BY を最適化。
        Index("ix_deliverable_records_deliverable_id", "deliverable_id"),
        # §確定 R1-K: タスク単位での評価照会を最適化。
        Index("ix_deliverable_records_task_id", "task_id"),
        # §確定 R1-K: ステータス別フィルタリングを最適化。
        Index("ix_deliverable_records_validation_status", "validation_status"),
    )


__all__ = ["DeliverableRecordRow"]
