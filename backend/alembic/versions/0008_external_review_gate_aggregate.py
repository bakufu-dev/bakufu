"""ExternalReviewGate Aggregate tables: 3 tables + 3 indexes.

Adds the three tables that back :class:`SqliteExternalReviewGateRepository`:

* ``external_review_gates`` (id PK + task_id FK CASCADE + stage_id NOT NULL
  (no FK, Aggregate boundary §設計決定 ERGR-001) + reviewer_id NOT NULL (no FK,
  Owner Aggregate M2 scope) + decision String(32) NOT NULL + feedback_text
  MaskedText NOT NULL + snapshot_stage_id NOT NULL (no FK) +
  snapshot_body_markdown MaskedText NOT NULL + snapshot_committed_by NOT NULL
  (no FK) + snapshot_committed_at UTCDateTime NOT NULL + created_at UTCDateTime
  NOT NULL + decided_at UTCDateTime NULL).
  Three indexes: ``ix_external_review_gates_task_id_created`` (composite),
  ``ix_external_review_gates_reviewer_decision`` (composite),
  ``ix_external_review_gates_decision`` (single-column).

* ``external_review_gate_attachments`` (id PK (save-internal, uuid4() per save)
  + gate_id FK CASCADE + sha256 String(64) NOT NULL + filename String(255)
  NOT NULL + mime_type String(128) NOT NULL + size_bytes Integer NOT NULL +
  UNIQUE(gate_id, sha256)).

* ``external_review_audit_entries`` (id PK (domain AuditEntry.id) + gate_id
  FK CASCADE + actor_id NOT NULL (no FK, Owner Aggregate boundary) +
  action String(32) NOT NULL + comment MaskedText NOT NULL + occurred_at
  UTCDateTime NOT NULL).

``external_review_gates.task_id → tasks.id`` ON DELETE CASCADE: when a Task
is removed, its associated Gates go with it. This is the only inter-Aggregate
FK (§設計決定 ERGR-001 — all other UUID references are boundary-crossing and
intentionally FK-free).

``stage_id``, ``reviewer_id``, ``snapshot_stage_id``, ``snapshot_committed_by``,
and ``actor_id`` intentionally have **no FK** (§設計決定 ERGR-001):
- Stage / Workflow Aggregate boundary (Gate must not depend on
  workflow_stages).
- Owner Aggregate not yet implemented (M2 scope; MVP uses fixed UUID).
- snapshot_committed_by: Agent deletion with CASCADE would destroy the
  audit-frozen snapshot (task-repository §設計決定 TR-001 同論理).
- actor_id: Owner Aggregate same as reviewer_id rationale.

No inter-Aggregate FK申し送り is added: §設計決定 ERGR-001 resolves this as
a permanent design decision (not a BUG申し送り).

Per ``docs/features/external-review-gate-repository/detailed-design.md``
§確定 R1-B, §設計決定 ERGR-001, §確定 R1-K.

Revision ID: 0008_external_review_gate_aggregate
Revises: 0007_task_aggregate
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_external_review_gate_aggregate"
down_revision: str | None = "0007_task_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- external_review_gates table ----------------------------------------
    op.create_table(
        "external_review_gates",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "task_id",
            sa.CHAR(32),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # stage_id: intentionally NO FK onto workflow_stages.id —
        # Aggregate boundary (§設計決定 ERGR-001). GateService validates existence.
        sa.Column("stage_id", sa.CHAR(32), nullable=False),
        # reviewer_id: intentionally NO FK — Owner Aggregate not yet implemented
        # (§設計決定 ERGR-001). MVP: CEO = single system owner with fixed UUID.
        sa.Column("reviewer_id", sa.CHAR(32), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        # feedback_text: MaskedText serialises as TEXT (§設計決定 ERGR-002,
        # §確定 R1-E). CEO review comment; can carry webhook URLs / API keys.
        sa.Column("feedback_text", sa.Text(), nullable=False),
        # Inline snapshot_* columns — immutable after Gate creation (§確定 D).
        # snapshot_stage_id: NO FK onto workflow_stages.id — Aggregate boundary.
        sa.Column("snapshot_stage_id", sa.CHAR(32), nullable=False),
        # snapshot_body_markdown: MaskedText serialises as TEXT (§確定 R1-E).
        # Agent-authored deliverable body; LLM output may contain secrets.
        sa.Column("snapshot_body_markdown", sa.Text(), nullable=False),
        # snapshot_committed_by: NO FK onto agents.id — Agent deletion with
        # CASCADE would destroy audit-frozen snapshot (§設計決定 ERGR-001).
        sa.Column("snapshot_committed_by", sa.CHAR(32), nullable=False),
        # UTCDateTime TypeDecorator stores ISO-8601 text; always tz-aware at Python.
        sa.Column("snapshot_committed_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        # decided_at: NULL iff decision == PENDING (domain invariant).
        sa.Column("decided_at", sa.Text(), nullable=True),
    )

    # §確定 R1-K: composite (task_id, created_at) index for find_by_task_id.
    op.create_index(
        "ix_external_review_gates_task_id_created",
        "external_review_gates",
        ["task_id", "created_at"],
        unique=False,
    )

    # §確定 R1-K: composite (reviewer_id, decision) for find_pending_by_reviewer.
    op.create_index(
        "ix_external_review_gates_reviewer_decision",
        "external_review_gates",
        ["reviewer_id", "decision"],
        unique=False,
    )

    # §確定 R1-K: single-column (decision) for count_by_decision.
    op.create_index(
        "ix_external_review_gates_decision",
        "external_review_gates",
        ["decision"],
        unique=False,
    )

    # ---- external_review_gate_attachments table ----------------------------
    op.create_table(
        "external_review_gate_attachments",
        # id: save-internal PK (uuid4() regenerated on each save()).
        # Business key: UNIQUE(gate_id, sha256).
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "gate_id",
            sa.CHAR(32),
            sa.ForeignKey("external_review_gates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # sha256: 64-char lowercase hex; validated by Attachment VO.
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        # UNIQUE(gate_id, sha256): prevents duplicate content within one Gate;
        # sha256 provides deterministic ORDER BY anchor (§確定 R1-H).
        sa.UniqueConstraint(
            "gate_id",
            "sha256",
            name="uq_erg_attachments_gate_sha256",
        ),
    )

    # ---- external_review_audit_entries table -------------------------------
    op.create_table(
        "external_review_audit_entries",
        # id: taken from domain AuditEntry.id (NOT regenerated on save).
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "gate_id",
            sa.CHAR(32),
            sa.ForeignKey("external_review_gates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # actor_id: intentionally NO FK — Owner Aggregate not yet implemented
        # (§設計決定 ERGR-001). Same rationale as reviewer_id above.
        sa.Column("actor_id", sa.CHAR(32), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        # comment: MaskedText serialises as TEXT (§確定 R1-E).
        # CEO-authored text; can carry webhook URLs / API keys.
        sa.Column("comment", sa.Text(), nullable=False),
        # UTCDateTime TypeDecorator stores ISO-8601 text.
        sa.Column("occurred_at", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    # Reverse order: child tables first (CASCADE FK order), then root.
    # 1. Drop deepest child tables (no dependents within this migration).
    op.drop_table("external_review_audit_entries")
    op.drop_table("external_review_gate_attachments")

    # 2. Drop indexes before dropping root table.
    op.drop_index(
        "ix_external_review_gates_decision",
        table_name="external_review_gates",
    )
    op.drop_index(
        "ix_external_review_gates_reviewer_decision",
        table_name="external_review_gates",
    )
    op.drop_index(
        "ix_external_review_gates_task_id_created",
        table_name="external_review_gates",
    )

    # 3. Drop root table.
    op.drop_table("external_review_gates")
