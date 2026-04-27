"""``workflows`` table — Workflow Aggregate root row.

Holds three scalar columns (``id`` / ``name`` / ``entry_stage_id``); the
``stages`` and ``transitions`` collections live in the side tables
:mod:`...tables.workflow_stages` /
:mod:`...tables.workflow_transitions` so the row width stays bounded
and CASCADE targets are obvious.

``entry_stage_id`` is **intentionally not a foreign key** onto
``workflow_stages.stage_id`` — see
``docs/features/workflow-repository/detailed-design.md`` §確定 J. The
natural FK would form a circular reference (``workflows`` ↔
``workflow_stages``) that requires deferred constraints. SQLite's
``PRAGMA defer_foreign_keys`` works but tightens portability against
the M5+ PostgreSQL migration goal. The Aggregate-level
``_validate_entry_in_stages`` already proves ``entry_stage_id`` lives
inside ``stages``, so the DB constraint is redundant.

No ``Masked*`` TypeDecorator on any column. The CI three-layer defense
(grep guard + arch test + storage.md §逆引き表) registers this absence
so a future PR cannot silently swap a column to a secret-bearing
semantic.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class WorkflowRow(Base):
    """ORM mapping for the ``workflows`` table."""

    __tablename__ = "workflows"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    entry_stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)


__all__ = ["WorkflowRow"]
