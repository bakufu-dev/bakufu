"""LLMProviderErrorFactory — LLMProviderError サブクラスインスタンス生成（_meta.synthetic: True）。

``docs/features/deliverable-template/ai-validation/test-design.md`` §factory 設計方針 準拠。
Timeout / Auth / ProcessError / EmptyResponse の全 4 サブクラスを提供する。

本モジュールは本番コードから import してはならない。
"""

from __future__ import annotations

from bakufu.domain.exceptions.llm_provider import (
    LLMProviderAuthError,
    LLMProviderEmptyResponseError,
    LLMProviderProcessError,
    LLMProviderTimeoutError,
)


def make_timeout_error(
    *,
    message: str = "LLM CLI call timed out.",
    provider: str = "claude-code",
) -> LLMProviderTimeoutError:
    """LLMProviderTimeoutError インスタンスを構築する（_meta.synthetic: True）。"""
    exc = LLMProviderTimeoutError(message=message, provider=provider)
    exc._meta_synthetic = True  # type: ignore[attr-defined]
    return exc


def make_auth_error(
    *,
    message: str = "LLM CLI authentication failed.",
    provider: str = "claude-code",
) -> LLMProviderAuthError:
    """LLMProviderAuthError インスタンスを構築する（_meta.synthetic: True）。"""
    exc = LLMProviderAuthError(message=message, provider=provider)
    exc._meta_synthetic = True  # type: ignore[attr-defined]
    return exc


def make_process_error(
    *,
    message: str = "LLM CLI process error (exit_code=1).",
    provider: str = "codex",
) -> LLMProviderProcessError:
    """LLMProviderProcessError インスタンスを構築する（_meta.synthetic: True）。"""
    exc = LLMProviderProcessError(message=message, provider=provider)
    exc._meta_synthetic = True  # type: ignore[attr-defined]
    return exc


def make_empty_response_error(
    *,
    message: str = "LLM CLI returned no text content.",
    provider: str = "claude-code",
) -> LLMProviderEmptyResponseError:
    """LLMProviderEmptyResponseError インスタンスを構築する（_meta.synthetic: True）。"""
    exc = LLMProviderEmptyResponseError(message=message, provider=provider)
    exc._meta_synthetic = True  # type: ignore[attr-defined]
    return exc


__all__ = [
    "make_auth_error",
    "make_empty_response_error",
    "make_process_error",
    "make_timeout_error",
]
