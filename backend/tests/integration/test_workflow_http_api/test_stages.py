"""workflow / http-api 結合テスト — STAGES 系 (TC-IT-WFH-008/025).

Covers:
  TC-IT-WFH-008  GET /api/workflows/{id}/stages → 200 StageListResponse
  TC-IT-WFH-025  GET Workflow 不在 → 404 not_found (MSG-WF-HTTP-001)

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


class TestGetStages:
    """TC-IT-WFH-008: GET /api/workflows/{id}/stages → 200 StageListResponse。"""

    async def test_get_stages_returns_200(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.get(f"/api/workflows/{wf.id}/stages")  # type: ignore[attr-defined]
        assert resp.status_code == 200

    async def test_get_stages_has_stages_list(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.get(f"/api/workflows/{wf.id}/stages")  # type: ignore[attr-defined]
        assert isinstance(resp.json()["stages"], list)

    async def test_get_stages_has_transitions_list(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.get(f"/api/workflows/{wf.id}/stages")  # type: ignore[attr-defined]
        assert isinstance(resp.json()["transitions"], list)

    async def test_get_stages_has_entry_stage_id(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.get(f"/api/workflows/{wf.id}/stages")  # type: ignore[attr-defined]
        assert isinstance(resp.json()["entry_stage_id"], str)

    async def test_get_stages_entry_stage_id_matches_workflow(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.get(f"/api/workflows/{wf.id}/stages")  # type: ignore[attr-defined]
        assert resp.json()["entry_stage_id"] == str(wf.entry_stage_id)  # type: ignore[attr-defined]


class TestGetStagesNotFound:
    """TC-IT-WFH-025: GET /stages Workflow 不在 → 404 not_found (MSG-WF-HTTP-001)。"""

    async def test_workflow_not_found_returns_404(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get(f"/api/workflows/{uuid4()}/stages")
        assert resp.status_code == 404

    async def test_workflow_not_found_error_code(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get(f"/api/workflows/{uuid4()}/stages")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_workflow_not_found_error_message(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get(f"/api/workflows/{uuid4()}/stages")
        assert resp.json()["error"]["message"] == "Workflow not found."
