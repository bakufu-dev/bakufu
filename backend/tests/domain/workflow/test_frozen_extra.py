"""frozen=True / extra='forbid' invariants (TC-UT-WF-032 / 033).

Verifies that the Pydantic v2 frozen contract physically prevents post-
construction mutation across all aggregate / entity / VO surfaces, and that
unknown fields in payloads are rejected before any aggregate validation runs.
"""

from __future__ import annotations

import pytest
from bakufu.domain.exceptions import WorkflowInvariantViolation
from bakufu.domain.value_objects import StageKind, TransitionCondition
from bakufu.domain.workflow import Workflow
from pydantic import ValidationError

from tests.factories.workflow import (
    build_v_model_payload,
    make_notify_channel,
    make_stage,
    make_transition,
    make_workflow,
)


class TestFrozenContract:
    """TC-UT-WF-032 — Workflow / Stage / Transition / NotifyChannel frozen."""

    def test_workflow_rejects_attribute_assignment(self) -> None:
        wf = make_workflow()
        with pytest.raises(ValidationError):
            wf.name = "改竄"  # type: ignore[misc]

    def test_stage_rejects_attribute_assignment(self) -> None:
        stage = make_stage()
        with pytest.raises(ValidationError):
            stage.kind = StageKind.EXTERNAL_REVIEW  # type: ignore[misc]

    def test_transition_rejects_attribute_assignment(self) -> None:
        s0 = make_stage()
        s1 = make_stage()
        edge = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        with pytest.raises(ValidationError):
            edge.condition = TransitionCondition.REJECTED  # type: ignore[misc]

    def test_notify_channel_rejects_attribute_assignment(self) -> None:
        channel = make_notify_channel()
        with pytest.raises(ValidationError):
            channel.target = "https://discord.com/api/webhooks/2/3"  # type: ignore[misc]


class TestExtraForbid:
    """TC-UT-WF-033 — extra='forbid' rejects unknown fields."""

    def test_workflow_rejects_unknown_field(self) -> None:
        payload = build_v_model_payload()
        payload["unknown_field"] = "x"
        with pytest.raises((ValidationError, WorkflowInvariantViolation)):
            Workflow.from_dict(payload)
