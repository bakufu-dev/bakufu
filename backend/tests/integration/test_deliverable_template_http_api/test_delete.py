"""DeliverableTemplate HTTP API 結合テスト — DELETE 系 (TC-IT-DTH-016〜017).

Covers:
  TC-IT-DTH-016  DELETE 正常系 → 204 No Content + GET で 404 (§確定E / REQ-DT-HTTP-005)
  TC-IT-DTH-017  DELETE 不在 → 404 not_found (MSG-DT-HTTP-001)

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


async def _create_template(ctx: DtTestCtx, name: str = "delete-test") -> dict[str, Any]:
    body = {**_MINIMAL_MARKDOWN_BODY, "name": name}
    resp = await ctx.client.post("/api/deliverable-templates", json=body)
    assert resp.status_code == 201, f"creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# TC-IT-DTH-016: DELETE — 正常系 → 204 (§確定E)
# ---------------------------------------------------------------------------
class TestDeleteExists:
    """TC-IT-DTH-016: 存在する id → 204 No Content (§確定E / REQ-DT-HTTP-005)。"""

    async def test_delete_returns_204(self, dt_ctx: DtTestCtx) -> None:
        created = await _create_template(dt_ctx, "delete-me")
        resp = await dt_ctx.client.delete(f"/api/deliverable-templates/{created['id']}")
        assert resp.status_code == 204

    async def test_delete_then_get_returns_404(self, dt_ctx: DtTestCtx) -> None:
        """DELETE 後に GET で 404 となること（物理削除確認）。"""
        created = await _create_template(dt_ctx, "delete-me-2")
        await dt_ctx.client.delete(f"/api/deliverable-templates/{created['id']}")
        get_resp = await dt_ctx.client.get(f"/api/deliverable-templates/{created['id']}")
        assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# TC-IT-DTH-017: DELETE — 不在 → 404 (MSG-DT-HTTP-001)
# ---------------------------------------------------------------------------
class TestDeleteNonexistent:
    """TC-IT-DTH-017: 存在しない UUID で DELETE → 404 not_found (MSG-DT-HTTP-001)。"""

    async def test_delete_nonexistent_returns_404(self, dt_ctx: DtTestCtx) -> None:
        unknown_id = str(uuid.uuid4())
        resp = await dt_ctx.client.delete(f"/api/deliverable-templates/{unknown_id}")
        assert resp.status_code == 404

    async def test_delete_nonexistent_code_is_not_found(self, dt_ctx: DtTestCtx) -> None:
        unknown_id = str(uuid.uuid4())
        resp = await dt_ctx.client.delete(f"/api/deliverable-templates/{unknown_id}")
        assert resp.json()["error"]["code"] == "not_found"
