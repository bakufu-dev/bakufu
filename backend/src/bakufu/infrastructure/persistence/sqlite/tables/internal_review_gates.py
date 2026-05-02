"""``internal_review_gates`` テーブル — InternalReviewGate Aggregate ルート行。

InternalReviewGate Aggregate ルートのスカラー カラムを保持する。子コレクション
（verdicts）はコンパニオン モジュール
(:mod:`bakufu.infrastructure.persistence.sqlite.tables.internal_review_gate_verdicts`)
に置き、ルート行の幅を抑え CASCADE 対象を明確にする。

``task_id`` および ``stage_id`` は **FK を持たない**（Aggregate 境界保護）:

- ``task_id``: Task Aggregate 境界。Gate は tasks に直接依存してはならない
  （gate-repository §設計決定 IRGR-001）。
- ``stage_id``: Workflow Aggregate 境界。Gate は workflow_stages に直接依存して
  はならない（§設計決定 IRGR-001）。

``required_gate_roles`` は ``frozenset`` を JSON 配列として保存する（JSONEncoded）。
``gate_decision`` は ``GateDecision`` StrEnum 値（PENDING / APPROVED / REJECTED）で
デフォルト ``'PENDING'``。

2 つのインデックス（§確定E クエリ最適化）:

* ``ix_internal_review_gates_task_id_stage_id`` — 複合 ``(task_id, stage_id)``。
  ``find_by_task_and_stage`` の WHERE task_id + stage_id + gate_decision='PENDING'
  フィルタを最適化する。
* ``ix_internal_review_gates_task_id`` — 単一カラム ``(task_id)``。
  ``find_all_by_task_id`` の WHERE task_id + ORDER BY created_at ASC を最適化する。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, JSONEncoded, UTCDateTime, UUIDStr


class InternalReviewGateRow(Base):
    """``internal_review_gates`` テーブルの ORM マッピング。"""

    __tablename__ = "internal_review_gates"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    # task_id: Task Aggregate 境界 — FK なし（§設計決定 IRGR-001）。
    task_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # stage_id: Workflow Aggregate 境界 — FK なし（§設計決定 IRGR-001）。
    stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # required_gate_roles: frozenset[GateRole] を JSON 配列として保存。
    # JSONEncoded が sort_keys=True で serialize するため、等しい集合は
    # 行内でバイト等価になる。
    required_gate_roles: Mapped[Any] = mapped_column(JSONEncoded, nullable=False)
    # gate_decision: GateDecision StrEnum 値（PENDING / APPROVED / REJECTED）。
    # 新規 Gate 生成時のデフォルトは 'PENDING'。
    gate_decision: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    # ---- ライフサイクル タイムスタンプ ----------------------------------------
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    __table_args__ = (
        # §確定E: find_by_task_and_stage 用の複合 (task_id, stage_id) インデックス。
        # WHERE task_id + stage_id + gate_decision='PENDING' フィルタを最適化する。
        Index(
            "ix_internal_review_gates_task_id_stage_id",
            "task_id",
            "stage_id",
        ),
        # §確定E: find_all_by_task_id 用の単一カラム (task_id) インデックス。
        # WHERE task_id + ORDER BY created_at ASC を最適化する。
        Index("ix_internal_review_gates_task_id", "task_id"),
    )


__all__ = ["InternalReviewGateRow"]
