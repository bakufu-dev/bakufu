"""EventBusPort — Domain Event 配信ポート（REQ-WSB-006）。

``Protocol`` クラスとして定義することで ``InMemoryEventBus`` が明示的な継承を
必要とせず構造的に適合できる（structural subtyping）。将来の Redis EventBus 等も
同様に Protocol 適合として扱える。

実装方針は ``docs/features/websocket-broadcast/domain/detailed-design.md``
§確定（EventBusPort）に従う。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from bakufu.domain.events import DomainEvent

#: EventBus ハンドラ型エイリアス。非同期 callable を受け取る。
type HandlerType = Callable[[DomainEvent], Awaitable[None]]


class EventBusPort(Protocol):
    """Domain Event 配信インターフェース（Port パターン）。

    application 層が持つ EventBus への唯一の参照点。
    infrastructure 実装（``InMemoryEventBus``）は明示的な継承なしに本 Protocol に
    適合する（``@runtime_checkable`` は付与しない — Python 3.12 の
    duck typing で十分）。
    """

    def subscribe(self, handler: HandlerType) -> None:
        """購読者ハンドラを登録する。"""
        ...

    async def publish(self, event: DomainEvent) -> None:
        """全購読者ハンドラに ``event`` を配信する。"""
        ...


__all__ = ["EventBusPort", "HandlerType"]
