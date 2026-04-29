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

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import InternalReviewGateInvariantViolation
from bakufu.domain.value_objects import GateDecision, VerdictDecision

from tests.factories.internal_review_gate import (
    make_all_approved_gate,
    make_gate,
)


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
