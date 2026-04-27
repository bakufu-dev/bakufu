"""Empire Aggregate tables: empires + empire_room_refs + empire_agent_refs.

Adds the three tables that back :class:`SqliteEmpireRepository`:

* ``empires`` (id PK + name)
* ``empire_room_refs`` (FK CASCADE on empire_id, UNIQUE pair)
* ``empire_agent_refs`` (FK CASCADE on empire_id, UNIQUE pair)

Per ``docs/features/empire-repository/detailed-design.md`` §確定 F,
each subsequent ``feature/{aggregate}-repository`` PR appends its own
revision (``0003_workflow_aggregate``, ``0004_agent_aggregate``, …)
on top of this one so the Alembic chain stays linear.

Revision ID: 0002_empire_aggregate
Revises: 0001_init
Create Date: 2026-04-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_empire_aggregate"
down_revision: str | None = "0001_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "empires",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
    )

    op.create_table(
        "empire_room_refs",
        sa.Column(
            "empire_id",
            sa.CHAR(32),
            sa.ForeignKey("empires.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("room_id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint(
            "empire_id",
            "room_id",
            name="uq_empire_room_refs_pair",
        ),
    )

    op.create_table(
        "empire_agent_refs",
        sa.Column(
            "empire_id",
            sa.CHAR(32),
            sa.ForeignKey("empires.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("agent_id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.UniqueConstraint(
            "empire_id",
            "agent_id",
            name="uq_empire_agent_refs_pair",
        ),
    )


def downgrade() -> None:
    # Drop child tables first so the FK CASCADE doesn't trigger work
    # against an already-deleted parent.
    op.drop_table("empire_agent_refs")
    op.drop_table("empire_room_refs")
    op.drop_table("empires")
