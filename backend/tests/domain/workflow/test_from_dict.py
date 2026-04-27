"""Bulk-import factory ``Workflow.from_dict`` (REQ-WF-006 / T1 attack-surface).

Covers TC-UT-WF-024〜027 / 047. Verifies Pydantic ValidationError pass-through
for type/UUID/missing-field issues and the WorkflowInvariantViolation wrap with
``stage_index`` for Stage-self violations (Confirmation D).
"""

from __future__ import annotations

from typing import cast

import pytest
from bakufu.domain.exceptions import WorkflowInvariantViolation
from bakufu.domain.workflow import Workflow
from pydantic import ValidationError

from tests.factories.workflow import build_v_model_payload


class TestFromDict:
    """REQ-WF-006 / TC-UT-WF-024〜027 / 047."""

    def test_unknown_role_in_payload_raises(self) -> None:
        """TC-UT-WF-024: from_dict with role='UNKNOWN_ROLE' raises a violation."""
        payload = build_v_model_payload()
        stages = cast("list[dict[str, object]]", payload["stages"])
        stages[0]["required_role"] = ["UNKNOWN_ROLE"]
        with pytest.raises((ValidationError, WorkflowInvariantViolation)):
            Workflow.from_dict(payload)

    def test_invalid_uuid_raises(self) -> None:
        """TC-UT-WF-025: from_dict with id='not-a-uuid' raises ValidationError."""
        payload = build_v_model_payload()
        payload["id"] = "not-a-uuid"
        with pytest.raises((ValidationError, WorkflowInvariantViolation)):
            Workflow.from_dict(payload)

    def test_missing_entry_stage_id_raises(self) -> None:
        """TC-UT-WF-026: from_dict without entry_stage_id raises ValidationError."""
        payload = build_v_model_payload()
        del payload["entry_stage_id"]
        with pytest.raises((ValidationError, WorkflowInvariantViolation)):
            Workflow.from_dict(payload)

    def test_stage_index_appears_in_detail_on_stage_violation(self) -> None:
        """TC-UT-WF-027: from_dict failure surfaces the offending stage index."""
        payload = build_v_model_payload()
        stages = cast("list[dict[str, object]]", payload["stages"])
        stages[2]["required_role"] = []
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            Workflow.from_dict(payload)
        assert excinfo.value.kind == "from_dict_invalid"
        assert excinfo.value.detail.get("stage_index") == 2

    def test_msg_wf_011_starts_with_payload_invalid(self) -> None:
        """TC-UT-WF-047: MSG-WF-011 starts with '[FAIL] from_dict payload invalid:'."""
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            Workflow.from_dict("not-a-dict")
        assert excinfo.value.message.startswith("[FAIL] from_dict payload invalid:")
