"""OpenAILLMClient — OpenAI SDK 統合 LLM クライアント実装。

AbstractLLMClient Protocol を実装する。
asyncio.wait_for() でタイムアウトを制御する（SDK 内蔵タイムアウト不使用）。
OpenAI は system role を messages リストに含めて送信する（Anthropic と異なる）。
masking.mask() を適用後にのみ raw_error を格納する（T2 APIキー漏洩防止）。

設計書: docs/features/llm-client/infrastructure/detailed-design.md §確定 A/D/E
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, cast

import openai
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam

from bakufu.domain.exceptions.llm_client import (
    LLMAPIError,
    LLMAuthError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from bakufu.domain.value_objects.llm import LLMMessage, LLMResponse
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

_PROVIDER = "openai"


class OpenAILLMClient:
    """OpenAI SDK を使った LLM クライアント実装（§確定 A）。

    AbstractLLMClient Protocol を満たす。
    OpenAI は system role を messages リストに含めて送信する。
    """

    def __init__(self, config: LLMClientConfig) -> None:
        api_key = config.openai_api_key
        if api_key is None:
            raise LLMConfigError(
                message="OpenAILLMClient requires openai_api_key",
                field="bakufu_openai_api_key",
            )
        self._client = openai.AsyncOpenAI(api_key=api_key.get_secret_value())
        self._model_name = config.openai_model_name
        self._timeout_seconds = config.timeout_seconds

    async def complete(
        self,
        messages: tuple[LLMMessage, ...],
        max_tokens: int,
    ) -> LLMResponse:
        """OpenAI API に完了リクエストを送信して LLMResponse を返す。

        _convert_messages() でメッセージを変換し、asyncio.wait_for() で
        タイムアウトを制御する。max_completion_tokens パラメータを使用する。
        """
        api_messages = self._convert_messages(messages)
        messages_param = cast(list[ChatCompletionMessageParam], api_messages)
        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self._model_name,
                    max_completion_tokens=max_tokens,
                    messages=messages_param,
                ),
                timeout=self._timeout_seconds,
            )
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
        except openai.RateLimitError as exc:
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
        except openai.AuthenticationError as exc:
            msg = _MSG_LC_003.format(
                provider=_PROVIDER,
                PROVIDER=_PROVIDER.upper(),
            )
            logger.error(msg)
            raise LLMAuthError(message=msg, provider=_PROVIDER) from exc
        except openai.APIError as exc:
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
    ) -> list[dict[str, str]]:
        """messages タプルを OpenAI API 形式に変換する。

        OpenAI は system role を messages リストに含めて送信できる。
        全ロールをそのまま変換する。
        """
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def _extract_text(self, response: ChatCompletion) -> str:
        """OpenAI レスポンスからテキストを抽出する。

        content が None または空文字の場合は LLMAPIError(kind='empty_response') を raise。
        """
        content = response.choices[0].message.content
        if not content:
            msg = _MSG_LC_006.format(provider=_PROVIDER)
            logger.error(msg)
            raise LLMAPIError(
                message=msg,
                provider=_PROVIDER,
                kind="empty_response",
            )
        return content
