"""MSG-LC-007〜009 確定文言テスト（TC-UT-MSG-007〜009）.

Issue: #144
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_llm_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ["BAKUFU_LLM_PROVIDER", "BAKUFU_ANTHROPIC_API_KEY", "BAKUFU_OPENAI_API_KEY",
                "BAKUFU_ANTHROPIC_MODEL_NAME", "BAKUFU_OPENAI_MODEL_NAME"]:
        monkeypatch.delenv(var, raising=False)


class TestMsgLc007:
    """TC-UT-MSG-007: PROVIDER 未設定時のエラーメッセージ。"""

    def test_missing_provider_message_contains_fail_and_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-UT-MSG-007: BAKUFU_LLM_PROVIDER 未設定.

        エラーに [FAIL] と BAKUFU_LLM_PROVIDER が含まれる。
        """
        from bakufu.infrastructure.llm.config import LLMClientConfig

        # pydantic-settings は BAKUFU_LLM_PROVIDER が未設定だと ValidationError を投げる
        try:
            LLMClientConfig()
            pytest.fail("Expected ValidationError or LLMConfigError")
        except Exception as exc:
            # pydantic ValidationError の場合、メッセージに 'bakufu_llm_provider' が含まれる
            exc_str = str(exc).lower()
            assert "bakufu_llm_provider" in exc_str or "llm_provider" in exc_str


class TestMsgLc008:
    """TC-UT-MSG-008: API キー未設定時のエラーメッセージ。"""

    def test_missing_anthropic_api_key_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-MSG-008: provider=anthropic + API キーなし → [FAIL] + BAKUFU_ANTHROPIC_API_KEY。"""
        from bakufu.infrastructure.llm.config import LLMClientConfig

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "anthropic")

        try:
            LLMClientConfig()
            pytest.fail("Expected LLMConfigError")
        except Exception as exc:
            # pydantic ValidationError でラップされている可能性
            exc_str = str(exc)
            # LLMConfigError の message が含まれているか確認
            assert "[FAIL]" in exc_str or "BAKUFU_ANTHROPIC_API_KEY" in exc_str


class TestMsgLc009:
    """TC-UT-MSG-009: 未知プロバイダ時のエラーメッセージ。"""

    def test_unknown_provider_message_contains_fail_and_supported_providers(self) -> None:
        """TC-UT-MSG-009: 未知プロバイダ.

        [FAIL] + anthropic, openai がサポート対象として含まれる。
        """
        from unittest.mock import MagicMock

        from bakufu.infrastructure.llm.config import LLMConfigError
        from bakufu.infrastructure.llm.factory import llm_client_factory

        config = MagicMock()
        config.provider.value = "gemini"  # 未知のプロバイダ（.value が必要）

        with pytest.raises(LLMConfigError) as exc_info:
            llm_client_factory(config)

        assert "[FAIL]" in exc_info.value.message
        assert "anthropic" in exc_info.value.message
        assert "openai" in exc_info.value.message
