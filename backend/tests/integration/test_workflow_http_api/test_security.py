"""workflow / http-api 結合テスト — CSRF 保護 (TC-IT-WFH-028).

Covers:
  TC-IT-WFH-028  POST Origin: evil → 403 (T1: CSRF 保護の物理保証)

Issue: #58
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration.test_workflow_http_api.helpers import WfTestCtx

pytestmark = pytest.mark.asyncio


class TestCsrfProtection:
    """TC-IT-WFH-028: POST + 不正 Origin → 403 (TC-IT-HAF-008 と同一パターン)。"""

    async def test_evil_origin_post_returns_403(self, wf_ctx: WfTestCtx) -> None:
        """CSRF ミドルウェアが workflows ルータにも適用されることの物理保証。"""
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{uuid4()}/workflows",
            json={
                "name": "X",
                "stages": [
                    {
                        "id": str(stage_id),
                        "name": "S",
                        "kind": "WORK",
                        "required_role": ["DEVELOPER"],
                        "notify_channels": [],
                        "deliverable_template": "",
                    }
                ],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
            headers={"Origin": "http://evil.example.com"},
        )
        assert resp.status_code == 403

    async def test_evil_origin_error_code_is_forbidden(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.post(
            f"/api/rooms/{uuid4()}/workflows",
            json={"preset_name": "v-model"},
            headers={"Origin": "http://evil.example.com"},
        )
        assert resp.json()["error"]["code"] == "forbidden"

    async def test_evil_origin_error_message(self, wf_ctx: WfTestCtx) -> None:
        resp = await wf_ctx.client.post(
            f"/api/rooms/{uuid4()}/workflows",
            json={"preset_name": "v-model"},
            headers={"Origin": "http://evil.example.com"},
        )
        assert resp.json()["error"]["message"] == "CSRF check failed: Origin not allowed."
