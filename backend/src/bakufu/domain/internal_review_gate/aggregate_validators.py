"""Aggregate-level invariant helpers for :class:`InternalReviewGate`.

Each helper is a **module-level pure function** so tests can ``import``
and invoke directly — the same testability pattern used by the
agent / room / directive / task / external_review_gate aggregate
validators.

Four invariants (matching internal-review-gate detailed-design §確定 J):

1. :func:`_validate_required_gate_roles_nonempty` — ``required_gate_roles``
   must contain at least one role; an empty set would make
   ALL_APPROVED unreachable by design and is a workflow-author mistake
   that should surface immediately.
2. :func:`_validate_verdict_roles_in_required` — every verdict's
   ``role`` must appear in ``required_gate_roles``; a verdict from an
   unrecognized role indicates a stale or misconfigured agent and should
   be rejected before it influences the decision.
3. :func:`_validate_no_duplicate_roles` — each GateRole may have at most
   one verdict; duplicate submissions are rejected (the agent must be
   ``submit_verdict``-guarded at the behavior layer too, but the
   aggregate validator provides a second line of defense during
   hydration).
4. :func:`_validate_gate_decision_consistency` — the stored
   ``gate_decision`` must equal what ``compute_decision`` produces from
   the current ``verdicts`` and ``required_gate_roles``; detects
   Repository row corruption or a misbehaving behavior method.

The public :func:`validate_all` function runs all four in order and is
called by :meth:`InternalReviewGate._check_invariants`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bakufu.domain.exceptions import InternalReviewGateInvariantViolation
from bakufu.domain.internal_review_gate.state_machine import compute_decision

if TYPE_CHECKING:
    from bakufu.domain.internal_review_gate.internal_review_gate import InternalReviewGate


def _validate_required_gate_roles_nonempty(gate: InternalReviewGate) -> None:
    """``required_gate_roles`` must not be empty (invariant 1).

    An empty set would make ``GateDecision.ALL_APPROVED`` structurally
    unreachable (no roles to approve means the condition ``all required
    roles approved`` is vacuously true from the state-machine's
    perspective, but the business rule intends that at least one human
    reviewer category participates).  Raising here at construction time
    surfaces the workflow-author mistake before any agent can interact
    with the Gate.
    """
    if not gate.required_gate_roles:
        raise InternalReviewGateInvariantViolation(
            kind="required_gate_roles_empty",
            message=(
                "[FAIL] InternalReviewGate.required_gate_roles が空です。\n"
                "Next: 少なくとも 1 つの GateRole を required_gate_roles に設定してください。"
            ),
            detail={"gate_id": str(gate.id)},
        )


def _validate_verdict_roles_in_required(gate: InternalReviewGate) -> None:
    """Every verdict role must be in ``required_gate_roles`` (invariant 2).

    A verdict whose ``role`` is absent from ``required_gate_roles``
    indicates either a stale Gate configuration (the role was removed
    after the Gate was created) or a misconfigured agent (it is
    presenting a role it was never granted). Either case is a data
    integrity violation that should surface before the Gate's decision
    is computed.
    """
    required = gate.required_gate_roles
    for verdict in gate.verdicts:
        if verdict.role not in required:
            raise InternalReviewGateInvariantViolation(
                kind="verdict_role_invalid",
                message=(
                    f'[FAIL] Verdict の GateRole "{verdict.role}" は '
                    f"required_gate_roles に含まれていません。\n"
                    f"Next: 有効な GateRole（{sorted(required)}）の verdict のみ "
                    f"InternalReviewGate に追加してください。"
                ),
                detail={
                    "gate_id": str(gate.id),
                    "invalid_role": verdict.role,
                    "required_gate_roles": sorted(required),
                },
            )


def _validate_no_duplicate_roles(gate: InternalReviewGate) -> None:
    """Each GateRole must appear at most once in ``verdicts`` (invariant 3).

    Duplicate role verdicts are a programming error — ``submit_verdict``
    guards against re-submission at the behavior layer, but the
    aggregate validator enforces the same invariant during hydration so
    a corrupt Repository row does not yield a silently-inconsistent Gate.
    """
    seen: set[str] = set()
    for verdict in gate.verdicts:
        if verdict.role in seen:
            raise InternalReviewGateInvariantViolation(
                kind="duplicate_role_verdict",
                message=(
                    f'[FAIL] GateRole "{verdict.role}" の verdict が重複しています。\n'
                    f"Next: 各 GateRole の verdict は 1 件のみ許可されています。"
                ),
                detail={
                    "gate_id": str(gate.id),
                    "duplicate_role": verdict.role,
                },
            )
        seen.add(verdict.role)


def _validate_gate_decision_consistency(gate: InternalReviewGate) -> None:
    """``gate_decision`` must equal ``compute_decision(...)`` (invariant 4).

    Detects Repository row corruption (e.g. ``gate_decision=ALL_APPROVED``
    when no verdicts exist) or a misbehaving behavior method that updated
    the decision field without going through the state machine.
    """
    expected = compute_decision(gate.verdicts, gate.required_gate_roles)
    if gate.gate_decision != expected:
        raise InternalReviewGateInvariantViolation(
            kind="gate_decision_inconsistent",
            message=(
                f"[FAIL] gate_decision が不整合です "
                f"（stored={gate.gate_decision.value}, "
                f"computed={expected.value}）。\n"
                f"Next: Repository 行の整合性を確認してください。"
            ),
            detail={
                "gate_id": str(gate.id),
                "stored_decision": gate.gate_decision.value,
                "computed_decision": expected.value,
            },
        )


def validate_all(gate: InternalReviewGate) -> None:
    """Run all four aggregate invariants in order.

    Called by :meth:`InternalReviewGate._check_invariants` so every
    construction path (direct instantiation, ``model_validate``, and
    Repository hydration) runs the same checks. The invariants are
    ordered from cheapest to most expensive:

    1. Non-empty roles (O(1) set truth check).
    2. Verdict roles subset check (O(n) over verdicts).
    3. Duplicate role detection (O(n) with a ``set`` accumulator).
    4. Decision consistency (O(n) ``compute_decision`` fold).
    """
    _validate_required_gate_roles_nonempty(gate)
    _validate_verdict_roles_in_required(gate)
    _validate_no_duplicate_roles(gate)
    _validate_gate_decision_consistency(gate)


__all__ = [
    "_validate_gate_decision_consistency",
    "_validate_no_duplicate_roles",
    "_validate_required_gate_roles_nonempty",
    "_validate_verdict_roles_in_required",
    "validate_all",
]
