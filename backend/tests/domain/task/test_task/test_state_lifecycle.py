"""Task state machine: BLOCKED contract + pre-validate + lifecycle integration.

TC-UT-TS-007 (BLOCKED non-empty last_error contract) + TC-UT-TS-038
(pre-validate leaves original Task untouched) + TC-IT-TS-001〜005
(multi-method integration scenarios) + ``updated_at`` monotonicity
across all 13 ✓ transitions.

Per ``docs/features/task/test-design.md``. Split out of
``test_state_machine.py`` per Norman R-N1 (633 → 3 files). Sibling
files cover the table lock + 13 ✓ cells and the 47 ✗ cells.
"""

from __future__ import annotations

import contextlib
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import TaskInvariantViolation
from bakufu.domain.task.state_machine import TRANSITIONS, TaskAction
from bakufu.domain.value_objects import TaskStatus

from tests.domain.task.test_task._helpers import (
    ALL_ACTIONS,
    invoke_action,
    make_task_in_status,
    next_ts,
)
from tests.factories.task import (
    make_deliverable,
    make_in_progress_task,
    make_task,
)


# ---------------------------------------------------------------------------
# TC-UT-TS-007: BLOCKED contract — block() rejects empty last_error
# ---------------------------------------------------------------------------
class TestBlockRequiresNonEmptyLastError:
    """TC-UT-TS-007: ``block(reason, last_error='')`` Fail-Fast.

    BUG-TSK-001 fix landed (commit ``377366e``): ``Task._check_invariants``
    now runs ``_validate_blocked_has_last_error`` **before**
    ``_validate_last_error_consistency``, so the empty-string path
    raises the design-contracted ``MSG-TS-006``
    (``blocked_requires_last_error``) — the "block() requires non-empty
    last_error" Next-action hint. The single-kind assertion below pins
    that contract; a regression that swapped the ordering back would
    surface here, not behind a permissive ``or`` set.
    """

    def test_block_with_empty_last_error_raises_blocked_requires_last_error(self) -> None:
        """``block(last_error='')`` raises ``blocked_requires_last_error`` (MSG-TS-006)."""
        task = make_in_progress_task()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            task.block("retry exhausted", "", updated_at=next_ts(task))
        assert exc_info.value.kind == "blocked_requires_last_error", (
            f"[FAIL] block(empty last_error) raised {exc_info.value.kind!r}, expected "
            f"'blocked_requires_last_error' (MSG-TS-006).\n"
            f"Next: verify ``Task._check_invariants`` runs "
            f"``_validate_blocked_has_last_error`` BEFORE "
            f"``_validate_last_error_consistency`` — see BUG-TSK-001 fix "
            f"(commit 377366e)."
        )

    def test_block_with_too_long_last_error_raises(self) -> None:
        """A 10001-char ``last_error`` exceeds MAX and raises blocked_requires_last_error.

        For the over-length path, the consistency check passes
        (BLOCKED + non-empty string is structurally OK) and the
        length check fires — same kind as the empty-string path
        after the BUG-TSK-001 fix.
        """
        task = make_in_progress_task()
        too_long = "x" * 10_001
        with pytest.raises(TaskInvariantViolation) as exc_info:
            task.block("oops", too_long, updated_at=next_ts(task))
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
            original.assign([uuid4()], updated_at=next_ts(original))

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
        task = task.assign([agent_a], updated_at=next_ts(task))
        assert task.status == TaskStatus.IN_PROGRESS

        # Step 2: commit_deliverable
        d1 = make_deliverable(stage_id=stage_a)
        task = task.commit_deliverable(
            stage_id=stage_a,
            deliverable=d1,
            by_agent_id=agent_a,
            updated_at=next_ts(task),
        )
        assert task.deliverables[stage_a] == d1

        # Step 3: request_external_review → AWAITING
        task = task.request_external_review(updated_at=next_ts(task))
        assert task.status == TaskStatus.AWAITING_EXTERNAL_REVIEW

        # Step 4: approve_review → IN_PROGRESS at next stage
        stage_b = uuid4()
        task = task.approve_review(uuid4(), uuid4(), stage_b, updated_at=next_ts(task))
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.current_stage_id == stage_b

        # Step 5: commit + complete
        d2 = make_deliverable(stage_id=stage_b)
        task = task.commit_deliverable(
            stage_id=stage_b,
            deliverable=d2,
            by_agent_id=agent_a,
            updated_at=next_ts(task),
        )
        task = task.complete(uuid4(), uuid4(), updated_at=next_ts(task))
        assert task.status == TaskStatus.DONE
        assert len(task.deliverables) == 2

        # DONE rejects every subsequent action (cross-check with
        # TestTerminalGate on a freshly-walked Task).
        for action in ALL_ACTIONS:
            with pytest.raises(TaskInvariantViolation) as exc_info:
                invoke_action(task, action)
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
        task = task.block("auth retry exhausted", last_err, updated_at=next_ts(task))
        assert task.status == TaskStatus.BLOCKED
        assert task.last_error is not None
        assert task.last_error == last_err  # Aggregate keeps raw form

        # Unblock → back to IN_PROGRESS, last_error cleared.
        task = task.unblock_retry(updated_at=next_ts(task))
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.last_error is None

        # Commit + complete.
        d = make_deliverable(stage_id=stage)
        task = task.commit_deliverable(
            stage_id=stage,
            deliverable=d,
            by_agent_id=agent,
            updated_at=next_ts(task),
        )
        task = task.complete(uuid4(), uuid4(), updated_at=next_ts(task))
        assert task.status == TaskStatus.DONE

    def test_reject_review_and_resubmit_loop(self) -> None:
        """TC-IT-TS-005: AWAITING → IN_PROGRESS (rejected to rollback) → re-review → DONE.

        Verifies that ``reject_review`` is a real round-trip path:
        a Task that is rejected can return through a different
        ``current_stage_id``, re-submit, and eventually complete.
        """
        task = make_task_in_status(TaskStatus.AWAITING_EXTERNAL_REVIEW)
        agent = task.assigned_agent_ids[0]

        # Reject — fall back to a "rollback" stage.
        rollback_stage = uuid4()
        task = task.reject_review(
            uuid4(),
            uuid4(),
            rollback_stage,
            updated_at=next_ts(task),
        )
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.current_stage_id == rollback_stage

        # Re-commit + re-review.
        d = make_deliverable(stage_id=rollback_stage)
        task = task.commit_deliverable(
            stage_id=rollback_stage,
            deliverable=d,
            by_agent_id=agent,
            updated_at=next_ts(task),
        )
        task = task.request_external_review(updated_at=next_ts(task))
        assert task.status == TaskStatus.AWAITING_EXTERNAL_REVIEW

        # Approve this time → IN_PROGRESS at next stage.
        next_stage = uuid4()
        task = task.approve_review(
            uuid4(),
            uuid4(),
            next_stage,
            updated_at=next_ts(task),
        )
        assert task.current_stage_id == next_stage

        # Complete.
        task = task.complete(uuid4(), uuid4(), updated_at=next_ts(task))
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
            task.assign([uuid4()], updated_at=next_ts(task))

        # Original Task is unchanged → ``commit_deliverable`` works.
        d = make_deliverable(stage_id=stage)
        out = task.commit_deliverable(
            stage_id=stage,
            deliverable=d,
            by_agent_id=agent,
            updated_at=next_ts(task),
        )
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.deliverables[stage] == d

    def test_cancel_from_each_state_clears_last_error(self) -> None:
        """TC-IT-TS-004: cancel from PENDING / IN_PROGRESS / AWAITING / BLOCKED clears last_error.

        Repeats ``test_cancel_from_each_of_four_states`` (sibling file)
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
            task = make_task_in_status(status)
            with contextlib.suppress(TaskInvariantViolation):
                # PENDING factory yields last_error=None already; the
                # remaining factories also keep it None except for
                # BLOCKED which carries the synthetic string.
                pass
            out = task.cancel(uuid4(), "manual abort", updated_at=next_ts(task))
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
            task = make_task_in_status(status)
            # block requires non-empty last_error which the helper
            # passes through; commit_deliverable requires a Deliverable
            # whose stage_id matches; both are handled by invoke_action.
            try:
                out = invoke_action(task, action)
            except TaskInvariantViolation:  # pragma: no cover - defensive
                pytest.fail(
                    f"Allowed transition ({status.value}, {action}) raised — contract regression."
                )
            assert out.updated_at > task.updated_at, (
                f"({status.value}, {action}): updated_at did not advance."
            )
