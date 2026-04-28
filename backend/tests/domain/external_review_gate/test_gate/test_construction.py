"""ExternalReviewGate construction tests (TC-UT-GT-001 / 002 / 012).

Per ``docs/features/external-review-gate/test-design.md`` §Gate 構築.
Covers construction defaults, the 4 ``ReviewDecision`` rehydration
cases, frozen + structural equality, and ``extra='forbid'``.
"""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.external_review_gate import ExternalReviewGate
from bakufu.domain.value_objects import ReviewDecision
from pydantic import ValidationError

from tests.factories.external_review_gate import (
    is_synthetic,
    make_approved_gate,
    make_cancelled_gate,
    make_gate,
    make_rejected_gate,
)


# ---------------------------------------------------------------------------
# TC-UT-GT-001: default-valued construction
# ---------------------------------------------------------------------------
class TestGateDefaults:
    """TC-UT-GT-001: factory default Gate is structurally PENDING + empty."""

    def test_default_gate_is_pending_with_empty_state(self) -> None:
        """Defaults: decision=PENDING, audit_trail=[], feedback_text='', decided_at=None."""
        gate = make_gate()
        assert gate.decision == ReviewDecision.PENDING
        assert gate.audit_trail == []
        assert gate.feedback_text == ""
        assert gate.decided_at is None

    def test_factory_marks_instance_synthetic(self) -> None:
        """Factory output is registered in :func:`is_synthetic`."""
        gate = make_gate()
        assert is_synthetic(gate)


# ---------------------------------------------------------------------------
# TC-UT-GT-002: rehydration into all 4 ReviewDecision values
# ---------------------------------------------------------------------------
class TestRehydrateAllDecisions:
    """TC-UT-GT-002: each of the 4 ReviewDecision values constructs cleanly.

    Repository hydration must be able to land any persisted decision.
    Terminal states (APPROVED / REJECTED / CANCELLED) need a non-None
    ``decided_at`` per the consistency invariant; PENDING needs
    ``decided_at is None``.
    """

    def test_pending_constructs(self) -> None:
        assert make_gate().decision == ReviewDecision.PENDING

    def test_approved_constructs_with_decided_at(self) -> None:
        gate = make_approved_gate()
        assert gate.decision == ReviewDecision.APPROVED
        assert gate.decided_at is not None

    def test_rejected_constructs_with_decided_at(self) -> None:
        gate = make_rejected_gate()
        assert gate.decision == ReviewDecision.REJECTED
        assert gate.decided_at is not None

    def test_cancelled_constructs_with_decided_at(self) -> None:
        gate = make_cancelled_gate()
        assert gate.decision == ReviewDecision.CANCELLED
        assert gate.decided_at is not None


# ---------------------------------------------------------------------------
# TC-UT-GT-012: frozen + structural equality + hashable
# ---------------------------------------------------------------------------
class TestFrozenStructuralEquality:
    """TC-UT-GT-012: same-attribute Gates are ``==``."""

    def test_same_attributes_compare_equal(self) -> None:
        """Two Gate instances with identical attrs are ``==``."""
        common_id = uuid4()
        common_task = uuid4()
        common_stage = uuid4()
        common_reviewer = uuid4()
        ts = datetime(9999, 1, 1, 0, 0, 0, tzinfo=UTC)
        # Reuse the same Deliverable so both Gates share an identical
        # snapshot — equality requires snapshot equality.
        from tests.factories.task import make_deliverable

        snapshot = make_deliverable()
        a = make_gate(
            gate_id=common_id,
            task_id=common_task,
            stage_id=common_stage,
            reviewer_id=common_reviewer,
            deliverable_snapshot=snapshot,
            created_at=ts,
        )
        b = make_gate(
            gate_id=common_id,
            task_id=common_task,
            stage_id=common_stage,
            reviewer_id=common_reviewer,
            deliverable_snapshot=snapshot,
            created_at=ts,
        )
        assert a == b


# ---------------------------------------------------------------------------
# extra='forbid' rejects unknown fields
# ---------------------------------------------------------------------------
class TestExtraForbid:
    """An unknown field at construction time is rejected."""

    def test_unknown_field_rejected_via_model_validate(self) -> None:
        """``ExternalReviewGate.model_validate({..., 'unknown': 'x'})`` raises."""
        from tests.factories.task import make_deliverable

        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            ExternalReviewGate.model_validate(
                {
                    "id": uuid4(),
                    "task_id": uuid4(),
                    "stage_id": uuid4(),
                    "deliverable_snapshot": make_deliverable(),
                    "reviewer_id": uuid4(),
                    "created_at": now,
                    "unknown_field": "should-be-rejected",
                }
            )


# ---------------------------------------------------------------------------
# Frozen instance — direct attribute assignment rejected
# ---------------------------------------------------------------------------
class TestFrozenInstance:
    """``gate.<attr> = value`` raises on a frozen Pydantic model."""

    def test_decision_assignment_rejected(self) -> None:
        gate = make_gate()
        with pytest.raises(ValidationError):
            gate.decision = ReviewDecision.APPROVED  # pyright: ignore[reportAttributeAccessIssue]

    def test_audit_trail_assignment_rejected(self) -> None:
        gate = make_gate()
        with pytest.raises(ValidationError):
            gate.audit_trail = []  # pyright: ignore[reportAttributeAccessIssue]

    def test_deliverable_snapshot_assignment_rejected(self) -> None:
        """The §確定 D snapshot frozen layer (one of the triple-defense)."""
        from tests.factories.task import make_deliverable

        gate = make_gate()
        with pytest.raises(ValidationError):
            gate.deliverable_snapshot = make_deliverable()  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# Type errors land as pydantic.ValidationError (§確定 I)
# ---------------------------------------------------------------------------
class TestTypeErrorsRaisePydanticValidationError:
    """Type-shaped failures use ``pydantic.ValidationError`` (no kind concept).

    The §確定 I contract: structural / field-type errors are pure
    Pydantic validation errors; only the 5
    ``ExternalReviewGateInvariantViolation`` kinds are issued by the
    aggregate's invariants.
    """

    def test_naive_created_at_rejected(self) -> None:
        """``created_at`` without a timezone must be rejected."""
        naive = datetime.now()
        with pytest.raises(ValidationError):
            make_gate(created_at=naive)

    def test_naive_decided_at_rejected(self) -> None:
        """``decided_at`` without a timezone must be rejected when set."""
        naive = datetime.now()
        with pytest.raises(ValidationError):
            make_gate(decision=ReviewDecision.APPROVED, decided_at=naive)


# ---------------------------------------------------------------------------
# feedback_text NFC normalization (§確定 F)
# ---------------------------------------------------------------------------
class TestFeedbackTextNormalization:
    """``feedback_text`` is NFC-normalized but **not** stripped."""

    def test_leading_whitespace_preserved(self) -> None:
        """CEO indent style survives normalization (no strip)."""
        raw = "> 引用文\n  続き行\n"
        gate = make_gate(feedback_text=raw)
        assert gate.feedback_text == unicodedata.normalize("NFC", raw)
        assert gate.feedback_text.startswith(">")
        assert gate.feedback_text.endswith("\n")
