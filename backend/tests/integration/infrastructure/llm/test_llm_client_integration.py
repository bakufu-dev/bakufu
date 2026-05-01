"""LLM クライアント結合テスト（TC-IT-LC-001〜003）.

Issue: #144
raw fixture を SDK mock の return_value に設定して factory → client → complete のフローを検証する。
ユニットテストとの違い: factory 由来合成データは使わない。raw fixture のみ使用。
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import anthropic.types
import openai.types.chat
import pytest
from bakufu.domain.value_objects.llm import LLMMessage, LLMResponse, MessageRole

_FIXTURES_DIR = Path(__file__).parents[3] / "fixtures" / "characterization" / "raw" / "llm_client"


def _load_fixture(name: str) -> dict:
    path = _FIXTURES_DIR / name
    assert path.exists(), f"Raw fixture が存在しない: {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "_meta" in data, f"_meta キーが欠落: {path}"
    return data


@pytest.mark.asyncio
class TestAnthropicIntegration:
    """TC-IT-LC-001: factory → AnthropicLLMClient → complete（raw fixture 使用）。"""

    async def test_complete_with_raw_fixture(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-IT-LC-001: raw fixture から SDK オブジェクトを再構築して complete を検証。"""
        for var in ["BAKUFU_LLM_PROVIDER", "BAKUFU_ANTHROPIC_API_KEY",
                    "BAKUFU_ANTHROPIC_MODEL_NAME", "BAKUFU_OPENAI_API_KEY"]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("BAKUFU_ANTHROPIC_API_KEY", "sk-ant-test-integration")

        from bakufu.infrastructure.llm.config import LLMClientConfig
        from bakufu.infrastructure.llm.factory import llm_client_factory

        config = LLMClientConfig()
        client = llm_client_factory(config)

        # raw fixture から SDK オブジェクトを再構築（_meta を除いた部分で model_validate）
        raw = _load_fixture("anthropic_complete_success.json")
        sdk_data = {k: v for k, v in raw.items() if k != "_meta"}
        sdk_response = anthropic.types.Message.model_validate(sdk_data)

        # SDK client を mock に差し替え
        sdk_mock = MagicMock()
        sdk_mock.messages.create = AsyncMock(return_value=sdk_response)
        client._client = sdk_mock  # type: ignore[attr-defined]

        messages = (LLMMessage(role=MessageRole.USER, content="テスト入力"),)
        result = await client.complete(messages, max_tokens=512)

        assert isinstance(result, LLMResponse)
        assert len(result.content) > 0
        assert result.content == raw["content"][0]["text"]


@pytest.mark.asyncio
class TestOpenAIIntegration:
    """TC-IT-LC-002: factory → OpenAILLMClient → complete（raw fixture 使用）。"""

    async def test_complete_with_raw_fixture(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-IT-LC-002: raw fixture から SDK オブジェクトを再構築して complete を検証。"""
        for var in ["BAKUFU_LLM_PROVIDER", "BAKUFU_ANTHROPIC_API_KEY",
                    "BAKUFU_OPENAI_API_KEY", "BAKUFU_OPENAI_MODEL_NAME"]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "openai")
        monkeypatch.setenv("BAKUFU_OPENAI_API_KEY", "sk-test-openai-integration")

        from bakufu.infrastructure.llm.config import LLMClientConfig
        from bakufu.infrastructure.llm.factory import llm_client_factory

        config = LLMClientConfig()
        client = llm_client_factory(config)

        raw = _load_fixture("openai_complete_success.json")
        sdk_data = {k: v for k, v in raw.items() if k != "_meta"}
        sdk_response = openai.types.chat.ChatCompletion.model_validate(sdk_data)

        sdk_mock = MagicMock()
        sdk_mock.chat.completions.create = AsyncMock(return_value=sdk_response)
        client._client = sdk_mock  # type: ignore[attr-defined]

        messages = (LLMMessage(role=MessageRole.USER, content="テスト入力"),)
        result = await client.complete(messages, max_tokens=512)

        assert isinstance(result, LLMResponse)
        assert len(result.content) > 0
        assert result.content == raw["choices"][0]["message"]["content"]


class TestProviderSwitching:
    """TC-IT-LC-003: プロバイダ切り替え確認。"""

    def test_provider_switch_returns_different_client_types(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-IT-LC-003: anthropic → AnthropicLLMClient、openai → OpenAILLMClient。"""
        from bakufu.infrastructure.llm.anthropic_llm_client import AnthropicLLMClient
        from bakufu.infrastructure.llm.config import LLMClientConfig
        from bakufu.infrastructure.llm.factory import llm_client_factory
        from bakufu.infrastructure.llm.openai_llm_client import OpenAILLMClient

        for var in ["BAKUFU_LLM_PROVIDER", "BAKUFU_ANTHROPIC_API_KEY",
                    "BAKUFU_OPENAI_API_KEY", "BAKUFU_ANTHROPIC_MODEL_NAME",
                    "BAKUFU_OPENAI_MODEL_NAME", "BAKUFU_LLM_TIMEOUT_SECONDS"]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("BAKUFU_ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("BAKUFU_OPENAI_API_KEY", "sk-test")
        config_ant = LLMClientConfig()
        client_ant = llm_client_factory(config_ant)
        assert isinstance(client_ant, AnthropicLLMClient)

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "openai")
        config_oai = LLMClientConfig()
        client_oai = llm_client_factory(config_oai)
        assert isinstance(client_oai, OpenAILLMClient)
