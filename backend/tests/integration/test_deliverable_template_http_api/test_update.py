"""DeliverableTemplate HTTP API 結合テスト — UPDATE 系 (TC-IT-DTH-012〜015).

Covers:
  TC-IT-DTH-012  PUT version 同一 → 200 (§確定B / REQ-DT-HTTP-004)
  TC-IT-DTH-013  PUT version 昇格 → 200 (§確定B / REQ-DT-HTTP-004)
  TC-IT-DTH-014  PUT version 降格 → 422 version_downgrade (§確定B / MSG-DT-HTTP-004)
  TC-IT-DTH-015  PUT 不在 → 404 not_found (MSG-DT-HTTP-001)

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


async def _create_template(
    ctx: DtTestCtx,
    version: dict[str, int] | None = None,
    name: str = "update-test",
) -> dict[str, Any]:
    body = {**_MINIMAL_MARKDOWN_BODY, "name": name}
    if version is not None:
        body["version"] = version
    resp = await ctx.client.post("/api/deliverable-templates", json=body)
    assert resp.status_code == 201, f"creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


async def _put_template(
    ctx: DtTestCtx,
    template_id: str,
    version: dict[str, int],
    name: str = "update-test",
) -> Any:
    body = {**_MINIMAL_MARKDOWN_BODY, "name": name, "version": version}
    return await ctx.client.put(f"/api/deliverable-templates/{template_id}", json=body)


# ---------------------------------------------------------------------------
# TC-IT-DTH-012: PUT — version 同一 → 200 (§確定B)
# ---------------------------------------------------------------------------
class TestUpdateSameVersion:
    """TC-IT-DTH-012: version 同一で PUT → 200 (§確定B / REQ-DT-HTTP-004)。"""

    async def test_update_with_same_version_returns_200(self, dt_ctx: DtTestCtx) -> None:
        created = await _create_template(dt_ctx, name="same-ver-test")
        resp = await _put_template(
            dt_ctx,
            created["id"],
            version={"major": 1, "minor": 0, "patch": 0},
            name="same-ver-test",
        )
        assert resp.status_code == 200

    async def test_update_same_version_response_version_unchanged(
        self, dt_ctx: DtTestCtx
    ) -> None:
        created = await _create_template(dt_ctx, name="same-ver-test2")
        resp = await _put_template(
            dt_ctx,
            created["id"],
            version={"major": 1, "minor": 0, "patch": 0},
            name="same-ver-test2",
        )
        assert resp.json()["version"]["major"] == 1
        assert resp.json()["version"]["minor"] == 0
        assert resp.json()["version"]["patch"] == 0


# ---------------------------------------------------------------------------
# TC-IT-DTH-013: PUT — version 昇格 → 200 (§確定B)
# ---------------------------------------------------------------------------
class TestUpdateHigherVersion:
    """TC-IT-DTH-013: version 昇格で PUT → 200 (§確定B / REQ-DT-HTTP-004)。"""

    async def test_update_with_higher_version_returns_200(self, dt_ctx: DtTestCtx) -> None:
        created = await _create_template(dt_ctx, name="higher-ver-test")
        resp = await _put_template(
            dt_ctx,
            created["id"],
            version={"major": 2, "minor": 0, "patch": 0},
            name="higher-ver-test",
        )
        assert resp.status_code == 200

    async def test_update_higher_version_response_version_updated(
        self, dt_ctx: DtTestCtx
    ) -> None:
        created = await _create_template(dt_ctx, name="higher-ver-test2")
        resp = await _put_template(
            dt_ctx,
            created["id"],
            version={"major": 2, "minor": 0, "patch": 0},
            name="higher-ver-test2",
        )
        assert resp.json()["version"]["major"] == 2


# ---------------------------------------------------------------------------
# TC-IT-DTH-014: PUT — version 降格 → 422 version_downgrade (§確定B)
# ---------------------------------------------------------------------------
class TestUpdateLowerVersion:
    """TC-IT-DTH-014: version 降格で PUT → 422 version_downgrade (§確定B / MSG-DT-HTTP-004)。"""

    async def test_update_with_lower_version_returns_422(self, dt_ctx: DtTestCtx) -> None:
        # まず version 2.0.0 に昇格
        created = await _create_template(dt_ctx, name="lower-ver-test")
        await _put_template(
            dt_ctx,
            created["id"],
            version={"major": 2, "minor": 0, "patch": 0},
            name="lower-ver-test",
        )
        # version 1.0.0 に降格 → 422
        resp = await _put_template(
            dt_ctx,
            created["id"],
            version={"major": 1, "minor": 0, "patch": 0},
            name="lower-ver-test",
        )
        assert resp.status_code == 422

    async def test_update_lower_version_code_is_version_downgrade(
        self, dt_ctx: DtTestCtx
    ) -> None:
        created = await _create_template(dt_ctx, name="lower-ver-test2")
        await _put_template(
            dt_ctx,
            created["id"],
            version={"major": 2, "minor": 0, "patch": 0},
            name="lower-ver-test2",
        )
        resp = await _put_template(
            dt_ctx,
            created["id"],
            version={"major": 1, "minor": 0, "patch": 0},
            name="lower-ver-test2",
        )
        assert resp.json()["error"]["code"] == "version_downgrade"


# ---------------------------------------------------------------------------
# TC-IT-DTH-015: PUT — 不在 → 404 (MSG-DT-HTTP-001)
# ---------------------------------------------------------------------------
class TestUpdateNonexistent:
    """TC-IT-DTH-015: 存在しない UUID で PUT → 404 not_found (MSG-DT-HTTP-001)。"""

    async def test_update_nonexistent_returns_404(self, dt_ctx: DtTestCtx) -> None:
        unknown_id = str(uuid.uuid4())
        resp = await _put_template(
            dt_ctx,
            unknown_id,
            version={"major": 1, "minor": 0, "patch": 0},
        )
        assert resp.status_code == 404

    async def test_update_nonexistent_code_is_not_found(self, dt_ctx: DtTestCtx) -> None:
        unknown_id = str(uuid.uuid4())
        resp = await _put_template(
            dt_ctx,
            unknown_id,
            version={"major": 1, "minor": 0, "patch": 0},
        )
        assert resp.json()["error"]["code"] == "not_found"
