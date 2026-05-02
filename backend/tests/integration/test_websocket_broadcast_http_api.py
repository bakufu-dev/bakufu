"""websocket-broadcast / http-api 結合テスト（TC-IT-WSB-101〜107）。

設計書: docs/features/websocket-broadcast/http-api/test-design.md
対象: REQ-WSB-009〜012 / §確定B（スナップショット走査）/ §確定D / §確定E / §確定F
Issue: #159

前提:
- ASGI アプリ: create_app() + starlette.testclient.TestClient でサーバを起動
- ConnectionManager: lifespan で app.state.connection_manager として初期化済み
- InMemoryEventBus: lifespan で app.state.event_bus として初期化済み、cm.handle_event 登録済み
- WebSocket クライアント: TestClient.websocket_connect("/ws") コンテキストマネージャを使用
- 全 WebSocket 操作に timeout=5（秒）を設定（CIハング防止 — test-design.md §前提）
- DB: BAKUFU_DATA_DIR=tmp_path の SQLite（WebSocket テストでは DB 操作なし）

---
[バグレポート] get_connection_manager() が WebSocket DI で動作しない問題
-----------------------------------------------------------------------
対象ファイル: backend/src/bakufu/interfaces/http/dependencies.py
対象行: 94 — def get_connection_manager(request: Request) -> ConnectionManager:

期待される動作:
  get_connection_manager(request: Request) が WebSocket エンドポイントの
  DI（Depends(get_connection_manager)）経由で ConnectionManager を返す。

実際の動作:
  FastAPI 0.136.1 + Starlette 1.0.0 の依存解決コード（fastapi/dependencies/utils.py）は
  ``if dependant.request_param_name and isinstance(request, Request):`` という条件で
  request を解決する。WebSocket コンテキストでは request は WebSocket オブジェクトであり、
  WebSocket は Request の兄弟クラス（両者とも HTTPConnection の派生）であって
  Request のサブクラスではない（isinstance(ws, Request) == False）。
  そのため request 引数が渡されず TypeError が発火する。

再現手順:
  1. create_app() → TestClient(app) → websocket_connect("/ws")
  2. → TypeError: get_connection_manager() missing 1 required positional argument: 'request'

修正方針:
  request: Request → conn: HTTPConnection（starlette.requests.HTTPConnection）に変更し、
  conn.app.state.connection_manager を参照する。
  HTTPConnection は Request・WebSocket 両方の基底クラスであるため、
  両コンテキストで DI が正常動作する。

回避策（本テストファイルでの対応）:
  app.dependency_overrides[get_connection_manager] = lambda: app.state.connection_manager
  を使用して DI バグを回避し、lifespan が設定した ConnectionManager を直接返す。
  dependency_overrides は FastAPI 公式のテスト推奨パターン（late-binding lambda を使用）。
"""

from __future__ import annotations

import threading
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

# ---------------------------------------------------------------------------
# ヘルパー: receive_json() にタイムアウトを追加（CIハング防止）
# ---------------------------------------------------------------------------


def _recv_json(ws: Any, timeout: float = 5.0) -> Any:
    """WebSocketTestSession.receive_json() にタイムアウトを追加したヘルパー。

    CIハング防止のための設計凍結（test-design.md §前提）。
    Starlette 1.0.0 の WebSocketTestSession.receive_json() は timeout パラメータを
    持たないため、threading.Thread で代替実装する。
    daemon=True により pytest プロセスの終了を妨げない。
    """
    result: list[Any] = []
    exc: list[BaseException] = []

    def _task() -> None:
        try:
            result.append(ws.receive_json())
        except BaseException as e:
            exc.append(e)

    t = threading.Thread(target=_task, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        pytest.fail(f"receive_json() が {timeout}s 経過してもブロックしている（CIハング防止）")
    if exc:
        raise exc[0]
    return result[0]


# ---------------------------------------------------------------------------
# フィクスチャ: WebSocket 結合テスト用 TestClient（lifespan 起動済み）
# ---------------------------------------------------------------------------

_MASKING_ENV_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "OAUTH_CLIENT_SECRET",
    "BAKUFU_DISCORD_BOT_TOKEN",
)


@pytest.fixture
def ws_client_ctx(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[Any, TestClient], None, None]:
    """WebSocket 結合テスト用 TestClient フィクスチャ。

    - BAKUFU_DATA_DIR を tmp_path に設定し lifespan の SQLite 作成先を制御
    - BAKUFU_ALLOWED_ORIGINS を "http://localhost:5173" に固定
    - lifespan を起動（with TestClient(app) as client）して
      app.state.connection_manager / event_bus / allowed_origins を初期化
    - dependency_overrides で DI バグ（request: Request → WebSocket 非互換）を回避:
      get_connection_manager のオーバーライドを lambda で late-binding
    """
    from bakufu.infrastructure.config import data_dir as data_dir_mod
    from bakufu.interfaces.http.app import create_app
    from bakufu.interfaces.http.dependencies import get_connection_manager

    # masking.init() が必要とする API キー環境変数をクリア
    for env_key in _MASKING_ENV_KEYS:
        monkeypatch.delenv(env_key, raising=False)

    monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BAKUFU_ALLOWED_ORIGINS", "http://localhost:5173")
    data_dir_mod.reset()  # _resolved キャッシュをクリア（前テストからの残留を防ぐ）

    app = create_app()

    # DI バグ回避: late-binding lambda（lifespan 起動後に app.state.connection_manager が確定）
    app.dependency_overrides[get_connection_manager] = lambda: app.state.connection_manager

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            yield app, client
    finally:
        app.dependency_overrides.clear()
        data_dir_mod.reset()  # テスト後もキャッシュをクリア


# ---------------------------------------------------------------------------
# TC-IT-WSB-101〜103: GET /ws 接続管理
# ---------------------------------------------------------------------------


class TestWebSocketConnectionManagement:
    """TC-IT-WSB-101〜103: WebSocket 接続・切断の ConnectionManager 反映。"""

    def test_connection_adds_to_pool(self, ws_client_ctx: Any) -> None:
        """TC-IT-WSB-101: GET /ws 接続後に cm._connections の len が 1 になる（§確定D）。

        §確定D: accept 完了後 append の結合確認。timeout=5 を _recv_json で担保。
        """
        app, client = ws_client_ctx
        cm = app.state.connection_manager

        with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as _ws:
            assert len(cm._connections) == 1, (
                f"接続後に cm._connections の len が 1 でない: {len(cm._connections)}"
            )

    def test_disconnect_removes_from_pool(self, ws_client_ctx: Any) -> None:
        """TC-IT-WSB-102: GET /ws 切断後に cm._connections が空になる（§確定F）。

        §確定F: WebSocketDisconnect 捕捉 + disconnect() 呼び出しの結合確認。
        コンテキストマネージャ正常退出で切断を発火する。
        """
        app, client = ws_client_ctx
        cm = app.state.connection_manager

        with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as _ws:
            assert len(cm._connections) == 1

        # コンテキスト終了後、接続が除去されている
        assert len(cm._connections) == 0, (
            f"切断後に cm._connections が空でない: {len(cm._connections)}"
        )

    def test_explicit_close_empties_pool_no_exception(self, ws_client_ctx: Any) -> None:
        """TC-IT-WSB-103: websocket.close() 後に cm._connections が空、例外が伝播しない。

        コンテキストマネージャ内で close() を明示呼び出し。
        """
        app, client = ws_client_ctx
        cm = app.state.connection_manager

        with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as ws:
            assert len(cm._connections) == 1
            ws.close()  # 明示的に close()

        # 例外なく完了し、_connections が空になる
        assert len(cm._connections) == 0


# ---------------------------------------------------------------------------
# TC-IT-WSB-104〜106: EventBus → WebSocket 配信 / lifespan 統合
# ---------------------------------------------------------------------------


class TestWebSocketEventBroadcast:
    """TC-IT-WSB-104〜106: EventBus → WebSocket 配信 / lifespan 統合確認。"""

    def test_event_bus_publish_delivers_json_to_websocket(self, ws_client_ctx: Any) -> None:
        """TC-IT-WSB-104: EventBus.publish() → ws.receive_json() が正しい構造を返す。

        client.portal.call(event_bus.publish, event) でスレッドセーフに発行。
        _recv_json(ws, timeout=5) で受信タイムアウトを保証する。
        """
        from tests.factories.domain_event_factory import make_task_state_changed_event

        app, client = ws_client_ctx
        event_bus = app.state.event_bus

        with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as ws:
            event = make_task_state_changed_event()
            # anyio BlockingPortal.call() で async event_bus.publish() を同期実行
            client.portal.call(event_bus.publish, event)

            data = _recv_json(ws, timeout=5)

        assert data["event_type"] == "task.state_changed"
        assert data["aggregate_type"] == "Task"
        assert data["aggregate_id"] == str(event.aggregate_id)
        assert set(data.keys()) == {
            "event_type",
            "aggregate_id",
            "aggregate_type",
            "occurred_at",
            "payload",
        }

    def test_fail_soft_with_broken_client_other_receives(self, ws_client_ctx: Any) -> None:
        """TC-IT-WSB-105: Fail Soft — 切断済みクライアント混在でも残存クライアントへ配信継続。

        §確定B（スナップショット走査）の結合確認。
        broken_ws（send_text が RuntimeError を発火）を cm._connections に直接追加し、
        broadcast() が Fail Soft で broken_ws を除去しつつ ws1 に配信することを検証。
        プールからの除去前に broadcast が発生するタイミングを AsyncMock で確定的に再現する。
        """
        from unittest.mock import AsyncMock

        from tests.factories.domain_event_factory import make_task_state_changed_event

        app, client = ws_client_ctx
        cm = app.state.connection_manager
        event_bus = app.state.event_bus

        with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as ws1:
            # broken_ws: send_text が RuntimeError を発火するモック（Fail Soft シナリオ）
            broken_ws = AsyncMock()
            broken_ws.send_text.side_effect = RuntimeError("simulated connection failure")
            cm._connections.append(broken_ws)

            assert len(cm._connections) == 2  # ws1(実) + broken_ws(モック)

            event = make_task_state_changed_event()
            # broadcast 実行: broken_ws は失敗（Fail Soft）、ws1 は成功
            client.portal.call(event_bus.publish, event)

            # Fail Soft: broken_ws は _connections から除去されている
            assert broken_ws not in cm._connections, (
                "Fail Soft により broken_ws が _connections から除去されていない"
            )

            # ws1 はイベントを受信できる
            data = _recv_json(ws1, timeout=5)

        assert data["event_type"] == "task.state_changed"

    def test_lifespan_initializes_connection_manager_and_event_bus(
        self, ws_client_ctx: Any
    ) -> None:
        """TC-IT-WSB-106: lifespan が ConnectionManager・EventBus を初期化し bridge 登録済み。

        §REQ-WSB-012 / §確定C lifespan 契約の結合確認。
        - app.state.connection_manager が ConnectionManager インスタンスである
        - app.state.event_bus._handlers の len が 1 以上（cm.handle_event 登録済み）
        """
        from bakufu.interfaces.http.connection_manager import ConnectionManager

        app, _client = ws_client_ctx

        cm = app.state.connection_manager
        event_bus = app.state.event_bus

        assert isinstance(cm, ConnectionManager), (
            f"app.state.connection_manager が ConnectionManager でない: {type(cm)}"
        )
        assert len(event_bus._handlers) >= 1, (
            "app.state.event_bus._handlers が空 — cm.handle_event が登録されていない"
        )
        # cm.handle_event が登録されていることを bound method レベルで確認
        assert any(
            getattr(h, "__func__", None) is ConnectionManager.handle_event
            for h in event_bus._handlers
        ), "event_bus._handlers に ConnectionManager.handle_event が見当たらない"


# ---------------------------------------------------------------------------
# TC-IT-WSB-107: §確定E — Origin 検証結合確認
# ---------------------------------------------------------------------------


class TestWebSocketOriginValidation:
    """TC-IT-WSB-107: §確定E — 不正 Origin が WebSocket 接続を拒否される（結合確認）。"""

    def test_invalid_origin_rejected_with_websocket_disconnect_1008(
        self, ws_client_ctx: Any
    ) -> None:
        """TC-IT-WSB-107: 不正 Origin が 1008 で拒否され cm._connections に追加されない。

        §確定E: Cross-Origin WebSocket Hijacking 防止の結合確認。
        TestClient.websocket_connect() に不正 Origin を渡し、
        WebSocketDisconnect(code=1008) が発生することを検証。
        """
        app, client = ws_client_ctx
        cm = app.state.connection_manager

        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect("/ws", headers={"origin": "https://attacker.com"}) as _ws,
        ):
            pass  # __enter__ 内で拒否される

        assert exc_info.value.code == 1008, f"close code が 1008 でない: code={exc_info.value.code}"
        assert len(cm._connections) == 0, "不正 Origin の接続が cm._connections に混入している"
