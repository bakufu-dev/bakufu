"""RoleProfile HTTP API 結合テスト — READ / DELETE 系 (TC-IT-RPH-001〜005 / 011〜012).

Covers:
  TC-IT-RPH-001  GET /api/empires/{empire_id}/role-profiles 空 → 200 [] (REQ-RP-HTTP-001)
  TC-IT-RPH-002  GET Empire 不在 → 404 (MSG-RP-HTTP-003)
  TC-IT-RPH-003  GET /api/empires/{empire_id}/role-profiles/{role} 正常系 → 200 (REQ-RP-HTTP-002)
  TC-IT-RPH-004  GET role プロファイル不在 → 404 not_found (MSG-RP-HTTP-001)
  TC-IT-RPH-005  GET role 不正値 → 422
  TC-IT-RPH-011  DELETE 正常系 → 204 (§確定E / REQ-RP-HTTP-004)
  TC-IT-RPH-012  DELETE 不在 → 404 not_found (MSG-RP-HTTP-001)

Issue: #122
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.integration.test_role_profile_http_api.conftest import (
    RpTestCtx,
    _create_empire,
)

pytestmark = pytest.mark.asyncio


async def _upsert_role_profile(
    ctx: RpTestCtx,
    empire_id: str,
    role: str = "DEVELOPER",
    refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"deliverable_template_refs": refs if refs is not None else []}
    resp = await ctx.client.put(
        f"/api/empires/{empire_id}/role-profiles/{role}",
        json=body,
    )
    assert resp.status_code == 200, f"upsert failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# TC-IT-RPH-001: GET list — 空リスト
# ---------------------------------------------------------------------------
class TestListEmpty:
    """TC-IT-RPH-001: Empire に RoleProfile なし → 200 空リスト (REQ-RP-HTTP-001)。"""

    async def test_list_returns_200_with_empty_items(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await rp_ctx.client.get(f"/api/empires/{empire['id']}/role-profiles")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    async def test_list_empty_total_is_zero(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await rp_ctx.client.get(f"/api/empires/{empire['id']}/role-profiles")
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# TC-IT-RPH-002: GET list — Empire 不在 → 404
# ---------------------------------------------------------------------------
class TestListEmpireNotFound:
    """TC-IT-RPH-002: 存在しない empire_id → 404 (MSG-RP-HTTP-003)。"""

    async def test_list_with_nonexistent_empire_returns_404(self, rp_ctx: RpTestCtx) -> None:
        unknown_empire_id = str(uuid.uuid4())
        resp = await rp_ctx.client.get(f"/api/empires/{unknown_empire_id}/role-profiles")
        assert resp.status_code == 404

    async def test_list_nonexistent_empire_code_is_not_found(self, rp_ctx: RpTestCtx) -> None:
        unknown_empire_id = str(uuid.uuid4())
        resp = await rp_ctx.client.get(f"/api/empires/{unknown_empire_id}/role-profiles")
        assert resp.json()["error"]["code"] == "not_found"


# ---------------------------------------------------------------------------
# TC-IT-RPH-003: GET single — 正常系
# ---------------------------------------------------------------------------
class TestGetSingle:
    """TC-IT-RPH-003: 存在する profile → 200 (REQ-RP-HTTP-002)。"""

    async def test_get_returns_200_with_profile(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        await _upsert_role_profile(rp_ctx, empire["id"], role="LEADER")
        resp = await rp_ctx.client.get(f"/api/empires/{empire['id']}/role-profiles/LEADER")
        assert resp.status_code == 200

    async def test_get_response_role_matches(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        await _upsert_role_profile(rp_ctx, empire["id"], role="LEADER")
        resp = await rp_ctx.client.get(f"/api/empires/{empire['id']}/role-profiles/LEADER")
        assert resp.json()["role"] == "LEADER"

    async def test_get_response_empire_id_matches(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        await _upsert_role_profile(rp_ctx, empire["id"], role="REVIEWER")
        resp = await rp_ctx.client.get(f"/api/empires/{empire['id']}/role-profiles/REVIEWER")
        assert resp.json()["empire_id"] == empire["id"]


# ---------------------------------------------------------------------------
# TC-IT-RPH-004: GET single — 不在 → 404
# ---------------------------------------------------------------------------
class TestGetNonexistent:
    """TC-IT-RPH-004: 存在しない role → 404 not_found (MSG-RP-HTTP-001)。"""

    async def test_get_nonexistent_returns_404(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await rp_ctx.client.get(f"/api/empires/{empire['id']}/role-profiles/DEVELOPER")
        assert resp.status_code == 404

    async def test_get_nonexistent_code_is_not_found(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await rp_ctx.client.get(f"/api/empires/{empire['id']}/role-profiles/DEVELOPER")
        assert resp.json()["error"]["code"] == "not_found"


# ---------------------------------------------------------------------------
# TC-IT-RPH-005: GET single — role 不正値 → 422
# ---------------------------------------------------------------------------
class TestGetInvalidRole:
    """TC-IT-RPH-005: 不正 role 値で GET → 422。"""

    async def test_get_with_invalid_role_returns_422(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await rp_ctx.client.get(f"/api/empires/{empire['id']}/role-profiles/INVALID_ROLE")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TC-IT-RPH-011: DELETE — 正常系 → 204 (§確定E)
# ---------------------------------------------------------------------------
class TestDeleteExists:
    """TC-IT-RPH-011: 存在する profile → 204 (§確定E / REQ-RP-HTTP-004)。"""

    async def test_delete_returns_204(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        await _upsert_role_profile(rp_ctx, empire["id"], role="DEVELOPER")
        resp = await rp_ctx.client.delete(f"/api/empires/{empire['id']}/role-profiles/DEVELOPER")
        assert resp.status_code == 204

    async def test_delete_then_get_returns_404(self, rp_ctx: RpTestCtx) -> None:
        """DELETE 後に GET で 404（物理削除確認）。"""
        empire = await _create_empire(rp_ctx)
        await _upsert_role_profile(rp_ctx, empire["id"], role="LEADER")
        await rp_ctx.client.delete(f"/api/empires/{empire['id']}/role-profiles/LEADER")
        get_resp = await rp_ctx.client.get(f"/api/empires/{empire['id']}/role-profiles/LEADER")
        assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# TC-IT-RPH-012: DELETE — 不在 → 404 (MSG-RP-HTTP-001)
# ---------------------------------------------------------------------------
class TestDeleteNonexistent:
    """TC-IT-RPH-012: 存在しない role → 404 not_found (MSG-RP-HTTP-001)。"""

    async def test_delete_nonexistent_returns_404(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await rp_ctx.client.delete(f"/api/empires/{empire['id']}/role-profiles/DEVELOPER")
        assert resp.status_code == 404

    async def test_delete_nonexistent_code_is_not_found(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await rp_ctx.client.delete(f"/api/empires/{empire['id']}/role-profiles/DEVELOPER")
        assert resp.json()["error"]["code"] == "not_found"
