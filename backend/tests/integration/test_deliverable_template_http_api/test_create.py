"""DeliverableTemplate HTTP API 結合テスト — CREATE 系 (TC-IT-DTH-001〜006 / 018 / 019 / 021).

Covers:
  TC-IT-DTH-001  POST /api/deliverable-templates → 201 全フィールド確認 (REQ-DT-HTTP-001)
  TC-IT-DTH-002  POST composition ref 不在 → 422 ref_not_found (MSG-DT-HTTP-002)
  TC-IT-DTH-003  POST 自己参照循環 → 422 validation_error (MSG-DT-002 domain invariant)
  TC-IT-DTH-004  POST 推移的循環 A→B→A → 422 composition_cycle / transitive_cycle (MSG-DT-HTTP-003a)
  TC-IT-DTH-005  POST DAG 深度ガード 11 → 422 composition_cycle / depth_limit (MSG-DT-HTTP-003b)
  TC-IT-DTH-006  POST name 空文字 → 422 Pydantic validation
  TC-IT-DTH-018  POST JSON_SCHEMA type → schema が dict で返却 (§確定I)
  TC-IT-DTH-019  POST AcceptanceCriterion id 省略 → UUID 自動生成 (§確定H)
  TC-IT-DTH-021  POST acceptance_criteria id 重複 → 422 domain invariant (§確定H)

Issue: #122
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.integration.test_deliverable_template_http_api.conftest import DtTestCtx

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# ヘルパ
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# TC-IT-DTH-001: POST 正常系
# ---------------------------------------------------------------------------
class TestCreateTemplate:
    """TC-IT-DTH-001: POST /api/deliverable-templates → 201 (REQ-DT-HTTP-001)。"""

    async def test_create_returns_201(self, dt_ctx: DtTestCtx) -> None:
        resp = await dt_ctx.client.post("/api/deliverable-templates", json=_MINIMAL_MARKDOWN_BODY)
        assert resp.status_code == 201

    async def test_create_response_id_is_uuid_string(self, dt_ctx: DtTestCtx) -> None:
        body = await _create_template(dt_ctx)
        # UUID 形式であることを uuid.UUID でパース確認
        parsed = uuid.UUID(body["id"])
        assert isinstance(parsed, uuid.UUID)

    async def test_create_response_name_matches(self, dt_ctx: DtTestCtx) -> None:
        body = await _create_template(dt_ctx)
        assert body["name"] == _MINIMAL_MARKDOWN_BODY["name"]

    async def test_create_response_type_matches(self, dt_ctx: DtTestCtx) -> None:
        body = await _create_template(dt_ctx)
        assert body["type"] == "MARKDOWN"

    async def test_create_response_version_matches(self, dt_ctx: DtTestCtx) -> None:
        body = await _create_template(dt_ctx)
        assert body["version"] == {"major": 1, "minor": 0, "patch": 0}

    async def test_create_response_acceptance_criteria_empty(self, dt_ctx: DtTestCtx) -> None:
        body = await _create_template(dt_ctx)
        assert body["acceptance_criteria"] == []

    async def test_create_response_composition_empty(self, dt_ctx: DtTestCtx) -> None:
        body = await _create_template(dt_ctx)
        assert body["composition"] == []

    async def test_create_round_trip_get_returns_same_id(self, dt_ctx: DtTestCtx) -> None:
        """ラウンドトリップ: POST → GET で同一 id が確認できる。"""
        created = await _create_template(dt_ctx)
        get_resp = await dt_ctx.client.get(f"/api/deliverable-templates/{created['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == created["id"]


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
        """DB に先に INSERT してから自己参照 POST を試みる。"""
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
    """TC-IT-DTH-004: 推移的循環参照 → 422 composition_cycle / transitive_cycle (MSG-DT-HTTP-003a)。

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

    async def test_transitive_cycle_cycle_path_contains_both_uuids(
        self, dt_ctx: DtTestCtx
    ) -> None:
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
        cycle_path = resp.json()["error"]["detail"]["cycle_path"]
        assert a["id"] in cycle_path or b["id"] in cycle_path


# ---------------------------------------------------------------------------
# TC-IT-DTH-005: POST — DAG 深度ガード → 422 depth_limit (§確定D)
# ---------------------------------------------------------------------------
class TestCreateDagDepthLimit:
    """TC-IT-DTH-005: composition チェーン深度 11 → 422 depth_limit (MSG-DT-HTTP-003b)。

    T1(leaf) → T2 → ... → T11 の 11 段チェーンを構築し、
    T12 が T11 を参照すると depth 11 > 10 で depth_limit。
    """

    async def test_create_dag_depth_limit_returns_422(self, dt_ctx: DtTestCtx) -> None:
        """深度 11 の composition チェーン構築 → 422。"""
        # T1 (leaf)
        prev = await _create_template(
            dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "depth-chain-T1"}
        )
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
        prev = await _create_template(
            dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "dl-chain-T1"}
        )
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

    async def test_create_dag_depth_limit_reason_is_depth_limit(
        self, dt_ctx: DtTestCtx
    ) -> None:
        prev = await _create_template(
            dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "dr-chain-T1"}
        )
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

    async def test_create_dag_depth_limit_cycle_path_is_empty(
        self, dt_ctx: DtTestCtx
    ) -> None:
        prev = await _create_template(
            dt_ctx, {**_MINIMAL_MARKDOWN_BODY, "name": "de-chain-T1"}
        )
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
        assert resp.json()["error"]["detail"]["cycle_path"] == []


# ---------------------------------------------------------------------------
# TC-IT-DTH-006: POST — name 空文字 → 422
# ---------------------------------------------------------------------------
class TestCreateInvalidName:
    """TC-IT-DTH-006: name 空文字 → 422 Pydantic バリデーション。"""

    async def test_create_with_empty_name_returns_422(self, dt_ctx: DtTestCtx) -> None:
        body = {**_MINIMAL_MARKDOWN_BODY, "name": ""}
        resp = await dt_ctx.client.post("/api/deliverable-templates", json=body)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TC-IT-DTH-018: POST — JSON_SCHEMA type → schema が dict で返却 (§確定I)
# ---------------------------------------------------------------------------
class TestCreateJsonSchemaType:
    """TC-IT-DTH-018: type=JSON_SCHEMA → schema レスポンスが dict (§確定I)。"""

    async def test_create_json_schema_type_returns_dict_schema(
        self, dt_ctx: DtTestCtx
    ) -> None:
        """JSON_SCHEMA type で dict schema を POST → レスポンスの schema が dict。"""
        from bakufu.domain.deliverable_template.deliverable_template import DeliverableTemplate

        from tests.factories.deliverable_template import ValidStubValidator

        # テスト用 validator を注入（Fail Secure 回避）
        original_validator = DeliverableTemplate._validator
        try:
            DeliverableTemplate._validator = ValidStubValidator()
            body = {
                **_MINIMAL_MARKDOWN_BODY,
                "type": "JSON_SCHEMA",
                "schema": {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object"},
            }
            resp = await dt_ctx.client.post("/api/deliverable-templates", json=body)
            assert resp.status_code == 201
            assert isinstance(resp.json()["schema"], dict)
        finally:
            DeliverableTemplate._validator = original_validator


# ---------------------------------------------------------------------------
# TC-IT-DTH-019: POST — AcceptanceCriterion id 省略 → UUID 自動生成 (§確定H)
# ---------------------------------------------------------------------------
class TestCreateWithOmittedAcId:
    """TC-IT-DTH-019: acceptance_criteria.id 省略 → UUID 自動生成 (§確定H)。"""

    async def test_create_with_omitted_ac_id_generates_uuid(self, dt_ctx: DtTestCtx) -> None:
        body = {
            **_MINIMAL_MARKDOWN_BODY,
            "acceptance_criteria": [
                {"description": "条件1", "required": True},
            ],
        }
        resp = await dt_ctx.client.post("/api/deliverable-templates", json=body)
        assert resp.status_code == 201
        ac_id = resp.json()["acceptance_criteria"][0]["id"]
        # UUID 形式であることを確認
        parsed = uuid.UUID(ac_id)
        assert isinstance(parsed, uuid.UUID)


# ---------------------------------------------------------------------------
# TC-IT-DTH-021: POST — acceptance_criteria id 重複 → 422 (§確定H)
# ---------------------------------------------------------------------------
class TestCreateWithDuplicateAcId:
    """TC-IT-DTH-021: acceptance_criteria 内 id 重複 → 422 domain invariant (§確定H)。"""

    async def test_create_with_duplicate_ac_id_returns_422(self, dt_ctx: DtTestCtx) -> None:
        dup_id = str(uuid.uuid4())
        body = {
            **_MINIMAL_MARKDOWN_BODY,
            "acceptance_criteria": [
                {"id": dup_id, "description": "条件1", "required": True},
                {"id": dup_id, "description": "条件2", "required": True},
            ],
        }
        resp = await dt_ctx.client.post("/api/deliverable-templates", json=body)
        assert resp.status_code == 422

    async def test_create_with_duplicate_ac_id_code_is_validation_error(
        self, dt_ctx: DtTestCtx
    ) -> None:
        dup_id = str(uuid.uuid4())
        body = {
            **_MINIMAL_MARKDOWN_BODY,
            "acceptance_criteria": [
                {"id": dup_id, "description": "条件1", "required": True},
                {"id": dup_id, "description": "条件2", "required": True},
            ],
        }
        resp = await dt_ctx.client.post("/api/deliverable-templates", json=body)
        assert resp.json()["error"]["code"] == "validation_error"
