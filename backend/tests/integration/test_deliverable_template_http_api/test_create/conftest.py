"""test_create パッケージ共有ヘルパー。

``_MINIMAL_MARKDOWN_BODY`` および ``_create_template`` は
test_basic.py / test_dag.py の両方から参照されるためここで一元定義する。
"""

from __future__ import annotations

from typing import Any

from tests.integration.test_deliverable_template_http_api.conftest import DtTestCtx

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
    body: dict[str, Any] | None = None,
    *,
    assert_201: bool = True,
) -> dict[str, Any]:
    """POST /api/deliverable-templates してパース済み JSON ボディを返す。"""
    payload = body if body is not None else _MINIMAL_MARKDOWN_BODY
    resp = await ctx.client.post("/api/deliverable-templates", json=payload)
    if assert_201:
        assert resp.status_code == 201, f"template creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


__all__ = ["DtTestCtx", "_MINIMAL_MARKDOWN_BODY", "_create_template"]  # noqa: RUF022
