"""InMemoryEventBus — EventBusPort のインプロセス実装（REQ-WSB-007）。

asyncio.gather による並行ハンドラ実行。個別ハンドラのエラーは MSG-WSB-001 として
ログ記録し他ハンドラの実行を継続する（Fail Soft）。

実装方針は ``docs/features/websocket-broadcast/domain/detailed-design.md``
§確定 D（InMemoryEventBus エラーハンドリング）に従う。
"""

from __future__ import annotations

import asyncio
import logging

from bakufu.application.ports.event_bus import HandlerType
from bakufu.domain.events import DomainEvent

logger = logging.getLogger(__name__)


class InMemoryEventBus:
    """asyncio.gather による並行 Event 配信実装（REQ-WSB-007）。

    ``EventBusPort`` に構造的に適合する（明示的な継承なし）。

    不変条件:
    - ``publish()`` は asyncio イベントループ内（``async def`` 内）から呼ぶ
    - ハンドラの登録順序は保証するが、並行実行のため完了順序は不定
    - ハンドラが 0 件の場合 ``publish()`` は即座に resolve する
    """

    def __init__(self) -> None:
        self._handlers: list[HandlerType] = []

    def subscribe(self, handler: HandlerType) -> None:
        """購読者ハンドラをリスト末尾に追加する。"""
        self._handlers.append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """全購読者ハンドラに ``event`` を並行配信する（MSG-WSB-001 / MSG-WSB-002）。

        ``asyncio.gather(..., return_exceptions=True)`` で全ハンドラを並行実行し、
        個別ハンドラの例外を ``BaseException`` として収集する。例外があれば
        MSG-WSB-001（WARNING）としてログ記録後、他ハンドラの実行を継続する（Fail Soft）。
        配信完了後に MSG-WSB-002（DEBUG）を記録する。
        """
        if self._handlers:
            results = await asyncio.gather(
                *[h(event) for h in self._handlers],
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, BaseException):
                    # MSG-WSB-001: ハンドラ例外発生時の WARNING ログ
                    logger.warning(
                        "EventBus handler error: %s: %s",
                        type(result).__name__,
                        result,
                    )
        # MSG-WSB-002: 配信完了 DEBUG ログ
        logger.debug(
            "DomainEvent published: %s aggregate_id=%s",
            event.event_type,
            event.aggregate_id,
        )


__all__ = ["InMemoryEventBus"]
