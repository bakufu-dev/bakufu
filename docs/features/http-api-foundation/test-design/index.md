# テスト設計書 — index

<!-- feature: http-api-foundation -->
<!-- 配置先: docs/features/http-api-foundation/test-design/index.md -->
<!-- 対象範囲: REQ-HAF-001〜007 / 受入基準 1〜5 / §確定 A〜F / MSG-HAF-001〜003 -->

本 feature は FastAPI アプリケーション基盤（app.py / dependencies.py / error_handlers.py / schemas/common.py / routers/health.py / main.py / application services 骨格）に閉じる。個別 Aggregate HTTP API は後続 Issue B〜G の責務であり本 feature の範囲外。

**テストの主役は結合（integration）**である。理由:

1. DI 連鎖（`get_session` → `get_*_repository` → `get_*_service`）の真価は「request スコープで session が生成・close される」「各 Depends が型安全な具象インスタンスを返す」という**配線の物理保証**にあり、unit でモックすると本物の挙動を見失う
2. エラーハンドラは「例外種別 → 統一 ErrorResponse 変換」という I/O 変換であり、httpx TestClient を使えば実 HTTP レスポンスで検証できる
3. unit では「モジュール単体ロジック」（Pydantic スキーマ構造・環境変数デフォルト値・service の commit 非呼び出し）に絞る

## ファイル構成

| ファイル | 内容 |
|--------|------|
| [index.md](index.md)（本ファイル）| 受入基準一覧 / テストマトリクス / 外部I/O依存マップ / モック方針 |
| [e2e.md](e2e.md) | E2Eテストケース（TC-E2E-HAF-001〜005）/ 結合テストケース（TC-IT-HAF-001〜016）|
| [unit.md](unit.md) | ユニットテストケース（TC-UT-HAF-001〜015）/ CI テスト（TC-CI-HAF-001〜002）|

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
| REQ-HAF-001（T2 防御） | `BAKUFU_CORS_ORIGINS=*` → `ValueError` Fail Fast（起動拒否）| TC-UT-HAF-015 | ユニット | 異常系 | — |
| REQ-HAF-002 | `get_session()` が `AsyncSession` を yield、request 終了時 close | TC-IT-HAF-003 | 結合 | 正常系 | — |
| REQ-HAF-002 | `get_empire_repository(session)` → `SqliteEmpireRepository(session)` | TC-IT-HAF-004 | 結合 | 正常系 | — |
| REQ-HAF-002 | DI 連鎖 `get_session` → `get_empire_repository` → `get_empire_service` | TC-IT-HAF-005 | 結合 | 正常系 | — |
| REQ-HAF-002 | `app.state` 未初期化時（lifespan 未実行）→ AttributeError → HTTP 500 | TC-IT-HAF-006 | 結合 | 異常系 | 3 |
| REQ-HAF-003 | `HTTPException` → `{"error":{"code":"HTTP_<status>","message":...}}` 変換 | TC-E2E-HAF-005, TC-IT-HAF-011 | E2E / 結合 | 正常系 | 3 |
| REQ-HAF-003 | `RequestValidationError` → HTTP 422 + `{"error":{"code":"VALIDATION_ERROR",...}}` | TC-E2E-HAF-004, TC-IT-HAF-012 | E2E / 結合 | 異常系 | 3 |
| REQ-HAF-003 | `IntegrityError` → HTTP 409 + `{"error":{"code":"CONFLICT_DUPLICATE" or "CONFLICT_FK",...}}` | TC-IT-HAF-013 | 結合 | 異常系 | 3 |
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
| §確定 E | `HTTP_xxx` / `VALIDATION_ERROR` / `CONFLICT_DUPLICATE` / `CONFLICT_FK` / `INTERNAL_ERROR` のコード体系 | TC-UT-HAF-014 | ユニット | 正常系 | 3 |
| MSG-HAF-001 | `[FAIL] Internal server error` 文言確認（HTTP 500） | TC-IT-HAF-014 | 結合 | 異常系 | 3 |
| MSG-HAF-002 | `[FAIL] Validation error:` 文言確認（HTTP 422） | TC-IT-HAF-012 | 結合 | 異常系 | 3 |
| MSG-HAF-003 | `[FAIL] Conflict:` 文言確認（HTTP 409）+ コード分離確認 | TC-IT-HAF-013 | 結合 | 異常系 | 3 |
| AC-5（pyright） | pyright 0 errors | TC-CI-HAF-001 | CI | — | 5 |
| AC-5（CI 全緑） | CI 7 ジョブ全緑 | TC-CI-HAF-002 | CI | — | 5 |

**マトリクス充足の証拠**:
- REQ-HAF-001〜007 すべてに最低 1 件のテストケース
- 受入基準 1〜5 すべてにテストケース対応あり
- §確定 A（lifespan エンジン初期化）/ B（request スコープ session）/ C（limit 上限 100）/ D（環境変数デフォルト値）/ E（エラーコード体系）/ F（service 戻り値 tuple）すべてに証拠ケース
- T2（CORS ワイルドカード禁止）に TC-UT-HAF-015 で物理確認（タブリーズ指摘対応）
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
