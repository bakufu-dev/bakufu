"""Directive Aggregate table: directives.

Adds the table that backs :class:`SqliteDirectiveRepository`:

* ``directives`` (id PK + text MaskedText NOT NULL + target_room_id FK CASCADE
  onto rooms.id + created_at DateTime NOT NULL + task_id nullable CHAR(32)
  with NO FK at this level — see §BUG-DRR-001 申し送り below).
* ``INDEX(target_room_id, created_at)`` composite index for Room-scoped
  ``find_by_room`` queries.

§BUG-DRR-001 FK申し送り:
``directives.task_id`` is declared as a nullable CHAR(32) at this revision.
The ``tasks.id`` FK will be closed in the task-repository PR via
``op.batch_alter_table('directives', recreate='always')`` (same pattern as
BUG-EMR-001 closure in 0005_room_aggregate, empire-repository PR #33).

ON DELETE RESTRICT is recommended for the deferred FK: a Directive is the
audit trail of an instruction; Task deletion should be blocked if a
Directive still references it.

Per ``docs/features/directive-repository/detailed-design.md`` §確定 R1-B
and §確定 R1-C.

Revision ID: 0006_directive_aggregate
Revises: 0005_room_aggregate
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_directive_aggregate"
down_revision: str | None = "0005_room_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # directives table: flat 5-column aggregate (no child tables).
    op.create_table(
        "directives",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        # MaskedText TypeDecorator serializes as TEXT in SQLite. The Python-side
        # decorator does the masking gate (base.py MaskedText). §確定 R1-E.
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "target_room_id",
            sa.CHAR(32),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # created_at uses Text storage (UTCDateTime TypeDecorator stores
        # ISO-8601 string). Always UTC-aware at the Python layer.
        sa.Column("created_at", sa.Text(), nullable=False),
        # task_id: nullable CHAR(32) with NO FK at this level — see §BUG-DRR-001.
        # The FK closure (fk_directives_task_id → tasks.id RESTRICT) is deferred
        # to the task-repository PR.
        sa.Column("task_id", sa.CHAR(32), nullable=True),
    )

    # §確定 R1-D: composite index for Room-scoped find_by_room query.
    # Left-prefix covers ``WHERE target_room_id = ?`` and
    # ``WHERE target_room_id = ? ORDER BY created_at DESC``.
    op.create_index(
        "ix_directives_target_room_id_created_at",
        "directives",
        ["target_room_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Reverse order: index first, then table.
    op.drop_index("ix_directives_target_room_id_created_at", table_name="directives")
    op.drop_table("directives")
