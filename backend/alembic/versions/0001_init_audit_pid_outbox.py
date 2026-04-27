"""Initial revision: audit_log + bakufu_pid_registry + domain_event_outbox.

Creates the three cross-cutting tables shared across every Aggregate,
the polling-optimized index on the Outbox, and the two SQLite triggers
that enforce ``audit_log`` immutability at the database layer
(Confirmation C — see ``docs/features/persistence-foundation/detailed-design/triggers.md``).

Revision ID: 0001_init
Revises:
Create Date: 2026-04-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("command", sa.String(64), nullable=False),
        sa.Column("args_json", sa.Text(), nullable=False),
        sa.Column("result", sa.String(16), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.Text(), nullable=False),
    )

    op.create_table(
        "bakufu_pid_registry",
        sa.Column("pid", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("parent_pid", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("cmd", sa.Text(), nullable=False),
        sa.Column("task_id", sa.CHAR(32), nullable=True),
        sa.Column("stage_id", sa.CHAR(32), nullable=True),
    )

    op.create_table(
        "domain_event_outbox",
        sa.Column("event_id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column("event_kind", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.CHAR(32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("next_attempt_at", sa.Text(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("dispatched_at", sa.Text(), nullable=True),
    )

    op.create_index(
        "ix_outbox_status_next_attempt",
        "domain_event_outbox",
        ["status", "next_attempt_at"],
    )

    # Trigger 1: forbid DELETE on audit_log (append-only).
    op.execute(
        "CREATE TRIGGER audit_log_no_delete "
        "BEFORE DELETE ON audit_log "
        "FOR EACH ROW BEGIN "
        "  SELECT RAISE(ABORT, 'audit_log is append-only'); "
        "END"
    )

    # Trigger 2: forbid UPDATE once `result` has been set.
    op.execute(
        "CREATE TRIGGER audit_log_update_restricted "
        "BEFORE UPDATE ON audit_log "
        "FOR EACH ROW WHEN OLD.result IS NOT NULL BEGIN "
        "  SELECT RAISE(ABORT, 'audit_log result is immutable once set'); "
        "END"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_update_restricted")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete")
    op.drop_index("ix_outbox_status_next_attempt", table_name="domain_event_outbox")
    op.drop_table("domain_event_outbox")
    op.drop_table("bakufu_pid_registry")
    op.drop_table("audit_log")
