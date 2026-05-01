"""external_review_gate_criteria テーブル追加（Issue #121）。

ExternalReviewGate の required_deliverable_criteria snapshot を永続化する
``external_review_gate_criteria`` テーブルを追加する。

Gate 生成時に Stage.required_deliverables から引き込んだ AcceptanceCriterion を
order_index 付きで保持する。``gate_id`` は ``external_review_gates.id`` への
FK（ON DELETE CASCADE）。``masking 対象なし``（§確定 R1-E、REQ-ERGR-009）。

Revision ID: 0014_external_review_gate_criteria
Revises: 0013_add_room_role_overrides
Create Date: 2026-05-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_external_review_gate_criteria"
down_revision: str | None = "0013_add_room_role_overrides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_review_gate_criteria",
        # PK: 保存ごとに uuid4() で再生成（DELETE-then-INSERT パターン）。
        # 外部参照禁止。ビジネスキーは UNIQUE(gate_id, order_index)。
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        # gate_id: external_review_gates.id への FK（ON DELETE CASCADE）。
        sa.Column(
            "gate_id",
            sa.String(36),
            sa.ForeignKey("external_review_gates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # criterion_id: AcceptanceCriterion.id（DeliverableTemplate Aggregate 境界
        # のため FK なし — Template 削除 CASCADE が snapshot を破壊しないよう）。
        sa.Column("criterion_id", sa.String(36), nullable=False),
        # description: masking 不要（deliverable-template §13 機密レベル「低」業務判定）。
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("required", sa.Boolean, nullable=False, server_default=sa.true()),
        # order_index: 元の tuple 順序を保持（0-based、enumerate で付与）。
        sa.Column("order_index", sa.Integer, nullable=False),
        # UNIQUE(gate_id, order_index): 同一 Gate 内での order_index 重複禁止。
        sa.UniqueConstraint(
            "gate_id", "order_index", name="uq_external_review_gate_criteria_order"
        ),
    )
    # §確定 R1-K: 子テーブル SELECT の WHERE gate_id = :id を最適化。
    op.create_index(
        "ix_external_review_gate_criteria_gate_id",
        "external_review_gate_criteria",
        ["gate_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_review_gate_criteria_gate_id", table_name="external_review_gate_criteria"
    )
    op.drop_table("external_review_gate_criteria")
