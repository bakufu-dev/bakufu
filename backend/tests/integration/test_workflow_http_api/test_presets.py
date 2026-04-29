"""workflow / http-api 結合テスト — PRESETS 系 (TC-IT-WFH-009/027).

Covers:
  TC-IT-WFH-009  GET /api/workflows/presets → 200 WorkflowPresetListResponse (total=2)
  TC-IT-WFH-027  GET /api/workflows/presets リテラルパス優先（ルーティング順序）

Issue: #58
"""

from __future__ import annotations

import pytest

from tests.integration.test_workflow_http_api.helpers import WfTestCtx

pytestmark = pytest.mark.asyncio


class TestGetPresets:
    """TC-IT-WFH-009: GET /api/workflows/presets → 200 WorkflowPresetListResponse。"""

    async def test_get_presets_returns_200(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get("/api/workflows/presets")
        assert resp.status_code == 200

    async def test_get_presets_total_is_2(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get("/api/workflows/presets")
        assert resp.json()["total"] == 2

    async def test_get_presets_items_has_2_elements(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get("/api/workflows/presets")
        assert len(resp.json()["items"]) == 2

    async def test_get_presets_includes_v_model(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get("/api/workflows/presets")
        preset_names = [item["preset_name"] for item in resp.json()["items"]]
        assert "v-model" in preset_names

    async def test_get_presets_includes_agile(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get("/api/workflows/presets")
        preset_names = [item["preset_name"] for item in resp.json()["items"]]
        assert "agile" in preset_names

    async def test_get_presets_items_have_display_name(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get("/api/workflows/presets")
        assert all("display_name" in item for item in resp.json()["items"])

    async def test_get_presets_items_have_stage_count(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.get("/api/workflows/presets")
        assert all(isinstance(item["stage_count"], int) for item in resp.json()["items"])


class TestPresetsRoutingOrder:
    """TC-IT-WFH-027: GET /api/workflows/presets リテラルパス優先（§確定E）。"""

    async def test_presets_not_treated_as_uuid_param(self, wf_ctx: WfTestCtx) -> None:
        """GET /api/workflows/presets が 404/422 ではなく 200 を返すこと。

        ルーティング登録順序の物理保証（§確定E）。
        """
        resp = await wf_ctx.client.get("/api/workflows/presets")
        assert resp.status_code == 200
