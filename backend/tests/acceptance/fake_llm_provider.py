"""FakeRoundBasedLLMProvider — 受入テスト用 fake LLM プロバイダ。

ラウンドベース制御: chat_with_tools() の呼び出しごとに verdict リストから
順番に APPROVED/REJECTED を返す。リスト枯渇後は全て APPROVED を返す。
"""

from __future__ import annotations

from bakufu.domain.value_objects.chat_result import ChatResult, ToolCall


class FakeRoundBasedLLMProvider:
    """LLMProviderPort の fake 実装（受入テスト専用）。

    chat(): WORK Stage 用。固定の deliverable テキストを返す。
    chat_with_tools(): INTERNAL_REVIEW Stage 用。verdicts リストから
        順番に APPROVED/REJECTED を返す。
    """

    provider: str = "fake-acceptance"

    def __init__(self, *, chat_with_tools_verdicts: list[str] | None = None) -> None:
        # verdicts が None または空の場合は全て APPROVED
        self._verdicts: list[str] = list(chat_with_tools_verdicts or [])
        self._chat_call_count: int = 0
        self._tools_call_count: int = 0

    async def chat(
        self, messages, system, use_tools=False, agent_name="", session_id=None
    ) -> ChatResult:
        self._chat_call_count += 1
        msg = (
            f"フェイク成果物（受入テスト, call={self._chat_call_count}）。"
            "要件の概要: テスト用サンプルdeliverable。"
        )
        return ChatResult(
            response=msg,
            session_id=None,
            compacted=False,
        )

    async def chat_with_tools(self, messages, system, tools, session_id=None) -> ChatResult:
        self._tools_call_count += 1
        verdict = self._verdicts.pop(0) if self._verdicts else "APPROVED"
        reason = (
            "フェイク差し戻し: 要件の集約境界が不明確。エンティティ境界を再定義せよ。"
            if verdict == "REJECTED"
            else "フェイク承認: 受入テスト合成承認。問題なし。"
        )
        return ChatResult(
            response="",
            session_id=None,
            compacted=False,
            tool_calls=(
                ToolCall(name="submit_verdict", input={"decision": verdict, "reason": reason}),
            ),
        )
