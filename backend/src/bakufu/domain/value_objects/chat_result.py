"""ChatResult — LLM CLI サブプロセス応答の値オブジェクト。

NamedTuple として不変 VO を定義する（REQ-LC-002 / REQ-LC-004）。
session_id はセッション継続のために保持し、
compacted はコンテキスト圧縮の発生を呼び出し元に通知する。
tool_calls は chat_with_tools() のツール呼び出し結果を格納する（M5-B）。

設計書: docs/features/llm-client/domain/basic-design.md REQ-LC-002 / REQ-LC-004
"""

from __future__ import annotations

from typing import NamedTuple


class ToolCall(NamedTuple):
    """LLM ツール呼び出し VO（不変）。

    Attributes:
        name: ツール名（例: "submit_verdict"）。
        input: ツール呼び出し引数（dict[str, object]）。
    """

    name: str
    input: dict[str, object]


class ChatResult(NamedTuple):
    """LLM CLI サブプロセス応答 VO（不変）。

    Attributes:
        response: LLM 応答テキスト（空文字は infrastructure 層が Fail Fast で防ぐ）。
        session_id: CLI セッション ID（セッション継続時に使用、新規の場合は None）。
        compacted: コンテキスト圧縮フラグ（Claude Code CLI が圧縮した場合 True）。
        tool_calls: ツール呼び出し結果（chat_with_tools() 使用時のみ非空）。
            chat() では空タプルを返す（M5-A 後方互換）。
    """

    response: str
    session_id: str | None
    compacted: bool = False
    tool_calls: tuple[ToolCall, ...] = ()


__all__ = ["ChatResult", "ToolCall"]
