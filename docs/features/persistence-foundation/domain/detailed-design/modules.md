# 詳細設計補章: Module 別仕様

> 親: [`../detailed-design.md`](../detailed-design.md)。本書は infrastructure 層の各 Module の関数・属性・カラム契約を凍結する真実源。

## Module: `infrastructure/config/data_dir.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `resolve()` | なし | `pathlib.Path` | 絶対パス、解決済み（symlink 展開後） |
| `_default_for_os()` | なし | `pathlib.Path` | Linux/macOS: `${XDG_DATA_HOME:-$HOME/.local/share}/bakufu` / Windows: `%LOCALAPPDATA%\bakufu` |
| `_validate_absolute(value: str)` | `str` | `pathlib.Path` | 相対パス / NUL バイト / `..` を含む値で `BakufuConfigError(MSG-PF-001)` |

**module 状態**:
- `_resolved: pathlib.Path | None = None`（singleton キャッシュ、`resolve()` 初回呼び出しで確定）

## Module: `infrastructure/persistence/sqlite/engine.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `create_engine(url: str, debug: bool = False)` | url, debug | `AsyncEngine` | **application 接続用**。`sqlalchemy.ext.asyncio.create_async_engine` を呼び、接続 listener `_set_pragmas` で PRAGMA 8 件を SET（`defensive=ON` / `writable_schema=OFF` / `trusted_schema=OFF` を含む、[`pragma.md`](pragma.md) §確定 D-1） |
| `create_migration_engine(url: str)` | url | `AsyncEngine` | **migration 接続用**（dual connection、[`pragma.md`](pragma.md) §確定 D-2）。Alembic 専用 engine を `_set_migration_pragmas` で生成（`defensive=OFF` / `writable_schema=ON` の DDL 許容セット）。Bootstrap stage 3 でのみ使用、stage 3 終了時に `dispose()` で破棄（[`pragma.md`](pragma.md) §確定 D-3） |
| `_set_pragmas(dbapi_conn, _connection_record)` | DBAPI conn, connection record | None | application 接続 event listener、[`pragma.md`](pragma.md) §確定 D-1 の **8 件**を SET |
| `_set_migration_pragmas(dbapi_conn, _connection_record)` | 同上 | None | migration 専用 listener、[`pragma.md`](pragma.md) §確定 D-2 の DDL 許容 PRAGMA を SET |

**PRAGMA SET 順序の詳細**: [`pragma.md`](pragma.md) §確定 D-1（application 接続 8 件） / §確定 D-2（migration 接続）を真実源とする。本 Module 説明では 5 件の旧リストを保持しない（記述衝突を避ける、Schneier 漏れ 2 対応）。

**根拠**: SQLite の `journal_mode=WAL` は接続レベル設定だが永続化される（DB ファイルメタデータ）。`foreign_keys` は接続レベルで毎接続 SET 必須。busy_timeout は接続レベル。詳細は [SQLite PRAGMA](https://www.sqlite.org/pragma.html) 公式参照。

## Module: `infrastructure/persistence/sqlite/session.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `make_session_factory(engine: AsyncEngine)` | engine | `async_sessionmaker[AsyncSession]` | `expire_on_commit=False`, `autoflush=False`, `class_=AsyncSession` |

**module 状態**:
- `session_factory: async_sessionmaker[AsyncSession] | None = None`（singleton、Bootstrap が engine 生成後に初期化）

## Module: `infrastructure/persistence/sqlite/base.py`

| 名前 | 種別 | 内容 |
|----|----|----|
| `Base` | declarative base | `DeclarativeBase` を継承した bakufu 共通 base |
| `UUIDStr` | TypeDecorator | UUID を `CHAR(32)` hex 形式で永続化、Python 側は `uuid.UUID` |
| `UTCDateTime` | TypeDecorator | datetime を UTC で永続化、tz-aware を要求（naive datetime は Fail Fast） |
| `JSONEncoded` | TypeDecorator | dict / list を JSON 文字列で永続化（`json.dumps(..., ensure_ascii=False, sort_keys=True)`、masking なしの中立 type） |
| `MaskedJSONEncoded` | TypeDecorator | `JSONEncoded` を拡張、`process_bind_param` で `MaskingGateway.mask_in()` 適用後に JSON エンコード（[`triggers.md`](triggers.md) §確定 B、Core / ORM 両経路で発火） |
| `MaskedText` | TypeDecorator | `Text` を拡張、`process_bind_param` で `MaskingGateway.mask()` 適用後に文字列を返す |

## Module: `infrastructure/persistence/sqlite/tables/audit_log.py`

| カラム | 型 | 制約 | 意図 |
|----|----|----|----|
| `id` | `UUIDStr` | PK, NOT NULL | UUIDv4 |
| `actor` | `String(255)` | NOT NULL | OS ユーザー名 + ホスト名 |
| `command` | `String(64)` | NOT NULL | enum string（`retry-task` / `cancel-task` / `retry-event` / `list-blocked` / `list-dead-letters`） |
| `args_json` | `MaskedJSONEncoded` | NOT NULL | `process_bind_param` で `MaskingGateway.mask_in()` 適用後に JSON エンコード（[`triggers.md`](triggers.md) §確定 B） |
| `result` | `String(16)` | NULL | NULL → SUCCESS / FAILURE |
| `error_text` | `MaskedText` | NULL | `process_bind_param` で `MaskingGateway.mask()` 適用 |
| `executed_at` | `UTCDateTime` | NOT NULL | UTC |

**masking 配線**: `mapped_column(MaskedJSONEncoded, ...)` / `mapped_column(MaskedText, ...)` で宣言。SQLAlchemy が bind parameter 解決時に `process_bind_param` を発火、Core `insert(table).values({...})` 経路でも捕捉される（旧 event listener 方式は不発火、PR #23 BUG-PF-001 で反転）。

## Module: `infrastructure/persistence/sqlite/tables/pid_registry.py`

| カラム | 型 | 制約 | 意図 |
|----|----|----|----|
| `pid` | `Integer` | PK, NOT NULL | OS の PID |
| `parent_pid` | `Integer` | NOT NULL | bakufu Backend 自身の `os.getpid()` |
| `started_at` | `UTCDateTime` | NOT NULL | `psutil.Process.create_time()` 値（PID 衝突対策の比較キー） |
| `cmd` | `MaskedText` | NOT NULL | `process_bind_param` で `MaskingGateway.mask()` 適用（CLI flags に env 値が混入し得るため必須） |
| `task_id` | `UUIDStr` | NULL | task と紐づく場合（後続 PR で FK 追加） |
| `stage_id` | `UUIDStr` | NULL | stage と紐づく場合 |

**masking 配線**: `mapped_column(MaskedText, ...)` で宣言（[`triggers.md`](triggers.md) §確定 B）。Core / ORM 両経路で `process_bind_param` 発火。

## Module: `infrastructure/persistence/sqlite/tables/outbox.py`

| カラム | 型 | 制約 | 意図 |
|----|----|----|----|
| `event_id` | `UUIDStr` | PK, NOT NULL | UUIDv4、Handler 冪等性キー |
| `event_kind` | `String(64)` | NOT NULL | `DirectiveIssued` 等の enum string |
| `aggregate_id` | `UUIDStr` | NOT NULL | 発火元 Aggregate |
| `payload_json` | `MaskedJSONEncoded` | NOT NULL | `process_bind_param` で `MaskingGateway.mask_in()` 適用後に JSON エンコード（[`triggers.md`](triggers.md) §確定 B） |
| `created_at` | `UTCDateTime` | NOT NULL | UTC |
| `status` | `String(16)` | NOT NULL | `PENDING` / `DISPATCHING` / `DISPATCHED` / `DEAD_LETTER` |
| `attempt_count` | `Integer` | NOT NULL DEFAULT 0 | リトライ回数 |
| `next_attempt_at` | `UTCDateTime` | NOT NULL | UTC |
| `last_error` | `MaskedText` | NULL | `process_bind_param` で `MaskingGateway.mask()` 適用 |
| `updated_at` | `UTCDateTime` | NOT NULL | UTC、リカバリ判定用 |
| `dispatched_at` | `UTCDateTime` | NULL | UTC |

**INDEX**: `(status, next_attempt_at)`（polling SQL の最適化）

**masking 配線**: `mapped_column(MaskedJSONEncoded, ...)` / `mapped_column(MaskedText, ...)` で宣言。Schneier 申し送り #6（Outbox `payload_json` / `last_error` 永続化前マスキング）が Core / ORM 両経路で物理保証される（TC-IT-PF-020 PASSED で検証）。

## Module: `infrastructure/security/masking.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `mask(value: str)` | str | str | 起動時に compile 済みの正規表現 + 環境変数辞書を順次適用 |
| `mask_in(obj: object)` | dict / list / str / int / None | 同型 | dict / list を再帰走査、str に対して `mask()` を適用 |

**適用順序（厳守、[`storage.md`](../../../design/domain-model/storage.md) §適用順序）**:

1. **環境変数値の伏字化**（最も具体的）— 起動時 `_load_env_patterns()` が実施
2. **正規表現パターンマッチ**（9 種、[`masking.md`](masking.md) §確定 A の表）
3. **ホームパス置換**（`$HOME` 絶対パス → `<HOME>`）

## Module: `infrastructure/security/masked_env.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `load_env_patterns()` | なし | `list[tuple[str, re.Pattern]]` | 起動時に 1 回呼ばれる、`os.environ` から既知 env キーの値を取り長さ 8 以上ならパターン辞書化 |

**対象環境変数**（`storage.md` 既存定義に従う）:

`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GH_TOKEN` / `GITHUB_TOKEN` / `OAUTH_CLIENT_SECRET` / `BAKUFU_DISCORD_BOT_TOKEN`

長さ 8 以上の値のみパターン化（短すぎる値は誤マッチを起こす）。値は `re.escape()` でエスケープしてから compile。

**`BAKUFU_DB_KEY` を削除した理由**（Schneier 中等 2 対応）:

- MVP では SQLite at-rest 暗号化（SQLCipher 等）を採用しない方針（`functional-scope.md` §含めない機能）。OAuth トークン暗号化保存・SQLite 暗号化は Phase 2 対応
- 「実は何にも使ってない env を masking 対象として列挙している」状態は混乱の元
- 漏洩時の対応は **OS file mode 0600 + OS ユーザー隔離** に頼る（threat-model.md §T5 / §T6）
- Phase 2 で SQLCipher を導入する際に再度 masking 対象に追加し、設計書 1 箇所（本書）で確定する

代わりに `BAKUFU_DISCORD_BOT_TOKEN` を追加（threat-model.md §資産 で「高」機密性が明記され、Discord 通知経路の核となる秘密）。

## Module: `infrastructure/persistence/sqlite/outbox/dispatcher.py`

| 属性 | 型 | 値 |
|----|----|----|
| `batch_size` | `int` | `50`（1 ポーリングで取得する最大行数） |
| `poll_interval_seconds` | `float` | `1.0` |
| `dispatching_recovery_minutes` | `int` | `5`（DISPATCHING 行の強制再取得判定） |
| `max_attempts` | `int` | `5`（dead-letter 化閾値） |

**polling 取得条件（構造契約、コードブロック禁止）**:

| 条件 | 値 | 意図 |
|----|----|----|
| WHERE: 第 1 項 | `status == 'PENDING'` AND `next_attempt_at <= :now` | 通常の retry 対象行 |
| WHERE: 第 2 項（OR 合成） | `status == 'DISPATCHING'` AND `updated_at < :now - dispatching_recovery_minutes` | クラッシュ後の再取得（5 分閾値、[`pragma.md`](pragma.md) §確定 D-1） |
| ORDER BY | `next_attempt_at ASC` | backoff 設計どおりの公平な順序 |
| LIMIT | `batch_size`（既定 50） | 1 サイクル当たりの上限 |

実装は SQLAlchemy 2.x の `select(OutboxRow)` + `where(or_(...))` + `order_by(...)` + `limit(...)` で構築する。raw SQL は使わない（[`tech-stack.md`](../../../design/tech-stack.md) §ORM 確定方針による）。具体的なクエリ構築は実装 PR で行う（本書では構造契約のみ）。

**backoff スケジュール**:

| attempt_count | 次の `next_attempt_at` (now + ...) |
|---|---|
| 1 | 10 秒 |
| 2 | 1 分 |
| 3 | 5 分 |
| 4 | 30 分 |
| 5 | 30 分 |
| 6 以上 | dead-letter（次の試行はしない） |

`events-and-outbox.md` §Retry 戦略 と同一。

## Module: `infrastructure/persistence/sqlite/outbox/handler_registry.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `register(event_kind: str, handler: Callable)` | event_kind, async handler | None | 既存登録があれば上書き禁止（`KeyError` raise）、テスト時は `clear()` で初期化 |
| `resolve(event_kind: str)` | event_kind | `Callable` | 未登録なら `HandlerNotRegisteredError`（dispatcher は warn ログ + 行を再 PENDING に戻す） |

**module 状態**:
- `_handlers: dict[str, Callable] = {}`

本 Issue では Handler 実装を **登録しない**（空レジストリ）。後続 PR が `feature/{event-kind}-handler` で個別に register する。

## Module: `infrastructure/persistence/sqlite/pid_gc.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `run_startup_gc()` | なし | None | テーブル全行に対し `_classify_row` → 孤児なら `_kill_descendants` |
| `_classify_row(row)` | row | `Literal['orphan_kill', 'protected', 'absent']` | `psutil.Process(pid).create_time()` と `started_at` を比較 |
| `_kill_descendants(pid: int)` | pid | None | `psutil.Process(pid).children(recursive=True)` で SIGTERM → 5s grace → SIGKILL |

**判定ロジック**:

| 状況 | psutil 結果 | 判定 |
|----|----|----|
| プロセスが存在しない | `psutil.NoSuchProcess` | `absent` — テーブルから DELETE のみ |
| プロセスが存在し `create_time()` が `started_at` と一致 | OK | `orphan_kill` — 子孫含めて kill + DELETE |
| プロセスが存在し `create_time()` が `started_at` と不一致 | OK | `protected` — PID 再利用された別プロセス、テーブルから DELETE のみ（kill しない） |
| 権限不足 | `psutil.AccessDenied` | WARN ログ、当該行は次回 GC で再試行（DELETE しない） |

詳細手順は [`bootstrap.md`](bootstrap.md) §確定 E。

## Module: `infrastructure/storage/attachment_root.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `ensure_root()` | なし | `pathlib.Path` | `<DATA_DIR>/attachments/` を作成、POSIX なら `0700` で chmod |
| `start_orphan_gc_scheduler()` | なし | `asyncio.Task` | 24h 周期の GC タスクを起動（実 GC は本 Issue では空実装、後続 `feature/attachment-store` PR が中身を実装） |

## Module: `infrastructure/exceptions.py`

| 例外 | 継承元 | 用途 |
|----|----|----|
| `BakufuConfigError` | `Exception` | DATA_DIR / engine / migration 設定エラー |
| `BakufuMigrationError` | `BakufuConfigError` | Alembic migration 失敗専用 |
| `HandlerNotRegisteredError` | `KeyError` | Handler レジストリで未登録 event_kind |

## Module: `main.py`（Bootstrap）

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `Bootstrap.run()` | なし | None | 起動シーケンス 8 段階を順次実行、各段階失敗で `sys.exit(1)`。`try / finally` で stage 6/7 task の cleanup（[`bootstrap.md`](bootstrap.md) §確定 J） |

8 段階の実装は [`../feature-spec.md`](../feature-spec.md) §確定 R1-C の順序通り。各段階の前後でログを出力（masking 適用済み）。詳細は [`bootstrap.md`](bootstrap.md)。
