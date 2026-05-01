"""Anthropic / OpenAI SDK レスポンスオブジェクトのファクトリ群.

schema を元に合成データを生成する。unit test 専用。
integration test では raw fixture を使用すること（テスト戦略ガイド参照）。
本モジュールは本番コードから import してはならない。
"""
from __future__ import annotations

import anthropic
import anthropic.types
import openai
import openai.types
import openai.types.chat
import openai.types.chat.chat_completion as cc
from openai.types.chat import ChatCompletionMessage


class AnthropicSDKResponseFactory:
    """Anthropic SDK Message オブジェクトのファクトリ。"""

    @staticmethod
    def build(*, content: str = "合成応答テキスト") -> anthropic.types.Message:
        """TextBlock を 1 件持つ正常応答オブジェクトを生成する。"""
        return anthropic.types.Message(
            id="msg_synthetic_001",
            type="message",
            role="assistant",
            content=[anthropic.types.TextBlock(type="text", text=content)],
            model="claude-3-5-sonnet-20241022",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=anthropic.types.Usage(input_tokens=10, output_tokens=20),
        )

    @staticmethod
    def build_no_text_block() -> anthropic.types.Message:
        """TextBlock を持たない応答（ToolUseBlock のみ）を生成する。"""
        return anthropic.types.Message(
            id="msg_synthetic_no_text_001",
            type="message",
            role="assistant",
            content=[
                anthropic.types.ToolUseBlock(
                    type="tool_use",
                    id="tool_synthetic_001",
                    name="some_tool",
                    input={"key": "value"},
                )
            ],
            model="claude-3-5-sonnet-20241022",
            stop_reason="tool_use",
            stop_sequence=None,
            usage=anthropic.types.Usage(input_tokens=10, output_tokens=5),
        )


class OpenAISDKResponseFactory:
    """OpenAI SDK ChatCompletion オブジェクトのファクトリ。"""

    @staticmethod
    def build(*, content: str = "合成応答テキスト") -> openai.types.chat.ChatCompletion:
        """正常応答オブジェクトを生成する。"""
        return openai.types.chat.ChatCompletion(
            id="chatcmpl_synthetic_001",
            object="chat.completion",
            created=1746124800,
            model="gpt-4o-mini",
            choices=[
                cc.Choice(
                    index=0,
                    message=ChatCompletionMessage(role="assistant", content=content),
                    finish_reason="stop",
                    logprobs=None,
                )
            ],
            usage=openai.types.CompletionUsage(
                prompt_tokens=10, completion_tokens=20, total_tokens=30
            ),
        )

    @staticmethod
    def build_null_content() -> openai.types.chat.ChatCompletion:
        """content が None の応答オブジェクトを生成する（empty_response テスト用）。"""
        return openai.types.chat.ChatCompletion(
            id="chatcmpl_synthetic_null_001",
            object="chat.completion",
            created=1746124800,
            model="gpt-4o-mini",
            choices=[
                cc.Choice(
                    index=0,
                    message=ChatCompletionMessage(role="assistant", content=None),
                    finish_reason="stop",
                    logprobs=None,
                )
            ],
            usage=openai.types.CompletionUsage(
                prompt_tokens=10, completion_tokens=0, total_tokens=10
            ),
        )


__all__ = [
    "AnthropicSDKResponseFactory",
    "OpenAISDKResponseFactory",
]
