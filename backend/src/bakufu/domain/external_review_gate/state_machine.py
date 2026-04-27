"""Decision-table state machine for the :class:`ExternalReviewGate` aggregate.

Implements ``docs/features/external-review-gate/detailed-design.md``
§確定 B (state machine table lock) and §確定 A (Method x
current_decision dispatch table). The contract is intentionally a
**flat ``Mapping[(ReviewDecision, str), ReviewDecision]``** rather
than an ``if-elif`` ladder so:

1. The exact set of allowed transitions is enumerable in one
   structure — code review can compare it against §確定 A's
   16-cell dispatch table (4 method x 4 state) at a glance.
2. The lookup function refuses unknown ``(decision, action)`` pairs
   with ``KeyError`` so the caller wraps the failure in
   :class:`ExternalReviewGateInvariantViolation(kind='decision_already_decided')`
   — Fail-Fast on illegal ``approve`` / ``reject`` / ``cancel`` calls
   against a Gate that is no longer PENDING.
3. ``Final[Mapping]`` + :func:`types.MappingProxyType` makes both
   pyright (re-assignment detection) and the runtime (``setitem``
   rejection) refuse to mutate the table after import. A future PR
   that wants to add a transition has to edit *this* file plus the
   corresponding test.

The 7 entries below correspond 1:1 with the ``→`` cells in §確定 A's
dispatch table:

* ``PENDING`` → ``approve`` / ``reject`` / ``cancel`` (the three
  decision-emitting actions, terminating to APPROVED / REJECTED /
  CANCELLED respectively).
* ``record_view`` self-loops on **every** decision value (PENDING,
  APPROVED, REJECTED, CANCELLED) — auditing a decided Gate is
  legitimate (§確定 G "誰がいつ何度見たか"). The four self-loops are
  enumerated explicitly so test side can mirror the dispatch table
  and a future PR cannot silently restrict ``record_view`` to a
  subset.

The remaining 9 illegal cells (PENDING-only actions invoked on a
non-PENDING Gate) hit ``KeyError`` on lookup and translate to
``decision_already_decided`` (MSG-GT-001) at the Aggregate boundary.

``action`` is constrained at the type level by :data:`GateAction` so
typo-driven typos (``'approv'`` etc.) are caught by pyright strict
before they reach runtime. The 4 ``Literal`` values mirror the 4
:class:`ExternalReviewGate` methods one-for-one — adding a method
without updating this list (or vice versa) is a type error.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal

from bakufu.domain.value_objects import ReviewDecision

type GateAction = Literal[
    "approve",
    "reject",
    "cancel",
    "record_view",
]
"""Closed set of action names matching :class:`ExternalReviewGate`
method names 1:1.

Per §確定 A (task #42 §確定 A-2 パターン継承), Gate methods do **not**
dispatch on runtime values. Each method calls
``state_machine.lookup(self.decision, '<method_name>')`` so the action
name is a compile-time string literal — the table lookup result and
the method's behavior are statically tied together.
"""


_TRANSITIONS: Mapping[tuple[ReviewDecision, GateAction], ReviewDecision] = MappingProxyType(
    {
        # PENDING — the three decision-emitting transitions plus the
        # record_view self-loop. After any of approve / reject / cancel
        # the Gate is terminal for those three actions.
        (ReviewDecision.PENDING, "approve"): ReviewDecision.APPROVED,
        (ReviewDecision.PENDING, "reject"): ReviewDecision.REJECTED,
        (ReviewDecision.PENDING, "cancel"): ReviewDecision.CANCELLED,
        (ReviewDecision.PENDING, "record_view"): ReviewDecision.PENDING,
        # APPROVED / REJECTED / CANCELLED — only ``record_view`` is
        # legal so the Gate's audit trail can keep tracking late
        # readers. The four self-loops are enumerated rather than
        # inferred so the dispatch table mirrors the implementation
        # exactly (§確定 A §"4 行明示列挙する根拠").
        (ReviewDecision.APPROVED, "record_view"): ReviewDecision.APPROVED,
        (ReviewDecision.REJECTED, "record_view"): ReviewDecision.REJECTED,
        (ReviewDecision.CANCELLED, "record_view"): ReviewDecision.CANCELLED,
    }
)
"""Read-only view of the canonical 7-entry transition map.

Wrapping the underlying ``dict`` in :class:`types.MappingProxyType`
makes ``_TRANSITIONS[k] = v`` raise ``TypeError`` at runtime even
when somebody `cast`s the table. ``Final`` blocks re-assignment of
the symbol itself in pyright strict mode.
"""

TRANSITIONS: Final[Mapping[tuple[ReviewDecision, GateAction], ReviewDecision]] = _TRANSITIONS
"""Public alias for the transition table.

Tests import this to assert the table size (``len(TRANSITIONS) == 7``)
and to walk every legal transition without going through ``lookup``.
The :class:`MappingProxyType` wrapper still applies, so code that
imports it cannot mutate it.
"""


def lookup(current_decision: ReviewDecision, action: GateAction) -> ReviewDecision:
    """Return the allowed ``next_decision`` for ``(current_decision, action)``.

    Raises:
        KeyError: when the pair is not in the canonical transition
            table. The :class:`ExternalReviewGate` aggregate catches
            this and re-raises as
            :class:`ExternalReviewGateInvariantViolation(kind='decision_already_decided')`
            with the original / attempted decision attached for
            diagnostics — that translation lives in ``gate.py`` so
            this module stays free of the exception package import
            cycle.
    """
    return _TRANSITIONS[(current_decision, action)]


def allowed_actions_from(current_decision: ReviewDecision) -> list[GateAction]:
    """Return the subset of actions legal from ``current_decision``.

    Used by :class:`ExternalReviewGate` to populate the
    ``allowed_actions`` field of MSG-GT-001 so the human-readable
    next-action hint surfaces *which* transitions would have worked.
    Returned in stable insertion order (Python 3.7+ dict iteration)
    so test snapshots stay deterministic.
    """
    return [action for (decision, action) in _TRANSITIONS if decision == current_decision]


__all__ = [
    "TRANSITIONS",
    "GateAction",
    "allowed_actions_from",
    "lookup",
]
