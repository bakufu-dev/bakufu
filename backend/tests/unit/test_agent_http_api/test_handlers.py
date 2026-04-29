"""agent / http-api error handler ユニットテスト (TC-UT-AGH-001〜004).

Per ``docs/features/agent/http-api/test-design.md`` §ユニットテストケース.

Covers:
  TC-UT-AGH-001  agent_not_found_handler (MSG-AG-HTTP-001)
  TC-UT-AGH-002  agent_name_already_exists_handler (MSG-AG-HTTP-002)
  TC-UT-AGH-003  agent_archived_handler (MSG-AG-HTTP-003)
  TC-UT-AGH-004  agent_invariant_violation_handler (MSG-AG-HTTP-004 / §確定C 前処理ルール)
Issue: #59
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# TC-UT-AGH-001: agent_not_found_handler (MSG-AG-HTTP-001)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestAgentNotFoundHandler:
    """TC-UT-AGH-001: agent_not_found_handler → 404, code=not_found, MSG-AG-HTTP-001。"""

    def _make_request(self) -> Any:
        return MagicMock()

    async def test_returns_404(self) -> None:
        """AgentNotFoundError → HTTP 404。"""
        from bakufu.application.exceptions.agent_exceptions import AgentNotFoundError
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = AgentNotFoundError(agent_id="test-id")
        resp = await HttpErrorHandlers.agent_not_found_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 404  # type: ignore[union-attr]

    async def test_error_code_is_not_found(self) -> None:
        from bakufu.application.exceptions.agent_exceptions import AgentNotFoundError
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = AgentNotFoundError(agent_id="test-id")
        resp = await HttpErrorHandlers.agent_not_found_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "not_found"

    async def test_error_message_is_msg_ag_http_001(self) -> None:
        """MSG-AG-HTTP-001: 確定文言 'Agent not found.'"""
        from bakufu.application.exceptions.agent_exceptions import AgentNotFoundError
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = AgentNotFoundError(agent_id="test-id")
        resp = await HttpErrorHandlers.agent_not_found_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Agent not found."

    async def test_wrong_exception_type_raises_type_error(self) -> None:
        """非 AgentNotFoundError → TypeError (Fail Fast)。"""
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        with pytest.raises(TypeError, match="Expected AgentNotFoundError"):
            await HttpErrorHandlers.agent_not_found_handler(
                self._make_request(), ValueError("oops")
            )  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TC-UT-AGH-002: agent_name_already_exists_handler (MSG-AG-HTTP-002)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestAgentNameAlreadyExistsHandler:
    """TC-UT-AGH-002: agent_name_already_exists_handler → 409, code=conflict, MSG-AG-HTTP-002。"""

    def _make_request(self) -> Any:
        return MagicMock()

    async def test_returns_409(self) -> None:
        from bakufu.application.exceptions.agent_exceptions import AgentNameAlreadyExistsError
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = AgentNameAlreadyExistsError(empire_id="eid", name="n")
        resp = await HttpErrorHandlers.agent_name_already_exists_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 409  # type: ignore[union-attr]

    async def test_error_code_is_conflict(self) -> None:
        from bakufu.application.exceptions.agent_exceptions import AgentNameAlreadyExistsError
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = AgentNameAlreadyExistsError(empire_id="eid", name="n")
        resp = await HttpErrorHandlers.agent_name_already_exists_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "conflict"

    async def test_error_message_is_msg_ag_http_002(self) -> None:
        """MSG-AG-HTTP-002: 確定文言 'Agent with this name already exists in the Empire.'"""
        from bakufu.application.exceptions.agent_exceptions import AgentNameAlreadyExistsError
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = AgentNameAlreadyExistsError(empire_id="eid", name="n")
        resp = await HttpErrorHandlers.agent_name_already_exists_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Agent with this name already exists in the Empire."


# ---------------------------------------------------------------------------
# TC-UT-AGH-003: agent_archived_handler (MSG-AG-HTTP-003)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestAgentArchivedHandler:
    """TC-UT-AGH-003: agent_archived_handler → 409, code=conflict, MSG-AG-HTTP-003。"""

    def _make_request(self) -> Any:
        return MagicMock()

    async def test_returns_409(self) -> None:
        from bakufu.application.exceptions.agent_exceptions import AgentArchivedError
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = AgentArchivedError(agent_id="test-id")
        resp = await HttpErrorHandlers.agent_archived_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 409  # type: ignore[union-attr]

    async def test_error_code_is_conflict(self) -> None:
        from bakufu.application.exceptions.agent_exceptions import AgentArchivedError
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = AgentArchivedError(agent_id="test-id")
        resp = await HttpErrorHandlers.agent_archived_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "conflict"

    async def test_error_message_is_msg_ag_http_003(self) -> None:
        """MSG-AG-HTTP-003: 確定文言 'Agent is archived and cannot be modified.'"""
        from bakufu.application.exceptions.agent_exceptions import AgentArchivedError
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = AgentArchivedError(agent_id="test-id")
        resp = await HttpErrorHandlers.agent_archived_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Agent is archived and cannot be modified."


# ---------------------------------------------------------------------------
# TC-UT-AGH-004: agent_invariant_violation_handler (MSG-AG-HTTP-004 / §確定C)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestAgentInvariantViolationHandler:
    """TC-UT-AGH-004: agent_invariant_violation_handler — §確定C 前処理ルール。"""

    def _make_request(self) -> Any:
        return MagicMock()

    def _make_exc(self, msg: str) -> Any:
        from bakufu.domain.exceptions import AgentInvariantViolation

        return AgentInvariantViolation(
            kind="default_not_unique",
            message=msg,
        )

    async def test_returns_422_with_fail_prefix(self) -> None:
        """(a) [FAIL] プレフィックス付き入力 → HTTP 422。"""
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = self._make_exc(
            "[FAIL] providers must have exactly one default provider."
            "\nNext: set is_default=True for exactly one provider."
        )
        resp = await HttpErrorHandlers.agent_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 422  # type: ignore[union-attr]

    async def test_fail_prefix_removed(self) -> None:
        """[FAIL] プレフィックスが除去されること (§確定C)。"""
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = self._make_exc(
            "[FAIL] providers must have exactly one default provider."
            "\nNext: set is_default=True for exactly one provider."
        )
        resp = await HttpErrorHandlers.agent_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "[FAIL]" not in body["error"]["message"]

    async def test_next_suffix_removed(self) -> None:
        """\\nNext:.* サフィックスが除去されること (§確定C)。"""
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = self._make_exc(
            "[FAIL] providers must have exactly one default provider."
            "\nNext: set is_default=True for exactly one provider."
        )
        resp = await HttpErrorHandlers.agent_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "Next:" not in body["error"]["message"]

    async def test_clean_message_is_business_text_only(self) -> None:
        """前処理後の message が純粋な業務テキストであること (§確定C)。"""
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = self._make_exc(
            "[FAIL] providers must have exactly one default provider."
            "\nNext: set is_default=True for exactly one provider."
        )
        resp = await HttpErrorHandlers.agent_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "providers must have exactly one default provider."

    async def test_no_fail_prefix_without_next(self) -> None:
        """(b) [FAIL] のみ（Next: なし）でも正しく前処理されること。"""
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = self._make_exc("[FAIL] Agent name は 1〜40 文字でなければなりません。")
        resp = await HttpErrorHandlers.agent_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "[FAIL]" not in body["error"]["message"]

    async def test_error_code_is_validation_error(self) -> None:
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = self._make_exc("[FAIL] Agent name は 1〜40 文字でなければなりません。")
        resp = await HttpErrorHandlers.agent_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "validation_error"
