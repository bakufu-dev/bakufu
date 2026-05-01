"""StubLLMProviderFactory — LLMProviderPort スタブ（_meta.synthetic: True）。

``docs/features/deliverable-template/ai-validation/test-design.md`` §factory 設計方針 準拠。
LLMProviderPort Protocol を満たす AsyncMock ベースのスタブを提供する。

本モジュールは本番コードから import してはならない。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from bakufu.domain.value_objects.chat_result import ChatResult


def make_stub_llm_provider(
    *,
    responses: list[ChatResult] | None = None,
    provider: str = "claude-code",
) -> AsyncMock:
    """LLMProviderPort のスタブ（AsyncMock）を返す。

    chat() が ``responses`` の順で ChatResult を返す AsyncMock。
    responses が None の場合はデフォルト PASSED 応答を 1 件設定する。

    _meta.synthetic: True（stub._meta_synthetic = True 設定済み）。
    """
    if responses is None:
        responses = [
            ChatResult(
                response='{"status": "PASSED", "reason": "合成評価理由"}',
                session_id=None,
                compacted=False,
            )
        ]

    stub = AsyncMock()
    stub.provider = provider
    stub.chat = AsyncMock(side_effect=responses)
    stub._meta_synthetic = True
    return stub


def make_stub_llm_provider_raises(
    *,
    exc: Exception,
    provider: str = "claude-code",
) -> AsyncMock:
    """chat() が exc を raise する LLMProviderPort スタブを返す。

    _meta.synthetic: True（stub._meta_synthetic = True 設定済み）。
    """
    stub = AsyncMock()
    stub.provider = provider
    stub.chat = AsyncMock(side_effect=exc)
    stub._meta_synthetic = True
    return stub


__all__ = [
    "make_stub_llm_provider",
    "make_stub_llm_provider_raises",
]
