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

# 共有 UTC タイムスタンプヘルパ。
_NOW = datetime.now(UTC)


def _ts() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# TC-UT-IRG-003: APPROVED Verdict 提出 → PENDING 継続 (REQ-IRG-002, AC#3)
# ---------------------------------------------------------------------------
class TestSubmitVerdictPending:
    """TC-UT-IRG-003: 部分提出は gate を PENDING のまま維持する。"""

    def test_single_approved_out_of_three_stays_pending(self) -> None:
        """1/3 APPROVED → gate_decision=PENDING。"""
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
        """Frozen pre-validate パターン: 元 Gate は変更されない。"""
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
    """TC-UT-IRG-004: required な全 role が APPROVED → ALL_APPROVED。"""

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
    """TC-UT-IRG-005: 単一 REJECTED で即時遷移する (他の未提出 role は無関係)。"""

    def test_one_rejected_transitions_immediately(self) -> None:
        """1/3 roles REJECTED → gate_decision=REJECTED (残り 2 role は未提出のまま)。"""
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
        """残り 2 role は未提出。REJECTED の verdict が 1 件のみ存在する。"""
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
        """REJECTED verdict のフィードバックコメントが保存される (AC#5)。"""
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
    """TC-UT-IRG-006: 同一 role の再提出は role_already_submitted を発火する。"""

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
        """ステップ順: role_already_submitted は step 2 で発火する (gate は PENDING のまま)。"""
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        # reviewer を 1 度提出 ── gate は PENDING のまま。
        gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        assert gate.gate_decision == GateDecision.PENDING
        # 同一 role を再提出 → role_already_submitted (gate_already_decided ではない)。
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
    """TC-UT-IRG-007: ALL_APPROVED/REJECTED Gate への任意提出で gate_already_decided が発火。"""

    def test_submit_to_all_approved_gate_raises(self) -> None:
        # required role に "reviewer" を含む gate を構築する ──
        # invalid_role ではなく gate_already_decided が先に発火するように。
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
        """Step 1 (gate_already_decided) は step 2 (role_already_submitted) より先に発火する。"""
        # reviewer + ux 経由で ALL_APPROVED に達した gate を作る。
        all_approved = make_all_approved_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        # "reviewer" を再提出する (already decided かつ role already submitted の両方に該当)。
        # Step 1 が勝たねばならない。
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
        """NFC 正規化後 5000 文字は、生形に関わらず受理される。"""
        # NFD 'が' (2 コードポイント) は NFC'が' (1 コードポイント) に正規化される。
        # 厳密に NFC 5000 文字となる文字列を構築する。
        nfc_char = "が"  # NFC で 1 コードポイント
        nfd_form = unicodedata.normalize("NFD", nfc_char)  # NFD で 2 コードポイント
        comment = nfd_form * 5000  # 生では 10000 コードポイント、NFC で 5000 文字
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
    """TC-UT-IRG-009: required_gate_roles に含まれない role は invalid_role を発火する。"""

    def test_role_not_in_required_raises(self) -> None:
        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux"}))
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            gate.submit_verdict(
                role="security",  # required_gate_roles に含まれない
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
    """TC-UT-IRG-011: VerdictDecision の有効値は APPROVED と REJECTED のみ。"""

    @pytest.mark.parametrize("bad_value", ["ambiguous", "maybe", "conditional", "pending"])
    def test_invalid_verdict_decision_raises_validation_error(self, bad_value: str) -> None:
        """§確定 F: APPROVED / REJECTED 以外の値は型エラーとなる。"""
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
    """TC-UT-IRG-012: comment は NFC 正規化するが前後の空白は保持する。"""

    def test_trailing_newline_preserved(self) -> None:
        """comment 末尾の改行は保持される (strip しない)。"""
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
        """NFD 分解された文字は NFC 形に合成される。"""
        # 'か' + 結合濁点 (U+3099) = NFD 'が'。NFC = 'が' (U+304C)
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
    """TC-UT-IRG-013〜016: InternalReviewGateInvariantViolation メッセージは 2 行構造を持つ。"""

    def test_msg_irg_001_starts_with_fail_and_has_next(self) -> None:
        """TC-UT-IRG-013: MSG-IRG-001 (role_already_submitted) ── [FAIL]…\\nNext:…"""
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
        """TC-UT-IRG-014: MSG-IRG-002 (gate_already_decided) ── [FAIL]…\\nNext:…"""
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
        """TC-UT-IRG-015: MSG-IRG-003 (comment_too_long) ── [FAIL]…\\nNext:…"""
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
        """TC-UT-IRG-016: MSG-IRG-004 (invalid_role) ── [FAIL]…\\nNext:…"""
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
    """TC-UT-IRG-017: Aggregate は ID の参照整合性を検証しない。"""

    def test_nonexistent_task_id_accepted(self) -> None:
        """ランダム (非存在) な task_id でも Gate を構築できる。"""
        # Aggregate は UUID のみを保持し、Repository に問い合わせない。
        gate = make_gate(task_id=uuid4())
        assert gate.task_id is not None

    def test_nonexistent_stage_id_accepted(self) -> None:
        gate = make_gate(stage_id=uuid4())
        assert gate.stage_id is not None

    def test_nonexistent_agent_id_in_verdict_accepted(self) -> None:
        """ランダム (非存在) な agent_id を持つ Verdict も提出に成功する。"""
        gate = make_gate(required_gate_roles=frozenset({"reviewer"}))
        new_gate = gate.submit_verdict(
            role="reviewer",
            agent_id=uuid4(),  # ランダム値。どの Repository にも存在しない
            decision=VerdictDecision.APPROVED,
            comment="",
            decided_at=_ts(),
        )
        assert len(new_gate.verdicts) == 1
