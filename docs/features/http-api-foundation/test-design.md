# テスト設計書

<!-- feature: http-api-foundation -->
<!-- 配置先: docs/features/http-api-foundation/test-design.md -->
<!-- 対象範囲: REQ-HAF-001〜007 / 受入基準 1〜5 / §確定 A〜F / MSG-HAF-001〜003 -->

本 feature は FastAPI アプリケーション基盤（app.py / dependencies.py / error_handlers.py / schemas/common.py / routers/health.py / main.py / application services 骨格）に閉じる。個別 Aggregate HTTP API は後続 Issue B〜G の責務であり本 feature の範囲外。

**テストの主役は結合（integration）**である。理由:

1. DI 連鎖（`get_session` → `get_*_repository` → `get_*_service`）の真価は「request スコープで session が生成・close される」「各 Depends が型安全な具象インスタンスを返す」という**配線の物理保証**にあり、unit でモックすると本物の挙動を見失う
2. エラーハンドラは「例外種別 → 統一 ErrorResponse 変換」という I/O 変換であり、httpx TestClient を使えば実 HTTP レスポンスで検証できる
3. unit では「モジュール単体ロジック」（Pydantic スキーマ構造・環境変数デフォルト値・service の commit 非呼び出し）に絞る

## 受入基準一覧

| # | 基準 | 検証テストケース |
|---|------|----------------|
| 1 | `GET /health` が `{"status":"ok"}` を含むレスポンスを返す | TC-E2E-HAF-001/002 |
| 2 | `/openapi.json` が HTTP 200 を返す | TC-E2E-HAF-003 |
| 3 | 不正な JSON ボディの POST が `{"error":{"code":"...","message":"..."}}` を返す | TC-E2E-HAF-004/005 |
| 4 | `BAKUFU_BIND_HOST` / `BAKUFU_BIND_PORT` で bind アドレスが変更できる | TC-UT-HAF-006/007/008 |
| 5 | pyright 0 errors、CI 7 ジョブ全緑 | TC-CI-HAF-001/002 |

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-HAF-001 | `create_app()` lifespan エンジン初期化 | TC-IT-HAF-001 | 結合 | 正常系 | 1, 2 |
| REQ-HAF-001 | lifespan での `app.state.async_sessionmaker` 格納 | TC-IT-HAF-002 | 結合 | 正常系 | 1 |
| REQ-HAF-001 | `GET /openapi.json` HTTP 200 | TC-E2E-HAF-003, TC-IT-HAF-008 | E2E / 結合 | 正常系 | 2 |
| REQ-HAF-001 | CORS: `BAKUFU_CORS_ORIGINS` 未設定 → `http://localhost:5173` のみ許可 | TC-IT-HAF-009 | 結合 | 正常系 | — |
| REQ-HAF-001 | CORS: 未許可 Origin の preflight を拒否（ACAO ヘッダなし） | TC-IT-HAF-010 | 結合 | 異常系 | — |
| REQ-HAF-002 | `get_session()` が `AsyncSession` を yield、request 終了時 close | TC-IT-HAF-003 | 結合 | 正常系 | — |
| REQ-HAF-002 | `get_empire_repository(session)` → `SqliteEmpireRepository(session)` | TC-IT-HAF-004 | 結合 | 正常系 | — |
| REQ-HAF-002 | DI 連鎖 `get_session` → `get_empire_repository` → `get_empire_service` | TC-IT-HAF-005 | 結合 | 正常系 | — |
| REQ-HAF-002 | `app.state` 未初期化時（lifespan 未実行）→ AttributeError → HTTP 500 | TC-IT-HAF-006 | 結合 | 異常系 | 3 |
| REQ-HAF-003 | `HTTPException` → `{"error":{"code":"HTTP_<status>","message":...}}` 変換 | TC-E2E-HAF-005, TC-IT-HAF-011 | E2E / 結合 | 正常系 | 3 |
| REQ-HAF-003 | `RequestValidationError` → HTTP 422 + `{"error":{"code":"VALIDATION_ERROR",...}}` | TC-E2E-HAF-004, TC-IT-HAF-012 | E2E / 結合 | 異常系 | 3 |
| REQ-HAF-003 | `IntegrityError` → HTTP 409 + `{"error":{"code":"CONFLICT",...}}` | TC-IT-HAF-013 | 結合 | 異常系 | 3 |
| REQ-HAF-003 | 未捕捉 `Exception` → HTTP 500 + `{"error":{"code":"INTERNAL_ERROR","message":"Internal server error"}}` | TC-IT-HAF-014 | 結合 | 異常系 | 3 |
| REQ-HAF-003（T4 防御） | HTTP 500 レスポンス body にスタックトレースが含まれない | TC-IT-HAF-015 | 結合 | 異常系 | 3 |
| REQ-HAF-004 | `PaginatedResponse[T]` 4 フィールド（items / total / offset / limit） | TC-UT-HAF-001 | ユニット | 正常系 | — |
| REQ-HAF-004 | `limit` 上限 100 超 → Pydantic validation error（§確定 C） | TC-UT-HAF-002 | ユニット | 境界値 | — |
| REQ-HAF-004 | `ErrorResponse.error.code` / `.message` 構造 | TC-UT-HAF-003 | ユニット | 正常系 | 3 |
| REQ-HAF-004 | `ErrorDetail.detail` は `VALIDATION_ERROR` 時のみ存在（その他 None） | TC-UT-HAF-004 | ユニット | 境界値 | 3 |
| REQ-HAF-005 | `GET /health` → HTTP 200 + `{"status":"ok"}` 含む | TC-E2E-HAF-001 | E2E | 正常系 | 1 |
| REQ-HAF-005 | `GET /health` → `version` フィールドが存在し空でない | TC-E2E-HAF-002 | E2E | 正常系 | 1 |
| REQ-HAF-006 | `BAKUFU_BIND_PORT` が数値でない → `ValueError`（Fail Fast） | TC-UT-HAF-008 | ユニット | 異常系 | 4 |
| REQ-HAF-006 | `BAKUFU_BIND_HOST` 未設定 → `127.0.0.1` デフォルト（§確定 D） | TC-UT-HAF-006 | ユニット | 正常系 | 4 |
| REQ-HAF-006 | `BAKUFU_BIND_PORT` 未設定 → `8000` デフォルト（§確定 D） | TC-UT-HAF-007 | ユニット | 正常系 | 4 |
| REQ-HAF-006 | `BAKUFU_RELOAD` 未設定 → `False` デフォルト（本番安全デフォルト、§確定 D） | TC-UT-HAF-009 | ユニット | 正常系 | 4 |
| REQ-HAF-007 | `EmpireService.__init__` が `EmpireRepository` Protocol を受け取る | TC-UT-HAF-010 | ユニット | 正常系 | — |
| REQ-HAF-007 | `service.save()` が `commit()` を呼ばない（§確定 R1-H） | TC-UT-HAF-011 | ユニット | 正常系 | — |
| REQ-HAF-007 | `service.find_all(offset, limit)` → `(items, total)` tuple（§確定 F） | TC-UT-HAF-012, TC-IT-HAF-016 | ユニット / 結合 | 正常系 | — |
| REQ-HAF-007 | service が `Sqlite*Repository` 具象型でなく Repository Protocol に依存する | TC-UT-HAF-013 | ユニット | 正常系 | — |
| §確定 E | `HTTP_xxx` / `VALIDATION_ERROR` / `CONFLICT` / `INTERNAL_ERROR` の 4 コード体系 | TC-UT-HAF-014 | ユニット | 正常系 | 3 |
| MSG-HAF-001 | `[FAIL] Internal server error` 文言確認（HTTP 500） | TC-IT-HAF-014 | 結合 | 異常系 | 3 |
| MSG-HAF-002 | `[FAIL] Validation error:` 文言確認（HTTP 422） | TC-IT-HAF-012 | 結合 | 異常系 | 3 |
| MSG-HAF-003 | `[FAIL] Conflict:` 文言確認（HTTP 409） | TC-IT-HAF-013 | 結合 | 異常系 | 3 |
| AC-5（pyright） | pyright 0 errors | TC-CI-HAF-001 | CI | — | 5 |
| AC-5（CI 全緑） | CI 7 ジョブ全緑 | TC-CI-HAF-002 | CI | — | 5 |

**マトリクス充足の証拠**:
- REQ-HAF-001〜007 すべてに最低 1 件のテストケース
- 受入基準 1〜5 すべてにテストケース対応あり
- §確定 A（lifespan エンジン初期化）/ B（request スコープ session）/ C（limit 上限 100）/ D（環境変数デフォルト値）/ E（エラーコード 4 種）/ F（service 戻り値 tuple）すべてに証拠ケース
- T4（スタックトレース露出防止）に TC-IT-HAF-015 で物理確認
- MSG-HAF-001〜003 すべてに文言照合ケース
- 孤児要件ゼロ

## 外部 I/O 依存マップ

本 feature は外部 API / 外部サービス / ファイルシステムへの依存なし。
SQLite DB は M2 で確立済みの実接続を使用（テスト時は `:memory:` SQLite を使用、lifespan=False + テスト用 `app.state` 直接注入）。

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|---------|------|------------|---------|----------------------|
| SQLite（in-memory） | テスト用 DB | 不要（M2 で確立済み） | 不要 | 済（M2 スコープ） |
| 環境変数（`BAKUFU_*`） | bind 設定・CORS 設定 | 不要 | 不要（os.environ monkeypatch） | 済（ユニットテスト内完結） |

外部 API（LLM / Discord / GitHub）: M5/M4 スコープ。本 feature で依存なし。Characterization task 不要。

## モック方針

### E2E テスト
- `httpx.AsyncClient(app=create_app(), base_url="http://test")` でインプロセス完結
- `lifespan=False` を create_app に渡し、`app.state.async_sessionmaker` に in-memory SQLite sessionmaker を直接注入
- DB は M2 のテスト用 `session_factory` fixture を流用（Alembic head 適用済み in-memory）
- モック不使用（DB も本物の SQLite を使う）

### 結合テスト
- 同上（httpx + in-memory SQLite）
- エラーハンドラのテスト: テスト用ルートを dynamic に登録して例外を raise させる（`app.add_api_route("/test-error", handler)` 方式）
- `IntegrityError` シミュレーション: 同一 id の Aggregate を 2 回 save → UPSERT または UNIQUE 制約違反を誘発

### ユニットテスト
- Pydantic スキーマ（`PaginatedResponse[T]` / `ErrorResponse`）: モック不要（schema 単体バリデーション）
- main.py の環境変数読み取り: `monkeypatch.setenv` で `os.environ` を差し替え
- service の commit 非呼び出し: `unittest.mock.MagicMock` で Repository を注入し `mock.commit.assert_not_called()`
- service の Repository Protocol 依存: `isinstance(service._repo, <ConcreteClass>)` でなく Protocol の duck typing で確認

## テストケース詳細

### E2E テスト（受入基準検証）

---

#### TC-E2E-HAF-001: GET /health → {"status":"ok"}（受入基準 1）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-005 |
| 工程 | 要件定義 |
| 種別 | 正常系 |
| 前提条件 | FastAPI アプリ起動済み（TestClient）。認証不要 |
| 操作 | `GET /health` |
| 期待結果 | HTTP 200 / レスポンス body に `"status": "ok"` を含む |

---

#### TC-E2E-HAF-002: GET /health → version フィールド存在（受入基準 1 補足）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-005 |
| 工程 | 要件定義 |
| 種別 | 正常系 |
| 前提条件 | FastAPI アプリ起動済み |
| 操作 | `GET /health` |
| 期待結果 | HTTP 200 / レスポンス body に `"version"` フィールドが存在し空文字列でない |

---

#### TC-E2E-HAF-003: GET /openapi.json → HTTP 200（受入基準 2）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 要件定義 |
| 種別 | 正常系 |
| 前提条件 | FastAPI アプリ起動済み |
| 操作 | `GET /openapi.json` |
| 期待結果 | HTTP 200 / Content-Type: application/json |

---

#### TC-E2E-HAF-004: 不正 JSON POST → {"error":...} 形式（受入基準 3、RequestValidationError）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 要件定義 |
| 種別 | 異常系 |
| 前提条件 | FastAPI アプリ起動済み。Pydantic body を期待するエンドポイントが存在する |
| 操作 | `POST /api/<endpoint>` に `Content-Type: application/json` + 不正な JSON ボディ（例: `{"invalid_field": 123}`） |
| 期待結果 | HTTP 422 / body が `{"error":{"code":"VALIDATION_ERROR","message":"..."}}` 形式 |

---

#### TC-E2E-HAF-005: HTTPException → {"error":...} 形式（受入基準 3、HTTPException）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 要件定義 |
| 種別 | 異常系 |
| 前提条件 | テスト用ルート（`HTTPException(status_code=404, detail="Not found")` を raise）が存在 |
| 操作 | テスト用ルートへの GET リクエスト |
| 期待結果 | HTTP 404 / body が `{"error":{"code":"HTTP_404","message":"Not found"}}` |

---

### 結合テスト（基本設計 モジュール間連携）

---

#### TC-IT-HAF-001: lifespan エンジン初期化（§確定 A、REQ-HAF-001）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | `create_app()` に実 lifespan を渡して TestClient を生成 |
| 操作 | TestClient の context manager 入退出（`with TestClient(create_app()) as client:`） |
| 期待結果 | `app.state.async_sessionmaker` が `None` でない / `AsyncEngine` が生成されエラーなく dispose される |

---

#### TC-IT-HAF-002: `app.state.async_sessionmaker` 格納確認（§確定 A）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | lifespan 付き TestClient |
| 操作 | lifespan 実行後に `app.state.async_sessionmaker` を参照 |
| 期待結果 | `async_sessionmaker` インスタンスが格納されている（`async_sessionmaker` 型） |

---

#### TC-IT-HAF-003: `get_session()` request スコープ（§確定 B、REQ-HAF-002）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-002 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | in-memory SQLite sessionmaker を `app.state` に注入。session の close を記録するテスト用ルート |
| 操作 | テスト用ルートに 2 回リクエスト送信 |
| 期待結果 | リクエストごとに別の `AsyncSession` インスタンスが生成され、各リクエスト終了後に session が close される |

---

#### TC-IT-HAF-004: DI factory `get_empire_repository` 型確認（REQ-HAF-002）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-002 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | in-memory SQLite セッションで `get_empire_repository(session)` を呼び出せるテスト |
| 操作 | `session` を直接渡して `get_empire_repository(session)` を呼び出す |
| 期待結果 | 戻り値が `EmpireRepository` Protocol を満たす（duck typing: `find_by_id` / `count` / `save` を持つ） |

---

#### TC-IT-HAF-005: DI 連鎖 full path（REQ-HAF-002、§確定 G）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-002 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | in-memory SQLite + lifespan 付き TestClient |
| 操作 | `Depends(get_empire_service)` を使うテスト用ルートへの GET リクエスト |
| 期待結果 | ルートハンドラが `EmpireService` インスタンスを受け取りエラーなく実行できる |

---

#### TC-IT-HAF-006: `app.state` 未初期化 → HTTP 500（REQ-HAF-002 異常系）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-002 |
| 工程 | 基本設計 |
| 種別 | 異常系 |
| 前提条件 | `create_app(lifespan=None)` かつ `app.state` に sessionmaker を注入しない |
| 操作 | `Depends(get_session)` を使うルートへのリクエスト |
| 期待結果 | HTTP 500 / `{"error":{"code":"INTERNAL_ERROR","message":"..."}}` |

---

#### TC-IT-HAF-008: GET /openapi.json → HTTP 200 + JSON（REQ-HAF-001）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | TestClient 起動済み |
| 操作 | `GET /openapi.json` |
| 期待結果 | HTTP 200 / body が JSON 解析可能 / `"paths"` キーを含む OpenAPI スキーマ |

---

#### TC-IT-HAF-009: CORS 未設定デフォルト（§確定 R1-F、REQ-HAF-001）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | `BAKUFU_CORS_ORIGINS` 未設定で `create_app()` |
| 操作 | `Origin: http://localhost:5173` ヘッダ付きリクエスト |
| 期待結果 | レスポンスに `Access-Control-Allow-Origin: http://localhost:5173` が含まれる |

---

#### TC-IT-HAF-010: CORS 未許可 Origin 拒否（§確定 R1-F）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 基本設計 |
| 種別 | 異常系 |
| 前提条件 | `BAKUFU_CORS_ORIGINS` 未設定 |
| 操作 | `Origin: https://evil.example.com` ヘッダ付きリクエスト |
| 期待結果 | レスポンスに `Access-Control-Allow-Origin` ヘッダが含まれない |

---

#### TC-IT-HAF-011: `HTTPException` 変換（REQ-HAF-003、§確定 E）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | `HTTPException(status_code=404, detail="Resource not found")` を raise するテスト用ルート |
| 操作 | テスト用ルートへのリクエスト |
| 期待結果 | HTTP 404 / `{"error":{"code":"HTTP_404","message":"Resource not found"}}` |

---

#### TC-IT-HAF-012: `RequestValidationError` 変換 + MSG-HAF-002 照合（REQ-HAF-003）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 基本設計 |
| 種別 | 異常系 |
| 前提条件 | Pydantic body (`id: UUID`) を期待するテスト用ルート |
| 操作 | `id` フィールドに `"not-a-uuid"` を POST |
| 期待結果 | HTTP 422 / `{"error":{"code":"VALIDATION_ERROR","message":"..."}}` / `"detail"` フィールドがリスト形式で存在 |

---

#### TC-IT-HAF-013: `IntegrityError` 変換 + MSG-HAF-003 照合（REQ-HAF-003）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 基本設計 |
| 種別 | 異常系 |
| 前提条件 | `sqlalchemy.exc.IntegrityError` を raise するテスト用ルート |
| 操作 | テスト用ルートへのリクエスト |
| 期待結果 | HTTP 409 / `{"error":{"code":"CONFLICT","message":"..."}}` / `message` に `"Conflict"` または `"conflict"` を含む |

---

#### TC-IT-HAF-014: 未捕捉 Exception → HTTP 500 + MSG-HAF-001 照合（REQ-HAF-003）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 基本設計 |
| 種別 | 異常系 |
| 前提条件 | `RuntimeError("unexpected")` を raise するテスト用ルート |
| 操作 | テスト用ルートへのリクエスト |
| 期待結果 | HTTP 500 / `{"error":{"code":"INTERNAL_ERROR","message":"Internal server error"}}` |

---

#### TC-IT-HAF-015: HTTP 500 レスポンス body にスタックトレースなし（T4 防御）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 基本設計 |
| 種別 | 異常系 |
| 前提条件 | `RuntimeError("secret internal reason")` を raise するテスト用ルート |
| 操作 | テスト用ルートへのリクエスト |
| 期待結果 | HTTP 500 / response body に `"traceback"` / `"secret internal reason"` / `"Traceback"` が含まれない |

---

#### TC-IT-HAF-016: `service.find_all()` → `(items, total)` tuple（§確定 F）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-007 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | in-memory SQLite に Empire 3 件 INSERT 済み |
| 操作 | `empire_service.find_all(offset=0, limit=10)` |
| 期待結果 | 戻り値が `(list[Empire], int)` 型 / `total == 3` / `len(items) == 3` |

---

### ユニットテスト（詳細設計 クラス/メソッド）

---

#### TC-UT-HAF-001: `PaginatedResponse[T]` 4 フィールド構造（§確定 C）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-004 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `PaginatedResponse(items=[...], total=5, offset=0, limit=20)` を構築 |
| 期待結果 | `items` / `total` / `offset` / `limit` の 4 フィールドが model_dump に含まれる |

---

#### TC-UT-HAF-002: `limit` 上限 100 超 → ValidationError（§確定 C）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-004 |
| 工程 | 詳細設計 |
| 種別 | 境界値 |
| 操作 | `PaginatedResponse(items=[], total=0, offset=0, limit=101)` を構築 |
| 期待結果 | `pydantic.ValidationError` が raise される |

---

#### TC-UT-HAF-003: `ErrorResponse` body 構造（§確定 E）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-004 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `ErrorResponse(error=ErrorDetail(code="HTTP_404", message="Not found"))` を構築 |
| 期待結果 | `model_dump()` が `{"error":{"code":"HTTP_404","message":"Not found"}}` と一致 |

---

#### TC-UT-HAF-004: `ErrorDetail.detail` は VALIDATION_ERROR 時のみ（§確定 E）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-004 |
| 工程 | 詳細設計 |
| 種別 | 境界値 |
| 操作 | `detail=None` で ErrorDetail 構築 / `detail=[{"field": "id", "error": "invalid"}]` で構築 |
| 期待結果 | `detail=None` の場合 model_dump で `detail` が `None` または欠落 / リスト付きの場合 `detail` フィールドにリストが入る |

---

#### TC-UT-HAF-006: `BAKUFU_BIND_HOST` 未設定 → `127.0.0.1`（§確定 D）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-006 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `BAKUFU_BIND_HOST` を unset して main.py の bind 設定読み取り関数を呼ぶ |
| 期待結果 | host が `"127.0.0.1"` |

---

#### TC-UT-HAF-007: `BAKUFU_BIND_PORT` 未設定 → `8000`（§確定 D）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-006 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `BAKUFU_BIND_PORT` を unset して bind 設定読み取り関数を呼ぶ |
| 期待結果 | port が `8000` |

---

#### TC-UT-HAF-008: `BAKUFU_BIND_PORT` 非数値 → `ValueError`（§確定 D、Fail Fast）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-006 |
| 工程 | 詳細設計 |
| 種別 | 異常系 |
| 操作 | `BAKUFU_BIND_PORT=abc` を設定して bind 設定読み取り関数を呼ぶ |
| 期待結果 | `ValueError` が raise される |

---

#### TC-UT-HAF-009: `BAKUFU_RELOAD` 未設定 → `False`（§確定 D）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-006 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `BAKUFU_RELOAD` を unset して bind 設定読み取り関数を呼ぶ |
| 期待結果 | reload が `False` |

---

#### TC-UT-HAF-010: service が Repository Protocol を受け取る（REQ-HAF-007）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-007 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `EmpireService(mock_repo)` を構築（`mock_repo` は `EmpireRepository` Protocol を満たす MagicMock） |
| 期待結果 | 構築が成功する / `service._repo is mock_repo` |

---

#### TC-UT-HAF-011: `service.save()` が `commit()` を呼ばない（§確定 R1-H）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-007 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `mock_repo` を注入した `EmpireService.save(empire)` を呼ぶ |
| 期待結果 | `mock_repo.session.commit.assert_not_called()` が pass（または commit 相当の呼び出しがない） |

---

#### TC-UT-HAF-012: `service.find_all()` が `(items, total)` tuple を返す（§確定 F）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-007 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `mock_repo.find_all.return_value = [empire1, empire2]` / `mock_repo.count.return_value = 2` で `find_all(offset=0, limit=20)` |
| 期待結果 | 戻り値が `([empire1, empire2], 2)` の tuple |

---

#### TC-UT-HAF-013: service が Repository 具象型でなく Protocol に依存（REQ-HAF-007）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-007 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `EmpireService` のソースコードの import を確認（`SqliteEmpireRepository` を直接 import していないこと） |
| 期待結果 | `EmpireService` が `bakufu.infrastructure.*` への直接 import を持たない（pyright + grep で確認） |

---

#### TC-UT-HAF-014: エラーコード 4 種の文字列確認（§確定 E）

| 項目 | 内容 |
|------|------|
| 対応 REQ 確定 E | §確定 E |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | エラーコード定数（または文字列リテラル）の値を確認 |
| 期待結果 | `"HTTP_404"` 形式 / `"VALIDATION_ERROR"` / `"CONFLICT"` / `"INTERNAL_ERROR"` が大文字スネークケース ASCII |

---

### CI テスト

---

#### TC-CI-HAF-001: pyright 0 errors（受入基準 5）

| 項目 | 内容 |
|------|------|
| 対応 受入基準 | 5 |
| 操作 | `uv run pyright` |
| 期待結果 | `0 errors, 0 warnings` |

---

#### TC-CI-HAF-002: CI 7 ジョブ全緑（受入基準 5）

| 項目 | 内容 |
|------|------|
| 対応 受入基準 | 5 |
| 操作 | PR の CI（branch-policy / pr-title-check / lint / typecheck / test-backend / test-frontend / audit） |
| 期待結果 | 全 7 ジョブが ✅ |
