"""Room HTTP API E2E テスト — TC-E2E-RM-004/005.

Per ``docs/features/room/system-test-design.md`` §E2E テストケース.

Covers:
  TC-E2E-RM-004  HTTP API 経由 Room ライフサイクル一気通貫
                 POST→GET list→POST agent→GET→DELETE agent→PATCH→DELETE→GET(archived)
                 受入基準 19, 22, 23, 25, 27, 28, 30 を一気通貫で確認
  TC-E2E-RM-005  HTTP API 経由の UUID バリデーション（不正 UUID → 422）
                 業務ルール R1-10

Issue: #57
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from tests.integration.test_room_http_api.helpers import (
    RoomTestCtx,
    _create_empire,
    _seed_agent,
    _seed_workflow,
)

pytestmark = pytest.mark.asyncio


class TestRoomLifecycleE2E:
    """TC-E2E-RM-004: Room HTTP API lifecycle — complete blackbox end-to-end.

    All assertions are against HTTP responses only (no DB direct access,
    no internal state inspection).  This test exercises the full stack:
    httpx → FastAPI → RoomService → SqliteRoomRepository → SQLite.

    Workflow / Agent は HTTP API スコープ外のため direct DB seeding を使う
    （assumed mock 禁止原則準拠）。
    """

    async def test_full_lifecycle(self, room_e2e_ctx: RoomTestCtx) -> None:
        """TC-E2E-RM-004: 8ステップ Room ライフサイクル一気通貫.

        Step 1: POST /api/empires/{empire_id}/rooms → 201, room_id 取得
        Step 2: GET /api/empires/{empire_id}/rooms → 200, items に 1 件
        Step 3: POST /api/rooms/{room_id}/agents (role="LEADER") → 201, members に 1 件
        Step 4: GET /api/rooms/{room_id} → 200, members に LEADER 1 件
        Step 5: DELETE /api/rooms/{room_id}/agents/{agent_id}/roles/LEADER → 204
        Step 6: PATCH /api/rooms/{room_id} (name="アジャイル開発室") → 200
        Step 7: DELETE /api/rooms/{room_id} → 204 (アーカイブ)
        Step 8: GET /api/rooms/{room_id} → 200, archived=True
        """
        client = room_e2e_ctx.client
        session_factory = room_e2e_ctx.session_factory

        # ── 前準備: Empire / Workflow / Agent をシード ───────────────────────
        empire = await _create_empire(client, name="E2E テスト幕府")
        empire_id_str: str = str(empire["id"])
        empire_id_uuid = UUID(empire_id_str)

        wf = await _seed_workflow(session_factory)
        workflow_id_str = str(wf.id)  # type: ignore[attr-defined]

        agent = await _seed_agent(session_factory, empire_id=empire_id_uuid)
        agent_id_str = str(agent.id)  # type: ignore[attr-defined]

        # ── Step 1: Room 作成 → 201 ──────────────────────────────────────────
        create_resp = await client.post(
            f"/api/empires/{empire_id_str}/rooms",
            json={
                "name": "V モデル開発室",
                "workflow_id": workflow_id_str,
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert create_resp.status_code == 201, f"Step 1 failed: {create_resp.text}"
        room_body = create_resp.json()
        assert room_body["name"] == "V モデル開発室"
        assert room_body["archived"] is False
        assert isinstance(room_body["id"], str)
        assert room_body["members"] == []
        room_id_str: str = str(room_body["id"])

        # ── Step 2: GET 一覧 → 200 + items に 1 件 ──────────────────────────
        list_resp = await client.get(f"/api/empires/{empire_id_str}/rooms")
        assert list_resp.status_code == 200, f"Step 2 failed: {list_resp.text}"
        list_body = list_resp.json()
        assert list_body["total"] == 1
        assert len(list_body["items"]) == 1
        assert list_body["items"][0]["id"] == room_id_str

        # ── Step 3: Agent 割り当て → 201 + members に 1 件 ──────────────────
        assign_resp = await client.post(
            f"/api/rooms/{room_id_str}/agents",
            json={"agent_id": agent_id_str, "role": "LEADER"},
        )
        assert assign_resp.status_code == 201, f"Step 3 failed: {assign_resp.text}"
        assign_body = assign_resp.json()
        assert len(assign_body["members"]) == 1
        assert assign_body["members"][0]["agent_id"] == agent_id_str
        assert assign_body["members"][0]["role"] == "LEADER"

        # ── Step 4: GET 単件 → 200 + members に LEADER 1 件 ─────────────────
        get_resp = await client.get(f"/api/rooms/{room_id_str}")
        assert get_resp.status_code == 200, f"Step 4 failed: {get_resp.text}"
        get_body = get_resp.json()
        assert len(get_body["members"]) == 1
        assert get_body["members"][0]["role"] == "LEADER"

        # ── Step 5: Agent 割り当て解除 → 204 ─────────────────────────────────
        unassign_resp = await client.delete(
            f"/api/rooms/{room_id_str}/agents/{agent_id_str}/roles/LEADER"
        )
        assert unassign_resp.status_code == 204, f"Step 5 failed: {unassign_resp.text}"
        assert unassign_resp.content == b""

        # ── Step 6: PATCH で name 更新 → 200 + name 更新済み ─────────────────
        patch_resp = await client.patch(
            f"/api/rooms/{room_id_str}",
            json={"name": "アジャイル開発室"},
        )
        assert patch_resp.status_code == 200, f"Step 6 failed: {patch_resp.text}"
        patch_body = patch_resp.json()
        assert patch_body["name"] == "アジャイル開発室"
        assert patch_body["archived"] is False

        # ラウンドトリップ: GET で更新が永続化されていることを確認
        roundtrip = await client.get(f"/api/rooms/{room_id_str}")
        assert roundtrip.json()["name"] == "アジャイル開発室"

        # ── Step 7: DELETE (アーカイブ) → 204 ────────────────────────────────
        archive_resp = await client.delete(f"/api/rooms/{room_id_str}")
        assert archive_resp.status_code == 204, f"Step 7 failed: {archive_resp.text}"
        assert archive_resp.content == b""

        # ── Step 8: GET → 200 + archived=True ────────────────────────────────
        get_archived = await client.get(f"/api/rooms/{room_id_str}")
        assert get_archived.status_code == 200, f"Step 8 failed: {get_archived.text}"
        archived_body = get_archived.json()
        assert archived_body["archived"] is True
        # name は保持されている（論理削除確認）
        assert archived_body["name"] == "アジャイル開発室"
        # members は空（Step 5 で解除済み）
        assert archived_body["members"] == []


class TestRoomUuidValidationE2E:
    """TC-E2E-RM-005: 不正 UUID パスパラメータはすべて 422 を返す（業務ルール R1-10）.

    FastAPI の path validation が不正 UUID 形式を 422 で弾く。
    500 が発生しないことを確認する（安全性担保）。
    """

    async def test_get_room_invalid_uuid_returns_422(self, room_e2e_ctx: RoomTestCtx) -> None:
        """GET /api/rooms/not-a-uuid → 422."""
        resp = await room_e2e_ctx.client.get("/api/rooms/not-a-uuid")
        assert resp.status_code == 422

    async def test_create_room_invalid_empire_uuid_returns_422(
        self, room_e2e_ctx: RoomTestCtx
    ) -> None:
        """POST /api/empires/not-a-uuid/rooms → 422."""
        resp = await room_e2e_ctx.client.post(
            "/api/empires/not-a-uuid/rooms",
            json={
                "name": "テスト",
                "workflow_id": str(uuid4()),
            },
        )
        assert resp.status_code == 422

    async def test_unassign_agent_invalid_agent_uuid_returns_422(
        self, room_e2e_ctx: RoomTestCtx
    ) -> None:
        """DELETE /api/rooms/{room_id}/agents/not-a-uuid/roles/LEADER → 422.

        room_id は有効 UUID 形式（存在しなくてよい）。agent_id が不正なため 422。
        """
        valid_room_id = str(uuid4())
        resp = await room_e2e_ctx.client.delete(
            f"/api/rooms/{valid_room_id}/agents/not-a-uuid/roles/LEADER"
        )
        assert resp.status_code == 422
