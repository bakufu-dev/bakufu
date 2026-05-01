"""room-matching 結合テスト — RoleOverride CRUD 系 (TC-IT-RMM-007〜012).

Covers:
  TC-IT-RMM-007  PUT role-overrides/{role} → 200（upsert）
  TC-IT-RMM-008  PUT role-overrides/{role} 2 回目 → 200（上書き確認）
  TC-IT-RMM-009  DELETE role-overrides/{role} → 204
  TC-IT-RMM-010  DELETE 不在 override → 204（no-op）
  TC-IT-RMM-011  GET role-overrides → 200 一覧
  TC-IT-RMM-012  GET role-overrides → 200 空リスト

完全ブラックボックス: DB 直接確認禁止。PUT → GET ラウンドトリップで状態を確認する。

Issue: #120
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration.test_room_matching_http_api.conftest import (
    RmmTestCtx,
    _create_empire,
    _create_room,
    _make_min_version,
    _seed_workflow_with_required_deliverable,
)

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# 共通ヘルパー
# ---------------------------------------------------------------------------

_OVERRIDE_REFS = [
    {"template_id": str(uuid4()), "minimum_version": {"major": 1, "minor": 0, "patch": 0}}
]


async def _setup_room(ctx: RmmTestCtx, name: str = "オーバーライド検証室") -> tuple[str, str]:
    """Empire + Room を作成して (empire_id, room_id) を返す。"""
    empire = await _create_empire(ctx.client, name=f"幕府_{name}")
    wf = await _seed_workflow_with_required_deliverable(ctx.session_factory, uuid4())
    room = await _create_room(ctx.client, str(empire["id"]), str(wf.id), name=name)
    return str(empire["id"]), str(room["id"])


# ---------------------------------------------------------------------------
# TC-IT-RMM-007: PUT role-overrides/{role} → 200（upsert）
# ---------------------------------------------------------------------------
class TestPutRoleOverrideUpsert:
    """TC-IT-RMM-007: 初回 PUT → 200 (REQ-RM-MATCH-003 / UC-RM-016)。"""

    async def test_upsert_returns_200(self, rmm_ctx: RmmTestCtx) -> None:
        _empire_id, room_id = await _setup_room(rmm_ctx, "UPSERT初回テスト室")
        resp = await rmm_ctx.client.put(
            f"/api/rooms/{room_id}/role-overrides/DEVELOPER",
            json={"deliverable_template_refs": _OVERRIDE_REFS},
        )
        assert resp.status_code == 200

    async def test_upsert_response_contains_role(self, rmm_ctx: RmmTestCtx) -> None:
        _empire_id, room_id = await _setup_room(rmm_ctx, "UPSERTロール確認室")
        resp = await rmm_ctx.client.put(
            f"/api/rooms/{room_id}/role-overrides/DEVELOPER",
            json={"deliverable_template_refs": _OVERRIDE_REFS},
        )
        assert resp.json()["role"] == "DEVELOPER"

    async def test_upsert_response_contains_refs(self, rmm_ctx: RmmTestCtx) -> None:
        _empire_id, room_id = await _setup_room(rmm_ctx, "UPSERTrefs確認室")
        refs = [{"template_id": str(uuid4()), "minimum_version": _make_min_version()}]
        resp = await rmm_ctx.client.put(
            f"/api/rooms/{room_id}/role-overrides/DEVELOPER",
            json={"deliverable_template_refs": refs},
        )
        assert len(resp.json()["deliverable_template_refs"]) == 1

    async def test_upsert_roundtrip_via_get(self, rmm_ctx: RmmTestCtx) -> None:
        """PUT → GET でラウンドトリップ確認。"""
        _empire_id, room_id = await _setup_room(rmm_ctx, "UPSERTラウンドトリップ室")
        refs = [{"template_id": str(uuid4()), "minimum_version": _make_min_version()}]
        await rmm_ctx.client.put(
            f"/api/rooms/{room_id}/role-overrides/DEVELOPER",
            json={"deliverable_template_refs": refs},
        )
        get_resp = await rmm_ctx.client.get(f"/api/rooms/{room_id}/role-overrides")
        items = get_resp.json()["items"]
        assert len(items) == 1
        assert items[0]["role"] == "DEVELOPER"


# ---------------------------------------------------------------------------
# TC-IT-RMM-008: PUT 2 回目 → 200（上書き確認）
# ---------------------------------------------------------------------------
class TestPutRoleOverrideUpdate:
    """TC-IT-RMM-008: 2 回目 PUT → 200 で上書き（idempotent upsert）。"""

    async def test_second_upsert_returns_200(self, rmm_ctx: RmmTestCtx) -> None:
        _empire_id, room_id = await _setup_room(rmm_ctx, "2回目UPSERT室")
        refs_v1 = [{"template_id": str(uuid4()), "minimum_version": _make_min_version()}]
        refs_v2 = [
            {"template_id": str(uuid4()), "minimum_version": _make_min_version()},
            {"template_id": str(uuid4()), "minimum_version": _make_min_version()},
        ]
        await rmm_ctx.client.put(
            f"/api/rooms/{room_id}/role-overrides/DEVELOPER",
            json={"deliverable_template_refs": refs_v1},
        )
        resp = await rmm_ctx.client.put(
            f"/api/rooms/{room_id}/role-overrides/DEVELOPER",
            json={"deliverable_template_refs": refs_v2},
        )
        assert resp.status_code == 200

    async def test_second_upsert_overwrites_refs(self, rmm_ctx: RmmTestCtx) -> None:
        """2 回目 PUT で refs が上書きされている（GET でラウンドトリップ確認）。"""
        _empire_id, room_id = await _setup_room(rmm_ctx, "2回目上書き室")
        refs_v1 = [{"template_id": str(uuid4()), "minimum_version": _make_min_version()}]
        refs_v2 = [
            {"template_id": str(uuid4()), "minimum_version": _make_min_version()},
            {"template_id": str(uuid4()), "minimum_version": _make_min_version()},
        ]
        await rmm_ctx.client.put(
            f"/api/rooms/{room_id}/role-overrides/DEVELOPER",
            json={"deliverable_template_refs": refs_v1},
        )
        await rmm_ctx.client.put(
            f"/api/rooms/{room_id}/role-overrides/DEVELOPER",
            json={"deliverable_template_refs": refs_v2},
        )
        get_resp = await rmm_ctx.client.get(f"/api/rooms/{room_id}/role-overrides")
        items = get_resp.json()["items"]
        assert len(items[0]["deliverable_template_refs"]) == 2


# ---------------------------------------------------------------------------
# TC-IT-RMM-009: DELETE role-overrides/{role} → 204
# ---------------------------------------------------------------------------
class TestDeleteRoleOverride:
    """TC-IT-RMM-009: DELETE 存在する override → 204 (REQ-RM-MATCH-004 / UC-RM-016)。"""

    async def test_delete_existing_override_returns_204(self, rmm_ctx: RmmTestCtx) -> None:
        _empire_id, room_id = await _setup_room(rmm_ctx, "DELETE正常室")
        await rmm_ctx.client.put(
            f"/api/rooms/{room_id}/role-overrides/DEVELOPER",
            json={"deliverable_template_refs": _OVERRIDE_REFS},
        )
        resp = await rmm_ctx.client.delete(f"/api/rooms/{room_id}/role-overrides/DEVELOPER")
        assert resp.status_code == 204

    async def test_delete_removes_entry_from_list(self, rmm_ctx: RmmTestCtx) -> None:
        """DELETE 後 GET → 該当 role のエントリが消えていること（ラウンドトリップ）。"""
        _empire_id, room_id = await _setup_room(rmm_ctx, "DELETE削除確認室")
        await rmm_ctx.client.put(
            f"/api/rooms/{room_id}/role-overrides/DEVELOPER",
            json={"deliverable_template_refs": _OVERRIDE_REFS},
        )
        await rmm_ctx.client.delete(f"/api/rooms/{room_id}/role-overrides/DEVELOPER")
        get_resp = await rmm_ctx.client.get(f"/api/rooms/{room_id}/role-overrides")
        items = get_resp.json()["items"]
        assert all(item["role"] != "DEVELOPER" for item in items)


# ---------------------------------------------------------------------------
# TC-IT-RMM-010: DELETE 不在 override → 204（no-op）
# ---------------------------------------------------------------------------
class TestDeleteNotExistingRoleOverride:
    """TC-IT-RMM-010: 不在 override の DELETE → 204（no-op、REQ-RM-MATCH-004 no-op 仕様）。"""

    async def test_delete_nonexistent_override_returns_204(self, rmm_ctx: RmmTestCtx) -> None:
        _empire_id, room_id = await _setup_room(rmm_ctx, "DELETE不在室")
        resp = await rmm_ctx.client.delete(f"/api/rooms/{room_id}/role-overrides/TESTER")
        assert resp.status_code == 204

    async def test_delete_nonexistent_has_no_body(self, rmm_ctx: RmmTestCtx) -> None:
        _empire_id, room_id = await _setup_room(rmm_ctx, "DELETE不在本文確認室")
        resp = await rmm_ctx.client.delete(f"/api/rooms/{room_id}/role-overrides/WRITER")
        assert resp.content == b""


# ---------------------------------------------------------------------------
# TC-IT-RMM-011: GET role-overrides → 200 一覧
# ---------------------------------------------------------------------------
class TestGetRoleOverridesList:
    """TC-IT-RMM-011: 複数 override 登録後 GET → 200 + items 全件 (REQ-RM-MATCH-005)。"""

    async def test_get_overrides_returns_200(self, rmm_ctx: RmmTestCtx) -> None:
        _empire_id, room_id = await _setup_room(rmm_ctx, "GET一覧室")
        await rmm_ctx.client.put(
            f"/api/rooms/{room_id}/role-overrides/DEVELOPER",
            json={"deliverable_template_refs": _OVERRIDE_REFS},
        )
        resp = await rmm_ctx.client.get(f"/api/rooms/{room_id}/role-overrides")
        assert resp.status_code == 200

    async def test_get_overrides_lists_all_roles(self, rmm_ctx: RmmTestCtx) -> None:
        """2 ロール登録 → GET items に両方含まれる。"""
        _empire_id, room_id = await _setup_room(rmm_ctx, "GET全ロール室")
        for role in ("DEVELOPER", "TESTER"):
            await rmm_ctx.client.put(
                f"/api/rooms/{room_id}/role-overrides/{role}",
                json={"deliverable_template_refs": _OVERRIDE_REFS},
            )
        resp = await rmm_ctx.client.get(f"/api/rooms/{room_id}/role-overrides")
        items = resp.json()["items"]
        roles_in_resp = {item["role"] for item in items}
        assert "DEVELOPER" in roles_in_resp
        assert "TESTER" in roles_in_resp

    async def test_get_overrides_total_matches_items_count(self, rmm_ctx: RmmTestCtx) -> None:
        """total が items の件数と一致する。"""
        _empire_id, room_id = await _setup_room(rmm_ctx, "GETtotal確認室")
        await rmm_ctx.client.put(
            f"/api/rooms/{room_id}/role-overrides/REVIEWER",
            json={"deliverable_template_refs": _OVERRIDE_REFS},
        )
        resp = await rmm_ctx.client.get(f"/api/rooms/{room_id}/role-overrides")
        body = resp.json()
        assert body["total"] == len(body["items"])


# ---------------------------------------------------------------------------
# TC-IT-RMM-012: GET role-overrides → 200 空リスト
# ---------------------------------------------------------------------------
class TestGetRoleOverridesEmpty:
    """TC-IT-RMM-012: override 未登録 → GET 200 / items=[] (REQ-RM-MATCH-005 境界値)。"""

    async def test_get_overrides_empty_returns_200(self, rmm_ctx: RmmTestCtx) -> None:
        _empire_id, room_id = await _setup_room(rmm_ctx, "GET空リスト室")
        resp = await rmm_ctx.client.get(f"/api/rooms/{room_id}/role-overrides")
        assert resp.status_code == 200

    async def test_get_overrides_empty_items_is_empty_list(self, rmm_ctx: RmmTestCtx) -> None:
        _empire_id, room_id = await _setup_room(rmm_ctx, "GET空リスト確認室")
        resp = await rmm_ctx.client.get(f"/api/rooms/{room_id}/role-overrides")
        assert resp.json()["items"] == []

    async def test_get_overrides_empty_total_is_zero(self, rmm_ctx: RmmTestCtx) -> None:
        _empire_id, room_id = await _setup_room(rmm_ctx, "GETtotalゼロ室")
        resp = await rmm_ctx.client.get(f"/api/rooms/{room_id}/role-overrides")
        assert resp.json()["total"] == 0
