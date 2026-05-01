"""セキュリティテスト — §確定E / T2 APIキー漏洩防止（TC-UT-SEC-001〜002）.

Issue: #144
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import openai
import pytest
from bakufu.domain.exceptions.llm_client import LLMAPIError
from bakufu.infrastructure.security import masking


@pytest.fixture(autouse=True)
def _init_masking(monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[reportUnusedFunction]
    """masking を初期化してテスト内で mask() が機能するようにする。"""
    _ant_key = "sk-ant-api03-REALKEYVALUE12345678901234567890123456789012"
    _oai_key = "sk-REALKEYVALUE123456789012345678901234567890"
    monkeypatch.setenv("BAKUFU_ANTHROPIC_API_KEY", _ant_key)
    monkeypatch.setenv("BAKUFU_OPENAI_API_KEY", _oai_key)
    masking.init()


@pytest.mark.asyncio
class TestApiKeyNotLeakedInRawError:
    """TC-UT-SEC-001〜002: LLMAPIError.raw_error に API キーが含まれない。"""

    async def test_anthropic_api_error_raw_error_is_masked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-UT-SEC-001: Anthropic APIError.raw_error に API キーが含まれない（§確定E / T2）。"""
        from bakufu.domain.value_objects.llm import LLMMessage, MessageRole
        from bakufu.infrastructure.llm.anthropic_llm_client import AnthropicLLMClient

        api_key = "sk-ant-api03-REALKEYVALUE12345678901234567890123456789012"
        config = MagicMock()
        config.anthropic_api_key.get_secret_value.return_value = api_key
        config.anthropic_model_name = "claude-3-5-sonnet-20241022"
        config.timeout_seconds = 30.0

        client = AnthropicLLMClient(config)
        sdk_mock: MagicMock = MagicMock()
        client._client = sdk_mock  # type: ignore[reportPrivateUsage]

        mock_req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        mock_resp = httpx.Response(500, request=mock_req)
        # API キーを含むエラーメッセージをシミュレート
        error_msg = f"API error: key={api_key}, status=500"
        sdk_mock.messages.create = AsyncMock(
            side_effect=anthropic.InternalServerError(
                message=error_msg, response=mock_resp, body={"error": {"type": "api_error"}}
            )
        )

        llm_msg = LLMMessage(role=MessageRole.USER, content="test")

        with pytest.raises(LLMAPIError) as exc_info:
            await client.complete((llm_msg,), max_tokens=100)

        # raw_error に API キーが含まれていないこと（§確定E）
        assert api_key not in exc_info.value.raw_error

    async def test_openai_api_error_raw_error_is_masked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-UT-SEC-002: OpenAI APIError.raw_error に API キーが含まれない（§確定E / T2）。"""
        from bakufu.domain.value_objects.llm import LLMMessage, MessageRole
        from bakufu.infrastructure.llm.openai_llm_client import OpenAILLMClient

        api_key = "sk-REALKEYVALUE123456789012345678901234567890"
        config = MagicMock()
        config.openai_api_key.get_secret_value.return_value = api_key
        config.openai_model_name = "gpt-4o-mini"
        config.timeout_seconds = 30.0

        client = OpenAILLMClient(config)
        sdk_mock: MagicMock = MagicMock()
        client._client = sdk_mock  # type: ignore[reportPrivateUsage]

        mock_req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        mock_resp = httpx.Response(500, request=mock_req)
        error_msg = f"API error: key={api_key}, status=500"
        sdk_mock.chat.completions.create = AsyncMock(
            side_effect=openai.InternalServerError(
                message=error_msg, response=mock_resp, body={"error": {"type": "server_error"}}
            )
        )

        llm_msg = LLMMessage(role=MessageRole.USER, content="test")

        with pytest.raises(LLMAPIError) as exc_info:
            await client.complete((llm_msg,), max_tokens=100)

        assert api_key not in exc_info.value.raw_error
