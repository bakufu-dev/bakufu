"""workflow_stages: deliverable_template 廃止 → required_deliverables_json 追加（Issue #117）。

Issue #117 で ``Stage.deliverable_template: str`` が廃止され、
``Stage.required_deliverables: tuple[DeliverableRequirement, ...]`` に移行する。

永続化スキーマの対応変更:

* ``workflow_stages.deliverable_template`` (TEXT NOT NULL DEFAULT '') を削除
* ``workflow_stages.required_deliverables_json`` (TEXT NOT NULL DEFAULT '[]') を追加

§確定 L（``docs/features/workflow/repository/detailed-design.md``）に従い、
SQLite 3.35.0+ で利用可能な ``DROP COLUMN`` を使用する。
``pyproject.toml`` の ``requires-python = ">=3.12"`` により Python 3.12 同梱
SQLite は 3.42.0 以上が保証されるため、追加要件なし。

MVP 時点で本番データなし → ``DEFAULT '[]'`` のみで充足（データ変換不要）。

Revision ID: 0011_stage_required_deliverables
Revises: 0010_workflow_archived
Create Date: 2026-04-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_stage_required_deliverables"
down_revision: str | None = "0010_workflow_archived"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # §確定 L: DROP → ADD の順序で単一トランザクション相当の変更を行う。
    op.drop_column("workflow_stages", "deliverable_template")
    op.add_column(
        "workflow_stages",
        sa.Column(
            "required_deliverables_json",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def downgrade() -> None:
    # required_deliverables_json を削除し deliverable_template を復元する。
    # 既存データ復元は不要（空文字 default で充足）。
    op.drop_column("workflow_stages", "required_deliverables_json")
    op.add_column(
        "workflow_stages",
        sa.Column(
            "deliverable_template",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
