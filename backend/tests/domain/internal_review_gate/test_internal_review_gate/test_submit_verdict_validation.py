"""InternalReviewGate submit_verdict validation tests (TC-UT-IRG-008〜017)."""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import InternalReviewGateInvariantViolation
from bakufu.domain.value_objects import VerdictDecision
from pydantic import ValidationError

from tests.factories.internal_review_gate import (
    make_all_approved_gate,
    make_gate,
)


def _ts() -> datetime:
    return datetime.now(UTC)


class TestCommentBoundary:
    """TC-UT-IRG-008: comment 長 0 / 5000 は OK、5001 は comment_too_long。"""

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
        nfd_form = unicodedata.normalize("NFD", "が")
        gate = make_gate(required_gate_roles=frozenset({"reviewer"}))
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment=nfd_form * 5000,
            decided_at=_ts(),
        )
        assert len(new_gate.verdicts[0].comment) == 5000


class TestInvalidRole:
    """TC-UT-IRG-009: required_gate_roles に含まれない role は invalid_role を発火する。"""

    def test_role_not_in_required_raises(self) -> None:
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="security",
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


class TestVerdictDecisionTwoValuesOnly:
    """TC-UT-IRG-011: VerdictDecision の有効値は APPROVED と REJECTED のみ。"""

    @pytest.mark.parametrize("bad_value", ["ambiguous", "maybe", "conditional", "pending"])
    def test_invalid_verdict_decision_raises_validation_error(self, bad_value: str) -> None:
        from bakufu.domain.value_objects import Verdict

        with pytest.raises(ValidationError):
            Verdict(
                role="reviewer",
                agent_id=uuid4(),
                decision=bad_value,  # pyright: ignore[reportArgumentType]
                comment="",
                decided_at=datetime.now(UTC),
            )


class TestCommentNFCNoStrip:
    """TC-UT-IRG-012: comment は NFC 正規化するが前後の空白は保持する。"""

    def test_trailing_newline_preserved(self) -> None:
        gate = make_gate(required_gate_roles=frozenset({"reviewer"}))
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="\n承認コメント\n",
            decided_at=_ts(),
        )
        assert new_gate.verdicts[0].comment.startswith("\n")
        assert new_gate.verdicts[0].comment.endswith("\n")

    def test_nfd_form_normalized_to_nfc(self) -> None:
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


class TestMsgTwoLineStructure:
    """TC-UT-IRG-013〜016: エラーメッセージは 2 行構造を持つ。"""

    def test_msg_irg_001_starts_with_fail_and_has_next(self) -> None:
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


class TestApplicationLayerResponsibility:
    """TC-UT-IRG-017: Aggregate は ID の参照整合性を検証しない。"""

    def test_nonexistent_task_id_accepted(self) -> None:
        gate = make_gate(task_id=uuid4())
        assert gate.task_id is not None

    def test_nonexistent_stage_id_accepted(self) -> None:
        gate = make_gate(stage_id=uuid4())
        assert gate.stage_id is not None

    def test_nonexistent_agent_id_in_verdict_accepted(self) -> None:
        gate = make_gate(required_gate_roles=frozenset({"reviewer"}))
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        assert len(new_gate.verdicts) == 1
