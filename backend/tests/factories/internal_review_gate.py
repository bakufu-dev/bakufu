"""Factories for the InternalReviewGate aggregate and its VOs.

Per ``docs/features/internal-review-gate/domain/test-design.md`` §外部 I/O 依存マップ.
Mirrors the M1 sibling pattern (external_review_gate / agent / room / directive / task /
workflow): every factory returns a *valid* default instance built through the production
constructor, allows keyword overrides, and registers the result in a
:class:`WeakValueDictionary` so :func:`is_synthetic` can later flag test-built objects
without mutating the frozen Pydantic models.

Four factories are exposed:

* :func:`make_verdict` — a single APPROVED :class:`Verdict` VO.
* :func:`make_gate` — a PENDING :class:`InternalReviewGate` (empty verdicts).
* :func:`make_all_approved_gate` — ALL_APPROVED Gate with all required roles voted.
* :func:`make_rejected_gate` — REJECTED Gate with one REJECTED verdict.

Factories build directly via ``model_validate`` — they do **NOT** call ``submit_verdict``
— because unit tests for the behavior methods need a clean entry state without prior
method-driven mutation.

Production code MUST NOT import this module.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.internal_review_gate import InternalReviewGate
from bakufu.domain.value_objects import (
    GateDecision,
    Verdict,
    VerdictDecision,
)
from pydantic import BaseModel

# Module-scope registry: synthetic instances are tracked weakly so GC pressure
# stays neutral while the object is alive.
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()

# Default role set shared by PENDING / REJECTED factories.
_DEFAULT_ROLES: frozenset[str] = frozenset({"reviewer", "ux", "security"})
# Smaller role set used by ALL_APPROVED factory (keeps verdicts minimal).
_APPROVED_ROLES: frozenset[str] = frozenset({"reviewer", "ux"})


def is_synthetic(instance: BaseModel) -> bool:
    """Return ``True`` when ``instance`` was created by a factory in this module.

    Check is identity-based (``id()``) so two independently-produced equal
    instances are still distinguishable.
    """
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# Verdict factory
# ---------------------------------------------------------------------------
def make_verdict(
    *,
    role: str = "reviewer",
    agent_id: UUID | None = None,
    decision: VerdictDecision = VerdictDecision.APPROVED,
    comment: str = "",
    decided_at: datetime | None = None,
) -> Verdict:
    """Build a valid :class:`Verdict` VO.

    Defaults to an APPROVED verdict from the ``"reviewer"`` role with an
    empty comment — the simplest legal shape for unit test setup.
    """
    verdict = Verdict(
        role=role,
        agent_id=agent_id if agent_id is not None else uuid4(),
        decision=decision,
        comment=comment,
        decided_at=decided_at if decided_at is not None else datetime.now(UTC),
    )
    _register(verdict)
    return verdict


# ---------------------------------------------------------------------------
# InternalReviewGate factories
# ---------------------------------------------------------------------------
def make_gate(
    *,
    gate_id: UUID | None = None,
    task_id: UUID | None = None,
    stage_id: UUID | None = None,
    required_gate_roles: frozenset[str] | None = None,
    verdicts: list[Verdict] | None = None,
    gate_decision: GateDecision = GateDecision.PENDING,
    created_at: datetime | None = None,
) -> InternalReviewGate:
    """Build a valid PENDING :class:`InternalReviewGate` directly via ``model_validate``.

    Defaults:
    * ``gate_decision = PENDING``
    * ``verdicts = []``
    * ``required_gate_roles = {"reviewer", "ux", "security"}``

    Pass ``verdicts`` + matching ``gate_decision`` to build terminal-state Gates
    (prefer :func:`make_all_approved_gate` / :func:`make_rejected_gate` for that).
    """
    now = datetime.now(UTC)
    roles = required_gate_roles if required_gate_roles is not None else _DEFAULT_ROLES
    raw_verdicts = verdicts if verdicts is not None else []
    gate = InternalReviewGate.model_validate(
        {
            "id": gate_id if gate_id is not None else uuid4(),
            "task_id": task_id if task_id is not None else uuid4(),
            "stage_id": stage_id if stage_id is not None else uuid4(),
            "required_gate_roles": roles,
            "verdicts": [v.model_dump() for v in raw_verdicts],
            "gate_decision": gate_decision,
            "created_at": created_at if created_at is not None else now,
        }
    )
    _register(gate)
    return gate


def make_all_approved_gate(
    *,
    required_gate_roles: frozenset[str] | None = None,
    gate_id: UUID | None = None,
    task_id: UUID | None = None,
    stage_id: UUID | None = None,
) -> InternalReviewGate:
    """Build an ALL_APPROVED :class:`InternalReviewGate`.

    Defaults to ``required_gate_roles={"reviewer","ux"}`` — the smallest
    valid set that demonstrates full consensus (2 APPROVED verdicts).
    Every required role gets an APPROVED Verdict.
    """
    roles = required_gate_roles if required_gate_roles is not None else _APPROVED_ROLES
    ts = datetime.now(UTC)
    verdicts = [
        make_verdict(role=role, decision=VerdictDecision.APPROVED, decided_at=ts)
        for role in sorted(roles)
    ]
    return make_gate(
        gate_id=gate_id,
        task_id=task_id,
        stage_id=stage_id,
        required_gate_roles=roles,
        verdicts=verdicts,
        gate_decision=GateDecision.ALL_APPROVED,
    )


def make_rejected_gate(
    *,
    rejecting_role: str = "reviewer",
    required_gate_roles: frozenset[str] | None = None,
    comment: str = "バグを発見しました。",
    gate_id: UUID | None = None,
    task_id: UUID | None = None,
    stage_id: UUID | None = None,
) -> InternalReviewGate:
    """Build a REJECTED :class:`InternalReviewGate`.

    One REJECTED Verdict from ``rejecting_role``; remaining required roles
    are *not* submitted (demonstrates the most-pessimistic-wins rule:
    immediate REJECTED even with pending roles).
    """
    roles = required_gate_roles if required_gate_roles is not None else _DEFAULT_ROLES
    if rejecting_role not in roles:
        raise ValueError(
            f"rejecting_role '{rejecting_role}' must be present in required_gate_roles"
        )
    ts = datetime.now(UTC)
    verdict = make_verdict(
        role=rejecting_role,
        decision=VerdictDecision.REJECTED,
        comment=comment,
        decided_at=ts,
    )
    return make_gate(
        gate_id=gate_id,
        task_id=task_id,
        stage_id=stage_id,
        required_gate_roles=roles,
        verdicts=[verdict],
        gate_decision=GateDecision.REJECTED,
    )


__all__ = [
    "is_synthetic",
    "make_all_approved_gate",
    "make_gate",
    "make_rejected_gate",
    "make_verdict",
]
