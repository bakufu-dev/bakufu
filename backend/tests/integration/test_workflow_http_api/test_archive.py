"""workflow / http-api 結合テスト — ARCHIVE 系 (TC-IT-WFH-007/023/024).

Covers:
  TC-IT-WFH-007  DELETE → 204 + 後続 PATCH → 409 conflict (MSG-WF-HTTP-002)
  TC-IT-WFH-023  DELETE Workflow 不在 → 404 not_found (MSG-WF-HTTP-001)
  TC-IT-WFH-024  DELETE × 2 冪等性 → 両方 204 (R1-14)

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


class TestArchiveWorkflow:
    """TC-IT-WFH-007: DELETE → 204; 後続 PATCH → 409 (REQ-WF-HTTP-005)。"""

    async def test_archive_returns_204(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.delete(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        assert resp.status_code == 204

    async def test_archive_response_has_no_body(self, wf_ctx: WfTestCtx) -> None:
        """204 No Content は body を持たない。"""
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.delete(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        assert resp.content == b""

    async def test_after_archive_patch_returns_409(self, wf_ctx: WfTestCtx) -> None:
        """DELETE 後の PATCH → 409 conflict (WorkflowArchivedError)。"""
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        await wf_ctx.client.delete(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"name": "変更試み"},
        )
        assert resp.status_code == 409

    async def test_after_archive_patch_error_code(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        await wf_ctx.client.delete(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"name": "変更試み"},
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_after_archive_patch_error_message(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        await wf_ctx.client.delete(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"name": "変更試み"},
        )
        assert resp.json()["error"]["message"] == "Workflow is archived and cannot be modified."


class TestArchiveWorkflowNotFound:
    """TC-IT-WFH-023: DELETE Workflow 不在 → 404 not_found (MSG-WF-HTTP-001)。"""

    async def test_workflow_not_found_returns_404(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.delete(f"/api/workflows/{uuid4()}")
        assert resp.status_code == 404

    async def test_workflow_not_found_error_code(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.delete(f"/api/workflows/{uuid4()}")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_workflow_not_found_error_message(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.delete(f"/api/workflows/{uuid4()}")
        assert resp.json()["error"]["message"] == "Workflow not found."


class TestArchiveWorkflowIdempotent:
    """TC-IT-WFH-024: DELETE × 2 冪等性 (R1-14「再アーカイブは禁止されない」)。"""

    async def test_first_archive_returns_204(self, wf_ctx: WfTestCtx) -> None:
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        resp = await wf_ctx.client.delete(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        assert resp.status_code == 204

    async def test_second_archive_also_returns_204(self, wf_ctx: WfTestCtx) -> None:
        """2 回目の DELETE も 204 (冪等 — archive() は WorkflowArchivedError を発生させない)。"""
        wf = await _seed_workflow_direct(wf_ctx.session_factory)
        await wf_ctx.client.delete(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        resp = await wf_ctx.client.delete(f"/api/workflows/{wf.id}")  # type: ignore[attr-defined]
        assert resp.status_code == 204
