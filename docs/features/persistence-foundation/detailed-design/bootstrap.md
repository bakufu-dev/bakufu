# 詳細設計補章: Bootstrap 起動シーケンス + cleanup + umask + pid_gc

> 親: [`../detailed-design.md`](../detailed-design.md)。本書は Backend 起動シーケンス（確定 G）、pid_registry 起動時 GC（確定 E）、Bootstrap cleanup（確定 J、Schneier 中等 4 対応）、`os.umask(0o077)` 設定（確定 L、Schneier 中等 1 対応）を凍結する。

## 確定 E: pid_registry 起動時 GC の順序と保護条件

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

**「process_iter で claude プロセスを kill する」実装の禁止**を明文化（[`tech-stack.md`](../../../design/tech-stack.md) §子孫追跡 と同方針）。bakufu 起動前に同一ユーザーが手動で起動した CLI を巻き込まない。

## 確定 G: Backend 起動シーケンスの順序保証（[`../requirements-analysis.md`](../requirements-analysis.md) §確定 R1-C 再掲、実装側）

| 順 | 段階 | 失敗時の挙動 | 後続段階 |
|---|---|---|---|
| 0 | `os.umask(0o077)` SET（§確定 L） | OS が拒否 → `BakufuConfigError` raise → exit 1 | スキップ |
| 1 | DATA_DIR 解決 | `BakufuConfigError(MSG-PF-001)` raise → exit 1 | スキップ |
| 2 | engine 初期化 | `BakufuConfigError(MSG-PF-002)` raise → exit 1 | スキップ |
| 3 | Alembic upgrade head（migration engine 経由） | `BakufuMigrationError(MSG-PF-004)` raise → exit 1 | スキップ |
| 4 | pid_registry GC | `psutil` 例外は WARN ログ → 続行（致命的でない） | 続行 |
| 5 | attachments FS 初期化 | `BakufuConfigError(MSG-PF-003)` raise → exit 1 | スキップ |
| 6 | Outbox Dispatcher 起動 | asyncio.create_task の例外 → exit 1 | スキップ |
| 7 | attachments 孤児 GC スケジューラ起動 | asyncio.create_task の例外 → exit 1 | スキップ |
| 8 | FastAPI / WebSocket リスナ開始 | バインド失敗 → exit 1 | — |

段階 4 のみ非 fatal（孤児 GC が一部失敗しても次回 GC で回収可能）。それ以外は Fail Fast。

### 起動進捗ログ（Norman 指摘 R5「フィードバック原則」対応）

各段階の **開始** / **完了** / **失敗** で構造化ログを出力する。運用者が「どこで詰まったか」を即座に把握できるようにする。ログは masking 適用済みで stdout / 構造化ログファイルの両方に出力。

| 段階 | 開始ログ（INFO） | 完了ログ（INFO） | 失敗ログ（FATAL） |
|----|----|----|----|
| 1 | `[INFO] Bootstrap stage 1/8: resolving BAKUFU_DATA_DIR...` | `[INFO] Bootstrap stage 1/8: data dir resolved at <HOME>/...` | `[FAIL] Bootstrap stage 1/8: ...` |
| 2 | `[INFO] Bootstrap stage 2/8: initializing SQLite engine...` | `[INFO] Bootstrap stage 2/8: engine ready (PRAGMA WAL/foreign_keys/busy_timeout/synchronous/temp_store/defensive applied)` | `[FAIL] Bootstrap stage 2/8: ...` |
| 3 | `[INFO] Bootstrap stage 3/8: applying Alembic migrations...` | `[INFO] Bootstrap stage 3/8: schema at head <revision_id>` | `[FAIL] Bootstrap stage 3/8: ...` |
| 4 | `[INFO] Bootstrap stage 4/8: pid_registry orphan GC...` | `[INFO] Bootstrap stage 4/8: GC complete (killed={n_killed}, protected={n_protected}, absent={n_absent})` | `[WARN] Bootstrap stage 4/8: psutil.AccessDenied for pid={pid}, retry next cycle` |
| 5 | `[INFO] Bootstrap stage 5/8: ensuring attachment FS root...` | `[INFO] Bootstrap stage 5/8: attachments root at <HOME>/.../attachments (mode=0700)` | `[FAIL] Bootstrap stage 5/8: ...` |
| 6 | `[INFO] Bootstrap stage 6/8: starting Outbox Dispatcher (poll_interval=1s, batch=50)...` | `[INFO] Bootstrap stage 6/8: dispatcher running (handler_registry size={N})` + 空レジストリ時の追加 WARN（[`outbox.md`](outbox.md) §確定 K） | `[FAIL] Bootstrap stage 6/8: ...` |
| 7 | `[INFO] Bootstrap stage 7/8: starting attachment orphan GC scheduler (interval=24h)...` | `[INFO] Bootstrap stage 7/8: scheduler running` | `[FAIL] Bootstrap stage 7/8: ...` |
| 8 | `[INFO] Bootstrap stage 8/8: binding FastAPI listener on 127.0.0.1:8000...` | `[INFO] Bootstrap stage 8/8: bakufu Backend ready` | `[FAIL] Bootstrap stage 8/8: ...` |

### ログ出力先

- **構造化ログ**（JSON）: `<DATA_DIR>/logs/bakufu.log`（パーミッション 0600、masking 適用済み）
- **stdout**: 同等内容を人間可読形式で出力（コンテナ運用時に `docker logs` で取得可能）
- **stderr**: FATAL のみ（プロセス exit 直前）

`stage_id` / `stage_name` / `started_at` / `completed_at` / `duration_ms` / `status` / `details` のキーを必ず含める。

### Bootstrap cleanup（Schneier 中等 4 対応、§確定 J）

各段階の失敗時、**段階 6 / 7 で起動した asyncio task は exit 前に `task.cancel()` で停止する**。これは確定 J で凍結する。

## 確定 J: Bootstrap 起動失敗時の cleanup（Schneier 中等 4 対応）

起動シーケンス段階 6（Outbox Dispatcher）/ 段階 7（attachments 孤児 GC scheduler）で起動した asyncio task は、後続段階失敗時に**プロセス exit 前に明示的に cancel する**。グレースフルシャットダウン設計の最初のレイヤを本 PR で凍結する。

### Bootstrap の `try / finally` 構造（凍結）

| 段階 | 起動 task | 段階 6 / 7 失敗時の cleanup | 段階 8 失敗時の cleanup |
|----|----|----|----|
| 6 | `dispatcher_task = asyncio.create_task(dispatcher.run())` | `dispatcher_task.cancel()` → `await asyncio.gather(dispatcher_task, return_exceptions=True)` | 同上 |
| 7 | `gc_task = asyncio.create_task(scheduler.run_forever())` | `gc_task.cancel()` → `await asyncio.gather(gc_task, return_exceptions=True)` | 同上 |
| その他 | — | — | — |

### cleanup 順序

`finally` ブロック内で **後に起動したものから先に cancel**（LIFO）:

1. 段階 7 の scheduler を cancel（先に止めることで `attachment_root.start_orphan_gc_scheduler()` の副作用が増えない）
2. 段階 6 の dispatcher を cancel
3. engine の `dispose()`（接続 pool / WAL flush）
4. 構造化ログ flush
5. プロセス exit（適切な exit code: stage が指定する 1）

### Phase 2 への伸び代

本 PR では Bootstrap 起動失敗時の cleanup のみを凍結。**ランタイム中の `bakufu admin shutdown`** などのグレースフル停止は Phase 2 で `BootstrapShutdown.run()` として拡張する経路を残す（task list を Bootstrap 内で保持しているため、shutdown ハンドラが同じ list を逆順 cancel するだけで実装できる）。

### test-design.md でのカバレッジ

| TC | 検証内容 |
|----|----|
| TC-IT-PF-012-A | 段階 7 で例外発生時、段階 6 の dispatcher_task が `cancel()` 済みになる（`task.cancelled() == True`） |
| TC-IT-PF-012-B | 段階 8 で例外発生時、段階 6 / 7 の両 task が cancel される |
| TC-IT-PF-012-C | engine.dispose() が cleanup 中に必ず呼ばれる（mock で確認） |

## 確定 L: Bootstrap 入口の `os.umask(0o077)` 設定（Schneier 中等 1 対応）

WAL / SHM ファイルや `bakufu_pid_registry` 関連ファイルが SQLite / OS 経由で自動生成される際、**親プロセスの umask が 0022 のままだと 0o644 で作られる**経路がある。これを潰すため、Bootstrap 入口で **`os.umask(0o077)` を最初に SET** する。

### 適用順序

| 順 | 操作 |
|---|---|
| 0（**stage 1 より前**） | `os.umask(0o077)` を SET（`Bootstrap.run()` の最初の文） |
| 1 | DATA_DIR 解決 |
| 2 | engine 初期化（DB / WAL / SHM ファイル作成時に umask 0o077 が効く） |
| 3〜8 | 既存通り |

### POSIX のみ

`os.umask` は POSIX 限定。Windows では `os.umask` は意味を持たないが、`%LOCALAPPDATA%` 配下のホームディレクトリは OS ユーザーのみアクセス可能と信頼（threat-model.md §T5）。

### test-design.md でのカバレッジ

| TC | 検証内容 |
|----|----|
| TC-IT-PF-001-A | Bootstrap 起動後、`bakufu.db-wal` / `bakufu.db-shm` のモードが 0o600 で作成される（POSIX）|
| TC-UT-PF-001-A | `Bootstrap.run()` が最初に `os.umask(0o077)` を呼ぶ（mock で確認）|
