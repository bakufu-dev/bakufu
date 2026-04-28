# 要件定義書

> feature: `http-api-foundation`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/architecture/tech-stack.md`](../../architecture/tech-stack.md)

## 機能要件

### REQ-HAF-001: FastAPI アプリ初期化

| 項目 | 内容 |
|------|------|
| 入力 | 環境変数 `BAKUFU_CORS_ORIGINS`（カンマ区切り URL 列） |
| 処理 | `@asynccontextmanager lifespan(app)` で `AsyncEngine` 作成 → `async_sessionmaker` 生成 → `app.state` に格納。`CORSMiddleware` を `allow_origins=parsed_origins` で設定。全ルーター（health + 後続 B〜G）を prefix `/api` でインクルード |
| 出力 | ASGI アプリケーション（`FastAPI` インスタンス） |
| エラー時 | lifespan 初期化失敗 → uvicorn 起動失敗（Fail Fast、Backend が起動しない） |

### REQ-HAF-002: DI コンテナ

| 項目 | 内容 |
|------|------|
| 入力 | `Request` オブジェクト（FastAPI Depends 連鎖） |
| 処理 | `get_session()` は `app.state.async_sessionmaker` から `AsyncSession` を yield（request スコープ、§確定 R1-B）。`get_empire_repository(session)` は `SqliteEmpireRepository(session)` を返す。同様に全 7 Repository の factory を定義。`get_empire_service(repo)` 等 Service factory も定義 |
| 出力 | 各 Depends が型安全な Repository / Service インスタンス |
| エラー時 | `app.state` 未初期化（lifespan 未実行）→ `AttributeError` → 500 → エラーハンドラが `{"error":{"code":"INTERNAL_ERROR","message":"..."}}` で応答 |

### REQ-HAF-003: エラーハンドリング

| 項目 | 内容 |
|------|------|
| 入力 | FastAPI / SQLAlchemy / Pydantic が raise した例外 |
| 処理 | `HTTPException` → `{"error":{"code":"HTTP_<status>","message":detail}}`。`RequestValidationError` → HTTP 422 `{"error":{"code":"VALIDATION_ERROR","message":"..."}}` + `detail` フィールドにフィールド別エラー。`sqlalchemy.exc.IntegrityError` → HTTP 409。UNIQUE 制約違反は `code: "CONFLICT"`（MSG-HAF-003）、FK 制約違反は `code: "DEPENDENCY"`（MSG-HAF-004）で判別して返す（判別方法は detailed-design.md §確定 E）。`Exception`（その他）→ HTTP 500 `{"error":{"code":"INTERNAL_ERROR","message":"Internal server error"}}`（スタックトレースは stdout には出すが response には含めない） |
| 出力 | 統一エラー JSON レスポンス |
| エラー時 | 該当なし — 理由: エラーハンドラ自体が例外を raise した場合は uvicorn がデフォルト 500 を返す |

### REQ-HAF-004: 共通 Pydantic スキーマ

| 項目 | 内容 |
|------|------|
| 入力 | 任意の Pydantic モデル型 `T` |
| 処理 | `PaginatedResponse[T]` は `items: list[T]`, `total: int`, `offset: int`, `limit: int` の 4 フィールド。`ErrorResponse` は `error: ErrorDetail`。`ErrorDetail` は `code: str`, `message: str`（`detail: list | None` はオプション） |
| 出力 | OpenAPI schema に自動登録される Pydantic モデル |
| エラー時 | 型不一致は pyright strict で build time 検出 |

### REQ-HAF-005: ヘルスチェック

| 項目 | 内容 |
|------|------|
| 入力 | `GET /health`（認証なし） |
| 処理 | `{"status":"ok","version":"<bakufu_version>"}` を返す。DB ping は行わない（ヘルスチェックの責務は「プロセス生存確認」のみ） |
| 出力 | HTTP 200 + `{"status":"ok","version":"<str>"}` |
| エラー時 | 該当なし — 理由: プロセスが生きていれば必ず 200 を返す |

### REQ-HAF-006: uvicorn エントリポイント

| 項目 | 内容 |
|------|------|
| 入力 | 環境変数 `BAKUFU_BIND_HOST`（デフォルト: `127.0.0.1`）/ `BAKUFU_BIND_PORT`（デフォルト: `8000`）/ `BAKUFU_RELOAD`（デフォルト: `false`） |
| 処理 | `uvicorn.run(app, host=..., port=..., reload=...)` を `main.py` の `if __name__ == "__main__":` で呼ぶ。`BAKUFU_RELOAD=true` は開発時のみ（本番は `false` 必須） |
| 出力 | uvicorn プロセス起動（`127.0.0.1:8000` 既定） |
| エラー時 | `BAKUFU_BIND_PORT` が数値でない → `ValueError` → Fail Fast（起動失敗） |

### REQ-HAF-007: application services 骨格

| 項目 | 内容 |
|------|------|
| 入力 | 各 Repository Port インスタンス |
| 処理 | `backend/src/bakufu/application/services/` 配下に `empire_service.py` / `room_service.py` / `workflow_service.py` / `agent_service.py` / `directive_service.py` / `task_service.py` / `gate_service.py` を配置。各 service は対応 Repository Port を `__init__` で受け取り、CRUD の中継のみ行う（M3 スコープ）。`save()` / `find_by_id()` / `find_all()` / `count()` を thin wrapper として実装 |
| 出力 | 後続 Issue B〜G が `Depends(get_<name>_service)` で受け取れる service インスタンス |
| エラー時 | Repository の `IntegrityError` は上位伝播（service 内で catch しない） |

<!-- requirements-analysis.md の機能一覧に列挙された REQ-XX-NNN を全件詳細化する。孤児要件を作らない。 -->

## 画面・CLI 仕様

<!-- ユーザーが直接触れる画面 / CLI / API のインタフェース外形。実装の細部は detailed-design.md で凍結する。 -->

### CLI レシピ / コマンド

該当なし — 理由: 本 feature は HTTP API 基盤。Admin CLI は `feature/admin-cli` で扱う

| コマンド | 概要 |
|---------|------|
| （なし） | — |

### Web UI 画面

該当なし — 理由: 本 feature は backend のみ

| 画面ID | 画面名 | 主要操作 |
|-------|-------|---------|
| （なし） | — | — |

## API 仕様

<!-- REST / WebSocket / IPC のエンドポイント外形。詳細は detailed-design.md。-->

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| GET | `/health` | プロセス生存確認 | なし | `{"status":"ok","version":"<str>"}` |
| GET | `/openapi.json` | OpenAPI スキーマ | なし | JSON Schema |
| GET | `/docs` | Swagger UI（開発時のみ） | なし | HTML |

## データモデル

本 feature は新規テーブルなし — 理由: 既存 M2 のスキーマを利用するのみ

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| （なし） | — | — | — | — |

## ユーザー向けメッセージ一覧

<!-- ID 規則: MSG-<feature 略号>-<3 桁連番>。文言確定は detailed-design.md で行うが、本書では「種別 + 表示条件」を凍結。 -->

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|----|------|----------------|---------|
| MSG-HAF-001 | エラー | `Internal server error` | 未捕捉例外（HTTP 500）|
| MSG-HAF-002 | エラー | `Validation error: <fields>` | RequestValidationError（HTTP 422）|
| MSG-HAF-003 | エラー | `Conflict: resource already exists` | UNIQUE 制約違反（重複作成, HTTP 409）|
| MSG-HAF-004 | エラー | `Conflict: dependency constraint violation` | FK 制約違反（HTTP 409）|

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | FastAPI | pyproject.toml | uv | 既存（tech-stack.md 採用済み）|
| Python 依存 | Pydantic v2 | pyproject.toml | uv | 既存 |
| Python 依存 | uvicorn | pyproject.toml | uv | 既存 |
| Python 依存 | SQLAlchemy 2.x / aiosqlite | pyproject.toml | uv | 既存（M2 で導入済み）|
| Python 依存 | pytest + pytest-asyncio + httpx | pyproject.toml | uv | 既存（テスト用）|
