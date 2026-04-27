"""Workflow lifecycle integration scenarios (TC-IT-WF-001 / 002 / 003).

Aggregate-internal round trips and the V-model preset. These tests act as
"E2E by stand-in" for a domain layer with no public entry point — they
exercise the public Workflow API end-to-end through ``from_dict`` and the
mutator chain.
"""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import WorkflowInvariantViolation
from bakufu.domain.value_objects import StageKind, TransitionCondition
from bakufu.domain.workflow import Workflow
from pydantic import ValidationError

from tests.factories.workflow import (
    build_v_model_payload,
    make_stage,
    make_transition,
    make_workflow,
)


class TestWorkflowLifecycleIntegration:
    """Aggregate-internal round-trip + V-model preset + bad-payload variants."""

    def test_v_model_preset_constructs_via_from_dict(self) -> None:
        """TC-IT-WF-001: 13-stage / 15-transition V-model payload constructs."""
        wf = Workflow.from_dict(build_v_model_payload())
        assert len(wf.stages) == 13 and len(wf.transitions) == 15

    def test_v_model_preset_has_external_review_notify_channels(self) -> None:
        """TC-IT-WF-001: every EXTERNAL_REVIEW Stage has at least one notify_channel."""
        wf = Workflow.from_dict(build_v_model_payload())
        review_stages = [s for s in wf.stages if s.kind is StageKind.EXTERNAL_REVIEW]
        assert all(len(s.notify_channels) >= 1 for s in review_stages)

    def test_round_trip_failed_then_recover(self) -> None:
        """TC-IT-WF-002: failed add_transition rolls back; further legitimate add succeeds.

        Pre-state: 3-stage chain s0→s1→s2 (s2 sink). Try to add a duplicate
        APPROVED edge s0→s1, which trips ``transition_duplicate``. The
        original Workflow is unchanged. Then add a REJECTED back-edge s1→s0,
        which is unique on (s1, REJECTED) and preserves s2 as the sole sink.
        """
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e0 = make_transition(
            from_stage_id=s0.id, to_stage_id=s1.id, condition=TransitionCondition.APPROVED
        )
        e1 = make_transition(
            from_stage_id=s1.id, to_stage_id=s2.id, condition=TransitionCondition.APPROVED
        )
        wf = make_workflow(stages=[s0, s1, s2], transitions=[e0, e1], entry_stage_id=s0.id)

        bad_dup = make_transition(
            from_stage_id=s0.id, to_stage_id=s1.id, condition=TransitionCondition.APPROVED
        )
        with pytest.raises(WorkflowInvariantViolation):
            wf.add_transition(bad_dup)
        assert len(wf.transitions) == 2  # original unchanged

        e_back = make_transition(
            from_stage_id=s1.id, to_stage_id=s0.id, condition=TransitionCondition.REJECTED
        )
        updated = wf.add_transition(e_back)
        assert len(updated.transitions) == 3

        # Failed remove_stage(unknown) leaves updated unchanged.
        with pytest.raises(WorkflowInvariantViolation):
            updated.remove_stage(uuid4())
        assert len(updated.stages) == 3

    def test_t1_payload_variants_all_rejected(self) -> None:
        """TC-IT-WF-003: bad payload variants (role / uuid / missing entry / dup stage) reject."""
        # Variant 1: bad role.
        v1 = build_v_model_payload()
        stages_v1 = cast("list[dict[str, object]]", v1["stages"])
        stages_v1[0]["required_role"] = ["UNKNOWN_ROLE"]
        with pytest.raises((ValidationError, WorkflowInvariantViolation)):
            Workflow.from_dict(v1)

        # Variant 2: bad UUID.
        v2 = build_v_model_payload()
        v2["id"] = "not-a-uuid"
        with pytest.raises((ValidationError, WorkflowInvariantViolation)):
            Workflow.from_dict(v2)

        # Variant 3: missing entry_stage_id.
        v3 = build_v_model_payload()
        del v3["entry_stage_id"]
        with pytest.raises((ValidationError, WorkflowInvariantViolation)):
            Workflow.from_dict(v3)

        # Variant 4: duplicate stage_id.
        v4 = build_v_model_payload()
        stages_v4 = cast("list[dict[str, object]]", v4["stages"])
        stages_v4[1]["id"] = stages_v4[0]["id"]
        with pytest.raises((ValidationError, WorkflowInvariantViolation)):
            Workflow.from_dict(v4)
