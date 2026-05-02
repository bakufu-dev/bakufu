# テスト設計書 — websocket-broadcast / http-api

<!-- feature: websocket-broadcast / sub-feature: http-api -->
<!-- 配置先: docs/features/websocket-broadcast/http-api/test-design.md -->
<!-- 対象範囲: REQ-WSB-009〜012 / MSG-WSB-003〜005 / 確定A〜F -->
<!-- 関連 Issue: #159 feat(websocket-broadcast): WebSocket endpoint + ConnectionManager -->

本 sub-feature は interfaces/http 層（`connection_manager.py` / `routers/ws.py` / `app.py` lifespan 統合）を対象とする。domain sub-feature（Issue #158）で確立した EventBus / DomainEvent 基盤の上に WebSocket 接続管理・ブロードキャスト・lifespan 統合を実装する。

---

## テストマトリクス

| 要件 ID | 実装アーティファクト | テストケース ID | テストレベル | 種別 | 親 spec 受入基準 |
|---|---|---|---|---|---|
| REQ-WSB-009（ConnectionManager）| `interfaces/http/connection_manager.py: ConnectionManager.connect()` | TC-UT-WSB-101〜102 | ユニット | 正常系 | — |
| REQ-WSB-009（ConnectionManager §確定D 回帰防止）| `interfaces/http/connection_manager.py: ConnectionManager.connect()` | TC-UT-WSB-114 | ユニット | 異常系 | — |
| REQ-WSB-009（ConnectionManager）| `interfaces/http/connection_manager.py: ConnectionManager.disconnect()` | TC-UT-WSB-103〜105 | ユニット | 正常系 / 境界値 | — |
| REQ-WSB-009（ConnectionManager Fail Soft）| `interfaces/http/connection_manager.py: ConnectionManager.broadcast()` | TC-UT-WSB-106〜110 | ユニット | 正常系 / 境界値 / 異常系 | — |
| REQ-WSB-010（ConnectionManager.handle_event）| `interfaces/http/connection_manager.py: ConnectionManager.handle_event()` | TC-UT-WSB-111〜113 | ユニット | 正常系 | — |
| §確定E（WebSocket Origin 検証）| `interfaces/http/routers/ws.py` — Origin 拒否 | TC-UT-WSB-115 | ユニット | 異常系 | — |
| MSG-WSB-003（接続ログ）| `ConnectionManager.connect()` | TC-UT-WSB-102 | ユニット | 正常系 | — |
| MSG-WSB-004（切断ログ）| `ConnectionManager.disconnect()` | TC-UT-WSB-104 | ユニット | 正常系 | — |
| MSG-WSB-005（ブロードキャスト失敗ログ）| `ConnectionManager.broadcast()` | TC-UT-WSB-110 | ユニット | 異常系 | — |
| REQ-WSB-011（GET /ws エンドポイント）| `interfaces/http/routers/ws.py` | TC-IT-WSB-101〜103 | 結合 | 正常系 / 異常系 | §9 #1 / #5 |
| §確定E（Origin 検証結合）| `interfaces/http/routers/ws.py` — Origin 拒否 | TC-IT-WSB-107 | 結合 | 異常系 | — |
| REQ-WSB-009〜011（EventBus → WS 配信）| `ConnectionManager` + `InMemoryEventBus` + `handle_event` | TC-IT-WSB-104〜105 | 結合 | 正常系 / 異常系 | §9 #2 / #3 / #5 |
| REQ-WSB-012（lifespan 統合）| `interfaces/http/app.py: lifespan` | TC-IT-WSB-106 | 結合 | 正常系 | §9 #1 |

**マトリクス充足の証拠**:
- REQ-WSB-009〜012 すべてに最低 1 件のテストケース ✅
- MSG-WSB-003〜005 すべてに静的文字列照合ケース ✅
- 確定A（`list[WebSocket]`）/ 確定B（スナップショット走査）/ 確定C（bound method）/ 確定D（accept 後 append + 失敗時非混入）/ 確定E（Origin 明示検証）/ 確定F（receive_text ループ）の契約を検証するケース ✅
- 孤児要件なし

---

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 | characterization 状態 |
|---|---|---|---|---|---|
| FastAPI `WebSocket` オブジェクト | `connect()` / `disconnect()` / `broadcast()` の I/O 対象 | 不要（フレームワーク型。外部 API データではない）| 不要 | ユニット: `AsyncMock` でシミュレート。結合: `TestClient.websocket_connect()` で実接続 | 不要（外部 API 非依存）|
| `asyncio` イベントループ | `InMemoryEventBus.publish()` の非同期実行 | — | — | `pytest-asyncio` + `@pytest.mark.asyncio` | 不要（標準ライブラリ）|

**外部 API・外部サービス依存なし**。全テストケースで characterization fixture は不要。

---

## モック方針

| テストレベル | モック対象 | 方針 |
|---|---|---|
| ユニット | `WebSocket`（FastAPI）| `AsyncMock` で `accept()` / `send_text()` / `receive_text()` をモック。送信失敗シミュレーションは `send_text.side_effect = RuntimeError(...)` で設定 |
| 結合 | モックなし | `starlette.testclient.TestClient.websocket_connect()` で実 ASGI アプリ + 実 `ConnectionManager` + 実 `InMemoryEventBus` を使用 |

raw（integration 用）/ factory（unit 用）の使い分けは本 sub-feature では不要（WebSocket は外部 API データではなくフレームワーク型）。

---

## ユニットテストケース

テストファイル: `tests/unit/test_websocket_broadcast_http_api.py`

### REQ-WSB-009: ConnectionManager.connect()

| テスト ID | 対象クラス.メソッド | 種別 | 入力 | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-101 | `ConnectionManager.connect(websocket)` | 正常系 | `AsyncMock` の `websocket`（`accept()` は正常完了） | `websocket.accept()` が呼ばれ、`cm._connections` に `websocket` が追加される（len が 0 → 1）。§確定D: accept 完了後に append する順序を検証 |
| TC-UT-WSB-102 | `ConnectionManager.connect(websocket)` — MSG-WSB-003 | 正常系 | `AsyncMock` の `websocket` + `caplog` | `caplog` の INFO ログに `"WebSocket client connected: total=1"` が含まれる（MSG-WSB-003 静的照合）|
| TC-UT-WSB-114 | `ConnectionManager.connect(websocket)` — `accept()` 失敗 | 異常系 | `accept()` が `RuntimeError` を発火する `AsyncMock` の `websocket` | `cm._connections` に `websocket` が追加されない（len が 0 のまま）。§確定D 回帰防止: 未 accept の WebSocket が接続プールに混入しないことを検証 |

### REQ-WSB-009: ConnectionManager.disconnect()

| テスト ID | 対象クラス.メソッド | 種別 | 入力 | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-103 | `ConnectionManager.disconnect(websocket)` | 正常系 | 接続プールに存在する `websocket` | `cm._connections` から `websocket` が除去される（len が 1 → 0）|
| TC-UT-WSB-104 | `ConnectionManager.disconnect(websocket)` — MSG-WSB-004 | 正常系 | 接続プールに存在する `websocket` + `caplog` | `caplog` の INFO ログに `"WebSocket client disconnected: total=0"` が含まれる（MSG-WSB-004 静的照合）|
| TC-UT-WSB-105 | `ConnectionManager.disconnect(websocket)` — ガード | 境界値 | 接続プールに**存在しない** `websocket` | 例外なく完了する（`ValueError` が発火しない）。`if websocket in _connections` ガード確認 |

### REQ-WSB-009: ConnectionManager.broadcast()

| テスト ID | 対象クラス.メソッド | 種別 | 入力 | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-106 | `ConnectionManager.broadcast(message)` — 空プール | 境界値 | 接続プールが空（`_connections=[]`）の状態で `broadcast("msg")` | 例外なく完了する。`send_text` は呼ばれない |
| TC-UT-WSB-107 | `ConnectionManager.broadcast(message)` — 1 クライアント | 正常系 | `AsyncMock` の `websocket` 1 個 + `message="hello"` | `websocket.send_text("hello")` が 1 回呼ばれる |
| TC-UT-WSB-108 | `ConnectionManager.broadcast(message)` — 3 クライアント | 正常系 | `AsyncMock` の `websocket` 3 個 + `message="event"` | 全 3 クライアントの `send_text("event")` が各 1 回ずつ呼ばれる（スナップショット走査）|
| TC-UT-WSB-109 | `ConnectionManager.broadcast(message)` — Fail Soft | 異常系 | `ws1`（`send_text` が `RuntimeError` を発火）+ `ws2`（正常）を接続プールに登録し `broadcast("msg")` | `ws1.send_text()` 例外後、`ws1` が `_connections` から除去される。`ws2.send_text("msg")` が呼ばれる。`broadcast()` 例外なく完了する |
| TC-UT-WSB-110 | `ConnectionManager.broadcast(message)` — MSG-WSB-005 | 異常系 | `send_text` が `RuntimeError("fake error")` を発火する `ws` + `caplog` | `caplog` の WARNING ログに `"WebSocket broadcast failed for client:"` が含まれる（MSG-WSB-005 静的照合）|

### REQ-WSB-010: ConnectionManager.handle_event()

§確定C: EventBus bridge handler は `ConnectionManager.handle_event` bound method として lifespan で `event_bus.subscribe(cm.handle_event)` に登録する。

| テスト ID | 対象クラス.メソッド | 種別 | 入力 | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-111 | `ConnectionManager.handle_event` — async メソッド確認 | 正常系 | `ConnectionManager()` インスタンス `cm` | `inspect.iscoroutinefunction(cm.handle_event)` が `True` である。bound method として callable である |
| TC-UT-WSB-112 | `ConnectionManager.handle_event(event)` — broadcast 呼び出し | 正常系 | `broadcast` を `AsyncMock` に置換した `cm` + `TaskStateChangedEventFactory.build()` による `event` | `await cm.handle_event(event)` を呼ぶと `cm.broadcast` が 1 回呼ばれる。引数が `json.dumps(event.to_ws_message())` に一致する JSON 文字列である |
| TC-UT-WSB-113 | `ConnectionManager.handle_event(event)` — JSON 構造 | 正常系 | `broadcast` を `AsyncMock` に置換した `cm` + `ExternalReviewGateStateChangedEventFactory.build()` | `cm.broadcast.call_args[0][0]` を `json.loads()` すると `{"event_type": "external_review_gate.state_changed", "aggregate_id": ..., "aggregate_type": "ExternalReviewGate", "occurred_at": ..., "payload": {...}}` となる（to_ws_message 5 キー構造）|

### §確定E: WebSocket Origin 検証

§確定E: `ws.py` エンドポイントは接続前に Origin ヘッダーを検証し、`BAKUFU_ALLOWED_ORIGINS` 外の Origin を `close(code=1008)` で拒否する。

| テスト ID | 対象クラス.メソッド | 種別 | 入力 | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-115 | `GET /ws` — 不正 Origin 拒否 | 異常系 | `TestClient.websocket_connect("/ws", headers={"origin": "https://attacker.com"})` （`BAKUFU_ALLOWED_ORIGINS` に含まれない Origin）| WebSocket 接続が拒否される。`_connections` に追加されない。§確定E: Cross-Origin WebSocket Hijacking 防止の単体確認 |

---

## 結合テストケース

テストファイル: `tests/integration/test_websocket_broadcast_http_api.py`

**前提**:
- ASGI アプリ: `create_app()` + `starlette.testclient.TestClient` でサーバを起動
- `ConnectionManager`: lifespan で `app.state.connection_manager` として初期化済み
- `InMemoryEventBus`: lifespan で `app.state.event_bus` として初期化済み、`cm.handle_event` が subscribe 済み
- WebSocket クライアント: `TestClient.websocket_connect("/ws")` コンテキストマネージャを使用
- **全 WebSocket 操作に `timeout=5`（秒）を設定する**（CIハング防止のための設計凍結。`receive_json(timeout=5)` / `receive_text(timeout=5)` 等）
- DB: `tmp_path` ベースの SQLite（WebSocket テストでは DB 操作なしだが他テストとの fixture 整合のため `create_all_tables` 実行済み）

| テスト ID | 対象モジュール連携 | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|
| TC-IT-WSB-101 | `GET /ws` 接続確立 → `ConnectionManager._connections` に追加 | `create_app()` lifespan 起動済み / `BAKUFU_ALLOWED_ORIGINS` に合致する Origin ヘッダー付き | `TestClient.websocket_connect("/ws")` コンテキスト内で `app.state.connection_manager._connections` を確認（timeout=5）| `_connections` の len が 1 である。§確定D: accept 完了後 append の結合確認 |
| TC-IT-WSB-102 | `GET /ws` 切断 → `ConnectionManager._connections` から除去 | 接続中（TC-IT-WSB-101 と同構成）| コンテキストマネージャを正常退出（timeout=5）| コンテキスト終了後、`_connections` の len が 0 になる。§確定F: `WebSocketDisconnect` 捕捉 + `disconnect()` 呼び出しの結合確認 |
| TC-IT-WSB-103 | `WebSocketDisconnect` → `cm.disconnect()` が呼ばれる（`close_code` 任意）| `TestClient.websocket_connect("/ws")` で接続済み | `websocket.close()` を明示的に呼ぶ（timeout=5）| `cm._connections` が空になる。例外が外部に伝播しない |
| TC-IT-WSB-104 | `InMemoryEventBus.publish(TaskStateChangedEvent)` → WebSocket クライアントが JSON 受信 | `TestClient.websocket_connect("/ws")` で接続中。EventBus に `cm.handle_event` が登録済み | スレッドセーフな方法（`anyio.from_thread.run_sync` 等）で `event_bus.publish(event)` を呼ぶ（`receive_json(timeout=5)`）| `ws.receive_json()` が `{"event_type": "task.state_changed", "aggregate_id": ..., "aggregate_type": "Task", "occurred_at": ..., "payload": {...}}` の構造を持つ dict を返す |
| TC-IT-WSB-105 | Fail Soft: 切断済みクライアント混在でも残存クライアントへの配信継続 | WS クライアント 2 個が接続済み。1 個目を `close()` して切断（プールからの除去前に broadcast 発生）| `event_bus.publish(event)` を呼ぶ（`receive_json(timeout=5)`）| 2 個目のクライアントが JSON を受信する。`broadcast()` 例外なく完了する。§確定B（スナップショット走査）の結合確認 |
| TC-IT-WSB-106 | lifespan 統合: `app.state.connection_manager` が初期化済み / bridge handler が EventBus に登録済み | `create_app()` をインスタンス化してシングル HTTP リクエストを送信（lifespan を起動させる）| `app.state.connection_manager` と `app.state.event_bus._handlers` の内容を確認（timeout=5）| `app.state.connection_manager` が `ConnectionManager` インスタンスである。`app.state.event_bus._handlers` の len が 1 以上である（`cm.handle_event` が登録済み）。§REQ-WSB-012 / §確定C lifespan 契約の結合確認 |
| TC-IT-WSB-107 | `GET /ws` — 不正 Origin が WebSocket 接続を拒否される | `BAKUFU_ALLOWED_ORIGINS` に含まれない Origin ヘッダーを付与してリクエスト | `TestClient.websocket_connect("/ws", headers={"origin": "https://attacker.com"})` を呼ぶ（timeout=5）| 接続が拒否される（WebSocket close code 1008 または接続確立不可）。`cm._connections` に追加されない。§確定E の結合確認 |

---

## カバレッジ基準

- REQ-WSB-009〜012 の各要件に **最低 1 件** のテストケースが対応する ✅（マトリクス参照）
- MSG-WSB-003〜005 の各文言が **静的文字列照合** で検証される ✅（TC-UT-WSB-102/104/110）
- 確定A〜F の各設計凍結事項が対応するテストケースで検証される ✅
  - 確定D（accept 完了後 append + 失敗時非混入）: TC-UT-WSB-101/114 + TC-IT-WSB-101
  - 確定E（Origin 明示検証）: TC-UT-WSB-115 + TC-IT-WSB-107
- 親 spec §9 受入基準 #1（接続確立）/ #2（task.state_changed 配信）/ #3（external_review_gate.state_changed 配信）/ #5（切断後の残存配信継続）は本 sub-feature の結合テストで部分カバー ✅
- §9 受入基準 #4（agent.status_changed）/ #6（レイテンシ p95 2 秒）は `system-test-design.md` のシステムテストで検証
- 行カバレッジ目標: `interfaces/http/connection_manager.py` + `interfaces/http/routers/ws.py` で **90% 以上**（feature-spec.md §10 Q-2 準拠）

---

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で `pytest (unit + integration)` ジョブが緑
- ローカル:
  ```bash
  cd backend
  uv run pytest tests/unit/test_websocket_broadcast_http_api.py -v
  uv run pytest tests/integration/test_websocket_broadcast_http_api.py -v
  uv run pytest tests/unit/test_websocket_broadcast_http_api.py tests/integration/test_websocket_broadcast_http_api.py \
    --cov=bakufu.interfaces.http.connection_manager \
    --cov=bakufu.interfaces.http.routers.ws \
    --cov-report=term-missing
  ```
- ローカル WebSocket 手動確認（サーバ起動後）:
  ```bash
  # websocat でリアルタイム受信確認
  websocat ws://localhost:8000/ws
  # 別ターミナルで TaskService.cancel() を呼ぶと JSON が届く
  ```

---

## テストディレクトリ構造

```
backend/tests/
├── unit/
│   └── test_websocket_broadcast_http_api.py   # TC-UT-WSB-101〜115
└── integration/
    └── test_websocket_broadcast_http_api.py   # TC-IT-WSB-101〜107
```

---

## 未決課題・要起票 characterization task

本 sub-feature は外部 API・外部サービスに依存しない。`WebSocket` はフレームワーク型（FastAPI/Starlette）であり characterization fixture は不要。

| # | タスク | 状態 |
|---|---|---|
| — | 外部 I/O 依存なし → characterization 不要 | 確定（不要）|

---

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — REQ-WSB-009〜012
- [`detailed-design.md`](detailed-design.md) — MSG-WSB-003〜005 確定文言 / クラス詳細 / 確定A〜F
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様（UC-WSB / 業務ルール R1 / 受入基準 §9）
- [`../system-test-design.md`](../system-test-design.md) — システムテスト（feature 業務概念単位、受入基準全体）
- [`../domain/test-design.md`](../domain/test-design.md) — domain sub-feature テスト設計（TC-UT-WSB-001〜033 / TC-IT-WSB-001〜004）
