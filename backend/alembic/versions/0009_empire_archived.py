"""``empires`` テーブルに ``archived`` カラムを追加（確定 I）。

UC-EM-010 / REQ-EM-HTTP-005（``DELETE /api/empires/{id}`` → 論理削除）が要求する
論理削除フラグを追加する。

Revision ID: 0009_empire_archived
Revises: 0008_external_review_gate_aggregate
Create Date: 2026-04-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_empire_archived"
down_revision: str | None = "0008_external_review_gate_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "empires",
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
    # 参照: https://alembic.sqlalchemy.org/en/latest/batch.html
    with op.batch_alter_table("empires") as batch_op:
        batch_op.drop_column("archived")
