"""RoleProfile HTTP API 結合テスト — UPSERT 系 (TC-IT-RPH-006〜010 / 013).

Covers:
  TC-IT-RPH-006  PUT 新規 Upsert → 200 (§確定C / REQ-RP-HTTP-003)
  TC-IT-RPH-007  PUT 2 回 Upsert → 同一 id 保持 (§確定C 冪等性)
  TC-IT-RPH-008  PUT Empire 不在 → 404 (MSG-RP-HTTP-003)
  TC-IT-RPH-009  PUT ref 不在 → 422 ref_not_found (MSG-RP-HTTP-002)
  TC-IT-RPH-010  PUT refs 完全置換 (§確定C)
  TC-IT-RPH-013  PUT role 不正値 → 422

Issue: #122
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.integration.test_role_profile_http_api.conftest import (
    RpTestCtx,
    _create_deliverable_template,
    _create_empire,
)

pytestmark = pytest.mark.asyncio


async def _put_role_profile(
    ctx: RpTestCtx,
    empire_id: str,
    role: str = "DEVELOPER",
    refs: list[dict[str, Any]] | None = None,
) -> Any:
    """PUT /api/empires/{empire_id}/role-profiles/{role}。"""
    body: dict[str, Any] = {"deliverable_template_refs": refs if refs is not None else []}
    return await ctx.client.put(
        f"/api/empires/{empire_id}/role-profiles/{role}",
        json=body,
    )


# ---------------------------------------------------------------------------
# TC-IT-RPH-006: PUT — 新規 Upsert → 200 (§確定C)
# ---------------------------------------------------------------------------
class TestUpsertNew:
    """TC-IT-RPH-006: 初回 PUT → 新規 RoleProfile 作成 (§確定C / REQ-RP-HTTP-003)。"""

    async def test_upsert_creates_new_profile_returns_200(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await _put_role_profile(rp_ctx, empire["id"])
        assert resp.status_code == 200

    async def test_upsert_new_response_has_uuid_id(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await _put_role_profile(rp_ctx, empire["id"])
        parsed = uuid.UUID(resp.json()["id"])
        assert isinstance(parsed, uuid.UUID)

    async def test_upsert_new_response_empire_id_matches(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await _put_role_profile(rp_ctx, empire["id"])
        assert resp.json()["empire_id"] == empire["id"]

    async def test_upsert_new_response_role_matches(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await _put_role_profile(rp_ctx, empire["id"], role="DEVELOPER")
        assert resp.json()["role"] == "DEVELOPER"

    async def test_upsert_new_response_refs_empty(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await _put_role_profile(rp_ctx, empire["id"])
        assert resp.json()["deliverable_template_refs"] == []


# ---------------------------------------------------------------------------
# TC-IT-RPH-007: PUT — 2 回 Upsert で同一 id を保持 (§確定C 冪等性)
# ---------------------------------------------------------------------------
class TestUpsertIdempotency:
    """TC-IT-RPH-007: 同一 empire_id×role で 2 回 PUT → id が変わらない (§確定C)。"""

    async def test_upsert_twice_preserves_same_id(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        first_resp = await _put_role_profile(rp_ctx, empire["id"])
        first_id = first_resp.json()["id"]

        second_resp = await _put_role_profile(rp_ctx, empire["id"])
        second_id = second_resp.json()["id"]

        assert first_id == second_id

    async def test_upsert_twice_both_return_200(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        r1 = await _put_role_profile(rp_ctx, empire["id"])
        r2 = await _put_role_profile(rp_ctx, empire["id"])
        assert r1.status_code == 200
        assert r2.status_code == 200


# ---------------------------------------------------------------------------
# TC-IT-RPH-008: PUT — Empire 不在 → 404 (MSG-RP-HTTP-003)
# ---------------------------------------------------------------------------
class TestUpsertEmpireNotFound:
    """TC-IT-RPH-008: 存在しない empire_id → 404 (MSG-RP-HTTP-003)。"""

    async def test_upsert_with_nonexistent_empire_returns_404(self, rp_ctx: RpTestCtx) -> None:
        unknown_empire_id = str(uuid.uuid4())
        resp = await _put_role_profile(rp_ctx, unknown_empire_id)
        assert resp.status_code == 404

    async def test_upsert_with_nonexistent_empire_code_is_not_found(
        self, rp_ctx: RpTestCtx
    ) -> None:
        unknown_empire_id = str(uuid.uuid4())
        resp = await _put_role_profile(rp_ctx, unknown_empire_id)
        assert resp.json()["error"]["code"] == "not_found"


# ---------------------------------------------------------------------------
# TC-IT-RPH-009: PUT — ref 不在 → 422 ref_not_found (MSG-RP-HTTP-002)
# ---------------------------------------------------------------------------
class TestUpsertRefNotFound:
    """TC-IT-RPH-009: 存在しない template ref → 422 ref_not_found (MSG-RP-HTTP-002)。"""

    async def test_upsert_with_nonexistent_ref_returns_422(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        unknown_template_id = str(uuid.uuid4())
        resp = await _put_role_profile(
            rp_ctx,
            empire["id"],
            refs=[
                {
                    "template_id": unknown_template_id,
                    "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                }
            ],
        )
        assert resp.status_code == 422

    async def test_upsert_with_nonexistent_ref_code_is_ref_not_found(
        self, rp_ctx: RpTestCtx
    ) -> None:
        empire = await _create_empire(rp_ctx)
        unknown_template_id = str(uuid.uuid4())
        resp = await _put_role_profile(
            rp_ctx,
            empire["id"],
            refs=[
                {
                    "template_id": unknown_template_id,
                    "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                }
            ],
        )
        assert resp.json()["error"]["code"] == "ref_not_found"


# ---------------------------------------------------------------------------
# TC-IT-RPH-010: PUT — refs 完全置換 (§確定C)
# ---------------------------------------------------------------------------
class TestUpsertRefsReplacement:
    """TC-IT-RPH-010: 2 件 refs → 空 refs で PUT → 完全置換 (§確定C)。"""

    async def test_upsert_replaces_all_refs(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        t1 = await _create_deliverable_template(rp_ctx, "ref-t1")
        t2 = await _create_deliverable_template(rp_ctx, "ref-t2")

        # 1 回目: 2 件 refs
        await _put_role_profile(
            rp_ctx,
            empire["id"],
            refs=[
                {"template_id": t1["id"], "minimum_version": {"major": 1, "minor": 0, "patch": 0}},
                {"template_id": t2["id"], "minimum_version": {"major": 1, "minor": 0, "patch": 0}},
            ],
        )

        # 2 回目: refs を空に置換
        resp = await _put_role_profile(rp_ctx, empire["id"], refs=[])
        assert resp.status_code == 200
        assert resp.json()["deliverable_template_refs"] == []


# ---------------------------------------------------------------------------
# TC-IT-RPH-013: PUT — role 不正値 → 422
# ---------------------------------------------------------------------------
class TestUpsertInvalidRole:
    """TC-IT-RPH-013: 不正 role 値で PUT → 422。"""

    async def test_upsert_with_invalid_role_returns_422(self, rp_ctx: RpTestCtx) -> None:
        empire = await _create_empire(rp_ctx)
        resp = await _put_role_profile(rp_ctx, empire["id"], role="INVALID_ROLE")
        assert resp.status_code == 422
