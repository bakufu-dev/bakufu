# 詳細設計書

> feature: `persistence-foundation`
> 関連: [basic-design.md](basic-design.md) / [`tech-stack.md`](../../architecture/tech-stack.md) §ORM / [`storage.md`](../../architecture/domain-model/storage.md) §シークレットマスキング規則 / [`events-and-outbox.md`](../../architecture/domain-model/events-and-outbox.md) §`domain_event_outbox`

## 記述ルール（必ず守ること）

詳細設計に**疑似コード・サンプル実装（python/ts/sh/yaml 等の言語コードブロック）を書かない**。
ソースコードと二重管理になりメンテナンスコストしか生まない。
必要なのは「構造契約（属性名・型・制約）」と「確定文言（メッセージ文字列）」と「実装の意図」。

## クラス設計（詳細）

```mermaid
classDiagram
    class DataDirResolver {
        +resolve() Path
    }
    class SqliteEngine {
        +create_engine(url: str, debug: bool) AsyncEngine
    }
    class MaskingGateway {
        +mask(value: str) str
        +mask_in(obj: object) object
    }
    class OutboxDispatcher {
        +start() None
        +stop() None
        -batch_size: int = 50
        -poll_interval_seconds: float = 1.0
        -dispatching_recovery_minutes: int = 5
        -max_attempts: int = 5
    }
    class HandlerRegistry {
        +register(event_kind: str, handler: Callable) None
        +resolve(event_kind: str) Callable
    }
    class PidRegistryGC {
        +run_startup_gc() None
        -sigterm_grace_seconds: int = 5
    }
    class Bootstrap {
        +run() None
    }
```

### Module: `infrastructure/config/data_dir.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `resolve()` | なし | `pathlib.Path` | 絶対パス、解決済み（symlink 展開後） |
| `_default_for_os()` | なし | `pathlib.Path` | Linux/macOS: `${XDG_DATA_HOME:-$HOME/.local/share}/bakufu` / Windows: `%LOCALAPPDATA%\bakufu` |
| `_validate_absolute(value: str)` | `str` | `pathlib.Path` | 相対パス / NUL バイト / `..` を含む値で `BakufuConfigError(MSG-PF-001)` |

**module 状態**:
- `_resolved: pathlib.Path | None = None`（singleton キャッシュ、`resolve()` 初回呼び出しで確定）

### Module: `infrastructure/persistence/sqlite/engine.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `create_engine(url: str, debug: bool = False)` | url, debug | `AsyncEngine` | `sqlalchemy.ext.asyncio.create_async_engine` を呼び、接続 listener で PRAGMA を SET |
| `_set_pragmas(dbapi_conn, _connection_record)` | DBAPI conn, connection record | None | event listener、PRAGMA 5 件を SET |

**PRAGMA SET 順序（固定）**:

1. `PRAGMA journal_mode=WAL` — 最初に WAL モード切替（他 PRAGMA より先）
2. `PRAGMA foreign_keys=ON` — 接続ごとに ON（既定 OFF のため必須）
3. `PRAGMA busy_timeout=5000` — ms 単位
4. `PRAGMA synchronous=NORMAL` — WAL モード下で安全
5. `PRAGMA temp_store=MEMORY` — 一時テーブルのメモリ化

**根拠**: SQLite の `journal_mode=WAL` は接続レベル設定だが永続化される（DB ファイルメタデータ）。`foreign_keys` は接続レベルで毎接続 SET 必須。busy_timeout は接続レベル。詳細は [SQLite PRAGMA](https://www.sqlite.org/pragma.html) 公式参照。

### Module: `infrastructure/persistence/sqlite/session.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `make_session_factory(engine: AsyncEngine)` | engine | `async_sessionmaker[AsyncSession]` | `expire_on_commit=False`, `autoflush=False`, `class_=AsyncSession` |

**module 状態**:
- `session_factory: async_sessionmaker[AsyncSession] | None = None`（singleton、Bootstrap が engine 生成後に初期化）

### Module: `infrastructure/persistence/sqlite/base.py`

| 名前 | 種別 | 内容 |
|----|----|----|
| `Base` | declarative base | `DeclarativeBase` を継承した bakufu 共通 base |
| `UUIDStr` | TypeDecorator | UUID を `CHAR(32)` hex 形式で永続化、Python 側は `uuid.UUID` |
| `UTCDateTime` | TypeDecorator | datetime を UTC で永続化、tz-aware を要求（naive datetime は Fail Fast） |
| `JSONEncoded` | TypeDecorator | dict / list を JSON 文字列で永続化（`json.dumps(..., ensure_ascii=False, sort_keys=True)`） |

### Module: `infrastructure/persistence/sqlite/tables/audit_log.py`

| カラム | 型 | 制約 | 意図 |
|----|----|----|----|
| `id` | `UUIDStr` | PK, NOT NULL | UUIDv4 |
| `actor` | `String(255)` | NOT NULL | OS ユーザー名 + ホスト名 |
| `command` | `String(64)` | NOT NULL | enum string（`retry-task` / `cancel-task` / `retry-event` / `list-blocked` / `list-dead-letters`） |
| `args_json` | `JSONEncoded` | NOT NULL | masking 適用済み |
| `result` | `String(16)` | NULL | NULL → SUCCESS / FAILURE |
| `error_text` | `Text` | NULL | masking 適用済み |
| `executed_at` | `UTCDateTime` | NOT NULL | UTC |

**event listener 配線**: `before_insert` / `before_update` で `target.args_json` / `target.error_text` に `MaskingGateway.mask_in()` / `mask()` を適用してから INSERT / UPDATE。

### Module: `infrastructure/persistence/sqlite/tables/pid_registry.py`

| カラム | 型 | 制約 | 意図 |
|----|----|----|----|
| `pid` | `Integer` | PK, NOT NULL | OS の PID |
| `parent_pid` | `Integer` | NOT NULL | bakufu Backend 自身の `os.getpid()` |
| `started_at` | `UTCDateTime` | NOT NULL | `psutil.Process.create_time()` 値（PID 衝突対策の比較キー） |
| `cmd` | `Text` | NOT NULL | masking 適用済み |
| `task_id` | `UUIDStr` | NULL | task と紐づく場合（後続 PR で FK 追加） |
| `stage_id` | `UUIDStr` | NULL | stage と紐づく場合 |

**event listener 配線**: `before_insert` / `before_update` で `target.cmd` に `MaskingGateway.mask()` を適用。

### Module: `infrastructure/persistence/sqlite/tables/outbox.py`

| カラム | 型 | 制約 | 意図 |
|----|----|----|----|
| `event_id` | `UUIDStr` | PK, NOT NULL | UUIDv4、Handler 冪等性キー |
| `event_kind` | `String(64)` | NOT NULL | `DirectiveIssued` 等の enum string |
| `aggregate_id` | `UUIDStr` | NOT NULL | 発火元 Aggregate |
| `payload_json` | `JSONEncoded` | NOT NULL | masking 適用済み |
| `created_at` | `UTCDateTime` | NOT NULL | UTC |
| `status` | `String(16)` | NOT NULL | `PENDING` / `DISPATCHING` / `DISPATCHED` / `DEAD_LETTER` |
| `attempt_count` | `Integer` | NOT NULL DEFAULT 0 | リトライ回数 |
| `next_attempt_at` | `UTCDateTime` | NOT NULL | UTC |
| `last_error` | `Text` | NULL | masking 適用済み |
| `updated_at` | `UTCDateTime` | NOT NULL | UTC、リカバリ判定用 |
| `dispatched_at` | `UTCDateTime` | NULL | UTC |

**INDEX**: `(status, next_attempt_at)`（polling SQL の最適化）

**event listener 配線**: `before_insert` / `before_update` で `target.payload_json` / `target.last_error` に `MaskingGateway.mask_in()` / `mask()` を適用。

### Module: `infrastructure/security/masking.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `mask(value: str)` | str | str | 起動時に compile 済みの正規表現 + 環境変数辞書を順次適用 |
| `mask_in(obj: object)` | dict / list / str / int / None | 同型 | dict / list を再帰走査、str に対して `mask()` を適用 |

**適用順序（厳守、[`storage.md`](../../architecture/domain-model/storage.md) §適用順序）**:

1. **環境変数値の伏字化**（最も具体的）— 起動時 `_load_env_patterns()` が実施
2. **正規表現パターンマッチ**（9 種、§確定 A の表）
3. **ホームパス置換**（`$HOME` 絶対パス → `<HOME>`）

### Module: `infrastructure/security/masked_env.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `load_env_patterns()` | なし | `list[tuple[str, re.Pattern]]` | 起動時に 1 回呼ばれる、`os.environ` から既知 env キーの値を取り長さ 8 以上ならパターン辞書化 |

**対象環境変数**（`storage.md` 既存定義に従う）:

`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GH_TOKEN` / `GITHUB_TOKEN` / `OAUTH_CLIENT_SECRET` / `BAKUFU_DISCORD_BOT_TOKEN`

長さ 8 以上の値のみパターン化（短すぎる値は誤マッチを起こす）。値は `re.escape()` でエスケープしてから compile。

**`BAKUFU_DB_KEY` を削除した理由**（Schneier 中等 2 対応）:

- MVP では SQLite at-rest 暗号化（SQLCipher 等）を採用しない方針（[`mvp-scope.md`](../../architecture/mvp-scope.md) §含めない機能 §「OAuth トークン暗号化保存 ... SQLite 暗号化は Sub-issue C 相当の Phase 2 で対応」）
- 「実は何にも使ってない env を masking 対象として列挙している」状態は混乱の元
- 漏洩時の対応は **OS file mode 0600 + OS ユーザー隔離** に頼る（threat-model.md §T5 / §T6）
- Phase 2 で SQLCipher を導入する際に再度 masking 対象に追加し、設計書 1 箇所（本書）で確定する

代わりに `BAKUFU_DISCORD_BOT_TOKEN` を追加（threat-model.md §資産 で「高」機密性が明記され、Discord 通知経路の核となる秘密）。

### Module: `infrastructure/persistence/sqlite/outbox/dispatcher.py`

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
| WHERE: 第 2 項（OR 合成） | `status == 'DISPATCHING'` AND `updated_at < :now - dispatching_recovery_minutes` | クラッシュ後の再取得（5 分閾値、§確定 D-1） |
| ORDER BY | `next_attempt_at ASC` | backoff 設計どおりの公平な順序 |
| LIMIT | `batch_size`（既定 50） | 1 サイクル当たりの上限 |

実装は SQLAlchemy 2.x の `select(OutboxRow)` + `where(or_(...))` + `order_by(...)` + `limit(...)` で構築する。raw SQL は使わない（[`tech-stack.md`](../../architecture/tech-stack.md) §ORM 確定方針による）。具体的なクエリ構築は実装 PR で行う（本書では構造契約のみ）。

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

### Module: `infrastructure/persistence/sqlite/outbox/handler_registry.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `register(event_kind: str, handler: Callable)` | event_kind, async handler | None | 既存登録があれば上書き禁止（`KeyError` raise）、テスト時は `clear()` で初期化 |
| `resolve(event_kind: str)` | event_kind | `Callable` | 未登録なら `HandlerNotRegisteredError`（dispatcher は warn ログ + 行を再 PENDING に戻す） |

**module 状態**:
- `_handlers: dict[str, Callable] = {}`

本 Issue では Handler 実装を **登録しない**（空レジストリ）。後続 PR が `feature/{event-kind}-handler` で個別に register する。

### Module: `infrastructure/persistence/sqlite/pid_gc.py`

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

### Module: `infrastructure/storage/attachment_root.py`

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `ensure_root()` | なし | `pathlib.Path` | `<DATA_DIR>/attachments/` を作成、POSIX なら `0700` で chmod |
| `start_orphan_gc_scheduler()` | なし | `asyncio.Task` | 24h 周期の GC タスクを起動（実 GC は本 Issue では空実装、後続 `feature/attachment-store` PR が中身を実装） |

### Module: `infrastructure/exceptions.py`

| 例外 | 継承元 | 用途 |
|----|----|----|
| `BakufuConfigError` | `Exception` | DATA_DIR / engine / migration 設定エラー |
| `BakufuMigrationError` | `BakufuConfigError` | Alembic migration 失敗専用 |
| `HandlerNotRegisteredError` | `KeyError` | Handler レジストリで未登録 event_kind |

### Module: `main.py`（Bootstrap）

| 関数 | 引数 | 戻り値 | 制約 |
|----|----|----|----|
| `Bootstrap.run()` | なし | None | 起動シーケンス 8 段階を順次実行、各段階失敗で `sys.exit(1)` |

8 段階の実装は §確定 R1-C の順序通り。各段階の前後でログを出力（masking 適用済み）。

## 確定事項（先送り撤廃）

### 確定 A: マスキング 9 種正規表現 + 環境変数 + ホームパス

[`storage.md`](../../architecture/domain-model/storage.md) §マスキング対象パターン の表を本 feature の `masking.py` に**そのまま**実装する。改変・追加は本 Issue では行わない（追加が必要な場合は別 Issue で `storage.md` 更新 + 同期 PR）。

#### 9 種の正規表現（凍結）

| 種別 | 正規表現 | 置換後 |
|----|----|----|
| Anthropic API key | `sk-ant-(api03-)?[A-Za-z0-9_\-]{40,}` | `<REDACTED:ANTHROPIC_KEY>` |
| OpenAI API key | `sk-[A-Za-z0-9]{20,}`（`sk-ant-` を除く、negative lookahead） | `<REDACTED:OPENAI_KEY>` |
| GitHub PAT | `(ghp\|gho\|ghu\|ghs\|ghr)_[A-Za-z0-9]{36,}` | `<REDACTED:GITHUB_PAT>` |
| GitHub fine-grained PAT | `github_pat_[A-Za-z0-9_]{82,}` | `<REDACTED:GITHUB_PAT>` |
| AWS Access Key | `AKIA[0-9A-Z]{16}` | `<REDACTED:AWS_ACCESS_KEY>` |
| AWS Secret | `aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}` | `<REDACTED:AWS_SECRET>` |
| Slack token | `xox[baprs]-[A-Za-z0-9-]{10,}` | `<REDACTED:SLACK_TOKEN>` |
| Discord bot token | `[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}` | `<REDACTED:DISCORD_TOKEN>` |
| Bearer / Authorization | `(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._\-]+` | `\1<REDACTED:BEARER>` |

#### 適用順序（厳守）

1. 環境変数値（最も具体的、長さ 8 以上のみ）
2. 正規表現 9 種（リスト順は OpenAI が `sk-ant-` を除く必要があるため Anthropic を先に適用）
3. ホームパス（`$HOME` 絶対パス → `<HOME>`）

### 確定 B: SQLAlchemy event listener の登録方式

table モジュール内で `event.listens_for(TableClass, 'before_insert')` / `'before_update'` をデコレータとして登録する。listener 関数は table モジュールの module-level に定義し、外部から差し替え不可（テスト時は `event.remove()` で削除可）。

理由:

- table 定義と listener が同一ファイルにあり、属性追加時に listener 内のフィールドリストを更新する責務が明確
- SQLAlchemy の event API は import 時に listener が登録される（lazy import を避ける）
- pyright strict で listener の引数型（`Mapper`, `Connection`, `Target`）を明示

### 確定 C: SQLite トリガ（`audit_log` 不変性）

Alembic 初回 revision で**2 つのトリガ**を発行する。SQL 本体は実装 PR で記述（本書は構造契約のみ）。

##### トリガ 1: DELETE 拒否（`audit_log_no_delete`）

| 項目 | 値 |
|----|----|
| トリガ名 | `audit_log_no_delete` |
| タイミング | `BEFORE DELETE` |
| 対象テーブル | `audit_log` |
| 行スコープ | `FOR EACH ROW` |
| アクション | `RAISE(ABORT, 'audit_log is append-only')` |

##### トリガ 2: UPDATE 制限（`audit_log_update_restricted`）

| 項目 | 値 |
|----|----|
| トリガ名 | `audit_log_update_restricted` |
| タイミング | `BEFORE UPDATE` |
| 対象テーブル | `audit_log` |
| 行スコープ | `FOR EACH ROW` |
| 条件 | `OLD.result IS NOT NULL`（`result` が既に値を持つ行への UPDATE） |
| アクション | `RAISE(ABORT, 'audit_log result is immutable once set')` |

##### UPDATE 許容範囲

UPDATE は **`result` / `error_text` を NULL → 値**（実行完了時の 1 回のみ）の遷移だけ許可。すでに値が入っている行への UPDATE はトリガ 2 で拒否。

##### 実装責務分離

- Alembic migration（`backend/alembic/versions/0001_init_*.py`）が SQL 本体を `op.execute("CREATE TRIGGER ...")` で発行
- 本書はトリガの**構造契約**（名前 / タイミング / 条件 / アクション）のみ凍結
- 結合テスト TC-IT-PF-005 / TC-IT-PF-015 が両トリガの動作を実 SQLite で検証

### 確定 D: PRAGMA SET の順序と引き金（Schneier 重大 2 対応）

`audit_log` の DELETE / UPDATE 拒否トリガ（確定 C）は、**そのトリガ自身が DROP TRIGGER で削除可能**であれば防衛にならない。SQLite では `sqlite_master` を直接 UPDATE してトリガ定義を消す経路もある。これに対する Defense in Depth として PRAGMA リストに `defensive=ON` / `writable_schema=OFF` を追加し、**application 接続と migration 接続を分離**する。

##### 確定 D-1: application 接続の PRAGMA リスト（毎接続 SET）

接続ごとに `event.listens_for(engine.sync_engine, 'connect')` で発火。順序固定:

| # | PRAGMA | 値 | 意図 |
|---|----|----|----|
| 1 | `journal_mode` | `WAL` | 同時読み書き性能、再起動時の WAL 自動チェックポイント。**他 PRAGMA より先**（他は WAL モード前提） |
| 2 | `foreign_keys` | `ON` | SQLite 既定 OFF。Aggregate 間の参照整合性を物理保証 |
| 3 | `busy_timeout` | `5000`（ms） | 同時アクセス時のロック待ち上限 |
| 4 | `synchronous` | `NORMAL` | WAL モードで安全。完全 fsync より高速 |
| 5 | `temp_store` | `MEMORY` | 一時テーブル / インデックスをメモリ保持 |
| 6 | `defensive` | `ON` | SQLite 3.31+。**runtime DDL（CREATE / DROP TRIGGER 等）を制限**し、`audit_log` トリガを DROP できない経路に置く |
| 7 | `writable_schema` | `OFF` | 既定 OFF だが**明示 SET**。runtime 中の `sqlite_master` 直接 UPDATE を阻止 |
| 8 | `trusted_schema` | `OFF` | SQLite 3.31+。スキーマ内の関数・VIEW などへの信頼を最小化 |

WAL モードはデータベースレベル永続化される（DB ファイルメタデータ）が、他は接続レベル。`foreign_keys` は SQLite 既定 OFF のため毎接続 SET 必須。

##### 確定 D-2: Alembic migration 接続は別経路（dual connection）

`defensive=ON` 下では `CREATE TABLE` / `CREATE TRIGGER` 等の DDL も制限される（具体的な制限内容は SQLite version に依存）。Alembic は migration 適用時に DDL を発行する必要があるため、**migration 専用の engine** を分離する。

| 接続種別 | engine 生成関数 | PRAGMA defensive | PRAGMA writable_schema | 用途 |
|----|----|----|----|----|
| application 接続 | `create_engine()`（既定） | `ON` | `OFF` | Backend ランタイム中の全 SELECT / INSERT / UPDATE |
| migration 接続 | `create_migration_engine()`（限定使用） | `OFF` | `ON`（DDL 発行時のみ） | Alembic `upgrade` / `downgrade` のみ。Bootstrap stage 3 のみで使用 |

##### 確定 D-3: migration engine の生存期間

`create_migration_engine()` は **Bootstrap stage 3 の `with` ブロック内のみ**で生存させる:

| 段階 | 操作 |
|----|----|
| stage 3 開始 | `create_migration_engine()` で migration 専用 engine を生成（`defensive=OFF`） |
| stage 3 中 | Alembic `upgrade head` を migration engine 経由で実行 |
| stage 3 終了 | migration engine を `dispose()` で破棄（接続 pool もクローズ） |
| stage 3 以降 | application engine（`defensive=ON`）のみが使われる |

これにより、Backend ランタイム中は `defensive=ON` の接続しか存在せず、攻撃者が runtime DDL でトリガを DROP する経路を物理的に塞ぐ。

##### 確定 D-4: `defensive=ON` で技術的に migration ができない場合の代替

SQLAlchemy 2.x / aiosqlite の現行版で上記が技術的に困難な場合（PRAGMA `defensive` のサポート状況に依存）、以下のフォールバックを採用:

1. application engine も `defensive=OFF` で起動するが、PRAGMA `query_only=ON`（書き込み禁止モード）を**書き込み Tx 開始時のみ OFF にして再 ON**にする ─ 実装コスト高
2. または **threat-model.md §T2 に「DDL 経由のトリガ削除は Backend を別 OS ユーザーで動かし、DB ファイル 0600 で他ユーザーから DDL 経路を物理的に塞ぐ」と信頼境界を明記**（OS レベルの隔離に頼る）

実装 PR で SQLite version + aiosqlite 実機検証を行い、`defensive=ON` がサポートされていれば確定 D-1〜D-3 を採用、サポート不能なら (2) のフォールバック + threat-model 明記に切り替える。**いずれの場合も決定を threat-model.md §T2 に記録する**（信頼境界の透明性）。

##### test-design.md でのカバレッジ

| TC | 検証内容 |
|----|----|
| TC-IT-PF-003 | PRAGMA 8 件すべてが application 接続で SET されていることを `PRAGMA <name>;` 取得で確認 |
| TC-IT-PF-003-A | application 接続から `DROP TRIGGER audit_log_no_delete` を試行 → SQLite が拒否 |
| TC-IT-PF-003-B | application 接続から `UPDATE sqlite_master SET ...` を試行 → 拒否 |
| TC-IT-PF-003-C | migration engine（stage 3）では DDL が成功する |
| TC-IT-PF-003-D | migration engine が stage 3 終了時に `dispose()` され、以降の DDL 発行経路が消えている |

### 確定 E: pid_registry 起動時 GC の順序と保護条件

| 段階 | 動作 |
|----|----|
| 1 | テーブルから全行 SELECT |
| 2 | 各行の `pid` を `psutil.Process(pid)` でアクセス試行 |
| 3 | `psutil.NoSuchProcess` → `absent` 判定、テーブルから DELETE（kill しない） |
| 4 | `psutil.AccessDenied` → WARN ログ、当該行は **DELETE しない**（次回 GC で再試行） |
| 5 | プロセス存在 → `create_time()` を `started_at` と比較 |
| 6 | 不一致 → `protected` 判定、テーブルから DELETE（kill しない、PID 再利用された別プロセス） |
| 7 | 一致 → `orphan_kill` 判定、`children(recursive=True)` で子孫列挙 |
| 8 | SIGTERM 送出 → 5 秒 grace → SIGKILL → テーブルから DELETE |

**「process_iter で claude プロセスを kill する」実装の禁止**を明文化（[`tech-stack.md`](../../architecture/tech-stack.md) §子孫追跡 と同方針）。bakufu 起動前に同一ユーザーが手動で起動した CLI を巻き込まない。

### 確定 F: マスキング適用の **Fail-Secure** 契約（Schneier 重大 1 対応）

`MaskingGateway.mask()` / `mask_in()` は**例外を投げない契約**だが、内部の異常時には **生データを書く経路をゼロにする** Fail-Secure フォールバックを採用する。「永続化を止めない」より「秘密を漏らさない」を優先順位の上位に置く。Fail Securely 原則（[OWASP Secure Coding Practices](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)）に従う。

##### Fail-Secure フォールバック表（凍結）

| 状況 | フォールバック | 結果として永続化される値 |
|----|----|----|
| `mask_in` が想定外の型（datetime, bytes 等）に出会う | `str()` で文字列化してから `mask()` 適用 | masking 適用後の文字列 |
| `mask` が文字列処理中に予期せぬ例外を raise | catch して **入力 str 全体を `<REDACTED:MASK_ERROR>` に完全置換** + WARN ログ | `<REDACTED:MASK_ERROR>`（生データは絶対に書かない） |
| 正規表現マッチ中の例外（理論上発生しない） | 同上 | `<REDACTED:MASK_ERROR>` |
| `mask_in` が再帰中に容量制限超過（10MB 等の異常 dict） | 当該 dict / list 全体を `<REDACTED:MASK_OVERFLOW>` に置換 + WARN ログ | `<REDACTED:MASK_OVERFLOW>` |
| listener 自体が予期せぬ例外を raise | listener の outer catch で row のすべての masking 対象フィールドを `<REDACTED:LISTENER_ERROR>` に置換 + ERROR ログ + 永続化は続行 | 全 masking 対象フィールドが `<REDACTED:*>` になる |

##### 環境変数辞書ロードは **Fail Fast**（Schneier 重大 1 (B) 対応）

masking の最初の layer（環境変数値の伏字化）が無効化された状態での起動は許容しない。

| 状況 | 挙動 |
|----|----|
| 起動時に `os.environ` から既知 env キー（ANTHROPIC_API_KEY 等）の取得自体が失敗 | OS 例外発生時のみ。`BakufuConfigError(MSG-PF-008)` を raise → プロセス終了 |
| 既知 env キーが**全て未設定**（CI 環境等） | OK。空のパターン辞書で起動（`MaskedEnvPatterns` のサイズ 0 ログ INFO 出力） |
| 既知 env キーの値が長さ 7 以下（短すぎて誤マッチを起こす） | スキップ（パターン辞書に追加しない、INFO ログ）|
| パターン辞書の compile に失敗（理論上発生しない） | `BakufuConfigError(MSG-PF-008)` raise → プロセス終了 |

「空辞書として継続、WARN ログ」を**削除**する。masking layer 1 が有効でない状態での bakufu 起動は信頼境界の前提を崩す。

##### listener の永続化を「止めない」契約は維持、ただし「生データを書かない」を絶対不変条件として上位化

旧契約: 「Outbox 全体が止まると bakufu 全体が機能停止」を理由に listener の masking スキップを許容していた。

新契約: **listener は常に何らかの masking 後値を書く**（`<REDACTED:MASK_ERROR>` / `<REDACTED:LISTENER_ERROR>` / `<REDACTED:MASK_OVERFLOW>` のいずれかでも、生データは絶対に書かない）。

論拠:
- bakufu は CEO 個人の秘密が永続化される環境であり、business continuity > security の優先順位は逆
- 「listener が masking スキップ → 生データが書かれる」経路は、攻撃者が ENV ロード失敗 / 型異常を誘発する単一経路で全マスキングを無効化できる単一障害点
- 永続化を「止めない」のではなく「`<REDACTED:*>` で書く」ことで運用継続性も維持される（dead-letter 化経路は masking 後値で動作する）

##### test-design.md でのカバレッジ

| TC | 検証内容 |
|----|----|
| TC-UT-PF-006-A | mask が予期せぬ例外 raise 時に `<REDACTED:MASK_ERROR>` が返る |
| TC-UT-PF-006-B | mask_in が異常 dict（10MB 超）受信時に `<REDACTED:MASK_OVERFLOW>` が返る |
| TC-UT-PF-006-C | listener 自体が例外時、row の全 masking 対象フィールドが `<REDACTED:LISTENER_ERROR>` になる |
| TC-IT-PF-007-D | 環境変数辞書ロード失敗時に Bootstrap が exit 1 する（Fail Fast） |

### 確定 G: Backend 起動シーケンスの順序保証（§確定 R1-C 再掲、実装側）

| 順 | 段階 | 失敗時の挙動 | 後続段階 |
|---|---|---|---|
| 1 | DATA_DIR 解決 | `BakufuConfigError(MSG-PF-001)` raise → exit 1 | スキップ |
| 2 | engine 初期化 | `BakufuConfigError(MSG-PF-002)` raise → exit 1 | スキップ |
| 3 | Alembic upgrade head | `BakufuMigrationError(MSG-PF-004)` raise → exit 1 | スキップ |
| 4 | pid_registry GC | `psutil` 例外は WARN ログ → 続行（致命的でない） | 続行 |
| 5 | attachments FS 初期化 | `BakufuConfigError(MSG-PF-003)` raise → exit 1 | スキップ |
| 6 | Outbox Dispatcher 起動 | asyncio.create_task の例外 → exit 1 | スキップ |
| 7 | attachments 孤児 GC スケジューラ起動 | asyncio.create_task の例外 → exit 1 | スキップ |
| 8 | FastAPI / WebSocket リスナ開始 | バインド失敗 → exit 1 | — |

段階 4 のみ非 fatal（孤児 GC が一部失敗しても次回 GC で回収可能）。それ以外は Fail Fast。

##### 起動進捗ログ（Norman 指摘 R5「フィードバック原則」対応）

各段階の **開始** / **完了** / **失敗** で構造化ログを出力する。運用者が「どこで詰まったか」を即座に把握できるようにする。ログは masking 適用済みで stdout / 構造化ログファイルの両方に出力。

| 段階 | 開始ログ（INFO） | 完了ログ（INFO） | 失敗ログ（FATAL） |
|----|----|----|----|
| 1 | `[INFO] Bootstrap stage 1/8: resolving BAKUFU_DATA_DIR...` | `[INFO] Bootstrap stage 1/8: data dir resolved at <HOME>/...` | `[FAIL] Bootstrap stage 1/8: ...` |
| 2 | `[INFO] Bootstrap stage 2/8: initializing SQLite engine...` | `[INFO] Bootstrap stage 2/8: engine ready (PRAGMA WAL/foreign_keys/busy_timeout/synchronous/temp_store/defensive applied)` | `[FAIL] Bootstrap stage 2/8: ...` |
| 3 | `[INFO] Bootstrap stage 3/8: applying Alembic migrations...` | `[INFO] Bootstrap stage 3/8: schema at head <revision_id>` | `[FAIL] Bootstrap stage 3/8: ...` |
| 4 | `[INFO] Bootstrap stage 4/8: pid_registry orphan GC...` | `[INFO] Bootstrap stage 4/8: GC complete (killed={n_killed}, protected={n_protected}, absent={n_absent})` | `[WARN] Bootstrap stage 4/8: psutil.AccessDenied for pid={pid}, retry next cycle` |
| 5 | `[INFO] Bootstrap stage 5/8: ensuring attachment FS root...` | `[INFO] Bootstrap stage 5/8: attachments root at <HOME>/.../attachments (mode=0700)` | `[FAIL] Bootstrap stage 5/8: ...` |
| 6 | `[INFO] Bootstrap stage 6/8: starting Outbox Dispatcher (poll_interval=1s, batch=50)...` | `[INFO] Bootstrap stage 6/8: dispatcher running (handler_registry size={N})` + 空レジストリ時の追加 WARN（§確定 K） | `[FAIL] Bootstrap stage 6/8: ...` |
| 7 | `[INFO] Bootstrap stage 7/8: starting attachment orphan GC scheduler (interval=24h)...` | `[INFO] Bootstrap stage 7/8: scheduler running` | `[FAIL] Bootstrap stage 7/8: ...` |
| 8 | `[INFO] Bootstrap stage 8/8: binding FastAPI listener on 127.0.0.1:8000...` | `[INFO] Bootstrap stage 8/8: bakufu Backend ready` | `[FAIL] Bootstrap stage 8/8: ...` |

##### ログ出力先

- **構造化ログ**（JSON）: `<DATA_DIR>/logs/bakufu.log`（パーミッション 0600、masking 適用済み）
- **stdout**: 同等内容を人間可読形式で出力（コンテナ運用時に `docker logs` で取得可能）
- **stderr**: FATAL のみ（プロセス exit 直前）

`stage_id` / `stage_name` / `started_at` / `completed_at` / `duration_ms` / `status` / `details` のキーを必ず含める。

##### Bootstrap cleanup（Schneier 中等 4 対応、§確定 J）

各段階の失敗時、**段階 6 / 7 で起動した asyncio task は exit 前に `task.cancel()` で停止する**。これは確定 J で凍結する。

### 確定 H: Schneier 申し送り 6 項目の実装ステータス

| # | 項目 | 本 PR | 後続 PR |
|---|---|---|---|
| 1 | `BAKUFU_DATA_DIR` 絶対パス | ✓ `data_dir.py` で実装 + 結合テスト | — |
| 2 | H10 TOCTOU | ✗ | `feature/skill-loader` で skill 読み込み直前再検証 |
| 3 | `Persona.prompt_body` Repository マスキング | △ event listener hook 構造のみ提供 | `feature/agent-repository` で `agents` テーブルに対し listener 登録 |
| 4 | `audit_log` DELETE 拒否 | ✓ Alembic 初回 revision でトリガ作成 + 結合テスト | — |
| 5 | `bakufu_pid_registry` 0600 | ✓ テーブル + GC スケルトン + パーミッション強制 | LLM Adapter 側で実 spawn / kill 配線（`feature/llm-adapter`） |
| 6 | Outbox `payload_json` / `last_error` マスキング | ✓ event listener で強制ゲートウェイ化 + 結合テスト | — |

「△」項目は hook を提供するに留まり、実適用は対応 Aggregate Repository PR の責務。本 Issue の設計書に「申し送りを継承」と明記する。

### 確定 I: 依存方向の物理保証

domain 層から infrastructure 層への import が 0 件であることを以下で保証:

1. CI script: `grep -rn 'from bakufu.infrastructure' backend/src/bakufu/domain/` の結果が空であること
2. テスト: `tests/architecture/test_dependency_direction.py` が `bakufu.domain.*` の全モジュールを import し、`bakufu.infrastructure.*` の名前が module 属性に含まれないことを検証

これにより、後続 Repository PR で誰かが `domain/` 内に infrastructure 参照を持ち込んでも CI で落ちる。

### 確定 J: Bootstrap 起動失敗時の cleanup（Schneier 中等 4 対応）

起動シーケンス段階 6（Outbox Dispatcher）/ 段階 7（attachments 孤児 GC scheduler）で起動した asyncio task は、後続段階失敗時に**プロセス exit 前に明示的に cancel する**。グレースフルシャットダウン設計の最初のレイヤを本 PR で凍結する。

##### Bootstrap の `try / finally` 構造（凍結）

| 段階 | 起動 task | 段階 6 / 7 失敗時の cleanup | 段階 8 失敗時の cleanup |
|----|----|----|----|
| 6 | `dispatcher_task = asyncio.create_task(dispatcher.run())` | `dispatcher_task.cancel()` → `await asyncio.gather(dispatcher_task, return_exceptions=True)` | 同上 |
| 7 | `gc_task = asyncio.create_task(scheduler.run_forever())` | `gc_task.cancel()` → `await asyncio.gather(gc_task, return_exceptions=True)` | 同上 |
| その他 | — | — | — |

##### cleanup 順序

`finally` ブロック内で **後に起動したものから先に cancel**（LIFO）:

1. 段階 7 の scheduler を cancel（先に止めることで `attachment_root.start_orphan_gc_scheduler()` の副作用が増えない）
2. 段階 6 の dispatcher を cancel
3. engine の `dispose()`（接続 pool / WAL flush）
4. 構造化ログ flush
5. プロセス exit（適切な exit code: stage が指定する 1）

##### Phase 2 への伸び代

本 PR では Bootstrap 起動失敗時の cleanup のみを凍結。**ランタイム中の `bakufu admin shutdown`** などのグレースフル停止は Phase 2 で `BootstrapShutdown.run()` として拡張する経路を残す（task list を Bootstrap 内で保持しているため、shutdown ハンドラが同じ list を逆順 cancel するだけで実装できる）。

##### test-design.md でのカバレッジ

| TC | 検証内容 |
|----|----|
| TC-IT-PF-012-A | 段階 7 で例外発生時、段階 6 の dispatcher_task が `cancel()` 済みになる（`task.cancelled() == True`） |
| TC-IT-PF-012-B | 段階 8 で例外発生時、段階 6 / 7 の両 task が cancel される |
| TC-IT-PF-012-C | engine.dispose() が cleanup 中に必ず呼ばれる（mock で確認） |

### 確定 K: Outbox Dispatcher 空 handler レジストリ稼働時の WARN（Schneier 中等 3 対応）

本 PR では Handler 実装を登録しない（空レジストリ）。後続 PR が register するまでの空レジストリ稼働中、Outbox 行が累積する経路に対して **早期検出の WARN ログ**を組み込む。

##### 空レジストリ検出ロジック（凍結）

| タイミング | 動作 |
|----|----|
| Bootstrap stage 6 起動完了直後 | `len(handler_registry) == 0` なら WARN 出力: `[WARN] Bootstrap stage 6/8: No event handlers registered. Outbox events will accumulate without dispatch. Register handlers via feature/{event-kind}-handler PRs before processing real events.` |
| Dispatcher polling サイクルごと | `polling SQL で取得した行数 > 0` AND `handler_registry が空` なら WARN（**1 サイクルにつき 1 回**、ログ・スパム防止）: `[WARN] Outbox has {n} pending events but handler_registry is empty.` |
| Outbox 滞留閾値 | `domain_event_outbox` の `status='PENDING'` 行数が **100 件超** で WARN（5 分に 1 回、`feature/admin-cli` の monitoring に通知）: `[WARN] Outbox PENDING count={n} > 100. Inspect with bakufu admin list-pending.` |

##### 「dispatcher を本 PR で起動しない」案を採用しなかった理由

Schneier 中等 3 (C) の「本 PR では dispatcher を起動しない」案は最もシンプルだが、**Bootstrap 起動シーケンス 8 段階の順序を本 PR で凍結する目的に反する**。後続 PR が「初回 handler 登録時に Bootstrap が一部やり直される」という分岐を入れると、起動順序の単一性が崩れ、TC-IT-PF-012 系の試験性も失われる。

代わりに「dispatcher は起動するが、空レジストリは WARN で運用者に通知される」という Fail Loud 設計を採用。CEO が起動ログを見れば即座に気付ける。

##### test-design.md でのカバレッジ

| TC | 検証内容 |
|----|----|
| TC-IT-PF-008-A | 空レジストリで Bootstrap 起動 → WARN ログ 1 件出力 |
| TC-IT-PF-008-B | PENDING 行 1 件 INSERT + 空レジストリで polling 1 サイクル → WARN ログ 1 件、`status='PENDING'` のまま |
| TC-IT-PF-008-C | 同シナリオで polling 2 サイクル目 → WARN は 1 回のみ（重複抑止） |
| TC-IT-PF-008-D | PENDING 行 101 件 INSERT → 滞留閾値 WARN 出力 |

### 確定 L: Bootstrap 入口の `os.umask(0o077)` 設定（Schneier 中等 1 対応）

WAL / SHM ファイルや `bakufu_pid_registry` 関連ファイルが SQLite / OS 経由で自動生成される際、**親プロセスの umask が 0022 のままだと 0o644 で作られる**経路がある。これを潰すため、Bootstrap 入口で **`os.umask(0o077)` を最初に SET** する。

##### 適用順序

| 順 | 操作 |
|---|---|
| 0（**stage 1 より前**） | `os.umask(0o077)` を SET（`Bootstrap.run()` の最初の文） |
| 1 | DATA_DIR 解決 |
| 2 | engine 初期化（DB / WAL / SHM ファイル作成時に umask 0o077 が効く） |
| 3〜8 | 既存通り |

##### POSIX のみ

`os.umask` は POSIX 限定。Windows では `os.umask` は意味を持たないが、`%LOCALAPPDATA%` 配下のホームディレクトリは OS ユーザーのみアクセス可能と信頼（threat-model.md §T5）。

##### test-design.md でのカバレッジ

| TC | 検証内容 |
|----|----|
| TC-IT-PF-001-A | Bootstrap 起動後、`bakufu.db-wal` / `bakufu.db-shm` のモードが 0o600 で作成される（POSIX）|
| TC-UT-PF-001-A | `Bootstrap.run()` が最初に `os.umask(0o077)` を呼ぶ（mock で確認）|

## 設計判断の補足

### なぜ event listener が TypeDecorator より優れるか

`MaskedString` 型を作って `Column(MaskedString)` で宣言する方式は、属性追加時に「型を指定し忘れる」経路がある（特に `prompt_body: str` の単純カラムが masking 対象になることを忘れる）。`event.listens_for(target, 'before_insert')` で table 単位に listener を登録する方式は、**新カラム追加時に masking 対象なら listener 内のフィールドリストに 1 行追加するだけ**で配線が完了する。

また、raw SQL（`session.execute(insert(table).values(...))` 等）の経路でも listener は走るため、ORM mapper を経由しない経路でも masking が適用される（多層防御）。

### なぜ `audit_log` を DELETE トリガで止めるか

DDD の Aggregate Root は「コードレベルで不変条件を強制」するが、SQLite ファイルに直接 SQL を流す経路（`sqlite3` CLI 等）はコードを経由しない。SQLite トリガはデータベースレベルの最後の防衛線で、「攻撃者が DB ファイルに直接アクセスして DELETE する」経路を物理的に塞ぐ（OWASP A08 Data Integrity Failures）。

### なぜ Outbox Dispatcher の Handler を本 PR で実装しないか

Handler は event_kind ごとに副作用が異なる:

- `DirectiveIssued` → Task 生成（次 Tx）
- `TaskAssigned` → WebSocket ブロードキャスト + LLM Adapter 呼び出し
- `ExternalReviewRequested` → Gate 生成 + Discord Notifier
- `OutboxDeadLettered` → Discord 通知（dead-letter 専用）

これらを 1 PR にまとめると WebSocket / Notifier / LLM Adapter / Gate Aggregate の依存が一気に発生し、レビュー帯域を圧迫する。Dispatcher 骨格 + 空レジストリで止め、Handler は `feature/{event-kind}-handler` の小粒 PR で個別に register する。

### なぜ起動シーケンスを Bootstrap クラスに集約するか

`main.py` に手続き的に書くと、各段階の失敗ハンドリングが分散して `try/except` が散在する。`Bootstrap` クラスに 1 つにまとめることで:

1. 起動順序が 1 箇所に閉じる（読み手が順序を即座に把握できる）
2. テストで `Bootstrap.run()` を呼ぶと起動シーケンスを単体テストできる
3. 段階追加時に Bootstrap 内のメソッド追加だけで完結

### なぜ pid_registry GC で `psutil.AccessDenied` を WARN にするか

OS 側で他プロセスへのアクセス権が拒否されるケースは複数あり得る（root プロセスの操作、別ユーザーの操作）。当該行を DELETE してしまうと**起動するたびに孤児が増える**経路ができる。WARN ログで運用者に知らせつつ、テーブルに残して次回 GC でリトライする方が運用上安全。

## ユーザー向けメッセージの確定文言

### プレフィックス統一

| プレフィックス | 意味 |
|--------------|-----|
| `[FAIL]` | 処理中止を伴う失敗（startup 段階） |
| `[WARN]` | 警告（処理は継続） |
| `[INFO]` | 情報提供（処理は継続） |

### MSG 確定文言表

| ID | 出力先 | 文言 |
|----|------|----|
| MSG-PF-001 | stderr / startup ログ | `[FAIL] BAKUFU_DATA_DIR must be an absolute path (got: {value})` — `{value}` はホームパス置換適用後 |
| MSG-PF-002 | stderr / startup ログ | `[FAIL] SQLite engine initialization failed: {reason}` |
| MSG-PF-003 | stderr / startup ログ | `[FAIL] Attachment FS root initialization failed at {path}: {reason}` |
| MSG-PF-004 | stderr / startup ログ | `[FAIL] Alembic migration failed: {reason}` |
| MSG-PF-005 | SQLite トリガ raise message | `audit_log is append-only` / `audit_log result is immutable once set` |
| MSG-PF-006 | WARN ログ | `[WARN] Masking gateway fallback applied: {kind}` — `{kind}` は `unknown_type` / `regex_failure` 等 |
| MSG-PF-007 | WARN ログ | `[WARN] pid_registry GC: psutil.AccessDenied for pid={pid}, retry next cycle` |

メッセージは ASCII 範囲。日本語化は UI 側 i18n（Phase 2、UI に届くメッセージのみ）。

## データ構造（永続化キー）

### `audit_log` テーブル

requirements.md §データモデル + §確定 C のトリガを参照。

### `bakufu_pid_registry` テーブル

requirements.md §データモデル を参照。

### `domain_event_outbox` テーブル

requirements.md §データモデル + §確定 A のマスキング適用先 を参照。

### Alembic 初回 revision キー構造

revision id: `0001`（自動生成 hash でも可、固定 ID `0001_init_audit_pid_outbox` を推奨）

| 操作 | 対象 |
|----|----|
| `op.create_table('audit_log', ...)` | 7 カラム |
| `op.create_table('bakufu_pid_registry', ...)` | 6 カラム |
| `op.create_table('domain_event_outbox', ...)` | 11 カラム |
| `op.create_index('ix_outbox_status_next_attempt', 'domain_event_outbox', ['status', 'next_attempt_at'])` | INDEX |
| `op.execute("CREATE TRIGGER audit_log_no_delete ...")` | DELETE 拒否トリガ |
| `op.execute("CREATE TRIGGER audit_log_update_restricted ...")` | UPDATE 制限トリガ |

`downgrade()` は `op.drop_table` / `op.execute("DROP TRIGGER ...")` で逆順に実行（Phase 2 のロールバック耐性）。

## API エンドポイント詳細

該当なし — 理由: 本 feature は infrastructure 層のみ。HTTP API は `feature/http-api` で凍結する。

## 出典・参考

- [SQLAlchemy 2.0 — async / AsyncEngine / AsyncSession](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — async engine / session の公式実装根拠
- [SQLAlchemy 2.0 — Events / before_insert / before_update](https://docs.sqlalchemy.org/en/20/orm/events.html) — listener 配線の公式 API
- [SQLAlchemy 2.0 — connect event for PRAGMA](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support) — PRAGMA SET の公式パターン
- [SQLite PRAGMA Statements](https://www.sqlite.org/pragma.html) — `journal_mode=WAL` / `foreign_keys` / `busy_timeout` 等の公式仕様
- [SQLite Trigger — RAISE(ABORT)](https://www.sqlite.org/lang_createtrigger.html) — `audit_log` DELETE 拒否トリガの実装根拠
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html) — migration / revision 管理の公式
- [psutil — Process.create_time / children](https://psutil.readthedocs.io/en/latest/#psutil.Process.create_time) — PID 衝突対策の公式 API
- [`docs/architecture/domain-model/storage.md`](../../architecture/domain-model/storage.md) — シークレットマスキング規則の集約先（`infrastructure/security/masking.py`）
- [`docs/architecture/domain-model/events-and-outbox.md`](../../architecture/domain-model/events-and-outbox.md) — Outbox 行スキーマ + Dispatcher 動作 + リカバリ条件
- [`docs/architecture/threat-model.md`](../../architecture/threat-model.md) — 信頼境界 / OWASP Top 10 / 攻撃面 A1〜A5 / Schneier 申し送り
