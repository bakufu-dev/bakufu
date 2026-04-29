"""Add ``archived`` column to ``empires`` table (確定 I).

Adds the logical-delete flag required by UC-EM-010 / REQ-EM-HTTP-005
(``DELETE /api/empires/{id}`` → soft-delete).

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
    # SQLite does not support ALTER TABLE ... DROP COLUMN directly via Alembic
    # without batch mode — use batch_alter_table as specified in 確定 I.
    # See: https://alembic.sqlalchemy.org/en/latest/batch.html
    with op.batch_alter_table("empires") as batch_op:
        batch_op.drop_column("archived")
