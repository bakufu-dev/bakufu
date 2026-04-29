"""Workflow Aggregate テーブル群: workflows + workflow_stages + workflow_transitions。

:class:`SqliteWorkflowRepository` を支える 3 つのテーブルを追加する:

* ``workflows``（id PK + name + entry_stage_id。entry_stage_id には
  ``docs/features/workflow-repository/detailed-design.md`` §確定 J に従い
  **FK を付けない**）。
* ``workflow_stages``（workflow_id に FK CASCADE、組で UNIQUE）—
  ``notify_channels_json`` カラムは Discord の Webhook URL を保持し、ORM 層では
  :class:`MaskedJSONEncoded` TypeDecorator として宣言される（Alembic 側では
  ``TEXT`` として保存し、マスキングゲートは Python 側に置く）。
* ``workflow_transitions``（workflow_id に FK CASCADE、組で UNIQUE）。

``docs/features/empire-repository/detailed-design.md`` §確定 F に従い、後続の
``feature/{aggregate}-repository`` PR は本 revision の上にそれぞれの revision
（``0004_agent_aggregate``、…）を積み重ね、Alembic チェーンを線形に保つ。本 revision は
``down_revision = "0002_empire_aggregate"`` を厳密に固定し、チェーン検査が単一 head
を強制するようにする。

Revision ID: 0003_workflow_aggregate
Revises: 0002_empire_aggregate
Create Date: 2026-04-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_workflow_aggregate"
down_revision: str | None = "0002_empire_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        # entry_stage_id には意図的に FK 制約を付けない — detailed-design §確定 J 参照。
        # 参照整合性は Aggregate 不変条件 ``_validate_entry_in_stages`` で守る。
        sa.Column("entry_stage_id", sa.CHAR(32), nullable=False),
    )

    op.create_table(
        "workflow_stages",
        sa.Column(
            "workflow_id",
            sa.CHAR(32),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("stage_id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("roles_csv", sa.String(255), nullable=False),
        sa.Column(
            "deliverable_template",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        # JSONEncoded / MaskedJSONEncoded TypeDecorator は SQLite では TEXT として
        # 直列化される。マスキングゲートは Python 側のデコレータで行う
        # （infrastructure/persistence/sqlite/base.py 参照）。
        sa.Column("completion_policy_json", sa.Text(), nullable=False),
        sa.Column(
            "notify_channels_json",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.UniqueConstraint(
            "workflow_id",
            "stage_id",
            name="uq_workflow_stages_pair",
        ),
    )

    op.create_table(
        "workflow_transitions",
        sa.Column(
            "workflow_id",
            sa.CHAR(32),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("transition_id", sa.CHAR(32), primary_key=True, nullable=False),
        # from_stage_id / to_stage_id には意図的に FK 制約を付けない —
        # workflows.entry_stage_id と同じ循環参照回避の理由による
        # （detailed-design §確定 J）。
        sa.Column("from_stage_id", sa.CHAR(32), nullable=False),
        sa.Column("to_stage_id", sa.CHAR(32), nullable=False),
        sa.Column("condition", sa.String(32), nullable=False),
        sa.Column(
            "label",
            sa.String(80),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.UniqueConstraint(
            "workflow_id",
            "transition_id",
            name="uq_workflow_transitions_pair",
        ),
    )


def downgrade() -> None:
    # 削除済みの親に対して FK CASCADE が発火しないよう、子テーブルから先に削除する。
    op.drop_table("workflow_transitions")
    op.drop_table("workflow_stages")
    op.drop_table("workflows")
