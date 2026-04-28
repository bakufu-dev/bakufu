# 詳細設計書

> feature: `http-api-foundation`
> 関連: [basic-design.md](basic-design.md) / [`docs/architecture/tech-stack.md`](../../architecture/tech-stack.md) / FastAPI 公式ドキュメント

## 記述ルール（必ず守ること）

詳細設計に**疑似コード・サンプル実装（python/ts/sh/yaml 等の言語コードブロック）を書かない**。
ソースコードと二重管理になりメンテナンスコストしか生まない。
必要なのは「構造契約（属性名・型・制約）」と「確定文言（メッセージ文字列）」と「実装の意図」。

## クラス設計（詳細）

### FastAPI Application

| 関数 / クラス | シグネチャ | 戻り値 | 意図 |
|------------|----------|--------|------|
| `create_app` | `(lifespan: Callable | None = None) -> FastAPI` | `FastAPI` | テスト時に lifespan を差し替え可能にするファクトリ関数 |
| `lifespan` | `(app: FastAPI) -> AsyncGenerator[None, None]` | `AsyncGenerator` | `asynccontextmanager` デコレーター。yield 前に `AsyncEngine` / `async_sessionmaker` 生成 + `app.state` 格納。yield 後にエンジン dispose |

### Dependencies モジュール

| 関数 | シグネチャ | 戻り値 | 意図 |
|------|----------|--------|------|
| `get_session` | `(request: Request) -> AsyncGenerator[AsyncSession, None]` | yields `AsyncSession` | request スコープ session。finally で close |
| `get_empire_repository` | `(session: AsyncSession = Depends(get_session)) -> EmpireRepository` | `SqliteEmpireRepository(session)` | EmpireRepository Protocol を満たす concrete 注入 |
| `get_empire_service` | `(repo: EmpireRepository = Depends(get_empire_repository)) -> EmpireService` | `EmpireService(repo)` | service 注入 |
| `get_room_repository` | `(session: AsyncSession = Depends(get_session)) -> RoomRepository` | `SqliteRoomRepository(session)` | RoomRepository Protocol を満たす concrete 注入 |
| `get_room_service` | `(repo: RoomRepository = Depends(get_room_repository)) -> RoomService` | `RoomService(repo)` | service 注入 |
| `get_workflow_repository` | `(session: AsyncSession = Depends(get_session)) -> WorkflowRepository` | `SqliteWorkflowRepository(session)` | WorkflowRepository Protocol を満たす concrete 注入 |
| `get_workflow_service` | `(repo: WorkflowRepository = Depends(get_workflow_repository)) -> WorkflowService` | `WorkflowService(repo)` | service 注入 |
| `get_agent_repository` | `(session: AsyncSession = Depends(get_session)) -> AgentRepository` | `SqliteAgentRepository(session)` | AgentRepository Protocol を満たす concrete 注入 |
| `get_agent_service` | `(repo: AgentRepository = Depends(get_agent_repository)) -> AgentService` | `AgentService(repo)` | service 注入 |
| `get_directive_repository` | `(session: AsyncSession = Depends(get_session)) -> DirectiveRepository` | `SqliteDirectiveRepository(session)` | DirectiveRepository Protocol を満たす concrete 注入 |
| `get_directive_service` | `(repo: DirectiveRepository = Depends(get_directive_repository)) -> DirectiveService` | `DirectiveService(repo)` | service 注入 |
| `get_task_repository` | `(session: AsyncSession = Depends(get_session)) -> TaskRepository` | `SqliteTaskRepository(session)` | TaskRepository Protocol を満たす concrete 注入 |
| `get_task_service` | `(repo: TaskRepository = Depends(get_task_repository)) -> TaskService` | `TaskService(repo)` | service 注入 |
| `get_gate_repository` | `(session: AsyncSession = Depends(get_session)) -> GateRepository` | `SqliteGateRepository(session)` | GateRepository Protocol を満たす concrete 注入 |
| `get_gate_service` | `(repo: GateRepository = Depends(get_gate_repository)) -> GateService` | `GateService(repo)` | service 注入 |

### application services の構造（全 7 service 共通パターン）

| メソッド | シグネチャ | 戻り値 | 意図 |
|---------|----------|--------|------|
| `__init__` | `(repo: <Name>Repository)` | `None` | Repository Port を受け取る（DI） |
| `find_by_id` | `(id: <Name>Id) -> <Name> \| None` | `<Name> \| None` | 薄い委譲 |
| `find_all` | `(offset: int = 0, limit: int = 20) -> tuple[list[<Name>], int]` | `(items, total)` | PaginatedResponse 構築用に total も返す |
| `save` | `(entity: <Name>) -> None` | `None` | 薄い委譲。commit は呼び出し元が行う |

## 確定事項（先送り撤廃）

<!-- requirements-analysis.md §確定 R1-A 等で凍結した内容のうち、構造契約レベルでさらに細部を確定するものをここで凍結。 -->

### 確定 A: lifespan 方式でのエンジン初期化（§確定 R1-A 詳細）

- `create_engine()` / `async_sessionmaker` は lifespan の起動側（yield 前）で一度だけ生成
- `app.state.async_sessionmaker` に格納することで `get_session()` が `request.app.state` 経由でアクセス可能
- テスト時は `TestClient` に lifespan=False を渡し、代わりにテスト用 in-memory SQLite の session を直接 `app.state` に注入する
- 根拠: FastAPI 公式ドキュメント "lifespan events" 参照。`startup` event は 0.95+ で deprecated

### 確定 B: session scope = request（§確定 R1-B 詳細）

- `get_session()` は `yield session` パターン。1 HTTP リクエスト = 1 `AsyncSession`
- transaction 境界（`async with session.begin():`）は application service の `save()` 呼び出し元（router handler）が管理
- service 内で `commit()` / `rollback()` は呼ばない（M2 Repository §確定 R1-A と同方針）
- 根拠: session を request スコープに閉じることで、異なる request 間の session 共有による副作用を排除（SQLAlchemy asyncio best practices）

### 確定 C: ページネーション offset/limit（§確定 R1-C 詳細）

- `PaginatedResponse[T]` の `offset: int`（≥0）/ `limit: int`（1〜100、デフォルト 20）
- `limit` 上限 100 は MVP スケールの DoS 防止。後続 Issue で変更する場合は本書を先に更新すること
- cursor-based pagination は YAGNI（MVP の SQLite シングルユーザーで十分）

### 確定 D: bind 設定（§確定 R1-D 詳細）

- `BAKUFU_BIND_HOST` 未設定 → `127.0.0.1`
- `BAKUFU_BIND_PORT` 未設定 → `8000`
- `BAKUFU_RELOAD` 未設定 → `false`（本番安全デフォルト）
- `BAKUFU_CORS_ORIGINS` 未設定 → `http://localhost:5173`（開発安全デフォルト）
- `BAKUFU_TRUST_PROXY` 未設定 → `false`（外部公開安全デフォルト）

### 確定 E: エラーコード体系

- `HTTP_<status>`: HTTPException（例: `HTTP_404`, `HTTP_409`）
- `VALIDATION_ERROR`: RequestValidationError
- `CONFLICT`: IntegrityError
- `INTERNAL_ERROR`: 未捕捉 Exception
- 全コードは大文字スネークケース ASCII 文字列。後続 Issue でコードを追加する場合は本書 §確定 E に追記してから実装すること

### 確定 F: `find_all` の戻り値が `tuple[list[T], int]`（total を含む）

- `total` は `COUNT(*)` クエリで取得（Repository の `count()` を呼ぶ）
- PaginatedResponse 構築には `items + total + offset + limit` の 4 要素が必要
- service が `(items, total)` tuple を返すことで router が 2 クエリを個別に発行する重複を排除

## 設計判断の補足

<!-- 「なぜこの API 形か」「なぜこのデフォルト値か」など、コードを読んでも分からない判断理由を残す。 -->

### なぜ `create_app()` ファクトリ関数か

- モジュールレベルで `app = FastAPI()` と定義するとテスト時に lifespan を制御できない
- ファクトリ関数にすることで `create_app(lifespan=test_lifespan)` の形でテスト用 lifespan を差し込める
- httpx の `AsyncClient(app=create_app(), ...)` パターンでインプロセステストが可能

### なぜ service が Repository Protocol に依存するか（Sqlite具象型でなく）

- Clean Architecture Port 契約。テスト時に mock/stub Repository を注入可能
- 後続フェーズで Postgres へのDB移行が発生しても service 層に変更不要

### なぜ transaction 境界を router handler に置くか

- service は単一 Aggregate の操作のみ担当（M3 スコープ）。複数 Aggregate をまたぐ操作は application layer の上位（router / use case）が担当する設計
- M5（LLM Adapter）では task.advance() + Gate 生成 + Outbox event 発行を同一 UoW でラップする必要があり、その時点で router handler が `async with session.begin():` を持つ設計が生きる

## ユーザー向けメッセージの確定文言

`requirements.md §ユーザー向けメッセージ一覧` で ID のみ定義した MSG を、本書で**正確な文言**として凍結する。実装者が勝手に改変できない契約。変更は本書の更新 PR のみで許可。

### プレフィックス統一

| プレフィックス | 意味 |
|--------------|-----|
| `[FAIL]` | 処理中止を伴う失敗 |
| `[OK]` | 成功完了 |
| `[SKIP]` | 冪等実行による省略 |
| `[WARN]` | 警告（処理は継続） |
| `[INFO]` | 情報提供（処理は継続） |

### MSG 確定文言表

| ID | 出力先 | 文言（必要なら 2 行構造） |
|----|------|----------------------|
| MSG-HAF-001 | HTTP 500 response body | `[FAIL] Internal server error` / `Retry or contact administrator if issue persists` |
| MSG-HAF-002 | HTTP 422 response body | `[FAIL] Validation error: <field_path> - <error>` |
| MSG-HAF-003 | HTTP 409 response body | `[FAIL] Conflict: resource already exists or constraint violation` |

## データ構造（永続化キー）

該当なし — 理由: 本 feature は新規テーブルなし

### `/health` レスポンス構造

| フィールド | 型 | 必須 | 説明 |
|----------|----|----|----|
| `status` | `Literal["ok"]` | 必須 | 常に `"ok"`（ヘルスチェック失敗は HTTP 非 200 で表現） |
| `version` | `str` | 必須 | `pyproject.toml` の version 文字列（例: `"0.1.0"`） |

### `PaginatedResponse[T]` 構造

| フィールド | 型 | 必須 | 説明 |
|----------|----|----|----|
| `items` | `list[T]` | 必須 | ページ内の要素リスト |
| `total` | `int` | 必須 | 全件数（`COUNT(*)`） |
| `offset` | `int` | 必須 | リクエストの offset 値 |
| `limit` | `int` | 必須 | リクエストの limit 値 |

### `ErrorResponse` 構造

| フィールド | 型 | 必須 | 説明 |
|----------|----|----|----|
| `error` | `ErrorDetail` | 必須 | エラー詳細 |

### `ErrorDetail` 構造

| フィールド | 型 | 必須 | 説明 |
|----------|----|----|----|
| `code` | `str` | 必須 | エラーコード（§確定 E の体系に従う） |
| `message` | `str` | 必須 | 人間可読メッセージ（MSG-HAF-NNN 文言） |
| `detail` | `list[dict] \| None` | 任意 | `VALIDATION_ERROR` 時のフィールド別詳細のみ |

## API エンドポイント詳細

<!-- requirements.md の API 仕様外形を、HTTP ステータス・エラーコード・WebSocket イベント名まで凍結する。 -->

### GET /health

| 項目 | 内容 |
|----|----|
| 用途 | プロセス生存確認（DB ping なし）|
| 認証 | なし |
| リクエスト Body | なし |
| 成功レスポンス | HTTP 200 + `{"status":"ok","version":"<str>"}` |
| 失敗レスポンス | 該当なし（プロセスが生きていれば必ず 200 を返す）|
| 副作用 | なし |

### GET /openapi.json

| 項目 | 内容 |
|----|----|
| 用途 | OpenAPI スキーマ取得（UI 開発開始のアンブロック）|
| 認証 | なし |
| リクエスト Body | なし |
| 成功レスポンス | HTTP 200 + JSON |
| 失敗レスポンス | 該当なし |
| 副作用 | なし |

## 出典・参考

<!-- 公式ドキュメント / RFC / 学術論文 / OWASP / 業界標準ガイドラインの URL を列挙。検証可能性を担保する。 -->

- [FastAPI — Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) — lifespan 採用根拠
- [FastAPI — Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) — Depends パターン
- [SQLAlchemy 2.x — Using AsyncSession](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — async session best practices
- [OWASP Top 10 2021](https://owasp.org/Top10/) — セキュリティ設計根拠
- [`docs/architecture/tech-stack.md`](../../architecture/tech-stack.md) §ネットワーク/TLS 方針 — loopback バインド根拠
