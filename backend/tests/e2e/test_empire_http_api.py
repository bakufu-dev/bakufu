"""Empire HTTP API E2E テスト — TC-E2E-EM-003 ライフサイクル一気通貫.

Per ``docs/features/empire/system-test-design.md`` §E2E テストケース.

Covers:
  TC-E2E-EM-003  HTTP API 経由 Empire ライフサイクル一気通貫
                 POST→GET→PATCH→DELETE→GET(archived)→PATCH(409)→POST(409)
                 業務ルール R1-1, R1-5, R1-8 / 受入基準 12〜19 を一気通貫で確認

Issue: #56
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestEmpireLifecycleE2E:
    """TC-E2E-EM-003: Empire HTTP API lifecycle — complete blackbox end-to-end.

    All assertions are against HTTP responses only (no DB direct access,
    no internal state inspection).  This test exercises the full stack:
    httpx → FastAPI → EmpireService → SqliteEmpireRepository → SQLite.
    """

    async def test_full_lifecycle(self, empire_e2e_client: AsyncClient) -> None:
        """TC-E2E-EM-003: POST→GET→PATCH→DELETE→GET(archived)→PATCH(409)→POST(409).

        Step 1: POST /api/empires → 201, empire_id 取得
        Step 2: GET /api/empires/{id} → 200, archived=false
        Step 3: PATCH /api/empires/{id} name 更新 → 200, 更新確認
        Step 4: DELETE /api/empires/{id} → 204
        Step 5: GET /api/empires/{id} → 200, archived=true
        Step 6: PATCH /api/empires/{id} → 409 conflict (アーカイブ済み)
        Step 7: POST /api/empires → 409 conflict (R1-5: 既存 Empire あり)
        """
        # ── Step 1: 新規 Empire 作成 ─────────────────────────────────────────
        create_resp = await empire_e2e_client.post(
            "/api/empires",
            json={"name": "山田の幕府"},
        )
        assert create_resp.status_code == 201
        body = create_resp.json()
        assert body["name"] == "山田の幕府"
        assert body["archived"] is False
        assert isinstance(body["id"], str)
        assert body["rooms"] == []
        assert body["agents"] == []
        empire_id = body["id"]

        # ── Step 2: GET で存在確認 / archived=false ──────────────────────────
        get_resp = await empire_e2e_client.get(f"/api/empires/{empire_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["archived"] is False
        assert get_resp.json()["name"] == "山田の幕府"

        # ── Step 3: PATCH で name 更新 ──────────────────────────────────────
        patch_resp = await empire_e2e_client.patch(
            f"/api/empires/{empire_id}",
            json={"name": "新山田の幕府"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["name"] == "新山田の幕府"
        assert patch_resp.json()["archived"] is False

        # GET で更新が永続化されていることをラウンドトリップ確認
        roundtrip = await empire_e2e_client.get(f"/api/empires/{empire_id}")
        assert roundtrip.json()["name"] == "新山田の幕府"

        # ── Step 4: DELETE → 204 No Content ────────────────────────────────
        delete_resp = await empire_e2e_client.delete(f"/api/empires/{empire_id}")
        assert delete_resp.status_code == 204
        assert delete_resp.content == b""

        # ── Step 5: GET → archived=true（論理削除確認）─────────────────────
        get_archived = await empire_e2e_client.get(f"/api/empires/{empire_id}")
        assert get_archived.status_code == 200
        assert get_archived.json()["archived"] is True
        # name は保持されている
        assert get_archived.json()["name"] == "新山田の幕府"

        # ── Step 6: PATCH → 409 Conflict（アーカイブ済み, R1-8）─────────────
        patch_archived = await empire_e2e_client.patch(
            f"/api/empires/{empire_id}",
            json={"name": "もう一度"},
        )
        assert patch_archived.status_code == 409
        err = patch_archived.json()["error"]
        assert err["code"] == "conflict"
        assert err["message"] == "Empire is archived and cannot be modified."

        # ── Step 7: POST → 409 Conflict（R1-5: 既存 Empire あり）──────────
        post_duplicate = await empire_e2e_client.post(
            "/api/empires",
            json={"name": "別の幕府"},
        )
        assert post_duplicate.status_code == 409
        err2 = post_duplicate.json()["error"]
        assert err2["code"] == "conflict"
        assert err2["message"] == "Empire already exists."

    async def test_list_reflects_created_empire(self, empire_e2e_client: AsyncClient) -> None:
        """TC-E2E-EM-003 補足: GET /api/empires 一覧が作成した Empire を返す."""
        # 空リスト確認
        list_empty = await empire_e2e_client.get("/api/empires")
        assert list_empty.status_code == 200
        assert list_empty.json() == {"items": [], "total": 0}

        # Empire 作成後に一覧に反映されることを確認
        await empire_e2e_client.post("/api/empires", json={"name": "幕府一覧テスト"})
        list_with = await empire_e2e_client.get("/api/empires")
        assert list_with.status_code == 200
        data = list_with.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "幕府一覧テスト"
