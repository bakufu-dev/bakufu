"""DeliverableTemplate HTTP API 結合テスト — CREATE ref バリデーション系 (TC-IT-DTH-002〜003).

Covers:
  TC-IT-DTH-002  POST composition ref 不在 → 422 ref_not_found (MSG-DT-HTTP-002)
  TC-IT-DTH-003  POST 自己参照循環 → 422 validation_error (MSG-DT-002 domain invariant)

Issue: #122
"""

from __future__ import annotations

import uuid

import pytest

from tests.integration.test_deliverable_template_http_api.conftest import DtTestCtx
from tests.integration.test_deliverable_template_http_api.test_create.conftest import (
    _MINIMAL_MARKDOWN_BODY,
    _create_template,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-IT-DTH-002: POST — composition ref 不在 → 422
# ---------------------------------------------------------------------------
class TestCreateWithNonexistentRef:
    """TC-IT-DTH-002: 存在しない ref → 422 ref_not_found (MSG-DT-HTTP-002)。"""

    async def test_create_with_nonexistent_ref_returns_422(self, dt_ctx: DtTestCtx) -> None:
        unknown_id = str(uuid.uuid4())
        body = {
            **_MINIMAL_MARKDOWN_BODY,
            "composition": [
                {"template_id": unknown_id, "minimum_version": {"major": 1, "minor": 0, "patch": 0}}
            ],
        }
        resp = await dt_ctx.client.post("/api/deliverable-templates", json=body)
        assert resp.status_code == 422

    async def test_create_with_nonexistent_ref_code_is_ref_not_found(
        self, dt_ctx: DtTestCtx
    ) -> None:
        unknown_id = str(uuid.uuid4())
        body = {
            **_MINIMAL_MARKDOWN_BODY,
            "composition": [
                {"template_id": unknown_id, "minimum_version": {"major": 1, "minor": 0, "patch": 0}}
            ],
        }
        resp = await dt_ctx.client.post("/api/deliverable-templates", json=body)
        assert resp.json()["error"]["code"] == "ref_not_found"


# ---------------------------------------------------------------------------
# TC-IT-DTH-003: POST — 自己参照循環 → 422 (domain invariant)
# ---------------------------------------------------------------------------
class TestCreateSelfReference:
    """TC-IT-DTH-003: 自己参照 → domain 不変条件発火 → 422 (MSG-DT-002)。

    自己参照は domain の _validate_composition_no_self_ref で検出される。
    service の _check_dag より前に発火するため code は "validation_error"。
    """

    async def test_create_with_self_reference_returns_422(self, dt_ctx: DtTestCtx) -> None:
        """DB に先に INSERT してから自己参照 PUT を試みる。"""
        # まず template を 1 件作成して id を取得
        created = await _create_template(dt_ctx)
        template_id = created["id"]

        # 同じ id を composition に含む PUT（self ref）
        body = {
            **_MINIMAL_MARKDOWN_BODY,
            "composition": [
                {
                    "template_id": template_id,
                    "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                }
            ],
        }
        # UPDATE リクエストで自己参照を設定 → domain invariant violation
        resp = await dt_ctx.client.put(f"/api/deliverable-templates/{template_id}", json=body)
        assert resp.status_code == 422

    async def test_create_with_self_reference_code_is_validation_error(
        self, dt_ctx: DtTestCtx
    ) -> None:
        created = await _create_template(dt_ctx)
        template_id = created["id"]
        body = {
            **_MINIMAL_MARKDOWN_BODY,
            "composition": [
                {
                    "template_id": template_id,
                    "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                }
            ],
        }
        resp = await dt_ctx.client.put(f"/api/deliverable-templates/{template_id}", json=body)
        assert resp.json()["error"]["code"] == "validation_error"
