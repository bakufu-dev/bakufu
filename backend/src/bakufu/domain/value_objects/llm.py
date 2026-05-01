"""LLM 通信に関わる Value Object 定義。

LLMMessage / LLMResponse / MessageRole を提供する。
これらは domain 層の純粋な VO であり、SDK 依存を持たない。

設計書: docs/features/llm-client/domain/detailed-design.md §確定 B / §確定 F
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(StrEnum):
    """LLM メッセージのロール種別（§確定 B）。

    Anthropic / OpenAI 共通の 3 値に閉じる。
    SDK 固有の値（例: "developer"）はこの VO レイヤでは表現しない。
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class LLMMessage(BaseModel):
    """LLM に送信する単一メッセージ（§確定 B）。

    frozen=True により不変性を保証する。
    content は空文字禁止（MSG-LC-005 参照）。
    """

    model_config = ConfigDict(frozen=True)

    role: MessageRole
    content: str = Field(min_length=1)


class LLMResponse(BaseModel):
    """LLM から受信した応答（§確定 F）。

    frozen=True により不変性を保証する。
    content は min_length=1 で空応答を型レベルで禁止する。
    空テキストを受け取った場合は infrastructure 層が
    LLMAPIError(kind='empty_response') を raise する（Fail Fast）。
    """

    model_config = ConfigDict(frozen=True)

    content: str = Field(min_length=1)


__all__ = [
    "LLMMessage",
    "LLMResponse",
    "MessageRole",
]
