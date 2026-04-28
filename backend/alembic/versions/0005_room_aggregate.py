"""Room Aggregate tables: rooms + room_members; empire_room_refs FK closure.

Adds the two tables that back :class:`SqliteRoomRepository`:

* ``rooms`` (id PK + empire_id FK CASCADE + workflow_id FK RESTRICT +
  5 scalar columns). The ``prompt_kit_prefix_markdown`` column is stored as
  ``TEXT`` here (Alembic does not know about ``MaskedText``); the masking
  gate lives on the Python side via the TypeDecorator.
* ``room_members`` (composite PK(room_id, agent_id, role) + FK CASCADE on
  room_id + UNIQUE(room_id, agent_id, role) for §確定 R1-D Defense-in-Depth
  + no FK on agent_id per room §確定).

Also closes BUG-EMR-001 FK closure:

* ``empire_room_refs.room_id → rooms.id`` FK (ON DELETE CASCADE) is added
  via ``op.batch_alter_table('empire_room_refs', recreate='always')`` because
  SQLite does not support ``ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY``
  directly. The batch operation rebuilds the table internally so all existing
  rows are preserved.

Per ``docs/features/empire-repository/detailed-design.md`` §確定 F each
subsequent ``feature/{aggregate}-repository`` PR appends its own revision;
this revision pins ``down_revision = "0004_agent_aggregate"`` strictly so the
chain check enforces a single head.

Revision ID: 0005_room_aggregate
Revises: 0004_agent_aggregate
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_room_aggregate"
down_revision: str | None = "0004_agent_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Step 1: rooms table (empire_id FK CASCADE + workflow_id FK RESTRICT).
    op.create_table(
        "rooms",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "empire_id",
            sa.CHAR(32),
            sa.ForeignKey("empires.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            sa.CHAR(32),
            sa.ForeignKey("workflows.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column(
            "description",
            sa.String(500),
            nullable=False,
            server_default=sa.text("''"),
        ),
        # MaskedText TypeDecorator serializes as TEXT in SQLite. The
        # Python-side decorator does the masking gate (base.py MaskedText).
        sa.Column(
            "prompt_kit_prefix_markdown",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # §確定 R1-F: non-UNIQUE composite index for Empire-scoped find_by_name.
    # Left-prefix optimises both ``WHERE empire_id = ?`` and
    # ``WHERE empire_id = ? AND name = ?`` queries.
    op.create_index(
        "ix_rooms_empire_id_name",
        "rooms",
        ["empire_id", "name"],
        unique=False,
    )

    # Step 2: room_members table (composite PK + FK CASCADE + UNIQUE §確定 R1-D).
    op.create_table(
        "room_members",
        sa.Column(
            "room_id",
            sa.CHAR(32),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            sa.CHAR(32),
            primary_key=True,
            nullable=False,
            # Intentionally no FK onto agents.id — application-layer
            # responsibility (room §確定, see detailed-design §設計判断補足).
        ),
        sa.Column(
            "role",
            sa.String(32),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        # §確定 R1-D: explicit UniqueConstraint in addition to composite PK so
        # CI Layer 2 arch test can assert constraint existence via
        # ``__table_args__`` scanning (agent_providers pattern).
        sa.UniqueConstraint(
            "room_id",
            "agent_id",
            "role",
            name="uq_room_members_triplet",
        ),
    )

    # Step 3: empire_room_refs FK closure (BUG-EMR-001 close).
    # SQLite does not support ``ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY``
    # directly. Alembic's ``batch_alter_table(recreate='always')`` rebuilds
    # the table internally, copying existing rows, then renames. The
    # ``recreate='always'`` flag forces the rebuild even when no column
    # changes are detected — necessary for FK addition in SQLite.
    with op.batch_alter_table("empire_room_refs", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            "fk_empire_room_refs_room_id",
            "rooms",
            ["room_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    # Reverse order: FK closure → index → child table → root table.
    with op.batch_alter_table("empire_room_refs", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_empire_room_refs_room_id", type_="foreignkey")

    op.drop_index("ix_rooms_empire_id_name", table_name="rooms")
    # Drop child table first (room_members.room_id FK CASCADE onto rooms.id).
    op.drop_table("room_members")
    op.drop_table("rooms")
