"""workflow / http-api ユニットテスト — ハンドラ検証 (TC-UT-WFH-006~009 / 011).

Covers:
  TC-UT-WFH-006  workflow_not_found_handler (MSG-WF-HTTP-001)
  TC-UT-WFH-007  workflow_archived_handler kind='update' (MSG-WF-HTTP-002)
  TC-UT-WFH-008  workflow_preset_not_found_handler (MSG-WF-HTTP-004)
  TC-UT-WFH-009  workflow_invariant_violation_handler 前処理ルール (MSG-WF-HTTP-005)
  TC-UT-WFH-011  workflow_irreversible_handler (MSG-WF-HTTP-008)

Issue: #58
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
class TestWorkflowNotFoundHandler:
    """TC-UT-WFH-006: workflow_not_found_handler (MSG-WF-HTTP-001 確定文言)。"""

    def _make_request(self) -> Any:
        return MagicMock()

    async def test_returns_404(self) -> None:
        from bakufu.application.exceptions.workflow_exceptions import WorkflowNotFoundError
        from bakufu.interfaces.http.error_handlers import workflow_not_found_handler

        exc = WorkflowNotFoundError(workflow_id="test-id")
        resp = await workflow_not_found_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 404  # type: ignore[union-attr]

    async def test_error_code_is_not_found(self) -> None:
        import json

        from bakufu.application.exceptions.workflow_exceptions import WorkflowNotFoundError
        from bakufu.interfaces.http.error_handlers import workflow_not_found_handler

        exc = WorkflowNotFoundError(workflow_id="test-id")
        resp = await workflow_not_found_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "not_found"

    async def test_error_message_matches_msg_wf_http_001(self) -> None:
        """MSG-WF-HTTP-001 確定文言と完全一致。"""
        import json

        from bakufu.application.exceptions.workflow_exceptions import WorkflowNotFoundError
        from bakufu.interfaces.http.error_handlers import workflow_not_found_handler

        exc = WorkflowNotFoundError(workflow_id="test-id")
        resp = await workflow_not_found_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Workflow not found."


@pytest.mark.asyncio
class TestWorkflowArchivedHandler:
    """TC-UT-WFH-007: workflow_archived_handler kind='update' (MSG-WF-HTTP-002 確定文言)。"""

    def _make_request(self) -> Any:
        return MagicMock()

    async def test_returns_409(self) -> None:
        from bakufu.application.exceptions.workflow_exceptions import WorkflowArchivedError
        from bakufu.interfaces.http.error_handlers import workflow_archived_handler

        exc = WorkflowArchivedError(workflow_id="test-id", kind="update")
        resp = await workflow_archived_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 409  # type: ignore[union-attr]

    async def test_error_code_is_conflict(self) -> None:
        import json

        from bakufu.application.exceptions.workflow_exceptions import WorkflowArchivedError
        from bakufu.interfaces.http.error_handlers import workflow_archived_handler

        exc = WorkflowArchivedError(workflow_id="test-id", kind="update")
        resp = await workflow_archived_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "conflict"

    async def test_error_message_matches_msg_wf_http_002(self) -> None:
        """MSG-WF-HTTP-002 確定文言と完全一致 (kind='update')。"""
        import json

        from bakufu.application.exceptions.workflow_exceptions import WorkflowArchivedError
        from bakufu.interfaces.http.error_handlers import workflow_archived_handler

        exc = WorkflowArchivedError(workflow_id="test-id", kind="update")
        resp = await workflow_archived_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Workflow is archived and cannot be modified."


@pytest.mark.asyncio
class TestWorkflowPresetNotFoundHandler:
    """TC-UT-WFH-008: workflow_preset_not_found_handler (MSG-WF-HTTP-004 確定文言)。"""

    def _make_request(self) -> Any:
        return MagicMock()

    async def test_returns_404(self) -> None:
        from bakufu.application.exceptions.workflow_exceptions import WorkflowPresetNotFoundError
        from bakufu.interfaces.http.error_handlers import workflow_preset_not_found_handler

        exc = WorkflowPresetNotFoundError(preset_name="unknown")
        resp = await workflow_preset_not_found_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 404  # type: ignore[union-attr]

    async def test_error_code_is_not_found(self) -> None:
        import json

        from bakufu.application.exceptions.workflow_exceptions import WorkflowPresetNotFoundError
        from bakufu.interfaces.http.error_handlers import workflow_preset_not_found_handler

        exc = WorkflowPresetNotFoundError(preset_name="unknown")
        resp = await workflow_preset_not_found_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "not_found"

    async def test_error_message_matches_msg_wf_http_004(self) -> None:
        """MSG-WF-HTTP-004 確定文言と完全一致。"""
        import json

        from bakufu.application.exceptions.workflow_exceptions import WorkflowPresetNotFoundError
        from bakufu.interfaces.http.error_handlers import workflow_preset_not_found_handler

        exc = WorkflowPresetNotFoundError(preset_name="unknown")
        resp = await workflow_preset_not_found_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Workflow preset not found."


@pytest.mark.asyncio
class TestWorkflowInvariantViolationHandler:
    """TC-UT-WFH-009: workflow_invariant_violation_handler 前処理ルール (MSG-WF-HTTP-005)。"""

    def _make_request(self) -> Any:
        return MagicMock()

    async def test_returns_422_with_next_suffix(self) -> None:
        """(a) [FAIL] + Next: 付きメッセージ → HTTP 422。"""
        from bakufu.domain.exceptions import WorkflowInvariantViolation
        from bakufu.interfaces.http.error_handlers import workflow_invariant_violation_handler

        exc = WorkflowInvariantViolation(
            kind="entry_not_in_stages",  # type: ignore[arg-type]
            message=(
                "[FAIL] entry_stage_id が stages に存在しません。"
                "\nNext: 有効な stage_id を指定してください。"
            ),
        )
        resp = await workflow_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 422  # type: ignore[union-attr]

    async def test_fail_prefix_removed(self) -> None:
        """(a) [FAIL] プレフィックスが除去される。"""
        import json

        from bakufu.domain.exceptions import WorkflowInvariantViolation
        from bakufu.interfaces.http.error_handlers import workflow_invariant_violation_handler

        exc = WorkflowInvariantViolation(
            kind="entry_not_in_stages",  # type: ignore[arg-type]
            message=(
                "[FAIL] entry_stage_id が stages に存在しません。"
                "\nNext: 有効な stage_id を指定してください。"
            ),
        )
        resp = await workflow_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "[FAIL]" not in body["error"]["message"]

    async def test_next_suffix_removed(self) -> None:
        """(a) \\nNext:.* サフィックスが除去される。"""
        import json

        from bakufu.domain.exceptions import WorkflowInvariantViolation
        from bakufu.interfaces.http.error_handlers import workflow_invariant_violation_handler

        exc = WorkflowInvariantViolation(
            kind="entry_not_in_stages",  # type: ignore[arg-type]
            message=(
                "[FAIL] entry_stage_id が stages に存在しません。"
                "\nNext: 有効な stage_id を指定してください。"
            ),
        )
        resp = await workflow_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "Next:" not in body["error"]["message"]

    async def test_error_code_is_validation_error(self) -> None:
        import json

        from bakufu.domain.exceptions import WorkflowInvariantViolation
        from bakufu.interfaces.http.error_handlers import workflow_invariant_violation_handler

        exc = WorkflowInvariantViolation(
            kind="capacity_exceeded",  # type: ignore[arg-type]
            message="[FAIL] Stage 数が上限を超えています。",
        )
        resp = await workflow_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "validation_error"

    async def test_no_next_returns_422(self) -> None:
        """(b) Next: なしのメッセージ → HTTP 422。"""
        from bakufu.domain.exceptions import WorkflowInvariantViolation
        from bakufu.interfaces.http.error_handlers import workflow_invariant_violation_handler

        exc = WorkflowInvariantViolation(
            kind="capacity_exceeded",  # type: ignore[arg-type]
            message="[FAIL] Stage 数が上限を超えています。",
        )
        resp = await workflow_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 422  # type: ignore[union-attr]

    async def test_no_next_message_clean(self) -> None:
        """(b) Next: なし → strip 後に Next: が残らない。"""
        import json

        from bakufu.domain.exceptions import WorkflowInvariantViolation
        from bakufu.interfaces.http.error_handlers import workflow_invariant_violation_handler

        exc = WorkflowInvariantViolation(
            kind="capacity_exceeded",  # type: ignore[arg-type]
            message="[FAIL] Stage 数が上限を超えています。",
        )
        resp = await workflow_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "Next:" not in body["error"]["message"]


@pytest.mark.asyncio
class TestWorkflowIrreversibleHandler:
    """TC-UT-WFH-011: workflow_irreversible_handler (MSG-WF-HTTP-008 確定文言)。"""

    def _make_request(self) -> Any:
        return MagicMock()

    async def test_returns_409(self) -> None:
        from bakufu.application.exceptions.workflow_exceptions import WorkflowIrreversibleError
        from bakufu.interfaces.http.error_handlers import workflow_irreversible_handler

        exc = WorkflowIrreversibleError(workflow_id="test-id")
        resp = await workflow_irreversible_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 409  # type: ignore[union-attr]

    async def test_error_code_is_conflict(self) -> None:
        import json

        from bakufu.application.exceptions.workflow_exceptions import WorkflowIrreversibleError
        from bakufu.interfaces.http.error_handlers import workflow_irreversible_handler

        exc = WorkflowIrreversibleError(workflow_id="test-id")
        resp = await workflow_irreversible_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "conflict"

    async def test_error_message_matches_msg_wf_http_008(self) -> None:
        """MSG-WF-HTTP-008 確定文言と完全一致。"""
        import json

        from bakufu.application.exceptions.workflow_exceptions import WorkflowIrreversibleError
        from bakufu.interfaces.http.error_handlers import workflow_irreversible_handler

        exc = WorkflowIrreversibleError(workflow_id="test-id")
        resp = await workflow_irreversible_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == (
            "Workflow contains masked notify_channels and cannot be modified."
            " Please recreate the workflow with new webhook URLs."
        )
