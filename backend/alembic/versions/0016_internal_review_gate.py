"""internal_review_gates / internal_review_gate_verdicts テーブル追加（Issue #164）。

InternalReviewGate 集約の内部（エージェント間）レビュー ゲートを永続化する
2 テーブルを追加する:

1. ``internal_review_gates`` — InternalReviewGate ルート行。
   ``required_gate_roles`` は JSON 配列（frozenset スナップショット）。
   ``gate_decision`` は PENDING / APPROVED / REJECTED（デフォルト 'PENDING'）。
   FK なし（Aggregate 境界保護: task_id / stage_id は FK を張らない）。
   2 つのインデックス: (task_id, stage_id) 複合 / task_id 単一。

2. ``internal_review_gate_verdicts`` — Verdict 子行。
   ``gate_id`` は ``internal_review_gates.id`` への FK（ON DELETE CASCADE）。
   ``comment`` は MaskedText 適用（Agent 出力に secret 混入の可能性）。
   ``agent_id`` は FK なし（Agent Aggregate 境界保護）。
   UNIQUE 制約 2 件: (gate_id, order_index) / (gate_id, role)。

Revision ID: 0016_internal_review_gate
Revises: 0015_deliverable_records
Create Date: 2026-05-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_internal_review_gate"
down_revision: str | None = "0015_deliverable_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # internal_review_gates テーブル作成（子テーブルより先に作成する FK 順序）。
    op.create_table(
        "internal_review_gates",
        # PK: InternalGateId（UUID v4 文字列）。
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        # task_id: Task Aggregate 境界 — FK なし（§設計決定 IRGR-001）。
        sa.Column("task_id", sa.String(36), nullable=False),
        # stage_id: Workflow Aggregate 境界 — FK なし（§設計決定 IRGR-001）。
        sa.Column("stage_id", sa.String(36), nullable=False),
        # required_gate_roles: frozenset[GateRole] を JSON 配列として保存。
        sa.Column("required_gate_roles", sa.Text, nullable=False),
        # gate_decision: GateDecision StrEnum 値（PENDING / APPROVED / REJECTED）。
        # 新規 Gate 生成時のデフォルトは 'PENDING'。
        sa.Column(
            "gate_decision",
            sa.String(20),
            nullable=False,
            server_default="PENDING",
        ),
        # created_at: Gate 生成時の UTC タイムスタンプ（ISO-8601 文字列）。
        sa.Column("created_at", sa.Text, nullable=False),
    )
    # §確定E: find_by_task_and_stage 用の複合 (task_id, stage_id) インデックス。
    op.create_index(
        "ix_internal_review_gates_task_id_stage_id",
        "internal_review_gates",
        ["task_id", "stage_id"],
    )
    # §確定E: find_all_by_task_id 用の単一カラム (task_id) インデックス。
    op.create_index(
        "ix_internal_review_gates_task_id",
        "internal_review_gates",
        ["task_id"],
    )

    # internal_review_gate_verdicts テーブル作成（internal_review_gates の後）。
    op.create_table(
        "internal_review_gate_verdicts",
        # PK: 保存ごとに uuid4() で再生成（DELETE-then-INSERT パターン）。
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        # gate_id: internal_review_gates.id への FK（ON DELETE CASCADE）。
        sa.Column(
            "gate_id",
            sa.String(36),
            sa.ForeignKey("internal_review_gates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # order_index: 元の tuple 順序を保持（enumerate で付与、0-based）。
        sa.Column("order_index", sa.Integer, nullable=False),
        # role: GateRole 値（String 表現）。1 Gate につき同一ロールは高々 1 件。
        sa.Column("role", sa.String(40), nullable=False),
        # agent_id: Agent Aggregate 境界 — FK なし（§設計決定 TR-001 / ERGR-001）。
        sa.Column("agent_id", sa.String(36), nullable=False),
        # decision: VerdictDecision 値（APPROVE / REJECT）。
        sa.Column("decision", sa.String(10), nullable=False),
        # comment: MaskedText 適用（Agent 出力に secret 混入の可能性）。
        sa.Column("comment", sa.Text, nullable=False),
        # decided_at: Verdict 提出時の UTC タイムスタンプ（ISO-8601 文字列）。
        sa.Column("decided_at", sa.Text, nullable=False),
        # UNIQUE 制約: (gate_id, order_index) の一意性。
        sa.UniqueConstraint("gate_id", "order_index", name="uq_irg_verdicts_gate_order"),
        # UNIQUE 制約: (gate_id, role) の一意性 — 1 Gate につき同一ロールは高々 1 件。
        sa.UniqueConstraint("gate_id", "role", name="uq_irg_verdicts_gate_role"),
    )


def downgrade() -> None:
    # 子テーブルから先に DROP する（FK 逆順）。
    op.drop_table("internal_review_gate_verdicts")

    op.drop_index(
        "ix_internal_review_gates_task_id",
        table_name="internal_review_gates",
    )
    op.drop_index(
        "ix_internal_review_gates_task_id_stage_id",
        table_name="internal_review_gates",
    )
    op.drop_table("internal_review_gates")
