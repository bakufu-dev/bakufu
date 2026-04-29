"""InternalReviewGate aggregate-internal integration tests (TC-IT-IRG-001, 002).

Per ``docs/features/internal-review-gate/domain/test-design.md`` §結合テストケース.

"Integration" in this module means **Aggregate-internal module collaboration**
(InternalReviewGate ↔ state_machine ↔ aggregate_validators ↔ Verdict VO) without
any external I/O — same zero-IO pattern as the sibling agent / directive / room /
workflow integration tests.

Covers:
  TC-IT-IRG-001  Gate lifecycle 完走(PENDING → ALL_APPROVED)(AC#2, 3, 4)
  TC-IT-IRG-002  REJECTED 経路(1件 REJECTED → 即遷移、残り未提出でも)(AC#5)

Issue: #65
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import InternalReviewGateInvariantViolation
from bakufu.domain.value_objects import GateDecision, VerdictDecision

from tests.factories.internal_review_gate import make_gate


def _ts() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# TC-IT-IRG-001: Gate lifecycle 完走(PENDING → ALL_APPROVED)
# ---------------------------------------------------------------------------
class TestGateLifecycleAllApproved:
    """TC-IT-IRG-001: full multi-step lifecycle PENDING → partial → ALL_APPROVED → guard."""

    def test_lifecycle_reaches_all_approved(self) -> None:
        """Step 1 (reviewer APPROVED) keeps PENDING; step 2 (ux APPROVED) → ALL_APPROVED."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))

        # Step 1: reviewer APPROVED → still PENDING.
        reviewer_agent = uuid4()
        gate_after_reviewer = gate.submit_verdict(
            role="reviewer",
            agent_id=reviewer_agent,
            decision=VerdictDecision.APPROVED,
            comment="コードレビューOK",
            decided_at=_ts(),
        )
        assert gate_after_reviewer.gate_decision == GateDecision.PENDING
        assert len(gate_after_reviewer.verdicts) == 1

        # Step 2: ux APPROVED → ALL_APPROVED.
        ux_agent = uuid4()
        gate_final = gate_after_reviewer.submit_verdict(
            role="ux",
            agent_id=ux_agent,
            decision=VerdictDecision.APPROVED,
            comment="UI確認OK",
            decided_at=_ts(),
        )
        assert gate_final.gate_decision == GateDecision.ALL_APPROVED
        assert len(gate_final.verdicts) == 2

    def test_all_approved_gate_rejects_further_submission(self) -> None:
        """Step 3: submission to ALL_APPROVED Gate raises gate_already_decided."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        gate = gate.submit_verdict(
            role="ux",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        assert gate.gate_decision == GateDecision.ALL_APPROVED

        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="reviewer",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="",
                decided_at=_ts(),
            )
        assert exc_info.value.kind == "gate_already_decided"

    def test_source_gate_unchanged_throughout_lifecycle(self) -> None:
        """Pre-validate rebuild: every intermediate Gate is immutable."""
        gate_initial = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        snapshot_initial = gate_initial.model_dump()

        gate_mid = gate_initial.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        snapshot_mid = gate_mid.model_dump()

        gate_final = gate_mid.submit_verdict(
            role="ux",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )

        # Original and mid-state gates must not have changed.
        assert gate_initial.model_dump() == snapshot_initial
        assert gate_mid.model_dump() == snapshot_mid
        # Only the final gate is ALL_APPROVED.
        assert gate_final.gate_decision == GateDecision.ALL_APPROVED

    def test_all_approved_gate_attribute_consistency(self) -> None:
        """ALL_APPROVED Gate's attributes are internally consistent post-lifecycle."""
        roles = frozenset({"reviewer", "ux"})
        gate = make_gate(required_gate_roles=roles)
        gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="LGTM",
            decided_at=_ts(),
        )
        gate = gate.submit_verdict(
            role="ux",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="UX OK",
            decided_at=_ts(),
        )
        # All required roles have verdicts.
        submitted_roles = frozenset(v.role for v in gate.verdicts)
        assert submitted_roles == roles
        # Every verdict is APPROVED.
        assert all(v.decision == VerdictDecision.APPROVED for v in gate.verdicts)


# ---------------------------------------------------------------------------
# TC-IT-IRG-002: REJECTED 経路(1件 REJECTED → 即遷移、残り未提出でも)
# ---------------------------------------------------------------------------
class TestGateLifecycleRejected:
    """TC-IT-IRG-002: immediate REJECTED transition with remaining roles unpublished."""

    def test_single_rejected_transitions_immediately(self) -> None:
        """1 REJECTED out of 3 required → REJECTED; ux and security never submitted."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux", "security"}))

        gate_rejected = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.REJECTED,
            comment="バグ #123 を発見",
            decided_at=_ts(),
        )
        assert gate_rejected.gate_decision == GateDecision.REJECTED
        # Only 1 verdict: remaining 2 roles are still not submitted.
        assert len(gate_rejected.verdicts) == 1
        assert gate_rejected.verdicts[0].decision == VerdictDecision.REJECTED

    def test_rejected_gate_rejects_further_submission(self) -> None:
        """REJECTED Gate also rejects any new Verdict (gate_already_decided)."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux", "security"}))
        gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.REJECTED,
            comment="バグ発見",
            decided_at=_ts(),
        )
        assert gate.gate_decision == GateDecision.REJECTED

        # ux tries to APPROVE after Gate is already REJECTED.
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="ux",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="",
                decided_at=_ts(),
            )
        assert exc_info.value.kind == "gate_already_decided"

    def test_rejected_feedback_comment_preserved(self) -> None:
        """Feedback comment from the REJECTED verdict is accessible after transition."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        feedback = "テストカバレッジが不十分です。修正してください。"
        gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.REJECTED,
            comment=feedback,
            decided_at=_ts(),
        )
        assert gate.verdicts[0].comment == feedback
