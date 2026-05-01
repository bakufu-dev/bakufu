"""OpenAILLMClient ユニットテスト（TC-UT-OC-001〜008）.

Issue: #144
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest
from bakufu.domain.exceptions.llm_client import (
    LLMAPIError,
    LLMAuthError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from bakufu.domain.value_objects.llm import LLMMessage, LLMResponse, MessageRole


def _make_client(timeout_seconds: float = 30.0) -> tuple[Any, MagicMock]:
    """OpenAILLMClient インスタンスと SDK mock を返す。"""
    from bakufu.infrastructure.llm.openai_llm_client import OpenAILLMClient

    config = MagicMock()
    config.openai_api_key.get_secret_value.return_value = "sk-test-openai-key"
    config.openai_model_name = "gpt-4o-mini"
    config.timeout_seconds = timeout_seconds

    client = OpenAILLMClient(config)
    sdk_mock: MagicMock = MagicMock()
    client._client = sdk_mock  # type: ignore[reportPrivateUsage]
    return client, sdk_mock


def _make_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def _make_user_message(content: str = "テスト入力") -> LLMMessage:
    return LLMMessage(role=MessageRole.USER, content=content)


@pytest.mark.asyncio
class TestCompleteNormalPath:
    """TC-UT-OC-001: complete 正常系。"""

    async def test_complete_returns_llm_response(self) -> None:
        """TC-UT-OC-001: SDK が content を返す場合 LLMResponse が得られる。"""
        from tests.factories.llm_sdk_response import OpenAISDKResponseFactory

        client, sdk_mock = _make_client()
        sdk_response = OpenAISDKResponseFactory.build(content="応答")
        sdk_mock.chat.completions.create = AsyncMock(return_value=sdk_response)

        result = await client.complete((_make_user_message(),), max_tokens=1024)
        assert isinstance(result, LLMResponse)
        assert result.content == "応答"


@pytest.mark.asyncio
class TestErrorConversion:
    """TC-UT-OC-002〜005: エラー変換テスト。"""

    async def test_timeout_error_converted(self) -> None:
        """TC-UT-OC-002: asyncio.TimeoutError → LLMTimeoutError。"""
        client, sdk_mock = _make_client(timeout_seconds=30.0)
        sdk_mock.chat.completions.create = AsyncMock(return_value=MagicMock())

        with (
            patch("asyncio.wait_for", side_effect=TimeoutError()),
            pytest.raises(LLMTimeoutError) as exc_info,
        ):
            await client.complete((_make_user_message(),), max_tokens=512)

        assert exc_info.value.provider == "openai"
        assert exc_info.value.timeout_seconds == 30.0

    async def test_rate_limit_error_converted(self) -> None:
        """TC-UT-OC-003: openai.RateLimitError → LLMRateLimitError。"""
        client, sdk_mock = _make_client()
        mock_req = _make_request()
        mock_resp = httpx.Response(429, headers={"retry-after": "60"}, request=mock_req)
        sdk_mock.chat.completions.create = AsyncMock(
            side_effect=openai.RateLimitError(
                message="rate limit", response=mock_resp,
                body={"error": {"type": "requests", "message": "rate limit exceeded"}}
            )
        )

        with pytest.raises(LLMRateLimitError) as exc_info:
            await client.complete((_make_user_message(),), max_tokens=512)

        assert exc_info.value.provider == "openai"
        assert exc_info.value.retry_after == 60.0

    async def test_authentication_error_converted(self) -> None:
        """TC-UT-OC-004: openai.AuthenticationError → LLMAuthError。"""
        client, sdk_mock = _make_client()
        mock_req = _make_request()
        mock_resp = httpx.Response(401, request=mock_req)
        sdk_mock.chat.completions.create = AsyncMock(
            side_effect=openai.AuthenticationError(
                message="invalid auth", response=mock_resp,
                body={"error": {"type": "invalid_api_key"}}
            )
        )

        with pytest.raises(LLMAuthError) as exc_info:
            await client.complete((_make_user_message(),), max_tokens=512)

        assert exc_info.value.provider == "openai"

    async def test_api_error_converted(self) -> None:
        """TC-UT-OC-005: openai.APIError → LLMAPIError。"""
        from bakufu.infrastructure.security import masking
        masking.init()

        client, sdk_mock = _make_client()
        mock_req = _make_request()
        mock_resp = httpx.Response(500, request=mock_req)
        sdk_mock.chat.completions.create = AsyncMock(
            side_effect=openai.InternalServerError(
                message="server error", response=mock_resp,
                body={"error": {"type": "server_error"}}
            )
        )

        with pytest.raises(LLMAPIError) as exc_info:
            await client.complete((_make_user_message(),), max_tokens=512)

        assert exc_info.value.provider == "openai"
        assert exc_info.value.status_code == 500


class TestExtractText:
    """TC-UT-OC-006〜007: _extract_text テスト。"""

    def test_extract_text_with_content(self) -> None:
        """TC-UT-OC-006: content が文字列の場合そのまま返す。"""
        from tests.factories.llm_sdk_response import OpenAISDKResponseFactory

        client, _ = _make_client()
        response = OpenAISDKResponseFactory.build(content="結果テキスト")
        result: str = client._extract_text(response)  # type: ignore[reportPrivateUsage]
        assert result == "結果テキスト"

    def test_extract_text_null_content_raises_api_error(self) -> None:
        """TC-UT-OC-007: content が None → LLMAPIError(kind='empty_response')。

        NOTE: infrastructure/test-design.md TC-UT-OC-007 says LLM_FALLBACK_RESPONSE_TEXT
        is returned, but the actual implementation raises LLMAPIError(kind='empty_response')
        per §確定D Fail Fast design. Test follows the ACTUAL implementation.
        """
        from tests.factories.llm_sdk_response import OpenAISDKResponseFactory

        client, _ = _make_client()
        response = OpenAISDKResponseFactory.build_null_content()
        with pytest.raises(LLMAPIError) as exc_info:
            client._extract_text(response)  # type: ignore[reportPrivateUsage]
        assert exc_info.value.kind == "empty_response"
        assert exc_info.value.provider == "openai"


class TestConvertMessages:
    """TC-UT-OC-008: _convert_messages — system role を messages に含む。"""

    def test_system_role_stays_in_messages(self) -> None:
        """TC-UT-OC-008: OpenAI は system を messages リストに含める（Anthropic と異なる）。"""
        client, _ = _make_client()
        msgs = (
            LLMMessage(role=MessageRole.SYSTEM, content="指示"),
            LLMMessage(role=MessageRole.USER, content="内容"),
        )
        result: list[dict[str, str]] = client._convert_messages(msgs)  # type: ignore[reportPrivateUsage]
        assert result == [
            {"role": "system", "content": "指示"},
            {"role": "user", "content": "内容"},
        ]
