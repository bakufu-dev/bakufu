"""AbstractLLMClient Protocol 結合テスト（TC-IT-DOMAIN-001〜002）.

Issue: #144
stub + VO 連携 + lifecycle 完走シナリオ。外部 I/O ゼロ。
"""
from __future__ import annotations

import pytest
from bakufu.domain.exceptions.llm_client import LLMClientError, LLMTimeoutError
from bakufu.domain.value_objects.llm import MessageRole

pytestmark = pytest.mark.asyncio


class TestProtocolIntegration:
    """TC-IT-DOMAIN-001〜002: stub + VO 連携シナリオ。"""

    async def test_complete_with_multiple_messages_returns_response(self) -> None:
        """TC-IT-DOMAIN-001: SYSTEM + USER メッセージタプル → stub.complete → LLMResponse。"""
        from tests.factories.llm_client import (
            make_llm_message,
            make_llm_response,
            make_stub_llm_client,
        )

        response = make_llm_response(content="意味検証結果")
        stub = make_stub_llm_client(response=response)

        msgs = (
            make_llm_message(role=MessageRole.SYSTEM, content="評価者としての役割"),
            make_llm_message(role=MessageRole.USER, content="成果物テキスト"),
        )
        result = await stub.complete(msgs, max_tokens=512)

        assert result.content == "意味検証結果"
        stub.complete.assert_called_once_with(msgs, max_tokens=512)

    async def test_error_propagates_as_llm_client_error(self) -> None:
        """TC-IT-DOMAIN-002: stub が LLMTimeoutError を raise.

        LLMClientError として catch 可能。
        """
        from tests.factories.llm_client import (
            make_llm_message,
            make_stub_llm_client_raises,
        )

        exc = LLMTimeoutError(
            message="[FAIL] timeout",
            provider="anthropic",
            timeout_seconds=30.0,
        )
        stub = make_stub_llm_client_raises(exc=exc)

        msgs = (make_llm_message(role=MessageRole.USER, content="テスト"),)

        with pytest.raises(LLMClientError) as exc_info:
            await stub.complete(msgs, max_tokens=512)

        assert isinstance(exc_info.value, LLMTimeoutError)
        assert exc_info.value.timeout_seconds == 30.0
