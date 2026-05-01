"""LLMClientConfig — LLM クライアント設定（pydantic-settings ベース）。

環境変数から設定を読み込む。プロバイダ別に独立した API キーとモデル名を持つ。
LLMConfigError は LLMClientError とは別系統（Exception 直接継承）。

設計書: docs/features/llm-client/infrastructure/detailed-design.md §確定 C
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProviderEnum(StrEnum):
    """LLM プロバイダ種別（§確定 C）。

    Phase 1: anthropic / openai の 2 値に閉じる。
    Phase 2 追加時は enum 値と factory 分岐を拡張する。
    """

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class LLMConfigError(Exception):
    """LLM 設定不備エラー（§確定 C）。

    LLMClientError とは別系統（Exception 直接継承）。
    起動時の設定チェック失敗を表し、実行時 API 呼び出しエラーとは区別する。
    """

    def __init__(self, *, message: str, field: str) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


# MSG-LC-007: BAKUFU_LLM_PROVIDER 未設定
_MSG_LC_007 = (
    "[FAIL] BAKUFU_LLM_PROVIDER is not set.\n"
    "Next: Set BAKUFU_LLM_PROVIDER=anthropic or BAKUFU_LLM_PROVIDER=openai."
)

# MSG-LC-008: 選択プロバイダの API キー未設定（{provider.upper()} は展開時に upper() を適用）
_MSG_LC_008_TEMPLATE = (
    "[FAIL] API key for provider={provider} is not set.\n"
    "Next: Set BAKUFU_{PROVIDER}_API_KEY to a valid API key."
)


class LLMClientConfig(BaseSettings):
    """LLM クライアント設定（§確定 C）。

    全フィールドは環境変数から読み込む。
    provider に応じた API キーが未設定の場合は LLMConfigError を raise する。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # プロバイダ選択（必須）
    bakufu_llm_provider: LLMProviderEnum

    # Anthropic 設定
    bakufu_anthropic_api_key: SecretStr | None = None
    bakufu_anthropic_model_name: str = "claude-3-5-sonnet-20241022"

    # OpenAI 設定
    bakufu_openai_api_key: SecretStr | None = None
    bakufu_openai_model_name: str = "gpt-4o-mini"

    # 共通設定
    bakufu_llm_timeout_seconds: float = 30.0

    @property
    def provider(self) -> LLMProviderEnum:
        """プロバイダ種別のショートカット。"""
        return self.bakufu_llm_provider

    @property
    def anthropic_api_key(self) -> SecretStr | None:
        """Anthropic API キーのショートカット。"""
        return self.bakufu_anthropic_api_key

    @property
    def openai_api_key(self) -> SecretStr | None:
        """OpenAI API キーのショートカット。"""
        return self.bakufu_openai_api_key

    @property
    def anthropic_model_name(self) -> str:
        """Anthropic モデル名のショートカット。"""
        return self.bakufu_anthropic_model_name

    @property
    def openai_model_name(self) -> str:
        """OpenAI モデル名のショートカット。"""
        return self.bakufu_openai_model_name

    @property
    def timeout_seconds(self) -> float:
        """タイムアウト秒数のショートカット。"""
        return self.bakufu_llm_timeout_seconds

    @model_validator(mode="after")
    def _validate_api_key_for_provider(self) -> LLMClientConfig:
        """選択プロバイダの API キーが設定されているか検証する（Fail Fast）。

        MSG-LC-008: プロバイダが選択されているのに API キーが未設定の場合に
        LLMConfigError を raise する。
        """
        if self.provider == LLMProviderEnum.ANTHROPIC and self.anthropic_api_key is None:
            provider = self.provider.value
            raise LLMConfigError(
                message=_MSG_LC_008_TEMPLATE.format(
                    provider=provider,
                    PROVIDER=provider.upper(),
                ),
                field="bakufu_anthropic_api_key",
            )
        if self.provider == LLMProviderEnum.OPENAI and self.openai_api_key is None:
            provider = self.provider.value
            raise LLMConfigError(
                message=_MSG_LC_008_TEMPLATE.format(
                    provider=provider,
                    PROVIDER=provider.upper(),
                ),
                field="bakufu_openai_api_key",
            )
        return self


__all__ = [
    "LLMClientConfig",
    "LLMConfigError",
    "LLMProviderEnum",
]
