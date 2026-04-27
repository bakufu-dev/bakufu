"""ExternalReviewGate state machine tests (TC-UT-GT-003〜006, 013〜015).

Per ``docs/features/external-review-gate/test-design.md``. The
§確定 A 4x4 = **16-cell dispatch matrix** is asserted in three
orthogonal ways here:

1. **7 ✓ cells**: each allowed transition has its own positive case
   (PENDING approve / reject / cancel + 4 self-loops via record_view).
2. **9 ✗ cells**: APPROVED/REJECTED/CANCELLED x approve/reject/cancel
   parametrize coverage → ``decision_already_decided`` (MSG-GT-001).
3. **§確定 G 冪等性なし**: same owner + same time = 2 audit entries
   (audit requirement: 誰がいつ何度見たか).

§確定 B (state machine table lock) is asserted via the 7-entry size
check + ``MappingProxyType`` setitem rejection.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.external_review_gate import ExternalReviewGate
from bakufu.domain.external_review_gate.state_machine import (
    TRANSITIONS,
    GateAction,
)
from bakufu.domain.value_objects import (
    AuditAction,
    ReviewDecision,
)

from tests.factories.external_review_gate import (
    make_approved_gate,
    make_cancelled_gate,
    make_gate,
    make_rejected_gate,
)

# All 4 action names — must match ExternalReviewGate method names 1:1 (§確定 A).
_ALL_ACTIONS: list[GateAction] = ["approve", "reject", "cancel", "record_view"]

# All 4 decision values for the 16-cell matrix.
_ALL_DECISIONS: list[ReviewDecision] = list(ReviewDecision)

# The 3 PENDING-only actions (terminal-firing).
_PENDING_ONLY_ACTIONS: list[GateAction] = ["approve", "reject", "cancel"]


def _next_ts(gate: ExternalReviewGate) -> datetime:
    """Return a strictly-later UTC timestamp for ``decided_at`` / ``viewed_at``."""
    base = gate.decided_at if gate.decided_at is not None else gate.created_at
    return base + timedelta(seconds=1)


def _invoke_action(gate: ExternalReviewGate, action: GateAction) -> ExternalReviewGate:
    """Dispatch ``action`` on ``gate`` with throwaway-but-valid arguments."""
    ts = _next_ts(gate)
    if action == "approve":
        return gate.approve(uuid4(), "synthetic approve comment", decided_at=ts)
    if action == "reject":
        return gate.reject(uuid4(), "synthetic reject comment", decided_at=ts)
    if action == "cancel":
        return gate.cancel(uuid4(), "synthetic cancel reason", decided_at=ts)
    # record_view
    return gate.record_view(uuid4(), viewed_at=ts)


def _make_gate_in_decision(decision: ReviewDecision) -> ExternalReviewGate:
    """Build a Gate in the given decision using the appropriate factory."""
    if decision == ReviewDecision.PENDING:
        return make_gate()
    if decision == ReviewDecision.APPROVED:
        return make_approved_gate()
    if decision == ReviewDecision.REJECTED:
        return make_rejected_gate()
    return make_cancelled_gate()


# ---------------------------------------------------------------------------
# §確定 B: state machine TABLE shape + immutability (TC-UT-GT-014)
# ---------------------------------------------------------------------------
class TestStateMachineTableLocked:
    """TC-UT-GT-014: ``TRANSITIONS`` has 7 entries and rejects mutation."""

    def test_table_size_is_seven(self) -> None:
        """The §確定 A dispatch table freezes 7 allowed transitions."""
        assert len(TRANSITIONS) == 7, (
            f"[FAIL] state machine table size drifted: got {len(TRANSITIONS)}, expected 7.\n"
            f"Next: docs/features/external-review-gate/detailed-design.md §確定 A "
            f"freezes 7 transitions; editing state_machine.py without updating "
            f"the design is a contract break."
        )

    def test_table_setitem_rejected_at_runtime(self) -> None:
        """``TRANSITIONS[k] = v`` raises ``TypeError`` (MappingProxyType lock)."""
        with pytest.raises(TypeError):
            TRANSITIONS[(ReviewDecision.APPROVED, "approve")] = ReviewDecision.PENDING  # pyright: ignore[reportIndexIssue]


# ---------------------------------------------------------------------------
# 7 allowed transitions — one positive case per ✓ cell
# ---------------------------------------------------------------------------
class TestSevenAllowedTransitions:
    """TC-UT-GT-003 / 004 / 006 / 013 — the 7 ✓ cells of the dispatch table."""

    # PENDING → APPROVED via approve
    def test_approve_pending_to_approved(self) -> None:
        """TC-UT-GT-003: ``approve`` on PENDING moves to APPROVED."""
        gate = make_gate()
        ts = _next_ts(gate)
        out = gate.approve(uuid4(), "looks good", decided_at=ts)
        assert out.decision == ReviewDecision.APPROVED
        assert out.decided_at == ts
        assert out.feedback_text == "looks good"
        # Audit trail: 1 new APPROVED entry appended.
        assert len(out.audit_trail) == len(gate.audit_trail) + 1
        assert out.audit_trail[-1].action == AuditAction.APPROVED
        # Original Gate unchanged (frozen + pre-validate).
        assert gate.decision == ReviewDecision.PENDING

    # PENDING → REJECTED via reject
    def test_reject_pending_to_rejected(self) -> None:
        """TC-UT-GT-004: ``reject`` on PENDING moves to REJECTED."""
        gate = make_gate()
        ts = _next_ts(gate)
        out = gate.reject(uuid4(), "needs revision", decided_at=ts)
        assert out.decision == ReviewDecision.REJECTED
        assert out.decided_at == ts
        assert out.feedback_text == "needs revision"
        assert out.audit_trail[-1].action == AuditAction.REJECTED

    # PENDING → CANCELLED via cancel
    def test_cancel_pending_to_cancelled(self) -> None:
        """TC-UT-GT-013: ``cancel`` on PENDING moves to CANCELLED."""
        gate = make_gate()
        ts = _next_ts(gate)
        out = gate.cancel(uuid4(), "directive withdrawn", decided_at=ts)
        assert out.decision == ReviewDecision.CANCELLED
        assert out.decided_at == ts
        assert out.feedback_text == "directive withdrawn"
        assert out.audit_trail[-1].action == AuditAction.CANCELLED

    # 4 record_view self-loops — one per decision state
    @pytest.mark.parametrize(
        "decision",
        list(ReviewDecision),
        ids=lambda d: d.value,
    )
    def test_record_view_self_loop_in_each_state(self, decision: ReviewDecision) -> None:
        """TC-UT-GT-006: ``record_view`` is a self-loop in every state."""
        gate = _make_gate_in_decision(decision)
        ts = _next_ts(gate)
        out = gate.record_view(uuid4(), viewed_at=ts)
        assert out.decision == decision  # state unchanged
        # Decided_at unchanged (record_view is purely an audit op).
        assert out.decided_at == gate.decided_at
        assert out.feedback_text == gate.feedback_text
        # Audit trail: 1 new VIEWED entry appended.
        assert len(out.audit_trail) == len(gate.audit_trail) + 1
        assert out.audit_trail[-1].action == AuditAction.VIEWED


# ---------------------------------------------------------------------------
# TC-UT-GT-005: 9 ✗ cells (decision_already_decided)
# ---------------------------------------------------------------------------
class TestDecisionAlreadyDecidedRejection:
    """9 ✗ cells: approve/reject/cancel on APPROVED/REJECTED/CANCELLED → MSG-GT-001.

    The 16-cell matrix splits as: 7 ✓ + 9 ✗. Every ✗ cell is a
    PENDING-only action attempted on a non-PENDING Gate.
    ``decision_already_decided`` fires (MSG-GT-001 with the
    ``allowed_actions`` hint pointing to record_view).
    """

    @pytest.mark.parametrize(
        "decision",
        [ReviewDecision.APPROVED, ReviewDecision.REJECTED, ReviewDecision.CANCELLED],
        ids=lambda d: d.value,
    )
    @pytest.mark.parametrize(
        "action",
        _PENDING_ONLY_ACTIONS,
        ids=lambda a: a,
    )
    def test_pending_only_action_on_terminal_raises(
        self,
        decision: ReviewDecision,
        action: GateAction,
    ) -> None:
        """Each (terminal decision, PENDING-only action) raises decision_already_decided."""
        gate = _make_gate_in_decision(decision)
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _invoke_action(gate, action)
        assert exc_info.value.kind == "decision_already_decided"
        # The detail surfaces the allowed_actions list — the only
        # legal action from a terminal decision is ``record_view``.
        # MSG-GT-001 itself routes the operator via "issue a new
        # directive" hint; the structured allowed_actions belongs to
        # detail (consumed by application-layer error reporters).
        allowed = exc_info.value.detail.get("allowed_actions")
        assert allowed == ["record_view"], (
            f"[FAIL] terminal Gate must list ['record_view'] as the only "
            f"allowed action; got {allowed!r}"
        )


# ---------------------------------------------------------------------------
# TC-UT-GT-006 (補強): record_view 冪等性なし (§確定 G)
# ---------------------------------------------------------------------------
class TestRecordViewIsNotIdempotent:
    """§確定 G: same owner + same timestamp = 2 audit entries.

    The audit requirement is "誰がいつ何度見たか" (who, when, how
    many times). Collapsing duplicates would discard the very
    frequency signal the audit trail is supposed to preserve.
    """

    def test_same_owner_same_time_appends_twice(self) -> None:
        """Two record_view calls with identical owner + time → 2 distinct entries."""
        gate = make_gate()
        owner = uuid4()
        ts = datetime(2026, 4, 28, 14, 0, 0, tzinfo=UTC)
        once = gate.record_view(owner, viewed_at=ts)
        twice = once.record_view(owner, viewed_at=ts)

        assert len(once.audit_trail) == 1
        assert len(twice.audit_trail) == 2
        # Both entries carry the same actor + occurred_at, but their
        # ``id`` differs (uuid4 inside _rebuild_with_state).
        e1, e2 = twice.audit_trail
        assert e1.actor_id == e2.actor_id == owner
        assert e1.occurred_at == e2.occurred_at == ts
        assert e1.id != e2.id

    def test_three_views_record_three_entries(self) -> None:
        """A 3-view sequence accumulates 3 audit entries."""
        gate = make_gate()
        viewer = uuid4()
        for _ in range(3):
            gate = gate.record_view(viewer, viewed_at=_next_ts(gate))
        assert len(gate.audit_trail) == 3
        assert all(e.action == AuditAction.VIEWED for e in gate.audit_trail)

    def test_record_view_preserves_decision_and_decided_at(self) -> None:
        """record_view does NOT change decision / decided_at / feedback_text."""
        gate = make_approved_gate(feedback_text="approved!")
        before_decision = gate.decision
        before_decided_at = gate.decided_at
        before_feedback = gate.feedback_text

        out = gate.record_view(uuid4(), viewed_at=_next_ts(gate))

        assert out.decision == before_decision
        assert out.decided_at == before_decided_at
        assert out.feedback_text == before_feedback


# ---------------------------------------------------------------------------
# TC-UT-GT-015: pre-validate failure leaves source Gate unchanged (§確定 E)
# ---------------------------------------------------------------------------
class TestPreValidateLeavesSourceUnchanged:
    """TC-UT-GT-015: a failed behavior call does not mutate the original Gate.

    The §確定 E pre-validate rebuild path means a behavior either
    returns a new Gate or raises — never partially-mutates the source
    instance. We assert this by attempting a `decision_already_decided`
    on a terminal Gate and inspecting the original Gate's full
    attribute set.
    """

    def test_failed_approve_on_approved_keeps_source_unchanged(self) -> None:
        """An ``approve`` on APPROVED raises and does not touch the source."""
        gate = make_approved_gate()
        snapshot = gate.model_dump()

        with pytest.raises(ExternalReviewGateInvariantViolation):
            gate.approve(uuid4(), "double-approve", decided_at=_next_ts(gate))

        assert gate.model_dump() == snapshot


# ---------------------------------------------------------------------------
# Lifecycle integration scenarios
# ---------------------------------------------------------------------------
class TestLifecycleIntegration:
    """Aggregate-internal "integration" — multi-method round-trip scenarios."""

    def test_pending_approve_then_views_then_approve_again_rejected(self) -> None:
        """PENDING → APPROVED → record_view x 2 → re-approve raises."""
        gate = make_gate()
        viewer_a = uuid4()
        viewer_b = uuid4()

        # Approve.
        gate = gate.approve(uuid4(), "all good", decided_at=_next_ts(gate))
        assert gate.decision == ReviewDecision.APPROVED

        # 2 distinct viewers record their views.
        gate = gate.record_view(viewer_a, viewed_at=_next_ts(gate))
        gate = gate.record_view(viewer_b, viewed_at=_next_ts(gate))
        assert len(gate.audit_trail) == 3  # 1 APPROVED + 2 VIEWED

        # Re-approve must raise — Gate is single-decision.
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            gate.approve(uuid4(), "re-approve", decided_at=_next_ts(gate))
        assert exc_info.value.kind == "decision_already_decided"

        # Audit trail must have 3 entries unchanged (the failed
        # approve did NOT add an entry — pre-validate left source
        # intact).
        assert len(gate.audit_trail) == 3

    def test_pending_reject_record_view_still_legal(self) -> None:
        """A REJECTED Gate still accepts late record_view audits."""
        gate = make_gate()
        gate = gate.reject(uuid4(), "needs more work", decided_at=_next_ts(gate))
        assert gate.decision == ReviewDecision.REJECTED

        for _ in range(2):
            gate = gate.record_view(uuid4(), viewed_at=_next_ts(gate))
        # 1 REJECTED + 2 VIEWED = 3 entries.
        assert len(gate.audit_trail) == 3
        assert gate.audit_trail[0].action == AuditAction.REJECTED
        assert gate.audit_trail[1].action == AuditAction.VIEWED
        assert gate.audit_trail[2].action == AuditAction.VIEWED

    def test_pending_cancel_then_record_view_still_legal(self) -> None:
        """A CANCELLED Gate still accepts late record_view audits.

        §確定 G コンプライアンス観点: "3 ヶ月前に CANCELLED した Gate
        を再確認した" ログ価値 — record_view permitted in every state.
        """
        gate = make_gate()
        gate = gate.cancel(uuid4(), "withdrawn", decided_at=_next_ts(gate))
        gate = gate.record_view(uuid4(), viewed_at=_next_ts(gate))
        assert gate.decision == ReviewDecision.CANCELLED
        assert len(gate.audit_trail) == 2


# ---------------------------------------------------------------------------
# Reachability sanity — each allowed transition produces consistent fields
# ---------------------------------------------------------------------------
class TestAuditTrailGrowsByOnePerCall:
    """Every behavior method appends exactly one audit entry."""

    @pytest.mark.parametrize(
        "decision",
        list(ReviewDecision),
        ids=lambda d: d.value,
    )
    def test_legal_action_grows_audit_by_one(self, decision: ReviewDecision) -> None:
        """For every legal (decision, action), audit_trail length grows by 1."""
        legal_actions: list[GateAction] = [a for (d, a) in TRANSITIONS if d == decision]
        assert legal_actions, f"decision {decision} has zero legal actions"
        for action in legal_actions:
            gate = _make_gate_in_decision(decision)
            before_len = len(gate.audit_trail)
            out = _invoke_action(gate, action)
            assert len(out.audit_trail) == before_len + 1, (
                f"({decision.value}, {action}): audit_trail did not grow by exactly 1."
            )


# Sanity import to keep pyright happy with the GateAction type usage above.
_ = GateAction
