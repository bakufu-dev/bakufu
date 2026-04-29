"""``external_review_gates`` テーブル — ExternalReviewGate Aggregate ルート行。

ExternalReviewGate Aggregate ルートの 12 個全てのスカラー カラム（``snapshot_``
プレフィックスを持つ 4 カラムからなるインライン ``deliverable_snapshot`` コピー
を含む）を保持する。子コレクション（attachments / 監査エントリ）はコンパニオン
モジュールに置き、ルート行の幅を抑え CASCADE 対象を明確にする。

``task_id`` は ``tasks.id`` に対する ``ON DELETE CASCADE`` 外部キーを持つ —
Task が削除されると関連する Gate も一緒に削除される。

``stage_id``、``reviewer_id``、``snapshot_committed_by`` は意図的に **FK を持たない**
（§設計決定 ERGR-001）:
- ``stage_id``: Workflow Aggregate 境界。Gate は workflow_stages に直接依存して
  はならない。
- ``reviewer_id``: Owner Aggregate は未実装（M2 範囲）。
- ``snapshot_committed_by``: Agent 削除に CASCADE が伴うと監査凍結された
  スナップショットを破壊してしまう（task-repository §設計決定 TR-001 と同論理）。

2 つのマスキング カラム（§設計決定 ERGR-002、§確定 R1-E、3-column CI 防御）:

* ``feedback_text`` — MaskedText: CEO が書くレビュー コメント。``approve`` /
  ``reject`` / ``cancel`` の入力経路は Webhook URL / API キーを持ち得る。
* ``snapshot_body_markdown`` — MaskedText: Agent が書く成果物本体。LLM 出力には
  コード ブロック内に API キー / 認証トークンが埋め込まれることがある。

3 つのインデックス（§確定 R1-K）:

* ``ix_external_review_gates_task_id_created`` — 複合 ``(task_id, created_at)``。
  ``find_by_task_id`` の WHERE + ORDER BY を 1 回の B-tree スキャンで賄う。
* ``ix_external_review_gates_reviewer_decision`` — 複合
  ``(reviewer_id, decision)``。``find_pending_by_reviewer`` の WHERE
  reviewer_id + decision = 'PENDING' フィルタ用。
* ``ix_external_review_gates_decision`` — 単一カラム ``(decision)``。
  ``count_by_decision`` WHERE フィルタ用（上記複合インデックスのプレフィックス
  カバレッジは全件 COUNT(*) スキャンには不十分）。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class ExternalReviewGateRow(Base):
    """``external_review_gates`` テーブルの ORM マッピング。"""

    __tablename__ = "external_review_gates"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    # stage_id: workflow_stages.id への FK は意図的に持たない —
    # Aggregate 境界（§設計決定 ERGR-001）。GateService が存在性を検証する。
    stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # reviewer_id: 意図的に FK 無し — Owner Aggregate は未実装
    # （§設計決定 ERGR-001）。MVP: CEO = 固定 UUID を持つ単一システム所有者。
    reviewer_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    # feedback_text: MaskedText — CEO のレビュー コメント。approve / reject /
    # cancel の入力経路は Webhook URL / API キーを持ち得る（§設計決定 ERGR-002、
    # §確定 R1-E）。MaskedText.process_bind_param が SQLite 格納前にシークレットを
    # 伏字化する。NOT NULL: ドメインの Gate.feedback_text は PENDING で "" がデフォルト。
    feedback_text: Mapped[str] = mapped_column(MaskedText, nullable=False)
    # ---- インライン deliverable_snapshot コピー（§確定 R1-C） ---------------
    # snapshot_stage_id: workflow_stages.id への FK 無し — 上の stage_id と
    # 同じ理由（Aggregate 境界）。
    snapshot_stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # snapshot_body_markdown: MaskedText — Agent が書く成果物本体。LLM 出力には
    # コード ブロック内にシークレットが埋め込まれることがある（§確定 R1-E）。
    snapshot_body_markdown: Mapped[str] = mapped_column(MaskedText, nullable=False)
    # snapshot_committed_by: 意図的に agents.id への FK 無し —
    # CASCADE 付きの Agent 削除は監査凍結されたスナップショットを破壊してしまう
    # （§設計決定 ERGR-001、TR-001 と同論理）。
    snapshot_committed_by: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    snapshot_committed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    # ---- ライフサイクル タイムスタンプ ----------------------------------------
    # decided_at: decision == PENDING のときに限り NULL（ドメイン不変条件）。
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    __table_args__ = (
        # §確定 R1-K: find_by_task_id 用の複合 (task_id, created_at) インデックス。
        # WHERE task_id + ORDER BY created_at ASC を 1 回の B-tree スキャンでカバー。
        Index("ix_external_review_gates_task_id_created", "task_id", "created_at"),
        # §確定 R1-K: find_pending_by_reviewer 用の複合 (reviewer_id, decision)。
        # WHERE reviewer_id + decision = 'PENDING' を全件スキャン無しでカバー。
        Index(
            "ix_external_review_gates_reviewer_decision",
            "reviewer_id",
            "decision",
        ),
        # §確定 R1-K: count_by_decision 用の単一カラム (decision)。
        # 上の複合インデックスは全レビュアーにわたる COUNT(*) をカバーしない。
        Index("ix_external_review_gates_decision", "decision"),
    )


__all__ = ["ExternalReviewGateRow"]
