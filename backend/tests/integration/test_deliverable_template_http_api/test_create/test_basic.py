"""DeliverableTemplate HTTP API 結合テスト — CREATE 基本系 (TC-IT-DTH-001 / 006 / 018 / 019 / 021).

Covers:
  TC-IT-DTH-001  POST /api/deliverable-templates → 201 全フィールド確認 (REQ-DT-HTTP-001)
  TC-IT-DTH-006  POST name 空文字 → 422 Pydantic validation
  TC-IT-DTH-018  POST JSON_SCHEMA type → schema が dict で返却 (§確定I)
  TC-IT-DTH-019  POST AcceptanceCriterion id 省略 → UUID 自動生成 (§確定H)
  TC-IT-DTH-021  POST acceptance_criteria id 重複 → 422 domain invariant (§確定H)

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

    async def test_create_json_schema_type_returns_dict_schema(self, dt_ctx: DtTestCtx) -> None:
        """JSON_SCHEMA type で dict schema を POST → レスポンスの schema が dict。"""
        from bakufu.domain.deliverable_template.deliverable_template import DeliverableTemplate

        from tests.factories.deliverable_template import ValidStubValidator

        # テスト用 validator を注入（Fail Secure 回避）
        original_validator = DeliverableTemplate._validator  # pyright: ignore[reportPrivateUsage]
        try:
            DeliverableTemplate._validator = ValidStubValidator()  # pyright: ignore[reportPrivateUsage]
            body = {
                **_MINIMAL_MARKDOWN_BODY,
                "type": "JSON_SCHEMA",
                "schema": {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object"},
            }
            resp = await dt_ctx.client.post("/api/deliverable-templates", json=body)
            assert resp.status_code == 201
            assert isinstance(resp.json()["schema"], dict)
        finally:
            DeliverableTemplate._validator = original_validator  # pyright: ignore[reportPrivateUsage]


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
