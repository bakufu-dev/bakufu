"""Module-level helper independence (Confirmation F / TC-UT-WF-060).

Each ``_validate_*`` is imported via ``bakufu.domain.workflow`` (the indirect
attribute access keeps pyright's ``reportPrivateUsage`` quiet) and invoked
directly without first constructing a Workflow. This proves the aggregate
helpers are pure module-level functions whose behavior does not depend on
``Stage._check_self_invariants`` having run — the design contract for
twin-defense (TC-UT-WF-006a vs 006b).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain import workflow as _workflow_module
from bakufu.domain.exceptions import WorkflowInvariantViolation
from bakufu.domain.value_objects import TransitionCondition
from bakufu.domain.workflow import MAX_STAGES

from tests.factories.workflow import make_stage, make_transition

_validate_capacity = _workflow_module._validate_capacity  # pyright: ignore[reportPrivateUsage]
_validate_dag_reachability = _workflow_module._validate_dag_reachability  # pyright: ignore[reportPrivateUsage]
_validate_dag_sink_exists = _workflow_module._validate_dag_sink_exists  # pyright: ignore[reportPrivateUsage]
_validate_entry_in_stages = _workflow_module._validate_entry_in_stages  # pyright: ignore[reportPrivateUsage]
_validate_stage_id_unique = _workflow_module._validate_stage_id_unique  # pyright: ignore[reportPrivateUsage]
_validate_transition_determinism = _workflow_module._validate_transition_determinism  # pyright: ignore[reportPrivateUsage]
_validate_transition_refs = _workflow_module._validate_transition_refs  # pyright: ignore[reportPrivateUsage]


class TestHelperIndependence:
    """TC-UT-WF-060 — module-level helpers are import-able and independently raise."""

    def test_capacity_helper_raises_directly(self) -> None:
        """`_validate_capacity` raises capacity_exceeded when stages > MAX_STAGES."""
        too_many = [make_stage() for _ in range(MAX_STAGES + 1)]
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            _validate_capacity(too_many, [])
        assert excinfo.value.kind == "capacity_exceeded"

    def test_stage_id_unique_helper_raises_directly(self) -> None:
        """`_validate_stage_id_unique` raises stage_duplicate on collisions."""
        s0 = make_stage()
        dup = make_stage(stage_id=s0.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            _validate_stage_id_unique([s0, dup])
        assert excinfo.value.kind == "stage_duplicate"

    def test_entry_in_stages_helper_raises_directly(self) -> None:
        """`_validate_entry_in_stages` raises when entry not in stages."""
        s0 = make_stage()
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            _validate_entry_in_stages([s0], uuid4())
        assert excinfo.value.kind == "entry_not_in_stages"

    def test_transition_refs_helper_raises_directly(self) -> None:
        """`_validate_transition_refs` raises when from/to point at unknown stages."""
        s0 = make_stage()
        bogus = make_transition(from_stage_id=s0.id, to_stage_id=uuid4())
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            _validate_transition_refs([s0], [bogus])
        assert excinfo.value.kind == "transition_ref_invalid"

    def test_transition_determinism_helper_raises_directly(self) -> None:
        """`_validate_transition_determinism` raises on (from, condition) collision."""
        s0 = make_stage()
        s1 = make_stage()
        e1 = make_transition(
            from_stage_id=s0.id, to_stage_id=s1.id, condition=TransitionCondition.APPROVED
        )
        e2 = make_transition(
            from_stage_id=s0.id, to_stage_id=s1.id, condition=TransitionCondition.APPROVED
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            _validate_transition_determinism([e1, e2])
        assert excinfo.value.kind == "transition_duplicate"

    def test_dag_sink_helper_raises_directly(self) -> None:
        """`_validate_dag_sink_exists` raises when no Stage lacks outgoing edges."""
        s0 = make_stage()
        s1 = make_stage()
        e1 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e2 = make_transition(from_stage_id=s1.id, to_stage_id=s0.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            _validate_dag_sink_exists([s0, s1], [e1, e2], s0.id)
        assert excinfo.value.kind == "no_sink_stage"

    def test_dag_reachability_helper_raises_directly(self) -> None:
        """`_validate_dag_reachability` raises unreachable_stage when orphan exists."""
        s0 = make_stage()
        orphan = make_stage()
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            _validate_dag_reachability([s0, orphan], [], s0.id)
        assert excinfo.value.kind == "unreachable_stage"
