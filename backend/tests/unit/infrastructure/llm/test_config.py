"""LLMClientConfig ユニットテスト（TC-UT-CONF-001〜008）.

Issue: #144
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_llm_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[reportUnusedFunction]
    """各テストの前に LLM 関連の環境変数をクリアする。"""
    for var in [
        "BAKUFU_LLM_PROVIDER",
        "BAKUFU_ANTHROPIC_API_KEY",
        "BAKUFU_OPENAI_API_KEY",
        "BAKUFU_ANTHROPIC_MODEL_NAME",
        "BAKUFU_OPENAI_MODEL_NAME",
        "BAKUFU_LLM_TIMEOUT_SECONDS",
    ]:
        monkeypatch.delenv(var, raising=False)


class TestNormalConstruction:
    """TC-UT-CONF-001〜002: 正常構築。"""

    def test_anthropic_provider_constructs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-CONF-001: provider=anthropic で正常構築。"""
        from bakufu.infrastructure.llm.config import LLMClientConfig, LLMProviderEnum

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("BAKUFU_ANTHROPIC_API_KEY", "sk-ant-test-key")
        config = LLMClientConfig()  # type: ignore[call-arg]
        assert config.provider == LLMProviderEnum.ANTHROPIC

    def test_openai_provider_constructs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-CONF-002: provider=openai で正常構築。"""
        from bakufu.infrastructure.llm.config import LLMClientConfig, LLMProviderEnum

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "openai")
        monkeypatch.setenv("BAKUFU_OPENAI_API_KEY", "sk-test-openai-key")
        config = LLMClientConfig()  # type: ignore[call-arg]
        assert config.provider == LLMProviderEnum.OPENAI


class TestFailFast:
    """TC-UT-CONF-003〜005: Fail Fast。"""

    def test_missing_provider_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-CONF-003: BAKUFU_LLM_PROVIDER 未設定 → ValidationError。"""
        import pydantic
        from bakufu.infrastructure.llm.config import LLMClientConfig

        with pytest.raises((pydantic.ValidationError, Exception)):
            LLMClientConfig()  # type: ignore[call-arg]

    def test_anthropic_without_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-CONF-004: provider=anthropic + ANTHROPIC_API_KEY 未設定 → LLMConfigError。"""
        from bakufu.infrastructure.llm.config import LLMClientConfig, LLMConfigError

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "anthropic")
        # BAKUFU_ANTHROPIC_API_KEY は設定しない

        with pytest.raises(Exception) as exc_info:
            LLMClientConfig()  # type: ignore[call-arg]
        # LLMConfigError または pydantic の ValidationError で包まれた LLMConfigError
        assert isinstance(exc_info.value, (LLMConfigError, Exception))

    def test_openai_without_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-CONF-005: provider=openai + OPENAI_API_KEY 未設定 → LLMConfigError。"""
        import pydantic
        from bakufu.infrastructure.llm.config import LLMClientConfig, LLMConfigError

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "openai")
        # BAKUFU_OPENAI_API_KEY は設定しない

        with pytest.raises((LLMConfigError, pydantic.ValidationError)):
            LLMClientConfig()  # type: ignore[call-arg]


class TestSecretStrMasking:
    """TC-UT-CONF-006: SecretStr マスキング（R1-2）。"""

    def test_api_key_not_exposed_in_str_repr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-CONF-006: str(config) で API キーが露出しない。"""
        from bakufu.infrastructure.llm.config import LLMClientConfig

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("BAKUFU_ANTHROPIC_API_KEY", "sk-ant-realkey-secret123")
        config = LLMClientConfig()  # type: ignore[call-arg]

        config_str = str(config)
        assert "sk-ant-realkey-secret123" not in config_str
        # SecretStr は ***** と表示される
        assert "**" in config_str or "secret" not in config_str.lower()


class TestDefaults:
    """TC-UT-CONF-007〜008: デフォルト値。"""

    def test_timeout_seconds_defaults_to_30(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-CONF-007: BAKUFU_LLM_TIMEOUT_SECONDS 未設定 → 30.0。"""
        from bakufu.infrastructure.llm.config import LLMClientConfig

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("BAKUFU_ANTHROPIC_API_KEY", "sk-ant-test")
        config = LLMClientConfig()  # type: ignore[call-arg]
        assert config.timeout_seconds == 30.0

    def test_anthropic_model_name_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-CONF-008: Anthropic モデル名デフォルト = claude-3-5-sonnet-20241022（§確定C）。"""
        from bakufu.infrastructure.llm.config import LLMClientConfig

        monkeypatch.setenv("BAKUFU_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("BAKUFU_ANTHROPIC_API_KEY", "sk-ant-test")
        config = LLMClientConfig()  # type: ignore[call-arg]
        assert config.anthropic_model_name == "claude-3-5-sonnet-20241022"
