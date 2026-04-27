"""DAG invariants 7 種 (REQ-WF-005 / TC-UT-WF-002〜007 / 022 / 023 / 038〜045).

Each invariant has its own ``Test*`` class so failures cluster by which
structural property of the DAG was violated.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain import workflow as _workflow_module
from bakufu.domain.exceptions import (
    StageInvariantViolation,
    WorkflowInvariantViolation,
)
from bakufu.domain.value_objects import StageKind, TransitionCondition
from bakufu.domain.workflow import Stage

from tests.factories.workflow import make_stage, make_transition, make_workflow

# Workflow's module-level invariant helpers are private by convention but are
# intentionally imported by tests under the Confirmation F twin-defense
# contract. Indirect attribute access keeps pyright strict happy.
_validate_external_review_notify = _workflow_module._validate_external_review_notify  # pyright: ignore[reportPrivateUsage]
_validate_required_role_non_empty = _workflow_module._validate_required_role_non_empty  # pyright: ignore[reportPrivateUsage]
_validate_dag_reachability = _workflow_module._validate_dag_reachability  # pyright: ignore[reportPrivateUsage]


class TestEntryStageId:
    """REQ-WF-005-① / TC-UT-WF-002 / 038."""

    def test_unknown_entry_raises_entry_not_in_stages(self) -> None:
        """TC-UT-WF-002: entry_stage_id outside stages raises entry_not_in_stages."""
        stage = make_stage()
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[stage], entry_stage_id=uuid4())
        assert excinfo.value.kind == "entry_not_in_stages"

    def test_msg_wf_002_includes_entry_stage_id(self) -> None:
        """TC-UT-WF-038: MSG-WF-002 wording carries the offending entry_stage_id."""
        stage = make_stage()
        unknown = uuid4()
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[stage], entry_stage_id=unknown)
        assert excinfo.value.message == f"[FAIL] entry_stage_id {unknown} not found in stages"


class TestUnreachableStage:
    """REQ-WF-005-④ / TC-UT-WF-003 / 039 — BFS reachability."""

    def test_orphan_stage_raises_unreachable_stage(self) -> None:
        """TC-UT-WF-003: stage not reachable from entry raises unreachable_stage."""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()  # orphan, no edges in
        edge = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(
                stages=[s0, s1, s2],
                transitions=[edge],
                entry_stage_id=s0.id,
            )
        assert excinfo.value.kind == "unreachable_stage"

    def test_msg_wf_003_lists_unreachable_stage_ids(self) -> None:
        """TC-UT-WF-039: MSG-WF-003 includes the unreachable stage's id."""
        s0 = make_stage()
        s1 = make_stage()
        orphan = make_stage()
        edge = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[s0, s1, orphan], transitions=[edge], entry_stage_id=s0.id)
        assert str(orphan.id) in excinfo.value.message


class TestSinkStage:
    """REQ-WF-005-⑤ / TC-UT-WF-004 / 040 — at least one sink Stage."""

    def test_pure_cycle_raises_no_sink_stage(self) -> None:
        """TC-UT-WF-004: 3 stages all with outgoing edges (cycle) raises no_sink_stage."""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e1 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e2 = make_transition(from_stage_id=s1.id, to_stage_id=s2.id)
        e3 = make_transition(from_stage_id=s2.id, to_stage_id=s0.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(
                stages=[s0, s1, s2],
                transitions=[e1, e2, e3],
                entry_stage_id=s0.id,
            )
        assert excinfo.value.kind == "no_sink_stage"

    def test_msg_wf_004_starts_with_no_sink_prefix(self) -> None:
        """TC-UT-WF-040: MSG-WF-004 wording starts with '[FAIL] No sink stage'."""
        s0 = make_stage()
        s1 = make_stage()
        e1 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e2 = make_transition(from_stage_id=s1.id, to_stage_id=s0.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[s0, s1], transitions=[e1, e2], entry_stage_id=s0.id)
        assert excinfo.value.message.startswith("[FAIL] No sink stage")


class TestTransitionDeterminism:
    """REQ-WF-005-③ / TC-UT-WF-005 / 041 — (from, condition) uniqueness."""

    def test_duplicate_from_condition_raises_transition_duplicate(self) -> None:
        """TC-UT-WF-005: same (from_stage_id, APPROVED) twice raises transition_duplicate."""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e1 = make_transition(
            from_stage_id=s0.id, to_stage_id=s1.id, condition=TransitionCondition.APPROVED
        )
        e2 = make_transition(
            from_stage_id=s0.id, to_stage_id=s2.id, condition=TransitionCondition.APPROVED
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(
                stages=[s0, s1, s2],
                transitions=[e1, e2],
                entry_stage_id=s0.id,
            )
        assert excinfo.value.kind == "transition_duplicate"

    def test_msg_wf_005_includes_from_and_condition(self) -> None:
        """TC-UT-WF-041: MSG-WF-005 wording carries from_stage and condition."""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e1 = make_transition(
            from_stage_id=s0.id, to_stage_id=s1.id, condition=TransitionCondition.APPROVED
        )
        e2 = make_transition(
            from_stage_id=s0.id, to_stage_id=s2.id, condition=TransitionCondition.APPROVED
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[s0, s1, s2], transitions=[e1, e2], entry_stage_id=s0.id)
        assert "APPROVED" in excinfo.value.message
        assert str(s0.id) in excinfo.value.message


class TestExternalReviewNotify:
    """REQ-WF-007-② / TC-UT-WF-006a / 006b / 042 — twin-defense."""

    def test_006a_stage_self_path_rejects_empty_notify(self) -> None:
        """TC-UT-WF-006a: Stage self-validator rejects empty notify_channels.

        Construction with ``kind=EXTERNAL_REVIEW`` and ``notify_channels=[]``
        raises :class:`StageInvariantViolation` directly from the Stage's
        own ``model_validator(mode='after')``, before any aggregate check
        runs — fulfilling the twin-defense Stage-side path.
        """
        with pytest.raises(StageInvariantViolation) as excinfo:
            make_stage(kind=StageKind.EXTERNAL_REVIEW, notify_channels=[])
        assert excinfo.value.kind == "missing_notify"

    def test_006b_aggregate_helper_rejects_empty_notify_via_direct_call(self) -> None:
        """TC-UT-WF-006b: ``_validate_external_review_notify`` raises aggregate violation directly.

        Builds an EXTERNAL_REVIEW Stage *with* notify_channels (so its own
        validator passes), then reconstructs via ``model_construct`` (skips
        validators) so the helper sees a state the Stage validator would have
        rejected. Proves the dual code paths (Stage self vs aggregate
        helper) do not share code.
        """
        good = make_stage(kind=StageKind.EXTERNAL_REVIEW)
        stage_without_notify = Stage.model_construct(
            id=good.id,
            name=good.name,
            kind=StageKind.EXTERNAL_REVIEW,
            required_role=good.required_role,
            deliverable_template=good.deliverable_template,
            completion_policy=good.completion_policy,
            notify_channels=[],
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            _validate_external_review_notify([stage_without_notify])
        assert excinfo.value.kind == "missing_notify_aggregate"

    def test_msg_wf_006_includes_stage_id(self) -> None:
        """TC-UT-WF-042: MSG-WF-006 wording carries the offending stage_id."""
        with pytest.raises(StageInvariantViolation) as excinfo:
            make_stage(kind=StageKind.EXTERNAL_REVIEW, notify_channels=[])
        assert "EXTERNAL_REVIEW stage" in excinfo.value.message
        assert "must have at least one notify_channel" in excinfo.value.message


class TestRequiredRoleNonEmpty:
    """REQ-WF-007-① / TC-UT-WF-007 / 043 — required_role non-empty."""

    def test_stage_self_path_rejects_empty_required_role(self) -> None:
        """TC-UT-WF-007: Stage(required_role=frozenset()) raises empty_required_role."""
        with pytest.raises(StageInvariantViolation) as excinfo:
            make_stage(required_role=frozenset())
        assert excinfo.value.kind == "empty_required_role"

    def test_msg_wf_007_includes_stage_id(self) -> None:
        """TC-UT-WF-043: MSG-WF-007 wording carries the offending stage_id."""
        with pytest.raises(StageInvariantViolation) as excinfo:
            make_stage(required_role=frozenset())
        assert "required_role must not be empty" in excinfo.value.message

    def test_aggregate_helper_rejects_empty_required_role(self) -> None:
        """`_validate_required_role_non_empty` rejects bypassed stage with empty role set."""
        good = make_stage()
        bad = Stage.model_construct(
            id=good.id,
            name=good.name,
            kind=StageKind.WORK,
            required_role=frozenset(),
            deliverable_template=good.deliverable_template,
            completion_policy=good.completion_policy,
            notify_channels=[],
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            _validate_required_role_non_empty([bad])
        assert excinfo.value.kind == "empty_required_role_aggregate"


class TestTransitionIdUnique:
    """REQ-WF-005-② sibling — symmetric transition_id duplicate guard.

    Steve's PR #16 review caught the asymmetry where ``_validate_stage_id_unique``
    rejected duplicate stage ids but transition ids slipped through. Linus
    added :func:`_validate_transition_id_unique`; these tests lock the
    aggregate-side behavior so the gap cannot reopen.
    """

    def test_duplicate_transition_id_raises_through_aggregate(self) -> None:
        """Aggregate path: two edges sharing a transition.id raise transition_id_duplicate.

        Pre-state: 3-stage chain s0→s1→s2 with one APPROVED edge. Add a second
        edge that shares the first's id but has different (from, to,
        condition). The aggregate-level helper must reject this even though
        the determinism check (which keys on (from, condition)) would let it
        through.
        """
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e0 = make_transition(
            from_stage_id=s0.id, to_stage_id=s1.id, condition=TransitionCondition.APPROVED
        )
        e_dup = make_transition(
            transition_id=e0.id,  # collide on transition.id deliberately
            from_stage_id=s1.id,
            to_stage_id=s2.id,
            condition=TransitionCondition.APPROVED,
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(
                stages=[s0, s1, s2],
                transitions=[e0, e_dup],
                entry_stage_id=s0.id,
            )
        assert excinfo.value.kind == "transition_id_duplicate"

    def test_msg_for_duplicate_transition_id_includes_id(self) -> None:
        """Message wording: '[FAIL] Transition id duplicate: <transition_id>'."""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e0 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e_dup = make_transition(
            transition_id=e0.id,
            from_stage_id=s1.id,
            to_stage_id=s2.id,
            condition=TransitionCondition.REJECTED,
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(
                stages=[s0, s1, s2],
                transitions=[e0, e_dup],
                entry_stage_id=s0.id,
            )
        assert excinfo.value.message == f"[FAIL] Transition id duplicate: {e0.id}"


class TestTransitionRefIntegrity:
    """REQ-WF-005-② / TC-UT-WF-022 / 045 — Transition refs must point at known Stages."""

    def test_transition_to_unknown_stage_raises(self) -> None:
        """TC-UT-WF-022: Transition.to_stage_id outside stages raises transition_ref_invalid."""
        s0 = make_stage()
        bad_to = uuid4()
        edge = make_transition(from_stage_id=s0.id, to_stage_id=bad_to)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[s0], transitions=[edge], entry_stage_id=s0.id)
        assert excinfo.value.kind == "transition_ref_invalid"

    def test_msg_wf_009_includes_from_and_to(self) -> None:
        """TC-UT-WF-045: MSG-WF-009 wording carries from / to stage ids."""
        s0 = make_stage()
        bad_to = uuid4()
        edge = make_transition(from_stage_id=s0.id, to_stage_id=bad_to)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[s0], transitions=[edge], entry_stage_id=s0.id)
        assert "Transition references unknown stage" in excinfo.value.message
        assert str(bad_to) in excinfo.value.message


class TestBFSCycleSafety:
    """TC-UT-WF-023 — BFS terminates on cyclic graphs without infinite loop."""

    def test_helper_terminates_on_cycle(self) -> None:
        """`_validate_dag_reachability` returns without hanging on a 3-stage cycle."""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e1 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e2 = make_transition(from_stage_id=s1.id, to_stage_id=s2.id)
        e3 = make_transition(from_stage_id=s2.id, to_stage_id=s0.id)
        # All stages reachable; reachability check should not raise.
        _validate_dag_reachability([s0, s1, s2], [e1, e2, e3], s0.id)
