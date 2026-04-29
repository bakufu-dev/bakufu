"""InternalReviewGate construction tests (TC-UT-IRG-001, 002, 010, 018, 019, 020).

Per ``docs/features/internal-review-gate/domain/test-design.md`` §構築 + 不変条件.
Covers:
  TC-UT-IRG-001  正常構築(REQ-IRG-001, AC#2)
  TC-UT-IRG-002  required_gate_roles 空集合拒否(REQ-IRG-001/004, AC#2)
  TC-UT-IRG-010  gate_decision / verdicts 整合性違反(REQ-IRG-004, AC#4, 5)
  TC-UT-IRG-018  frozen 不変性(Q-3)
  TC-UT-IRG-019  frozen 構造的等価 / hash(Q-3)
  TC-UT-IRG-020  extra='forbid' 未知フィールド拒否(Q-3)

Issue: #65
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import InternalReviewGateInvariantViolation
from bakufu.domain.internal_review_gate import InternalReviewGate
from bakufu.domain.value_objects import GateDecision, VerdictDecision
from pydantic import ValidationError

from tests.factories.internal_review_gate import (
    is_synthetic,
    make_gate,
    make_verdict,
)


# ---------------------------------------------------------------------------
# TC-UT-IRG-001: 正常構築 (REQ-IRG-001, AC#2)
# ---------------------------------------------------------------------------
class TestGateDefaults:
    """TC-UT-IRG-001: factory default Gate is PENDING, empty verdicts, UTC created_at."""

    def test_default_gate_decision_is_pending(self) -> None:
        """Freshly created Gate has gate_decision=PENDING."""
        gate = make_gate()
        assert gate.gate_decision == GateDecision.PENDING

    def test_default_verdicts_is_empty_tuple(self) -> None:
        """Verdicts start as an empty tuple (not a list)."""
        gate = make_gate()
        assert gate.verdicts == ()

    def test_default_created_at_is_tz_aware(self) -> None:
        """created_at must carry timezone info (UTC-aware)."""
        gate = make_gate()
        assert gate.created_at.tzinfo is not None

    def test_default_required_roles_is_nonempty(self) -> None:
        """Default factory provides at least one required role."""
        gate = make_gate()
        assert len(gate.required_gate_roles) > 0

    def test_factory_marks_instance_synthetic(self) -> None:
        """Factory output is registered in is_synthetic."""
        gate = make_gate()
        assert is_synthetic(gate)


# ---------------------------------------------------------------------------
# TC-UT-IRG-002: required_gate_roles 空集合 → raise (REQ-IRG-001/004, AC#2)
# ---------------------------------------------------------------------------
class TestRequiredGateRolesEmpty:
    """TC-UT-IRG-002: empty required_gate_roles raises at construction time."""

    def test_empty_roles_raises_invariant_violation(self) -> None:
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            make_gate(required_gate_roles=frozenset())
        assert exc_info.value.kind == "required_gate_roles_empty"

    def test_empty_roles_error_has_next_hint(self) -> None:
        """MSG 2行構造: error message contains 'Next:' hint (R1-G)."""
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            make_gate(required_gate_roles=frozenset())
        assert "Next:" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TC-UT-IRG-010: gate_decision / verdicts 整合性違反 (REQ-IRG-004, AC#4, 5)
# ---------------------------------------------------------------------------
class TestGateDecisionInconsistency:
    """TC-UT-IRG-010: directly constructing inconsistent gate_decision raises."""

    def test_all_approved_with_empty_verdicts_raises(self) -> None:
        """gate_decision=ALL_APPROVED + verdicts=[] is inconsistent."""
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            InternalReviewGate.model_validate(
                {
                    "id": uuid4(),
                    "task_id": uuid4(),
                    "stage_id": uuid4(),
                    "required_gate_roles": frozenset({"reviewer"}),
                    "verdicts": [],
                    "gate_decision": GateDecision.ALL_APPROVED,
                    "created_at": datetime.now(UTC),
                }
            )
        assert exc_info.value.kind == "gate_decision_inconsistent"

    def test_pending_with_rejected_verdict_raises(self) -> None:
        """gate_decision=PENDING + REJECTED Verdict is inconsistent."""
        rejected = make_verdict(role="reviewer", decision=VerdictDecision.REJECTED)
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            InternalReviewGate.model_validate(
                {
                    "id": uuid4(),
                    "task_id": uuid4(),
                    "stage_id": uuid4(),
                    "required_gate_roles": frozenset({"reviewer"}),
                    "verdicts": [rejected.model_dump()],
                    "gate_decision": GateDecision.PENDING,
                    "created_at": datetime.now(UTC),
                }
            )
        assert exc_info.value.kind == "gate_decision_inconsistent"

    def test_inconsistency_error_has_next_hint(self) -> None:
        """MSG 2行構造: inconsistency error contains 'Next:'."""
        with pytest.raises(InternalReviewGateInvariantViolation) as exc_info:
            InternalReviewGate.model_validate(
                {
                    "id": uuid4(),
                    "task_id": uuid4(),
                    "stage_id": uuid4(),
                    "required_gate_roles": frozenset({"reviewer"}),
                    "verdicts": [],
                    "gate_decision": GateDecision.ALL_APPROVED,
                    "created_at": datetime.now(UTC),
                }
            )
        assert "Next:" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TC-UT-IRG-018: frozen 不変性 (Q-3)
# ---------------------------------------------------------------------------
class TestFrozenInstance:
    """TC-UT-IRG-018: attribute assignment on frozen Gate raises ValidationError."""

    def test_gate_decision_assignment_raises(self) -> None:
        """Direct assignment to gate_decision is rejected (frozen model)."""
        gate = make_gate()
        with pytest.raises(ValidationError):
            gate.gate_decision = GateDecision.ALL_APPROVED  # pyright: ignore[reportAttributeAccessIssue]

    def test_verdicts_assignment_raises(self) -> None:
        """Direct assignment to verdicts is rejected (frozen model)."""
        gate = make_gate()
        with pytest.raises(ValidationError):
            gate.verdicts = ()  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# TC-UT-IRG-019: frozen 構造的等価 / hash (Q-3)
# ---------------------------------------------------------------------------
class TestFrozenStructuralEquality:
    """TC-UT-IRG-019: same-attribute Gates are == and share equal hash."""

    def _build_gate(self, gate_id: object, task_id: object, stage_id: object) -> InternalReviewGate:
        ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        return InternalReviewGate.model_validate(
            {
                "id": gate_id,
                "task_id": task_id,
                "stage_id": stage_id,
                "required_gate_roles": frozenset({"reviewer", "ux"}),
                "verdicts": [],
                "gate_decision": GateDecision.PENDING,
                "created_at": ts,
            }
        )

    def test_same_attributes_compare_equal(self) -> None:
        common_id = uuid4()
        common_task = uuid4()
        common_stage = uuid4()
        a = self._build_gate(common_id, common_task, common_stage)
        b = self._build_gate(common_id, common_task, common_stage)
        assert a == b

    def test_same_attributes_have_equal_hash(self) -> None:
        common_id = uuid4()
        common_task = uuid4()
        common_stage = uuid4()
        a = self._build_gate(common_id, common_task, common_stage)
        b = self._build_gate(common_id, common_task, common_stage)
        assert hash(a) == hash(b)


# ---------------------------------------------------------------------------
# TC-UT-IRG-020: extra='forbid' 未知フィールド拒否 (Q-3)
# ---------------------------------------------------------------------------
class TestExtraForbid:
    """TC-UT-IRG-020: unknown field at construction raises ValidationError."""

    def test_unknown_field_via_model_validate_raises(self) -> None:
        with pytest.raises(ValidationError):
            InternalReviewGate.model_validate(
                {
                    "id": uuid4(),
                    "task_id": uuid4(),
                    "stage_id": uuid4(),
                    "required_gate_roles": frozenset({"reviewer"}),
                    "verdicts": [],
                    "gate_decision": GateDecision.PENDING,
                    "created_at": datetime.now(UTC),
                    "unknown_field": "should-be-rejected",
                }
            )
