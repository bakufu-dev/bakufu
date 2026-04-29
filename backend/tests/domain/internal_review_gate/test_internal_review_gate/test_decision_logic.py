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
        """1/2 必須ロール承認 → PENDING（全ロール必須）."""
        v_reviewer = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        result = compute_decision((v_reviewer,), frozenset({"reviewer", "ux"}))
        assert result == GateDecision.PENDING

    def test_superset_required_roles_missing_stays_pending(self) -> None:
        """3 必須ロール、2 承認 → PENDING（1 件未提出）."""
        v1 = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        v2 = make_verdict(role="ux", decision=VerdictDecision.APPROVED)
        result = compute_decision((v1, v2), frozenset({"reviewer", "ux", "security"}))
        assert result == GateDecision.PENDING


# ---------------------------------------------------------------------------
# TC-UT-IRG-004 (re): ALL_APPROVED condition
# ---------------------------------------------------------------------------
class TestComputeDecisionAllApproved:
    """全必須ロール承認時に compute_decision → ALL_APPROVED."""

    def test_all_required_approved_transitions(self) -> None:
        """全必須ロール承認 → ALL_APPROVED."""
        v1 = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        v2 = make_verdict(role="ux", decision=VerdictDecision.APPROVED)
        result = compute_decision((v1, v2), frozenset({"reviewer", "ux"}))
        assert result == GateDecision.ALL_APPROVED

    def test_single_required_role_approved_transitions(self) -> None:
        """必須ロール 1 件でも承認で ALL_APPROVED に遷移."""
        v = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        result = compute_decision((v,), frozenset({"reviewer"}))
        assert result == GateDecision.ALL_APPROVED

    def test_extra_verdicts_beyond_required_still_all_approved(self) -> None:
        """必須外の追加承認判定は ALL_APPROVED をブロックしない."""
        v1 = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        v2 = make_verdict(role="ux", decision=VerdictDecision.APPROVED)
        # required = {"reviewer"} のみ。ux は追加だが承認 → ALL_APPROVED
        result = compute_decision((v1, v2), frozenset({"reviewer"}))
        assert result == GateDecision.ALL_APPROVED


# ---------------------------------------------------------------------------
# TC-UT-IRG-005 (re): REJECTED condition — most-pessimistic-wins
# ---------------------------------------------------------------------------
class TestComputeDecisionRejected:
    """いずれかの判定が却下時に compute_decision → 即座に REJECTED."""

    def test_single_rejected_wins_immediately(self) -> None:
        """1 却下、2 ロール保留中 → REJECTED（最悲観的ルール優先）."""
        v = make_verdict(role="security", decision=VerdictDecision.REJECTED)
        result = compute_decision((v,), frozenset({"reviewer", "ux", "security"}))
        assert result == GateDecision.REJECTED

    def test_rejected_overrides_approved(self) -> None:
        """他のロールが承認でも却下が優先."""
        v_approved = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        v_rejected = make_verdict(role="ux", decision=VerdictDecision.REJECTED)
        result = compute_decision((v_approved, v_rejected), frozenset({"reviewer", "ux"}))
        assert result == GateDecision.REJECTED

    def test_rejected_checked_before_all_approved(self) -> None:
        """ルール 1（却下チェック）がルール 2（全承認チェック）より先に発火.

        全必須ロール提出でも 1 件が却下なら、結果は ALL_APPROVED でなく
        REJECTED でなければならない。
        """
        v_approved = make_verdict(role="reviewer", decision=VerdictDecision.APPROVED)
        v_rejected = make_verdict(role="ux", decision=VerdictDecision.REJECTED)
        # 両必須ロール提出。ルール 1 がなければルール 2 が発火
        result = compute_decision((v_approved, v_rejected), frozenset({"reviewer", "ux"}))
        assert result == GateDecision.REJECTED


# ---------------------------------------------------------------------------
# §確定 C: compute_decision is Final-locked public alias
# ---------------------------------------------------------------------------
class TestComputeDecisionFinalLock:
    """§確定 C: compute_decision は _compute_decision の公開エイリアス."""

    def test_compute_decision_is_the_private_implementation(self) -> None:
        """公開エイリアスは _compute_decision を指す（同一オブジェクト）."""
        assert compute_decision is _compute_decision

    def test_compute_decision_is_callable(self) -> None:
        result = compute_decision((), frozenset({"reviewer"}))
        assert isinstance(result, GateDecision)
