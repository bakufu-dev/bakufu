"""workflow / http-api 結合テスト — GET 系 (TC-IT-WFH-004/018).

Covers:
  TC-IT-WFH-004  GET /api/workflows/{id} → 200 WorkflowResponse
  TC-IT-WFH-018  GET Workflow 不在 → 404 not_found (MSG-WF-HTTP-001)

Issue: #58
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration.test_workflow_http_api.helpers import (
    WfTestCtx,
    _seed_workflow_direct,
)

pytestmark = pytest.mark.asyncio


class TestGetWorkflow:
    """TC-IT-WFH-004: GET /api/workflows/{workflow_id} → 200 WorkflowResponse."""

    async def test_get_returns_200(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.get(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        assert resp.status_code == 200

    async def test_get_response_id_matches(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.get(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        assert resp.json()["id"] == str(wf.id)  # type: ignore[attr-defined]

    async def test_get_response_has_stages(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.get(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        assert isinstance(resp.json()["stages"], list)

    async def test_get_response_has_transitions(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.get(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        assert isinstance(resp.json()["transitions"], list)

    async def test_get_response_has_entry_stage_id(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.get(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        assert isinstance(resp.json()["entry_stage_id"], str)

    async def test_get_response_archived_is_false(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.get(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        assert resp.json()["archived"] is False


class TestGetWorkflowNotFound:
    """TC-IT-WFH-018: GET Workflow 不在 → 404 not_found (MSG-WF-HTTP-001)."""

    async def test_workflow_not_found_returns_404(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get(f"/api/workflows/{uuid4()}")
        assert resp.status_code == 404

    async def test_workflow_not_found_error_code(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get(f"/api/workflows/{uuid4()}")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_workflow_not_found_error_message(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get(f"/api/workflows/{uuid4()}")
        assert resp.json()["error"]["message"] == "Workflow not found."
