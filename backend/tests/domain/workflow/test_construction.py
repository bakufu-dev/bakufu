"""Construction & name normalization (TC-UT-WF-001 / 011 / 012 / 037).

Covers REQ-WF-001 minimal contracts and the NFC + strip pipeline shared with
the empire feature.
"""

from __future__ import annotations

import pytest
from bakufu.domain.exceptions import WorkflowInvariantViolation

from tests.factories.workflow import make_workflow


class TestWorkflowConstruction:
    """Minimal Workflow contract (TC-UT-WF-001)."""

    def test_single_stage_workflow_constructs(self) -> None:
        """TC-UT-WF-001: 1-stage workflow with entry == sink succeeds."""
        wf = make_workflow()
        assert len(wf.stages) == 1 and len(wf.transitions) == 0

    def test_entry_stage_id_resolves_to_first_stage(self) -> None:
        """TC-UT-WF-001: factory's default entry_stage_id matches the lone Stage id."""
        wf = make_workflow()
        assert wf.entry_stage_id == wf.stages[0].id


class TestWorkflowName:
    """Workflow.name length and normalization (TC-UT-WF-011 / 012 / 037)."""

    @pytest.mark.parametrize("valid_length", [1, 80])
    def test_accepts_lower_and_upper_boundary(self, valid_length: int) -> None:
        """TC-UT-WF-011: 1-char and 80-char names construct."""
        wf = make_workflow(name="a" * valid_length)
        assert len(wf.name) == valid_length

    @pytest.mark.parametrize("invalid_name", ["", "a" * 81, "   "])
    def test_rejects_zero_eightyone_or_whitespace_only(self, invalid_name: str) -> None:
        """TC-UT-WF-011: 0/81/whitespace-only names raise WorkflowInvariantViolation."""
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(name=invalid_name)
        assert excinfo.value.kind == "name_range"

    def test_strips_surrounding_whitespace(self) -> None:
        """TC-UT-WF-012: leading/trailing whitespace is stripped (NFC pipeline)."""
        wf = make_workflow(name="  V モデル開発フロー  ")
        assert wf.name == "V モデル開発フロー"

    def test_msg_wf_001_for_oversized_name_matches_exact_wording(self) -> None:
        """TC-UT-WF-037: MSG-WF-001 wording matches '[FAIL] Workflow name ...'."""
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(name="a" * 81)
        assert excinfo.value.message == "[FAIL] Workflow name must be 1-80 characters (got 81)"
