"""``internal_review_gate_verdicts`` テーブル — InternalReviewGate の Verdict 子行。

Gate が保持するロール別 :class:`Verdict` のスナップショットを保持する。
``verdicts`` タプルは Gate 生成後も追記可能だが、既存 Verdict は不変
（``_validate_verdicts_immutable`` が強制）。

``gate_id`` は ``internal_review_gates.id`` への ``ON DELETE CASCADE`` 外部キーを持つ —
Gate が削除されると関連する Verdict も一緒に削除される。

``agent_id`` は Agent Aggregate 境界のため **FK を持たない**:
Agent 削除に CASCADE が伴うと監査凍結された Verdict を破壊してしまう
（task-repository §設計決定 TR-001 / external_review_gates §設計決定 ERGR-001 と同論理）。

``comment`` は MaskedText 適用 — Agent が書くレビュー コメントには
コード ブロック内に API キー / 認証トークンが埋め込まれることがある。

2 つの UNIQUE 制約:

* ``uq_irg_verdicts_gate_order`` — (gate_id, order_index) の一意性。
  Verdict タプルの順序位置が衝突しないことを DB レベルで保証する。
* ``uq_irg_verdicts_gate_role`` — (gate_id, role) の一意性。
  1 Gate につき同一ロールの Verdict は高々 1 件という不変条件を DB レベルで強制する。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, MaskedText, UTCDateTime, UUIDStr


class InternalReviewGateVerdictRow(Base):
    """``internal_review_gate_verdicts`` テーブルの ORM マッピング。"""

    __tablename__ = "internal_review_gate_verdicts"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    gate_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("internal_review_gates.id", ondelete="CASCADE"),
        nullable=False,
    )
    # order_index: 元の tuple 順序を保持（INSERT 時に enumerate で付与、0-based）。
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # role: GateRole 値（String 表現）。1 Gate につき同一ロールは高々 1 件。
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    # agent_id: Agent Aggregate 境界 — FK なし（§設計決定 TR-001 / ERGR-001）。
    # Agent 削除 CASCADE が監査凍結された Verdict を破壊しないよう FK を張らない。
    agent_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # decision: VerdictDecision 値（APPROVE / REJECT）。
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    # comment: MaskedText — Agent のレビュー コメント。LLM 出力にはシークレットが
    # 埋め込まれることがある（§確定 R1-E）。
    comment: Mapped[str] = mapped_column(MaskedText, nullable=False)
    # decided_at: Verdict 提出時の UTC タイムスタンプ。
    decided_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    __table_args__ = (
        # (gate_id, order_index) の一意性: Verdict タプルの順序位置衝突防止。
        UniqueConstraint("gate_id", "order_index", name="uq_irg_verdicts_gate_order"),
        # (gate_id, role) の一意性: 1 Gate につき同一ロールは高々 1 件。
        UniqueConstraint("gate_id", "role", name="uq_irg_verdicts_gate_role"),
    )


__all__ = ["InternalReviewGateVerdictRow"]
