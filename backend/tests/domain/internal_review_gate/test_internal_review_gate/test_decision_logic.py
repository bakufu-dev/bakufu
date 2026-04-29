"""compute_decision + GateDecision 遷移テスト (TC-UT-IRG-003 / 004 / 005 再掲).

Per ``docs/features/internal-review-gate/domain/test-design.md``
§compute_decision + GateDecision 遷移.

Tests ``compute_decision`` as a **pure function** directly, independent of
``submit_verdict``, to verify the most-pessimistic-wins logic:

  Rule 1 (highest priority): any REJECTED verdict → GateDecision.REJECTED
  Rule 2: all required roles APPROVED → GateDecision.ALL_APPROVED
  Rule 3 (default): otherwise → GateDecision.PENDING

Also verifies the ``Final`` binding contract (§確定 C / state_machine.py).

Issue: #65
"""

from __future__ import annotations

from bakufu.domain.internal_review_gate.state_machine import (
    _compute_decision,  # pyright: ignore[reportPrivateUsage]
    compute_decision,
)
from bakufu.domain.value_objects import GateDecision, VerdictDecision

from tests.factories.internal_review_gate import make_verdict


# ---------------------------------------------------------------------------
# TC-UT-IRG-003 (re): PENDING condition — some but not all APPROVED
# ---------------------------------------------------------------------------
class TestComputeDecisionPending:
    """compute_decision → PENDING when some required roles have not submitted."""

    def test_no_verdicts_is_pending(self) -> None:
        result = compute_decision((), frozenset({"reviewer", "ux"}))
        assert result == GateDecision.PENDING

    def test_partial_approved_is_pending(self) -> None:
        """1/2 required roles approved → PENDING (need all roles)."""
        v_reviewer = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        result = compute_decision((v_reviewer,), frozenset({"reviewer", "ux"}))
        assert result == GateDecision.PENDING

    def test_superset_required_roles_missing_stays_pending(self) -> None:
        """3 required roles, 2 approved → PENDING (1 still missing)."""
        v1 = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        v2 = make_verdict(role="ux", decision=VerdictDecision.APPROVED)
        result = compute_decision((v1, v2), frozenset({"reviewer", "ux", "security"}))
        assert result == GateDecision.PENDING


# ---------------------------------------------------------------------------
# TC-UT-IRG-004 (re): ALL_APPROVED condition
# ---------------------------------------------------------------------------
class TestComputeDecisionAllApproved:
    """compute_decision → ALL_APPROVED when all required roles have APPROVED."""

    def test_all_required_approved_transitions(self) -> None:
        """All required roles APPROVED → ALL_APPROVED."""
        v1 = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        v2 = make_verdict(role="ux", decision=VerdictDecision.APPROVED)
        result = compute_decision((v1, v2), frozenset({"reviewer", "ux"}))
        assert result == GateDecision.ALL_APPROVED

    def test_single_required_role_approved_transitions(self) -> None:
        """Even with only 1 required role, APPROVED transitions to ALL_APPROVED."""
        v = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        result = compute_decision((v,), frozenset({"reviewer"}))
        assert result == GateDecision.ALL_APPROVED

    def test_extra_verdicts_beyond_required_still_all_approved(self) -> None:
        """Additional APPROVED verdicts beyond required set don't block ALL_APPROVED."""
        v1 = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        v2 = make_verdict(role="ux", decision=VerdictDecision.APPROVED)
        # required = {"reviewer"} only; ux is extra but still APPROVED → ALL_APPROVED.
        result = compute_decision((v1, v2), frozenset({"reviewer"}))
        assert result == GateDecision.ALL_APPROVED


# ---------------------------------------------------------------------------
# TC-UT-IRG-005 (re): REJECTED condition — most-pessimistic-wins
# ---------------------------------------------------------------------------
class TestComputeDecisionRejected:
    """compute_decision → REJECTED immediately when any verdict is REJECTED."""

    def test_single_rejected_wins_immediately(self) -> None:
        """1 REJECTED with 2 roles pending → REJECTED (most-pessimistic-wins)."""
        v = make_verdict(role="security", decision=VerdictDecision.REJECTED)
        result = compute_decision((v,), frozenset({"reviewer", "ux", "security"}))
        assert result == GateDecision.REJECTED

    def test_rejected_overrides_approved(self) -> None:
        """REJECTED wins even when other roles have APPROVED."""
        v_approved = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        v_rejected = make_verdict(role="ux", decision=VerdictDecision.REJECTED)
        result = compute_decision(
            (v_approved, v_rejected), frozenset({"reviewer", "ux"})
        )
        assert result == GateDecision.REJECTED

    def test_rejected_checked_before_all_approved(self) -> None:
        """Rule 1 (REJECTED check) fires before Rule 2 (ALL_APPROVED check).

        If all required roles submitted, but one of them is REJECTED,
        the result must be REJECTED, not ALL_APPROVED.
        """
        v_approved = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        v_rejected = make_verdict(role="ux", decision=VerdictDecision.REJECTED)
        # Both required roles submitted → Rule 2 would fire if Rule 1 didn't exist.
        result = compute_decision(
            (v_approved, v_rejected), frozenset({"reviewer", "ux"})
        )
        assert result == GateDecision.REJECTED


# ---------------------------------------------------------------------------
# §確定 C: compute_decision is Final-locked public alias
# ---------------------------------------------------------------------------
class TestComputeDecisionFinalLock:
    """§確定 C: compute_decision is the public alias of _compute_decision."""

    def test_compute_decision_is_the_private_implementation(self) -> None:
        """The public alias must point at _compute_decision (same object)."""
        assert compute_decision is _compute_decision

    def test_compute_decision_is_callable(self) -> None:
        result = compute_decision((), frozenset({"reviewer"}))
        assert isinstance(result, GateDecision)
