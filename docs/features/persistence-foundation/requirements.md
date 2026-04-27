# 要件定義書

> feature: `persistence-foundation`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/architecture/tech-stack.md`](../../architecture/tech-stack.md) §ORM

## 機能要件

### REQ-PF-001: データルート解決

| 項目 | 内容 |
|------|------|
| 入力 | 環境変数 `BAKUFU_DATA_DIR`（`os.environ`）、現在の OS 種別（`platform.system()`） |
| 処理 | (a) `BAKUFU_DATA_DIR` が設定されていれば値を取り、`pathlib.Path` でパース → 絶対パスでなければ Fail Fast。(b) 未設定時は OS 別既定: Linux/macOS は `${XDG_DATA_HOME:-$HOME/.local/share}/bakufu`、Windows は `%LOCALAPPDATA%\bakufu`。(c) 解決後の Path に対し `Path.resolve()` で symlink 展開しつつ正規化、existence は問わない（mkdir は別 REQ）。(d) module level singleton として保持 |
| 出力 | `pathlib.Path`（絶対パス、解決済み） |
| エラー時 | 相対パス / NULL バイト / `..` を含む値 → `BakufuConfigError(MSG-PF-001)` を Fail Fast。プロセスは exit 非 0 |

### REQ-PF-002: SQLite engine 初期化

| 項目 | 内容 |
|------|------|
| 入力 | REQ-PF-001 で解決した DATA_DIR。**DB ファイルパスは `<DATA_DIR>/bakufu.db` 固定**（Schneier 重大 4 対応で `BAKUFU_DB_PATH` 環境変数は廃止 — YAGNI、攻撃面を減らす） |
| 処理 | (a) `sqlalchemy.ext.asyncio.create_async_engine(url, future=True, echo=BAKUFU_DEBUG)` で application 用 async engine を生成。URL: `sqlite+aiosqlite:///<absolute path>`。(b) `event.listens_for(engine.sync_engine, 'connect')` で接続時 PRAGMA を SET（**詳細設計 §確定 D-1 の 8 件**: `journal_mode=WAL` / `foreign_keys=ON` / `busy_timeout=5000` / `synchronous=NORMAL` / `temp_store=MEMORY` / `defensive=ON` / `writable_schema=OFF` / `trusted_schema=OFF`）。(c) **DB ファイル権限の検出 + 警告**（Schneier 重大 3 対応、§REQ-PF-002-A 参照） |
| 出力 | `AsyncEngine` インスタンス（モジュールスコープ singleton） |
| エラー時 | engine 生成失敗 → 例外を raise してプロセス終了。PRAGMA SET 失敗（SQLite version 古い等）→ Fail Fast、`BakufuConfigError(MSG-PF-002)`。DB ファイル権限が想定外 → §REQ-PF-002-A の動作 |

#### REQ-PF-002-A: DB ファイル権限の検出 + 警告（Schneier 重大 3 対応、Forensic 観点）

`os.chmod` でサイレントに修正する設計を**廃止**。過去に発生した権限変更の痕跡を消さず、運用者に通知する設計に変更。

| ケース | 検出ロジック | 動作 |
|---|---|---|
| **新規 DB ファイル**（path が存在しない） | `Path.exists() == False` | engine 経由で SQLite が DB ファイルを新規作成。**作成直後に `os.stat` でモード確認**し `0o600` でなければ `os.chmod(path, 0o600)` で強制。**INFO ログ**「Created new DB file at {path} (mode=0o600)」 |
| **既存 DB ファイル、権限正常**（POSIX、mode == 0o600） | `os.stat(path).st_mode & 0o777 == 0o600` | INFO ログ「DB file at {path} has expected permission 0o600」のみで通常起動 |
| **既存 DB ファイル、権限異常**（POSIX、mode != 0o600） | 同上の不一致 | **WARN ログ + 修復 + 続行**: `[WARN] DB file at {path} has unexpected permission 0o{mode}, expected 0o600. This may indicate prior unauthorized access. Manual investigation recommended (compare with audit_log of last access). Auto-fixing to 0o600 to prevent further exposure.` を ERROR ログにも複製、`os.chmod(path, 0o600)` で修復、起動続行 |
| **WAL / SHM ファイル**（`bakufu.db-wal` / `bakufu.db-shm`） | 同上の検査を WAL / SHM ファイルにも適用 | 同上 |
| **Windows** | `platform.system() == 'Windows'` | `os.stat` のモードビットは意味を持たないため検査スキップ。`%LOCALAPPDATA%` のホーム配下を信頼（threat-model.md §T5 で明記） |

##### Forensic 観点の論拠

- 「サイレントに直す」は**異常状態の検出可能性を消す**アンチパターン
- 「Fail Fast で起動拒否」は安全だが、運用上の自動復旧ができない（CEO 個人運用なので可、ただし最低でも WARN による検出可能性を残せば十分）
- WARN + 修復 + 続行が運用バランスとして妥当

##### test-design.md でのカバレッジ

| TC | 検証内容 |
|----|----|
| TC-IT-PF-002-A | 新規 DB ファイル作成時 0o600 で作成される（POSIX）|
| TC-IT-PF-002-B | 既存 DB ファイルが 0o644 だった場合に WARN ログ + 修復後起動する |
| TC-IT-PF-002-C | WAL / SHM ファイルにも同じ検出ロジックが適用される |

### REQ-PF-003: AsyncSession factory

| 項目 | 内容 |
|------|------|
| 入力 | REQ-PF-002 の engine |
| 処理 | (a) `async_sessionmaker(engine, expire_on_commit=False, autoflush=False)` で session factory を構築。(b) `async with session.begin():` を Unit-of-Work 境界として application 層 / Repository 層が利用 |
| 出力 | `async_sessionmaker[AsyncSession]` |
| エラー時 | session 内で例外発生 → `session.begin()` ブロックが自動 rollback、上位に伝播 |

### REQ-PF-004: Alembic 初回 migration

| 項目 | 内容 |
|------|------|
| 入力 | REQ-PF-002 の engine、`alembic/env.py` の設定 |
| 処理 | (a) `alembic upgrade head` 相当を起動時に実行（auto-migrate）。(b) 初回 revision: `audit_log` / `bakufu_pid_registry` / `domain_event_outbox` の 3 テーブル + `audit_log` 用 DELETE 拒否トリガ + `audit_log` 用 UPDATE 制限トリガ（result / error_text の null 埋めのみ） |
| 出力 | 3 テーブル + 2 トリガが SQLite に存在する状態 |
| エラー時 | migration 失敗 → 例外 raise、プロセス終了。`BakufuMigrationError(MSG-PF-004)` |

### REQ-PF-005: マスキング単一ゲートウェイ

| 項目 | 内容 |
|------|------|
| 入力 | 任意の文字列 / dict / list（再帰的に走査される） |
| 処理 | 適用順序を厳守（[`storage.md`](../../architecture/domain-model/storage.md) §適用順序）: (1) 起動時に `os.environ` から `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GH_TOKEN` / `GITHUB_TOKEN` / `OAUTH_CLIENT_SECRET` / `BAKUFU_DISCORD_BOT_TOKEN` の値（長さ 8 以上）をパターン辞書化 → 完全一致を `<REDACTED:ENV:<KEY>>` 化、(2) 9 種正規表現（Anthropic / OpenAI / GitHub PAT / GitHub fine-grained PAT / AWS Access / AWS Secret / Slack / Discord bot / Bearer）を順次適用、(3) `$HOME` 絶対パスを `<HOME>` 置換。**注**: `BAKUFU_DB_KEY` は MVP では SQLCipher 等の at-rest 暗号化を採用しないため削除（Schneier 中等 2 対応、YAGNI / 不要な攻撃面の事前排除）。代わりに `BAKUFU_DISCORD_BOT_TOKEN` を masking 対象に追加（threat-model.md §資産 で明記済みの高機密 token） |
| 出力 | masking 適用済みの文字列（または再帰的に適用済みの dict / list） |
| エラー時 | **Fail-Secure 契約**（detailed-design §確定 F）: 内部例外発生時も**生データを返す経路はゼロ**。`mask` の予期せぬ例外 → `<REDACTED:MASK_ERROR>` で完全置換、`mask_in` の容量超過 → `<REDACTED:MASK_OVERFLOW>` で完全置換、想定外型 → `str()` 化後 `mask` 適用。環境変数辞書ロード失敗時は **Fail Fast**（`BakufuConfigError(MSG-PF-008)`、起動拒否）|

### REQ-PF-006: SQLAlchemy event listener 配線（Outbox）

| 項目 | 内容 |
|------|------|
| 入力 | `domain_event_outbox` テーブルへの `before_insert` / `before_update` event |
| 処理 | (a) listener 内で row の `payload_json` / `last_error` フィールドを取得、(b) REQ-PF-005 の masking ゲートウェイを呼び出し、(c) row の値を masking 後の値で**上書き**してから INSERT / UPDATE を実行させる |
| 出力 | masking 後の値が永続化される |
| エラー時 | **Fail-Secure 契約**（detailed-design §確定 F）: listener 内で masking 例外が発生した場合、対象フィールドを `<REDACTED:LISTENER_ERROR>` / `<REDACTED:MASK_ERROR>` / `<REDACTED:MASK_OVERFLOW>` で**完全置換**してから INSERT / UPDATE を継続。**生データを書く経路はゼロ**。「row 上書きをスキップして INSERT / UPDATE をそのまま走らせる」旧 fail-open 経路は**廃止**。詳細は detailed-design.md §確定 F の Fail-Secure フォールバック表 |

### REQ-PF-007: Outbox Dispatcher 骨格

| 項目 | 内容 |
|------|------|
| 入力 | `domain_event_outbox` テーブルの状態 |
| 処理 | (a) 1 秒間隔で polling SQL: `WHERE (status='PENDING' AND next_attempt_at <= now()) OR (status='DISPATCHING' AND updated_at < now() - 5min) LIMIT N`。(b) 取得行を `status=DISPATCHING`, `updated_at=now()` に更新（シングルプロセス前提）。(c) Handler レジストリから `event_kind` に対応する handler を解決、(d) `await handler(payload)` を実行、成功時 `status=DISPATCHED` + `dispatched_at=now()`、失敗時 `attempt_count += 1` + `next_attempt_at = now() + backoff` + `last_error` 記録（masking 適用済み）+ `status=PENDING`。(e) `attempt_count >= 5` で `status=DEAD_LETTER` + `OutboxDeadLettered` event を別行として追記 |
| 出力 | Outbox 行の状態遷移 |
| エラー時 | Handler 例外 → 上記 (d) の失敗経路。Dispatcher 自身の例外（DB 接続切断等）→ ログに WARN 出力、次サイクルで再試行 |

### REQ-PF-008: pid_registry 起動時 GC

| 項目 | 内容 |
|------|------|
| 入力 | `bakufu_pid_registry` テーブルの全 PID 行 |
| 処理 | (a) 各行の `pid` を `psutil.Process(pid)` で取得、(b) `psutil.Process.create_time()` を `started_at` と比較し、不一致なら「PID 再利用された別プロセス」と判定して保護（テーブルから DELETE するのみ、kill しない）、(c) 一致なら `psutil.Process.children(recursive=True)` で子孫まで列挙 → SIGTERM → 5 秒 grace → SIGKILL → テーブルから DELETE |
| 出力 | 孤児プロセスがすべて kill された状態 + テーブルが整合した状態 |
| エラー時 | `psutil.NoSuchProcess` → 既に終了済み、テーブルから DELETE のみ。`psutil.AccessDenied` → ログに WARN 出力、当該行は次回 GC で再試行 |

### REQ-PF-009: アタッチメント FS ルート初期化

| 項目 | 内容 |
|------|------|
| 入力 | REQ-PF-001 の DATA_DIR |
| 処理 | (a) `<DATA_DIR>/attachments/` を `mkdir(parents=True, exist_ok=True)` で作成、(b) POSIX 環境では `os.chmod` で `0700` 強制、(c) 24h 周期の孤児 GC スケジューラを asyncio task として起動（実 GC ロジックは `feature/attachment-store` の責務、本 Issue は枠のみ） |
| 出力 | アタッチメントディレクトリが正しい権限で存在する状態 |
| エラー時 | 作成失敗（権限不足等）→ 例外 raise、プロセス終了 |

### REQ-PF-010: 起動シーケンス凍結

| 項目 | 内容 |
|------|------|
| 入力 | プロセス起動時の環境 |
| 処理 | requirements-analysis.md §確定 R1-C の 8 段階を `main.py` で順次実行: (1) DATA_DIR 解決 → (2) engine 初期化 → (3) Alembic auto-migrate → (4) pid_registry GC → (5) attachments FS 初期化 → (6) Outbox Dispatcher 起動 → (7) attachments 孤児 GC スケジューラ起動 → (8) FastAPI / WebSocket リスナ開始 |
| 出力 | Backend が正常起動した状態（HTTP listening on 127.0.0.1:8000） |
| エラー時 | 各段階で例外 raise → プロセス終了（exit 非 0）。後続段階は走らない（Fail Fast） |

## 画面・CLI 仕様

### CLI レシピ / コマンド

該当なし — 理由: 本 Issue は基盤層。Admin CLI は `feature/admin-cli` で扱う。本 Issue が提供するのは Backend プロセス起動時の自動初期化のみ。

| コマンド | 概要 |
|---------|------|
| 該当なし | — |

### Web UI 画面

該当なし — 理由: UI は提供しない。

| 画面ID | 画面名 | 主要操作 |
|-------|-------|---------|
| 該当なし | — | — |

## API 仕様

該当なし — 理由: HTTP API は `feature/http-api` で扱う。本 Issue は内部 API（Python module-level の関数 / クラス）のみ提供する。

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| 該当なし | — | — | — | — |

## データモデル

本 Issue で導入する 3 テーブル + 2 トリガ。Aggregate 別テーブルは後続 PR で追加。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| audit_log | `id` | `UUID` | PK, NOT NULL | — |
| audit_log | `actor` | `VARCHAR` | NOT NULL | — |
| audit_log | `command` | `VARCHAR` | NOT NULL | — |
| audit_log | `args_json` | `JSON` | NOT NULL（masking 適用後） | — |
| audit_log | `result` | `VARCHAR` | NULL → SUCCESS / FAILURE | — |
| audit_log | `error_text` | `TEXT` | NULL（masking 適用後） | — |
| audit_log | `executed_at` | `DATETIME` | NOT NULL（UTC） | — |
| audit_log_no_delete | TRIGGER | — | BEFORE DELETE → RAISE(ABORT, 'audit_log is append-only') | audit_log |
| audit_log_update_restricted | TRIGGER | — | BEFORE UPDATE WHEN OLD.result IS NOT NULL → RAISE(ABORT) | audit_log |
| bakufu_pid_registry | `pid` | `INTEGER` | PK, NOT NULL | — |
| bakufu_pid_registry | `parent_pid` | `INTEGER` | NOT NULL | — |
| bakufu_pid_registry | `started_at` | `DATETIME` | NOT NULL（UTC、`psutil.create_time()` 比較用） | — |
| bakufu_pid_registry | `cmd` | `TEXT` | NOT NULL（masking 適用） | — |
| bakufu_pid_registry | `task_id` | `UUID` | NULL（task と紐づく場合） | tasks への参照（後続 PR で FK） |
| bakufu_pid_registry | `stage_id` | `UUID` | NULL（stage と紐づく場合） | — |
| domain_event_outbox | `event_id` | `UUID` | PK, NOT NULL | — |
| domain_event_outbox | `event_kind` | `VARCHAR` | NOT NULL（enum） | — |
| domain_event_outbox | `aggregate_id` | `UUID` | NOT NULL | 発火元 Aggregate |
| domain_event_outbox | `payload_json` | `JSON` | NOT NULL（masking 適用後） | — |
| domain_event_outbox | `created_at` | `DATETIME` | NOT NULL（UTC） | — |
| domain_event_outbox | `status` | `VARCHAR` | NOT NULL（PENDING / DISPATCHING / DISPATCHED / DEAD_LETTER） | — |
| domain_event_outbox | `attempt_count` | `INTEGER` | NOT NULL DEFAULT 0 | — |
| domain_event_outbox | `next_attempt_at` | `DATETIME` | NOT NULL（UTC） | — |
| domain_event_outbox | `last_error` | `TEXT` | NULL（masking 適用後） | — |
| domain_event_outbox | `updated_at` | `DATETIME` | NOT NULL（UTC、リカバリ判定） | — |
| domain_event_outbox | `dispatched_at` | `DATETIME` | NULL | — |
| INDEX | `domain_event_outbox` | `(status, next_attempt_at)` | — | polling SQL 最適化 |

## ユーザー向けメッセージ一覧

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|----|------|----------------|---------|
| MSG-PF-001 | エラー（startup） | `BAKUFU_DATA_DIR` の値が無効 | 相対パス / NUL バイト / `..` を含む値 |
| MSG-PF-002 | エラー（startup） | SQLite engine 初期化失敗 | engine 生成 / PRAGMA SET 失敗 |
| MSG-PF-003 | エラー（startup） | アタッチメント FS ルート作成失敗 | mkdir 失敗 / chmod 失敗 |
| MSG-PF-004 | エラー（startup） | Alembic migration 失敗 | upgrade head 中の例外 |
| MSG-PF-005 | エラー（runtime） | audit_log への DELETE 拒否 | SQLite トリガで `RAISE(ABORT)` 発火 |
| MSG-PF-006 | 警告（runtime） | masking Fail-Secure フォールバック適用 | listener / mask 内で例外発生 → `mask_error` / `listener_error` / `mask_overflow` のいずれかで完全置換（`<REDACTED:*>`）。確定 F の 3 種に同期 |
| MSG-PF-007 | 警告（runtime） | pid_registry GC で `psutil.AccessDenied` | OS が PID 操作を拒否（次回 GC で再試行） |
| MSG-PF-008 | エラー（startup） | masking 環境変数辞書ロード失敗（Fail Fast） | `os.environ` から既知 env キー取得時の OS 例外 / regex compile 失敗。masking layer 1 が無効化された状態での起動を**許容しない**（信頼境界の前提が崩れるため） |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | SQLAlchemy 2.x | pyproject.toml | uv | 新規追加 |
| Python 依存 | aiosqlite | pyproject.toml | uv | 新規追加（async SQLite driver） |
| Python 依存 | Alembic | pyproject.toml | uv | 新規追加 |
| Python 依存 | psutil | pyproject.toml | uv | 新規追加（pid_registry 起動時 GC で使用） |
| Python 依存 | greenlet | pyproject.toml | uv | SQLAlchemy async の transitive 依存 |
| 標準ライブラリ | os / pathlib / platform / re / asyncio | — | — | 既存 |
| 外部サービス | 該当なし | — | — | infrastructure 層のため外部通信なし |
