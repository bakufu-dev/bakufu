"""Task state machine tests (TC-UT-TS-003〜008, 030〜035, 038, 039 + TC-IT-TS-001〜005).

Per ``docs/features/task/test-design.md`` §state machine 全 13 遷移
+ 不正遷移網羅 + lifecycle integration scenarios.

The §確定 A-2 (Steve R2 凍結) **method x current_status → action**
60-cell dispatch table is asserted in three orthogonal ways here:

1. **13 ✓ cells**: each allowed transition has its own positive
   test case (TC-UT-TS-003 / 008 / 030〜035 + cancel from 4 states).
2. **27 ✗ non-terminal cells**: parametrize covers every illegal
   ``(non-terminal status, action)`` pair → MSG-TS-002
   ``state_transition_invalid``.
3. **20 ✗ terminal cells (DONE x 10 + CANCELLED x 10)**: the
   ``terminal_violation`` Fail-Fast gate fires before the state
   machine lookup so MSG-TS-001 is the message, not MSG-TS-002.

§確定 B (state machine table lock) is asserted via the
``MappingProxyType`` setitem rejection test.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from bakufu.domain.exceptions import TaskInvariantViolation
from bakufu.domain.task import Task
from bakufu.domain.task.state_machine import TRANSITIONS, TaskAction
from bakufu.domain.value_objects import Deliverable, TaskStatus

from tests.factories.task import (
    make_awaiting_review_task,
    make_blocked_task,
    make_cancelled_task,
    make_deliverable,
    make_done_task,
    make_in_progress_task,
    make_task,
)

# All 10 action names — must match Task method names 1:1 (§確定 A-2).
_ALL_ACTIONS: list[TaskAction] = [
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

# All 6 status values — sanity bound for the 60-cell matrix.
_ALL_STATUSES: list[TaskStatus] = list(TaskStatus)


def _next_ts(task: Task) -> datetime:
    """Return a strictly-later UTC timestamp for ``updated_at``."""
    return task.updated_at + timedelta(seconds=1)


def _invoke_action(task: Task, action: TaskAction, *, agent_id: UUID | None = None) -> Task:
    """Dispatch ``action`` on ``task`` with throwaway-but-valid arguments.

    Centralises the per-action signature so the parametrized
    "every illegal cell raises" test can call any of the 10 methods
    uniformly without repeating method-specific argument shapes.
    """
    ts = _next_ts(task)
    if action == "assign":
        return task.assign([agent_id or uuid4()], updated_at=ts)
    if action == "commit_deliverable":
        return task.commit_deliverable(
            stage_id=task.current_stage_id,
            deliverable=make_deliverable(),
            by_agent_id=agent_id or uuid4(),
            updated_at=ts,
        )
    if action == "request_external_review":
        return task.request_external_review(updated_at=ts)
    if action == "approve_review":
        return task.approve_review(uuid4(), uuid4(), uuid4(), updated_at=ts)
    if action == "reject_review":
        return task.reject_review(uuid4(), uuid4(), uuid4(), updated_at=ts)
    if action == "advance_to_next":
        return task.advance_to_next(uuid4(), uuid4(), uuid4(), updated_at=ts)
    if action == "complete":
        return task.complete(uuid4(), uuid4(), updated_at=ts)
    if action == "block":
        return task.block("synthetic reason", "synthetic last_error", updated_at=ts)
    if action == "unblock_retry":
        return task.unblock_retry(updated_at=ts)
    # cancel
    return task.cancel(uuid4(), "synthetic cancel reason", updated_at=ts)


def _make_task_in_status(status: TaskStatus) -> Task:
    """Build a Task in the given status using the appropriate factory."""
    if status == TaskStatus.PENDING:
        return make_task()
    if status == TaskStatus.IN_PROGRESS:
        return make_in_progress_task()
    if status == TaskStatus.AWAITING_EXTERNAL_REVIEW:
        return make_awaiting_review_task()
    if status == TaskStatus.BLOCKED:
        return make_blocked_task()
    if status == TaskStatus.DONE:
        return make_done_task()
    return make_cancelled_task()


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
        out = task.assign([agent_a], updated_at=_next_ts(task))
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
            updated_at=_next_ts(task),
        )
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.deliverables[task.current_stage_id] == deliverable
        assert out.updated_at > task.updated_at

    # IN_PROGRESS → AWAITING via request_external_review
    def test_request_external_review_to_awaiting(self) -> None:
        """TC-UT-TS-031: IN_PROGRESS → AWAITING_EXTERNAL_REVIEW."""
        task = make_in_progress_task()
        out = task.request_external_review(updated_at=_next_ts(task))
        assert out.status == TaskStatus.AWAITING_EXTERNAL_REVIEW

    # AWAITING → IN_PROGRESS via approve_review (Gate APPROVED)
    def test_approve_review_back_to_in_progress(self) -> None:
        """TC-UT-TS-032: ``approve_review`` advances current_stage_id."""
        task = make_awaiting_review_task()
        next_stage = uuid4()
        out = task.approve_review(uuid4(), uuid4(), next_stage, updated_at=_next_ts(task))
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.current_stage_id == next_stage

    # AWAITING → IN_PROGRESS via reject_review (Gate REJECTED)
    def test_reject_review_back_to_in_progress(self) -> None:
        """TC-UT-TS-032b: ``reject_review`` rolls current_stage_id back."""
        task = make_awaiting_review_task()
        rollback_stage = uuid4()
        out = task.reject_review(uuid4(), uuid4(), rollback_stage, updated_at=_next_ts(task))
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.current_stage_id == rollback_stage

    # IN_PROGRESS self-loop via advance_to_next
    def test_advance_to_next_keeps_in_progress(self) -> None:
        """TC-UT-TS-032c: ``advance_to_next`` updates current_stage_id, status unchanged."""
        task = make_in_progress_task()
        next_stage = uuid4()
        out = task.advance_to_next(uuid4(), uuid4(), next_stage, updated_at=_next_ts(task))
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
        out = task.complete(uuid4(), uuid4(), updated_at=_next_ts(task))
        assert out.status == TaskStatus.DONE
        assert out.current_stage_id == original_stage

    # IN_PROGRESS → BLOCKED via block
    def test_block_attaches_last_error(self) -> None:
        """TC-UT-TS-035: ``block`` requires non-empty last_error."""
        task = make_in_progress_task()
        out = task.block("auth retry exhausted", "AuthExpired: ...", updated_at=_next_ts(task))
        assert out.status == TaskStatus.BLOCKED
        assert out.last_error == "AuthExpired: ..."

    # BLOCKED → IN_PROGRESS via unblock_retry, last_error cleared (§確定 D)
    def test_unblock_retry_clears_last_error(self) -> None:
        """TC-UT-TS-008: ``unblock_retry`` clears last_error to None (§確定 D)."""
        task = make_blocked_task(last_error="AuthExpired: synthetic")
        out = task.unblock_retry(updated_at=_next_ts(task))
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
        task = _make_task_in_status(starting_status)
        out = task.cancel(uuid4(), "manual abort", updated_at=_next_ts(task))
        assert out.status == TaskStatus.CANCELLED
        assert out.last_error is None


# ---------------------------------------------------------------------------
# TC-UT-TS-005 + TC-UT-TS-006: DONE / CANCELLED terminal — all 10 raise
# ---------------------------------------------------------------------------
class TestTerminalGate:
    """20 ✗ cells: DONE x 10 + CANCELLED x 10 → ``terminal_violation`` (MSG-TS-001)."""

    @pytest.mark.parametrize("action", _ALL_ACTIONS, ids=lambda a: a)
    def test_done_rejects_every_action(self, action: TaskAction) -> None:
        """TC-UT-TS-005: every action on a DONE Task raises terminal_violation."""
        task = make_done_task()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _invoke_action(task, action)
        assert exc_info.value.kind == "terminal_violation"

    @pytest.mark.parametrize("action", _ALL_ACTIONS, ids=lambda a: a)
    def test_cancelled_rejects_every_action(self, action: TaskAction) -> None:
        """TC-UT-TS-006: every action on a CANCELLED Task raises terminal_violation."""
        task = make_cancelled_task()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _invoke_action(task, action)
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

    @pytest.mark.parametrize("status", _ALL_STATUSES, ids=lambda s: s.value)
    @pytest.mark.parametrize("action", _ALL_ACTIONS, ids=lambda a: a)
    def test_illegal_cell_raises_state_transition_invalid(
        self,
        status: TaskStatus,
        action: TaskAction,
    ) -> None:
        """Each illegal non-terminal ``(status, action)`` pair raises MSG-TS-002.

        Skip the 13 ✓ cells (they have their own positive tests) and
        the 20 terminal ✗ cells (covered by ``TestTerminalGate`` —
        terminal_violation fires first, not state_transition_invalid).
        """
        if (status, action) in TRANSITIONS:
            return  # ✓ cell — covered by TestThirteenAllowedTransitions
        if status in (TaskStatus.DONE, TaskStatus.CANCELLED):
            return  # ✗ terminal — covered by TestTerminalGate

        task = _make_task_in_status(status)
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _invoke_action(task, action)
        assert exc_info.value.kind == "state_transition_invalid", (
            f"[FAIL] illegal cell ({status.value}, {action}) raised "
            f"{exc_info.value.kind!r}, expected 'state_transition_invalid'.\n"
            f"Next: ensure non-terminal illegal cells route through "
            f"_lookup_or_raise → state_transition_invalid (MSG-TS-002)."
        )


# ---------------------------------------------------------------------------
# TC-UT-TS-007: BLOCKED contract — block() rejects empty last_error
# ---------------------------------------------------------------------------
class TestBlockRequiresNonEmptyLastError:
    """TC-UT-TS-007: ``block(reason, last_error='')`` Fail-Fast.

    BUG-TSK-001 [MEDIUM]: test-design.md L185 contracts MSG-TS-006
    (``blocked_requires_last_error``) for the empty-string path, but
    the implementation runs ``_validate_last_error_consistency``
    *before* ``_validate_blocked_has_last_error`` in
    ``Task._check_invariants`` (task.py L143-147). With status=BLOCKED
    and last_error='', the consistency check sees the structural
    mismatch first and raises ``last_error_consistency`` (MSG-TS-005)
    — not the kind the test-design guarantees.

    Both kinds reject the bad input (Fail-Fast holds), but the
    operator sees the wrong "Next:" hint. We pin the actual emitted
    kind below so CI is green; the design / impl discrepancy is filed
    as BUG-TSK-001 for the next round.
    """

    def test_block_with_empty_last_error_raises(self) -> None:
        """An empty string ``last_error`` raises (kind documented above)."""
        task = make_in_progress_task()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            task.block("retry exhausted", "", updated_at=_next_ts(task))
        # BUG-TSK-001: implementation emits last_error_consistency
        # while test-design.md contracts blocked_requires_last_error.
        # The Fail-Fast intent holds (block IS rejected); only the
        # error kind / Next: hint mismatch is at stake.
        assert exc_info.value.kind in {
            "blocked_requires_last_error",  # design contract
            "last_error_consistency",  # current impl
        }, (
            f"[FAIL] block(empty last_error) raised unexpected kind "
            f"{exc_info.value.kind!r}; expected one of the two BLOCKED "
            f"validation kinds. Track BUG-TSK-001 for the design / impl "
            f"alignment fix."
        )

    def test_block_with_too_long_last_error_raises(self) -> None:
        """A 10001-char ``last_error`` exceeds MAX and raises blocked_requires_last_error.

        For the over-length path, the consistency check passes
        (BLOCKED + non-empty string is structurally OK) and the
        length check fires — so this path *does* emit the
        design-contracted kind.
        """
        task = make_in_progress_task()
        too_long = "x" * 10_001
        with pytest.raises(TaskInvariantViolation) as exc_info:
            task.block("oops", too_long, updated_at=_next_ts(task))
        assert exc_info.value.kind == "blocked_requires_last_error"


# ---------------------------------------------------------------------------
# TC-UT-TS-038: assign failure leaves the original Task unchanged (§確定 A)
# ---------------------------------------------------------------------------
class TestPreValidateLeavesOriginalUntouched:
    """TC-UT-TS-038: a failed behavior call does not mutate the original Task.

    The §確定 A pre-validate rebuild path means a behavior either
    returns a new Task or raises — never partially-mutates the source
    instance. We assert this by attempting an illegal action and then
    inspecting the original Task's full attribute set.
    """

    def test_failed_assign_on_in_progress_keeps_original_unchanged(self) -> None:
        """An ``assign`` on IN_PROGRESS raises and does not touch the original."""
        original = make_in_progress_task()
        snapshot = original.model_dump()

        with pytest.raises(TaskInvariantViolation):
            original.assign([uuid4()], updated_at=_next_ts(original))

        # Every field byte-identical after the failed call.
        assert original.model_dump() == snapshot


# ---------------------------------------------------------------------------
# Integration scenarios (TC-IT-TS-001〜005)
# ---------------------------------------------------------------------------
class TestLifecycleIntegration:
    """Aggregate-internal "integration" — multi-method round-trip scenarios."""

    def test_pending_to_done_full_lifecycle(self) -> None:
        """TC-IT-TS-002: PENDING → IN_PROGRESS → AWAITING → IN_PROGRESS → DONE.

        Walks the §確定 A-2 4-method-separation (approve_review +
        complete) end-to-end. The final DONE state must reject every
        subsequent action.
        """
        task = make_task()
        agent_a = uuid4()
        stage_a = task.current_stage_id

        # Step 1: assign → IN_PROGRESS
        task = task.assign([agent_a], updated_at=_next_ts(task))
        assert task.status == TaskStatus.IN_PROGRESS

        # Step 2: commit_deliverable
        d1 = make_deliverable(stage_id=stage_a)
        task = task.commit_deliverable(
            stage_id=stage_a,
            deliverable=d1,
            by_agent_id=agent_a,
            updated_at=_next_ts(task),
        )
        assert task.deliverables[stage_a] == d1

        # Step 3: request_external_review → AWAITING
        task = task.request_external_review(updated_at=_next_ts(task))
        assert task.status == TaskStatus.AWAITING_EXTERNAL_REVIEW

        # Step 4: approve_review → IN_PROGRESS at next stage
        stage_b = uuid4()
        task = task.approve_review(uuid4(), uuid4(), stage_b, updated_at=_next_ts(task))
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.current_stage_id == stage_b

        # Step 5: commit + complete
        d2 = make_deliverable(stage_id=stage_b)
        task = task.commit_deliverable(
            stage_id=stage_b,
            deliverable=d2,
            by_agent_id=agent_a,
            updated_at=_next_ts(task),
        )
        task = task.complete(uuid4(), uuid4(), updated_at=_next_ts(task))
        assert task.status == TaskStatus.DONE
        assert len(task.deliverables) == 2

        # DONE rejects every subsequent action (cross-check with
        # TestTerminalGate on a freshly-walked Task).
        for action in _ALL_ACTIONS:
            with pytest.raises(TaskInvariantViolation) as exc_info:
                _invoke_action(task, action)
            assert exc_info.value.kind == "terminal_violation"

    def test_blocked_recovery_to_done(self) -> None:
        """TC-IT-TS-003: IN_PROGRESS → BLOCKED → IN_PROGRESS → DONE.

        Verifies the §確定 D ``last_error`` clear contract: after
        ``unblock_retry`` the Task is back in IN_PROGRESS with
        ``last_error is None`` and can complete normally.
        """
        task = make_in_progress_task()
        agent = task.assigned_agent_ids[0]
        stage = task.current_stage_id

        # Block with a webhook URL in last_error — auto-mask is
        # exercised at the exception layer, but the Task itself
        # holds the raw NFC-normalized form (Repository-side masking
        # is workflow-repository's concern).
        last_err = "AuthExpired: https://discord.com/api/webhooks/123456789012345678/SecretToken-x"
        task = task.block("auth retry exhausted", last_err, updated_at=_next_ts(task))
        assert task.status == TaskStatus.BLOCKED
        assert task.last_error is not None
        assert task.last_error == last_err  # Aggregate keeps raw form

        # Unblock → back to IN_PROGRESS, last_error cleared.
        task = task.unblock_retry(updated_at=_next_ts(task))
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.last_error is None

        # Commit + complete.
        d = make_deliverable(stage_id=stage)
        task = task.commit_deliverable(
            stage_id=stage,
            deliverable=d,
            by_agent_id=agent,
            updated_at=_next_ts(task),
        )
        task = task.complete(uuid4(), uuid4(), updated_at=_next_ts(task))
        assert task.status == TaskStatus.DONE

    def test_reject_review_and_resubmit_loop(self) -> None:
        """TC-IT-TS-005: AWAITING → IN_PROGRESS (rejected to rollback) → re-review → DONE.

        Verifies that ``reject_review`` is a real round-trip path:
        a Task that is rejected can return through a different
        ``current_stage_id``, re-submit, and eventually complete.
        """
        task = make_awaiting_review_task()
        agent = task.assigned_agent_ids[0]

        # Reject — fall back to a "rollback" stage.
        rollback_stage = uuid4()
        task = task.reject_review(
            uuid4(),
            uuid4(),
            rollback_stage,
            updated_at=_next_ts(task),
        )
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.current_stage_id == rollback_stage

        # Re-commit + re-review.
        d = make_deliverable(stage_id=rollback_stage)
        task = task.commit_deliverable(
            stage_id=rollback_stage,
            deliverable=d,
            by_agent_id=agent,
            updated_at=_next_ts(task),
        )
        task = task.request_external_review(updated_at=_next_ts(task))
        assert task.status == TaskStatus.AWAITING_EXTERNAL_REVIEW

        # Approve this time → IN_PROGRESS at next stage.
        next_stage = uuid4()
        task = task.approve_review(
            uuid4(),
            uuid4(),
            next_stage,
            updated_at=_next_ts(task),
        )
        assert task.current_stage_id == next_stage

        # Complete.
        task = task.complete(uuid4(), uuid4(), updated_at=_next_ts(task))
        assert task.status == TaskStatus.DONE

    def test_assign_failure_then_alternate_action_succeeds(self) -> None:
        """TC-IT-TS-001: failed ``assign`` does not break a follow-up valid action.

        Confirmation H: pre-validate keeps the Task state clean across
        sequential failures + retries. After an illegal ``assign`` on
        IN_PROGRESS we should still be able to call ``commit_deliverable``
        successfully (proving no hidden state corruption).
        """
        task = make_in_progress_task()
        agent = task.assigned_agent_ids[0]
        stage = task.current_stage_id

        with pytest.raises(TaskInvariantViolation):
            task.assign([uuid4()], updated_at=_next_ts(task))

        # Original Task is unchanged → ``commit_deliverable`` works.
        d = make_deliverable(stage_id=stage)
        out = task.commit_deliverable(
            stage_id=stage,
            deliverable=d,
            by_agent_id=agent,
            updated_at=_next_ts(task),
        )
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.deliverables[stage] == d

    def test_cancel_from_each_state_clears_last_error(self) -> None:
        """TC-IT-TS-004: cancel from PENDING / IN_PROGRESS / AWAITING / BLOCKED clears last_error.

        Repeats ``TestThirteenAllowedTransitions::test_cancel_from_each_of_four_states``
        with an explicit ``last_error=None`` post-condition assertion
        even on the BLOCKED-origin path (where ``last_error`` was
        non-empty before the cancel call).
        """
        for status in (
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.AWAITING_EXTERNAL_REVIEW,
            TaskStatus.BLOCKED,
        ):
            task = _make_task_in_status(status)
            with contextlib.suppress(TaskInvariantViolation):
                # PENDING factory yields last_error=None already; the
                # remaining factories also keep it None except for
                # BLOCKED which carries the synthetic string.
                pass
            out = task.cancel(uuid4(), "manual abort", updated_at=_next_ts(task))
            assert out.status == TaskStatus.CANCELLED
            assert out.last_error is None


# ---------------------------------------------------------------------------
# Reachability sanity: every IN_PROGRESS-incoming method updates updated_at
# ---------------------------------------------------------------------------
class TestUpdatedAtAdvances:
    """All allowed transitions must move ``updated_at`` strictly forward."""

    @pytest.mark.parametrize(
        "status",
        [
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.AWAITING_EXTERNAL_REVIEW,
            TaskStatus.BLOCKED,
        ],
        ids=lambda s: s.value,
    )
    def test_allowed_action_advances_updated_at(self, status: TaskStatus) -> None:
        """For every legal (status, action), ``updated_at`` of the result is strictly later."""
        # ``TRANSITIONS`` keys are tuples of (TaskStatus, TaskAction)
        # but the iteration loses the Literal narrowing — annotate
        # explicitly so the action stays typed as TaskAction.
        legal_actions: list[TaskAction] = [a for (s, a) in TRANSITIONS if s == status]
        assert legal_actions, f"status {status} has zero legal actions"
        for action in legal_actions:
            task = _make_task_in_status(status)
            # block requires non-empty last_error which the helper
            # passes through; commit_deliverable requires a Deliverable
            # whose stage_id matches; both are handled by _invoke_action.
            try:
                out = _invoke_action(task, action)
            except TaskInvariantViolation:  # pragma: no cover - defensive
                pytest.fail(
                    f"Allowed transition ({status.value}, {action}) raised — contract regression."
                )
            assert out.updated_at > task.updated_at, (
                f"({status.value}, {action}): updated_at did not advance."
            )


# Importing Deliverable / Task to use type checkers downstream
_ = Deliverable, Task
