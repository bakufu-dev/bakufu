"""ConnectionManager — WebSocket 接続プール管理と EventBus bridge（REQ-WSB-009/010）。

DomainEvent を WebSocket クライアントへブロードキャストする唯一の接点。
lifespan で生成・登録し、app.state.connection_manager として保持する（REQ-WSB-012）。

実装方針は ``docs/features/websocket-broadcast/http-api/detailed-design.md``
§確定 A〜F に従う。
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from fastapi import WebSocket

if TYPE_CHECKING:
    from bakufu.domain.events import DomainEvent

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 接続プール管理・ブロードキャスト・EventBus bridge（REQ-WSB-009/010）。

    接続プールは ``list[WebSocket]``（§確定 A）。``broadcast()`` はスナップショット
    走査（§確定 B）。EventBus bridge は bound method ``handle_event``（§確定 C）。
    ``connect()`` は ``accept()`` 完了後に追加（§確定 D）。
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """WebSocket を accept して接続プールに追加する（REQ-WSB-009 §確定D）。

        ``accept()`` が失敗した場合（例外発生時）は ``_connections`` への追加を行わず、
        例外を呼び出し元に伝播する。accept 完了を「接続有効」の条件とする。
        """
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("WebSocket client connected: total=%d", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """接続プールから WebSocket を削除する（REQ-WSB-009）。

        二重削除で ``ValueError`` が出ないよう存在チェック後に削除する。
        MSG-WSB-004 は削除が実行された場合のみ記録する（削除なしの呼び出しはサイレント）。
        """
        if websocket in self._connections:
            self._connections.remove(websocket)
            logger.info("WebSocket client disconnected: total=%d", len(self._connections))

    async def broadcast(self, message: str) -> None:
        """全接続クライアントにメッセージを送信する（REQ-WSB-009 §確定B）。

        ``list(_connections)`` でスナップショットを取ってから走査し、走査中の
        ``disconnect()`` による ``RuntimeError`` を防ぐ（§確定B）。
        個別クライアント送信失敗は Fail Soft — ``disconnect()`` + WARNING ログ後に継続
        （MSG-WSB-005）。
        """
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception as exc:
                self.disconnect(ws)
                logger.warning(
                    "WebSocket broadcast failed for client: %s: %s",
                    type(exc).__name__,
                    exc,
                )

    async def handle_event(self, event: DomainEvent) -> None:
        """DomainEvent を JSON 文字列に変換してブロードキャストする（REQ-WSB-010 §確定C）。

        ``EventBusPort.subscribe()`` の handler シグネチャ
        ``(event: DomainEvent) -> Awaitable[None]`` に適合する bound method。
        lifespan で ``event_bus.subscribe(cm.handle_event)`` として登録する。

        ``event.to_ws_message()`` が返す dict は ``event_id``（UUID）と
        ``occurred_at``（datetime）を文字列変換済みのため、標準 ``json.dumps`` で直列化可能。
        """
        json_str = json.dumps(event.to_ws_message())
        await self.broadcast(json_str)


__all__ = ["ConnectionManager"]
