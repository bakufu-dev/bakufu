"""DeliverableTemplate HTTP API 結合テスト — CREATE 循環検出系 (TC-IT-DTH-004〜005).

Covers:
  TC-IT-DTH-004  POST 推移的循環 A→B→A → 422 composition_cycle / transitive_cycle
  TC-IT-DTH-005  POST DAG 深度ガード 11 → 422 composition_cycle / depth_limit (MSG-DT-HTTP-003b)

セキュリティ注記:
  composition_cycle エラーレスポンスは cycle_path を含まない（Tabriz 指摘 / OWASP A05 対応）。
  cycle_path は内部 UUID 列挙を引き起こす可能性があるため最小情報開示原則に基づき除外済み。

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
# TC-IT-DTH-004: POST — 推移的循環 A→B→A → 422 transitive_cycle
# ---------------------------------------------------------------------------
class TestCreateTransitiveCycle:
    """TC-IT-DTH-004: 推移的循環参照 → 422 composition_cycle / transitive_cycle (MSG-DT-HTTP-003a).

    セットアップ:
      1. B を作成（composition なし）
      2. A を作成（composition = [ref_to_B]）  → A→B (正常)
      3. B を PUT（composition = [ref_to_A]）  → B→A となり A→B→A 循環 → 422
    """

    async def test_create_with_transitive_cycle_returns_422(self, dt_ctx: DtTestCtx) -> None:
        # 1. B 作成
        b = await _create_template(dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "template-B"})
        # 2. A 作成（B を参照）
        a = await _create_template(
            dt_ctx,
            {
                **_MINIMAL_MARKDOWN_BODY,
                "name": "template-A",
                "composition": [
                    {
                        "template_id": b["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        # 3. B を PUT → A を参照（A→B→A 循環）
        resp = await dt_ctx.client.put(
            f"/api/deliverable-templates/{b['id']}",
            json={
                **_MINIMAL_MARKDOWN_BODY,
                "name": "template-B",
                "composition": [
                    {
                        "template_id": a["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        assert resp.status_code == 422

    async def test_transitive_cycle_code_is_composition_cycle(self, dt_ctx: DtTestCtx) -> None:
        b = await _create_template(dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "template-B2"})
        a = await _create_template(
            dt_ctx,
            {
                **_MINIMAL_MARKDOWN_BODY,
                "name": "template-A2",
                "composition": [
                    {
                        "template_id": b["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        resp = await dt_ctx.client.put(
            f"/api/deliverable-templates/{b['id']}",
            json={
                **_MINIMAL_MARKDOWN_BODY,
                "name": "template-B2",
                "composition": [
                    {
                        "template_id": a["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        assert resp.json()["error"]["code"] == "composition_cycle"

    async def test_transitive_cycle_reason_is_transitive_cycle(self, dt_ctx: DtTestCtx) -> None:
        b = await _create_template(dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "template-B3"})
        a = await _create_template(
            dt_ctx,
            {
                **_MINIMAL_MARKDOWN_BODY,
                "name": "template-A3",
                "composition": [
                    {
                        "template_id": b["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        resp = await dt_ctx.client.put(
            f"/api/deliverable-templates/{b['id']}",
            json={
                **_MINIMAL_MARKDOWN_BODY,
                "name": "template-B3",
                "composition": [
                    {
                        "template_id": a["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        assert resp.json()["error"]["detail"]["reason"] == "transitive_cycle"

    async def test_transitive_cycle_no_cycle_path_in_response(self, dt_ctx: DtTestCtx) -> None:
        """cycle_path はセキュリティ上レスポンスに含まれないこと（OWASP A05 / Tabriz 指摘対応）。

        旧実装では cycle_path に内部 UUID を含んでいたが、最小情報開示原則に基づき除外された。
        """
        b = await _create_template(dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "template-B4"})
        a = await _create_template(
            dt_ctx,
            {
                **_MINIMAL_MARKDOWN_BODY,
                "name": "template-A4",
                "composition": [
                    {
                        "template_id": b["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        resp = await dt_ctx.client.put(
            f"/api/deliverable-templates/{b['id']}",
            json={
                **_MINIMAL_MARKDOWN_BODY,
                "name": "template-B4",
                "composition": [
                    {
                        "template_id": a["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        # cycle_path はレスポンス detail に含まれないこと（最小情報開示原則）
        assert "cycle_path" not in resp.json()["error"]["detail"]


# ---------------------------------------------------------------------------
# TC-IT-DTH-005: POST — DAG 深度ガード → 422 depth_limit (§確定D)
# ---------------------------------------------------------------------------
class TestCreateDagDepthLimit:
    """TC-IT-DTH-005: composition チェーン深度 11 → 422 depth_limit (MSG-DT-HTTP-003b).

    T1(leaf) → T2 → ... → T11 の 11 段チェーンを構築し、
    T12 が T11 を参照すると depth 11 > 10 で depth_limit。
    """

    async def test_create_dag_depth_limit_returns_422(self, dt_ctx: DtTestCtx) -> None:
        """深度 11 の composition チェーン構築 → 422。"""
        # T1 (leaf)
        prev = await _create_template(dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "depth-chain-T1"})
        # T2〜T11: 各 T_i が T_{i-1} を参照（10段のチェーン: T11→T10→...→T1）
        for i in range(2, 12):
            prev = await _create_template(
                dt_ctx,
                {
                    **_MINIMAL_MARKDOWN_BODY,
                    "name": f"depth-chain-T{i}",
                    "composition": [
                        {
                            "template_id": prev["id"],
                            "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                        }
                    ],
                },
            )
        # T12 が T11 を参照 → depth 11 を走査 → 422
        resp = await dt_ctx.client.post(
            "/api/deliverable-templates",
            json={
                **_MINIMAL_MARKDOWN_BODY,
                "name": "depth-chain-T12",
                "composition": [
                    {
                        "template_id": prev["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        assert resp.status_code == 422

    async def test_create_dag_depth_limit_code_is_composition_cycle(
        self, dt_ctx: DtTestCtx
    ) -> None:
        prev = await _create_template(dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "dl-chain-T1"})
        for i in range(2, 12):
            prev = await _create_template(
                dt_ctx,
                {
                    **_MINIMAL_MARKDOWN_BODY,
                    "name": f"dl-chain-T{i}",
                    "composition": [
                        {
                            "template_id": prev["id"],
                            "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                        }
                    ],
                },
            )
        resp = await dt_ctx.client.post(
            "/api/deliverable-templates",
            json={
                **_MINIMAL_MARKDOWN_BODY,
                "name": "dl-chain-T12",
                "composition": [
                    {
                        "template_id": prev["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        assert resp.json()["error"]["code"] == "composition_cycle"

    async def test_create_dag_depth_limit_reason_is_depth_limit(self, dt_ctx: DtTestCtx) -> None:
        prev = await _create_template(dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "dr-chain-T1"})
        for i in range(2, 12):
            prev = await _create_template(
                dt_ctx,
                {
                    **_MINIMAL_MARKDOWN_BODY,
                    "name": f"dr-chain-T{i}",
                    "composition": [
                        {
                            "template_id": prev["id"],
                            "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                        }
                    ],
                },
            )
        resp = await dt_ctx.client.post(
            "/api/deliverable-templates",
            json={
                **_MINIMAL_MARKDOWN_BODY,
                "name": "dr-chain-T12",
                "composition": [
                    {
                        "template_id": prev["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        assert resp.json()["error"]["detail"]["reason"] == "depth_limit"

    async def test_create_dag_depth_limit_no_cycle_path_in_response(
        self, dt_ctx: DtTestCtx
    ) -> None:
        """depth_limit レスポンスにも cycle_path は含まれないこと（OWASP A05）。"""
        prev = await _create_template(dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "de-chain-T1"})
        for i in range(2, 12):
            prev = await _create_template(
                dt_ctx,
                {
                    **_MINIMAL_MARKDOWN_BODY,
                    "name": f"de-chain-T{i}",
                    "composition": [
                        {
                            "template_id": prev["id"],
                            "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                        }
                    ],
                },
            )
        resp = await dt_ctx.client.post(
            "/api/deliverable-templates",
            json={
                **_MINIMAL_MARKDOWN_BODY,
                "name": "de-chain-T12",
                "composition": [
                    {
                        "template_id": prev["id"],
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            },
        )
        # cycle_path はレスポンス detail に含まれないこと（最小情報開示原則）
        assert "cycle_path" not in resp.json()["error"]["detail"]
