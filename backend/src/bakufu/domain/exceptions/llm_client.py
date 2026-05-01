"""LLM クライアント例外階層（§確定 C domain/detailed-design.md）。

全例外は LLMClientError を基底クラスとして継承する。
LLMConfigError のみ別系統（Exception 直接継承）で infrastructure に配置。

設計書: docs/features/llm-client/domain/detailed-design.md §確定 C
"""

from __future__ import annotations


class LLMClientError(Exception):
    """LLM 呼び出し例外の基底クラス。

    全てのサブクラスは message（人間可読文言）と provider（プロバイダ名）を持つ。
    """

    def __init__(self, *, message: str, provider: str) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider


class LLMTimeoutError(LLMClientError):
    """タイムアウト例外（MSG-LC-001）。

    asyncio.TimeoutError 発生時に raise される。
    timeout_seconds は設定されていた上限秒数。
    """

    def __init__(self, *, message: str, provider: str, timeout_seconds: float) -> None:
        super().__init__(message=message, provider=provider)
        self.timeout_seconds = timeout_seconds


class LLMRateLimitError(LLMClientError):
    """レート制限例外（MSG-LC-002）。

    HTTP 429 または SDK RateLimitError 発生時に raise される。
    retry_after は API が返した Retry-After 秒数。不明な場合は None。
    """

    def __init__(self, *, message: str, provider: str, retry_after: float | None) -> None:
        super().__init__(message=message, provider=provider)
        self.retry_after = retry_after


class LLMAuthError(LLMClientError):
    """認証失敗例外（MSG-LC-003）。

    HTTP 401/403 または SDK AuthenticationError 発生時に raise される。
    """


class LLMAPIError(LLMClientError):
    """汎用 API エラー例外（MSG-LC-004 / MSG-LC-006）。

    上記以外の SDK API エラーおよび空応答（kind='empty_response'）で raise される。
    raw_error は masking.mask() 適用後の文字列のみ格納する。
    kind='empty_response' は LLM が空テキストを返した場合の特殊種別。
    """

    def __init__(
        self,
        *,
        message: str,
        provider: str,
        status_code: int | None = None,
        raw_error: str = "",
        kind: str | None = None,
    ) -> None:
        super().__init__(message=message, provider=provider)
        self.status_code = status_code
        self.raw_error = raw_error
        self.kind = kind


class LLMMessageValidationError(LLMClientError):
    """単一メッセージのバリデーションエラー（MSG-LC-005）。

    LLMMessage.content が空文字など制約違反の場合に raise される。
    field は違反フィールド名（通常 "content"）。
    """

    def __init__(self, *, message: str, provider: str, field: str) -> None:
        super().__init__(message=message, provider=provider)
        self.field = field


class LLMMessagesEmptyError(LLMClientError):
    """メッセージリスト空エラー（MSG-LC-010）。

    Anthropic で system role 除外後に user/assistant メッセージが
    0 件になった場合に raise される。
    context は空になった経緯の説明文字列。
    """

    def __init__(self, *, message: str, provider: str, context: str) -> None:
        super().__init__(message=message, provider=provider)
        self.context = context


__all__ = [
    "LLMAPIError",
    "LLMAuthError",
    "LLMClientError",
    "LLMMessageValidationError",
    "LLMMessagesEmptyError",
    "LLMRateLimitError",
    "LLMTimeoutError",
]
