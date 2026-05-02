"""WebSocket エンドポイント（REQ-WSB-011）。

``GET /ws`` で WebSocket 接続を受け付け、DomainEvent ブロードキャストを提供する。
Origin 検証（§確定E）を接続前に実施し、不一致は close(code=1008) で即時拒否する。

実装方針は ``docs/features/websocket-broadcast/http-api/detailed-design.md``
§確定 E〜F および REQ-WSB-011 に従う。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from bakufu.interfaces.http.connection_manager import ConnectionManager
from bakufu.interfaces.http.dependencies import get_connection_manager

router = APIRouter()

_CMDep = Annotated[ConnectionManager, Depends(get_connection_manager)]


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, cm: _CMDep) -> None:
    """WebSocket 接続を受け付け、切断まで維持する（REQ-WSB-011）。

    処理フロー:
    1. Origin ヘッダーを ``BAKUFU_ALLOWED_ORIGINS`` と照合。不一致なら
       ``close(code=1008)`` で即時拒否 → return（§確定E）。
    2. ``cm.connect(websocket)`` で接続を受け入れ接続プールに登録。
    3. ``receive_text()`` ループで接続を維持（MVP ではクライアント送信メッセージを無視）。
    4. ``WebSocketDisconnect`` を捕捉して ``cm.disconnect(websocket)`` を呼ぶ（§確定F）。

    Origin が None（ヘッダーなし）の場合は通過を許可する。
    ブラウザは Origin を常に付与するため、CLI/AI エージェントツールの接続への影響を避ける。
    """
    origin: str | None = websocket.headers.get("origin")
    allowed_origins: list[str] = websocket.app.state.allowed_origins
    if origin is not None and origin not in allowed_origins:
        await websocket.close(code=1008)
        return

    await cm.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        cm.disconnect(websocket)
