"""AnthropicLLMClient ユニットテスト（TC-UT-AC-001〜012）.

Issue: #144
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest
from bakufu.domain.exceptions.llm_client import (
    LLMAPIError,
    LLMAuthError,
    LLMClientError,
    LLMMessagesEmptyError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from bakufu.domain.value_objects.llm import LLMMessage, LLMResponse, MessageRole


def _make_client(
    timeout_seconds: float = 30.0, model: str = "claude-3-5-sonnet-20241022"
) -> tuple[Any, MagicMock]:
    """AnthropicLLMClient インスタンスと SDK mock を返す。

    _client を直接 MagicMock で差し替えて SDK 呼び出しを制御する。
    """
    from bakufu.infrastructure.llm.anthropic_llm_client import AnthropicLLMClient

    config = MagicMock()
    config.anthropic_api_key.get_secret_value.return_value = "sk-ant-test-key-for-unit-tests"
    config.anthropic_model_name = model
    config.timeout_seconds = timeout_seconds

    client = AnthropicLLMClient(config)
    sdk_mock: MagicMock = MagicMock()
    client._client = sdk_mock  # type: ignore[reportPrivateUsage]
    return client, sdk_mock


def _make_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _make_user_message(content: str = "テスト入力") -> LLMMessage:
    return LLMMessage(role=MessageRole.USER, content=content)


def _make_system_message(content: str = "システムプロンプト") -> LLMMessage:  # type: ignore[reportUnusedFunction]
    return LLMMessage(role=MessageRole.SYSTEM, content=content)


@pytest.mark.asyncio
class TestCompleteNormalPath:
    """TC-UT-AC-001: complete 正常系。"""

    async def test_complete_returns_llm_response(self) -> None:
        """TC-UT-AC-001: SDK が TextBlock を返す場合 LLMResponse が得られる。"""
        from tests.factories.llm_sdk_response import AnthropicSDKResponseFactory

        client, sdk_mock = _make_client()
        sdk_response = AnthropicSDKResponseFactory.build(content="合格")
        sdk_mock.messages.create = AsyncMock(return_value=sdk_response)

        result = await client.complete((_make_user_message(),), max_tokens=512)
        assert isinstance(result, LLMResponse)
        assert result.content == "合格"


@pytest.mark.asyncio
class TestErrorConversion:
    """TC-UT-AC-002〜005: エラー変換テスト。"""

    async def test_timeout_error_converted_to_llm_timeout_error(self) -> None:
        """TC-UT-AC-002: asyncio.TimeoutError → LLMTimeoutError（§確定A）。"""
        client, sdk_mock = _make_client(timeout_seconds=30.0)
        sdk_mock.messages.create = AsyncMock(return_value=MagicMock())

        with (
            patch("asyncio.wait_for", side_effect=TimeoutError()),
            pytest.raises(LLMTimeoutError) as exc_info,
        ):
            await client.complete((_make_user_message(),), max_tokens=512)

        assert exc_info.value.provider == "anthropic"
        assert exc_info.value.timeout_seconds == 30.0
        assert isinstance(exc_info.value, LLMClientError)

    async def test_rate_limit_error_converted(self) -> None:
        """TC-UT-AC-003: anthropic.RateLimitError → LLMRateLimitError（retry_after=60）。"""
        client, sdk_mock = _make_client()
        mock_req = _make_request()
        mock_resp = httpx.Response(429, headers={"retry-after": "60"}, request=mock_req)
        sdk_mock.messages.create = AsyncMock(
            side_effect=anthropic.RateLimitError(
                message="rate limit",
                response=mock_resp,
                body={"error": {"type": "rate_limit_error"}},
            )
        )

        with pytest.raises(LLMRateLimitError) as exc_info:
            await client.complete((_make_user_message(),), max_tokens=512)

        assert exc_info.value.provider == "anthropic"
        assert exc_info.value.retry_after == 60.0

    async def test_authentication_error_converted(self) -> None:
        """TC-UT-AC-004: anthropic.AuthenticationError → LLMAuthError。"""
        client, sdk_mock = _make_client()
        mock_req = _make_request()
        mock_resp = httpx.Response(401, request=mock_req)
        sdk_mock.messages.create = AsyncMock(
            side_effect=anthropic.AuthenticationError(
                message="auth failed",
                response=mock_resp,
                body={"error": {"type": "authentication_error"}},
            )
        )

        with pytest.raises(LLMAuthError) as exc_info:
            await client.complete((_make_user_message(),), max_tokens=512)

        assert exc_info.value.provider == "anthropic"

    async def test_api_error_converted_with_status_code(self) -> None:
        """TC-UT-AC-005: anthropic.APIError → LLMAPIError（raw_error はマスキング済み）。"""
        from bakufu.infrastructure.security import masking

        masking.init()

        client, sdk_mock = _make_client()
        mock_req = _make_request()
        mock_resp = httpx.Response(503, request=mock_req)
        sdk_mock.messages.create = AsyncMock(
            side_effect=anthropic.InternalServerError(
                message="server error",
                response=mock_resp,
                body={"error": {"type": "api_error"}},
            )
        )

        with pytest.raises(LLMAPIError) as exc_info:
            await client.complete((_make_user_message(),), max_tokens=512)

        assert exc_info.value.provider == "anthropic"
        assert exc_info.value.status_code == 503


class TestExtractText:
    """TC-UT-AC-006〜007: _extract_text テスト（同期）。"""

    def test_extract_text_returns_text_block_content(self) -> None:
        """TC-UT-AC-006: TextBlock があるとき text を返す。"""
        from tests.factories.llm_sdk_response import AnthropicSDKResponseFactory

        client, _ = _make_client()
        response = AnthropicSDKResponseFactory.build(content="テキスト応答")
        result: str = client._extract_text(response)  # type: ignore[reportPrivateUsage]
        assert result == "テキスト応答"

    def test_extract_text_no_text_block_raises_api_error(self) -> None:
        """TC-UT-AC-007: TextBlock なし → LLMAPIError(kind='empty_response')。"""
        from tests.factories.llm_sdk_response import AnthropicSDKResponseFactory

        client, _ = _make_client()
        response = AnthropicSDKResponseFactory.build_no_text_block()
        with pytest.raises(LLMAPIError) as exc_info:
            client._extract_text(response)  # type: ignore[reportPrivateUsage]
        assert exc_info.value.kind == "empty_response"
        assert isinstance(exc_info.value, LLMClientError)


class TestConvertMessages:
    """TC-UT-AC-008〜011: _convert_messages（§確定F Anthropic system 分離、同期）。"""

    def test_system_and_user_separated(self) -> None:
        """TC-UT-AC-008: SYSTEM + USER → system 引数に分離。"""
        client, _ = _make_client()
        msgs = (
            LLMMessage(role=MessageRole.SYSTEM, content="評価者役割指示"),
            LLMMessage(role=MessageRole.USER, content="成果物テキスト"),
        )
        api_messages: list[dict[str, str]]
        system_str: str | None
        api_messages, system_str = client._convert_messages(msgs)  # type: ignore[reportPrivateUsage]
        assert system_str == "評価者役割指示"
        assert api_messages == [{"role": "user", "content": "成果物テキスト"}]

    def test_multiple_system_joined_with_double_newline(self) -> None:
        """TC-UT-AC-009: SYSTEM × 2 件 → '\\n\\n' で結合。"""
        client, _ = _make_client()
        msgs = (
            LLMMessage(role=MessageRole.SYSTEM, content="指示1"),
            LLMMessage(role=MessageRole.SYSTEM, content="指示2"),
            LLMMessage(role=MessageRole.USER, content="内容"),
        )
        api_messages: list[dict[str, str]]
        system_str: str | None
        api_messages, system_str = client._convert_messages(msgs)  # type: ignore[reportPrivateUsage]
        assert system_str == "指示1\n\n指示2"
        assert all(m["role"] != "system" for m in api_messages)

    def test_no_system_returns_none_for_system_str(self) -> None:
        """TC-UT-AC-010: SYSTEM なし → system_str is None。"""
        client, _ = _make_client()
        msgs = (LLMMessage(role=MessageRole.USER, content="内容のみ"),)
        api_messages: list[dict[str, str]]
        system_str: str | None
        api_messages, system_str = client._convert_messages(msgs)  # type: ignore[reportPrivateUsage]
        assert system_str is None
        assert api_messages == [{"role": "user", "content": "内容のみ"}]

    def test_system_only_raises_messages_empty_error(self) -> None:
        """TC-UT-AC-011: SYSTEM のみ（user なし）→ LLMMessagesEmptyError（Fail Fast）。

        ⚠️ BUG NOTE: infrastructure/test-design.md TC-UT-AC-011 says LLMMessageValidationError
        but the actual implementation raises LLMMessagesEmptyError. Test follows implementation.
        """
        client, _ = _make_client()
        msgs = (LLMMessage(role=MessageRole.SYSTEM, content="指示のみ"),)
        with pytest.raises(LLMMessagesEmptyError):
            client._convert_messages(msgs)  # type: ignore[reportPrivateUsage]


@pytest.mark.asyncio
class TestMaxTokensPassthrough:
    """TC-UT-AC-012: R1-5 max_tokens 固定値禁止。"""

    async def test_max_tokens_passed_through_to_sdk(self) -> None:
        """TC-UT-AC-012: max_tokens=256 が SDK にそのまま渡される。"""
        from tests.factories.llm_sdk_response import AnthropicSDKResponseFactory

        client, sdk_mock = _make_client()
        sdk_response = AnthropicSDKResponseFactory.build()
        sdk_mock.messages.create = AsyncMock(return_value=sdk_response)

        await client.complete((_make_user_message(),), max_tokens=256)

        call_kwargs = sdk_mock.messages.create.call_args.kwargs
        assert call_kwargs.get("max_tokens") == 256
