"""Outbox event-kind → ハンドラ レジストリ。

各 ``domain_event_outbox`` 行は、ディスパッチャが実行すべき副作用を識別する
``event_kind`` enum を持つ（DirectiveIssued → Task 作成、TaskAssigned →
WebSocket ブロードキャスト、ExternalReviewRequested → Discord 通知 等）。
本モジュールはそのマッピングを所有する。

コントラクト
------------
* :func:`register` は再登録を拒否する。テストでは :func:`clear` を使って状態を
  リセットする — 本番コードがハンドラをサイレントに上書きしてはならない。
* :func:`resolve` はハンドラが存在しないとき
  :class:`bakufu.infrastructure.exceptions.HandlerNotRegisteredError` を送出する。
  ディスパッチャがこれを捕捉し、行を次サイクル用に ``PENDING`` に再マークする。
* :func:`size` は登録数を Bootstrap 起動 WARN ロジック（Confirmation K）に
  公開する。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from bakufu.infrastructure.exceptions import HandlerNotRegisteredError

# ハンドラはペイロード dict を受け取り ``None`` を返す（永続化の副作用は
# ディスパッチャと同じ Unit-of-Work に収める）。
type EventHandler = Callable[[dict[str, object]], Awaitable[None]]

_handlers: dict[str, EventHandler] = {}


def register(event_kind: str, handler: EventHandler) -> None:
    """``event_kind`` を ``handler`` に紐付ける。既に紐付いていれば送出する。

    再登録を拒否することで、2 つの PR が同一の event_kind をサイレントに奪い合うのを
    防ぐ。テストではケース間で :func:`clear` を呼ぶこと。
    """
    if event_kind in _handlers:
        raise KeyError(
            f"Handler already registered for event_kind={event_kind!r}; "
            "call clear() in test setups to reset"
        )
    _handlers[event_kind] = handler


def resolve(event_kind: str) -> EventHandler:
    """``event_kind`` に紐付いたハンドラを返す。なければ送出する。

    Raises:
        HandlerNotRegisteredError: ハンドラが登録されていないとき。ディスパッチャ
            がこれを捕捉して警告し、行を次サイクル用に ``PENDING`` に再マークする。
    """
    handler = _handlers.get(event_kind)
    if handler is None:
        raise HandlerNotRegisteredError(event_kind)
    return handler


def clear() -> None:
    """登録済みハンドラを全て破棄する。テスト専用ヘルパ。"""
    _handlers.clear()


def size() -> int:
    """登録済みハンドラ数を返す。"""
    return len(_handlers)


__all__ = [
    "EventHandler",
    "clear",
    "register",
    "resolve",
    "size",
]
