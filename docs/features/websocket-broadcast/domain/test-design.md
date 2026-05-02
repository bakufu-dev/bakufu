# テスト設計書 — websocket-broadcast / domain

<!-- feature: websocket-broadcast / sub-feature: domain -->
<!-- 配置先: docs/features/websocket-broadcast/domain/test-design.md -->
<!-- 対象範囲: REQ-WSB-001〜008 / MSG-WSB-001〜002 / 確定E(Fail Fast) / 親 spec §9 受入基準（domain 担当分）-->
<!-- REQ-WSB-008 M4 スコープ: TaskService(cancel/unblock_retry/commit_deliverable) + ExternalReviewGateService(approve/reject) のみ。AgentService / DirectiveService は M5 Phase 2 -->
<!-- 関連 Issue: #158 feat(websocket-broadcast): Domain Event 基盤 -->

本 sub-feature は domain 層（`domain/events.py`）+ application/ports（`application/ports/event_bus.py`）+ infrastructure（`infrastructure/event_bus.py`）+ ApplicationService 統合（`application/services/*.py`）に閉じる。WebSocket endpoint / ConnectionManager は `http-api` sub-feature（Issue #159）が担当し、本 test-design.md の対象外とする。

外部 I/O ゼロ（DomainEvent / InMemoryEventBus はピュアなインプロセス実装）。ApplicationService 統合テスト（TC-IT-WSB）は SQLite DB 実接続 + SpyEventBus で検証する。

---

## テストマトリクス

| 要件 ID | 実装アーティファクト | テストケース ID | テストレベル | 種別 | 親 spec 受入基準 |
|---|---|---|---|---|---|
| REQ-WSB-001（DomainEvent 基底クラス） | `domain/events.py: DomainEvent` | TC-UT-WSB-001〜005 | ユニット | 正常系 | — |
| REQ-WSB-002（TaskStateChangedEvent） | `domain/events.py: TaskStateChangedEvent` | TC-UT-WSB-006〜009 | ユニット | 正常系 / 異常系 | — |
| REQ-WSB-003（ExternalReviewGateStateChangedEvent） | `domain/events.py: ExternalReviewGateStateChangedEvent` | TC-UT-WSB-010〜013 | ユニット | 正常系 / 異常系 / 境界値 | — |
| REQ-WSB-004（AgentStatusChangedEvent） | `domain/events.py: AgentStatusChangedEvent` | TC-UT-WSB-014〜016 | ユニット | 正常系 / 異常系 | — |
| REQ-WSB-005（DirectiveCompletedEvent） | `domain/events.py: DirectiveCompletedEvent` | TC-UT-WSB-017〜019 | ユニット | 正常系 / 異常系 | — |
| REQ-WSB-006（EventBusPort Protocol） | `application/ports/event_bus.py: EventBusPort` | TC-UT-WSB-020 | ユニット | 正常系 | — |
| REQ-WSB-007（InMemoryEventBus） | `infrastructure/event_bus.py: InMemoryEventBus` | TC-UT-WSB-021〜027 | ユニット | 正常系 / 異常系 / 境界値 | — |
| REQ-WSB-008（ApplicationService 統合 — M4）| `application/services/task_service.py` / `application/services/external_review_gate_service.py` | TC-IT-WSB-001〜004 | 結合 | 正常系 / 異常系 | — |
| REQ-WSB-008（確定E: Fail Fast） | `task_service.py` / `external_review_gate_service.py` `__init__` | TC-UT-WSB-028〜029 | ユニット | 異常系 | — |
| MSG-WSB-001（ハンドラ例外ログ） | `infrastructure/event_bus.py: InMemoryEventBus.publish` | TC-UT-WSB-026 | ユニット | 異常系 | — |
| MSG-WSB-002（配信完了ログ） | `infrastructure/event_bus.py: InMemoryEventBus.publish` | TC-UT-WSB-027 | ユニット | 正常系 | — |

**マトリクス充足の証拠**:
- REQ-WSB-001〜008 すべてに最低 1 件のテストケース ✅
- MSG-WSB-001〜002 すべてに静的文字列照合ケース ✅
- 確定E（Fail Fast）の event_bus=None 検証ケース ✅（TC-UT-WSB-028/029）
- 親 spec 受入基準 §9 #1〜#6 はシステムテスト（`../system-test-design.md`）で検証（domain sub-feature 単体では WebSocket endpoint が存在しないため、全受入基準は http-api 完了後のシステムテストで担保）
- REQ-WSB-008 AgentService / DirectiveService は M5 Phase 2 対象のため本 test-design.md には含めない（未実装 Service への phantom test は許容しない）
- 孤児要件なし

---

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 | characterization 状態 |
|---|---|---|---|---|---|
| SQLite DB（テスト用 tempfile） | TC-IT-WSB: ApplicationService の永続化層 | 不要（既存スキーマを pytest fixture で生成） | `tests/factories/domain_event_factory.py`（本 PR 追加） | pytest `tmp_path` + Alembic `run_upgrade_head` で実 DB 構築 | 不要（実 DB、外部 API なし） |
| asyncio イベントループ | InMemoryEventBus.publish() の非同期実行 | — | — | `pytest-asyncio` の `@pytest.mark.asyncio` | 不要（標準ライブラリ） |

**外部 API・外部サービス依存なし**。全テストケースで characterization fixture は不要。

---

## Factory 定義

`tests/factories/domain_event_factory.py` に以下を追加する。external I/O がないため raw fixture は不要。factory は `_meta.synthetic: True` を保持する。

| Factory クラス | 生成対象 | 主要なデフォルト値 |
|---|---|---|
| `TaskStateChangedEventFactory` | `TaskStateChangedEvent` | `old_status="PENDING"`, `new_status="IN_PROGRESS"` |
| `ExternalReviewGateStateChangedEventFactory` | `ExternalReviewGateStateChangedEvent` | `old_status="OPEN"`, `new_status="PENDING"`, `reviewer_comment=None` |
| `AgentStatusChangedEventFactory` | `AgentStatusChangedEvent` | `old_status="idle"`, `new_status="running"` |
| `DirectiveCompletedEventFactory` | `DirectiveCompletedEvent` | `final_status="DONE"` |

各 Factory インスタンスは `_meta = {"synthetic": True}` フィールドを持つクラス変数で保持する。テストケースの「入力（factory）」列はこの Factory を使用すること。

---

## ユニットテストケース

テストファイル: `tests/unit/test_websocket_broadcast_domain.py`

### REQ-WSB-001: DomainEvent 基底クラス

| テスト ID | 対象クラス.メソッド | 種別 | 入力（factory） | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-001 | `TaskStateChangedEvent` インスタンス化 | 正常系 | `TaskStateChangedEventFactory.build()` | `event_id` が UUID インスタンスである |
| TC-UT-WSB-002 | `TaskStateChangedEvent` インスタンス化 | 正常系 | `TaskStateChangedEventFactory.build()` | `occurred_at` が `timezone.utc` 付き `datetime` インスタンスである |
| TC-UT-WSB-003 | `TaskStateChangedEvent.to_ws_message()` | 正常系 | `TaskStateChangedEventFactory.build()` | 戻り値 dict のキーが `{"event_type", "aggregate_id", "aggregate_type", "occurred_at", "payload"}` の 5 キーのみ |
| TC-UT-WSB-004 | `TaskStateChangedEvent.to_ws_message()` | 正常系 | `TaskStateChangedEventFactory.build()` | `occurred_at` 値が ISO 8601 UTC 形式文字列（`str` 型、`Z` または `+00:00` 含む） |
| TC-UT-WSB-005 | `TaskStateChangedEvent.to_ws_message()` | 正常系 | `TaskStateChangedEventFactory.build()` | `payload` に `event_id` / `event_type` / `aggregate_id` / `aggregate_type` / `occurred_at` が**含まれない** |

### REQ-WSB-002: TaskStateChangedEvent

| テスト ID | 対象クラス.メソッド | 種別 | 入力（factory） | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-006 | `TaskStateChangedEvent` インスタンス化 | 正常系 | `TaskStateChangedEventFactory.build()` | インスタンスが生成される（例外なし） |
| TC-UT-WSB-007 | `TaskStateChangedEvent.event_type` | 正常系 | `TaskStateChangedEventFactory.build()` | `event_type == "task.state_changed"` |
| TC-UT-WSB-008 | `TaskStateChangedEvent.to_ws_message()` | 正常系 | `TaskStateChangedEventFactory.build(aggregate_id="task-uuid-1", directive_id="d1", old_status="PENDING", new_status="IN_PROGRESS", room_id="r1")` | `payload == {"directive_id": "d1", "old_status": "PENDING", "new_status": "IN_PROGRESS", "room_id": "r1"}`（`task_id` フィールドは存在しない。task の識別子は base class フィールド `aggregate_id` に設定する）|
| TC-UT-WSB-009 | `TaskStateChangedEvent` インスタンス化 | 異常系 | `directive_id` 欠落（必須フィールド省略） | `pydantic.ValidationError` が発火する |

### REQ-WSB-003: ExternalReviewGateStateChangedEvent

| テスト ID | 対象クラス.メソッド | 種別 | 入力（factory） | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-010 | `ExternalReviewGateStateChangedEvent` インスタンス化 | 境界値 | `ExternalReviewGateStateChangedEventFactory.build(reviewer_comment=None)` | `reviewer_comment is None` でインスタンス生成される |
| TC-UT-WSB-011 | `ExternalReviewGateStateChangedEvent` インスタンス化 | 正常系 | `ExternalReviewGateStateChangedEventFactory.build(reviewer_comment="LGTM")` | `reviewer_comment == "LGTM"` でインスタンス生成される |
| TC-UT-WSB-012 | `ExternalReviewGateStateChangedEvent.event_type` | 正常系 | `ExternalReviewGateStateChangedEventFactory.build()` | `event_type == "external_review_gate.state_changed"` |
| TC-UT-WSB-013 | `ExternalReviewGateStateChangedEvent` インスタンス化 | 異常系 | `gate_id` 欠落（必須フィールド省略） | `pydantic.ValidationError` が発火する |

### REQ-WSB-004: AgentStatusChangedEvent

| テスト ID | 対象クラス.メソッド | 種別 | 入力（factory） | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-014 | `AgentStatusChangedEvent` インスタンス化 | 正常系 | `AgentStatusChangedEventFactory.build()` | インスタンスが生成される（例外なし） |
| TC-UT-WSB-015 | `AgentStatusChangedEvent.event_type` | 正常系 | `AgentStatusChangedEventFactory.build()` | `event_type == "agent.status_changed"` |
| TC-UT-WSB-016 | `AgentStatusChangedEvent` インスタンス化 | 異常系 | `agent_id` 欠落（必須フィールド省略） | `pydantic.ValidationError` が発火する |

### REQ-WSB-005: DirectiveCompletedEvent

| テスト ID | 対象クラス.メソッド | 種別 | 入力（factory） | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-017 | `DirectiveCompletedEvent` インスタンス化 | 正常系 | `DirectiveCompletedEventFactory.build()` | インスタンスが生成される（例外なし） |
| TC-UT-WSB-018 | `DirectiveCompletedEvent.event_type` | 正常系 | `DirectiveCompletedEventFactory.build()` | `event_type == "directive.completed"` |
| TC-UT-WSB-019 | `DirectiveCompletedEvent` インスタンス化 | 異常系 | `directive_id` 欠落（必須フィールド省略） | `pydantic.ValidationError` が発火する |

### REQ-WSB-006: EventBusPort Protocol

| テスト ID | 対象クラス.メソッド | 種別 | 入力 | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-020 | `EventBusPort` Protocol 適合確認 | 正常系 | `InMemoryEventBus()` インスタンス | `isinstance(InMemoryEventBus(), EventBusPort)` が `True` である（runtime_checkable Protocol）。あるいは pyright strict で型エラーなし（静的検査） |

### REQ-WSB-007: InMemoryEventBus

| テスト ID | 対象クラス.メソッド | 種別 | 入力 | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-021 | `InMemoryEventBus.subscribe()` | 正常系 | ダミー async callable | `subscribe()` 後、`_handlers` リストの長さが 1 増加する |
| TC-UT-WSB-022 | `InMemoryEventBus.publish()` | 正常系 | `TaskStateChangedEventFactory.build()` + 1 個の spy handler | `publish()` 後、spy handler が event を 1 回受け取る |
| TC-UT-WSB-023 | `InMemoryEventBus.publish()` | 境界値 | ハンドラ未登録の空 EventBus + `TaskStateChangedEventFactory.build()` | 例外なく正常完了する |
| TC-UT-WSB-024 | `InMemoryEventBus.publish()` | 正常系 | `TaskStateChangedEventFactory.build()` + 3 個の spy handler | 全 3 handler が event を受け取る（asyncio.gather で並行実行） |
| TC-UT-WSB-025 | `InMemoryEventBus.publish()` — Fail Soft | 異常系 | 1 個目が例外を発火するハンドラ + 2 個目は正常な spy handler | 2 個目の spy handler が event を受け取る（1 個目の例外が他をブロックしない） |
| TC-UT-WSB-026 | `InMemoryEventBus.publish()` — MSG-WSB-001 | 異常系 | 例外を発火するハンドラ + `caplog` フィクスチャ | WARNING レベルのログに `"EventBus handler error:"` 文字列が含まれる（MSG-WSB-001 静的照合） |
| TC-UT-WSB-027 | `InMemoryEventBus.publish()` — MSG-WSB-002 | 正常系 | 正常 spy handler + `caplog` フィクスチャ | DEBUG レベルのログに `"DomainEvent published:"` 文字列が含まれる（MSG-WSB-002 静的照合） |

### 確定E（Fail Fast）: event_bus=None 禁止

`detailed-design.md §確定E` の凍結: 各 Service の `__init__` は `event_bus: EventBusPort` を必須引数とし、`None` デフォルトを禁止する（Fail Fast）。以下のケースでこの契約を検証する。

| テスト ID | 対象クラス.メソッド | 種別 | 入力 | 期待結果 |
|---|---|---|---|---|
| TC-UT-WSB-028 | `TaskService.__init__` | 異常系 | `event_bus=None`（または `event_bus` 引数を省略）を渡してインスタンス化 | `TypeError` または `pydantic.ValidationError` が発火する（`None` は許容されない） |
| TC-UT-WSB-029 | `ExternalReviewGateService.__init__` | 異常系 | `event_bus=None`（または `event_bus` 引数を省略）を渡してインスタンス化 | `TypeError` または `pydantic.ValidationError` が発火する（`None` は許容されない） |

---

## 結合テストケース

テストファイル: `tests/integration/test_websocket_broadcast_domain.py`

**前提**:
- DB: `tmp_path` ベースの SQLite 実接続（pytest fixture で `run_upgrade_head` を実行済み）
- EventBus: `InMemoryEventBus()` に SpyHandler を登録（InMemoryEventBus 自体は実装を使用）
- 各 Service は `event_bus: EventBusPort` を DI 注入した状態でインスタンス化する

**M4 対象 Service**:
- `TaskService`: `cancel()` / `unblock_retry()` / `commit_deliverable()` のみ（M4 実装済み）
- `ExternalReviewGateService`: `approve()` / `reject()` のみ（M4 実装済み）
- `AgentService` / `DirectiveService`: M5 Phase 2 対象 — 本 test-design.md では扱わない

| テスト ID | 対象モジュール連携 | 使用 factory | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|---|
| TC-IT-WSB-001 | `TaskService.cancel()` → `InMemoryEventBus.publish()` | `TaskStateChangedEventFactory` | DB に Task 存在（キャンセル可能な状態）、EventBus に SpyHandler 登録 | `task_service.cancel(task_id)` を呼ぶ | SpyHandler が `TaskStateChangedEvent`（`event_type="task.state_changed"`）を 1 件受け取る |
| TC-IT-WSB-002 | `TaskService.cancel()` 失敗時の publish() 非呼び出し | `TaskStateChangedEventFactory` | DB に Task 不存在（invalid task_id）、EventBus に SpyHandler 登録 | `task_service.cancel(invalid_id)` を呼ぶ | 例外が発火する（Task 未発見等）。SpyHandler の受信件数が 0 である |
| TC-IT-WSB-003 | `TaskService.cancel()` 成功 → EventBus handler 例外が業務結果をブロックしない | `TaskStateChangedEventFactory` | DB に Task 存在、EventBus に「必ず例外を発火するハンドラ」を登録 | `task_service.cancel(task_id)` を呼ぶ | Service の戻り値（TaskResponse 相当）が返る。例外が呼び出し元に伝播しない |
| TC-IT-WSB-004 | `ExternalReviewGateService.approve()` → `ExternalReviewGateStateChangedEvent` publish | `ExternalReviewGateStateChangedEventFactory` | DB に Gate 存在（承認待ち状態）、EventBus に SpyHandler 登録 | `gate_service.approve(gate_id, reviewer_comment="LGTM")` を呼ぶ | SpyHandler が `ExternalReviewGateStateChangedEvent`（`event_type="external_review_gate.state_changed"`, `reviewer_comment` が masking 適用済み）を 1 件受け取る |

---

## カバレッジ基準

- REQ-WSB-001〜008 の各要件に **最低 1 件** のテストケースが対応する ✅（マトリクス参照）
- MSG-WSB-001〜002 の各文言が **静的文字列照合** で検証される ✅（TC-UT-WSB-026/027）
- 親 spec §9 受入基準 #1〜#6 は http-api sub-feature（Issue #159）完了後のシステムテストで検証する。本 sub-feature 単体では WebSocket endpoint 未実装のため受入基準の直接検証は不可
- 行カバレッジ目標: `domain/events.py` + `application/ports/event_bus.py` + `infrastructure/event_bus.py` で **90% 以上**（feature-spec.md §10 Q-2 準拠）

---

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で `pytest (unit + integration)` ジョブが緑
- ローカル:
  ```bash
  cd backend
  uv run pytest tests/unit/test_websocket_broadcast_domain.py -v
  uv run pytest tests/integration/test_websocket_broadcast_domain.py -v
  uv run pytest tests/unit/test_websocket_broadcast_domain.py tests/integration/test_websocket_broadcast_domain.py --cov=bakufu.domain.events --cov=bakufu.application.ports.event_bus --cov=bakufu.infrastructure.event_bus --cov-report=term-missing
  ```

---

## テストディレクトリ構造

```
backend/tests/
├── factories/
│   └── domain_event_factory.py       # 新規追加: DomainEvent 各クラス用 factory
├── unit/
│   └── test_websocket_broadcast_domain.py   # TC-UT-WSB-001〜029（確定E Fail Fast 含む）
└── integration/
    └── test_websocket_broadcast_domain.py   # TC-IT-WSB-001〜004（M4 スコープ: TaskService + ExternalReviewGateService）
```

---

## 未決課題・要起票 characterization task

本 sub-feature は外部 I/O（外部 API / 外部サービス）に依存しない。全テストケースで characterization fixture は不要。

| # | タスク | 状態 |
|---|---|---|
| — | 外部 I/O 依存なし → characterization 不要 | 確定（不要） |

---

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — REQ-WSB-001〜008
- [`detailed-design.md`](detailed-design.md) — MSG-WSB-001〜002 確定文言 / クラス詳細
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様（UC-WSB / 業務ルール R1 / 受入基準 §9）
- [`../system-test-design.md`](../system-test-design.md) — システムテスト（feature 業務概念単位、WebSocket 全体 E2E）
