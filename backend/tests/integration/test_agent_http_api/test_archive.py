"""agent / http-api 結合テスト — ARCHIVE 系 (TC-IT-AGH-021〜023).

Per ``docs/features/agent/http-api/test-design.md`` §結合テストケース.

Covers:
  TC-IT-AGH-021  DELETE /api/agents/{agent_id} → 204 No Content (REQ-AG-HTTP-005)
  TC-IT-AGH-022  DELETE Agent 不在 → 404 not_found (MSG-AG-HTTP-001)
  TC-IT-AGH-023  DELETE 冪等性: 2 回目も 204 (§確定G / BUG-AG-001 解消済み)

Issue: #59
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration.test_agent_http_api.helpers import (
    AgTestCtx,
    _create_agent_via_http,
    _create_empire,
)

pytestmark = pytest.mark.asyncio


class TestArchiveAgent:
    """TC-IT-AGH-021: DELETE → 204 論理削除 (REQ-AG-HTTP-005)."""

    async def test_archive_returns_204(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        resp = await ag_ctx.client.delete(f"/api/agents/{agent['id']}")
        assert resp.status_code == 204

    async def test_archive_response_has_no_body(self, ag_ctx: AgTestCtx) -> None:
        """204 No Content は body を持たない (物理保証)."""
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        resp = await ag_ctx.client.delete(f"/api/agents/{agent['id']}")
        assert resp.content == b""

    async def test_after_archive_get_shows_archived_true(self, ag_ctx: AgTestCtx) -> None:
        """論理削除後 GET → archived=true (物理保証)."""
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        await ag_ctx.client.delete(f"/api/agents/{agent['id']}")
        resp = await ag_ctx.client.get(f"/api/agents/{agent['id']}")
        assert resp.json()["archived"] is True


class TestArchiveAgentNotFound:
    """TC-IT-AGH-022: DELETE 存在しない agent_id → 404 (AgentNotFoundError)."""

    async def test_not_found_returns_404(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.delete(f"/api/agents/{uuid4()}")
        assert resp.status_code == 404

    async def test_not_found_error_code(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.delete(f"/api/agents/{uuid4()}")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_not_found_error_message(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.delete(f"/api/agents/{uuid4()}")
        assert resp.json()["error"]["message"] == "Agent not found."


class TestArchiveAgentIdempotency:
    """TC-IT-AGH-023: DELETE 冪等性 — 2 回目も 204 (§確定G / BUG-AG-001 解消済み).

    BUG-AG-001 解消済み: system-test-design.md コミット ``94e28fd`` で
    「2 回目 DELETE → 204（冪等）」に修正。全設計書間の矛盾は解消された。
    ``AgentService.archive()`` は archived かどうかに関わらず save() を呼ぶ設計
    (``detailed-design.md §確定G`` 凍結値)。
    """

    async def test_first_delete_returns_204(self, ag_ctx: AgTestCtx) -> None:
        """1 回目の DELETE が 204 を返すこと。"""
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        resp = await ag_ctx.client.delete(f"/api/agents/{agent['id']}")
        assert resp.status_code == 204

    async def test_second_delete_returns_204(self, ag_ctx: AgTestCtx) -> None:
        """2 回目の DELETE も 204 を返すこと (§確定G 冪等性)."""
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        await ag_ctx.client.delete(f"/api/agents/{agent['id']}")
        resp = await ag_ctx.client.delete(f"/api/agents/{agent['id']}")
        assert resp.status_code == 204
