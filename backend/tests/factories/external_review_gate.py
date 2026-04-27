"""Factories for the ExternalReviewGate aggregate and its VOs.

Per ``docs/features/external-review-gate/test-design.md`` §外部 I/O 依存
マップ. Mirrors the M1 6-sibling pattern (empire / workflow / agent /
room / directive / task): every factory returns a *valid* default
instance built through the production constructor, allows keyword
overrides, and registers the result in a :class:`WeakValueDictionary`
so :func:`is_synthetic` can later flag test-built objects without
mutating the frozen Pydantic models.

Five Gate factories are exposed (one per ``ReviewDecision`` + a
PendingGateFactory baseline) so each lifecycle position can be
reached without walking the state machine in setup. The factories
build directly via ``ExternalReviewGate.model_validate`` — they do
NOT call the behavior methods — because tests for the behavior
methods need a clean entry state without prior method-driven
mutation (and the §確定 C audit_trail append-only contract means
factory-set audit_trail bytes are pinned for every subsequent
mutation).

Production code MUST NOT import this module — it lives under
``tests/`` to keep the synthetic-data boundary auditable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.external_review_gate import ExternalReviewGate
from bakufu.domain.value_objects import (
    AuditAction,
    AuditEntry,
    Deliverable,
    ReviewDecision,
)
from pydantic import BaseModel

from tests.factories.task import make_deliverable

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


# ---------------------------------------------------------------------------
# AuditEntry factory
# ---------------------------------------------------------------------------
def make_audit_entry(
    *,
    entry_id: UUID | None = None,
    actor_id: UUID | None = None,
    action: AuditAction = AuditAction.VIEWED,
    comment: str = "",
    occurred_at: datetime | None = None,
) -> AuditEntry:
    """Build a valid :class:`AuditEntry`.

    Defaults to a VIEWED audit entry — the simplest legal shape that
    every Gate state can carry. Tests that need APPROVED / REJECTED /
    CANCELLED audit rows override ``action`` explicitly.
    """
    entry = AuditEntry(
        id=entry_id if entry_id is not None else uuid4(),
        actor_id=actor_id if actor_id is not None else uuid4(),
        action=action,
        comment=comment,
        occurred_at=occurred_at if occurred_at is not None else datetime.now(UTC),
    )
    _register(entry)
    return entry


# ---------------------------------------------------------------------------
# ExternalReviewGate factories — one per ReviewDecision + a baseline
# ---------------------------------------------------------------------------
def make_gate(
    *,
    gate_id: UUID | None = None,
    task_id: UUID | None = None,
    stage_id: UUID | None = None,
    deliverable_snapshot: Deliverable | None = None,
    reviewer_id: UUID | None = None,
    decision: ReviewDecision = ReviewDecision.PENDING,
    feedback_text: str = "",
    audit_trail: Sequence[AuditEntry] | None = None,
    created_at: datetime | None = None,
    decided_at: datetime | None = None,
) -> ExternalReviewGate:
    """Build a valid :class:`ExternalReviewGate` directly via ``model_validate``.

    Defaults yield a PENDING Gate with no audit entries, no feedback,
    and ``decided_at=None`` — the canonical entry state right after
    ``GateService.create()`` (after Task.request_external_review).

    Note: ``decision != PENDING`` requires a non-None ``decided_at``
    per the consistency invariant; tests that need a terminal Gate
    should use :func:`make_approved_gate` /
    :func:`make_rejected_gate` / :func:`make_cancelled_gate`.
    """
    now = datetime.now(UTC)
    gate = ExternalReviewGate.model_validate(
        {
            "id": gate_id if gate_id is not None else uuid4(),
            "task_id": task_id if task_id is not None else uuid4(),
            "stage_id": stage_id if stage_id is not None else uuid4(),
            "deliverable_snapshot": (
                deliverable_snapshot if deliverable_snapshot is not None else make_deliverable()
            ),
            "reviewer_id": reviewer_id if reviewer_id is not None else uuid4(),
            "decision": decision,
            "feedback_text": feedback_text,
            "audit_trail": list(audit_trail) if audit_trail is not None else [],
            "created_at": created_at if created_at is not None else now,
            "decided_at": decided_at,
        }
    )
    _register(gate)
    return gate


def make_approved_gate(
    *,
    feedback_text: str = "Approved by reviewer.",
    audit_trail: Sequence[AuditEntry] | None = None,
    decided_at: datetime | None = None,
    **overrides: object,
) -> ExternalReviewGate:
    """Build an APPROVED Gate. ``decided_at`` is mandatory for the consistency invariant."""
    decided_at = decided_at if decided_at is not None else datetime.now(UTC)
    if audit_trail is None:
        audit_trail = [
            make_audit_entry(action=AuditAction.APPROVED, occurred_at=decided_at),
        ]
    return make_gate(
        decision=ReviewDecision.APPROVED,
        feedback_text=feedback_text,
        audit_trail=audit_trail,
        decided_at=decided_at,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def make_rejected_gate(
    *,
    feedback_text: str = "Rejected: needs revision.",
    audit_trail: Sequence[AuditEntry] | None = None,
    decided_at: datetime | None = None,
    **overrides: object,
) -> ExternalReviewGate:
    """Build a REJECTED Gate."""
    decided_at = decided_at if decided_at is not None else datetime.now(UTC)
    if audit_trail is None:
        audit_trail = [
            make_audit_entry(action=AuditAction.REJECTED, occurred_at=decided_at),
        ]
    return make_gate(
        decision=ReviewDecision.REJECTED,
        feedback_text=feedback_text,
        audit_trail=audit_trail,
        decided_at=decided_at,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def make_cancelled_gate(
    *,
    feedback_text: str = "Cancelled: directive withdrawn.",
    audit_trail: Sequence[AuditEntry] | None = None,
    decided_at: datetime | None = None,
    **overrides: object,
) -> ExternalReviewGate:
    """Build a CANCELLED Gate."""
    decided_at = decided_at if decided_at is not None else datetime.now(UTC)
    if audit_trail is None:
        audit_trail = [
            make_audit_entry(action=AuditAction.CANCELLED, occurred_at=decided_at),
        ]
    return make_gate(
        decision=ReviewDecision.CANCELLED,
        feedback_text=feedback_text,
        audit_trail=audit_trail,
        decided_at=decided_at,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


__all__ = [
    "is_synthetic",
    "make_approved_gate",
    "make_audit_entry",
    "make_cancelled_gate",
    "make_gate",
    "make_rejected_gate",
]
