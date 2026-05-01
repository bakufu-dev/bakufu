"""ChatResult — LLM CLI サブプロセス応答の値オブジェクト。

NamedTuple として不変 VO を定義する（REQ-LC-002）。
session_id はセッション継続のために保持し、
compacted はコンテキスト圧縮の発生を呼び出し元に通知する。

設計書: docs/features/llm-client/domain/basic-design.md REQ-LC-002
"""

from __future__ import annotations

from typing import NamedTuple


class ChatResult(NamedTuple):
    """LLM CLI サブプロセス応答 VO（不変）。

    Attributes:
        response: LLM 応答テキスト（空文字は infrastructure 層が Fail Fast で防ぐ）。
        session_id: CLI セッション ID（セッション継続時に使用、新規の場合は None）。
        compacted: コンテキスト圧縮フラグ（Claude Code CLI が圧縮した場合 True）。
    """

    response: str
    session_id: str | None
    compacted: bool = False


__all__ = ["ChatResult"]
