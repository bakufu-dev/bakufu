"""agent / http-api 結合テスト — GET 系 (TC-IT-AGH-011〜013).

Per ``docs/features/agent/http-api/test-design.md`` §結合テストケース.

Covers:
  TC-IT-AGH-011  GET /api/agents/{agent_id} → 200 AgentResponse
  TC-IT-AGH-012  GET Agent 不在 → 404 not_found (MSG-AG-HTTP-001)
  TC-IT-AGH-013  GET prompt_body が masked (R1-9 独立防御証明 / T4 / A02)
                 R1-8 バイパス: 直接 DB シードで raw token を INSERT し、
                 GET レスポンスで field_serializer が発火することを証明する

Issue: #59
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from tests.integration.test_agent_http_api.helpers import (
    AgTestCtx,
    _create_agent_via_http,
    _create_empire,
    _seed_agent_with_raw_prompt_body,
)

pytestmark = pytest.mark.asyncio

# masking 検証用 raw GitHub PAT（ghp_ + 36 chars）
_RAW_GITHUB_PAT: str = "ghp_" + "A" * 36


class TestGetAgent:
    """TC-IT-AGH-011: GET /api/agents/{agent_id} → 200 AgentResponse (REQ-AG-HTTP-003)."""

    async def test_get_returns_200(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "取得エージェント")
        resp = await ag_ctx.client.get(f"/api/agents/{agent['id']}")
        assert resp.status_code == 200

    async def test_get_response_id_matches(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "取得エージェント")
        resp = await ag_ctx.client.get(f"/api/agents/{agent['id']}")
        assert resp.json()["id"] == agent["id"]

    async def test_get_response_name_matches(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "取得エージェント")
        resp = await ag_ctx.client.get(f"/api/agents/{agent['id']}")
        assert resp.json()["name"] == "取得エージェント"

    async def test_get_response_empire_id_matches(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "取得エージェント")
        resp = await ag_ctx.client.get(f"/api/agents/{agent['id']}")
        assert resp.json()["empire_id"] == empire["id"]


class TestGetAgentNotFound:
    """TC-IT-AGH-012: GET 存在しない agent_id → 404 (AgentNotFoundError)."""

    async def test_not_found_returns_404(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.get(f"/api/agents/{uuid4()}")
        assert resp.status_code == 404

    async def test_not_found_error_code(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.get(f"/api/agents/{uuid4()}")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_not_found_error_message(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.get(f"/api/agents/{uuid4()}")
        assert resp.json()["error"]["message"] == "Agent not found."


class TestGetAgentMaskingR1_9Independence:
    """TC-IT-AGH-013: GET prompt_body が masked — R1-9 独立防御証明 (R1-9 / T4 / A02).

    R1-8 バイパス経路: HTTP POST を経由せず直接 DB シードで raw token を INSERT する。
    GET の field_serializer が R1-8 と独立して発火することを証明する。
    """

    async def test_get_prompt_body_raw_token_not_in_response(self, ag_ctx: AgTestCtx) -> None:
        """R1-8 バイパス: 直接 DB INSERT した raw token が GET レスポンスに露出しないこと。"""
        empire = await _create_empire(ag_ctx.client)
        empire_id = UUID(str(empire["id"]))
        raw_prompt = f"GITHUB_PAT={_RAW_GITHUB_PAT}"
        agent = await _seed_agent_with_raw_prompt_body(
            ag_ctx.session_factory, empire_id, raw_prompt
        )
        resp = await ag_ctx.client.get(f"/api/agents/{agent.id}")  # type: ignore[attr-defined]
        assert _RAW_GITHUB_PAT not in resp.json()["persona"]["prompt_body"]

    async def test_get_prompt_body_is_redacted(self, ag_ctx: AgTestCtx) -> None:
        """GET レスポンスの persona.prompt_body が <REDACTED:GITHUB_PAT> 形式であること。"""
        empire = await _create_empire(ag_ctx.client)
        empire_id = UUID(str(empire["id"]))
        raw_prompt = f"GITHUB_PAT={_RAW_GITHUB_PAT}"
        agent = await _seed_agent_with_raw_prompt_body(
            ag_ctx.session_factory, empire_id, raw_prompt
        )
        resp = await ag_ctx.client.get(f"/api/agents/{agent.id}")  # type: ignore[attr-defined]
        assert "<REDACTED:GITHUB_PAT>" in resp.json()["persona"]["prompt_body"]
