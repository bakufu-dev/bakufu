"""agent / http-api 結合テスト — LIST 系 (TC-IT-AGH-007〜010).

Per ``docs/features/agent/http-api/test-design.md`` §結合テストケース.

Covers:
  TC-IT-AGH-007  GET /api/empires/{empire_id}/agents → 200 AgentListResponse (1 件)
  TC-IT-AGH-008  GET /api/empires/{empire_id}/agents → 200 空リスト (0 件)
  TC-IT-AGH-009  GET Empire 不在 → 404 not_found
  TC-IT-AGH-010  GET list がアーカイブ済み Agent を含む (total=2)

Issue: #59
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from tests.integration.test_agent_http_api.helpers import (
    AgTestCtx,
    _create_agent_via_http,
    _create_empire,
    _seed_agent_direct,
)

pytestmark = pytest.mark.asyncio


class TestListAgentsOnce:
    """TC-IT-AGH-007: GET /api/empires/{empire_id}/agents → 200 with 1 agent (REQ-AG-HTTP-002)."""

    async def test_list_returns_200(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        resp = await ag_ctx.client.get(f"/api/empires/{empire['id']}/agents")
        assert resp.status_code == 200

    async def test_list_total_is_one(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        resp = await ag_ctx.client.get(f"/api/empires/{empire['id']}/agents")
        assert resp.json()["total"] == 1

    async def test_list_items_length_is_one(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        resp = await ag_ctx.client.get(f"/api/empires/{empire['id']}/agents")
        assert len(resp.json()["items"]) == 1

    async def test_list_item_has_id(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        resp = await ag_ctx.client.get(f"/api/empires/{empire['id']}/agents")
        assert isinstance(resp.json()["items"][0]["id"], str)


class TestListAgentsEmpty:
    """TC-IT-AGH-008: GET /api/empires/{empire_id}/agents → 200 空リスト (REQ-AG-HTTP-002)."""

    async def test_empty_list_returns_200(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.get(f"/api/empires/{empire['id']}/agents")
        assert resp.status_code == 200

    async def test_empty_list_items_is_empty(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.get(f"/api/empires/{empire['id']}/agents")
        assert resp.json()["items"] == []

    async def test_empty_list_total_is_zero(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.get(f"/api/empires/{empire['id']}/agents")
        assert resp.json()["total"] == 0


class TestListAgentsEmpireNotFound:
    """TC-IT-AGH-009: GET 存在しない empire_id → 404 (EmpireNotFoundError)."""

    async def test_empire_not_found_returns_404(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.get(f"/api/empires/{uuid4()}/agents")
        assert resp.status_code == 404

    async def test_empire_not_found_error_code(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.get(f"/api/empires/{uuid4()}/agents")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_empire_not_found_error_message(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.get(f"/api/empires/{uuid4()}/agents")
        assert resp.json()["error"]["message"] == "Empire not found."


class TestListAgentsIncludesArchived:
    """TC-IT-AGH-010: GET list がアーカイブ済み Agent を含む (total=2)。"""

    async def test_list_includes_archived_total_is_two(self, ag_ctx: AgTestCtx) -> None:
        """アーカイブ済みを含めて 2 件返ること (REQ-AG-HTTP-002)."""
        empire = await _create_empire(ag_ctx.client)
        empire_id = UUID(str(empire["id"]))
        # active な Agent: HTTP API 経由で作成
        await _create_agent_via_http(ag_ctx.client, str(empire_id), "アクティブエージェント")
        # archived な Agent: 直接 DB に INSERT
        await _seed_agent_direct(
            ag_ctx.session_factory,
            empire_id,
            name="アーカイブエージェント",
            archived=True,
        )
        resp = await ag_ctx.client.get(f"/api/empires/{empire_id}/agents")
        assert resp.json()["total"] == 2

    async def test_list_includes_archived_items_length_is_two(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        empire_id = UUID(str(empire["id"]))
        await _create_agent_via_http(ag_ctx.client, str(empire_id), "アクティブエージェント")
        await _seed_agent_direct(
            ag_ctx.session_factory,
            empire_id,
            name="アーカイブエージェント",
            archived=True,
        )
        resp = await ag_ctx.client.get(f"/api/empires/{empire_id}/agents")
        assert len(resp.json()["items"]) == 2
