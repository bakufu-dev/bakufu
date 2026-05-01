"""room_role_overrides テーブル追加（Issue #120）。

room-matching 機能: Room スコープのロール別 DeliverableTemplate オーバーライドを
永続化する ``room_role_overrides`` テーブルを追加する。

PK は (room_id, role) — 個別の id カラムは存在しない。
room_id は rooms.id への FK（ON DELETE CASCADE）。

Revision ID: 0013_add_room_role_overrides
Revises: 0012_deliverable_template_aggregate
Create Date: 2026-05-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_add_room_role_overrides"
down_revision: str | None = "0012_deliverable_template_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "room_role_overrides",
        # PK は (room_id, role) — id カラムなし。
        sa.Column("room_id", sa.CHAR(32), nullable=False),
        sa.Column("role", sa.VARCHAR(64), nullable=False),
        # list[DeliverableTemplateRef] の JSON シリアライズ（DEFAULT '[]'）。
        sa.Column(
            "deliverable_template_refs_json",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("room_id", "role"),
    )


def downgrade() -> None:
    op.drop_table("room_role_overrides")
