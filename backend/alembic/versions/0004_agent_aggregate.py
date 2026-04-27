"""Agent Aggregate tables: agents + agent_providers + agent_skills.

Adds the three tables that back :class:`SqliteAgentRepository`:

* ``agents`` (id PK + empire_id FK CASCADE + Persona scalars). The
  ``prompt_body`` column is declared with the
  :class:`MaskedText` TypeDecorator at the ORM level (Alembic stores
  it as ``TEXT`` here; the masking gate lives on the Python side).
* ``agent_providers`` (FK CASCADE on agent_id, UNIQUE(agent_id,
  provider_kind)) **plus a partial unique index** on ``agent_id``
  scoped by ``WHERE is_default = 1``. The partial index is the §確定 G
  Defense-in-Depth floor for "exactly one default provider per Agent"
  — even if a future PR introduces a corrupted SQL path, the DB still
  refuses two ``is_default=1`` rows on the same Agent.
* ``agent_skills`` (FK CASCADE on agent_id, UNIQUE(agent_id,
  skill_id)). The ``path`` column is bounded to 500 characters per
  the agent feature §確定 H pipeline; H1〜H10 traversal defense lives
  on the VO side.

Per ``docs/features/empire-repository/detailed-design.md`` §確定 F
each subsequent ``feature/{aggregate}-repository`` PR appends its own
revision; this revision pins ``down_revision = "0003_workflow_aggregate"``
strictly so the chain check enforces a single head.

Revision ID: 0004_agent_aggregate
Revises: 0003_workflow_aggregate
Create Date: 2026-04-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_agent_aggregate"
down_revision: str | None = "0003_workflow_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "empire_id",
            sa.CHAR(32),
            sa.ForeignKey("empires.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column(
            "archetype",
            sa.String(80),
            nullable=False,
            server_default=sa.text("''"),
        ),
        # MaskedText TypeDecorator serializes as TEXT in SQLite. The
        # Python-side decorator does the masking gate (see
        # infrastructure/persistence/sqlite/base.py).
        sa.Column(
            "prompt_body",
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

    op.create_table(
        "agent_providers",
        sa.Column(
            "agent_id",
            sa.CHAR(32),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "provider_kind",
            sa.String(32),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint(
            "agent_id",
            "provider_kind",
            name="uq_agent_providers_pair",
        ),
    )
    # detailed-design §確定 G: partial unique index for the
    # "at most one default provider per agent" Defense-in-Depth floor.
    # SQLite ships partial indexes natively; the same syntax ports to
    # PostgreSQL when the M5+ migration lands.
    op.create_index(
        "uq_agent_providers_default",
        "agent_providers",
        ["agent_id"],
        unique=True,
        sqlite_where=sa.text("is_default = 1"),
    )

    op.create_table(
        "agent_skills",
        sa.Column(
            "agent_id",
            sa.CHAR(32),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("skill_id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.UniqueConstraint(
            "agent_id",
            "skill_id",
            name="uq_agent_skills_pair",
        ),
    )


def downgrade() -> None:
    # Drop child tables first so the FK CASCADE doesn't trigger work
    # against an already-deleted parent.
    op.drop_table("agent_skills")
    op.drop_index("uq_agent_providers_default", table_name="agent_providers")
    op.drop_table("agent_providers")
    op.drop_table("agents")
