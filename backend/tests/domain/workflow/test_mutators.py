"""Workflow mutators (REQ-WF-002 / 003 / 004) + pre-validate rollback.

Covers add_stage / add_transition / remove_stage and Confirmation A's contract
that failed mutators leave the original Workflow unchanged.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import WorkflowInvariantViolation
from bakufu.domain.value_objects import Role, StageKind, TransitionCondition
from bakufu.domain.workflow import MAX_STAGES, MAX_TRANSITIONS, Workflow

from tests.factories.workflow import make_stage, make_transition, make_workflow


class TestAddStage:
    """REQ-WF-002 / TC-UT-WF-014 / 044.

    Note on TC-UT-WF-013: ``add_stage`` in isolation cannot succeed because a
    newly-added Stage with no incoming Transition is orphaned and the
    aggregate-level ``_validate_dag_reachability`` rejects it. The "appends"
    success path is exercised through ``from_dict`` (TC-IT-WF-001) — granular
    mutators are designed for **constrained** changes.
    """

    def test_duplicate_stage_id_raises_stage_duplicate(self) -> None:
        """TC-UT-WF-014: add_stage with existing id raises stage_duplicate."""
        wf = make_workflow()
        existing = wf.stages[0]
        duplicate = make_stage(stage_id=existing.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            wf.add_stage(duplicate)
        assert excinfo.value.kind == "stage_duplicate"

    def test_msg_wf_008_for_duplicate_includes_stage_id(self) -> None:
        """TC-UT-WF-044: MSG-WF-008 wording carries the duplicate stage_id."""
        wf = make_workflow()
        existing = wf.stages[0]
        duplicate = make_stage(stage_id=existing.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            wf.add_stage(duplicate)
        assert excinfo.value.message == f"[FAIL] Stage id duplicate: {existing.id}"


class TestAddStageCapacity:
    """REQ-WF-002 capacity / TC-UT-WF-015."""

    def test_overflow_raises_capacity_exceeded(self) -> None:
        """TC-UT-WF-015: bulk-importing >MAX_STAGES via from_dict raises capacity_exceeded."""
        stages: list[dict[str, object]] = []
        first_id: str | None = None
        for _ in range(MAX_STAGES + 1):
            sid = str(uuid4())
            stages.append(
                {
                    "id": sid,
                    "name": "S",
                    "kind": StageKind.WORK.value,
                    "required_role": [Role.DEVELOPER.value],
                    "deliverable_template": "",
                    "completion_policy": {"kind": "manual", "description": ""},
                    "notify_channels": [],
                }
            )
            if first_id is None:
                first_id = sid
        # Build forward APPROVED chain so we have at least valid topology.
        transitions: list[dict[str, object]] = []
        previous: str | None = None
        for stage in stages:
            current = stage["id"]
            if previous is not None:
                transitions.append(
                    {
                        "id": str(uuid4()),
                        "from_stage_id": previous,
                        "to_stage_id": current,
                        "condition": TransitionCondition.APPROVED.value,
                        "label": "",
                    }
                )
            previous = str(current)
        payload = {
            "id": str(uuid4()),
            "name": "overflow",
            "stages": stages,
            "transitions": transitions,
            "entry_stage_id": first_id,
        }
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            Workflow.from_dict(payload)
        assert excinfo.value.kind == "capacity_exceeded"


class TestAddTransition:
    """REQ-WF-003 / TC-UT-WF-016 / 017."""

    def test_appends_transition_to_list(self) -> None:
        """TC-UT-WF-016: add_transition returns a new Workflow with the edge appended.

        Pre-state: 3-stage chain s0→s1→s2 with two forward APPROVED edges.
        Adding a REJECTED back-edge s1→s0 leaves s2 as the sole sink.
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
        e_back = make_transition(
            from_stage_id=s1.id, to_stage_id=s0.id, condition=TransitionCondition.REJECTED
        )
        updated = wf.add_transition(e_back)
        assert len(updated.transitions) == 3

    def test_does_not_mutate_original(self) -> None:
        """TC-UT-WF-016: caller's Workflow stays at 2 transitions after add path."""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e0 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e1 = make_transition(from_stage_id=s1.id, to_stage_id=s2.id)
        wf = make_workflow(stages=[s0, s1, s2], transitions=[e0, e1], entry_stage_id=s0.id)
        e_back = make_transition(
            from_stage_id=s1.id, to_stage_id=s0.id, condition=TransitionCondition.REJECTED
        )
        wf.add_transition(e_back)
        assert len(wf.transitions) == 2

    def test_dangling_ref_raises_transition_ref_invalid(self) -> None:
        """TC-UT-WF-017: add_transition with unknown from/to raises transition_ref_invalid."""
        wf = make_workflow()
        bad_edge = make_transition(from_stage_id=wf.stages[0].id, to_stage_id=uuid4())
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            wf.add_transition(bad_edge)
        assert excinfo.value.kind == "transition_ref_invalid"


class TestAddTransitionCapacity:
    """REQ-WF-003 capacity / TC-UT-WF-018."""

    def test_overflow_raises_capacity_exceeded(self) -> None:
        """TC-UT-WF-018: building >MAX_TRANSITIONS via from_dict raises capacity_exceeded."""
        stage_ids = [str(uuid4()) for _ in range(2)]
        stages_payload: list[dict[str, object]] = [
            {
                "id": sid,
                "name": "S",
                "kind": StageKind.WORK.value,
                "required_role": [Role.DEVELOPER.value],
                "deliverable_template": "",
                "completion_policy": {"kind": "manual", "description": ""},
                "notify_channels": [],
            }
            for sid in stage_ids
        ]
        transitions_payload: list[dict[str, object]] = [
            {
                "id": str(uuid4()),
                "from_stage_id": stage_ids[0],
                "to_stage_id": stage_ids[1],
                "condition": TransitionCondition.APPROVED.value,
                "label": "",
            }
        ]
        for _ in range(MAX_TRANSITIONS):
            transitions_payload.append(
                {
                    "id": str(uuid4()),
                    "from_stage_id": stage_ids[0],
                    "to_stage_id": stage_ids[1],
                    "condition": TransitionCondition.APPROVED.value,
                    "label": "",
                }
            )
        payload = {
            "id": str(uuid4()),
            "name": "overflow",
            "stages": stages_payload,
            "transitions": transitions_payload,
            "entry_stage_id": stage_ids[0],
        }
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            Workflow.from_dict(payload)
        # Capacity is checked before determinism, so capacity_exceeded fires first.
        assert excinfo.value.kind == "capacity_exceeded"


class TestRemoveStage:
    """REQ-WF-004 / TC-UT-WF-009 / 019 / 020 / 021 / 046."""

    def test_remove_entry_stage_raises_cannot_remove_entry(self) -> None:
        """TC-UT-WF-009: remove_stage(entry_stage_id) raises cannot_remove_entry."""
        wf = make_workflow()
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            wf.remove_stage(wf.entry_stage_id)
        assert excinfo.value.kind == "cannot_remove_entry"

    def test_msg_wf_010_includes_stage_id(self) -> None:
        """TC-UT-WF-046: MSG-WF-010 wording carries the entry stage_id."""
        wf = make_workflow()
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            wf.remove_stage(wf.entry_stage_id)
        assert excinfo.value.message == f"[FAIL] Cannot remove entry stage: {wf.entry_stage_id}"

    def test_unknown_stage_id_raises_stage_not_found(self) -> None:
        """TC-UT-WF-019: remove_stage(unknown) raises stage_not_found with MSG-WF-012."""
        wf = make_workflow()
        unknown = uuid4()
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            wf.remove_stage(unknown)
        assert excinfo.value.kind == "stage_not_found"
        assert excinfo.value.message == f"[FAIL] Stage not found in workflow: stage_id={unknown}"

    def test_cascades_incident_transitions(self) -> None:
        """TC-UT-WF-020: removing a Stage also drops Transitions referencing it."""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e0 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e1 = make_transition(from_stage_id=s1.id, to_stage_id=s2.id)
        wf = make_workflow(stages=[s0, s1, s2], transitions=[e0, e1], entry_stage_id=s0.id)
        # Removing the trailing stage s2 leaves s0→s1 valid (s1 becomes sink).
        updated = wf.remove_stage(s2.id)
        assert len(updated.stages) == 2 and len(updated.transitions) == 1


class TestPreValidateRollback:
    """Confirmation A — failed mutators leave original Workflow unchanged."""

    def test_failed_add_stage_keeps_original(self) -> None:
        """TC-UT-WF-008: failed add_stage does not mutate caller's Workflow."""
        wf = make_workflow()
        existing = wf.stages[0]
        with pytest.raises(WorkflowInvariantViolation):
            wf.add_stage(make_stage(stage_id=existing.id))
        assert len(wf.stages) == 1

    def test_failed_add_transition_keeps_original(self) -> None:
        """TC-UT-WF-030: failed add_transition does not mutate caller's Workflow."""
        wf = make_workflow()
        bad = make_transition(from_stage_id=wf.stages[0].id, to_stage_id=uuid4())
        with pytest.raises(WorkflowInvariantViolation):
            wf.add_transition(bad)
        assert wf.transitions == []

    def test_failed_remove_stage_keeps_original(self) -> None:
        """TC-UT-WF-031: failed remove_stage does not mutate caller's Workflow."""
        wf = make_workflow()
        with pytest.raises(WorkflowInvariantViolation):
            wf.remove_stage(uuid4())
        assert len(wf.stages) == 1
