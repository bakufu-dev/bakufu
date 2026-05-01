"""DeliverableTemplate HTTP API 結合テスト — READ 系 (TC-IT-DTH-007〜011 / 020).

Covers:
  TC-IT-DTH-007  GET /api/deliverable-templates 空 → 200 {items:[], total:0} (REQ-DT-HTTP-002)
  TC-IT-DTH-008  GET /api/deliverable-templates 複数件 → name 昇順 (REQ-DT-HTTP-002)
  TC-IT-DTH-009  GET /api/deliverable-templates/{id} 正常系 → 200 (REQ-DT-HTTP-003)
  TC-IT-DTH-010  GET /api/deliverable-templates/{id} 不在 → 404 not_found (MSG-DT-HTTP-001)
  TC-IT-DTH-011  GET /api/deliverable-templates/{id} UUID 形式不正 → 422
  TC-IT-DTH-020  エラーレスポンスフォーマット確認 (§確定G)

Issue: #122
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.integration.test_deliverable_template_http_api.conftest import DtTestCtx

pytestmark = pytest.mark.asyncio

_MINIMAL_MARKDOWN_BODY: dict[str, Any] = {
    "name": "テストテンプレート",
    "description": "説明",
    "type": "MARKDOWN",
    "schema": "## ガイドライン",
    "version": {"major": 1, "minor": 0, "patch": 0},
    "acceptance_criteria": [],
    "composition": [],
}


async def _create_template(ctx: DtTestCtx, name: str = "テストテンプレート") -> dict[str, Any]:
    body = {**_MINIMAL_MARKDOWN_BODY, "name": name}
    resp = await ctx.client.post("/api/deliverable-templates", json=body)
    assert resp.status_code == 201, f"creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# TC-IT-DTH-007: GET /api/deliverable-templates — 空リスト
# ---------------------------------------------------------------------------
class TestListEmpty:
    """TC-IT-DTH-007: DB 空 → items:[], total:0 (REQ-DT-HTTP-002)。"""

    async def test_list_returns_200(self, dt_ctx: DtTestCtx) -> None:
        resp = await dt_ctx.client.get("/api/deliverable-templates")
        assert resp.status_code == 200

    async def test_list_returns_empty_items(self, dt_ctx: DtTestCtx) -> None:
        resp = await dt_ctx.client.get("/api/deliverable-templates")
        assert resp.json()["items"] == []

    async def test_list_returns_zero_total(self, dt_ctx: DtTestCtx) -> None:
        resp = await dt_ctx.client.get("/api/deliverable-templates")
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# TC-IT-DTH-008: GET /api/deliverable-templates — 複数件 name 昇順
# ---------------------------------------------------------------------------
class TestListSorted:
    """TC-IT-DTH-008: 複数件 → name ASC 順に返却 (REQ-DT-HTTP-002)。"""

    async def test_list_returns_items_sorted_by_name_asc(self, dt_ctx: DtTestCtx) -> None:
        # 順不同で POST
        await _create_template(dt_ctx, "Z-template")
        await _create_template(dt_ctx, "A-template")
        await _create_template(dt_ctx, "M-template")

        resp = await dt_ctx.client.get("/api/deliverable-templates")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 3
        assert items[0]["name"] == "A-template"
        assert items[1]["name"] == "M-template"
        assert items[2]["name"] == "Z-template"

    async def test_list_returns_total_matching_count(self, dt_ctx: DtTestCtx) -> None:
        await _create_template(dt_ctx, "Z-t2")
        await _create_template(dt_ctx, "A-t2")
        resp = await dt_ctx.client.get("/api/deliverable-templates")
        assert resp.json()["total"] == 2


# ---------------------------------------------------------------------------
# TC-IT-DTH-009: GET /api/deliverable-templates/{id} — 正常系
# ---------------------------------------------------------------------------
class TestGetSingle:
    """TC-IT-DTH-009: 存在する id → 200 フィールド一致 (REQ-DT-HTTP-003)。"""

    async def test_get_returns_200(self, dt_ctx: DtTestCtx) -> None:
        created = await _create_template(dt_ctx)
        resp = await dt_ctx.client.get(f"/api/deliverable-templates/{created['id']}")
        assert resp.status_code == 200

    async def test_get_response_id_matches(self, dt_ctx: DtTestCtx) -> None:
        created = await _create_template(dt_ctx)
        resp = await dt_ctx.client.get(f"/api/deliverable-templates/{created['id']}")
        assert resp.json()["id"] == created["id"]

    async def test_get_response_name_matches(self, dt_ctx: DtTestCtx) -> None:
        created = await _create_template(dt_ctx, "get-test-template")
        resp = await dt_ctx.client.get(f"/api/deliverable-templates/{created['id']}")
        assert resp.json()["name"] == "get-test-template"

    async def test_get_response_version_matches(self, dt_ctx: DtTestCtx) -> None:
        created = await _create_template(dt_ctx)
        resp = await dt_ctx.client.get(f"/api/deliverable-templates/{created['id']}")
        assert resp.json()["version"] == {"major": 1, "minor": 0, "patch": 0}


# ---------------------------------------------------------------------------
# TC-IT-DTH-010: GET — 不在 → 404
# ---------------------------------------------------------------------------
class TestGetNonexistent:
    """TC-IT-DTH-010: 存在しない UUID → 404 not_found (MSG-DT-HTTP-001)。"""

    async def test_get_nonexistent_returns_404(self, dt_ctx: DtTestCtx) -> None:
        unknown_id = str(uuid.uuid4())
        resp = await dt_ctx.client.get(f"/api/deliverable-templates/{unknown_id}")
        assert resp.status_code == 404

    async def test_get_nonexistent_code_is_not_found(self, dt_ctx: DtTestCtx) -> None:
        unknown_id = str(uuid.uuid4())
        resp = await dt_ctx.client.get(f"/api/deliverable-templates/{unknown_id}")
        assert resp.json()["error"]["code"] == "not_found"


# ---------------------------------------------------------------------------
# TC-IT-DTH-011: GET — UUID 形式不正 → 422
# ---------------------------------------------------------------------------
class TestGetInvalidUuid:
    """TC-IT-DTH-011: UUID 形式でない path parameter → 422。"""

    async def test_get_with_invalid_uuid_returns_422(self, dt_ctx: DtTestCtx) -> None:
        resp = await dt_ctx.client.get("/api/deliverable-templates/not-a-uuid")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TC-IT-DTH-020: エラーレスポンスフォーマット確認 (§確定G)
# ---------------------------------------------------------------------------
class TestErrorResponseFormat:
    """TC-IT-DTH-020: 404 レスポンスが §確定G フォーマット準拠。スタックトレース非含。"""

    async def test_error_response_format_matches_confirmed_g(self, dt_ctx: DtTestCtx) -> None:
        unknown_id = str(uuid.uuid4())
        resp = await dt_ctx.client.get(f"/api/deliverable-templates/{unknown_id}")
        body = resp.json()
        # {"error": {"code": str, "message": str}} 構造
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert isinstance(body["error"]["code"], str)
        assert isinstance(body["error"]["message"], str)

    async def test_error_response_does_not_contain_traceback(self, dt_ctx: DtTestCtx) -> None:
        unknown_id = str(uuid.uuid4())
        resp = await dt_ctx.client.get(f"/api/deliverable-templates/{unknown_id}")
        body_text = resp.text
        assert "Traceback" not in body_text
        assert "traceback" not in body_text
