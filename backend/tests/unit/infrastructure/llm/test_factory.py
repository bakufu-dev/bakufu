"""llm_client_factory ユニットテスト（TC-UT-FAC-001〜004）.

Issue: #144
"""

from __future__ import annotations

import inspect

import pytest


@pytest.fixture(autouse=True)
def _clear_llm_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[reportUnusedFunction]
    for var in [
        "BAKUFU_LLM_PROVIDER",
        "BAKUFU_ANTHROPIC_API_KEY",
        "BAKUFU_OPENAI_API_KEY",
        "BAKUFU_ANTHROPIC_MODEL_NAME",
        "BAKUFU_OPENAI_MODEL_NAME",
        "BAKUFU_LLM_TIMEOUT_SECONDS",
    ]:
        monkeypatch.delenv(var, raising=False)


class TestFactoryProviderSelection:
    """TC-UT-FAC-001〜002: プロバイダ選択。"""

    def test_anthropic_provider_returns_anthropic_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-UT-FAC-001: provider=anthropic → AnthropicLLMClient。"""
        from bakufu.infrastructure.llm.config import LLMClientConfig
        from bakufu.infrastructure.llm.factory import llm_client_factory

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("BAKUFU_ANTHROPIC_API_KEY", "sk-ant-test-key")
        config = LLMClientConfig()  # type: ignore[call-arg]
        client = llm_client_factory(config)
        assert type(client).__name__ == "AnthropicLLMClient"

    def test_openai_provider_returns_openai_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-FAC-002: provider=openai → OpenAILLMClient。"""
        from bakufu.infrastructure.llm.config import LLMClientConfig
        from bakufu.infrastructure.llm.factory import llm_client_factory

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "openai")
        monkeypatch.setenv("BAKUFU_OPENAI_API_KEY", "sk-test-openai-key")
        config = LLMClientConfig()  # type: ignore[call-arg]
        client = llm_client_factory(config)
        assert type(client).__name__ == "OpenAILLMClient"


class TestUnknownProvider:
    """TC-UT-FAC-003: 未知プロバイダ → LLMConfigError。"""

    def test_unknown_provider_raises_llm_config_error(self) -> None:
        """TC-UT-FAC-003: 未知プロバイダ → LLMConfigError (MSG-LC-009)。"""
        from unittest.mock import MagicMock

        from bakufu.infrastructure.llm.config import LLMConfigError
        from bakufu.infrastructure.llm.factory import llm_client_factory

        # provider を enum 外の値に設定した config mock を使用する
        # MagicMock を使い provider.value を直接設定する（文字列では .value が使えないため）
        config = MagicMock()
        config.provider.value = "gemini"  # ANTHROPIC / OPENAI どちらにも一致しない

        with pytest.raises(LLMConfigError) as exc_info:
            llm_client_factory(config)  # type: ignore[arg-type]
        assert "[FAIL]" in exc_info.value.message
        assert "gemini" in exc_info.value.message


class TestProtocolConformance:
    """TC-UT-FAC-004: factory 返り値が AbstractLLMClient Protocol を満たす。"""

    def test_factory_returns_protocol_conformant_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-UT-FAC-004: hasattr(client, 'complete') かつ coroutinefunction。"""
        from bakufu.infrastructure.llm.config import LLMClientConfig
        from bakufu.infrastructure.llm.factory import llm_client_factory

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("BAKUFU_ANTHROPIC_API_KEY", "sk-ant-test")
        config = LLMClientConfig()  # type: ignore[call-arg]
        client = llm_client_factory(config)

        assert hasattr(client, "complete")
        assert inspect.iscoroutinefunction(client.complete)
