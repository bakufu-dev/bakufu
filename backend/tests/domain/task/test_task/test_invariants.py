"""Task invariant + MSG + auto-mask tests.

TC-UT-TS-009 / 010 / 011 / 041 / 042 / 043 / 046〜052 — the 5
``_validate_*`` helpers, the §確定 I auto-mask, the §確定 K
"Aggregate does not enforce application-layer invariants" boundary,
and the §確定 J / room §確定 I 踏襲 **Next: hint physical guarantee**
across all 7 MSG-TS-001〜007 messages.

Per ``docs/features/task/test-design.md``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import TaskInvariantViolation
from bakufu.domain.task.aggregate_validators import (
    MAX_ASSIGNED_AGENTS,
    MAX_LAST_ERROR_LENGTH,
    _validate_assigned_agents_capacity,  # pyright: ignore[reportPrivateUsage]
    _validate_assigned_agents_unique,  # pyright: ignore[reportPrivateUsage]
    _validate_blocked_has_last_error,  # pyright: ignore[reportPrivateUsage]
    _validate_last_error_consistency,  # pyright: ignore[reportPrivateUsage]
    _validate_timestamp_order,  # pyright: ignore[reportPrivateUsage]
)
from bakufu.domain.value_objects import TaskStatus

from tests.factories.task import (
    make_blocked_task,
    make_deliverable,
    make_in_progress_task,
    make_task,
)


# ---------------------------------------------------------------------------
# TC-UT-TS-009: assigned_agents_unique
# ---------------------------------------------------------------------------
class TestAssignedAgentsUnique:
    """TC-UT-TS-009: duplicate agent ids raise assigned_agents_unique (MSG-TS-003)."""

    def test_duplicate_agents_raise(self) -> None:
        """Two of the same AgentId in the list → MSG-TS-003."""
        agent_a = uuid4()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_assigned_agents_unique([agent_a, uuid4(), agent_a])
        assert exc_info.value.kind == "assigned_agents_unique"
        # detail surfaces the duplicate (sorted str list).
        assert "duplicates" in exc_info.value.detail
        assert str(agent_a) in str(exc_info.value.detail["duplicates"])

    def test_unique_list_passes(self) -> None:
        """A duplicate-free list returns without raising."""
        # Direct call returns None (validator is a side-effecting raise-on-violation).
        _validate_assigned_agents_unique([uuid4(), uuid4(), uuid4()])

    def test_via_aggregate_construction_raises(self) -> None:
        """Constructing a Task with duplicate agents raises through the model validator."""
        agent_a = uuid4()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            make_in_progress_task(assigned_agent_ids=[agent_a, agent_a])
        assert exc_info.value.kind == "assigned_agents_unique"


# ---------------------------------------------------------------------------
# TC-UT-TS-041: assigned_agents_capacity (MAX = 5)
# ---------------------------------------------------------------------------
class TestAssignedAgentsCapacity:
    """TC-UT-TS-041: ``len > MAX_ASSIGNED_AGENTS`` raises (MSG-TS-004)."""

    def test_six_agents_raises(self) -> None:
        """6 unique agent_ids exceeds the cap of 5 and raises."""
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_assigned_agents_capacity([uuid4() for _ in range(6)])
        assert exc_info.value.kind == "assigned_agents_capacity"
        assert exc_info.value.detail.get("max") == MAX_ASSIGNED_AGENTS

    def test_five_agents_passes(self) -> None:
        """At-cap list (5 agents) is accepted."""
        _validate_assigned_agents_capacity([uuid4() for _ in range(5)])


# ---------------------------------------------------------------------------
# TC-UT-TS-010: last_error_consistency
# ---------------------------------------------------------------------------
class TestLastErrorConsistency:
    """TC-UT-TS-010: status==BLOCKED iff last_error is non-empty (MSG-TS-005)."""

    def test_in_progress_with_last_error_raises(self) -> None:
        """status=IN_PROGRESS + last_error='something' → MSG-TS-005."""
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_last_error_consistency(TaskStatus.IN_PROGRESS, "leftover error")
        assert exc_info.value.kind == "last_error_consistency"

    def test_blocked_with_none_last_error_raises(self) -> None:
        """status=BLOCKED + last_error=None → MSG-TS-005."""
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_last_error_consistency(TaskStatus.BLOCKED, None)
        assert exc_info.value.kind == "last_error_consistency"

    def test_blocked_with_non_empty_last_error_passes(self) -> None:
        """The legal pairing — BLOCKED + non-empty string — is accepted."""
        _validate_last_error_consistency(TaskStatus.BLOCKED, "AuthExpired")

    def test_done_with_none_last_error_passes(self) -> None:
        """Terminal status + last_error=None is the legal terminal shape."""
        _validate_last_error_consistency(TaskStatus.DONE, None)


# ---------------------------------------------------------------------------
# TC-UT-TS-051 (also): blocked_requires_last_error length check
# ---------------------------------------------------------------------------
class TestBlockedRequiresLastError:
    """TC-UT-TS-051: BLOCKED + 0-length last_error raises (MSG-TS-006).

    Distinct from ``last_error_consistency`` — when status==BLOCKED
    and last_error is None or empty string, the *consistency* check
    catches the structural mismatch first; this validator confirms the
    NFC-normalized length is in the [1, 10000] band when consistency
    is satisfied.
    """

    def test_blocked_with_too_long_last_error_raises(self) -> None:
        """A 10001-char last_error exceeds MAX_LAST_ERROR_LENGTH."""
        too_long = "x" * (MAX_LAST_ERROR_LENGTH + 1)
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_blocked_has_last_error(TaskStatus.BLOCKED, too_long)
        assert exc_info.value.kind == "blocked_requires_last_error"

    def test_non_blocked_status_short_circuits(self) -> None:
        """Non-BLOCKED statuses skip the length check entirely."""
        _validate_blocked_has_last_error(TaskStatus.IN_PROGRESS, None)
        _validate_blocked_has_last_error(TaskStatus.DONE, None)


# ---------------------------------------------------------------------------
# TC-UT-TS-052: timestamp_order
# ---------------------------------------------------------------------------
class TestTimestampOrder:
    """TC-UT-TS-052: created_at > updated_at raises (MSG-TS-007)."""

    def test_created_after_updated_raises(self) -> None:
        """The validator emits MSG-TS-007 with ISO timestamps in detail."""
        ts_old = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        ts_new = ts_old - timedelta(seconds=1)
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_timestamp_order(ts_old, ts_new)
        assert exc_info.value.kind == "timestamp_order"
        # detail surfaces ISO timestamps for forensics.
        assert "created_at" in exc_info.value.detail
        assert "updated_at" in exc_info.value.detail


# ---------------------------------------------------------------------------
# TC-UT-TS-011: TaskInvariantViolation auto-mask (§確定 I)
# ---------------------------------------------------------------------------
class TestExceptionAutoMasksDiscordWebhooks:
    """TC-UT-TS-011: webhook URLs in ``last_error`` get masked in the exception.

    Build a Task whose BLOCKED state carries a webhook URL inside
    ``last_error``, then trigger an invariant by trying to construct
    an inconsistent state. The exception's ``str(exc)`` and
    ``exc.detail`` must both have the token redacted to
    ``<REDACTED:DISCORD_WEBHOOK>``.
    """

    _SECRET = "https://discord.com/api/webhooks/123456789012345678/CataclysmicSecret-token"
    _REDACT_SENTINEL = "<REDACTED:DISCORD_WEBHOOK>"
    _RAW_TOKEN = "CataclysmicSecret-token"

    def test_webhook_token_redacted_in_message(self) -> None:
        """str(exc) does not leak the raw token; sentinel is present."""
        # Pass a webhook URL in the consistency-violation path.
        # status=IN_PROGRESS + non-empty last_error => MSG-TS-005,
        # message includes the field values.
        with pytest.raises(TaskInvariantViolation) as exc_info:
            make_in_progress_task(
                last_error=self._SECRET,
                # The actual MSG echoes "non-empty" for consistency,
                # but the exception's __init__ runs auto-mask on every
                # detail value pre-emptively. Trigger via the invariant
                # by constructing an IN_PROGRESS Task with a non-empty
                # last_error.
            )
        assert self._RAW_TOKEN not in str(exc_info.value), (
            "[FAIL] Raw Discord webhook token leaked into exception message.\n"
            "Next: TaskInvariantViolation.__init__ must apply mask_discord_webhook "
            "to message + mask_discord_webhook_in to detail per §確定 I."
        )

    def test_webhook_token_redacted_in_detail(self) -> None:
        """exc.detail values are recursively masked.

        We trigger the violation through ``block`` with the secret in
        ``last_error`` then transition to a state-inconsistent build.
        The detail dict shape varies by validator; we assert that no
        detail value carries the raw token.
        """
        # Force a blocked_requires_last_error violation by building
        # a Task with status=BLOCKED + last_error=secret + override the
        # length check by using too-long form... easier: invoke the
        # validator directly with the secret as the message-bearing
        # value via _validate_blocked_has_last_error.
        # We construct the exception directly to avoid coupling to the
        # specific validator that injects the webhook into detail —
        # the §確定 I contract is on TaskInvariantViolation.__init__,
        # not on any specific validator.
        exc = TaskInvariantViolation(
            kind="blocked_requires_last_error",
            message=f"[FAIL] secret in message: {self._SECRET}\nNext: re-input webhook.",
            detail={
                "last_error_value": self._SECRET,
                "nested": {"target": self._SECRET},
                "as_list": [self._SECRET, "ok"],
            },
        )

        # Message: token gone, sentinel present.
        assert self._RAW_TOKEN not in exc.message
        assert self._REDACT_SENTINEL in exc.message
        # Detail: every value recursively masked.
        flat = repr(exc.detail)
        assert self._RAW_TOKEN not in flat, (
            f"[FAIL] Raw token leaked into detail: {flat!r}\n"
            f"Next: ensure mask_discord_webhook_in handles dict/list/tuple recursion."
        )
        assert self._REDACT_SENTINEL in flat


# ---------------------------------------------------------------------------
# §確定 G + K: Aggregate-layer non-enforcement of application invariants
# ---------------------------------------------------------------------------
class TestAggregateDoesNotEnforceApplicationInvariants:
    """TC-UT-TS-042 / 043: Aggregate does NOT validate cross-aggregate refs."""

    def test_commit_deliverable_does_not_check_by_agent_id_membership(self) -> None:
        """TC-UT-TS-042: ``by_agent_id`` need not be in ``assigned_agent_ids``.

        §確定 G: that membership check is the application service's
        job. We pass an agent that is NOT in the assigned set and
        expect the call to succeed at the Aggregate level.
        """
        task = make_in_progress_task(assigned_agent_ids=[uuid4()])
        outsider_agent = uuid4()
        # Sanity: outsider not in the assigned set.
        assert outsider_agent not in task.assigned_agent_ids

        d = make_deliverable(stage_id=task.current_stage_id)
        out = task.commit_deliverable(
            stage_id=task.current_stage_id,
            deliverable=d,
            by_agent_id=outsider_agent,
            updated_at=task.updated_at + timedelta(seconds=1),
        )
        assert out.deliverables[task.current_stage_id] == d

    def test_arbitrary_room_id_and_directive_id_accepted(self) -> None:
        """TC-UT-TS-043: random IDs for cross-aggregate refs construct cleanly.

        The Aggregate stores VO-typed IDs without verifying the target
        rows exist (§確定 K). Repository / TaskService verifies
        existence at hydration / construction; the Aggregate's job is
        only to keep its **own** state consistent.
        """
        # Random IDs — none of them refer to anything that exists in
        # any test fixture / DB. The Aggregate accepts them.
        task = make_task(
            room_id=uuid4(),
            directive_id=uuid4(),
            current_stage_id=uuid4(),
        )
        # Construction succeeded; no reference-integrity check fired.
        assert task.room_id is not None
        assert task.directive_id is not None
        assert task.current_stage_id is not None


# ---------------------------------------------------------------------------
# TC-UT-TS-046〜052: 2-line MSG + Next: hint physical guarantee (§確定 J)
# ---------------------------------------------------------------------------
class TestNextHintPhysicalGuarantee:
    """Across all 7 ``TaskViolationKind`` values, ``str(exc)`` carries 'Next:'.

    The room §確定 I 踏襲 contract: every error message has a 2-line
    structure (``[FAIL] <fact>\\nNext: <action>``). A failing assertion
    on ``"Next:" in str(exc)`` means a developer wrote a one-line MSG
    and the operator-feedback contract is broken.

    We trigger each kind through the natural code path (not direct
    exception construction) so the actual emitted string is what gets
    asserted.
    """

    def test_terminal_violation_carries_next_hint(self) -> None:
        """TC-UT-TS-046: MSG-TS-001 (terminal_violation)."""
        from tests.factories.task import make_done_task

        task = make_done_task()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            task.assign([uuid4()], updated_at=task.updated_at + timedelta(seconds=1))
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "DONE/CANCELLED" in s  # hint substring

    def test_state_transition_invalid_carries_next_hint(self) -> None:
        """TC-UT-TS-047: MSG-TS-002 (state_transition_invalid)."""
        task = make_task()  # PENDING
        with pytest.raises(TaskInvariantViolation) as exc_info:
            task.commit_deliverable(
                stage_id=task.current_stage_id,
                deliverable=make_deliverable(),
                by_agent_id=uuid4(),
                updated_at=task.updated_at + timedelta(seconds=1),
            )
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "state_machine.py" in s

    def test_assigned_agents_unique_carries_next_hint(self) -> None:
        """TC-UT-TS-048: MSG-TS-003 (assigned_agents_unique)."""
        agent = uuid4()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_assigned_agents_unique([agent, agent])
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "Deduplicate" in s

    def test_assigned_agents_capacity_carries_next_hint(self) -> None:
        """TC-UT-TS-049: MSG-TS-004 (assigned_agents_capacity)."""
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_assigned_agents_capacity([uuid4() for _ in range(6)])
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "split work" in s

    def test_last_error_consistency_carries_next_hint(self) -> None:
        """TC-UT-TS-050: MSG-TS-005 (last_error_consistency)."""
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_last_error_consistency(TaskStatus.IN_PROGRESS, "oops")
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "Repository row integrity" in s

    def test_blocked_requires_last_error_carries_next_hint(self) -> None:
        """TC-UT-TS-051: MSG-TS-006 (blocked_requires_last_error).

        A direct invocation with status=BLOCKED + empty last_error.
        Note that the higher-level ``Task.block(..., last_error='')``
        path raises through the model validator on the rebuild —
        same kind, same hint.
        """
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_blocked_has_last_error(TaskStatus.BLOCKED, "")
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "1-10000" in s

    def test_timestamp_order_carries_next_hint(self) -> None:
        """TC-UT-TS-052: MSG-TS-007 (timestamp_order)."""
        ts_old = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        ts_new = ts_old - timedelta(seconds=1)
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_timestamp_order(ts_old, ts_new)
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "updated_at must be" in s


# ---------------------------------------------------------------------------
# Smoke: BLOCKED Task with raw last_error keeps the secret
# ---------------------------------------------------------------------------
class TestAggregateKeepsRawLastError:
    """The Aggregate stores ``last_error`` raw — masking is Repository-side.

    Reaffirms the design separation: ``MaskedText`` is a column
    decorator on ``tasks.last_error`` in ``feature/task-repository``;
    the in-memory Task instance must NOT pre-mask the value, otherwise
    the Aggregate would silently lose forensic information.
    """

    def test_in_memory_task_keeps_secret(self) -> None:
        """``make_blocked_task(last_error=secret)`` keeps the raw secret in-memory."""
        secret = (
            "AuthExpired: https://discord.com/api/webhooks/111122223333444455/RawTokenInMemory-only"
        )
        task = make_blocked_task(last_error=secret)
        assert task.last_error == secret
