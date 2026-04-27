"""Workflow Aggregate tables: workflows + workflow_stages + workflow_transitions.

Adds the three tables that back :class:`SqliteWorkflowRepository`:

* ``workflows`` (id PK + name + entry_stage_id, **no FK** on entry_stage_id
  per ``docs/features/workflow-repository/detailed-design.md`` §確定 J).
* ``workflow_stages`` (FK CASCADE on workflow_id, UNIQUE pair) — the
  ``notify_channels_json`` column carries Discord webhook URLs and is
  declared with the :class:`MaskedJSONEncoded` TypeDecorator at the ORM
  level (Alembic stores it as ``TEXT`` here; the masking gate lives on
  the Python side).
* ``workflow_transitions`` (FK CASCADE on workflow_id, UNIQUE pair).

Per ``docs/features/empire-repository/detailed-design.md`` §確定 F, each
subsequent ``feature/{aggregate}-repository`` PR appends its own
revision (``0004_agent_aggregate``, …) on top of this one so the
Alembic chain stays linear; this revision pins ``down_revision =
"0002_empire_aggregate"`` strictly so the chain check enforces a single
head.

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
        # entry_stage_id intentionally has NO FK constraint — see
        # detailed-design §確定 J. The Aggregate invariant
        # ``_validate_entry_in_stages`` guards reference integrity.
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
        # JSONEncoded / MaskedJSONEncoded TypeDecorators serialize as
        # TEXT in SQLite. The Python-side decorator does the masking
        # gate (see infrastructure/persistence/sqlite/base.py).
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
        # from_stage_id / to_stage_id intentionally have NO FK
        # constraint — same circular-reference rationale as
        # workflows.entry_stage_id (detailed-design §確定 J).
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
    # Drop child tables first so the FK CASCADE doesn't trigger work
    # against an already-deleted parent.
    op.drop_table("workflow_transitions")
    op.drop_table("workflow_stages")
    op.drop_table("workflows")
