"""LLMProviderPort — LLM CLI サブプロセス呼び出し Port 定義。

Protocol で定義することで duck typing による型チェックを実現する。
全 LLM 呼び出しは CLI サブプロセス経由のみ（APIキー不要）。

設計書: docs/features/llm-client/domain/basic-design.md §モジュール契約
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from bakufu.domain.value_objects.chat_result import ChatResult


@runtime_checkable
class LLMProviderPort(Protocol):
    """LLM CLI サブプロセス呼び出し契約を定義する Port。

    全実装は CLI サブプロセス経由（OAuthトークン / サブスク認証）。
    APIキー不要。非同期のみをサポートする。

    Raises:
        LLMProviderTimeoutError: タイムアウト発生時（asyncio.TimeoutError）。
        LLMProviderAuthError: 認証失敗（stderr 認証パターン検出時）。
        LLMProviderProcessError: 非ゼロ終了コード（その他）。
        LLMProviderEmptyResponseError: CLI 空応答時。
    """

    @property
    def provider(self) -> str:
        """プロバイダ識別子（"claude-code" / "codex"）。"""
        ...

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str,
        use_tools: bool = False,
        agent_name: str = "",
        session_id: str | None = None,
    ) -> ChatResult:
        """LLM CLI にメッセージを送信して応答を得る。

        Args:
            messages: 1 件以上のメッセージリスト（[{"role": "user", "content": "..."}] 形式）。
            system: システムプロンプト（評価者ロール指示）。
            use_tools: ツール使用フラグ（デフォルト False）。
            agent_name: エージェント名（デフォルト ""）。
            session_id: セッション継続 ID（新規の場合は None）。

        Returns:
            ChatResult — response は LLM の応答テキスト。
        """
        ...


__all__ = ["LLMProviderPort"]
