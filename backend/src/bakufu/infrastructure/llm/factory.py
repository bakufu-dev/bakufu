"""llm_client_factory — LLMClientConfig から適切なクライアントを生成するファクトリ。

設計書: docs/features/llm-client/infrastructure/detailed-design.md §確定 C
"""

from __future__ import annotations

from bakufu.application.ports.llm_client import AbstractLLMClient
from bakufu.application.ports.llm_provider_port import LLMProviderPort
from bakufu.infrastructure.llm.anthropic_llm_client import AnthropicLLMClient
from bakufu.infrastructure.llm.claude_code_llm_client import ClaudeCodeLLMClient
from bakufu.infrastructure.llm.codex_llm_client import CodexLLMClient
from bakufu.infrastructure.llm.config import (
    LLMCliConfig,
    LLMClientConfig,
    LLMCliProviderEnum,
    LLMConfigError,
    LLMProviderEnum,
)
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


_MSG_LC_009_CLI = (
    "[FAIL] Unknown LLM CLI provider: {provider}. Supported: claude-code, codex.\n"
    "Next: Set BAKUFU_LLM_PROVIDER=claude-code or BAKUFU_LLM_PROVIDER=codex."
)


def llm_provider_factory(config: LLMCliConfig) -> LLMProviderPort:
    """LLMCliConfig に基づいて CLI サブプロセス LLM クライアントを返す（REQ-LC-014）。

    Args:
        config: LLMCliConfig インスタンス（provider が確定済み）。

    Returns:
        LLMProviderPort を満たすインスタンス。

    Raises:
        LLMConfigError: 未知のプロバイダが指定された場合（MSG-LC-009）。
    """
    if config.provider == LLMCliProviderEnum.CLAUDE_CODE:
        return ClaudeCodeLLMClient(
            model_name=config.cli_model_name,
            timeout_seconds=config.timeout_seconds,
        )
    if config.provider == LLMCliProviderEnum.CODEX:
        return CodexLLMClient(
            model_name=config.cli_model_name,
            timeout_seconds=config.timeout_seconds,
        )

    raise LLMConfigError(
        message=_MSG_LC_009_CLI.format(provider=config.provider.value),
        field="bakufu_llm_provider",
    )


__all__ = [
    "llm_client_factory",
    "llm_provider_factory",
]
