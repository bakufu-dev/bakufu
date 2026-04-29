"""workflow / http-api 結合テスト — A02 masking / R1-16 不可逆 PATCH 物理確認.

Covers:
  TC-IT-WFH-029 (a)  POST 201 レスポンスの notify_channels が masked であること
                     （detailed-design.md §確定A / A02 Cryptographic Failures 防御）
  TC-IT-WFH-029 (b)  EXTERNAL_REVIEW workflow への PATCH が 409 になること（R1-16）
  TC-IT-WFH-030      WorkflowIrreversibleError → HTTP 409 / MSG-WF-HTTP-008
                     （直接 save() 経由の masked workflow に対する PATCH 拒否）

Issue: #58
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from tests.factories.workflow import DEFAULT_DISCORD_WEBHOOK
from tests.integration.test_workflow_http_api.helpers import (
    WfTestCtx,
    _create_empire,
    _create_room,
    _external_review_stage_payload,
    _seed_external_review_workflow_direct,
    _seed_workflow_direct,
)

pytestmark = pytest.mark.asyncio

_RAW_TOKEN = "SyntheticToken_-abcXYZ"
_MSG_WF_HTTP_008 = (
    "Workflow contains masked notify_channels and cannot be modified."
    " Please recreate the workflow with new webhook URLs."
)


class TestA02MaskingPost:
    """TC-IT-WFH-029 (a): POST 201 レスポンスの notify_channels が masked。"""

    async def _post_workflow_with_external_review(self, wf_ctx: WfTestCtx) -> object:
        """EXTERNAL_REVIEW stage を含む workflow を POST する。"""
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(
            wf_ctx.client,
            str(empire["id"]),
            str(placeholder.id),  # type: ignore[attr-defined]
        )
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
        assert len(stage["notify_channels"]) == 1  # type: ignore[arg-type]
        assert "<REDACTED" in stage["notify_channels"][0]


class TestA02MaskingPatch:
    """TC-IT-WFH-029 (b): EXTERNAL_REVIEW workflow への PATCH が 409 (R1-16)。

    §確定 H §不可逆性により EXTERNAL_REVIEW workflow は永続化後 PATCH 不可。
    WorkflowIrreversibleError → HTTP 409 / MSG-WF-HTTP-008 で拒否される。
    """

    async def _create_workflow_with_external_review(self, wf_ctx: WfTestCtx) -> dict[str, Any]:
        """EXTERNAL_REVIEW stage を含む workflow を POST で作成して JSON を返す。"""
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(
            wf_ctx.client,
            str(empire["id"]),
            str(placeholder.id),  # type: ignore[attr-defined]
        )
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

    async def test_patch_returns_409(self, wf_ctx: WfTestCtx) -> None:
        """PATCH は 409 Conflict を返すこと（WorkflowIrreversibleError → R1-16）。"""
        workflow = await self._create_workflow_with_external_review(wf_ctx)
        patch_resp = await wf_ctx.client.patch(
            f"/api/workflows/{workflow['id']}",
            json={"name": "名前変更"},
        )
        assert patch_resp.status_code == 409

    async def test_patch_error_code_is_conflict(self, wf_ctx: WfTestCtx) -> None:
        """PATCH 409 レスポンスの error.code が "conflict"。"""
        workflow = await self._create_workflow_with_external_review(wf_ctx)
        patch_resp = await wf_ctx.client.patch(
            f"/api/workflows/{workflow['id']}",
            json={"name": "名前変更"},
        )
        assert patch_resp.json()["error"]["code"] == "conflict"

    async def test_patch_error_message_matches_msg_wf_http_008(self, wf_ctx: WfTestCtx) -> None:
        """PATCH 409 レスポンスの error.message が MSG-WF-HTTP-008 確定文言と完全一致。"""
        workflow = await self._create_workflow_with_external_review(wf_ctx)
        patch_resp = await wf_ctx.client.patch(
            f"/api/workflows/{workflow['id']}",
            json={"name": "名前変更"},
        )
        assert patch_resp.json()["error"]["message"] == _MSG_WF_HTTP_008

    async def test_patch_notify_channels_token_not_in_response(self, wf_ctx: WfTestCtx) -> None:
        """PATCH 409 レスポンスに raw token が含まれないこと（A02 token 漏洩なし確認）。"""
        import json

        workflow = await self._create_workflow_with_external_review(wf_ctx)
        patch_resp = await wf_ctx.client.patch(
            f"/api/workflows/{workflow['id']}",
            json={"name": "名前変更"},
        )
        assert _RAW_TOKEN not in json.dumps(patch_resp.json())


class TestWorkflowIrreversiblePatch:
    """TC-IT-WFH-030: WorkflowIrreversibleError → HTTP 409 (直接 save() 経路)。

    POST 経由でなく SqliteWorkflowRepository.save() で直接 EXTERNAL_REVIEW
    workflow を tempdb に保存した場合も、PATCH が同じ 409 を返すことを確認する。
    """

    async def test_patch_returns_409(self, wf_ctx: WfTestCtx) -> None:
        """直接 save() 経路: PATCH は 409 を返すこと。"""
        wf = await _seed_external_review_workflow_direct(wf_ctx.session_factory)
        patch_resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"name": "更新試み"},
        )
        assert patch_resp.status_code == 409

    async def test_patch_error_code_is_conflict(self, wf_ctx: WfTestCtx) -> None:
        """直接 save() 経路: error.code が "conflict"。"""
        wf = await _seed_external_review_workflow_direct(wf_ctx.session_factory)
        patch_resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"name": "更新試み"},
        )
        assert patch_resp.json()["error"]["code"] == "conflict"

    async def test_patch_error_message_matches_msg_wf_http_008(self, wf_ctx: WfTestCtx) -> None:
        """直接 save() 経路: error.message が MSG-WF-HTTP-008 確定文言と完全一致。"""
        wf = await _seed_external_review_workflow_direct(wf_ctx.session_factory)
        patch_resp = await wf_ctx.client.patch(
            f"/api/workflows/{wf.id}",  # type: ignore[attr-defined]
            json={"name": "更新試み"},
        )
        assert patch_resp.json()["error"]["message"] == _MSG_WF_HTTP_008
