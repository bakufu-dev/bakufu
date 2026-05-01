"""AbstractLLMClient — LLM 呼び出し Port 定義。

Protocol で定義することで duck typing による型チェックを実現する。
abc.ABC ではなく typing.Protocol を使用する（§確定 A）。

設計書: docs/features/llm-client/domain/basic-design.md §モジュール契約
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from bakufu.domain.value_objects.llm import LLMMessage, LLMResponse


@runtime_checkable
class AbstractLLMClient(Protocol):
    """LLM 呼び出し契約を定義する Port（§確定 A）。

    非同期のみをサポートする。呼び出し元は await を使用すること。
    max_tokens は呼び出し元が指定する（factory/config でのデフォルト値禁止）。

    Raises:
        LLMTimeoutError: タイムアウト発生時（asyncio.TimeoutError）。
        LLMRateLimitError: レート制限（HTTP 429）。
        LLMAuthError: 認証失敗（HTTP 401/403）。
        LLMAPIError: 上記以外の API エラー、または空応答（kind='empty_response'）。
        LLMMessagesEmptyError: Anthropic で system role 除外後にメッセージが空。
    """

    async def complete(
        self,
        messages: tuple[LLMMessage, ...],
        max_tokens: int,
    ) -> LLMResponse:
        """LLM にメッセージを送信して応答を得る。

        Args:
            messages: 1 件以上の LLMMessage タプル（不変）。
            max_tokens: 生成する最大トークン数（1 以上）。

        Returns:
            LLMResponse — content は min_length=1 で常に非空。
        """
        ...
