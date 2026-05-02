"""LLMProviderError — CLI サブプロセス呼び出し例外階層（REQ-LC-003）。

全例外は LLMProviderError を基底クラスとして継承する。
CLI サブプロセスによる LLM 呼び出し時に発生するエラーを表現する。
APIキー・認証トークンはフィールドに含めない（セキュリティ設計 T2）。

設計書: docs/features/llm-client/domain/basic-design.md REQ-LC-003
"""

from __future__ import annotations


class LLMProviderError(Exception):
    """LLM CLI サブプロセス呼び出し例外の基底クラス。

    全てのサブクラスは message（人間可読文言）と provider（プロバイダ名）を持つ。
    provider はプロバイダ識別子のみ（"claude-code" / "codex"）。
    機密情報（APIキー・トークン）をフィールドに含めない。
    """

    def __init__(self, *, message: str, provider: str) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider


class LLMProviderTimeoutError(LLMProviderError):
    """タイムアウト例外（MSG-LC-001）。

    asyncio.TimeoutError 発生時に raise される。
    """


class LLMProviderAuthError(LLMProviderError):
    """認証失敗例外（MSG-LC-003）。

    stderr に認証パターン（"OAuth" / "unauthorized" / "authentication" 等）を
    検出した非ゼロ終了コード時に raise される。
    """


class LLMProviderProcessError(LLMProviderError):
    """CLI プロセスエラー例外（MSG-LC-004）。

    非ゼロ終了コード（認証パターン非該当）時に raise される。
    """


class LLMProviderEmptyResponseError(LLMProviderError):
    """空応答例外（MSG-LC-006）。

    CLI stdout から応答テキストが取得できなかった時に raise される。
    """


class LLMProviderSessionLostError(LLMProviderError):
    """セッション消失例外（§確定H）。

    stderr に ``"session not found"`` / ``"unknown session"`` を含む
    非ゼロ終了コード時に raise される。リトライ時は新規 UUID v4 の
    session_id を使用する（§確定B）。
    """


class LLMProviderRateLimitedError(LLMProviderError):
    """レート制限例外（§確定H）。

    stderr に ``"rate limit"`` / HTTP 429 相当のメッセージを含む場合に
    raise される。固定 backoff（60s → 300s → 900s）で最大 3 回リトライ
    する（§確定E）。
    """


__all__ = [
    "LLMProviderAuthError",
    "LLMProviderEmptyResponseError",
    "LLMProviderError",
    "LLMProviderProcessError",
    "LLMProviderRateLimitedError",
    "LLMProviderSessionLostError",
    "LLMProviderTimeoutError",
]
