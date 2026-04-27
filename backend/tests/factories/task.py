"""Factories for the Task aggregate and its VOs.

Per ``docs/features/task/test-design.md`` §外部 I/O 依存マップ, each
factory returns a *valid* default instance built via the production
constructor and registers the result in :data:`_SYNTHETIC_REGISTRY`
so :func:`is_synthetic` can later confirm "this object came from a
factory" — the WeakValueDictionary pattern established by the M1
5-sibling factories (empire / workflow / agent / room / directive).

Eight factories are exposed (one per status + DeliverableFactory +
AttachmentFactory) so each lifecycle position can be reached without
walking the state machine in setup. The factories build directly via
``Task.model_validate`` — they do NOT call the behavior methods —
because tests for the behavior methods need a clean entry state
without prior method-driven mutation.

Production code MUST NOT import this module — it lives under
``tests/`` to keep the synthetic-data boundary auditable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.task import Task
from bakufu.domain.value_objects import (
    Attachment,
    Deliverable,
    TaskStatus,
)
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

# Module-scope registry. Values are kept weakly so GC pressure stays
# neutral; we only want to know "did a factory produce this object"
# while it's alive.
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()


def is_synthetic(instance: BaseModel) -> bool:
    """Return ``True`` when ``instance`` was created by a factory in this module.

    The check is identity-based (``id``) rather than structural so
    two independently-produced equal instances are still
    distinguishable: only the actual object the factory returned is
    marked synthetic.
    """
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """Record ``instance`` in the synthetic registry."""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# A canonical 64-hex sha256 used by AttachmentFactory defaults.
_DEFAULT_SHA256 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


# ---------------------------------------------------------------------------
# Attachment factory
# ---------------------------------------------------------------------------
def make_attachment(
    *,
    sha256: str = _DEFAULT_SHA256,
    filename: str = "deliverable.png",
    mime_type: str = "image/png",
    size_bytes: int = 1024,
) -> Attachment:
    """Build a valid :class:`Attachment` and register it as synthetic."""
    attachment = Attachment(
        sha256=sha256,
        filename=filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
    )
    _register(attachment)
    return attachment


# ---------------------------------------------------------------------------
# Deliverable factory
# ---------------------------------------------------------------------------
def make_deliverable(
    *,
    stage_id: UUID | None = None,
    body_markdown: str = "# Test deliverable",
    attachments: Sequence[Attachment] | None = None,
    committed_by: UUID | None = None,
    committed_at: datetime | None = None,
) -> Deliverable:
    """Build a valid :class:`Deliverable` and register it as synthetic."""
    deliverable = Deliverable(
        stage_id=stage_id if stage_id is not None else uuid4(),
        body_markdown=body_markdown,
        attachments=list(attachments) if attachments is not None else [],
        committed_by=committed_by if committed_by is not None else uuid4(),
        committed_at=committed_at if committed_at is not None else datetime.now(UTC),
    )
    _register(deliverable)
    return deliverable


# ---------------------------------------------------------------------------
# Task factories — one per status + a generic make_task
# ---------------------------------------------------------------------------
def make_task(
    *,
    task_id: UUID | None = None,
    room_id: UUID | None = None,
    directive_id: UUID | None = None,
    current_stage_id: UUID | None = None,
    status: TaskStatus = TaskStatus.PENDING,
    assigned_agent_ids: Sequence[UUID] | None = None,
    deliverables: dict[UUID, Deliverable] | None = None,
    last_error: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Task:
    """Build a valid :class:`Task` directly via ``model_validate``.

    Defaults yield a PENDING Task with no assigned agents, no
    deliverables, and ``last_error=None`` — the canonical entry
    state right after ``DirectiveService.issue()``.

    Note: ``status=BLOCKED`` requires a non-empty ``last_error`` per
    the consistency invariant; tests that need a BLOCKED Task should
    use :func:`make_blocked_task` (or pass ``last_error`` themselves).
    """
    now = datetime.now(UTC)
    task = Task.model_validate(
        {
            "id": task_id if task_id is not None else uuid4(),
            "room_id": room_id if room_id is not None else uuid4(),
            "directive_id": directive_id if directive_id is not None else uuid4(),
            "current_stage_id": current_stage_id if current_stage_id is not None else uuid4(),
            "status": status,
            "assigned_agent_ids": (
                list(assigned_agent_ids) if assigned_agent_ids is not None else []
            ),
            "deliverables": dict(deliverables) if deliverables is not None else {},
            "last_error": last_error,
            "created_at": created_at if created_at is not None else now,
            "updated_at": updated_at if updated_at is not None else now,
        }
    )
    _register(task)
    return task


def make_in_progress_task(
    *,
    assigned_agent_ids: Sequence[UUID] | None = None,
    **overrides: object,
) -> Task:
    """Build an IN_PROGRESS Task with at least one assigned agent."""
    if assigned_agent_ids is None:
        assigned_agent_ids = [uuid4()]
    return make_task(
        status=TaskStatus.IN_PROGRESS,
        assigned_agent_ids=assigned_agent_ids,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def make_awaiting_review_task(
    *,
    assigned_agent_ids: Sequence[UUID] | None = None,
    **overrides: object,
) -> Task:
    """Build an AWAITING_EXTERNAL_REVIEW Task."""
    if assigned_agent_ids is None:
        assigned_agent_ids = [uuid4()]
    return make_task(
        status=TaskStatus.AWAITING_EXTERNAL_REVIEW,
        assigned_agent_ids=assigned_agent_ids,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def make_blocked_task(
    *,
    assigned_agent_ids: Sequence[UUID] | None = None,
    last_error: str = "AuthExpired: synthetic blocking error",
    **overrides: object,
) -> Task:
    """Build a BLOCKED Task. ``last_error`` is required for consistency."""
    if assigned_agent_ids is None:
        assigned_agent_ids = [uuid4()]
    return make_task(
        status=TaskStatus.BLOCKED,
        assigned_agent_ids=assigned_agent_ids,
        last_error=last_error,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def make_done_task(
    *,
    assigned_agent_ids: Sequence[UUID] | None = None,
    deliverables: dict[UUID, Deliverable] | None = None,
    **overrides: object,
) -> Task:
    """Build a DONE Task with at least one deliverable accumulated."""
    if assigned_agent_ids is None:
        assigned_agent_ids = [uuid4()]
    if deliverables is None:
        d = make_deliverable()
        deliverables = {d.stage_id: d}
    return make_task(
        status=TaskStatus.DONE,
        assigned_agent_ids=assigned_agent_ids,
        deliverables=deliverables,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def make_cancelled_task(
    *,
    assigned_agent_ids: Sequence[UUID] | None = None,
    **overrides: object,
) -> Task:
    """Build a CANCELLED Task. ``last_error`` must be None."""
    if assigned_agent_ids is None:
        assigned_agent_ids = [uuid4()]
    return make_task(
        status=TaskStatus.CANCELLED,
        assigned_agent_ids=assigned_agent_ids,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


__all__ = [
    "is_synthetic",
    "make_attachment",
    "make_awaiting_review_task",
    "make_blocked_task",
    "make_cancelled_task",
    "make_deliverable",
    "make_done_task",
    "make_in_progress_task",
    "make_task",
]
