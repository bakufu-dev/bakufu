"""workflow / http-api 結合テスト — UUID パスインジェクション防御 (TC-IT-WFH-026).

Covers:
  TC-IT-WFH-026  不正 UUID パスパラメータ → 422 (T3: UUID パスインジェクション防御)

Issue: #58
"""

from __future__ import annotations

import pytest

from tests.integration.test_workflow_http_api.helpers import WfTestCtx

pytestmark = pytest.mark.asyncio


class TestUuidPathInjection:
    """TC-IT-WFH-026: FastAPI UUID 型強制 → 422 (500 ではない)。"""

    async def test_get_workflow_invalid_uuid_returns_422(self, wf_ctx: WfTestCtx) -> None:
        """(a) GET /api/workflows/not-a-uuid → 422。"""
        resp = await wf_ctx.client.get("/api/workflows/not-a-uuid")
        assert resp.status_code == 422

    async def test_patch_workflow_invalid_uuid_returns_422(self, wf_ctx: WfTestCtx) -> None:
        """(b) PATCH /api/workflows/not-a-uuid → 422。"""
        resp = await wf_ctx.client.patch(
            "/api/workflows/not-a-uuid",
            json={"name": "X"},
        )
        assert resp.status_code == 422

    async def test_delete_workflow_invalid_uuid_returns_422(self, wf_ctx: WfTestCtx) -> None:
        """(c) DELETE /api/workflows/not-a-uuid → 422。"""
        resp = await wf_ctx.client.delete("/api/workflows/not-a-uuid")
        assert resp.status_code == 422

    async def test_get_stages_invalid_uuid_returns_422(self, wf_ctx: WfTestCtx) -> None:
        """(d) GET /api/workflows/not-a-uuid/stages → 422。"""
        resp = await wf_ctx.client.get("/api/workflows/not-a-uuid/stages")
        assert resp.status_code == 422

    async def test_post_workflows_invalid_room_uuid_returns_422(self, wf_ctx: WfTestCtx) -> None:
        """(e) POST /api/rooms/not-a-uuid/workflows → 422。"""
        from uuid import uuid4

        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            "/api/rooms/not-a-uuid/workflows",
            json={
                "name": "X",
                "stages": [
                    {
                        "id": str(stage_id),
                        "name": "S",
                        "kind": "WORK",
                        "required_role": ["DEVELOPER"],
                        "notify_channels": [],
                        "required_deliverables": [],
                    }
                ],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert resp.status_code == 422

    async def test_get_workflows_invalid_room_uuid_returns_422(self, wf_ctx: WfTestCtx) -> None:
        """(f) GET /api/rooms/not-a-uuid/workflows → 422。"""
        resp = await wf_ctx.client.get("/api/rooms/not-a-uuid/workflows")
        assert resp.status_code == 422
