"""deliverable_records / criterion_validation_results テーブル追加（Issue #123）。

DeliverableRecord 集約の LLM 受入基準評価結果を永続化する 2 テーブルを追加する:

1. ``deliverable_records`` — DeliverableRecord ルート行。
   ``content`` は MaskedText 適用（Agent 出力に secret 混入の可能性）。
   3 つのインデックス: deliverable_id / task_id / validation_status。

2. ``criterion_validation_results`` — CriterionValidationResult 子行。
   ``deliverable_record_id`` は ``deliverable_records.id`` への FK（ON DELETE CASCADE）。
   masking 対象なし（ai-validation §確定 E 業務判定）。
   2 つのインデックス: deliverable_record_id / criterion_id。

Revision ID: 0015_deliverable_records
Revises: 0014_external_review_gate_criteria
Create Date: 2026-05-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_deliverable_records"
down_revision: str | None = "0014_external_review_gate_criteria"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # deliverable_records テーブル作成（子テーブルより先に作成する FK 順序）。
    op.create_table(
        "deliverable_records",
        # PK: DeliverableRecordId（UUID v4 文字列）。
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        # deliverable_id: Task Deliverable 参照 — FK なし（Task Aggregate 境界、§TR-001）。
        sa.Column("deliverable_id", sa.String(36), nullable=False),
        # template_ref インライン展開（DeliverableTemplateRef VO）。
        # FK なし — Template 削除 CASCADE がスナップショットを破壊しないよう（§ERGR-001）。
        sa.Column("template_ref_template_id", sa.String(36), nullable=False),
        sa.Column("template_ref_version_major", sa.Integer, nullable=False),
        sa.Column("template_ref_version_minor", sa.Integer, nullable=False),
        sa.Column("template_ref_version_patch", sa.Integer, nullable=False),
        # content: MaskedText 適用（Agent 出力に secret 混入の可能性）。
        sa.Column("content", sa.Text, nullable=False),
        # task_id: Task Aggregate 境界 — FK なし（§TR-001）。
        sa.Column("task_id", sa.String(36), nullable=False),
        # validation_status: ValidationStatus StrEnum 値（PENDING / PASSED / FAILED / UNCERTAIN）。
        sa.Column("validation_status", sa.String(20), nullable=False),
        # produced_by: nullable（業務シナリオは ai-validation §確定 F 参照）。
        # Agent Aggregate 境界のため FK なし。
        sa.Column("produced_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        # validated_at: PENDING 時は NULL。derive_status() 後に UTC 日時をセット。
        sa.Column("validated_at", sa.Text, nullable=True),
    )
    # §確定 R1-K: find_by_deliverable_id の WHERE + ORDER BY を最適化。
    op.create_index(
        "ix_deliverable_records_deliverable_id",
        "deliverable_records",
        ["deliverable_id"],
    )
    # §確定 R1-K: タスク単位での評価照会を最適化。
    op.create_index(
        "ix_deliverable_records_task_id",
        "deliverable_records",
        ["task_id"],
    )
    # §確定 R1-K: ステータス別フィルタリングを最適化。
    op.create_index(
        "ix_deliverable_records_validation_status",
        "deliverable_records",
        ["validation_status"],
    )

    # criterion_validation_results テーブル作成（deliverable_records の後）。
    op.create_table(
        "criterion_validation_results",
        # PK: 保存ごとに uuid4() で再生成（DELETE-then-INSERT パターン）。
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        # deliverable_record_id: deliverable_records.id への FK（ON DELETE CASCADE）。
        sa.Column(
            "deliverable_record_id",
            sa.String(36),
            sa.ForeignKey("deliverable_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # criterion_id: AcceptanceCriterion.id — FK なし（DeliverableTemplate Aggregate 境界）。
        sa.Column("criterion_id", sa.String(36), nullable=False),
        # status: ValidationStatus StrEnum 値（PASSED / FAILED / UNCERTAIN）。
        sa.Column("status", sa.String(20), nullable=False),
        # reason: LLM 評価根拠（0〜1000 文字）。masking 対象なし（業務判定済み）。
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
    )
    # §確定 R1-K: 子テーブル SELECT の WHERE deliverable_record_id = :id を最適化。
    op.create_index(
        "ix_criterion_validation_results_record_id",
        "criterion_validation_results",
        ["deliverable_record_id"],
    )
    # §確定 R1-K: criterion 単位での評価照会を最適化。
    op.create_index(
        "ix_criterion_validation_results_criterion_id",
        "criterion_validation_results",
        ["criterion_id"],
    )


def downgrade() -> None:
    # 子テーブルから先に DROP する（FK 逆順）。
    op.drop_index(
        "ix_criterion_validation_results_criterion_id",
        table_name="criterion_validation_results",
    )
    op.drop_index(
        "ix_criterion_validation_results_record_id",
        table_name="criterion_validation_results",
    )
    op.drop_table("criterion_validation_results")

    op.drop_index(
        "ix_deliverable_records_validation_status",
        table_name="deliverable_records",
    )
    op.drop_index(
        "ix_deliverable_records_task_id",
        table_name="deliverable_records",
    )
    op.drop_index(
        "ix_deliverable_records_deliverable_id",
        table_name="deliverable_records",
    )
    op.drop_table("deliverable_records")
