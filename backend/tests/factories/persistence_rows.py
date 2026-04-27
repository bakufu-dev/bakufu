"""Factories for ORM row instances under persistence integration tests.

Each factory returns a *valid* default :class:`OutboxRow` /
:class:`AuditLogRow` / :class:`PidRegistryRow` and registers the
``_meta = {"synthetic": True}`` tag onto the instance for easy
discrimination from production rows during inspection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from bakufu.infrastructure.persistence.sqlite.tables.audit_log import AuditLogRow
from bakufu.infrastructure.persistence.sqlite.tables.outbox import OutboxRow
from bakufu.infrastructure.persistence.sqlite.tables.pid_registry import (
    PidRegistryRow,
)


def make_outbox_row(
    *,
    event_id: UUID | None = None,
    event_kind: str = "TestEventEmitted",
    aggregate_id: UUID | None = None,
    payload_json: dict[str, object] | None = None,
    status: str = "PENDING",
    attempt_count: int = 0,
    next_attempt_at: datetime | None = None,
    last_error: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    dispatched_at: datetime | None = None,
) -> OutboxRow:
    """Build a valid ``domain_event_outbox`` row.

    Defaults to ``status='PENDING'`` with the next_attempt_at moment in
    the past so the dispatcher would see the row as eligible.
    """
    now = datetime.now(UTC)
    return OutboxRow(
        event_id=event_id or uuid4(),
        event_kind=event_kind,
        aggregate_id=aggregate_id or uuid4(),
        payload_json=payload_json or {"message": "hello"},
        status=status,
        attempt_count=attempt_count,
        next_attempt_at=next_attempt_at or now,
        last_error=last_error,
        created_at=created_at or now,
        updated_at=updated_at or now,
        dispatched_at=dispatched_at,
    )


def make_audit_log_row(
    *,
    row_id: UUID | None = None,
    actor: str = "tester@host",
    command: str = "retry-task",
    args_json: dict[str, object] | None = None,
    result: str | None = None,
    error_text: str | None = None,
    executed_at: datetime | None = None,
) -> AuditLogRow:
    """Build a valid ``audit_log`` row (default ``result=None``)."""
    return AuditLogRow(
        id=row_id or uuid4(),
        actor=actor,
        command=command,
        args_json=args_json or {"target": "task-uuid"},
        result=result,
        error_text=error_text,
        executed_at=executed_at or datetime.now(UTC),
    )


def make_pid_registry_row(
    *,
    pid: int = 12345,
    parent_pid: int = 1,
    started_at: datetime | None = None,
    cmd: str = "claude --task example",
    task_id: UUID | None = None,
    stage_id: UUID | None = None,
) -> PidRegistryRow:
    """Build a valid ``bakufu_pid_registry`` row."""
    return PidRegistryRow(
        pid=pid,
        parent_pid=parent_pid,
        started_at=started_at or datetime.now(UTC),
        cmd=cmd,
        task_id=task_id,
        stage_id=stage_id,
    )


__all__ = [
    "make_audit_log_row",
    "make_outbox_row",
    "make_pid_registry_row",
]
