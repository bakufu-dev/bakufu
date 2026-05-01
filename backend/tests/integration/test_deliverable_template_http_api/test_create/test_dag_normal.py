"""DeliverableTemplate HTTP API 結合テスト — CREATE 合法 DAG 正常系 (TC-IT-DTH-022).

Covers:
  TC-IT-DTH-022  POST 合法な菱形 DAG（A→B, A→C, B→C）→ 201 (DFS + 経路スタック正常系)

旧 BFS 実装の誤検出（ヘルスバーグ指摘 Critical Defect #1）に対する回帰テスト。
DFS + ancestors（経路スタック）アルゴリズムが合法な菱形 DAG を正しく受容することを検証する。

Issue: #122
"""

from __future__ import annotations

import pytest

from tests.integration.test_deliverable_template_http_api.conftest import DtTestCtx
from tests.integration.test_deliverable_template_http_api.test_create.conftest import (
    _MINIMAL_MARKDOWN_BODY,
    _create_template,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-IT-DTH-022: POST — 合法な菱形 DAG（A→B, A→C, B→C）→ 201 (§確定D)
# ---------------------------------------------------------------------------
class TestCreateDiamondDag:
    """TC-IT-DTH-022: 合法な菱形 DAG（diamond DAG）が 201 で正常登録されること (§確定D).

    セットアップ:
      1. C を作成（composition なし、leaf node）
      2. B を作成（composition = [ref_to_C]）  → B→C (正常)
      3. A を作成（composition = [ref_to_B, ref_to_C]）→ A→B, A→C, B→C (菱形DAG)

    旧 BFS 実装では C が B 経由と A 直接経由の 2 経路で visited に 2 回現れ、
    誤って循環と判定していた（ヘルスバーグ指摘 Critical Defect #1）。
    新 DFS + ancestors（経路スタック）実装では ancestors が現在の DFS 経路のみを
    保持するため、C の再訪問は祖先集合に入らず循環として誤検出されない。
    """

    async def test_diamond_dag_returns_201(self, dt_ctx: DtTestCtx) -> None:
        """A→B, A→C, B→C の菱形 DAG が 201 で登録できること（循環エラーにならないこと）。"""
        # 1. C 作成（leaf）
        c = await _create_template(dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "diamond-C"})
        # 2. B 作成（B→C）
        b = await _create_template(
            dt_ctx,
            {
                **_MINIMAL_MARKDOWN_BODY,
                "name": "diamond-B",
                "composition": [
                    {
                        "template_id": c["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        # 3. A 作成（A→B, A→C → 菱形DAG）
        resp = await dt_ctx.client.post(
            "/api/deliverable-templates",
            json={
                **_MINIMAL_MARKDOWN_BODY,
                "name": "diamond-A",
                "composition": [
                    {
                        "template_id": b["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    },
                    {
                        "template_id": c["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    },
                ],
            },
        )
        assert resp.status_code == 201, (
            f"diamond DAG は合法な DAG であり composition_cycle になってはならない: {resp.text}"
        )

    async def test_diamond_dag_does_not_return_composition_cycle(self, dt_ctx: DtTestCtx) -> None:
        """A→B, A→C, B→C → composition_cycle エラーにならないこと。"""
        c = await _create_template(dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "diamond-C2"})
        b = await _create_template(
            dt_ctx,
            {
                **_MINIMAL_MARKDOWN_BODY,
                "name": "diamond-B2",
                "composition": [
                    {
                        "template_id": c["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        resp = await dt_ctx.client.post(
            "/api/deliverable-templates",
            json={
                **_MINIMAL_MARKDOWN_BODY,
                "name": "diamond-A2",
                "composition": [
                    {
                        "template_id": b["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    },
                    {
                        "template_id": c["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    },
                ],
            },
        )
        # 旧 BFS 実装では "composition_cycle" になっていたが DFS 実装では正常 → 検証
        assert resp.json().get("error", {}).get("code") != "composition_cycle", (
            f"diamond DAG が誤って composition_cycle と判定された: {resp.text}"
        )

    async def test_diamond_dag_response_has_two_composition_refs(self, dt_ctx: DtTestCtx) -> None:
        """A の composition に B と C の 2 つの ref が含まれること。"""
        c = await _create_template(dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "diamond-C3"})
        b = await _create_template(
            dt_ctx,
            {
                **_MINIMAL_MARKDOWN_BODY,
                "name": "diamond-B3",
                "composition": [
                    {
                        "template_id": c["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        resp = await dt_ctx.client.post(
            "/api/deliverable-templates",
            json={
                **_MINIMAL_MARKDOWN_BODY,
                "name": "diamond-A3",
                "composition": [
                    {
                        "template_id": b["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    },
                    {
                        "template_id": c["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    },
                ],
            },
        )
        assert resp.status_code == 201
        composition = resp.json()["composition"]
        assert len(composition) == 2
        template_ids = {ref["template_id"] for ref in composition}
        assert b["id"] in template_ids
        assert c["id"] in template_ids
