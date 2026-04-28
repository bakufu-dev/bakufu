"""Task Aggregate tables: tasks + 3 child tables; BUG-DRR-001 FK closure.

Adds the four tables that back :class:`SqliteTaskRepository`:

* ``tasks`` (id PK + room_id FK CASCADE + directive_id FK CASCADE +
  current_stage_id NOT NULL (no FK, Aggregate boundary §確定 R1-G) +
  status String(32) NOT NULL + last_error MaskedText NULL +
  created_at / updated_at UTCDateTime NOT NULL).
  Two indexes: ``ix_tasks_room_id`` (single-column) and
  ``ix_tasks_status_updated_id`` (composite, §確定 R1-K).
* ``task_assigned_agents`` (composite PK (task_id, agent_id) + FK CASCADE on
  task_id + NO FK on agent_id per §設計決定 TR-001 + UNIQUE(task_id, agent_id)
  Defense-in-Depth).
* ``deliverables`` (id PK + task_id FK CASCADE + stage_id NOT NULL (no FK,
  Aggregate boundary) + body_markdown MaskedText NOT NULL + committed_by
  NOT NULL (no FK) + committed_at UTCDateTime NOT NULL +
  UNIQUE(task_id, stage_id)).
* ``deliverable_attachments`` (id PK + deliverable_id FK CASCADE + sha256
  String(64) NOT NULL + filename String(255) NOT NULL + mime_type
  String(128) NOT NULL + size_bytes Integer NOT NULL +
  UNIQUE(deliverable_id, sha256)).

``conversations`` / ``conversation_messages`` tables are excluded (§BUG-TR-002
凍結済み): Task Aggregate currently has no ``conversations`` attribute. These
tables will be added in the future migration that wires up
``Task.conversations: list[Conversation]``.

Also closes BUG-DRR-001 FK申し送り:

* ``directives.task_id → tasks.id`` FK (ON DELETE RESTRICT) is added via
  ``op.batch_alter_table('directives', recreate='always')`` because SQLite
  does not support ``ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY`` directly.
  The batch operation rebuilds the table internally, copying existing rows,
  then renames. This is the same pattern as BUG-EMR-001 closure in
  0005_room_aggregate (empire-repository PR #47).

ON DELETE RESTRICT rationale: a Directive that references a Task must not
silently lose that reference when the Task is deleted. The application layer
must call ``directive.unlink_task()`` + ``save()`` before deleting a Task
(Fail Fast §確定 R1-C).

Per ``docs/features/task-repository/detailed-design.md`` §確定 R1-B,
§確定 R1-C, §確定 R1-K.

Revision ID: 0007_task_aggregate
Revises: 0006_directive_aggregate
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_task_aggregate"
down_revision: str | None = "0006_directive_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- tasks table -------------------------------------------------------
    op.create_table(
        "tasks",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "room_id",
            sa.CHAR(32),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "directive_id",
            sa.CHAR(32),
            sa.ForeignKey("directives.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # current_stage_id: intentionally NO FK onto workflow_stages.id —
        # Aggregate boundary (§確定 R1-G). TaskService validates existence.
        sa.Column("current_stage_id", sa.CHAR(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        # last_error: MaskedText serialises as TEXT. The Python-side TypeDecorator
        # does the masking gate (base.py MaskedText). NULL = not BLOCKED.
        sa.Column("last_error", sa.Text(), nullable=True),
        # UTCDateTime TypeDecorator stores ISO-8601 text; always tz-aware at Python.
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )

    # §確定 R1-K: single-column index for count_by_room WHERE filter.
    op.create_index("ix_tasks_room_id", "tasks", ["room_id"], unique=False)

    # §確定 R1-K: composite (status, updated_at, id) index.
    # Covers find_blocked WHERE status = 'BLOCKED' ORDER BY updated_at DESC, id DESC
    # and count_by_status WHERE status = ? in one B-tree scan.
    op.create_index(
        "ix_tasks_status_updated_id",
        "tasks",
        ["status", "updated_at", "id"],
        unique=False,
    )

    # ---- task_assigned_agents table ----------------------------------------
    op.create_table(
        "task_assigned_agents",
        sa.Column(
            "task_id",
            sa.CHAR(32),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        # agent_id: intentionally NO FK onto agents.id — Aggregate boundary
        # (§設計決定 TR-001, room_members.agent_id 前例同方針).
        sa.Column("agent_id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        # Defense-in-Depth: explicit UNIQUE mirrors Aggregate invariant
        # _validate_assigned_agents_unique at the DB level.
        sa.UniqueConstraint("task_id", "agent_id", name="uq_task_assigned_agents"),
    )

    # ---- deliverables table ------------------------------------------------
    op.create_table(
        "deliverables",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "task_id",
            sa.CHAR(32),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # stage_id: intentionally NO FK onto workflow_stages.id — Aggregate
        # boundary (§確定 R1-G, same rationale as tasks.current_stage_id).
        sa.Column("stage_id", sa.CHAR(32), nullable=False),
        # body_markdown: MaskedText serialises as TEXT (§確定 R1-E).
        sa.Column("body_markdown", sa.Text(), nullable=False),
        # committed_by: intentionally NO FK onto agents.id — Aggregate
        # boundary (§設計決定 TR-001, same as task_assigned_agents.agent_id).
        sa.Column("committed_by", sa.CHAR(32), nullable=False),
        # UTCDateTime TypeDecorator stores ISO-8601 text.
        sa.Column("committed_at", sa.Text(), nullable=False),
        # UNIQUE(task_id, stage_id): mirrors Aggregate's dict[StageId, Deliverable]
        # key-uniqueness invariant at the DB level.
        sa.UniqueConstraint("task_id", "stage_id", name="uq_deliverables_task_stage"),
    )

    # ---- deliverable_attachments table -------------------------------------
    op.create_table(
        "deliverable_attachments",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "deliverable_id",
            sa.CHAR(32),
            sa.ForeignKey("deliverables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # sha256: 64-char lowercase hex; validated by Attachment VO.
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        # UNIQUE(deliverable_id, sha256): prevents duplicate content within
        # one Deliverable; sha256 provides deterministic ORDER BY anchor.
        sa.UniqueConstraint(
            "deliverable_id",
            "sha256",
            name="uq_deliverable_attachments_sha256",
        ),
    )

    # ---- BUG-DRR-001 FK closure -------------------------------------------
    # ``directives.task_id → tasks.id`` FK (ON DELETE RESTRICT).
    # SQLite does not support ``ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY``
    # directly. Alembic's ``batch_alter_table(recreate='always')`` rebuilds
    # the table internally, copying existing rows, then renames.
    # The ``recreate='always'`` flag forces the rebuild even when no column
    # changes are detected — necessary for FK addition in SQLite
    # (same pattern as BUG-EMR-001 closure in 0005_room_aggregate).
    with op.batch_alter_table("directives", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            "fk_directives_task_id",
            "tasks",
            ["task_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    # Reverse order:
    # 1. Drop BUG-DRR-001 FK closure first (directives depends on tasks).
    with op.batch_alter_table("directives", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_directives_task_id", type_="foreignkey")

    # 2. Drop child tables (CASCADE dependency order: deepest first).
    op.drop_table("deliverable_attachments")

    # 3. Drop mid-level child tables.
    op.drop_table("deliverables")
    op.drop_table("task_assigned_agents")

    # 4. Drop indexes before dropping root table.
    op.drop_index("ix_tasks_status_updated_id", table_name="tasks")
    op.drop_index("ix_tasks_room_id", table_name="tasks")

    # 5. Drop root table.
    op.drop_table("tasks")
