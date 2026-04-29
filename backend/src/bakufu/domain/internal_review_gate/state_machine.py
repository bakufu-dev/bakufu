"""Decision computation for the :class:`InternalReviewGate` aggregate.

Implements the most-pessimistic-wins rule per internal-review-gate
detailed-design §確定 B:

1. Any :attr:`VerdictDecision.REJECTED` verdict → :attr:`GateDecision.REJECTED`
   (highest priority; a single dissent blocks the Gate immediately).
2. All ``required_gate_roles`` have an APPROVED verdict →
   :attr:`GateDecision.ALL_APPROVED`.
3. Otherwise → :attr:`GateDecision.PENDING`.

The computation is a **pure function** with no side effects, locked
behind a ``Final`` binding so pyright strict rejects re-assignment.

Unlike :mod:`bakufu.domain.external_review_gate.state_machine` which
models a *transition table* (action x state -> next_state), the
InternalReviewGate's decision is **computed** from the current
``verdicts`` collection and ``required_gate_roles`` set — there is no
explicit action dispatch, only a fold over the verdict tuple.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Final

from bakufu.domain.value_objects import GateDecision, VerdictDecision

if TYPE_CHECKING:
    from bakufu.domain.value_objects import GateRole, Verdict


def _compute_decision(
    verdicts: tuple[Verdict, ...],
    required_gate_roles: frozenset[GateRole],
) -> GateDecision:
    """Return the :class:`GateDecision` implied by the current state.

    Decision table (most-pessimistic-wins):

    1. Any verdict with ``decision == REJECTED`` → ``REJECTED``
       (checked first; a single dissent closes the Gate immediately,
       regardless of how many approvals exist).
    2. Every role in ``required_gate_roles`` has a corresponding
       APPROVED verdict → ``ALL_APPROVED``.
    3. Otherwise → ``PENDING`` (some required roles are still missing).

    Args:
        verdicts: All verdicts collected so far. May be empty.
        required_gate_roles: The closed set of role slugs that **must**
            all vote APPROVED before the Gate can reach ALL_APPROVED.
            Must be non-empty (enforced by
            :func:`bakufu.domain.internal_review_gate.aggregate_validators
            ._validate_required_gate_roles_nonempty` before this
            function is called).

    Returns:
        The :class:`GateDecision` that best describes the current
        verdict collection.
    """
    # Rule 1: any REJECTED verdict → REJECTED (most pessimistic wins).
    for verdict in verdicts:
        if verdict.decision == VerdictDecision.REJECTED:
            return GateDecision.REJECTED

    # Rule 2: all required roles have APPROVED verdicts → ALL_APPROVED.
    approved_roles = frozenset(
        verdict.role for verdict in verdicts if verdict.decision == VerdictDecision.APPROVED
    )
    if required_gate_roles.issubset(approved_roles):
        return GateDecision.ALL_APPROVED

    # Rule 3: still waiting on one or more required roles.
    return GateDecision.PENDING


compute_decision: Final[Callable[[tuple[Verdict, ...], frozenset[GateRole]], GateDecision]] = (
    _compute_decision
)
"""Public alias for the decision computation function.

Locked as ``Final`` so pyright strict catches any re-assignment attempt.
Import this symbol (not ``_compute_decision``) from application code and
tests so the public contract is explicit and the private implementation
detail remains free to be renamed.
"""

__all__ = ["compute_decision"]
