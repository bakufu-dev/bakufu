"""workflow / http-api 結合テスト — A02 masking 物理確認 (TC-IT-WFH-029).

Covers:
  TC-IT-WFH-029  POST/PATCH レスポンスの notify_channels が masked であること
                 （detailed-design.md §確定A / A02 Cryptographic Failures 防御）

Issue: #58
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.factories.workflow import DEFAULT_DISCORD_WEBHOOK
from tests.integration.test_workflow_http_api.helpers import (
    WfTestCtx,
    _create_empire,
    _create_room,
    _external_review_stage_payload,
    _seed_workflow_direct,
)

pytestmark = pytest.mark.asyncio

_RAW_TOKEN = "SyntheticToken_-abcXYZ"


class TestA02MaskingPost:
    """TC-IT-WFH-029 (a): POST 201 レスポンスの notify_channels が masked。"""

    async def _post_workflow_with_external_review(self, wf_ctx: WfTestCtx) -> object:
        """EXTERNAL_REVIEW stage を含む workflow を POST する。"""
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "外部レビューフロー",
                "stages": [_external_review_stage_payload(stage_id, DEFAULT_DISCORD_WEBHOOK)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        return resp

    async def test_post_returns_201(self, wf_ctx: WfTestCtx) -> None:
        resp = await self._post_workflow_with_external_review(wf_ctx)
        assert resp.status_code == 201  # type: ignore[union-attr]

    async def test_post_notify_channels_token_not_in_response(self, wf_ctx: WfTestCtx) -> None:
        """POST 201 レスポンスの notify_channels に raw token が含まれないこと。"""
        import json

        resp = await self._post_workflow_with_external_review(wf_ctx)
        assert _RAW_TOKEN not in json.dumps(resp.json())  # type: ignore[union-attr]

    async def test_post_notify_channels_is_redacted(self, wf_ctx: WfTestCtx) -> None:
        """POST 201 レスポンスの EXTERNAL_REVIEW stage の notify_channels が REDACTED 文字列。"""
        resp = await self._post_workflow_with_external_review(wf_ctx)
        stage = resp.json()["stages"][0]  # type: ignore[union-attr]
        assert len(stage["notify_channels"]) == 1
        assert "<REDACTED" in stage["notify_channels"][0]


class TestA02MaskingPatch:
    """TC-IT-WFH-029 (b): PATCH 200 レスポンスの notify_channels が masked。"""

    async def _create_workflow_with_external_review(self, wf_ctx: WfTestCtx) -> dict:
        """EXTERNAL_REVIEW stage を含む workflow を作成して JSON を返す。"""
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "外部レビューフロー",
                "stages": [_external_review_stage_payload(stage_id, DEFAULT_DISCORD_WEBHOOK)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert resp.status_code == 201
        return resp.json()  # type: ignore[return-value]

    async def test_patch_notify_channels_token_not_in_response(self, wf_ctx: WfTestCtx) -> None:
        """PATCH レスポンス（500 エラー含む）に raw token が含まれないこと。

        BUG-WF-003 により PATCH は 500 を返すが、500 エラーボディにも raw token は含まれない。
        A02 観点（token 漏洩なし）としては成立する。
        """
        import json

        workflow = await self._create_workflow_with_external_review(wf_ctx)
        patch_resp = await wf_ctx.client.patch(
            f"/api/workflows/{workflow['id']}",
            json={"name": "名前変更"},
        )
        assert _RAW_TOKEN not in json.dumps(patch_resp.json())

    @pytest.mark.xfail(
        reason=(
            "BUG-WF-003: §確定 H §不可逆性 (TC-IT-WFR-014) により "
            "EXTERNAL_REVIEW workflow の find_by_id は ValidationError を送出する。"
            "PATCH が 500 になり stages キーが存在しない。"
        ),
        strict=True,
    )
    async def test_patch_notify_channels_is_redacted(self, wf_ctx: WfTestCtx) -> None:
        """PATCH 200 レスポンスの EXTERNAL_REVIEW stage の notify_channels が REDACTED 文字列。"""
        workflow = await self._create_workflow_with_external_review(wf_ctx)
        patch_resp = await wf_ctx.client.patch(
            f"/api/workflows/{workflow['id']}",
            json={"name": "名前変更"},
        )
        stage = patch_resp.json()["stages"][0]
        assert len(stage["notify_channels"]) == 1
        assert "<REDACTED" in stage["notify_channels"][0]

    @pytest.mark.xfail(
        reason=(
            "BUG-WF-003: §確定 H §不可逆性 (TC-IT-WFR-014) により "
            "EXTERNAL_REVIEW workflow の find_by_id は ValidationError を送出する。"
            "PATCH が 500 になる。TC-IT-WFH-029(b) との競合。"
        ),
        strict=True,
    )
    async def test_patch_returns_200(self, wf_ctx: WfTestCtx) -> None:
        workflow = await self._create_workflow_with_external_review(wf_ctx)
        patch_resp = await wf_ctx.client.patch(
            f"/api/workflows/{workflow['id']}",
            json={"name": "名前変更"},
        )
        assert patch_resp.status_code == 200
