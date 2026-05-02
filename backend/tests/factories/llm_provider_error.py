"""LLMProviderErrorFactory — LLMProviderError サブクラスインスタンス生成（_meta.synthetic: True）。

``docs/features/deliverable-template/ai-validation/test-design.md`` §factory 設計方針 準拠。
Timeout / Auth / ProcessError / EmptyResponse の既存 4 サブクラスに加え、
stage-executor §確定 H の TBD-4 解消として SessionLost / RateLimited を追加する。

本モジュールは本番コードから import してはならない。
"""

from __future__ import annotations

from bakufu.domain.exceptions.llm_provider import (
    LLMProviderAuthError,
    LLMProviderEmptyResponseError,
    LLMProviderProcessError,
    LLMProviderRateLimitedError,
    LLMProviderSessionLostError,
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


def make_session_lost_error(
    *,
    message: str = "session not found: unknown session id",
    provider: str = "claude-code",
) -> LLMProviderSessionLostError:
    """LLMProviderSessionLostError インスタンスを構築する（§確定H TBD-4 解消）。"""
    exc = LLMProviderSessionLostError(message=message, provider=provider)
    exc._meta_synthetic = True  # type: ignore[attr-defined]
    return exc


def make_rate_limited_error(
    *,
    message: str = "rate limit exceeded: retry after 60s",
    provider: str = "claude-code",
) -> LLMProviderRateLimitedError:
    """LLMProviderRateLimitedError インスタンスを構築する（§確定H TBD-4 解消）。"""
    exc = LLMProviderRateLimitedError(message=message, provider=provider)
    exc._meta_synthetic = True  # type: ignore[attr-defined]
    return exc


__all__ = [
    "make_auth_error",
    "make_empty_response_error",
    "make_process_error",
    "make_rate_limited_error",
    "make_session_lost_error",
    "make_timeout_error",
]
