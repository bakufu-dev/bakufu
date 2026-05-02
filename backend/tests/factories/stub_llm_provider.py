"""StubLLMProviderFactory — LLMProviderPort スタブ（_meta.synthetic: True）。

``docs/features/deliverable-template/ai-validation/test-design.md`` §factory 設計方針 準拠。
LLMProviderPort Protocol を満たす AsyncMock ベースのスタブを提供する。

M5-B で `chat_with_tools()` 用スタブを追加 (§確定 D ツール呼び出し登録方式)。
応答形式は InternalReviewGateExecutor._extract_tool_call() が期待する JSON プロトコルに準拠。

本モジュールは本番コードから import してはならない。
"""

from __future__ import annotations

import json
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


# ---------------------------------------------------------------------------
# M5-B: chat_with_tools() 対応ファクトリ（§確定 D ツール呼び出し登録方式）
# ---------------------------------------------------------------------------


def make_tool_call_chat_result(
    decision: str = "APPROVED",
    reason: str = "合成審査OK",
) -> ChatResult:
    """submit_verdict ツール呼び出しを含む ChatResult を生成する。

    InternalReviewGateExecutor._extract_tool_call() が期待する JSON 形式:
      {"type": "tool_use", "input": {"decision": "APPROVED", "reason": "..."}}

    _meta.synthetic 相当: コンストラクタ引数から一意に識別可能。
    """
    response = json.dumps(
        {"type": "tool_use", "input": {"decision": decision, "reason": reason}}
    )
    return ChatResult(response=response, session_id=None, compacted=False)


def make_text_chat_result(text: str = "コードを確認しました。問題はありません。") -> ChatResult:
    """ツール呼び出しを含まないテキスト応答の ChatResult を生成する。

    _extract_tool_call() が None を返すため、Executor がリトライフローに入る。
    _meta.synthetic 相当: コンストラクタ引数から一意に識別可能。
    """
    return ChatResult(response=text, session_id=None, compacted=False)


def make_stub_llm_provider_with_tools(
    *,
    chat_with_tools_responses: list[ChatResult] | None = None,
    chat_responses: list[ChatResult] | None = None,
    provider: str = "claude-code",
) -> AsyncMock:
    """chat_with_tools() 対応 LLMProviderPort スタブを返す（§確定 D）。

    chat_with_tools_responses: 試行ごとの ChatResult リスト（side_effect）。
        None の場合はデフォルトで APPROVED ツール呼び出し応答を 1 件設定する。
    chat_responses: chat() 用 responses（省略時はデフォルト PASSED 応答 1 件）。

    _meta.synthetic: True（stub._meta_synthetic = True 設定済み）。
    """
    if chat_with_tools_responses is None:
        chat_with_tools_responses = [make_tool_call_chat_result()]

    if chat_responses is None:
        chat_responses = [
            ChatResult(
                response='{"status": "PASSED", "reason": "合成評価理由"}',
                session_id=None,
                compacted=False,
            )
        ]

    stub = AsyncMock()
    stub.provider = provider
    stub.chat = AsyncMock(side_effect=chat_responses)
    stub.chat_with_tools = AsyncMock(side_effect=chat_with_tools_responses)
    stub._meta_synthetic = True
    return stub


def make_stub_llm_provider_with_tools_raises(
    *,
    exc: Exception,
    provider: str = "claude-code",
) -> AsyncMock:
    """chat_with_tools() が exc を raise する LLMProviderPort スタブを返す。

    _meta.synthetic: True（stub._meta_synthetic = True 設定済み）。
    """
    stub = AsyncMock()
    stub.provider = provider
    stub.chat = AsyncMock(side_effect=exc)
    stub.chat_with_tools = AsyncMock(side_effect=exc)
    stub._meta_synthetic = True
    return stub


__all__ = [
    "make_stub_llm_provider",
    "make_stub_llm_provider_raises",
    "make_stub_llm_provider_with_tools",
    "make_stub_llm_provider_with_tools_raises",
    "make_text_chat_result",
    "make_tool_call_chat_result",
]
