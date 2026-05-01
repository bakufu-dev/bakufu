"""AnthropicLLMClient — Anthropic SDK 統合 LLM クライアント実装。

AbstractLLMClient Protocol を実装する。
asyncio.wait_for() でタイムアウトを制御する（SDK 内蔵タイムアウト不使用）。
system role を分離して Anthropic API の system パラメータで渡す。
masking.mask() を適用後にのみ raw_error を格納する（T2 APIキー漏洩防止）。

設計書: docs/features/llm-client/infrastructure/detailed-design.md §確定 A/D/E
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, cast

import anthropic
import anthropic.types
from anthropic.types import MessageParam

from bakufu.domain.exceptions.llm_client import (
    LLMAPIError,
    LLMAuthError,
    LLMMessagesEmptyError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from bakufu.domain.value_objects.llm import LLMMessage, LLMResponse, MessageRole
from bakufu.infrastructure.llm.config import LLMConfigError
from bakufu.infrastructure.security import masking

if TYPE_CHECKING:
    from bakufu.infrastructure.llm.config import LLMClientConfig

logger = logging.getLogger(__name__)

# エラーメッセージテンプレート（MSG-LC-XXX）
_MSG_LC_001 = (
    "[FAIL] LLM API call timed out after {timeout_seconds}s (provider={provider})\n"
    "Next: Retry with exponential backoff, or increase BAKUFU_LLM_TIMEOUT_SECONDS."
)
_MSG_LC_002 = (
    "[FAIL] LLM API rate limit exceeded (provider={provider}, retry_after={retry_after}s)\n"
    "Next: Wait {retry_after}s before retrying, or reduce request frequency."
)
_MSG_LC_003 = (
    "[FAIL] LLM API authentication failed (provider={provider})\n"
    "Next: Set BAKUFU_{PROVIDER}_API_KEY to a valid API key and restart."
)
_MSG_LC_004 = (
    "[FAIL] LLM API error (provider={provider}, status={status_code})\n"
    "Next: Check provider status page and inspect raw_error for details."
)
_MSG_LC_006 = (
    "[FAIL] LLM returned no text content (provider={provider}, kind=empty_response)\n"
    "Next: Retry the request or inspect the LLM provider status for content filtering."
)
_MSG_LC_010 = (
    "[FAIL] No user/assistant messages remain after system role filtering"
    " (provider={provider})\n"
    "Next: Include at least one user or assistant message in addition to system messages."
)

_PROVIDER = "anthropic"


class AnthropicLLMClient:
    """Anthropic SDK を使った LLM クライアント実装（§確定 A）。

    AbstractLLMClient Protocol を満たす。
    """

    def __init__(self, config: LLMClientConfig) -> None:
        api_key = config.anthropic_api_key
        if api_key is None:
            raise LLMConfigError(
                message="AnthropicLLMClient requires anthropic_api_key",
                field="bakufu_anthropic_api_key",
            )
        self._client = anthropic.AsyncAnthropic(api_key=api_key.get_secret_value())
        self._model_name = config.anthropic_model_name
        self._timeout_seconds = config.timeout_seconds

    async def complete(
        self,
        messages: tuple[LLMMessage, ...],
        max_tokens: int,
    ) -> LLMResponse:
        """Anthropic API に完了リクエストを送信して LLMResponse を返す。

        _convert_messages() で system role を分離し、asyncio.wait_for() で
        タイムアウトを制御する。
        """
        api_messages, system_str = self._convert_messages(messages)
        messages_param = cast(list[MessageParam], api_messages)
        if system_str is not None:
            create_coro = self._client.messages.create(
                model=self._model_name,
                max_tokens=max_tokens,
                system=system_str,
                messages=messages_param,
            )
        else:
            create_coro = self._client.messages.create(
                model=self._model_name,
                max_tokens=max_tokens,
                messages=messages_param,
            )
        try:
            response = await asyncio.wait_for(create_coro, timeout=self._timeout_seconds)
        except TimeoutError:
            msg = _MSG_LC_001.format(
                timeout_seconds=self._timeout_seconds,
                provider=_PROVIDER,
            )
            logger.warning(msg)
            raise LLMTimeoutError(
                message=msg,
                provider=_PROVIDER,
                timeout_seconds=self._timeout_seconds,
            ) from None
        except anthropic.RateLimitError as exc:
            retry_after: float | None = None
            raw = exc.response.headers.get("retry-after")
            if raw is not None:
                with contextlib.suppress(ValueError):
                    retry_after = float(raw)
            msg = _MSG_LC_002.format(
                provider=_PROVIDER,
                retry_after=retry_after,
            )
            logger.warning(msg)
            raise LLMRateLimitError(
                message=msg,
                provider=_PROVIDER,
                retry_after=retry_after,
            ) from exc
        except anthropic.AuthenticationError as exc:
            msg = _MSG_LC_003.format(
                provider=_PROVIDER,
                PROVIDER=_PROVIDER.upper(),
            )
            logger.error(msg)
            raise LLMAuthError(message=msg, provider=_PROVIDER) from exc
        except anthropic.APIError as exc:
            status_code: int | None = getattr(exc, "status_code", None)
            raw_error = masking.mask(str(exc))
            msg = _MSG_LC_004.format(
                provider=_PROVIDER,
                status_code=status_code,
            )
            logger.error(msg)
            raise LLMAPIError(
                message=msg,
                provider=_PROVIDER,
                status_code=status_code,
                raw_error=raw_error,
            ) from exc

        text = self._extract_text(response)
        return LLMResponse(content=text)

    def _convert_messages(
        self,
        messages: tuple[LLMMessage, ...],
    ) -> tuple[list[dict[str, str]], str | None]:
        """messages タプルを Anthropic API 形式に変換する。

        SYSTEM ロールを分離して system パラメータ用の文字列を返す。
        複数の SYSTEM がある場合は '\\n\\n' で結合する。
        SYSTEM 除外後に messages が空になる場合は LLMMessagesEmptyError を raise。

        Returns:
            (api_messages, system_str) のタプル。
            system_str は SYSTEM メッセージがない場合 None。
        """
        system_parts: list[str] = []
        api_messages: list[dict[str, str]] = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_parts.append(msg.content)
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        if not api_messages:
            context = "all messages are system role for Anthropic"
            msg_text = _MSG_LC_010.format(provider=_PROVIDER)
            logger.error(msg_text)
            raise LLMMessagesEmptyError(
                message=msg_text,
                provider=_PROVIDER,
                context=context,
            )

        system_str = "\n\n".join(system_parts) if system_parts else None
        return api_messages, system_str

    def _extract_text(self, response: anthropic.types.Message) -> str:
        """Anthropic レスポンスから TextBlock のテキストを抽出する。

        TextBlock が 0 件の場合は LLMAPIError(kind='empty_response') を raise。
        """
        text_blocks = [
            block for block in response.content if isinstance(block, anthropic.types.TextBlock)
        ]
        if not text_blocks:
            msg = _MSG_LC_006.format(provider=_PROVIDER)
            logger.error(msg)
            raise LLMAPIError(
                message=msg,
                provider=_PROVIDER,
                kind="empty_response",
            )
        return text_blocks[0].text
