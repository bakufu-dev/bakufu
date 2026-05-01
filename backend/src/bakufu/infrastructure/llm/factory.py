"""llm_client_factory — LLMClientConfig から適切なクライアントを生成するファクトリ。

設計書: docs/features/llm-client/infrastructure/detailed-design.md §確定 C
"""

from __future__ import annotations

from bakufu.application.ports.llm_client import AbstractLLMClient
from bakufu.infrastructure.llm.anthropic_llm_client import AnthropicLLMClient
from bakufu.infrastructure.llm.config import LLMClientConfig, LLMConfigError, LLMProviderEnum
from bakufu.infrastructure.llm.openai_llm_client import OpenAILLMClient

# MSG-LC-009: 未知のプロバイダ
_MSG_LC_009_TEMPLATE = (
    "[FAIL] Unknown LLM provider: {provider}. Supported: anthropic, openai.\n"
    "Next: Set BAKUFU_LLM_PROVIDER=anthropic or BAKUFU_LLM_PROVIDER=openai."
)


def llm_client_factory(config: LLMClientConfig) -> AbstractLLMClient:
    """LLMClientConfig に基づいて適切な LLM クライアントを返す。

    Args:
        config: LLMClientConfig インスタンス（provider が確定済み）。

    Returns:
        AbstractLLMClient を満たすインスタンス。

    Raises:
        LLMConfigError: 未知のプロバイダが指定された場合（MSG-LC-009）。
    """
    if config.provider == LLMProviderEnum.ANTHROPIC:
        return AnthropicLLMClient(config)
    if config.provider == LLMProviderEnum.OPENAI:
        return OpenAILLMClient(config)

    # enum 拡張時の将来防止（網羅性チェック）
    raise LLMConfigError(
        message=_MSG_LC_009_TEMPLATE.format(provider=config.provider.value),
        field="bakufu_llm_provider",
    )
