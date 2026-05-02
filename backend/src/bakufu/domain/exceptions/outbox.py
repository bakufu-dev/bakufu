"""Outbox ドメイン例外（admin-cli 操作対象の Outbox Event 用）。

MSG-AC-004 / MSG-AC-005 の文言はアプリケーション層（AdminService）で構築し、
本モジュールのクラスに注入する。設計書:
  docs/features/admin-cli/application/detailed-design.md §クラス設計（詳細）
"""

from __future__ import annotations

from uuid import UUID


class OutboxEventNotFoundError(Exception):
    """Outbox Event が見つからない場合（MSG-AC-004）。

    ``event_id`` で検索したが DB に存在しなかった場合に送出する。
    """

    def __init__(self, event_id: UUID, message: str) -> None:
        super().__init__(message)
        self.event_id: UUID = event_id
        self.message: str = message


class IllegalOutboxStateError(Exception):
    """Outbox Event が操作に対して不正な状態にある場合（MSG-AC-005）。

    ``retry-event`` の対象が DEAD_LETTER 以外の場合に送出する（Fail Fast）。
    """

    def __init__(self, event_id: UUID, current_status: str, message: str) -> None:
        super().__init__(message)
        self.event_id: UUID = event_id
        self.current_status: str = current_status
        self.message: str = message


__all__ = ["IllegalOutboxStateError", "OutboxEventNotFoundError"]
