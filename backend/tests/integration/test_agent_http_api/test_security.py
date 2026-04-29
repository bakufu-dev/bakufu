"""agent / http-api 結合テスト — セキュリティ系 (TC-IT-AGH-024〜027).

Per ``docs/features/agent/http-api/test-design.md`` §結合テストケース.

Covers:
  TC-IT-AGH-024  不正 UUID → 422 (T3: FastAPI UUID 型強制)
  TC-IT-AGH-025  POST + evil Origin → 403 (T1: CSRF 保護)
  TC-IT-AGH-026  内部エラー → 500 スタックトレース非露出 (T2)
  TC-IT-AGH-027  SkillRef path traversal → 422 (T5: H5 パストラバーサル防御)

Issue: #59
"""

from __future__ import annotations

import pytest

from tests.integration.test_agent_http_api.helpers import (
    AgTestCtx,
    _create_empire,
    _minimal_agent_payload,
)

pytestmark = pytest.mark.asyncio


class TestInvalidUuid:
    """TC-IT-AGH-024: 不正 UUID パスパラメータ → 422 (T3)."""

    async def test_invalid_uuid_get_agent_returns_422(self, ag_ctx: AgTestCtx) -> None:
        """GET /api/agents/not-a-valid-uuid → 422 (FastAPI UUID 型強制)."""
        resp = await ag_ctx.client.get("/api/agents/not-a-valid-uuid")
        assert resp.status_code == 422

    async def test_invalid_uuid_patch_agent_returns_422(self, ag_ctx: AgTestCtx) -> None:
        """PATCH /api/agents/not-a-valid-uuid → 422."""
        resp = await ag_ctx.client.patch(
            "/api/agents/not-a-valid-uuid",
            json={"name": "X"},
        )
        assert resp.status_code == 422

    async def test_invalid_uuid_delete_agent_returns_422(self, ag_ctx: AgTestCtx) -> None:
        """DELETE /api/agents/not-a-valid-uuid → 422."""
        resp = await ag_ctx.client.delete("/api/agents/not-a-valid-uuid")
        assert resp.status_code == 422


class TestCsrfProtection:
    """TC-IT-AGH-025: POST + 不正 Origin → 403 (T1: CSRF 保護の物理保証)."""

    async def test_evil_origin_post_returns_403(self, ag_ctx: AgTestCtx) -> None:
        """CSRF ミドルウェアが agent ルータにも適用されることの物理保証。"""
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload(),
            headers={"Origin": "http://evil.example.com"},
        )
        assert resp.status_code == 403

    async def test_evil_origin_error_code_is_forbidden(self, ag_ctx: AgTestCtx) -> None:
        """CSRF 403 の error code が "forbidden" であること。"""
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload(),
            headers={"Origin": "http://evil.example.com"},
        )
        assert resp.json()["error"]["code"] == "forbidden"

    async def test_evil_origin_error_message(self, ag_ctx: AgTestCtx) -> None:
        """CSRF 403 の error message が確定文言であること。"""
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload(),
            headers={"Origin": "http://evil.example.com"},
        )
        assert resp.json()["error"]["message"] == "CSRF check failed: Origin not allowed."


class TestInternalErrorNoStackTrace:
    """TC-IT-AGH-026: 内部エラー → 500 でスタックトレースが露出しないこと (T2).

    ``app_client`` fixture（tests/integration/conftest.py）の
    /test/raise-exception エンドポイントを利用する。
    ``raise_app_exceptions=False`` が設定されているため 500 JSON ボディが返る。
    """

    async def test_internal_error_returns_500(self, app_client: object) -> None:
        """RuntimeError → HTTP 500。"""
        from httpx import AsyncClient

        client: AsyncClient = app_client  # type: ignore[assignment]
        resp = await client.get("/test/raise-exception")
        assert resp.status_code == 500

    async def test_internal_error_no_traceback_in_body(self, app_client: object) -> None:
        """500 body に "Traceback" が含まれないこと (T2 スタックトレース非露出)."""
        from httpx import AsyncClient

        client: AsyncClient = app_client  # type: ignore[assignment]
        resp = await client.get("/test/raise-exception")
        assert "Traceback" not in resp.text

    async def test_internal_error_no_stacktrace_key(self, app_client: object) -> None:
        """500 body に "stacktrace" キーが含まれないこと。"""
        from httpx import AsyncClient

        client: AsyncClient = app_client  # type: ignore[assignment]
        resp = await client.get("/test/raise-exception")
        assert "stacktrace" not in resp.text

    async def test_internal_error_code_is_internal_error(self, app_client: object) -> None:
        """500 body の error code が "internal_error" であること。"""
        from httpx import AsyncClient

        client: AsyncClient = app_client  # type: ignore[assignment]
        resp = await client.get("/test/raise-exception")
        assert resp.json()["error"]["code"] == "internal_error"


class TestPathTraversalDefense:
    """TC-IT-AGH-027: SkillRef path traversal → 422 (T5: H5 パストラバーサル防御)."""

    async def test_path_traversal_returns_422(self, ag_ctx: AgTestCtx) -> None:
        """POST skills に path='../../../etc/passwd' → 422 (H5 トラバーサル防御)."""
        empire = await _create_empire(ag_ctx.client)
        payload = _minimal_agent_payload()
        import uuid
        payload["skills"] = [  # type: ignore[assignment]
            {
                "skill_id": str(uuid.uuid4()),
                "name": "traversal-skill",
                "path": "../../../etc/passwd",
            }
        ]
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=payload,
        )
        assert resp.status_code == 422

    async def test_path_traversal_error_code(self, ag_ctx: AgTestCtx) -> None:
        """path traversal 422 の error code が "validation_error" であること。"""
        empire = await _create_empire(ag_ctx.client)
        payload = _minimal_agent_payload()
        import uuid
        payload["skills"] = [  # type: ignore[assignment]
            {
                "skill_id": str(uuid.uuid4()),
                "name": "traversal-skill",
                "path": "../../../etc/passwd",
            }
        ]
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=payload,
        )
        assert resp.json()["error"]["code"] == "validation_error"
