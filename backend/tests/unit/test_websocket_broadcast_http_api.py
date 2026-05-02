"""websocket-broadcast / http-api ユニットテスト（TC-UT-WSB-101〜115）。

設計書: docs/features/websocket-broadcast/http-api/test-design.md
対象: REQ-WSB-009〜012 / MSG-WSB-003〜005 / 確定A〜F / §確定E
Issue: #159
"""

from __future__ import annotations

import inspect
import json
import logging
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# REQ-WSB-009: ConnectionManager.connect()
# ---------------------------------------------------------------------------


class TestConnectionManagerConnect:
    """TC-UT-WSB-101/102/114: ConnectionManager.connect()。

    §確定D: accept() 完了後に _connections へ append する順序を検証。
    """

    async def test_connect_adds_to_connections_after_accept(self) -> None:
        """TC-UT-WSB-101: connect() が accept() 完了後に _connections に追加する（§確定D）。"""
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        cm = ConnectionManager()
        ws = AsyncMock()

        assert len(cm._connections) == 0

        await cm.connect(ws)

        ws.accept.assert_awaited_once()
        assert len(cm._connections) == 1
        assert ws in cm._connections

    async def test_connect_logs_msg_wsb_003(self, caplog: pytest.LogCaptureFixture) -> None:
        """TC-UT-WSB-102: connect() が MSG-WSB-003 を INFO ログに出力する。"""
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        cm = ConnectionManager()
        ws = AsyncMock()

        with caplog.at_level(logging.INFO, logger="bakufu.interfaces.http.connection_manager"):
            await cm.connect(ws)

        info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
        assert any("WebSocket client connected: total=1" in msg for msg in info_messages), (
            f"MSG-WSB-003 ログが見つからない。実際のログ: {info_messages}"
        )

    async def test_connect_accept_failure_does_not_contaminate_connections(
        self,
    ) -> None:
        """TC-UT-WSB-114: accept() 失敗時に _connections に追加されない（§確定D 回帰防止）。

        §確定D: accept 完了を「接続有効」の条件とし、失敗時はプールに混入しない。
        """
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        cm = ConnectionManager()
        ws = AsyncMock()
        ws.accept.side_effect = RuntimeError("accept failed")

        with pytest.raises(RuntimeError, match="accept failed"):
            await cm.connect(ws)

        assert len(cm._connections) == 0, (
            "accept() 失敗にもかかわらず websocket が _connections に混入している"
        )
        assert ws not in cm._connections


# ---------------------------------------------------------------------------
# REQ-WSB-009: ConnectionManager.disconnect()
# ---------------------------------------------------------------------------


class TestConnectionManagerDisconnect:
    """TC-UT-WSB-103/104/105: ConnectionManager.disconnect()。"""

    async def test_disconnect_removes_from_connections(self) -> None:
        """TC-UT-WSB-103: disconnect() が _connections から websocket を除去する。"""
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        cm = ConnectionManager()
        ws = AsyncMock()
        cm._connections.append(ws)

        assert len(cm._connections) == 1

        cm.disconnect(ws)

        assert len(cm._connections) == 0
        assert ws not in cm._connections

    async def test_disconnect_logs_msg_wsb_004(self, caplog: pytest.LogCaptureFixture) -> None:
        """TC-UT-WSB-104: disconnect() が MSG-WSB-004 を INFO ログに出力する。"""
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        cm = ConnectionManager()
        ws = AsyncMock()
        cm._connections.append(ws)

        with caplog.at_level(logging.INFO, logger="bakufu.interfaces.http.connection_manager"):
            cm.disconnect(ws)

        info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
        assert any("WebSocket client disconnected: total=0" in msg for msg in info_messages), (
            f"MSG-WSB-004 ログが見つからない。実際のログ: {info_messages}"
        )

    async def test_disconnect_nonexistent_websocket_no_exception(self) -> None:
        """TC-UT-WSB-105: 存在しない websocket の disconnect() が例外なく完了する（境界値）。

        if websocket in _connections ガードにより ValueError が発火しない。
        """
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        cm = ConnectionManager()
        ws = AsyncMock()

        # 例外なく完了することを確認（_connections は空のまま）
        cm.disconnect(ws)

        assert len(cm._connections) == 0


# ---------------------------------------------------------------------------
# REQ-WSB-009: ConnectionManager.broadcast() — Fail Soft (§確定B)
# ---------------------------------------------------------------------------


class TestConnectionManagerBroadcast:
    """TC-UT-WSB-106〜110: ConnectionManager.broadcast()。

    §確定B: list(_connections) でスナップショットを取ってから走査。
    個別クライアント送信失敗は Fail Soft — disconnect() + WARNING ログ後に継続。
    """

    async def test_broadcast_empty_pool_no_exception(self) -> None:
        """TC-UT-WSB-106: 空プールへの broadcast() が例外なく完了する（境界値）。"""
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        cm = ConnectionManager()

        # 例外なく完了することを確認
        await cm.broadcast("msg")

    async def test_broadcast_one_client_sends_text(self) -> None:
        """TC-UT-WSB-107: 1クライアントへの broadcast() が send_text を 1 回呼ぶ。"""
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        cm = ConnectionManager()
        ws = AsyncMock()
        cm._connections.append(ws)

        await cm.broadcast("hello")

        ws.send_text.assert_awaited_once_with("hello")

    async def test_broadcast_three_clients_all_receive(self) -> None:
        """TC-UT-WSB-108: 3クライアントへの broadcast() で全員が受信する。

        §確定B: スナップショット走査。
        """
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        cm = ConnectionManager()
        ws1, ws2, ws3 = AsyncMock(), AsyncMock(), AsyncMock()
        cm._connections.extend([ws1, ws2, ws3])

        await cm.broadcast("event")

        ws1.send_text.assert_awaited_once_with("event")
        ws2.send_text.assert_awaited_once_with("event")
        ws3.send_text.assert_awaited_once_with("event")

    async def test_broadcast_fail_soft_continues_after_client_exception(self) -> None:
        """TC-UT-WSB-109: broadcast() Fail Soft — ws1 失敗後も ws2 が受信する。

        §確定B: 個別クライアント送信失敗は Fail Soft。
        ws1 を除去して ws2 に継続し、broadcast() 自体は例外なく完了する。
        """
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        cm = ConnectionManager()
        ws1, ws2 = AsyncMock(), AsyncMock()
        ws1.send_text.side_effect = RuntimeError("connection closed")
        cm._connections.extend([ws1, ws2])

        await cm.broadcast("msg")

        # ws1 は _connections から除去される
        assert ws1 not in cm._connections
        # ws2 は受信する
        ws2.send_text.assert_awaited_once_with("msg")

    async def test_broadcast_logs_msg_wsb_005_on_send_failure(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-UT-WSB-110: broadcast() 失敗時に MSG-WSB-005 を WARNING ログに出力する。"""
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        cm = ConnectionManager()
        ws = AsyncMock()
        ws.send_text.side_effect = RuntimeError("fake error")
        cm._connections.append(ws)

        with caplog.at_level(logging.WARNING, logger="bakufu.interfaces.http.connection_manager"):
            await cm.broadcast("msg")

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("WebSocket broadcast failed for client:" in msg for msg in warning_messages), (
            f"MSG-WSB-005 ログが見つからない。実際のログ: {warning_messages}"
        )


# ---------------------------------------------------------------------------
# REQ-WSB-010: ConnectionManager.handle_event() — EventBus bridge (§確定C)
# ---------------------------------------------------------------------------


class TestConnectionManagerHandleEvent:
    """TC-UT-WSB-111〜113: ConnectionManager.handle_event()。

    §確定C: EventBus bridge は bound method として lifespan で登録する。
    """

    async def test_handle_event_is_coroutinefunction(self) -> None:
        """TC-UT-WSB-111: handle_event が async メソッドかつ callable である。"""
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        cm = ConnectionManager()

        assert inspect.iscoroutinefunction(cm.handle_event), (
            "handle_event は async def でなければならない"
        )
        assert callable(cm.handle_event)

    async def test_handle_event_calls_broadcast_with_json_string(self) -> None:
        """TC-UT-WSB-112: handle_event() が broadcast を JSON 文字列で呼ぶ。

        broadcast の引数が json.dumps(event.to_ws_message()) に一致することを検証。
        """
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        from tests.factories.domain_event_factory import make_task_state_changed_event

        cm = ConnectionManager()
        cm.broadcast = AsyncMock()

        event = make_task_state_changed_event()
        await cm.handle_event(event)

        cm.broadcast.assert_awaited_once()
        call_arg = cm.broadcast.call_args[0][0]
        expected = json.dumps(event.to_ws_message())
        assert call_arg == expected, (
            f"broadcast に渡された JSON 文字列が期待値と異なる。\n"
            f"actual={call_arg!r}\nexpected={expected!r}"
        )

    async def test_handle_event_json_structure_five_keys(self) -> None:
        """TC-UT-WSB-113: handle_event() が 5キー構造の JSON を broadcast する。

        ExternalReviewGateStateChangedEvent を使用して to_ws_message() の
        5キー構造（event_type / aggregate_id / aggregate_type / occurred_at / payload）を確認。
        """
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        from tests.factories.domain_event_factory import (
            make_external_review_gate_state_changed_event,
        )

        cm = ConnectionManager()
        cm.broadcast = AsyncMock()

        event = make_external_review_gate_state_changed_event()
        await cm.handle_event(event)

        call_arg = cm.broadcast.call_args[0][0]
        data = json.loads(call_arg)

        assert set(data.keys()) == {
            "event_type",
            "aggregate_id",
            "aggregate_type",
            "occurred_at",
            "payload",
        }, f"JSON キーが 5 つではない: {set(data.keys())}"
        assert data["event_type"] == "external_review_gate.state_changed"
        assert data["aggregate_type"] == "ExternalReviewGate"
        assert data["aggregate_id"] == str(event.aggregate_id)


# ---------------------------------------------------------------------------
# §確定E: WebSocket Origin 検証 — 単体確認
# ---------------------------------------------------------------------------


class TestWebSocketEndpointOriginValidation:
    """TC-UT-WSB-115/116: GET /ws — Origin 検証の単体確認（§確定E）。"""

    async def test_endpoint_rejects_invalid_origin_with_code_1008(self) -> None:
        """TC-UT-WSB-115: 不正 Origin の場合に close(code=1008) が呼ばれ _connections 非混入。

        §確定E: Cross-Origin WebSocket Hijacking 防止。
        websocket_endpoint() を AsyncMock WebSocket で直接呼び出し、
        cm.connect() が呼ばれないことを検証する。
        """
        from bakufu.interfaces.http.connection_manager import ConnectionManager
        from bakufu.interfaces.http.routers.ws import websocket_endpoint

        ws = AsyncMock()
        # WebSocket.headers は dict-like（.get() を持つ）
        ws.headers = {"origin": "https://attacker.com"}
        # WebSocket.app.state.allowed_origins を明示設定（MagicMock のデフォルト動作を回避）
        ws.app.state.allowed_origins = ["http://localhost:5173"]

        cm = AsyncMock(spec=ConnectionManager)

        await websocket_endpoint(websocket=ws, cm=cm)

        # close(code=1008) が呼ばれていることを確認
        ws.close.assert_awaited_once_with(code=1008)
        # cm.connect() は呼ばれていない（_connections 非混入）
        cm.connect.assert_not_awaited()

    async def test_endpoint_allows_absent_origin_header(self) -> None:
        """TC-UT-WSB-116: Origin ヘッダー不在（headers={}）の場合に接続が通過する（§確定E）。

        §確定E: origin is None 通過設計の回帰防止。
        headers に "origin" キーが存在しない → headers.get("origin") が None を返す →
        origin is not None 条件が False → close() 呼び出しなし → cm.connect() に到達する。

        CLI / AI エージェントはブラウザと異なり Origin ヘッダーを送らないため、
        このケースは MVP 目標（bakufu 自己開発）において必須の正常系である。
        """
        from bakufu.interfaces.http.connection_manager import ConnectionManager
        from bakufu.interfaces.http.routers.ws import websocket_endpoint
        from fastapi import WebSocketDisconnect

        ws = AsyncMock()
        # Origin ヘッダーなし: headers.get("origin") → None
        ws.headers = {}
        ws.app.state.allowed_origins = ["http://localhost:5173"]
        # receive_text() ループを即座に終了させる（WebSocketDisconnect を発火）
        ws.receive_text.side_effect = WebSocketDisconnect()

        cm = AsyncMock(spec=ConnectionManager)

        await websocket_endpoint(websocket=ws, cm=cm)

        # close(code=1008) は呼ばれない（通過）
        ws.close.assert_not_awaited()
        # cm.connect() が呼ばれる（接続プールに登録）
        cm.connect.assert_awaited_once_with(ws)
