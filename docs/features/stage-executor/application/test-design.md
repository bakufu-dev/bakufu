# テスト設計書 — stage-executor / application

<!-- feature: stage-executor / sub-feature: application -->
<!-- 配置先: docs/features/stage-executor/application/test-design.md -->
<!-- 対象範囲: REQ-ME-001〜007 / MSG-ME-001〜004 / 確定 A〜H / 脅威 T1〜T4 -->
<!-- 関連 Issue: #163 feat(M5-A): stage-executorサービス実装 -->

本 sub-feature は `application/services/stage_executor_service.py`（StageKind dispatch・LLM エラー分類・BLOCKED 回復エントリポイント）および `infrastructure/worker/stage_worker.py`（asyncio Queue + Semaphore）を対象とする。

---

## テストマトリクス

| 要件 ID | 実装アーティファクト | テストケース ID | テストレベル | 種別 | 親 spec 受入基準 |
|---|---|---|---|---|---|
| REQ-ME-001（WORK Stage LLM 実行）| `application/services/stage_executor_service.py: dispatch_stage()` | TC-UT-ME-101〜105, TC-IT-ME-101〜102 | ユニット / 結合 | 正常系 | §9 #1 |
| REQ-ME-002（INTERNAL_REVIEW 委譲）| `application/services/stage_executor_service.py: dispatch_stage()` | TC-UT-ME-201〜202, TC-IT-ME-201 | ユニット / 結合 | 正常系 / 異常系 | §9 #2 |
| REQ-ME-003（EXTERNAL_REVIEW 遷移）| `application/services/stage_executor_service.py: dispatch_stage()` | TC-UT-ME-301, TC-IT-ME-301 | ユニット / 結合 | 正常系 | §9 #3 |
| REQ-ME-004（LLM エラー 5 分類 + EmptyResponse → BLOCKED）| `application/services/stage_executor_service.py: _handle_llm_error()` | TC-UT-ME-401〜409, TC-IT-ME-401 | ユニット / 結合 | 異常系 | §9 #4 |
| REQ-ME-005（BLOCKED retry エントリポイント）| `application/services/stage_executor_service.py: retry_blocked_task()` | TC-UT-ME-501〜503, TC-IT-ME-501〜502 | ユニット / 結合 | 正常系 / 異常系 | §9 #5 |
| REQ-ME-006（StageWorker 並行数制御）| `infrastructure/worker/stage_worker.py` | TC-UT-ME-601〜603, TC-IT-ME-601 | ユニット / 結合 | 正常系 / 境界値 / 異常系 | §9 #6 |
| REQ-ME-007（InternalReviewGateExecutorPort 凍結）| `application/ports/internal_review_gate_executor_port.py` | TC-UT-ME-701 | ユニット | 正常系 | — |
| MSG-ME-001（WORK Stage 失敗文言）| `StageExecutorService._handle_llm_error()` | TC-UT-ME-402 | ユニット | 異常系 | — |
| MSG-ME-002（INTERNAL_REVIEW 委譲失敗文言）| `StageExecutorService.dispatch_stage()` | TC-UT-ME-202 | ユニット | 異常系 | — |
| MSG-ME-003（retry 非 BLOCKED 文言）| `StageExecutorService.retry_blocked_task()` | TC-UT-ME-502 | ユニット | 異常系 | — |
| MSG-ME-004（retry task 不在文言）| `StageExecutorService.retry_blocked_task()` | TC-UT-ME-503 | ユニット | 異常系 | — |
| T1（masking gateway 強制通過）| `dispatch_stage()` deliverable / last_error | TC-UT-ME-103, TC-UT-ME-406, TC-IT-ME-402 | ユニット / 結合 | 異常系 | — |
| T2（subprocess 環境変数フィルタ）| `StageExecutorService._execute_work_stage()` | TC-UT-ME-106 | ユニット | 異常系 | — |
| T3（pid_registry 孤児防止）| `infrastructure/worker/stage_worker.py` + `pid_registry` | TC-IT-ME-103 | 結合 | 正常系 / 異常系 | — |
| T4（BLOCKED 回復 Service 経由必須）| `StageExecutorService.retry_blocked_task()` | TC-IT-ME-502 | 結合 | 正常系 | — |
| §確定 D（session_id = Stage ID）| `StageExecutorService._execute_work_stage()` | TC-UT-ME-102 | ユニット | 正常系 | — |
| §確定 F（Fail Fast: 不正 Task.status 検証）| `StageExecutorService.dispatch_stage()` / `retry_blocked_task()` | TC-UT-ME-107, TC-UT-ME-502 | ユニット | 異常系 | — |
| §確定 G（InternalReviewGateExecutorPort = typing.Protocol）| `application/ports/internal_review_gate_executor_port.py` | TC-UT-ME-701 | ユニット | 正常系 | — |

**マトリクス充足の証拠**:
- REQ-ME-001〜007 すべてに最低 1 件のテストケース ✅
- MSG-ME-001〜004 すべてに静的文字列照合ケース ✅
- 親受入基準 §9 #1〜#6 すべてにシステムテスト（[`../system-test-design.md`](../system-test-design.md)）または結合テスト対応あり ✅
- 脅威 T1〜T4 すべてに有効性確認ケース ✅
- 確定 D / F / G / H の設計凍結事項に対応ケース ✅
- §確定 H（LLMProviderError 5 分類 + EmptyResponse）の全クラスに個別テストケース ✅（TC-UT-ME-401〜409）
- 孤児要件なし

---

## LLMProviderError 例外階層マッピング（§確定 H 適用済み）

`detailed-design.md §確定 H`（commit `d839813` / ヘルスバーグ指摘対応）で 5 分類と実装クラスのマッピングが凍結された。本テスト設計書はこの凍結に従う。

| 業務分類 | 実装クラス | 新規 / 既存 | 判定根拠 |
|---|---|---|---|
| SessionLost | `LLMProviderSessionLostError` | **新規追加必須** | stderr: `"session not found"` / `"unknown session"` |
| RateLimited | `LLMProviderRateLimitedError` | **新規追加必須** | stderr: `"rate limit"` / HTTP 429 相当 |
| AuthExpired | `LLMProviderAuthError` | 既存活用（名称変更なし）| stderr: `"OAuth"` / `"unauthorized"` / `"authentication"` |
| Timeout | `LLMProviderTimeoutError` | 既存活用 | asyncio.TimeoutError / 10 分無応答 |
| Unknown（catch-all）| `LLMProviderProcessError` | 既存活用（セマンティクス明確化）| 上記いずれにも非該当の非ゼロ exit code |
| （独立保持）| `LLMProviderEmptyResponseError` | 既存活用（5 分類外・独立）| exit 0 だが deliverable 空 |

**実装担当が M5-A コーディング着手前に完了すべき事項**:
1. `domain/exceptions/llm_provider.py` に `LLMProviderSessionLostError` / `LLMProviderRateLimitedError` を追加する（§確定 H 参照）
2. `tests/factories/llm_provider_error.py` に `make_session_lost_error()` / `make_rate_limited_error()` を追加する（TBD-4）
3. 上記 2 件なしで実装に入った場合はレビューで **[却下]** する

---

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 | characterization 状態 |
|---|---|---|---|---|---|
| `LLMProviderPort`（Claude Code CLI subprocess）| WORK Stage の LLM 呼び出し | 不要（スタブ代替）| `tests/factories/stub_llm_provider.py: make_stub_llm_provider()` / `make_stub_llm_provider_raises()` | ユニット: `AsyncMock`。結合: スタブアダプタ（実 subprocess を起動しない）| 不要（stub adapter 使用）|
| `LLMProviderError` サブクラス（5 分類 + EmptyResponse）| エラーハンドリング入力 | — | `tests/factories/llm_provider_error.py`（既存: `make_auth_error` / `make_timeout_error` / `make_process_error` / `make_empty_response_error`。**追加必須**: `make_session_lost_error` / `make_rate_limited_error`）| ユニット: factory 経由。結合: factory 経由 + スタブ raises | 一部要追加（SessionLost / RateLimited の factory は M5-A 実装着手前に追加）|
| SQLite DB（`tasks` / `bakufu_pid_registry` / `domain_event_outbox`）| Task 取得・保存、pid 登録、Outbox | — | `tests/factories/db.py: make_test_engine()` / `create_all_tables()` + domain factories | 実 DB（`tmp_path` ベースの SQLite）| 不要（実接続）|
| `asyncio.Queue` / `asyncio.Semaphore` | Stage キューイング・並行数制御 | — | — | 実 asyncio（`pytest-asyncio` strict mode）| 不要（標準ライブラリ）|
| `masking` gateway（`infrastructure/security/masking.py`）| deliverable / last_error のシークレットマスキング | — | — | 実実装を使用（モックしない）| 不要（内部実装）|
| `EventBusPort`（InMemoryEventBus）| Domain Event 発行（TaskBlocked / DeliverableCommitted 等）| — | ユニット: `AsyncMock`。結合: `InMemoryEventBus()` 実インスタンス | ユニット: mock。結合: 実バス + spy handler | 不要（内部実装）|

**外部 API・外部サービス直接接続なし**。Claude Code CLI は全テストでスタブに置き換える。

---

## モック方針

| テストレベル | モック対象 | 方針 |
|---|---|---|
| ユニット | `LLMProviderPort` / `TaskRepositoryPort` / `WorkflowRepositoryPort` / `AgentRepositoryPort` / `InternalReviewGateExecutorPort` / `ExternalReviewGateService` / `EventBusPort` | `AsyncMock(spec=...)` で全外部依存をモック。masking gateway は**実実装**を使用（T1 検証のため）|
| 結合 | Claude Code CLI subprocess | スタブアダプタ（`make_stub_llm_provider_raises()` で失敗シミュレーション）。DB / asyncio Queue / masking は実接続 |

---

## ユニットテストケース

テストファイル: `tests/unit/test_stage_executor_application.py`

### REQ-ME-001: WORK Stage LLM 実行

| テスト ID | 対象メソッド | 種別 | 入力（factory）| 期待結果 |
|---|---|---|---|---|
| TC-UT-ME-101 | `StageExecutorService.dispatch_stage()` — WORK Stage 正常系 | 正常系 | `make_stage(kind=StageKind.WORK)` + `make_stub_llm_provider(responses=[ChatResult(...)])` | `LLMProviderPort.chat()` が 1 回呼ばれる。`Task.commit_deliverable()` が呼ばれる |
| TC-UT-ME-102 | `dispatch_stage()` — session_id = Stage ID（§確定 D）| 正常系 | `make_stage(kind=StageKind.WORK)` | `LLMProviderPort.chat()` に渡される `session_id` が Stage ID の UUID 文字列に一致する |
| TC-UT-ME-103 | `dispatch_stage()` — deliverable は masking gateway 通過後に commit（T1）| 正常系 | LLM 応答にシークレットパターンを含む `ChatResult`（`make_stub_llm_provider()` で設定）| `Task.commit_deliverable()` に渡される deliverable が masking 済みであり、シークレット原文が含まれない |
| TC-UT-ME-104 | `dispatch_stage()` — 次 Stage あり → `Task.advance_to_next()` + StageWorker.enqueue() | 正常系 | 2 Stage の Workflow（WORK → WORK）の 1st Stage を指す Task | `Task.advance_to_next()` が呼ばれ、`StageWorker.enqueue(task_id, next_stage_id)` が呼ばれる |
| TC-UT-ME-105 | `dispatch_stage()` — 終端 Stage → `Task.complete()` | 正常系 | 単一 Stage の Workflow の終端 Task | `Task.complete()` が呼ばれる。`Task.advance_to_next()` は呼ばれない |
| TC-UT-ME-106 | `dispatch_stage()` — subprocess 環境変数は allow list のみ引き継ぐ（T2）| 正常系 | `os.environ` に `AWS_ACCESS_KEY_ID=fake` を追加した状態 | LLM subprocess に渡される `env` dict に `AWS_ACCESS_KEY_ID` が含まれない。`PATH` / `HOME` / `BAKUFU_*` は含まれる |
| TC-UT-ME-107 | `dispatch_stage()` — Task.status ≠ IN_PROGRESS で Fail Fast（§確定 F）| 異常系 | `make_task(status=TaskStatus.DONE)` | 例外を即送出する。`LLMProviderPort.chat()` は呼ばれない |

### REQ-ME-002: INTERNAL_REVIEW Stage 委譲

| テスト ID | 対象メソッド | 種別 | 入力（factory）| 期待結果 |
|---|---|---|---|---|
| TC-UT-ME-201 | `dispatch_stage()` — INTERNAL_REVIEW Stage → Port.execute() 呼び出し | 正常系 | `make_stage(kind=StageKind.INTERNAL_REVIEW, required_gate_roles=frozenset({...}))` | `InternalReviewGateExecutorPort.execute(task_id, stage_id, required_gate_roles)` が 1 回呼ばれる。`LLMProviderPort.chat()` は呼ばれない |
| TC-UT-ME-202 | `dispatch_stage()` — Port.execute() 例外 → Task.block() + MSG-ME-002 文言（静的照合）| 異常系 | `InternalReviewGateExecutorPort.execute()` が `RuntimeError` を発火する `AsyncMock` | `Task.block()` が呼ばれる。Conversation system message に `"[FAIL] Internal review gate execution failed:"` が含まれる |

### REQ-ME-003: EXTERNAL_REVIEW Stage 遷移

| テスト ID | 対象メソッド | 種別 | 入力（factory）| 期待結果 |
|---|---|---|---|---|
| TC-UT-ME-301 | `dispatch_stage()` — EXTERNAL_REVIEW Stage → Task.request_external_review() | 正常系 | `make_stage(kind=StageKind.EXTERNAL_REVIEW)` | `Task.request_external_review()` が呼ばれる。`InternalReviewGateExecutorPort.execute()` / `LLMProviderPort.chat()` は呼ばれない |

### REQ-ME-004: LLM エラー 5 分類 + EmptyResponse → BLOCKED

§確定 H のマッピング（`detailed-design.md §確定 H`）に従い、実装クラス名で凍結する。`make_session_lost_error()` / `make_rate_limited_error()` は M5-A 実装着手前に factory 追加（TBD-4）が完了していること。

| テスト ID | 対象メソッド | 種別 | 入力（factory / 実装クラス）| 期待結果 |
|---|---|---|---|---|
| TC-UT-ME-401 | `_handle_llm_error()` — `LLMProviderAuthError` → 即 BLOCKED（リトライなし）| 異常系 | `make_auth_error()` → `LLMProviderAuthError` | `Task.block()` が 1 回呼ばれる。`LLMProviderPort.chat()` は再呼び出しなし |
| TC-UT-ME-402 | `_handle_llm_error()` — MSG-ME-001 文言（`LLMProviderAuthError`, 静的照合）| 異常系 | `make_auth_error()` | Conversation system message に `"[FAIL] Stage execution failed:"` が含まれる。`"bakufu admin retry-task"` への言及が含まれる |
| TC-UT-ME-403 | `_handle_llm_error()` — `LLMProviderSessionLostError` → 1 回リトライ → 成功 | 正常系 | `make_session_lost_error()` → `LLMProviderSessionLostError`（新規クラス）+ 2 回目 chat() 成功する stub | `LLMProviderPort.chat()` が 2 回呼ばれる。`Task.block()` は呼ばれない |
| TC-UT-ME-404 | `_handle_llm_error()` — `LLMProviderSessionLostError` → 1 回リトライ → 失敗 → BLOCKED | 異常系 | `make_session_lost_error()` + 2 回目も `LLMProviderSessionLostError` を発火する stub | `LLMProviderPort.chat()` が 2 回呼ばれる。`Task.block()` が 1 回呼ばれる |
| TC-UT-ME-405 | `_handle_llm_error()` — `LLMProviderRateLimitedError` → backoff 3 回 → 成功 | 正常系 | `make_rate_limited_error()` → `LLMProviderRateLimitedError`（新規クラス）+ 4 回目 chat() 成功する stub | `LLMProviderPort.chat()` が 4 回呼ばれる（初回 + backoff 3 回）。`Task.block()` は呼ばれない |
| TC-UT-ME-406 | `_handle_llm_error()` — last_error は masking gateway 通過済み（T1）| 異常系 | `make_auth_error()` + masking が反応するシークレット文字列を `message` に含める | `Task.block(last_error=...)` の引数 `last_error` にシークレット原文が含まれない（masking 通過確認）|
| TC-UT-ME-407 | `_handle_llm_error()` — `LLMProviderProcessError` → 即 BLOCKED（Unknown catch-all、リトライなし）| 異常系 | `make_process_error()` → `LLMProviderProcessError`（既存 factory ✅）| `Task.block()` が 1 回呼ばれる。リトライなし |
| TC-UT-ME-408 | `_handle_llm_error()` — `LLMProviderEmptyResponseError` → 即 BLOCKED（独立保持、Unknown 相当）| 異常系 | `make_empty_response_error()` → `LLMProviderEmptyResponseError`（既存 factory ✅）| `Task.block()` が 1 回呼ばれる。リトライなし（空応答は内容的異常として独立扱い）|
| TC-UT-ME-409 | `_handle_llm_error()` — `LLMProviderTimeoutError` → SIGTERM/SIGKILL → SessionLost 相当（1 回リトライ）| 異常系 | `make_timeout_error()` → `LLMProviderTimeoutError`（既存 factory ✅）+ 2 回目 chat() 成功する stub | Timeout がプロセス終了後に SessionLost 相当のリトライ 1 回に合流する。`LLMProviderPort.chat()` が 2 回呼ばれる |

### REQ-ME-005: BLOCKED Task retry エントリポイント

| テスト ID | 対象メソッド | 種別 | 入力（factory）| 期待結果 |
|---|---|---|---|---|
| TC-UT-ME-501 | `retry_blocked_task()` — 正常系 | 正常系 | `make_task(status=TaskStatus.BLOCKED)` | `Task.unblock_retry()` が呼ばれる。`StageWorker.enqueue(task_id, task.current_stage_id)` が呼ばれる |
| TC-UT-ME-502 | `retry_blocked_task()` — Task.status ≠ BLOCKED → MSG-ME-003（静的照合・§確定 F）| 異常系 | `make_task(status=TaskStatus.IN_PROGRESS)` | `Task.unblock_retry()` は呼ばれない。返値 / 例外に `"[FAIL] Task"` と `"is not BLOCKED"` が含まれる |
| TC-UT-ME-503 | `retry_blocked_task()` — Task 不在 → MSG-ME-004（静的照合）| 異常系 | 存在しない `task_id`（`TaskRepository.find_by_id()` が `None` を返す）| 返値 / 例外に `"[FAIL] Task"` と `"not found"` が含まれる |

### REQ-ME-006: StageWorker 並行数制御

| テスト ID | 対象メソッド | 種別 | 入力（factory）| 期待結果 |
|---|---|---|---|---|
| TC-UT-ME-601 | `StageWorker.enqueue()` → `dispatch_stage()` が呼ばれる | 正常系 | `task_id` / `stage_id` の 1 組 | `StageExecutorService.dispatch_stage(task_id, stage_id)` が 1 回呼ばれる |
| TC-UT-ME-602 | Semaphore acquire → dispatch_stage() → release のサイクル（§確定 A）| 正常系 | 正常完了する `dispatch_stage()` Mock | `dispatch_stage()` 実行前に Semaphore が `acquire()` 済みであり、実行後に `release()` が呼ばれる |
| TC-UT-ME-603 | `dispatch_stage()` 例外 → Semaphore release（リーク防止）| 異常系 | `dispatch_stage()` が `RuntimeError` を発火する Mock | 例外後も Semaphore が release されている（ロック状態でないことを確認）|

### REQ-ME-007: InternalReviewGateExecutorPort 定義（§確定 G）

| テスト ID | 対象 | 種別 | 入力 | 期待結果 |
|---|---|---|---|---|
| TC-UT-ME-701 | `InternalReviewGateExecutorPort` — typing.Protocol / runtime_checkable | 正常系 | Port を実装した stub クラス | `isinstance(stub, InternalReviewGateExecutorPort)` が `True`。Port が `typing.Protocol` として定義されている（`runtime_checkable` デコレータ確認）|

---

## 結合テストケース

テストファイル: `tests/integration/test_stage_executor_application.py`

**前提**:
- DB: `tmp_path` ベースの SQLite（`create_all_tables` 実行済み）
- LLM: `make_stub_llm_provider()` / `make_stub_llm_provider_raises()` でスタブ（実 subprocess 不使用）
- EventBus: `InMemoryEventBus()` + spy handler で Domain Event を記録
- masking: 実実装（API キー環境変数クリア済み: `monkeypatch.delenv(...)` 使用）
- `BAKUFU_MAX_CONCURRENT_STAGES`: `monkeypatch.setenv(...)` で制御

| テスト ID | 対象モジュール連携 | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|
| TC-IT-ME-101 | `StageExecutorService` + `TaskRepository` + LLM stub + masking | Task（IN_PROGRESS, WORK Stage）・Workflow・Agent を DB にシード。スタブが deliverable を返す | `dispatch_stage(task_id, stage_id)` を呼ぶ | DB の Task が `current_stage_id = next_stage_id` になっている（`TaskRepository.find_by_id()` で確認）。`DeliverableCommitted` イベントが EventBus に発行される |
| TC-IT-ME-102 | `StageExecutorService` 終端 Stage → Task DONE | 単一 Stage の Workflow の Task を DB にシード | `dispatch_stage()` を呼ぶ | DB の Task.status = `TaskStatus.DONE` になっている |
| TC-IT-ME-103 | pid_registry INSERT → subprocess 完了 → DELETE（T3）| Task・Workflow・Agent を DB にシード。`bakufu_pid_registry` テーブルが空 | `dispatch_stage()` を呼ぶ（スタブで制御）| 呼び出し完了後に `bakufu_pid_registry` テーブルが空である（孤児行なし）|
| TC-IT-ME-201 | `StageExecutorService` + `InternalReviewGateExecutorPort` stub | Task（IN_PROGRESS, INTERNAL_REVIEW Stage）を DB にシード。Port stub（AsyncMock）を DI 注入 | `dispatch_stage(task_id, stage_id)` を呼ぶ | Port stub の `execute(task_id, stage_id, required_gate_roles)` が 1 回呼ばれている |
| TC-IT-ME-301 | `StageExecutorService` + EXTERNAL_REVIEW Stage + DB | Task（IN_PROGRESS, EXTERNAL_REVIEW Stage）を DB にシード | `dispatch_stage(task_id, stage_id)` を呼ぶ | DB の Task.status = `TaskStatus.AWAITING_EXTERNAL_REVIEW` になっている |
| TC-IT-ME-401 | `StageExecutorService` + AuthExpired エラー → DB に BLOCKED（受入基準 #4）| Task（IN_PROGRESS, WORK Stage）を DB にシード。スタブが `LLMProviderAuthError` を発火 | `dispatch_stage()` を呼ぶ | DB の Task.status = `TaskStatus.BLOCKED` になっている。`Task.last_error` が `None` でない |
| TC-IT-ME-402 | masking gateway — last_error にシークレット非混入（T1）| シークレットパターンを含む AuthExpired エラーメッセージをスタブに設定 | `dispatch_stage()` を呼ぶ | DB に保存された `Task.last_error` にシークレット原文が含まれない |
| TC-IT-ME-501 | `StageExecutorService.retry_blocked_task()` + DB + StageWorker（受入基準 #5）| Task（BLOCKED, WORK Stage）を DB にシード。StageWorker mock（enqueue 記録用）| `retry_blocked_task(task_id)` を呼ぶ | DB の Task.status = `TaskStatus.IN_PROGRESS` になっている。`StageWorker.enqueue(task_id, current_stage_id)` が 1 回呼ばれる |
| TC-IT-ME-502 | `retry_blocked_task()` は Service 経由のみ — audit_log 記録（T4）| Task（BLOCKED）を DB にシード | `retry_blocked_task(task_id)` を呼ぶ | audit_log テーブル（または Conversation system message）に retry 操作の記録が存在する |
| TC-IT-ME-601 | `StageWorker` — BAKUFU_MAX_CONCURRENT_STAGES=1 でシリアル実行（受入基準 #6）| `BAKUFU_MAX_CONCURRENT_STAGES=1`。Task 2 件が同時に WORK Stage に遷移する状態を作る | 2 件分の `enqueue()` を同時に呼ぶ | 2 件の `dispatch_stage()` が並列ではなく順次実行される（実行順序 / 完了タイミングを spy で確認）|

---

## カバレッジ基準

- REQ-ME-001〜007 の各要件に **最低 1 件**のテストケースが対応する ✅（マトリクス参照）
- MSG-ME-001〜004 の各確定文言が **静的文字列照合**で検証される ✅（TC-UT-ME-402/202/502/503）
- 親受入基準（[`../feature-spec.md §9`](../feature-spec.md)）#1〜#6 の各々がシステムテスト（[`../system-test-design.md`](../system-test-design.md)）または結合テストで検証される ✅
- 脅威 T1〜T4 すべてに有効性確認ケース ✅（TC-UT-ME-103/406, TC-UT-ME-106, TC-IT-ME-103, TC-IT-ME-502）
- 設計凍結 §確定 D / F / G に対応ケース ✅（TC-UT-ME-102, TC-UT-ME-107/502, TC-UT-ME-701）
- LLM エラー全分類（§確定H: `LLMProviderSessionLostError` / `LLMProviderRateLimitedError` / `LLMProviderAuthError` / `LLMProviderTimeoutError` / `LLMProviderProcessError` / `LLMProviderEmptyResponseError`）すべてに個別テストケース ✅（TC-UT-ME-401〜409）
- 行カバレッジ目標: `application/services/stage_executor_service.py` + `infrastructure/worker/stage_worker.py` で **90% 以上**（feature-spec.md §10 Q-3 準拠）

---

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で `pytest (unit + integration)` ジョブが緑
- ローカル:
  ```bash
  # ユニットテストのみ
  uv run pytest backend/tests/unit/test_stage_executor_application.py -v
  # 結合テストのみ
  uv run pytest backend/tests/integration/test_stage_executor_application.py -v
  # 全テスト
  uv run pytest backend/tests/ -v
  ```

---

## テストディレクトリ構造

```
backend/tests/
├── factories/
│   └── llm_provider_error.py          # 既存（make_auth_error/make_timeout_error/make_process_error/make_empty_response_error）
│                                      # ↑ M5-A 実装前に make_session_lost_error / make_rate_limited_error を追加（TBD-4）
├── unit/
│   └── test_stage_executor_application.py   # TC-UT-ME-101〜701（本 Issue）
└── integration/
    └── test_stage_executor_application.py   # TC-IT-ME-101〜601（本 Issue）
```

---

## 未決課題・要対応 task

| # | タスク | 状態 | 起票先 | 優先度 |
|---|---|---|---|---|
| TBD-1 | `LLMProviderSessionLostError` の定義（新規クラス追加）| ✅ **§確定H で凍結済み**（`detailed-design.md §確定H`）| #163 実装 PR 内で `domain/exceptions/llm_provider.py` に追加 | 実装着手前に必須 |
| TBD-2 | `LLMProviderRateLimitedError` の定義（新規クラス追加）| ✅ **§確定H で凍結済み**（`detailed-design.md §確定H`）| #163 実装 PR 内で `domain/exceptions/llm_provider.py` に追加 | 実装着手前に必須 |
| TBD-3 | Unknown の扱い（`LLMProviderProcessError` vs 新規クラス）| ✅ **§確定H で凍結済み**（`LLMProviderProcessError` = Unknown catch-all として使用）| 対応不要（既存クラス活用で確定）| — |
| TBD-4 | `tests/factories/llm_provider_error.py` に `make_session_lost_error()` / `make_rate_limited_error()` を追加 | **要対応**（TBD-1/2 のクラス追加後）| #163 実装 PR 内 | 実装着手前に必須（TC-UT-ME-403〜405/409 で使用）|
| TBD-5 | `bakufu_pid_registry` テーブルの実際の INSERT/DELETE タイミングを TC-IT-ME-103 で確定（スタブの粒度に依存）| 継続（実装時に確定）| TC-IT-ME-103 実装時 | 結合テスト実装時 |

---

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — REQ-ME-001〜007 機能要件
- [`detailed-design.md §確定 A〜H`](detailed-design.md) — 設計凍結事項（session_id / Semaphore / MSG 文言 / LLMProviderError 5 分類マッピング）
- [`../feature-spec.md §7 R1-1〜R1-8`](../feature-spec.md) — 業務ルール（エラー分類・リトライ戦略・BLOCKED 回復）
- [`../feature-spec.md §9`](../feature-spec.md) — 親受入基準 #1〜#6
- [`../system-test-design.md`](../system-test-design.md) — システムテスト（TC-ST-ME-001〜006）
