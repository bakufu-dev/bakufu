# テスト設計書 — admin-cli / application

> feature: `admin-cli` / sub-feature: `application`
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md)
> 担当 Issue: [#165 feat(M5-C): admin-cli実装](https://github.com/bakufu-dev/bakufu/issues/165)

## 本書の役割

本書は **admin-cli / application sub-feature の IT（結合テスト）と UT（単体テスト）** を凍結する。システムテスト（TC-ST-AC-001〜010）は [`../system-test-design.md`](../system-test-design.md) が担当する。本書が担う IT テストは REQ-AC-NNN モジュール契約を網羅し、システムテストが扱わない境界条件（TaskNotFoundError / TaskNotCancellable / OutboxEventNotFoundError / audit_log FAIL 記録）を補完する。

## テスト方針

| レベル | 対象 | 手段 |
|-------|------|------|
| IT（結合）| `AdminService` + 実 SQLite（Port 実装クラス経由）| pytest-asyncio + `tests/factories/db.py` + 実 ORM Row factory |
| UT（単体）| `AdminService` のビジネスロジック（Fail Fast 検証・audit_log 記録タイミング）| pytest-asyncio + AsyncMock で Port をスタブ化 |

**実 SQLite を使う理由**: `AuditLogWriterPort` / `OutboxEventRepositoryPort` の実装クラスは SQLAlchemy `async_sessionmaker` に依存し、DB への追記を伴う。Mock では §確定 A（audit_log 常時記録）の end-to-end 動作を検証できない。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-AC-001 | `AdminService.list_blocked_tasks()` | TC-IT-AC-001, TC-IT-AC-013 | IT | 正常系 / 境界値 | feature-spec.md §9 #11 |
| REQ-AC-002 | `AdminService.retry_task()` | TC-IT-AC-002, TC-IT-AC-003, TC-IT-AC-004 | IT | 正常系 / 異常系 | feature-spec.md §9 #12 |
| REQ-AC-003 | `AdminService.cancel_task()` | TC-IT-AC-005, TC-IT-AC-006, TC-IT-AC-007, TC-IT-AC-008 | IT | 正常系 / 異常系 | feature-spec.md §9 #12b |
| REQ-AC-004 | `AdminService.list_dead_letters()` | TC-IT-AC-009 | IT | 正常系 | feature-spec.md §9 #13a |
| REQ-AC-005 | `AdminService.retry_event()` | TC-IT-AC-010, TC-IT-AC-011, TC-IT-AC-012 | IT | 正常系 / 異常系 | feature-spec.md §9 #13b |
| §確定 A | `AdminService._write_audit()` (try/finally) | TC-UT-AC-001, TC-UT-AC-002, TC-UT-AC-003, TC-UT-AC-004 | UT | 正常系 / 異常系 | feature-spec.md §9 #14 |
| §確定 B | `retry_task()` / `cancel_task()` status 検証 | TC-UT-AC-005, TC-UT-AC-006 | UT | 異常系 | feature-spec.md R1-2 / R1-3 |
| §確定 C | `retry_event()` status 検証 | TC-UT-AC-007 | UT | 異常系 | feature-spec.md R1-5 |
| §確定 E | `actor` DI 注入 | TC-UT-AC-008 | UT | 正常系 | — |
| MSG-AC-001 | `TaskNotFoundError.message` | TC-UT-AC-009 | UT | 文言照合 | — |
| MSG-AC-002 | `IllegalTaskStateError.message`（retry）| TC-UT-AC-010 | UT | 文言照合 | — |
| MSG-AC-003 | `IllegalTaskStateError.message`（cancel）| TC-UT-AC-011 | UT | 文言照合 | — |
| MSG-AC-004 | `OutboxEventNotFoundError.message` | TC-UT-AC-012 | UT | 文言照合 | — |
| MSG-AC-005 | `IllegalOutboxStateError.message` | TC-UT-AC-013 | UT | 文言照合 | — |
| T2: args_json raw テキスト禁止 | `_write_audit()` args_json 制限 | TC-UT-AC-014 | UT | セキュリティ | §確定 A |

**マトリクス充足の証拠**:
- REQ-AC-001 〜 REQ-AC-005 全てに IT テストケース（最低 1 件）
- §確定 A〜E 全てに UT テストケース（最低 1 件）
- MSG-AC-001 〜 MSG-AC-005 全てに文言照合テスト
- T2 脅威に有効性確認テスト
- 親受入基準 #11 / #12 / #12b / #13a / #13b / #14 がシステムテストまたは IT テストで検証

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 |
|---|---|---|---|---|
| SQLite `tasks` テーブル | BLOCKED Task 取得・status 更新 | — | `tests/factories/task.py` 既存（`make_blocked_task` / `make_in_progress_task` / `make_awaiting_review_task` / `make_done_task` / `make_cancelled_task`）| 実 DB（`make_test_engine` + `create_all_tables`）|
| SQLite `domain_event_outbox` テーブル | DEAD_LETTER Event 取得・status リセット | — | `tests/factories/persistence_rows.py` 既存（`make_outbox_row(status="DEAD_LETTER", attempt_count=N)`）| 実 DB |
| SQLite `audit_log` テーブル | 全操作の証跡記録 | — | `tests/factories/persistence_rows.py` 既存（`make_audit_log_row`、読み取り確認のみ）| 実 DB。INSERT は AdminService が担う |
| システム時刻 `now(UTC)` | `retry_event()` の `next_attempt_at` リセット値 | — | テスト内で `datetime.now(UTC)` を before/after で比較 | before ≤ actual ≤ after の範囲チェック |

**外部 API 依存なし**。Characterization fixture 不要。DBとの実接続のみ。

**IT テストの前提**:
- `create_all_tables(engine)` + `make_test_session_factory(engine)` で一時 SQLite DB を構築（`tmp_path` fixture 使用）
- 全 Task エンティティは `make_task(...)` / `make_blocked_task(...)` 等の既存 factory で構築し `SqliteTaskRepository(session).save(task)` でシード
- `OutboxRow` は `make_outbox_row(status="DEAD_LETTER", ...)` でシードし `session.add(row)` + `session.commit()` で永続化
- audit_log の検証は `SELECT * FROM audit_log ORDER BY executed_at DESC LIMIT 1` に相当する Repository 呼び出しで確認

## 結合テストケース（IT）

テストファイル: `backend/tests/integration/test_admin_service.py`

### TC-IT-AC-001: list_blocked_tasks() — BLOCKED Task のみ返す（R1-1）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-001 |
| 前提 | DB に status=BLOCKED × 3、status=IN_PROGRESS × 1 をシード |
| 操作 | `AdminService.list_blocked_tasks()` を await |
| 期待結果 | 3 件の `BlockedTaskSummary` が返る。IN_PROGRESS Task は含まれない。各 summary の `task_id` / `room_id` / `last_error` / `blocked_at` が Task の属性と一致する |
| 受入基準 | feature-spec.md §9 #11 |

### TC-IT-AC-002: retry_task() — BLOCKED → IN_PROGRESS 正常系 + audit_log OK（§確定 A）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-002 / §確定 A |
| 前提 | DB に BLOCKED Task をシード |
| 操作 | `AdminService.retry_task(task_id)` を await |
| 期待結果 | DB の `tasks.status = 'IN_PROGRESS'`、`tasks.last_error = NULL` に更新される。`audit_log` に `command='retry-task'` / `result='OK'` / `error_text=NULL` のレコードが追記される |
| 受入基準 | feature-spec.md §9 #12 / #14 |

### TC-IT-AC-003: retry_task() — TaskNotFoundError + audit_log FAIL

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-002 エラー時 / §確定 A |
| 前提 | DB が空（対象 task_id は存在しない）|
| 操作 | 存在しない `task_id` で `AdminService.retry_task(task_id)` を await |
| 期待結果 | `TaskNotFoundError` が送出される。`audit_log` に `command='retry-task'` / `result='FAIL'` のレコードが追記される |

### TC-IT-AC-004: retry_task() — 非 BLOCKED Task → IllegalTaskStateError + audit_log FAIL（§確定 B / R1-2）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-002 エラー時 / §確定 B |
| 前提 | DB に status=IN_PROGRESS の Task をシード |
| 操作 | `AdminService.retry_task(task_id)` を await |
| 期待結果 | `IllegalTaskStateError` が送出される。`audit_log` に `result='FAIL'` のレコードが追記される |

### TC-IT-AC-005: cancel_task() — BLOCKED Task → CANCELLED + audit_log OK（§確定 B / R1-3）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-003 / §確定 B |
| 前提 | DB に status=BLOCKED の Task をシード |
| 操作 | `AdminService.cancel_task(task_id, reason="test")` を await |
| 期待結果 | DB の `tasks.status = 'CANCELLED'` に更新される。`audit_log` に `result='OK'` が追記される |
| 受入基準 | feature-spec.md §9 #12b |

### TC-IT-AC-006: cancel_task() — IN_PROGRESS Task → CANCELLED + audit_log OK（R1-3 正常系）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-003 / feature-spec.md R1-3 |
| 前提 | DB に status=IN_PROGRESS の Task をシード |
| 操作 | `AdminService.cancel_task(task_id, reason="test")` を await |
| 期待結果 | DB の `tasks.status = 'CANCELLED'` に更新される。`audit_log` に `result='OK'` が追記される |

### TC-IT-AC-007: cancel_task() — AWAITING_EXTERNAL_REVIEW → IllegalTaskStateError + audit_log FAIL（R1-3 MVP スコープ外）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-003 エラー時 / feature-spec.md R1-3 |
| 前提 | DB に status=AWAITING_EXTERNAL_REVIEW の Task をシード |
| 操作 | `AdminService.cancel_task(task_id, reason="test")` を await |
| 期待結果 | `IllegalTaskStateError` が送出される。`audit_log` に `result='FAIL'` が追記される |
| 注記 | AWAITING_EXTERNAL_REVIEW は R1-3 で明示禁止（MVP スコープ外）。ExternalReviewGate との整合が必要なため |

### TC-IT-AC-008: cancel_task() — DONE Task → IllegalTaskStateError + audit_log FAIL（R1-3）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-003 エラー時 |
| 前提 | DB に status=DONE の Task をシード |
| 操作 | `AdminService.cancel_task(task_id, reason="test")` を await |
| 期待結果 | `IllegalTaskStateError` が送出される。`audit_log` に `result='FAIL'` が追記される |

### TC-IT-AC-009: list_dead_letters() — DEAD_LETTER Event のみ返す（R1-4）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-004 |
| 前提 | DB に status=DEAD_LETTER × 2、status=PENDING × 1 の OutboxRow をシード |
| 操作 | `AdminService.list_dead_letters()` を await |
| 期待結果 | 2 件の `DeadLetterSummary` が返る。PENDING の OutboxRow は含まれない。各 summary の `event_id` / `event_kind` / `attempt_count` / `last_error` が OutboxRow の属性と一致する |
| 受入基準 | feature-spec.md §9 #13a |

### TC-IT-AC-010: retry_event() — DEAD_LETTER → PENDING + attempt_count=0 + audit_log OK（R1-5）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-005 / §確定 C |
| 前提 | DB に status=DEAD_LETTER / attempt_count=5 の OutboxRow をシード |
| 操作 | `AdminService.retry_event(event_id)` を await |
| 期待結果 | DB の `status='PENDING'` / `attempt_count=0` / `next_attempt_at` が now(UTC) 以降に更新される。`audit_log` に `result='OK'` が追記される |
| 受入基準 | feature-spec.md §9 #13b |

### TC-IT-AC-011: retry_event() — OutboxEventNotFoundError + audit_log FAIL

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-005 エラー時 |
| 前提 | DB が空（対象 event_id は存在しない）|
| 操作 | 存在しない `event_id` で `AdminService.retry_event(event_id)` を await |
| 期待結果 | `OutboxEventNotFoundError` が送出される。`audit_log` に `result='FAIL'` が追記される |

### TC-IT-AC-012: retry_event() — 非 DEAD_LETTER → IllegalOutboxStateError + audit_log FAIL（§確定 C / R1-5）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-005 エラー時 / §確定 C |
| 前提 | DB に status=PENDING の OutboxRow をシード |
| 操作 | `AdminService.retry_event(event_id)` を await |
| 期待結果 | `IllegalOutboxStateError` が送出される。`audit_log` に `result='FAIL'` が追記される |

### TC-IT-AC-013: list_blocked_tasks() 0 件 — 空リスト + audit_log OK（R1-1 境界値）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-001 / feature-spec.md R1-1 |
| 前提 | DB に BLOCKED Task が存在しない（IN_PROGRESS のみ）|
| 操作 | `AdminService.list_blocked_tasks()` を await |
| 期待結果 | 空リスト `[]` が返る（エラーではない）。`audit_log` に `result='OK'` が追記される |

## ユニットテストケース（UT）

テストファイル: `backend/tests/unit/test_admin_service.py`

UT は全 Port を AsyncMock でスタブ化し、AdminService のビジネスロジックを DB 接続なしで検証する。

| テストID | 対象 | 種別 | 入力（mock/factory） | 期待結果 |
|---|---|---|---|---|
| TC-UT-AC-001 | `_write_audit()` — 成功時 result=OK | 正常系 | `result='OK'`, `error_text=None` | `audit_log_writer.write()` が `result='OK'` / `error_text=None` で呼ばれる |
| TC-UT-AC-002 | `_write_audit()` — 失敗時 result=FAIL | 正常系 | `result='FAIL'`, `error_text='some_error'` | `audit_log_writer.write()` が `result='FAIL'` / `error_text='some_error'` で呼ばれる |
| TC-UT-AC-003 | `retry_task()` — 例外発生後も audit_log が記録される（§確定 A） | 異常系 | `task_repo.find_by_id` が `TaskNotFoundError` を raise | `TaskNotFoundError` が再送出される AND `audit_log_writer.write()` が `result='FAIL'` で呼ばれる（try/finally 保証） |
| TC-UT-AC-004 | `cancel_task()` — 例外発生後も audit_log が記録される（§確定 A） | 異常系 | `task_repo.find_by_id` が `IllegalTaskStateError` を raise | `IllegalTaskStateError` が再送出される AND `audit_log_writer.write()` が `result='FAIL'` で呼ばれる |
| TC-UT-AC-005 | `retry_task()` — DONE Task は Fail Fast（§確定 B） | 異常系 | `task_repo.find_by_id` が `make_done_task()` を返す | `IllegalTaskStateError` が送出される（`task.unblock_retry()` は呼ばれない）|
| TC-UT-AC-006 | `cancel_task()` — CANCELLED Task は Fail Fast（§確定 B） | 異常系 | `task_repo.find_by_id` が `make_cancelled_task()` を返す | `IllegalTaskStateError` が送出される |
| TC-UT-AC-007 | `retry_event()` — PENDING OutboxRow は Fail Fast（§確定 C） | 異常系 | `outbox_event_repo.find_by_id` が `status='PENDING'` の `OutboxEventView` を返す | `IllegalOutboxStateError` が送出される（`reset_to_pending()` は呼ばれない）|
| TC-UT-AC-008 | `actor` フィールドが audit_log に記録される（§確定 E） | 正常系 | `AdminService(actor="test_user", ...)` で初期化 | `audit_log_writer.write()` の `actor='test_user'` 引数で呼ばれる |
| TC-UT-AC-009 | MSG-AC-001 — TaskNotFoundError のメッセージ文言 | 文言照合 | `TaskNotFoundError(task_id)` を構築 | `str(error)` に `[FAIL]` および `task_id` 相当の文字列が含まれる |
| TC-UT-AC-010 | MSG-AC-002 — IllegalTaskStateError(retry) のメッセージ文言 | 文言照合 | `IllegalTaskStateError(task_id, 'IN_PROGRESS', 'retry-task')` を構築 | `str(error)` に `BLOCKED` が含まれる |
| TC-UT-AC-011 | MSG-AC-003 — IllegalTaskStateError(cancel) のメッセージ文言 | 文言照合 | `IllegalTaskStateError(task_id, 'DONE', 'cancel-task')` を構築 | `str(error)` に `BLOCKED` / `PENDING` / `IN_PROGRESS` のいずれかが含まれる |
| TC-UT-AC-012 | MSG-AC-004 — OutboxEventNotFoundError のメッセージ文言 | 文言照合 | `OutboxEventNotFoundError(event_id)` を構築 | `str(error)` に `[FAIL]` および `event_id` 相当の文字列が含まれる |
| TC-UT-AC-013 | MSG-AC-005 — IllegalOutboxStateError のメッセージ文言 | 文言照合 | `IllegalOutboxStateError(event_id, 'PENDING')` を構築 | `str(error)` に `DEAD_LETTER` が含まれる |
| TC-UT-AC-014 | T2 対策 — args_json に raw テキスト（last_error）が含まれない | セキュリティ | `task_repo.find_by_id` が last_error 付き BLOCKED Task を返す | `audit_log_writer.write()` の `args_json` に `last_error` の値が含まれていない（task_id のみ）|

## カバレッジ基準

| 対象 | カバレッジ目標 |
|-----|------------|
| REQ-AC-001 〜 REQ-AC-005 の各要件 | IT テストで最低 1 件検証 |
| §確定 A（audit_log 常時記録） | TC-UT-AC-003 / TC-UT-AC-004 で try/finally 動作を検証 |
| §確定 B / C（Fail Fast） | UT で BLOCKED 以外・DEAD_LETTER 以外のケースを検証 |
| MSG-AC-001 〜 MSG-AC-005 | 全文言で静的文字列照合 |
| T2 脅威（args_json raw テキスト禁止）| TC-UT-AC-014 で args_json 内容を検証 |
| 親受入基準 #11 / #12 / #12b / #13a / #13b | IT テストで DB 状態変化を検証 |
| 親受入基準 #14（audit_log 全操作記録）| TC-IT-AC-002 / TC-IT-AC-010 で `result='OK'`、TC-IT-AC-003 / TC-IT-AC-004 で `result='FAIL'` を確認 |

## テストディレクトリ構造

```
backend/tests/
├── factories/
│   ├── task.py            ← 既存（make_blocked_task / make_in_progress_task 等）
│   └── persistence_rows.py ← 既存（make_outbox_row / make_audit_log_row）
├── unit/
│   └── test_admin_service.py       ← TC-UT-AC-001〜014
└── integration/
    └── test_admin_service.py       ← TC-IT-AC-001〜013
```

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全ジョブ緑であること
- ローカル: `cd backend && python -m pytest tests/unit/test_admin_service.py tests/integration/test_admin_service.py -v`

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — REQ-AC-001〜005
- [`detailed-design.md §確定事項`](detailed-design.md) — §確定 A〜E / MSG-AC-001〜005
- [`../feature-spec.md §7`](../feature-spec.md) — 業務ルール R1-1〜R1-8
- [`../system-test-design.md`](../system-test-design.md) — システムテスト TC-ST-AC-001〜010
