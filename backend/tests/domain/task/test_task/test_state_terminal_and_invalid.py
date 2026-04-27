"""Task state machine: 47 illegal cells (20 terminal + 27 non-terminal).

TC-UT-TS-005 / 006 (DONE / CANCELLED x 10 method = 20 terminal ✗
cells, MSG-TS-001) + TC-UT-TS-004 (27 non-terminal ✗ cells,
MSG-TS-002).

The §確定 A-2 (Steve R2 凍結) 60-cell dispatch table splits as
13 ✓ + 20 terminal ✗ + 27 illegal-non-terminal ✗. The 13 ✓ cells live
in :mod:`...test_task.test_state_machine_table`; this file pins the
**47 ✗ cells** so any future drift in the state machine table is
caught at the boundary that triggers a Fail-Fast for end users.

Per ``docs/features/task/test-design.md``. Split out of
``test_state_machine.py`` per Norman R-N1 (633 → 3 files).
"""

from __future__ import annotations

import pytest
from bakufu.domain.exceptions import TaskInvariantViolation
from bakufu.domain.task.state_machine import TRANSITIONS, TaskAction
from bakufu.domain.value_objects import TaskStatus

from tests.domain.task.test_task._helpers import (
    ALL_ACTIONS,
    ALL_STATUSES,
    invoke_action,
    make_task_in_status,
)
from tests.factories.task import make_cancelled_task, make_done_task


# ---------------------------------------------------------------------------
# TC-UT-TS-005 + TC-UT-TS-006: DONE / CANCELLED terminal — all 10 raise
# ---------------------------------------------------------------------------
class TestTerminalGate:
    """20 ✗ cells: DONE x 10 + CANCELLED x 10 → ``terminal_violation`` (MSG-TS-001)."""

    @pytest.mark.parametrize("action", ALL_ACTIONS, ids=lambda a: a)
    def test_done_rejects_every_action(self, action: TaskAction) -> None:
        """TC-UT-TS-005: every action on a DONE Task raises terminal_violation."""
        task = make_done_task()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            invoke_action(task, action)
        assert exc_info.value.kind == "terminal_violation"

    @pytest.mark.parametrize("action", ALL_ACTIONS, ids=lambda a: a)
    def test_cancelled_rejects_every_action(self, action: TaskAction) -> None:
        """TC-UT-TS-006: every action on a CANCELLED Task raises terminal_violation."""
        task = make_cancelled_task()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            invoke_action(task, action)
        assert exc_info.value.kind == "terminal_violation"


# ---------------------------------------------------------------------------
# TC-UT-TS-004: 27 ✗ non-terminal cells → state_transition_invalid
# ---------------------------------------------------------------------------
class TestEveryIllegalNonTerminalCellRaises:
    """27 ✗ cells: non-terminal-status x action with no transition → MSG-TS-002.

    The 60-cell matrix splits as: 13 ✓ + 20 terminal ✗ (DONE/CANCELLED x
    10) + 27 ✗ non-terminal (4 statuses x 10 actions - 13 allowed). We
    walk each non-terminal status x action pair and skip the 13 allowed
    transitions; the remaining 27 must raise
    ``state_transition_invalid``.
    """

    @pytest.mark.parametrize("status", ALL_STATUSES, ids=lambda s: s.value)
    @pytest.mark.parametrize("action", ALL_ACTIONS, ids=lambda a: a)
    def test_illegal_cell_raises_state_transition_invalid(
        self,
        status: TaskStatus,
        action: TaskAction,
    ) -> None:
        """Each illegal non-terminal ``(status, action)`` pair raises MSG-TS-002.

        Skip the 13 ✓ cells (they have their own positive tests in
        ``test_state_machine_table``) and the 20 terminal ✗ cells
        (covered by ``TestTerminalGate`` above — terminal_violation
        fires first, not state_transition_invalid).
        """
        if (status, action) in TRANSITIONS:
            return  # ✓ cell — covered by TestThirteenAllowedTransitions
        if status in (TaskStatus.DONE, TaskStatus.CANCELLED):
            return  # ✗ terminal — covered by TestTerminalGate

        task = make_task_in_status(status)
        with pytest.raises(TaskInvariantViolation) as exc_info:
            invoke_action(task, action)
        assert exc_info.value.kind == "state_transition_invalid", (
            f"[FAIL] illegal cell ({status.value}, {action}) raised "
            f"{exc_info.value.kind!r}, expected 'state_transition_invalid'.\n"
            f"Next: ensure non-terminal illegal cells route through "
            f"_lookup_or_raise → state_transition_invalid (MSG-TS-002)."
        )
