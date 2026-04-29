"""workflow / http-api 結合テスト — CREATE 系
(TC-IT-WFH-001/002/011/012/013/014/015/016).

Covers:
  TC-IT-WFH-001  POST JSON 定義 → 201 WorkflowResponse
  TC-IT-WFH-002  POST プリセット → 201 WorkflowResponse (stages=13)
  TC-IT-WFH-011  POST Room 不在 → 404 not_found
  TC-IT-WFH-012  POST Room archived → 409 conflict
  TC-IT-WFH-013  POST プリセット不明 → 404 not_found (MSG-WF-HTTP-004)
  TC-IT-WFH-014  POST DAG 違反 → 422 validation_error (MSG-WF-HTTP-005)
  TC-IT-WFH-015  POST 排他バリデーション（両方指定）→ 422
  TC-IT-WFH-016  POST 排他バリデーション（両方 None）→ 422

Issue: #58
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration.test_workflow_http_api.helpers import (
    WfTestCtx,
    _create_empire,
    _create_room,
    _minimal_stage_payload,
    _seed_workflow_direct,
)

pytestmark = pytest.mark.asyncio


class TestCreateWorkflowJson:
    """TC-IT-WFH-001: POST /api/rooms/{room_id}/workflows JSON 定義 → 201."""

    async def test_create_returns_201(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "Vモデル開発フロー",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert resp.status_code == 201

    async def test_create_response_has_id(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "Vモデル開発フロー",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert isinstance(resp.json()["id"], str)

    async def test_create_response_name_matches(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "Vモデル開発フロー",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert resp.json()["name"] == "Vモデル開発フロー"

    async def test_create_response_stages_has_one_item(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "Vモデル開発フロー",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert len(resp.json()["stages"]) == 1

    async def test_create_response_archived_is_false(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "Vモデル開発フロー",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert resp.json()["archived"] is False

    async def test_create_updates_room_workflow_id(self, wf_ctx: WfTestCtx) -> None:
        """POST 後に GET /api/rooms/{room_id} で Room.workflow_id が更新されていること。"""
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        post_resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "Vモデル開発フロー",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        new_workflow_id = post_resp.json()["id"]
        get_resp = await wf_ctx.client.get(f"/api/rooms/{room['id']}")
        assert get_resp.json()["workflow_id"] == new_workflow_id


class TestCreateWorkflowPreset:
    """TC-IT-WFH-002: POST プリセット指定 → 201 WorkflowResponse (stages=13/transitions=15)."""

    async def test_preset_returns_201(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={"preset_name": "v-model"},
        )
        assert resp.status_code == 201

    async def test_preset_stages_count_is_13(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={"preset_name": "v-model"},
        )
        assert len(resp.json()["stages"]) == 13

    async def test_preset_transitions_count_is_15(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={"preset_name": "v-model"},
        )
        assert len(resp.json()["transitions"]) == 15

    async def test_preset_archived_is_false(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={"preset_name": "v-model"},
        )
        assert resp.json()["archived"] is False


class TestCreateWorkflowRoomNotFound:
    """TC-IT-WFH-011: POST Room 不在 → 404 not_found (RoomNotFoundError)."""

    async def test_room_not_found_returns_404(self, wf_ctx: WfTestCtx) -> None:
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{uuid4()}/workflows",
            json={
                "name": "X",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert resp.status_code == 404

    async def test_room_not_found_error_code(self, wf_ctx: WfTestCtx) -> None:
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{uuid4()}/workflows",
            json={
                "name": "X",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_room_not_found_error_message(self, wf_ctx: WfTestCtx) -> None:
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{uuid4()}/workflows",
            json={
                "name": "X",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert resp.json()["error"]["message"] == "Room not found."


class TestCreateWorkflowRoomArchived:
    """TC-IT-WFH-012: POST Room archived → 409 conflict (RoomArchivedError)."""

    async def test_archived_room_returns_409(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        await wf_ctx.client.delete(f"/api/rooms/{room['id']}")
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "X",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert resp.status_code == 409

    async def test_archived_room_error_code(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        await wf_ctx.client.delete(f"/api/rooms/{room['id']}")
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "X",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_archived_room_error_message(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        await wf_ctx.client.delete(f"/api/rooms/{room['id']}")
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "X",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
            },
        )
        assert resp.json()["error"]["message"] == "Room is archived and cannot be modified."


class TestCreateWorkflowPresetNotFound:
    """TC-IT-WFH-013: POST プリセット不明 → 404 not_found (MSG-WF-HTTP-004)."""

    async def test_unknown_preset_returns_404(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={"preset_name": "unknown-preset-xyz"},
        )
        assert resp.status_code == 404

    async def test_unknown_preset_error_code(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={"preset_name": "unknown-preset-xyz"},
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_unknown_preset_error_message(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={"preset_name": "unknown-preset-xyz"},
        )
        assert resp.json()["error"]["message"] == "Workflow preset not found."


class TestCreateWorkflowDagViolation:
    """TC-IT-WFH-014: POST DAG 違反 → 422 validation_error (MSG-WF-HTTP-005)."""

    async def test_dag_violation_returns_422(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        nonexistent_id = uuid4()  # entry_stage_id が stages に存在しない
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "テスト",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(nonexistent_id),
            },
        )
        assert resp.status_code == 422

    async def test_dag_violation_error_code(self, wf_ctx: WfTestCtx) -> None:
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        nonexistent_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "テスト",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(nonexistent_id),
            },
        )
        assert resp.json()["error"]["code"] == "validation_error"

    async def test_dag_violation_message_no_fail_prefix(self, wf_ctx: WfTestCtx) -> None:
        """[FAIL] プレフィックスが HTTP レスポンスに露出しないこと (MSG-WF-HTTP-005 前処理)。"""
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        nonexistent_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "テスト",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(nonexistent_id),
            },
        )
        assert "[FAIL]" not in resp.json()["error"]["message"]

    async def test_dag_violation_message_no_next_suffix(self, wf_ctx: WfTestCtx) -> None:
        """\nNext:.* サフィックスが HTTP レスポンスに露出しないこと (MSG-WF-HTTP-005 前処理)。"""
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        nonexistent_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "テスト",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(nonexistent_id),
            },
        )
        assert "Next:" not in resp.json()["error"]["message"]


class TestCreateWorkflowExclusiveValidation:
    """TC-IT-WFH-015/016: WorkflowCreate 排他バリデーション。"""

    async def test_both_json_and_preset_returns_422(self, wf_ctx: WfTestCtx) -> None:
        """TC-IT-WFH-015: preset_name + stages 同時指定 → 422。"""
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        stage_id = uuid4()
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={
                "name": "X",
                "stages": [_minimal_stage_payload(stage_id)],
                "transitions": [],
                "entry_stage_id": str(stage_id),
                "preset_name": "v-model",
            },
        )
        assert resp.status_code == 422

    async def test_both_none_returns_422(self, wf_ctx: WfTestCtx) -> None:
        """TC-IT-WFH-016: 全フィールド None → 422。"""
        empire = await _create_empire(wf_ctx.client)
        placeholder = await _seed_workflow_direct(wf_ctx.session_factory)
        room = await _create_room(wf_ctx.client, str(empire["id"]), str(placeholder.id))  # type: ignore[attr-defined]
        resp = await wf_ctx.client.post(
            f"/api/rooms/{room['id']}/workflows",
            json={},
        )
        assert resp.status_code == 422
