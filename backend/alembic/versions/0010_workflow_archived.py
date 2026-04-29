"""``workflows`` テーブルに ``archived`` カラムを追加。

UC-WF-010 / REQ-WF-HTTP-005（``DELETE /api/workflows/{id}`` → 論理削除）が要求する
論理削除フラグを追加する。

Revision ID: 0010_workflow_archived
Revises: 0009_empire_archived
Create Date: 2026-04-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_workflow_archived"
down_revision: str | None = "0009_empire_archived"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    # SQLite は Alembic の通常モードでは ALTER TABLE ... DROP COLUMN を直接
    # サポートしない — 確定 I で指定された通り batch_alter_table を使う。
    with op.batch_alter_table("workflows") as batch_op:
        batch_op.drop_column("archived")
