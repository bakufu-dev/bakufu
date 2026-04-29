"""agent / http-api 結合テスト — UPDATE 系 (TC-IT-AGH-014〜020).

Per ``docs/features/agent/http-api/test-design.md`` §結合テストケース.

Covers:
  TC-IT-AGH-014  PATCH name のみ更新 → 200 AgentResponse (REQ-AG-HTTP-004)
  TC-IT-AGH-015  PATCH providers 全置換 → 200 AgentResponse
  TC-IT-AGH-016  PATCH Agent 不在 → 404 not_found (MSG-AG-HTTP-001)
  TC-IT-AGH-017  PATCH archived Agent → 409 conflict (MSG-AG-HTTP-003)
  TC-IT-AGH-018  PATCH name 重複 → 409 conflict (MSG-AG-HTTP-002)
  TC-IT-AGH-019  PATCH providers is_default=True × 2 → 422 (不変条件違反)
  TC-IT-AGH-020  PATCH prompt_body に raw token → レスポンスが masked (R1-9 / T4 / A02)

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

# masking 検証用 raw GitHub PAT（ghp_ + 36 chars）
_RAW_GITHUB_PAT: str = "ghp_" + "B" * 36


class TestUpdateAgentName:
    """TC-IT-AGH-014: PATCH name のみ更新 → 200 (REQ-AG-HTTP-004)."""

    async def test_update_name_returns_200(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "旧名前")
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent['id']}",
            json={"name": "新名前"},
        )
        assert resp.status_code == 200

    async def test_update_name_response_name_matches(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "旧名前")
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent['id']}",
            json={"name": "新名前"},
        )
        assert resp.json()["name"] == "新名前"

    async def test_update_name_other_fields_unchanged(self, ag_ctx: AgTestCtx) -> None:
        """name 以外のフィールドが変化しないこと。"""
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "旧名前")
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent['id']}",
            json={"name": "新名前"},
        )
        assert resp.json()["role"] == agent["role"]


class TestUpdateAgentProviders:
    """TC-IT-AGH-015: PATCH providers 全置換 → 200 (REQ-AG-HTTP-004)."""

    async def test_update_providers_returns_200(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        new_providers = [
            {"provider_kind": "GEMINI", "model": "gemini-2.0-flash", "is_default": True}
        ]
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent['id']}",
            json={"providers": new_providers},
        )
        assert resp.status_code == 200

    async def test_update_providers_replaced(self, ag_ctx: AgTestCtx) -> None:
        """providers が新 list に差し替わること。"""
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        new_providers = [
            {"provider_kind": "GEMINI", "model": "gemini-2.0-flash", "is_default": True}
        ]
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent['id']}",
            json={"providers": new_providers},
        )
        assert resp.json()["providers"][0]["provider_kind"] == "GEMINI"


class TestUpdateAgentNotFound:
    """TC-IT-AGH-016: PATCH 存在しない agent_id → 404 (AgentNotFoundError)."""

    async def test_not_found_returns_404(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.patch(
            f"/api/agents/{uuid4()}",
            json={"name": "変更"},
        )
        assert resp.status_code == 404

    async def test_not_found_error_code(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.patch(
            f"/api/agents/{uuid4()}",
            json={"name": "変更"},
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_not_found_error_message(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.patch(
            f"/api/agents/{uuid4()}",
            json={"name": "変更"},
        )
        assert resp.json()["error"]["message"] == "Agent not found."


class TestUpdateAgentArchived:
    """TC-IT-AGH-017: PATCH archived Agent → 409 conflict (MSG-AG-HTTP-003)."""

    async def test_archived_returns_409(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        empire_id = UUID(str(empire["id"]))
        agent = await _seed_agent_direct(
            ag_ctx.session_factory, empire_id, name="アーカイブ済み", archived=True
        )
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent.id}",  # type: ignore[attr-defined]
            json={"name": "変更試み"},
        )
        assert resp.status_code == 409

    async def test_archived_error_code(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        empire_id = UUID(str(empire["id"]))
        agent = await _seed_agent_direct(
            ag_ctx.session_factory, empire_id, name="アーカイブ済み", archived=True
        )
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent.id}",  # type: ignore[attr-defined]
            json={"name": "変更試み"},
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_archived_error_message(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        empire_id = UUID(str(empire["id"]))
        agent = await _seed_agent_direct(
            ag_ctx.session_factory, empire_id, name="アーカイブ済み", archived=True
        )
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent.id}",  # type: ignore[attr-defined]
            json={"name": "変更試み"},
        )
        assert resp.json()["error"]["message"] == "Agent is archived and cannot be modified."


class TestUpdateAgentNameConflict:
    """TC-IT-AGH-018: PATCH name 重複 → 409 conflict (MSG-AG-HTTP-002)."""

    async def test_name_conflict_returns_409(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent_a = await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "エージェントA")
        await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "エージェントB")
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent_a['id']}",
            json={"name": "エージェントB"},
        )
        assert resp.status_code == 409

    async def test_name_conflict_error_code(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent_a = await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "エージェントA")
        await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "エージェントB")
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent_a['id']}",
            json={"name": "エージェントB"},
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_name_conflict_error_message(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent_a = await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "エージェントA")
        await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "エージェントB")
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent_a['id']}",
            json={"name": "エージェントB"},
        )
        expected = "Agent with this name already exists in the Empire."
        assert resp.json()["error"]["message"] == expected


_TWO_DEFAULTS_PROVIDERS = [
    {"provider_kind": "CLAUDE_CODE", "model": "claude-sonnet-4-5", "is_default": True},
    {"provider_kind": "CODEX", "model": "gpt-4o", "is_default": True},
]


class TestUpdateAgentInvariantViolation:
    """TC-IT-AGH-019: PATCH providers is_default=True × 2 → 422 (AgentInvariantViolation)."""

    async def test_two_defaults_returns_422(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent['id']}",
            json={"providers": _TWO_DEFAULTS_PROVIDERS},
        )
        assert resp.status_code == 422

    async def test_two_defaults_error_code(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent['id']}",
            json={"providers": _TWO_DEFAULTS_PROVIDERS},
        )
        assert resp.json()["error"]["code"] == "validation_error"


class TestUpdateAgentMasking:
    """TC-IT-AGH-020: PATCH prompt_body に raw token → レスポンスが masked (R1-9 / T4 / A02)."""

    async def test_patch_prompt_body_raw_token_not_in_response(self, ag_ctx: AgTestCtx) -> None:
        """PATCH レスポンスの persona.prompt_body に raw GitHub PAT が含まれないこと。"""
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent['id']}",
            json={"persona": {"prompt_body": f"GITHUB_PAT={_RAW_GITHUB_PAT}"}},
        )
        assert _RAW_GITHUB_PAT not in resp.json()["persona"]["prompt_body"]

    async def test_patch_prompt_body_is_redacted(self, ag_ctx: AgTestCtx) -> None:
        """PATCH レスポンスの persona.prompt_body が <REDACTED:GITHUB_PAT> 形式であること。"""
        empire = await _create_empire(ag_ctx.client)
        agent = await _create_agent_via_http(ag_ctx.client, str(empire["id"]))
        resp = await ag_ctx.client.patch(
            f"/api/agents/{agent['id']}",
            json={"persona": {"prompt_body": f"GITHUB_PAT={_RAW_GITHUB_PAT}"}},
        )
        assert "<REDACTED:GITHUB_PAT>" in resp.json()["persona"]["prompt_body"]
