"""Task Aggregate Root package.

Implements ``REQ-TS-001``〜``REQ-TS-009`` per ``docs/features/task``.
M1 6 兄弟目 (after empire / workflow / agent / room / directive). The
package is split along the responsibility lines that the design
calls out:

* :mod:`bakufu.domain.task.state_machine` — decision-table state
  machine (``Final[Mapping]`` + :class:`types.MappingProxyType`,
  §確定 B). 13 entries matching §確定 A-2's dispatch table 1:1.
* :mod:`bakufu.domain.task.aggregate_validators` — five module-level
  ``_validate_*`` helpers for the structural invariants (§確定 J
  kinds 3〜7).
* :mod:`bakufu.domain.task.task` — :class:`Task` Aggregate Root
  exposing ten behavior methods whose names map 1:1 to the state
  machine action names (§確定 A-2 Steve R2 凍結 — no internal
  dispatch, no ``advance(...)`` umbrella method).

This ``__init__`` re-exports the public surface plus the
underscore-prefixed validators tests need to invoke directly (the
same pattern Norman approved for the agent / room / directive
packages).
"""

from __future__ import annotations

from bakufu.domain.task.aggregate_validators import (
    MAX_ASSIGNED_AGENTS,
    MAX_LAST_ERROR_LENGTH,
    MIN_LAST_ERROR_LENGTH,
    _validate_assigned_agents_capacity,
    _validate_assigned_agents_unique,
    _validate_blocked_has_last_error,
    _validate_last_error_consistency,
    _validate_timestamp_order,
)
from bakufu.domain.task.state_machine import (
    TRANSITIONS,
    TaskAction,
    allowed_actions_from,
    lookup,
)
from bakufu.domain.task.task import Task

__all__ = [
    "MAX_ASSIGNED_AGENTS",
    "MAX_LAST_ERROR_LENGTH",
    "MIN_LAST_ERROR_LENGTH",
    "TRANSITIONS",
    "Task",
    "TaskAction",
    "_validate_assigned_agents_capacity",
    "_validate_assigned_agents_unique",
    "_validate_blocked_has_last_error",
    "_validate_last_error_consistency",
    "_validate_timestamp_order",
    "allowed_actions_from",
    "lookup",
]
