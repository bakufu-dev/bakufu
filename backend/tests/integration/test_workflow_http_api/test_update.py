"""workflow / http-api 結合テスト — UPDATE 系
(TC-IT-WFH-005/006/019/020/021/022).

Covers:
  TC-IT-WFH-005  PATCH name のみ更新 → 200 WorkflowResponse
  TC-IT-WFH-006  PATCH DAG 全置換 → 200 WorkflowResponse
  TC-IT-WFH-019  PATCH Workflow 不在 → 404 not_found (MSG-WF-HTTP-001)
  TC-IT-WFH-020  PATCH Workflow archived → 409 conflict (MSG-WF-HTTP-002)
  TC-IT-WFH-021  PATCH DAG 違反 → 422 validation_error (MSG-WF-HTTP-005)
  TC-IT-WFH-022  PATCH 整合バリデーション違反 → 422

Issue: #58
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration.test_workflow_http_api.helpers import (
    WfTestCtx,
    _minimal_stage_payload,
    _seed_workflow_direct,
)

pytestmark = pytest.mark.asyncio


class TestUpdateWorkflowNameOnly:
    """TC-IT-WFH-005: PATCH name のみ更新 → 200 WorkflowResponse。"""

    async def test_update_name_returns_200(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"name": "新フロー名"},
        )
        assert resp.status_code == 200

    async def test_update_name_response_name_changed(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"name": "新フロー名"},
        )
        assert resp.json()["name"] == "新フロー名"

    async def test_update_name_stages_unchanged(self, wf_ctx: WfTestCtx) -> None:
        """name のみ更新時、stages は変更前と同一。"""
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        original_stages = wf.stages  # type: ignore[attr-defined]
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"name": "新フロー名"},
        )
        assert len(resp.json()["stages"]) == len(original_stages)  # type: ignore[arg-type]


class TestUpdateWorkflowDagReplace:
    """TC-IT-WFH-006: PATCH DAG 全置換 → 200 WorkflowResponse。"""

    async def test_update_dag_returns_200(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        stage_a_id = uuid4()
        stage_b_id = uuid4()
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={
                "stages": [
                    _minimal_stage_payload(stage_a_id),
                    _minimal_stage_payload(stage_b_id),
                ],
                "transitions": [
                    {
                        "id": str(uuid4()),
                        "from_stage_id": str(stage_a_id),
                        "to_stage_id": str(stage_b_id),
                        "condition": "APPROVED",
                        "label": "",
                    }
                ],
                "entry_stage_id": str(stage_a_id),
            },
        )
        assert resp.status_code == 200

    async def test_update_dag_stages_count_is_2(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        stage_a_id = uuid4()
        stage_b_id = uuid4()
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={
                "stages": [
                    _minimal_stage_payload(stage_a_id),
                    _minimal_stage_payload(stage_b_id),
                ],
                "transitions": [
                    {
                        "id": str(uuid4()),
                        "from_stage_id": str(stage_a_id),
                        "to_stage_id": str(stage_b_id),
                        "condition": "APPROVED",
                        "label": "",
                    }
                ],
                "entry_stage_id": str(stage_a_id),
            },
        )
        assert len(resp.json()["stages"]) == 2

    async def test_update_dag_entry_stage_id_updated(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        stage_a_id = uuid4()
        stage_b_id = uuid4()
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={
                "stages": [
                    _minimal_stage_payload(stage_a_id),
                    _minimal_stage_payload(stage_b_id),
                ],
                "transitions": [
                    {
                        "id": str(uuid4()),
                        "from_stage_id": str(stage_a_id),
                        "to_stage_id": str(stage_b_id),
                        "condition": "APPROVED",
                        "label": "",
                    }
                ],
                "entry_stage_id": str(stage_a_id),
            },
        )
        assert resp.json()["entry_stage_id"] == str(stage_a_id)


class TestUpdateWorkflowNotFound:
    """TC-IT-WFH-019: PATCH Workflow 不在 → 404 not_found (MSG-WF-HTTP-001)."""

    async def test_workflow_not_found_returns_404(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{uuid4()}",
            json={"name": "変更試み"},
        )
        assert resp.status_code == 404

    async def test_workflow_not_found_error_code(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{uuid4()}",
            json={"name": "変更試み"},
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_workflow_not_found_error_message(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{uuid4()}",
            json={"name": "変更試み"},
        )
        assert resp.json()["error"]["message"] == "Workflow not found."


class TestUpdateWorkflowArchived:
    """TC-IT-WFH-020: PATCH Workflow archived → 409 conflict (MSG-WF-HTTP-002)."""

    async def test_archived_workflow_returns_409(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        await wf_ctx.client.delete(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"name": "変更試み"},
        )
        assert resp.status_code == 409

    async def test_archived_workflow_error_code(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        await wf_ctx.client.delete(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"name": "変更試み"},
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_archived_workflow_error_message(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        await wf_ctx.client.delete(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"name": "変更試み"},
        )
        assert resp.json()["error"]["message"] == "Workflow is archived and cannot be modified."


class TestUpdateWorkflowDagViolation:
    """TC-IT-WFH-021: PATCH DAG 違反 → 422 validation_error (MSG-WF-HTTP-005)。

    B が stages に存在しない (A→B transition) → R1-5 孤立検査違反。
    """

    async def test_dag_violation_returns_422(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        stage_a_id = uuid4()
        stage_b_id = uuid4()  # stages に存在しない
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={
                "stages": [_minimal_stage_payload(stage_a_id)],
                "transitions": [
                    {
                        "id": str(uuid4()),
                        "from_stage_id": str(stage_a_id),
                        "to_stage_id": str(stage_b_id),
                        "condition": "APPROVED",
                        "label": "",
                    }
                ],
                "entry_stage_id": str(stage_a_id),
            },
        )
        assert resp.status_code == 422

    async def test_dag_violation_error_code(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        stage_a_id = uuid4()
        stage_b_id = uuid4()
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={
                "stages": [_minimal_stage_payload(stage_a_id)],
                "transitions": [
                    {
                        "id": str(uuid4()),
                        "from_stage_id": str(stage_a_id),
                        "to_stage_id": str(stage_b_id),
                        "condition": "APPROVED",
                        "label": "",
                    }
                ],
                "entry_stage_id": str(stage_a_id),
            },
        )
        assert resp.json()["error"]["code"] == "validation_error"

    async def test_dag_violation_message_no_fail_prefix(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        stage_a_id = uuid4()
        stage_b_id = uuid4()
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={
                "stages": [_minimal_stage_payload(stage_a_id)],
                "transitions": [
                    {
                        "id": str(uuid4()),
                        "from_stage_id": str(stage_a_id),
                        "to_stage_id": str(stage_b_id),
                        "condition": "APPROVED",
                        "label": "",
                    }
                ],
                "entry_stage_id": str(stage_a_id),
            },
        )
        assert "[FAIL]" not in resp.json()["error"]["message"]


class TestUpdateWorkflowConsistencyValidation:
    """TC-IT-WFH-022: PATCH 整合バリデーション違反（stages のみ指定）→ 422。"""

    async def test_stages_only_returns_422(self, wf_ctx: WfTestCtx) -> None:
        """stages のみ指定で transitions=None → WorkflowUpdate model_validator → 422。"""
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        stage_id = uuid4()
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"stages": [_minimal_stage_payload(stage_id)]},
        )
        assert resp.status_code == 422
