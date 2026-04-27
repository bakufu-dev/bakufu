"""Task state machine: table lock + 13 allowed transitions.

TC-UT-TS-039 (§確定 B table immutability) + TC-UT-TS-003 / 008 /
030〜035 + cancel x 4 (§確定 A-2 dispatch table 13 ✓ cells).

Per ``docs/features/task/test-design.md``. Split out of
``test_state_machine.py`` per Norman R-N1 (633 → 3 files). Sibling
files cover the **47 ✗ cells** and the **lifecycle integration**:

* :mod:`...test_task.test_state_terminal_and_invalid` — 20 terminal
  ✗ + 27 illegal-non-terminal ✗ cells (MSG-TS-001 / MSG-TS-002).
* :mod:`...test_task.test_state_lifecycle` — BLOCKED contract +
  pre-validate + multi-method integration scenarios + updated_at
  monotonicity.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.task import Task
from bakufu.domain.task.state_machine import TRANSITIONS
from bakufu.domain.value_objects import Deliverable, TaskStatus

from tests.domain.task.test_task._helpers import (
    make_task_in_status,
    next_ts,
)
from tests.factories.task import (
    make_blocked_task,
    make_deliverable,
    make_in_progress_task,
    make_task,
)


# ---------------------------------------------------------------------------
# §確定 B: state machine TABLE shape + immutability (TC-UT-TS-039)
# ---------------------------------------------------------------------------
class TestStateMachineTableLocked:
    """TC-UT-TS-039: ``TRANSITIONS`` has 13 entries and rejects mutation."""

    def test_table_size_is_thirteen(self) -> None:
        """The §確定 A-2 dispatch table freezes 13 allowed transitions."""
        assert len(TRANSITIONS) == 13, (
            f"[FAIL] state machine table size drifted: got {len(TRANSITIONS)}, expected 13.\n"
            f"Next: docs/features/task/detailed-design.md §確定 A-2 freezes 13 transitions; "
            f"editing state_machine.py without updating the design is a contract break."
        )

    def test_table_setitem_rejected_at_runtime(self) -> None:
        """``TRANSITIONS[k] = v`` raises ``TypeError`` (MappingProxyType lock)."""
        with pytest.raises(TypeError):
            TRANSITIONS[(TaskStatus.DONE, "assign")] = TaskStatus.IN_PROGRESS  # pyright: ignore[reportIndexIssue]


# ---------------------------------------------------------------------------
# 13 allowed transitions — one positive case per ✓ cell
# ---------------------------------------------------------------------------
class TestThirteenAllowedTransitions:
    """TC-UT-TS-003 / 008 / 030〜035 + cancel x 4 = 13 ✓ cells."""

    # PENDING → IN_PROGRESS via assign
    def test_assign_pending_to_in_progress(self) -> None:
        """TC-UT-TS-003: ``assign`` on PENDING moves to IN_PROGRESS."""
        task = make_task()
        agent_a = uuid4()
        out = task.assign([agent_a], updated_at=next_ts(task))
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.assigned_agent_ids == [agent_a]
        # original task unchanged (frozen + pre-validate)
        assert task.status == TaskStatus.PENDING

    # IN_PROGRESS self-loop via commit_deliverable
    def test_commit_deliverable_self_loop(self) -> None:
        """TC-UT-TS-030: ``commit_deliverable`` on IN_PROGRESS keeps status, adds entry."""
        task = make_in_progress_task()
        deliverable = make_deliverable(stage_id=task.current_stage_id)
        out = task.commit_deliverable(
            stage_id=task.current_stage_id,
            deliverable=deliverable,
            by_agent_id=task.assigned_agent_ids[0],
            updated_at=next_ts(task),
        )
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.deliverables[task.current_stage_id] == deliverable
        assert out.updated_at > task.updated_at

    # IN_PROGRESS → AWAITING via request_external_review
    def test_request_external_review_to_awaiting(self) -> None:
        """TC-UT-TS-031: IN_PROGRESS → AWAITING_EXTERNAL_REVIEW."""
        task = make_in_progress_task()
        out = task.request_external_review(updated_at=next_ts(task))
        assert out.status == TaskStatus.AWAITING_EXTERNAL_REVIEW

    # AWAITING → IN_PROGRESS via approve_review (Gate APPROVED)
    def test_approve_review_back_to_in_progress(self) -> None:
        """TC-UT-TS-032: ``approve_review`` advances current_stage_id."""
        task = make_task_in_status(TaskStatus.AWAITING_EXTERNAL_REVIEW)
        next_stage = uuid4()
        out = task.approve_review(uuid4(), uuid4(), next_stage, updated_at=next_ts(task))
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.current_stage_id == next_stage

    # AWAITING → IN_PROGRESS via reject_review (Gate REJECTED)
    def test_reject_review_back_to_in_progress(self) -> None:
        """TC-UT-TS-032b: ``reject_review`` rolls current_stage_id back."""
        task = make_task_in_status(TaskStatus.AWAITING_EXTERNAL_REVIEW)
        rollback_stage = uuid4()
        out = task.reject_review(uuid4(), uuid4(), rollback_stage, updated_at=next_ts(task))
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.current_stage_id == rollback_stage

    # IN_PROGRESS self-loop via advance_to_next
    def test_advance_to_next_keeps_in_progress(self) -> None:
        """TC-UT-TS-032c: ``advance_to_next`` updates current_stage_id, status unchanged."""
        task = make_in_progress_task()
        next_stage = uuid4()
        out = task.advance_to_next(uuid4(), uuid4(), next_stage, updated_at=next_ts(task))
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.current_stage_id == next_stage

    # IN_PROGRESS → DONE via complete
    def test_complete_terminates_at_done(self) -> None:
        """TC-UT-TS-033: ``complete`` is the terminal transition.

        ``current_stage_id`` is intentionally left as-is so downstream
        consumers can read the last Stage.
        """
        task = make_in_progress_task()
        original_stage = task.current_stage_id
        out = task.complete(uuid4(), uuid4(), updated_at=next_ts(task))
        assert out.status == TaskStatus.DONE
        assert out.current_stage_id == original_stage

    # IN_PROGRESS → BLOCKED via block
    def test_block_attaches_last_error(self) -> None:
        """TC-UT-TS-035: ``block`` requires non-empty last_error."""
        task = make_in_progress_task()
        out = task.block("auth retry exhausted", "AuthExpired: ...", updated_at=next_ts(task))
        assert out.status == TaskStatus.BLOCKED
        assert out.last_error == "AuthExpired: ..."

    # BLOCKED → IN_PROGRESS via unblock_retry, last_error cleared (§確定 D)
    def test_unblock_retry_clears_last_error(self) -> None:
        """TC-UT-TS-008: ``unblock_retry`` clears last_error to None (§確定 D)."""
        task = make_blocked_task(last_error="AuthExpired: synthetic")
        out = task.unblock_retry(updated_at=next_ts(task))
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.last_error is None

    # cancel from each of the 4 non-terminal states (§確定 E)
    @pytest.mark.parametrize(
        "starting_status",
        [
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.AWAITING_EXTERNAL_REVIEW,
            TaskStatus.BLOCKED,
        ],
        ids=lambda s: s.value,
    )
    def test_cancel_from_each_of_four_states(self, starting_status: TaskStatus) -> None:
        """TC-UT-TS-034: ``cancel`` reaches CANCELLED from PENDING/IN_PROG/AWAITING/BLOCKED.

        §確定 E enumerates exactly these 4 starting states; ``last_error``
        is reset to None to keep the consistency invariant happy.
        """
        task = make_task_in_status(starting_status)
        out = task.cancel(uuid4(), "manual abort", updated_at=next_ts(task))
        assert out.status == TaskStatus.CANCELLED
        assert out.last_error is None


# Importing Deliverable / Task to use type checkers downstream
_ = Deliverable, Task
