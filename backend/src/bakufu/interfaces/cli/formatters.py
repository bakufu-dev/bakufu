"""OutputFormatter — admin-cli 出力フォーマット（§確定 D）。

テーブル形式（tabulate）と JSON 形式（--json フラグ）の 2 モードをサポートする。
エラーメッセージは両モードで stderr に出力する。

設計書: docs/features/admin-cli/cli/detailed-design.md §確定 D
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tabulate import tabulate

if TYPE_CHECKING:
    from bakufu.application.services.admin_service import BlockedTaskSummary, DeadLetterSummary

_MAX_ERROR_LEN = 80
_TRUNC_SUFFIX = "..."


def _trunc(text: str | None, max_len: int = _MAX_ERROR_LEN) -> str:
    """テキストを max_len 文字でトランケートする。None は '-' で代替。"""
    if text is None:
        return "-"
    if len(text) <= max_len:
        return text
    return text[:max_len] + _TRUNC_SUFFIX


def format_blocked_tasks(tasks: list[BlockedTaskSummary], json_output: bool) -> str:
    """list-blocked の出力文字列を返す（§確定 D）。

    0 件時: テーブル形式は "(BLOCKED Task はありません)"、JSON 形式は "[]"。
    """
    if json_output:
        data = [
            {
                "task_id": str(t.task_id),
                "room_id": str(t.room_id),
                "blocked_at": t.blocked_at.isoformat(),
                "last_error": t.last_error,
            }
            for t in tasks
        ]
        return json.dumps(data, ensure_ascii=False, indent=2)

    if not tasks:
        return "（BLOCKED Task はありません）"

    rows = [
        [
            str(t.task_id),
            str(t.room_id),
            t.blocked_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            _trunc(t.last_error),
        ]
        for t in tasks
    ]
    return tabulate(
        rows,
        headers=["TASK ID", "ROOM ID", "BLOCKED AT", "LAST ERROR"],
        tablefmt="simple",
    )


def format_dead_letters(events: list[DeadLetterSummary], json_output: bool) -> str:
    """list-dead-letters の出力文字列を返す（§確定 D）。

    0 件時: テーブル形式は "(dead-letter Event はありません)"、JSON 形式は "[]"。
    """
    if json_output:
        data = [
            {
                "event_id": str(e.event_id),
                "event_kind": e.event_kind,
                "aggregate_id": str(e.aggregate_id),
                "attempt_count": e.attempt_count,
                "last_error": e.last_error,
                "updated_at": e.updated_at.isoformat(),
            }
            for e in events
        ]
        return json.dumps(data, ensure_ascii=False, indent=2)

    if not events:
        return "（dead-letter Event はありません）"

    rows = [
        [
            str(e.event_id),
            e.event_kind,
            str(e.aggregate_id),
            e.attempt_count,
            e.updated_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            _trunc(e.last_error),
        ]
        for e in events
    ]
    return tabulate(
        rows,
        headers=["EVENT ID", "KIND", "AGGREGATE ID", "ATTEMPTS", "UPDATED AT", "LAST ERROR"],
        tablefmt="simple",
    )


def format_success(message: str, json_output: bool, command: str = "", id_: str = "") -> str:
    """変更コマンド成功時の出力文字列を返す（§確定 D）。

    JSON 形式: ``{"result": "ok", "command": "<command>", "id": "<uuid>"}``
    テーブル形式: ``[OK] <message>``
    """
    if json_output:
        payload: dict[str, object] = {"result": "ok"}
        if command:
            payload["command"] = command
        if id_:
            payload["id"] = id_
        return json.dumps(payload, ensure_ascii=False)
    return f"[OK] {message}"


def format_error(message: str) -> str:
    """エラーメッセージ文字列を返す（常に ``[FAIL]`` で始まる形式）。

    既に ``[FAIL]`` で始まっている場合はそのまま返す（二重フォーマット防止）。
    """
    if message.startswith("[FAIL]"):
        return message
    return f"[FAIL] {message}"


__all__ = [
    "format_blocked_tasks",
    "format_dead_letters",
    "format_error",
    "format_success",
]
