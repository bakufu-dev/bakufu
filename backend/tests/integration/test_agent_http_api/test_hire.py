"""agent / http-api 結合テスト — HIRE 系 (TC-IT-AGH-001〜006).

Per ``docs/features/agent/http-api/test-design.md`` §結合テストケース.

Covers:
  TC-IT-AGH-001  POST /api/empires/{empire_id}/agents → 201 AgentResponse
  TC-IT-AGH-002  POST Empire 不在 → 404 not_found (MSG-AG-HTTP-001 Empire)
  TC-IT-AGH-003  POST name 重複 → 409 conflict (MSG-AG-HTTP-002)
  TC-IT-AGH-004  POST providers=[] → 422 validation_error (R1-2 違反)
  TC-IT-AGH-005  POST is_default=True × 2 → 422 validation_error (R1-3 違反)
  TC-IT-AGH-006  POST prompt_body に raw token → レスポンスが masked (R1-9 / T4 / A02)

Issue: #59
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration.test_agent_http_api.helpers import (
    AgTestCtx,
    _create_agent_via_http,
    _create_empire,
    _minimal_agent_payload,
)

pytestmark = pytest.mark.asyncio

# masking 検証用 raw Anthropic token（sk-ant-api03- + 40 chars）
_RAW_ANTHROPIC_TOKEN: str = "sk-ant-api03-" + "A" * 40


class TestHireAgent:
    """TC-IT-AGH-001: POST /api/empires/{empire_id}/agents → 201 (REQ-AG-HTTP-001)."""

    async def test_hire_returns_201(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload(),
        )
        assert resp.status_code == 201

    async def test_hire_response_id_is_str(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload(),
        )
        assert isinstance(resp.json()["id"], str)

    async def test_hire_response_empire_id_matches(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload(),
        )
        assert resp.json()["empire_id"] == empire["id"]

    async def test_hire_response_name_matches(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload("ダリオ"),
        )
        assert resp.json()["name"] == "ダリオ"

    async def test_hire_response_archived_is_false(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload(),
        )
        assert resp.json()["archived"] is False

    async def test_hire_response_providers_length_is_one(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload(),
        )
        assert len(resp.json()["providers"]) == 1

    async def test_hire_response_skills_is_empty(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload(),
        )
        assert resp.json()["skills"] == []


class TestHireAgentEmpireNotFound:
    """TC-IT-AGH-002: POST 存在しない empire_id → 404 (EmpireNotFoundError)."""

    async def test_empire_not_found_returns_404(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.post(
            f"/api/empires/{uuid4()}/agents",
            json=_minimal_agent_payload(),
        )
        assert resp.status_code == 404

    async def test_empire_not_found_error_code(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.post(
            f"/api/empires/{uuid4()}/agents",
            json=_minimal_agent_payload(),
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_empire_not_found_error_message(self, ag_ctx: AgTestCtx) -> None:
        resp = await ag_ctx.client.post(
            f"/api/empires/{uuid4()}/agents",
            json=_minimal_agent_payload(),
        )
        assert resp.json()["error"]["message"] == "Empire not found."


class TestHireAgentNameConflict:
    """TC-IT-AGH-003: POST 同名 Agent → 409 conflict (MSG-AG-HTTP-002)."""

    async def test_duplicate_name_returns_409(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "重複名エージェント")
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload("重複名エージェント"),
        )
        assert resp.status_code == 409

    async def test_duplicate_name_error_code(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "重複名エージェント")
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload("重複名エージェント"),
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_duplicate_name_error_message(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        await _create_agent_via_http(ag_ctx.client, str(empire["id"]), "重複名エージェント")
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=_minimal_agent_payload("重複名エージェント"),
        )
        expected = "Agent with this name already exists in the Empire."
        assert resp.json()["error"]["message"] == expected


class TestHireAgentProvidersEmpty:
    """TC-IT-AGH-004: POST providers=[] → 422 (R1-2 違反 / AgentInvariantViolation)."""

    async def test_providers_empty_returns_422(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        payload = _minimal_agent_payload()
        payload["providers"] = []  # type: ignore[assignment]
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=payload,
        )
        assert resp.status_code == 422

    async def test_providers_empty_error_code(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        payload = _minimal_agent_payload()
        payload["providers"] = []  # type: ignore[assignment]
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=payload,
        )
        assert resp.json()["error"]["code"] == "validation_error"

    async def test_providers_empty_no_fail_prefix_in_body(self, ag_ctx: AgTestCtx) -> None:
        """[FAIL] プレフィックスが response body に露出しないこと (§確定C 前処理ルール)."""
        empire = await _create_empire(ag_ctx.client)
        payload = _minimal_agent_payload()
        payload["providers"] = []  # type: ignore[assignment]
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=payload,
        )
        assert "[FAIL]" not in resp.text

    async def test_providers_empty_no_next_in_body(self, ag_ctx: AgTestCtx) -> None:
        """\\nNext: サフィックスが response body に露出しないこと (§確定C 前処理ルール)."""
        empire = await _create_empire(ag_ctx.client)
        payload = _minimal_agent_payload()
        payload["providers"] = []  # type: ignore[assignment]
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=payload,
        )
        assert "Next:" not in resp.text


class TestHireAgentDefaultNotUnique:
    """TC-IT-AGH-005: POST is_default=True × 2 → 422 (R1-3 違反)."""

    async def test_two_defaults_returns_422(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        payload = _minimal_agent_payload()
        payload["providers"] = [  # type: ignore[assignment]
            {"provider_kind": "CLAUDE_CODE", "model": "claude-sonnet-4-5", "is_default": True},
            {"provider_kind": "CODEX", "model": "gpt-4o", "is_default": True},
        ]
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=payload,
        )
        assert resp.status_code == 422

    async def test_two_defaults_error_code(self, ag_ctx: AgTestCtx) -> None:
        empire = await _create_empire(ag_ctx.client)
        payload = _minimal_agent_payload()
        payload["providers"] = [  # type: ignore[assignment]
            {"provider_kind": "CLAUDE_CODE", "model": "claude-sonnet-4-5", "is_default": True},
            {"provider_kind": "CODEX", "model": "gpt-4o", "is_default": True},
        ]
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=payload,
        )
        assert resp.json()["error"]["code"] == "validation_error"


class TestHireAgentMasking:
    """TC-IT-AGH-006: POST prompt_body に raw token → レスポンスが masked (R1-9 / T4 / A02)."""

    async def test_post_prompt_body_raw_token_not_in_response(self, ag_ctx: AgTestCtx) -> None:
        """POST レスポンスの persona.prompt_body に raw Anthropic token が含まれないこと。"""
        empire = await _create_empire(ag_ctx.client)
        payload = _minimal_agent_payload()
        payload["persona"] = {  # type: ignore[assignment]
            "display_name": "シークレットエージェント",
            "archetype": "security",
            "prompt_body": f"ANTHROPIC_API_KEY={_RAW_ANTHROPIC_TOKEN}",
        }
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=payload,
        )
        assert _RAW_ANTHROPIC_TOKEN not in resp.json()["persona"]["prompt_body"]

    async def test_post_prompt_body_is_redacted(self, ag_ctx: AgTestCtx) -> None:
        """POST レスポンスの persona.prompt_body が <REDACTED:ANTHROPIC_KEY> 形式であること。"""
        empire = await _create_empire(ag_ctx.client)
        payload = _minimal_agent_payload()
        payload["persona"] = {  # type: ignore[assignment]
            "display_name": "シークレットエージェント",
            "archetype": "security",
            "prompt_body": f"ANTHROPIC_API_KEY={_RAW_ANTHROPIC_TOKEN}",
        }
        resp = await ag_ctx.client.post(
            f"/api/empires/{empire['id']}/agents",
            json=payload,
        )
        assert "<REDACTED:ANTHROPIC_KEY>" in resp.json()["persona"]["prompt_body"]
