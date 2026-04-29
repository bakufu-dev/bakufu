"""ExternalReviewGate HTTP API handler/auth unit tests.

Covers:
  TC-UT-ERG-HTTP-011, TC-UT-ERG-HTTP-012

Issue: #61
"""

from __future__ import annotations

import json
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse


def _json_body(response: JSONResponse) -> dict[str, Any]:
    body = bytes(response.body)
    return cast("dict[str, Any]", json.loads(body.decode("utf-8")))


@pytest.mark.asyncio
class TestExternalReviewGateErrorHandlers:
    async def test_not_found_handler_returns_two_line_next_message(self) -> None:
        from bakufu.application.exceptions.external_review_gate_exceptions import (
            ExternalReviewGateNotFoundError,
        )
        from bakufu.interfaces.http.error_handlers import external_review_gate_not_found_handler

        response = await external_review_gate_not_found_handler(
            None,  # type: ignore[arg-type]
            ExternalReviewGateNotFoundError(uuid4()),
        )

        assert _json_body(response)["error"]["message"] == (
            "External review gate not found.\n"
            "Next: Refresh the gate list and select an existing gate."
        )

    async def test_authorization_handler_returns_two_line_next_message(self) -> None:
        from bakufu.application.exceptions.external_review_gate_exceptions import (
            ExternalReviewGateAuthorizationError,
        )
        from bakufu.interfaces.http.error_handlers import external_review_gate_authorization_handler

        response = await external_review_gate_authorization_handler(
            None,  # type: ignore[arg-type]
            ExternalReviewGateAuthorizationError(uuid4(), uuid4()),
        )

        assert _json_body(response)["error"]["message"] == (
            "Reviewer is not authorized for this gate.\n"
            "Next: Sign in as the assigned reviewer for this gate."
        )

    async def test_conflict_handler_returns_two_line_next_message(self) -> None:
        from bakufu.application.exceptions.external_review_gate_exceptions import (
            ExternalReviewGateDecisionConflictError,
        )
        from bakufu.interfaces.http.error_handlers import (
            external_review_gate_decision_conflict_handler,
        )

        response = await external_review_gate_decision_conflict_handler(
            None,  # type: ignore[arg-type]
            ExternalReviewGateDecisionConflictError(uuid4(), "APPROVED", "approve"),
        )

        assert _json_body(response)["error"]["message"] == (
            "External review gate has already been decided.\n"
            "Next: Open the task gate history and review the latest pending gate."
        )


@pytest.mark.asyncio
class TestExternalReviewGateBearerTokenResolver:
    async def test_resolver_accepts_matching_32_byte_bearer_token(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-UT-ERG-HTTP-012: 32 bytes 以上の一致 token だけ subject を作る。"""
        from bakufu.interfaces.http.dependencies import get_external_review_subject

        owner_id = uuid4()
        token = "owner-api-token-32-bytes-minimum-value"
        monkeypatch.setenv("BAKUFU_OWNER_API_TOKEN", token)
        monkeypatch.setenv("BAKUFU_OWNER_ID", str(owner_id))

        subject = await get_external_review_subject(f"Bearer {token}")

        assert subject.owner_id == owner_id

    async def test_resolver_rejects_short_token(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-UT-ERG-HTTP-012: 設定 token が短ければ一致しても 401。"""
        from bakufu.interfaces.http.dependencies import get_external_review_subject

        monkeypatch.setenv("BAKUFU_OWNER_API_TOKEN", "short-token")
        monkeypatch.setenv("BAKUFU_OWNER_ID", str(uuid4()))

        with pytest.raises(HTTPException) as exc_info:
            await get_external_review_subject("Bearer short-token")

        assert exc_info.value.status_code == 401

    async def test_resolver_rejects_mismatched_token_without_echoing_secret(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-UT-ERG-HTTP-012: 不一致 token は入力値を例外 detail に出さない。"""
        from bakufu.interfaces.http.dependencies import get_external_review_subject

        monkeypatch.setenv("BAKUFU_OWNER_API_TOKEN", "owner-api-token-32-bytes-minimum-value")
        monkeypatch.setenv("BAKUFU_OWNER_ID", str(uuid4()))

        with pytest.raises(HTTPException) as exc_info:
            await get_external_review_subject("Bearer attacker-token-32-bytes-value")

        assert "attacker-token" not in str(exc_info.value.detail)

    async def test_resolver_rejects_invalid_owner_uuid(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-UT-ERG-HTTP-012: token 一致でも owner UUID 不正なら 401。"""
        from bakufu.interfaces.http.dependencies import get_external_review_subject

        token = "owner-api-token-32-bytes-minimum-value"
        monkeypatch.setenv("BAKUFU_OWNER_API_TOKEN", token)
        monkeypatch.setenv("BAKUFU_OWNER_ID", "not-a-uuid")

        with pytest.raises(HTTPException) as exc_info:
            await get_external_review_subject(f"Bearer {token}")

        assert exc_info.value.status_code == 401
