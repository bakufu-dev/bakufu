"""DeliverableTemplate HTTP API 結合テスト — CREATE DAG 検証系 (TC-IT-DTH-002〜005 / 022).

Covers:
  TC-IT-DTH-002  POST composition ref 不在 → 422 ref_not_found (MSG-DT-HTTP-002)
  TC-IT-DTH-003  POST 自己参照循環 → 422 validation_error (MSG-DT-002 domain invariant)
  TC-IT-DTH-004  POST 推移的循環 A→B→A → 422 composition_cycle / transitive_cycle
  TC-IT-DTH-005  POST DAG 深度ガード 11 → 422 composition_cycle / depth_limit (MSG-DT-HTTP-003b)
  TC-IT-DTH-022  POST 合法な菱形 DAG（A→B, A→C, B→C）→ 201 (DFS + 経路スタック正常系)

セキュリティ注記:
  composition_cycle エラーレスポンスは cycle_path を含まない（Tabriz 指摘 / OWASP A05 対応）。
  cycle_path は内部 UUID 列挙を引き起こす可能性があるため最小情報開示原則に基づき除外済み。

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
