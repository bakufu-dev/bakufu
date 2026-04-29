"""InternalReviewGate submit_verdict tests (TC-UT-IRG-003〜017).

Per ``docs/features/internal-review-gate/domain/test-design.md`` §submit_verdict.
Covers:
  TC-UT-IRG-003  APPROVED 提出 → PENDING 継続(REQ-IRG-002, AC#3)
  TC-UT-IRG-004  全 GateRole APPROVED → ALL_APPROVED 遷移(REQ-IRG-002/003, AC#4)
  TC-UT-IRG-005  1件 REJECTED → REJECTED 即遷移(REQ-IRG-002/003, AC#5)
  TC-UT-IRG-006  同一 GateRole 重複提出 → raise(REQ-IRG-002/004, AC#6)
  TC-UT-IRG-007  確定後の追加 Verdict → raise(REQ-IRG-002, AC#7)
  TC-UT-IRG-008  comment 境界値(0 / 5000 / 5001 文字)(REQ-IRG-002, AC#11)
  TC-UT-IRG-009  invalid_role(REQ-IRG-004, AC#2,3)
  TC-UT-IRG-011  VerdictDecision 2 値のみ(§確定 F, Q-3)
  TC-UT-IRG-012  comment NFC + strip しない(§確定 G, Q-3)
  TC-UT-IRG-013  MSG-IRG-001 2行構造(§確定 H, Q-3)
  TC-UT-IRG-014  MSG-IRG-002 2行構造(§確定 H, Q-3)
  TC-UT-IRG-015  MSG-IRG-003 2行構造(§確定 H, Q-3)
  TC-UT-IRG-016  MSG-IRG-004 2行構造(§確定 H, Q-3)
  TC-UT-IRG-017  application 層責務(§確定 I, Q-3)

Issue: #65
"""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import InternalReviewGateInvariantViolation
from bakufu.domain.value_objects import GateDecision, VerdictDecision
from pydantic import ValidationError

from tests.factories.internal_review_gate import (
    make_all_approved_gate,
    make_gate,
)

# Shared UTC timestamp helper.
_NOW = datetime.now(UTC)


def _ts() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# TC-UT-IRG-003: APPROVED Verdict 提出 → PENDING 継続 (REQ-IRG-002, AC#3)
# ---------------------------------------------------------------------------
class TestSubmitVerdictPending:
    """TC-UT-IRG-003: partial submission keeps gate PENDING."""

    def test_single_approved_out_of_three_stays_pending(self) -> None:
        """1/3 APPROVED → gate_decision=PENDING."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux", "security"}))
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="LGTM",
            decided_at=_ts(),
        )
        assert new_gate.gate_decision == GateDecision.PENDING

    def test_partial_submission_appends_one_verdict(self) -> None:
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux", "security"}))
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        assert len(new_gate.verdicts) == 1

    def test_source_gate_is_unchanged_after_submission(self) -> None:
        """Frozen pre-validate pattern: original Gate must not be mutated."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        snapshot = gate.model_dump()
        gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        assert gate.model_dump() == snapshot


# ---------------------------------------------------------------------------
# TC-UT-IRG-004: 全 GateRole APPROVED → ALL_APPROVED 遷移 (AC#4)
# ---------------------------------------------------------------------------
class TestSubmitVerdictAllApproved:
    """TC-UT-IRG-004: all required roles APPROVED → ALL_APPROVED."""

    def test_all_approved_transitions_to_all_approved(self) -> None:
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

    def test_all_approved_gate_has_two_verdicts(self) -> None:
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
        assert len(gate.verdicts) == 2


# ---------------------------------------------------------------------------
# TC-UT-IRG-005: 1件 REJECTED → REJECTED 即遷移(残り未提出でも)(AC#5)
# ---------------------------------------------------------------------------
class TestSubmitVerdictRejectedImmediate:
    """TC-UT-IRG-005: single REJECTED transitions immediately, pending roles irrelevant."""

    def test_one_rejected_transitions_immediately(self) -> None:
        """1/3 roles REJECTED → gate_decision=REJECTED (other 2 roles still pending)."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux", "security"}))
        new_gate = gate.submit_verdict(
            role="security",
            agent_id=uuid4(),
            decision=VerdictDecision.REJECTED,
            comment="バグ発見",
            decided_at=_ts(),
        )
        assert new_gate.gate_decision == GateDecision.REJECTED

    def test_rejected_gate_has_only_one_verdict(self) -> None:
        """Remaining 2 roles are not submitted; only 1 REJECTED verdict present."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux", "security"}))
        new_gate = gate.submit_verdict(
            role="security",
            agent_id=uuid4(),
            decision=VerdictDecision.REJECTED,
            comment="バグ発見",
            decided_at=_ts(),
        )
        assert len(new_gate.verdicts) == 1

    def test_rejected_verdict_comment_is_recorded(self) -> None:
        """Feedback comment from REJECTED verdict is stored (AC#5)."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.REJECTED,
            comment="テスト失敗あり",
            decided_at=_ts(),
        )
        assert new_gate.verdicts[0].comment == "テスト失敗あり"


# ---------------------------------------------------------------------------
# TC-UT-IRG-006: 同一 GateRole 重複提出 → raise (REQ-IRG-002/004, AC#6)
# ---------------------------------------------------------------------------
class TestRoleAlreadySubmitted:
    """TC-UT-IRG-006: re-submission of the same role raises role_already_submitted."""

    def test_duplicate_role_raises(self) -> None:
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="reviewer",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="",
                decided_at=_ts(),
            )
        assert exc_info.value.kind == "role_already_submitted"

    def test_duplicate_raises_before_gate_already_decided(self) -> None:
        """Step order: role_already_submitted fires at step 2 (gate is still PENDING)."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        # Submit reviewer once — gate stays PENDING.
        gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        assert gate.gate_decision == GateDecision.PENDING
        # Re-submit same role → role_already_submitted (not gate_already_decided).
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="reviewer",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="",
                decided_at=_ts(),
            )
        assert exc_info.value.kind == "role_already_submitted"


# ---------------------------------------------------------------------------
# TC-UT-IRG-007: 確定後の追加 Verdict → raise (REQ-IRG-002, AC#7)
# ---------------------------------------------------------------------------
class TestGateAlreadyDecided:
    """TC-UT-IRG-007: any submission to ALL_APPROVED/REJECTED Gate raises gate_already_decided."""

    def test_submit_to_all_approved_gate_raises(self) -> None:
        # Build a gate whose required roles include "reviewer" so we hit
        # gate_already_decided rather than invalid_role first.
        all_approved = make_all_approved_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            all_approved.submit_verdict(
                role="reviewer",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="",
                decided_at=_ts(),
            )
        assert exc_info.value.kind == "gate_already_decided"

    def test_submit_to_rejected_gate_raises(self) -> None:
        from tests.factories.internal_review_gate import make_rejected_gate

        gate = make_rejected_gate()
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="ux",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="",
                decided_at=_ts(),
            )
        assert exc_info.value.kind == "gate_already_decided"

    def test_gate_already_decided_fires_before_role_already_submitted(self) -> None:
        """Step 1 (gate_already_decided) fires before step 2 (role_already_submitted)."""
        # Create a gate where the ALL_APPROVED was reached via reviewer + ux.
        all_approved = make_all_approved_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        # Try to re-submit "reviewer" (which is both already decided AND role already submitted).
        # Step 1 must win.
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            all_approved.submit_verdict(
                role="reviewer",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="",
                decided_at=_ts(),
            )
        assert exc_info.value.kind == "gate_already_decided"


# ---------------------------------------------------------------------------
# TC-UT-IRG-008: comment 境界値 (REQ-IRG-002, AC#11)
# ---------------------------------------------------------------------------
class TestCommentBoundary:
    """TC-UT-IRG-008: comment length 0 / 5000 OK; 5001 raises comment_too_long."""

    def test_empty_comment_accepted(self) -> None:
        gate = make_gate(required_gate_roles=frozenset({"reviewer"}))
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        assert new_gate.verdicts[0].comment == ""

    def test_5000_char_comment_accepted(self) -> None:
        gate = make_gate(required_gate_roles=frozenset({"reviewer"}))
        comment = "a" * 5000
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment=comment,
            decided_at=_ts(),
        )
        assert len(new_gate.verdicts[0].comment) == 5000

    def test_5001_char_comment_raises(self) -> None:
        gate = make_gate(required_gate_roles=frozenset({"reviewer"}))
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="reviewer",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="a" * 5001,
                decided_at=_ts(),
            )
        assert exc_info.value.kind == "comment_too_long"

    def test_comment_length_checked_after_nfc_normalization(self) -> None:
        """5000 chars after NFC normalization are accepted regardless of raw form."""
        # NFD 'が' (2 code points) normalizes to NFC 'が' (1 code point).
        # Build a string that is exactly 5000 NFC chars.
        nfc_char = "が"  # 1 NFC code point
        nfd_form = unicodedata.normalize("NFD", nfc_char)  # 2 code points in NFD
        comment = nfd_form * 5000  # 10000 raw code points → 5000 NFC chars
        gate = make_gate(required_gate_roles=frozenset({"reviewer"}))
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment=comment,
            decided_at=_ts(),
        )
        assert len(new_gate.verdicts[0].comment) == 5000


# ---------------------------------------------------------------------------
# TC-UT-IRG-009: invalid_role (REQ-IRG-004, AC#2, 3)
# ---------------------------------------------------------------------------
class TestInvalidRole:
    """TC-UT-IRG-009: role not in required_gate_roles raises invalid_role."""

    def test_role_not_in_required_raises(self) -> None:
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="security",  # not in required_gate_roles
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="",
                decided_at=_ts(),
            )
        assert exc_info.value.kind == "invalid_role"

    def test_invalid_role_detail_contains_role(self) -> None:
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="security",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="",
                decided_at=_ts(),
            )
        assert exc_info.value.detail.get("role") == "security"


# ---------------------------------------------------------------------------
# TC-UT-IRG-011: VerdictDecision 2 値のみ (§確定 F, Q-3)
# ---------------------------------------------------------------------------
class TestVerdictDecisionTwoValuesOnly:
    """TC-UT-IRG-011: only APPROVED and REJECTED are valid VerdictDecision values."""

    @pytest.mark.parametrize("bad_value", ["ambiguous", "maybe", "conditional", "pending"])
    def test_invalid_verdict_decision_raises_validation_error(self, bad_value: str) -> None:
        """§確定 F: values other than APPROVED/REJECTED are type errors."""
        from bakufu.domain.value_objects import Verdict

        with pytest.raises(ValidationError):
            Verdict(
                role="reviewer",
                agent_id=uuid4(),
                decision=bad_value,  # pyright: ignore[reportArgumentType]
                comment="",
                decided_at=datetime.now(UTC),
            )


# ---------------------------------------------------------------------------
# TC-UT-IRG-012: comment NFC + strip しない (§確定 G, Q-3)
# ---------------------------------------------------------------------------
class TestCommentNFCNoStrip:
    """TC-UT-IRG-012: comment is NFC-normalized but leading/trailing whitespace preserved."""

    def test_trailing_newline_preserved(self) -> None:
        """Trailing newlines in comment are preserved (no strip)."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer"}))
        raw = "\n承認コメント\n"
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment=raw,
            decided_at=_ts(),
        )
        assert new_gate.verdicts[0].comment.startswith("\n")
        assert new_gate.verdicts[0].comment.endswith("\n")

    def test_nfd_form_normalized_to_nfc(self) -> None:
        """NFD-decomposed characters are composed to NFC form."""
        # 'か' + combining dakuten (U+3099) = NFD 'が'; NFC = 'が' (U+304C)
        nfd_comment = "がレビュー"
        gate = make_gate(required_gate_roles=frozenset({"reviewer"}))
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment=nfd_comment,
            decided_at=_ts(),
        )
        expected = unicodedata.normalize("NFC", nfd_comment)
        assert new_gate.verdicts[0].comment == expected
        assert new_gate.verdicts[0].comment.startswith("が")


# ---------------------------------------------------------------------------
# TC-UT-IRG-013〜016: MSG 2 行構造 + Next: hint (§確定 H, Q-3)
# ---------------------------------------------------------------------------
class TestMsgTwoLineStructure:
    """TC-UT-IRG-013〜016: InternalReviewGateInvariantViolation messages have 2-line structure."""

    def test_msg_irg_001_starts_with_fail_and_has_next(self) -> None:
        """TC-UT-IRG-013: MSG-IRG-001 (role_already_submitted) — [FAIL]…\\nNext:…"""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="reviewer",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="",
                decided_at=_ts(),
            )
        msg = str(exc_info.value)
        assert msg.startswith("[FAIL]")
        assert "Next:" in msg

    def test_msg_irg_002_starts_with_fail_and_has_next(self) -> None:
        """TC-UT-IRG-014: MSG-IRG-002 (gate_already_decided) — [FAIL]…\\nNext:…"""
        all_approved = make_all_approved_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            all_approved.submit_verdict(
                role="reviewer",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="",
                decided_at=_ts(),
            )
        msg = str(exc_info.value)
        assert msg.startswith("[FAIL]")
        assert "Next:" in msg
        assert "新しい Gate" in msg

    def test_msg_irg_003_starts_with_fail_and_has_next(self) -> None:
        """TC-UT-IRG-015: MSG-IRG-003 (comment_too_long) — [FAIL]…\\nNext:…"""
        gate = make_gate(required_gate_roles=frozenset({"reviewer"}))
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="reviewer",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="a" * 5001,
                decided_at=_ts(),
            )
        msg = str(exc_info.value)
        assert msg.startswith("[FAIL]")
        assert "Next:" in msg
        assert "5000文字以内" in msg

    def test_msg_irg_004_starts_with_fail_and_has_next(self) -> None:
        """TC-UT-IRG-016: MSG-IRG-004 (invalid_role) — [FAIL]…\\nNext:…"""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="security",
                agent_id=uuid4(),
                decision=VerdictDecision.APPROVED,
                comment="",
                decided_at=_ts(),
            )
        msg = str(exc_info.value)
        assert msg.startswith("[FAIL]")
        assert "Next:" in msg
        assert "有効な GateRole" in msg


# ---------------------------------------------------------------------------
# TC-UT-IRG-017: application 層責務 / 参照整合性 (§確定 I, Q-3)
# ---------------------------------------------------------------------------
class TestApplicationLayerResponsibility:
    """TC-UT-IRG-017: Aggregate does not validate referential integrity of IDs."""

    def test_nonexistent_task_id_accepted(self) -> None:
        """Gate construction with a random (non-existent) task_id succeeds."""
        # The Aggregate holds only the UUID; it does NOT query a repository.
        gate = make_gate(task_id=uuid4())
        assert gate.task_id is not None

    def test_nonexistent_stage_id_accepted(self) -> None:
        gate = make_gate(stage_id=uuid4())
        assert gate.stage_id is not None

    def test_nonexistent_agent_id_in_verdict_accepted(self) -> None:
        """Verdict with a random (non-existent) agent_id submits successfully."""
        gate = make_gate(required_gate_roles=frozenset({"reviewer"}))
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),  # random, does not exist in any repository
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        assert len(new_gate.verdicts) == 1
