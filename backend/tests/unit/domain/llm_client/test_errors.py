"""LLMClientError 例外階層テスト（TC-UT-ERR-001〜011）.

Issue: #144
"""

from __future__ import annotations

from bakufu.domain.exceptions.llm_client import (
    LLMAPIError,
    LLMAuthError,
    LLMClientError,
    LLMMessageValidationError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class TestIsARelationships:
    """TC-UT-ERR-001〜005: 各例外が LLMClientError のサブクラスであること。"""

    def test_timeout_error_is_llm_client_error(self) -> None:
        """TC-UT-ERR-001: LLMTimeoutError is-a LLMClientError。"""
        exc = LLMTimeoutError(message="timeout", provider="anthropic", timeout_seconds=30.0)
        assert isinstance(exc, LLMClientError)

    def test_rate_limit_error_is_llm_client_error(self) -> None:
        """TC-UT-ERR-002: LLMRateLimitError is-a LLMClientError。"""
        exc = LLMRateLimitError(message="rate limit", provider="anthropic", retry_after=None)
        assert isinstance(exc, LLMClientError)

    def test_auth_error_is_llm_client_error(self) -> None:
        """TC-UT-ERR-003: LLMAuthError is-a LLMClientError。"""
        exc = LLMAuthError(message="auth failed", provider="anthropic")
        assert isinstance(exc, LLMClientError)

    def test_api_error_is_llm_client_error(self) -> None:
        """TC-UT-ERR-004: LLMAPIError is-a LLMClientError。"""
        exc = LLMAPIError(message="api error", provider="openai")
        assert isinstance(exc, LLMClientError)

    def test_message_validation_error_is_llm_client_error(self) -> None:
        """TC-UT-ERR-005: LLMMessageValidationError is-a LLMClientError。"""
        exc = LLMMessageValidationError(message="validation", provider="anthropic", field="content")
        assert isinstance(exc, LLMClientError)


class TestAdditionalAttributes:
    """TC-UT-ERR-006〜011: 各例外クラスの追加属性の確認。"""

    def test_timeout_error_has_timeout_seconds(self) -> None:
        """TC-UT-ERR-006: LLMTimeoutError.timeout_seconds == 30.0。"""
        exc = LLMTimeoutError(message="timeout", provider="anthropic", timeout_seconds=30.0)
        assert exc.timeout_seconds == 30.0

    def test_rate_limit_error_retry_after_none(self) -> None:
        """TC-UT-ERR-007: LLMRateLimitError.retry_after が None の場合。"""
        exc = LLMRateLimitError(message="rate limit", provider="anthropic", retry_after=None)
        assert exc.retry_after is None

    def test_rate_limit_error_retry_after_float(self) -> None:
        """TC-UT-ERR-008: LLMRateLimitError.retry_after が float の場合。"""
        exc = LLMRateLimitError(message="rate limit", provider="anthropic", retry_after=60.0)
        assert exc.retry_after == 60.0

    def test_api_error_has_status_code_and_raw_error(self) -> None:
        """TC-UT-ERR-009: LLMAPIError.status_code / raw_error を持つ。"""
        exc = LLMAPIError(
            message="api error", provider="openai", status_code=500, raw_error="masked error"
        )
        assert exc.status_code == 500
        assert exc.raw_error == "masked error"

    def test_api_error_status_code_can_be_none(self) -> None:
        """TC-UT-ERR-010: LLMAPIError.status_code が None の境界値。"""
        exc = LLMAPIError(message="api error", provider="openai", status_code=None, raw_error="err")
        assert exc.status_code is None

    def test_message_validation_error_has_field(self) -> None:
        """TC-UT-ERR-011: LLMMessageValidationError.field を持つ。"""
        exc = LLMMessageValidationError(message="validation", provider="anthropic", field="content")
        assert exc.field == "content"
