"""Decision-table state machine for the :class:`Task` aggregate.

Implements ``docs/features/task/detailed-design.md`` §確定 B (state
machine table lock) and §確定 A-2 (Method x current_status ->
action 名 dispatch table). The contract is intentionally a **flat
``Mapping[(TaskStatus, str), TaskStatus]``** rather than an
``if-elif`` ladder so:

1. The exact set of allowed transitions is **enumerable in one
   structure** — code review can compare it against §確定 A-2's
   60-cell dispatch table at a glance.
2. The lookup function refuses unknown ``(status, action)`` pairs
   with ``KeyError`` so the caller (``Task.<method>``) wraps the
   failure in :class:`TaskInvariantViolation(kind='state_transition_invalid')`
   — Fail-Fast on illegal state-machine bypass attempts.
3. ``Final[Mapping]`` + :func:`types.MappingProxyType` makes both
   pyright (re-assignment detection) and the runtime (``setitem``
   rejection) refuse to mutate the table after import. A future PR
   that wants to add a transition has to edit *this* file plus the
   corresponding test, matching the design's "physical lock" intent.

The 13 entries below correspond 1:1 with the ``→`` cells in
§確定 A-2's dispatch table:

* ``PENDING``        — assign / cancel
* ``IN_PROGRESS``    — commit_deliverable / request_external_review /
                       advance_to_next / complete / block / cancel
* ``AWAITING_EXTERNAL_REVIEW`` — approve_review / reject_review / cancel
* ``BLOCKED``        — unblock_retry / cancel
* ``DONE`` / ``CANCELLED`` — terminal, **no entries** (60 - 13 = 47
                              illegal cells, of which DONE/CANCELLED's
                              20 hit the terminal_violation gate first;
                              the remaining 27 hit ``state_transition_invalid``).

``action`` is constrained at the type level by :data:`TaskAction` so
typo-driven typos (``'aproove_review'`` etc.) are caught by pyright
strict before they reach runtime. The 10 ``Literal`` values mirror the
10 Task methods one-for-one — adding a method without updating this
list (or vice versa) is a type error.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal

from bakufu.domain.value_objects import TaskStatus

type TaskAction = Literal[
    "assign",
    "commit_deliverable",
    "request_external_review",
    "approve_review",
    "reject_review",
    "advance_to_next",
    "complete",
    "block",
    "unblock_retry",
    "cancel",
]
"""Closed set of action names matching :class:`Task` method names 1:1.

Per §確定 A-2 (Steve R2 凍結), Task methods do **not** dispatch on
runtime values. Each method calls
``state_machine.lookup(self.status, '<method_name>')`` so the action
name is a compile-time string literal — the table lookup result and
the method's behavior are statically tied together.
"""


_TRANSITIONS: Mapping[tuple[TaskStatus, TaskAction], TaskStatus] = MappingProxyType(
    {
        # PENDING — only ``assign`` / ``cancel`` are reachable.
        (TaskStatus.PENDING, "assign"): TaskStatus.IN_PROGRESS,
        (TaskStatus.PENDING, "cancel"): TaskStatus.CANCELLED,
        # IN_PROGRESS — six legal actions including the two self-loops
        # (``commit_deliverable`` / ``advance_to_next``) that update
        # ``deliverables`` / ``current_stage_id`` without changing status.
        (TaskStatus.IN_PROGRESS, "commit_deliverable"): TaskStatus.IN_PROGRESS,
        (TaskStatus.IN_PROGRESS, "request_external_review"): TaskStatus.AWAITING_EXTERNAL_REVIEW,
        (TaskStatus.IN_PROGRESS, "advance_to_next"): TaskStatus.IN_PROGRESS,
        (TaskStatus.IN_PROGRESS, "complete"): TaskStatus.DONE,
        (TaskStatus.IN_PROGRESS, "block"): TaskStatus.BLOCKED,
        (TaskStatus.IN_PROGRESS, "cancel"): TaskStatus.CANCELLED,
        # AWAITING_EXTERNAL_REVIEW — Gate decision dispatch is application-side.
        # The two specialised methods replace the older single ``advance``
        # method (§確定 A-2 採用 (B)), which kept Task ignorant of the
        # ``ReviewDecision`` Aggregate VO across the boundary.
        (TaskStatus.AWAITING_EXTERNAL_REVIEW, "approve_review"): TaskStatus.IN_PROGRESS,
        (TaskStatus.AWAITING_EXTERNAL_REVIEW, "reject_review"): TaskStatus.IN_PROGRESS,
        (TaskStatus.AWAITING_EXTERNAL_REVIEW, "cancel"): TaskStatus.CANCELLED,
        # BLOCKED — only retry / cancel reactivate the lifecycle.
        (TaskStatus.BLOCKED, "unblock_retry"): TaskStatus.IN_PROGRESS,
        (TaskStatus.BLOCKED, "cancel"): TaskStatus.CANCELLED,
    }
)
"""Read-only view of the canonical 13-entry transition map.

Wrapping the underlying ``dict`` in :class:`types.MappingProxyType`
makes ``_TRANSITIONS[k] = v`` raise ``TypeError`` at runtime even
when somebody `cast`s the table. ``Final`` blocks re-assignment of
the symbol itself in pyright strict mode. Together they enforce the
"after import the table is frozen" contract end-to-end.
"""

TRANSITIONS: Final[Mapping[tuple[TaskStatus, TaskAction], TaskStatus]] = _TRANSITIONS
"""Public alias for the transition table.

Tests import this to assert the table size (``len(TRANSITIONS) == 13``)
and to walk every legal transition without going through ``lookup``.
The :class:`MappingProxyType` wrapper still applies, so code that
imports it cannot mutate it.
"""


def lookup(current_status: TaskStatus, action: TaskAction) -> TaskStatus:
    """Return the allowed ``next_status`` for ``(current_status, action)``.

    Raises:
        KeyError: when the pair is not in the canonical transition
            table. The :class:`Task` aggregate catches this and
            re-raises as
            :class:`TaskInvariantViolation(kind='state_transition_invalid')`
            with the ``allowed_actions`` list attached for
            diagnostics — that translation lives in ``task.py`` so
            this module stays free of the exception package import
            cycle.
    """
    return _TRANSITIONS[(current_status, action)]


def allowed_actions_from(current_status: TaskStatus) -> list[TaskAction]:
    """Return the subset of actions legal from ``current_status``.

    Used by :class:`Task` to populate the ``allowed_actions`` field
    of MSG-TS-002 so the human-readable next-action hint surfaces
    *which* transitions would have worked. Returned in stable
    insertion order (Python 3.7+ dict iteration) so test snapshots
    stay deterministic.
    """
    return [action for (status, action) in _TRANSITIONS if status == current_status]


__all__ = [
    "TRANSITIONS",
    "TaskAction",
    "allowed_actions_from",
    "lookup",
]
