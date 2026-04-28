# テスト設計書

<!-- feature: task-repository -->
<!-- 配置先: docs/features/task-repository/test-design.md -->
<!-- 対象範囲: REQ-TR-001〜006 / 詳細設計 §確定 R1-A〜R1-K / 6段階 save() / BUG-DRR-001 closure / 2 masking カラム物理保証 / §BUG-TR-002 凍結（conversations 除外） -->

本 feature は M2 Repository **7 番目の Aggregate Repository PR**（empire / workflow / agent / room / directive 後）。Task Aggregate（M1、PR #42 マージ済み）に対する Repository 層を新規追加する。テンプレートは directive-repository (PR #50) を 100% 継承しつつ、**6-method Protocol**（`find_by_id` / `count` / `save(task)` / `count_by_status` / `count_by_room` / `find_blocked`）と **Task 固有の多段階 6-step save()** および **2 masking カラム**（`tasks.last_error` / `deliverables.body_markdown`）の構造を確立する。

> **§BUG-TR-002 凍結**: `conversations` / `conversation_messages` は YAGNI 違反（Task Aggregate PR #42 に `conversations` 属性なし）のため本 PR スコープから除外。関連テスト（`make_task_with_conversations` factory / `conversation_messages` masking テスト）は §BUG-TR-002 解除 PR が担当する。

task-repository 固有の論点 5 件を**専用テストファイルで物理保証**する:

1. **save() 6 段階**（§確定 R1-B）— 2 DELETE（CASCADE 活用）→ tasks UPSERT → 3 INSERT の順序強制と子テーブル完全往復
2. **2 masking カラム**（§確定 R1-E）— `tasks.last_error` / `deliverables.body_markdown` に raw secret が DB に残らないことを raw SQL で物理確認
3. **find_blocked ORDER BY updated_at DESC, id DESC + tiebreaker**（§確定 R1-H）— BUG-EMR-001 規約の Task 版。同時刻複数 BLOCKED Task で id DESC が tiebreaker として機能することを物理確認
4. **BUG-DRR-001 closure 物理確認**（§確定 R1-C）— 0007 適用後に `directives.task_id → tasks.id` FK が **存在すること**を `PRAGMA foreign_key_list('directives')` で確認（TC-IT-DRR-006 の反転）
5. **§設計決定 TR-001: `task_assigned_agents.agent_id` FK 非存在確認**（Aggregate 境界設計決定）— 0007 時点で `task_assigned_agents.agent_id` FK が **存在しないこと**を物理確認（room_members.agent_id 前例と同論理）

**最初から 5 ファイル分割**（directive-repo PR #50 正規構成の継承。`test_masking_fields.py` が 2 masking カラム物理保証の核心、`test_find_blocked.py` が find_blocked + count_by_* の 3 新 method 専用ファイル、`test_count_methods.py` が count 系 SQL 保証専用、`test_save_child_tables.py` が 6 段階 save() 物理確認専用）。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-TR-001 | `TaskRepository` Protocol **6 method** 定義 | TC-UT-TR-001 | 結合 | 正常系 | 1, 2 |
| REQ-TR-002（find_by_id） | `find_by_id` 存在 / 不在 | TC-UT-TR-002 | 結合 | 正常系 | 3 |
| REQ-TR-002（save round-trip） | `save(task)` 6 段階 → `find_by_id` round-trip | TC-UT-TR-003 | 結合 | 正常系 | 4 |
| REQ-TR-002（save 6段階 DELETE+UPSERT+INSERT） | 6 段階順序の物理確認（child table 完全往復） | TC-UT-TR-005 / TC-UT-TR-005b / TC-UT-TR-005c | 結合 | 正常系 | 4 |
| REQ-TR-002（count SQL） | `count()` が SQL `COUNT(*)` を発行 | TC-UT-TR-004 | 結合 | 正常系 | — |
| REQ-TR-002（count_by_status） | `count_by_status(status)` が SQL `COUNT(*) WHERE status = :status` を発行 | TC-UT-TR-006 | 結合 | 正常系 | — |
| REQ-TR-002（count_by_room） | `count_by_room(room_id)` が SQL `COUNT(*) WHERE room_id = :room_id` を発行 | TC-UT-TR-007 | 結合 | 正常系 | — |
| REQ-TR-002（find_blocked）| `find_blocked()` が BLOCKED Task のみ ORDER BY updated_at DESC, id DESC で返す | TC-UT-TR-008 / TC-UT-TR-008b / TC-UT-TR-008c / TC-UT-TR-008d / TC-UT-TR-008e | 結合 | 正常系 | — |
| REQ-TR-002（Tx boundary）| commit path 永続化 / rollback path 破棄 | TC-UT-TR-009 | 結合 | 正常系 / 異常系 | — |
| **REQ-TR-002（masking、§確定 R1-E）** | raw `last_error` / `body_markdown` → DB に `<REDACTED:*>` 永続化（**2 masking カラム物理保証**、§BUG-TR-002 凍結済みのため `conversation_messages` 除外）| TC-IT-TR-020-masking-* (6 経路) | 結合 | 正常系 | 5 |
| REQ-TR-003（Alembic 0007 DDL）| 4 テーブル + INDEX + FK 群作成（§BUG-TR-002 凍結済みのため conversations/conversation_messages 除外）| TC-IT-TR-001 / TC-IT-TR-002 / TC-IT-TR-003 | 結合 | 正常系 | 6 |
| REQ-TR-003（Alembic chain） | 0001→...→0007 単一 head | TC-IT-TR-004 | 結合 | 正常系 | — |
| REQ-TR-003（upgrade/downgrade） | 双方向 migration が idempotent | TC-IT-TR-005 | 結合 | 正常系 | 6 |
| REQ-TR-003（down_revision） | `0007.down_revision == "0006_directive_aggregate"` | TC-IT-TR-006 | 結合 | 正常系 | — |
| REQ-TR-003（Room CASCADE FK）| Room 削除で Task 自動削除（CASCADE）| TC-IT-TR-007 | 結合 | 正常系 | 7 |
| REQ-TR-003（BUG-DRR-001 closure）| 0007 適用後に `directives.task_id → tasks.id` FK が存在する | TC-IT-TR-008 | 結合 | 正常系 | 8 |
| REQ-TR-003（§設計決定 TR-001: Aggregate 境界）| 0007 で `task_assigned_agents.agent_id` FK が存在しない（Aggregate 境界設計決定） | TC-IT-TR-009 | 結合 | 正常系 | 9 |
| REQ-TR-004（CI Layer 2）| arch test parametrize（2 カラム追加）| TC-UT-TR-arch | 結合 | 正常系 | 10 |
| REQ-TR-004（CI Layer 1）| grep guard で 2 カラムの `MaskedText` 必須 | （CI ジョブ） | — | — | 10 |
| REQ-TR-005（storage.md）| §逆引き表更新（Task 関連 4 行追加）| TC-DOC-TR-001 | doc 検証 | 正常系 | 11 |
| REQ-TR-006（directive-repo §BUG-DRR-001 closure 記録）| directive-repository 詳細設計書の §BUG-DRR-001 が closure 済み状態を記録 | TC-IT-TR-008（物理確認で代替） | 結合 | 正常系 | 8 |
| **§確定 R1-A（テンプレ継承）** | empire/workflow/agent/room/directive §確定 A 継承 | TC-UT-TR-001〜009 全件 | 結合 | — | — |
| **§確定 R1-B（save 6 段階）** | DELETE 逆順 → tasks UPSERT → 3 テーブル INSERT 順序の物理確認 | TC-UT-TR-005 | 結合 | 正常系 | 4 |
| **§確定 R1-C（BUG-DRR-001 closure）** | 0007 で directives.task_id FK 追加の物理確認 | TC-IT-TR-008 | 結合 | 正常系 | 8 |
| **§確定 R1-D（6-method Protocol）** | count_by_status / count_by_room / find_blocked の 3 新 method 追加 | TC-UT-TR-006 / TC-UT-TR-007 / TC-UT-TR-008 | 結合 | 正常系 | — |
| **§確定 R1-E（CI 三層防衛 2 カラム）** | 正のチェック + 負のチェック 2 カラム分（§BUG-TR-002 凍結済みのため conversation_messages 除外）| TC-UT-TR-arch + TC-DOC-TR-001 | 結合 / doc | 正常系 | 10 |
| **§確定 R1-H（ORDER BY 決定論性）** | 全子テーブルの ORDER BY + find_blocked の tiebreaker | TC-UT-TR-003 + TC-UT-TR-008e | 結合 | 正常系 | — |
| **§確定 R1-A（TypeDecorator 信頼）** | UUIDStr / MaskedText 二重変換なし | TC-UT-TR-003 + TC-IT-TR-020-masking-* | 結合 | 正常系 | — |
| **§確定 R1-B（6 段階順序）** | deliverables UNIQUE(task_id, stage_id) 上書き確認 | TC-UT-TR-005 / TC-UT-TR-005b | 結合 | 正常系 | 4 |
| **§確定 R1-J（_from_rows 子構造再組み立て）** | assigned_agent_ids 順序 / deliverables dict / conversations list は §BUG-TR-002凍結済みのため除外 | TC-UT-TR-003 | 結合 | 正常系 | — |
| **§設計決定 TR-001（agent FK 非存在: Aggregate 境界）** | 0007 で task_assigned_agents.agent_id FK が存在しない（Aggregate 境界設計決定、room_members.agent_id 前例） | TC-IT-TR-009 | 結合 | 正常系 | 9 |
| **Lifecycle 統合** | save → find_by_id → count_by_status → find_blocked → save（更新）の 6 method 連携 | TC-IT-TR-LIFECYCLE | 結合 | 正常系 | 1, 4, 6 |

**マトリクス充足の証拠**:

- REQ-TR-001〜006 すべてに最低 1 件のテストケース
- **save() 6 段階の順序確認**: TC-UT-TR-005 で child table DELETE → tasks UPSERT → child INSERT の順序違反が `IntegrityError` になることを物理確認（段階 3 より前に tasks UPSERT をしないことの確認）
- **2 masking カラム全経路**: TC-IT-TR-020-masking-* で `tasks.last_error` / `deliverables.body_markdown` の各カラムに masked + passthrough + roundtrip を確認（§BUG-TR-002 凍結済みのため `conversation_messages.body_markdown` 除外）
- **find_blocked ORDER BY tiebreaker（BUG-EMR-001 準拠）**: TC-UT-TR-008e で同時刻 BLOCKED Task の id DESC tiebreaker を物理確認
- **BUG-DRR-001 closure**: TC-IT-TR-008 で 0007 適用後の `PRAGMA foreign_key_list('directives')` が `tasks` 参照を含むことを確認（TC-IT-DRR-006 の反転）
- **§設計決定 TR-001（Aggregate 境界）**: TC-IT-TR-009 で `task_assigned_agents.agent_id` FK が 0007 時点で存在しないことを確認（room_members.agent_id 前例と同論理）
- **全子テーブル ORDER BY 決定論性**: TC-UT-TR-003 で _from_rows の復元順序が §確定 R1-H 通りであることを確認
- 受入基準 1〜9 すべてに unit/integration ケース、10〜11 は CI / doc 確認
- 孤児要件ゼロ

## 外部 I/O 依存マップ

本 feature は infrastructure 層の Repository 実装。directive-repo と同方針で本物の SQLite + 本物の Alembic + 本物の SQLAlchemy AsyncSession + 本物の MaskingGateway を使う。

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **SQLite (sqlite+aiosqlite)** | engine / session / 4 テーブル / Alembic 0007 migration | 不要（実 DB を `tmp_path` 配下の bakufu.db で起動、テストごとに使い捨て）| 不要 | **済（M2 永続化基盤 conftest の `app_engine` / `session_factory` fixture を再利用）** |
| **ファイルシステム** | `BAKUFU_DATA_DIR` / `bakufu.db` / WAL/SHM | 不要（`pytest.tmp_path`）| 不要 | **済（本物使用）** |
| **Alembic** | 0007 revision の `upgrade head` / `downgrade base` + chain 検証 | 不要（本物の `alembic upgrade` を実 SQLite に対し実行）| 不要 | **済（本物使用、persistence-foundation の `run_upgrade_head` を再利用）** |
| **SQLAlchemy 2.x AsyncSession** | UoW 境界 / Repository メソッド経由の SQL 発行 | 不要 | 不要 | **済（本物使用）** |
| **MaskingGateway (`mask`)** | `MaskedText.process_bind_param` 経由で 2 カラムをマスキング（§BUG-TR-002凍結済みのため conversation_messages 除外）| 不要（実 init を `_initialize_masking` autouse fixture で実施）| 不要 | **済（persistence-foundation #23 で characterization 完了、本 PR で配線実適用）** |

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 | 備考 |
|--------|-----|------------------|------|
| `make_task`（**本 PR で追加**） | `Task`（valid デフォルト: `status=PENDING`, `last_error=None`, `assigned_agent_ids=[]`, `deliverables={}`）| `True` | task PR #42 の Task Aggregate factory |
| `make_task_with_agents`（**本 PR で追加**） | `Task`（`assigned_agent_ids` に 2 Agent 付き）| `True` | save() 段階 4 の INSERT テスト用 |
| `make_task_with_deliverables`（**本 PR で追加**） | `Task`（`deliverables` に 1 Deliverable + 1 Attachment 付き）| `True` | save() 段階 5/6 の INSERT テスト用 |
| `make_task_full`（**本 PR で追加**） | `Task`（全子構造を持つ full Task。assigned_agents / deliverables / attachments すべて付き）| `True` | round-trip + masking テスト用 |

> `make_task_with_conversations` は §BUG-TR-002 凍結済みのため除外。Task domain に `conversations` 属性が追加される将来 PR で追加する。

`tests/factories/task.py` を本 PR で新規作成（directive-repo `tests/factories/directive.py` 同パターン）。

**raw fixture / characterization は不要**: SQLite + SQLAlchemy + Alembic + MaskingGateway はすべて標準ライブラリ仕様 / 既存 characterization 完了済みの動作で固定。

## E2E テストケース

**該当なし** — 理由:

- 本 feature は infrastructure 層単独で、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない
- Repository は内部 API（Python module-level の Protocol / Class）のみ提供
- テスト戦略ガイド §E2E対象の判断「内部 API・ライブラリなどエンドユーザー操作がない場合は結合テストで代替可」に従い、E2E は本 feature 範囲外
- 後続 `feature/task-application` / `feature/http-api` が公開 I/F を実装した時点で E2E を起票

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — infrastructure 層のため公開 I/F なし | — | — |

## 結合テストケース

「Repository 契約 + 実 SQLite + 実 Alembic + 実 MaskingGateway」を contract testing する層。M2 永続化基盤の `app_engine` / `session_factory` fixture を再利用。

### Protocol 定義 + 充足（§確定 R1-A / §確定 R1-D）<!-- 番号統一済み -->

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-UT-TR-001 | `TaskRepository` Protocol が **6 method** を宣言 | — | `application/ports/task_repository.py` がインポート可能 | `from bakufu.application.ports.task_repository import TaskRepository` | Protocol が `find_by_id` / `count` / `save(task)` / `count_by_status` / `count_by_room` / `find_blocked` の **6 method** を宣言。すべて `async def`、`@runtime_checkable` なし（empire §確定 A）|
| （TC-UT-TR-001 内）| `SqliteTaskRepository` の Protocol 充足 | `session_factory` | engine + Alembic 適用済み | `repo: TaskRepository = SqliteTaskRepository(session)` で型代入が pyright で通る | pyright strict pass。duck typing で 6 method 全 `hasattr` 確認 |
| （TC-UT-TR-001 内）| Protocol に `find_by_task_id` 等 YAGNI 拒否済み method が**存在しない** | — | — | `hasattr(TaskRepository, 'find_by_task_id')` 等 | YAGNI 拒否済み method が Protocol に宣言されていない（§確定 R1-D）|

### 基本 CRUD — save round-trip / count（§確定 R1-A / §確定 R1-B / §確定 R1-J）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-UT-TR-002 | `find_by_id` 存在 / 不在 | `session_factory` + `make_task` + `seeded_task_context` | seeded room + seeded directive | (1) `save(task)` → `find_by_id(task.id)` / (2) `find_by_id(uuid4())` | (1) 保存済み Task を返す / (2) None を返す |
| TC-UT-TR-003 | `save(task)` → `find_by_id` round-trip 全属性（§確定 R1-J）| `session_factory` + `make_task_full` + `seeded_task_context` | seeded room + seeded directive | `save(full_task)` → `find_by_id(task.id)` | 復元 Task が以下全属性と等価: `id` / `room_id` / `directive_id` / `current_stage_id` / `status` / `last_error` / `created_at`（UTC tz-aware）/ `updated_at`（UTC tz-aware）/ `assigned_agent_ids`（order_index 順）/ `deliverables`（dict[StageId, Deliverable]）/ 各 Deliverable の attachments（sha256 ASC 順）。`conversations` は §BUG-TR-002 凍結済みのため除外 |
| TC-UT-TR-004 | `count()` SQL `COUNT(*)` 契約 | `session_factory` + `make_task` + `seeded_task_context` + `before_cursor_execute` event | DB に複数 Task 保存済 | `count()` 呼び出し + SQL ログ観測 | `SELECT count(*) FROM tasks` が発行される。全行ロード経路が**ない**ことを assert |
| TC-UT-TR-009 | Tx 境界の責務分離（empire §確定 B 踏襲） | `session_factory` | seeded task context | (1) `async with session.begin(): save(task)` → 別 session で `find_by_id` / (2) `async with session: save(task)` を `begin()` なしで実行 | (1) 永続化成功（外側 UoW commit）/ (2) `find_by_id` → None（auto-commit なし）|

### save() 6 段階 DELETE+UPSERT+INSERT（§確定 R1-B）

**`test_save_child_tables.py`** — 6 段階順序の物理確認（§確定 R1-B 専用ファイル）。

| テストID | 対象 | 種別 | 前提条件 | 操作 | 期待結果 |
|---------|-----|------|---------|------|---------|
| TC-UT-TR-005 | save(task) → re-save で child table が DELETE+再INSERT される（§確定 R1-B）| 正常系 | `make_task_with_deliverables` を保存済み | deliverables を変更した task を re-save → `find_by_id` | 再 save 後の deliverables が更新済み。古い deliverable_attachments 行が残らない（DELETE CASCADE + 再 INSERT の物理確認）|
| TC-UT-TR-005b | UNIQUE(task_id, stage_id) 制約: deliverables を更新しても重複行が発生しない（§確定 R1-B 段階 1 + 5）| 正常系 | `make_task_with_deliverables` を保存済み | 同 stage_id で内容を変更した deliverable で re-save → raw SQL で deliverables 行数確認 | `SELECT COUNT(*) FROM deliverables WHERE task_id = :id` = 1。古い行が段階 1 の DELETE で先行消去済みのため UNIQUE 違反なし。body_markdown が更新済み |
| TC-UT-TR-005c | 全子テーブル空 Task → 全子有り Task への更新（段階 3〜6 全実行）| 正常系 | empty assigned_agents / deliverables の Task を保存済み | `make_task_full` に相当する Task を同 id で re-save → `find_by_id` | 全子構造が正しく存在。`task_assigned_agents` / `deliverables` / `deliverable_attachments` の行数が factory と一致。§BUG-TR-002 凍結済みのため `conversations` / `conversation_messages` は確認対象外 |

### count_by_status / count_by_room / find_blocked（§確定 R1-D / §確定 R1-H）

**`test_find_blocked.py`** — 6-method Protocol の 3 新 method 専用テストファイル。

| テストID | 対象 | 種別 | 前提条件 | 操作 | 期待結果 |
|---------|-----|------|---------|------|---------|
| TC-UT-TR-006 | `count_by_status(status)` が SQL `COUNT(*) WHERE status = :status` を発行 | 正常系 | PENDING 2件 + BLOCKED 1件を保存済み + SQL event listener | `count_by_status(TaskStatus.PENDING)` | 戻り値 = 2。SQL ログに `WHERE status =` が含まれる。全行ロード経路なし |
| TC-UT-TR-007 | `count_by_room(room_id)` が SQL `COUNT(*) WHERE room_id = :room_id` を発行 | 正常系 | 同 room に 3件、別 room に 1件を保存済み + SQL event listener | `count_by_room(seeded_room_id)` | 戻り値 = 3。SQL ログに `WHERE room_id =` が含まれる。別 room の Task が混入しない（Room スコープ分離）|
| TC-UT-TR-008 | `find_blocked()` が BLOCKED Task のみ ORDER BY updated_at DESC, id DESC で返す（§確定 R1-H）| 正常系 | BLOCKED 2件 + PENDING 1件を保存済み | `find_blocked()` | 戻り値 list に BLOCKED Task が 2件。PENDING Task が混入しない。updated_at 降順 |
| TC-UT-TR-008b | `find_blocked()` が空リストを返す（BLOCKED Task なし）| 正常系 | PENDING / DONE Task のみ | `find_blocked()` | `[]` 返却（None ではない）|
| TC-UT-TR-008c | `find_blocked()` SQL ログに `WHERE status = 'BLOCKED' ORDER BY updated_at` が含まれる | 正常系 | BLOCKED Task 1件 + event listener | `find_blocked()` | SQL ログに `status` フィルタ + `ORDER BY updated_at` が含まれる（§確定 R1-H 物理確認）|
| TC-UT-TR-008d | `find_blocked()` 戻り値 Task が全属性 _from_rows で完全復元される（§確定 R1-J）| 正常系 | BLOCKED Task（last_error 付き）を保存済み | `find_blocked()` | 戻り値 Task の全属性（id / status / last_error / room_id / directive_id 等）が保存値と等価 |
| **TC-UT-TR-008e** | `find_blocked()` id DESC tiebreaker — 同時刻 BLOCKED Task の id DESC 降順（§確定 R1-H、BUG-EMR-001 準拠）| 正常系 | 同一 `updated_at` の BLOCKED Task 3件を保存済み | `find_blocked()` | 結果の id が UUID hex 降順（`sorted(ids, key=lambda u: u.hex, reverse=True)` と一致）。tiebreaker なしだと非決定論的になる回帰検出テスト |

### 2 masking カラム物理保証（§確定 R1-E / §確定 R1-A、本 PR の核心テストファイル）

**`test_masking_fields.py`** — `tasks.last_error` / `deliverables.body_markdown` の 2 カラムに raw secret が DB に残らないことを raw SQL SELECT で byte-level 証明する。directive-repo `test_masking_text.py` のテンプレート継承。`conversation_messages.body_markdown` は §BUG-TR-002 凍結済みのため除外。

| テストID | 対象カラム | 種別 | 入力（secret を含む値）| 期待結果（DB 物理格納値）|
|---------|-----------|------|------|---------|
| TC-IT-TR-020-masking-last_error-masked | `tasks.last_error` — Discord Bot Token マスキング | 正常系 | `last_error` に Discord Bot Token を含む BLOCKED Task を save | raw SQL `SELECT last_error FROM tasks WHERE id = :id` で `<REDACTED:DISCORD_TOKEN>` を含む。raw token が残らない |
| TC-IT-TR-020-masking-last_error-plain | `tasks.last_error` — secret なし passthrough | 正常系 | `last_error` に plain text（"タスク処理失敗: timeout"）を含む Task を save | raw SQL SELECT で文字列が改変されない（masking 過剰適用なし）|
| TC-IT-TR-020-masking-last_error-roundtrip | `tasks.last_error` — 不可逆性（§確定 R1-A）| 正常系 | Discord Bot Token を含む `last_error` で save → `find_by_id` | 復元 Task の `last_error` が `<REDACTED:DISCORD_TOKEN>` を含む。raw token が `find_by_id` 経由で復元不能 |
| TC-IT-TR-020-masking-deliverable-masked | `deliverables.body_markdown` — GitHub PAT マスキング | 正常系 | `body_markdown` に `ghp_XXX...` を含む Deliverable を持つ Task を save | raw SQL `SELECT body_markdown FROM deliverables WHERE id = :id` で `<REDACTED:GITHUB_PAT>` を含む。raw PAT が残らない |
| TC-IT-TR-020-masking-deliverable-plain | `deliverables.body_markdown` — secret なし passthrough | 正常系 | `body_markdown` に plain text（"設計書を完成させた。"）を持つ Deliverable を save | raw SQL SELECT で文字列が改変されない |
| TC-IT-TR-020-masking-null-last-error | `tasks.last_error` が NULL の場合 passthrough（NULL safe）| 正常系 | `last_error=None`（PENDING Task）を save | raw SQL SELECT で `last_error` が NULL。TypeDecorator が NULL に対し安全に動作 |

> TC-IT-TR-020-masking-message-* (2 ケース) は §BUG-TR-002 凍結済みのため除外。`conversation_messages.body_markdown` の masking テストは §BUG-TR-002 解除 PR が担当する。

### Alembic 0007 + FK CASCADE + BUG-DRR-001 closure + §設計決定 TR-001（受入基準 6〜9）

**`test_alembic_task.py`** — directive-repo `test_alembic_directive.py` のテンプレート継承。

| テストID | 対象 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|-----|--------------|---------|------|---------|
| TC-IT-TR-001 | 0007 が 4 テーブルを作成（受入基準 6）| `empty_engine`（clean DB） | — | `alembic upgrade head` → `SELECT name FROM sqlite_master WHERE type='table'` | `tasks` / `task_assigned_agents` / `deliverables` / `deliverable_attachments` の 4 テーブルが存在。`conversations` / `conversation_messages` は §BUG-TR-002 凍結済みのため 0007 では作成されないことを確認 |
| TC-IT-TR-002 | 0007 が INDEX 2 件を作成（§確定 R1-K）| `empty_engine` | — | `upgrade head` → `SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tasks'` | `ix_tasks_room_id` / `ix_tasks_status_updated_id` の 2 INDEX が存在 |
| TC-IT-TR-003 | `tasks` の FK 2 件（→ rooms CASCADE / → directives CASCADE）| `empty_engine` | — | `upgrade head` → `PRAGMA foreign_key_list('tasks')` | `rooms` / `directives` への FK 2 件が存在。ON DELETE CASCADE |
| TC-IT-TR-004 | Alembic chain 0001→...→0007 が単一 head（分岐なし）| — | alembic.ini 存在 | `ScriptDirectory.get_heads()` | `len(heads) == 1`（head 分岐なし）|
| TC-IT-TR-005 | upgrade head → downgrade base → upgrade head が idempotent（受入基準 6）| `empty_engine` | — | 双方向サイクル実行 | 最終状態で 4 テーブルが存在。downgrade base 後は全テーブル消滅。再 upgrade 後に再出現 |
| TC-IT-TR-006 | `0007_task_aggregate.down_revision == "0006_directive_aggregate"` | — | alembic.ini 存在 | `ScriptDirectory.get_revision("0007_task_aggregate").down_revision` | `"0006_directive_aggregate"` と等しい（chain 一直線の物理確認）|
| TC-IT-TR-007 | `tasks.room_id` FK ON DELETE CASCADE（受入基準 7）| `empty_engine` | — | raw SQL で empire → workflow → room → directive → task を INSERT → `DELETE FROM rooms WHERE id = :id` | Task 行が CASCADE で自動削除。`SELECT * FROM tasks WHERE id = :id` が空 |
| **TC-IT-TR-008** | **BUG-DRR-001 closure: 0007 適用後に `directives.task_id → tasks.id` FK が存在する（受入基準 8）** | `empty_engine` | — | `upgrade head` → `PRAGMA foreign_key_list('directives')` | FK 参照テーブル一覧に `tasks` が**存在する**（TC-IT-DRR-006 の反転。0007 で closure 完了）|
| TC-IT-TR-009 | §設計決定 TR-001: `task_assigned_agents.agent_id` FK が 0007 時点で存在しない（受入基準 9）| `empty_engine` | — | `upgrade head` → `PRAGMA foreign_key_list('task_assigned_agents')` | FK 参照テーブル一覧に `agents` が**存在しない**（Aggregate 境界設計決定。room_members.agent_id 前例と同論理。FK closure 申し送りなし）|

### CI 三層防衛 Task 拡張（受入基準 10、§確定 R1-E）

| テストID | 対象 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|-----|--------------|---------|------|---------|
| TC-UT-TR-arch | Layer 2: `tests/architecture/test_masking_columns.py` の Task parametrize 拡張（2 カラム）| `Base.metadata` | M2 永続化基盤の arch test に masking 検証構造あり | parametrize に `("tasks", "last_error", MaskedText)` / `("deliverables", "body_markdown", MaskedText)` を追加（`conversation_messages.body_markdown` は §BUG-TR-002 凍結済みのため除外）| pass（2 カラムは MaskedText、その他カラムは masking なし）。後続 PR が誤ってカラム型を変更した瞬間に落下して PR ブロック |
| TC-DOC-TR-001 | storage.md §逆引き表 Task 行存在（受入基準 11）| repo root | `docs/architecture/domain-model/storage.md` 編集済み | `tests/docs/test_storage_md_back_index.py` で Task 行検証 | (a) `tasks.last_error: MaskedText` が §逆引き表に存在、(b) `deliverables.body_markdown: MaskedText` が存在、(c) Task 残カラム（masking 対象なし）行が存在、(d) `Conversation.messages[].body_markdown` が `feature/conversation-repository`（後続）として据え置きのまま存在する（§BUG-TR-002 凍結確認）|

### Lifecycle 統合シナリオ

| テストID | 対象 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|-----|--------------|---------|------|---------|
| TC-IT-TR-LIFECYCLE | 6 method 全経路連携 — save → find_by_id → count_by_status → find_blocked → count_by_room → save（更新）| `session_factory` + `seeded_task_context` + `make_task_full` | seeded room + seeded directive | (1) `save(pending_task)` / `save(blocked_task)` → (2) `find_by_id(pending_task.id)` → (3) `count_by_status(BLOCKED)` = 1 → (4) `find_blocked()` → blocked_task → (5) `count_by_room(room_id)` = 2 → (6) `count()` = 2 → (7) status を DONE に更新して re-save → (8) `count_by_status(BLOCKED)` = 0 / `find_blocked()` = [] | 各段階で期待値と一致。re-save 後の count / find_blocked が正しく更新される。6 method 全経路が 1 シナリオで連携 |

## ユニットテストケース

**該当なし（DB 経由の物理確認に集約）** — 理由:

- agent-repo / workflow-repo / room-repo / directive-repo と同方針: Repository 層は SQLite + Alembic + MaskingGateway の実 I/O が責務の本質
- `_to_rows` / `_from_rows` のラウンドトリップは TC-UT-TR-003 + TC-UT-TR-005 で integration として物理確認
- domain layer のテストは task feature PR #42 で完了済み（本 PR スコープ外）

## カバレッジ基準

- REQ-TR-001〜006 すべてに最低 1 件のテストケース
- **save() 6 段階**: TC-UT-TR-005 / 005b / 005c で DELETE 先行 + UPSERT + INSERT 順序・child table 完全往復・UNIQUE 制約 3 経路すべてに証拠
- **2 masking カラム（6 経路）**: TC-IT-TR-020-masking-* で `tasks.last_error` / `deliverables.body_markdown` の各カラムに masked + passthrough + roundtrip（last_error のみ）+ NULL safe を確認（§BUG-TR-002 凍結済みのため `conversation_messages.body_markdown` 除外）
- **find_blocked ORDER BY tiebreaker**: TC-UT-TR-008e で同時刻 BLOCKED Task の id DESC tiebreaker を物理確認（BUG-EMR-001 準拠回帰検出）
- **BUG-DRR-001 closure**: TC-IT-TR-008 で 0007 適用後の `PRAGMA foreign_key_list('directives')` が `tasks` 参照を含むことを確認
- **§設計決定 TR-001（Aggregate 境界）**: TC-IT-TR-009 で `task_assigned_agents.agent_id` FK が 0007 時点で存在しないことを確認
- **Alembic chain 一直線**: TC-IT-TR-006 で `0007.down_revision == "0006_directive_aggregate"` を物理確認
- **4 テーブル DDL**: TC-IT-TR-001 で 4 テーブルの存在を物理確認（§BUG-TR-002 凍結済みのため `conversations` / `conversation_messages` は 0007 に含まれないことも確認）
- **INDEX**: TC-IT-TR-002 で 2 INDEX（ix_tasks_room_id / ix_tasks_status_updated_id）の存在を物理確認
- **upgrade/downgrade idempotent**: TC-IT-TR-005 で双方向 migration を物理確認
- **CI 三層防衛**: Layer 1 grep（CI ジョブ）+ Layer 2 arch（TC-UT-TR-arch）+ Layer 3 storage.md（TC-DOC-TR-001）3 層すべてに証拠
- C0 目標: `infrastructure/persistence/sqlite/repositories/task_repository.py` で **90% 以上**（directive-repo 同水準）

## 人間が動作確認できるタイミング

本 feature は infrastructure 層単独だが、M2 永続化基盤と同じく Backend プロセスを実起動して動作確認できる。

- CI 統合後: `gh pr checks` で全ジョブ緑
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/infrastructure/persistence/sqlite/repositories/test_task_repository tests/infrastructure/persistence/sqlite/test_alembic_task.py tests/architecture/test_masking_columns.py tests/docs/test_storage_md_back_index.py -v` → 全テスト緑（5ファイル分割: test_protocol_crud / test_find_blocked / test_count_methods / test_save_child_tables / test_masking_fields）
- Backend 実起動: `cd backend && uv run python -m bakufu`（環境変数 `BAKUFU_DATA_DIR=/tmp/bakufu-test` を設定）
  - 起動時に Alembic auto-migrate で 0001〜0007 が適用されることをログで目視
  - `sqlite3 <DATA_DIR>/bakufu.db ".tables"` で 4 テーブルが存在することを目視
  - `sqlite3 <DATA_DIR>/bakufu.db "PRAGMA foreign_key_list(directives)"` で `tasks.id` への FK が存在することを目視（BUG-DRR-001 closure 確認）
  - `sqlite3 <DATA_DIR>/bakufu.db "PRAGMA foreign_key_list(task_assigned_agents)"` で `agents` への FK が存在しないことを目視（§設計決定 TR-001: Aggregate 境界設計決定の確認）
- masking 物理確認: `uv run pytest tests/.../test_masking_fields.py -v` → 6 ケース緑、raw token が DB に残らないことを目視（§BUG-TR-002 凍結済みのため conversation_messages 除外）
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.application.ports.task_repository --cov=bakufu.infrastructure.persistence.sqlite.repositories.task_repository --cov-report=term-missing` → 90% 以上

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      task.py                                         # 新規（make_task / make_task_with_agents /
                                                      #        make_task_with_deliverables / make_task_full）
                                                      # make_task_with_conversations は §BUG-TR-002 除外
    architecture/
      test_masking_columns.py                         # 既存更新: Task 2 カラム parametrize 拡張
                                                      # TC-UT-TR-arch
    infrastructure/
      persistence/
        sqlite/
          repositories/
            test_task_repository/                     # 新規ディレクトリ（5 ファイル分割）
              __init__.py
              conftest.py                              # seeded_task_context helper
                                                      # （empire + workflow + room + directive をシード）
              test_protocol_crud.py                    # TC-UT-TR-001〜004 / 009 + TC-IT-TR-LIFECYCLE
              test_find_blocked.py                     # TC-UT-TR-008 / 008b / 008c / 008d / 008e
              test_count_methods.py                    # TC-UT-TR-006 / 007（count_by_status / count_by_room SQL保証）
              test_save_child_tables.py                # TC-UT-TR-005 / 005b / 005c（6段階 save() 物理確認）
              test_masking_fields.py                   # TC-IT-TR-020-masking-* (6 ケース、2 masking カラム核心)
          test_alembic_task.py                         # TC-IT-TR-001〜009（Alembic 0007 + BUG-DRR-001 closure）
    docs/
      test_storage_md_back_index.py                    # 既存更新: Task 行検証（TC-DOC-TR-001）
```

### `conftest.py` 設計: `seeded_task_context` fixture

Task を INSERT する前に以下の FK 依存グラフを満たす必要がある:

- `tasks.room_id → rooms.id`（CASCADE）
- `tasks.directive_id → directives.id`（CASCADE）
- `directives.target_room_id → rooms.id`（CASCADE）

依存グラフ:
```
empires
  └── workflows
        └── rooms  ← tasks.room_id FK
              └── directives  ← tasks.directive_id FK
                    └── tasks  ← テスト本体が save
```

```
conftest.py 提供内容:
  - seeded_task_context: tuple[UUID, UUID]  (room_id, directive_id) fixture
    empire + workflow + room + directive を Repository 経由でシードし (room.id, directive.id) を返す
  - seed_task_context(session_factory, ...) → tuple[UUID, UUID]
    複数 room / directive が必要なテスト用 helper
```

`seed_task_context` helper は directive-repository の `seed_room` と同パターン（Repository 経由でシードし、FK 依存グラフを満たす）。

### `test_masking_fields.py` の `_read_persisted_*` helper 設計

```
_read_persisted_last_error(session_factory, task_id) -> str | None
  raw SQL: SELECT last_error FROM tasks WHERE id = :id
  directive-repo _read_persisted_text と同パターン

_read_persisted_deliverable_body(session_factory, deliverable_id) -> str
  raw SQL: SELECT body_markdown FROM deliverables WHERE id = :id
```

各 helper は TypeDecorator の `process_result_value` をバイパスし、SQLite に物理格納されたバイト列を直接取得する。これにより MaskedText の `process_bind_param`（書き込み時マスキング）が確実に機能していることを byte-level で証明する。

> `_read_persisted_message_body` は §BUG-TR-002 凍結済みのため除外。`conversation_messages` テーブルが追加される将来 PR で追加する。

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| **§BUG-TR-002** | `conversations` / `conversation_messages` テーブル + 関連テスト（`make_task_with_conversations` / TC-IT-TR-020-masking-message-* / `_read_persisted_message_body`）は YAGNI 違反凍結。Task domain が `conversations: list[Conversation]` 属性を獲得した PR で解除し、本 §BUG-TR-002 を RESOLVED に更新する | conversation-repository（未 Issue）| FROZEN — 解除条件は詳細設計 §BUG-TR-002 参照 |
| Task 後続申し送り #1 | `tasks.current_stage_id → workflow_stages.id` FK は Aggregate 境界設計決定（§確定 R1-G）により **永続的に張らない**。FK closure 申し送りなし。変更は room_members.agent_id と同様に明示的 PR review を要する | なし | Aggregate 境界として凍結済み |
| Task 後続申し送り #3 | masked `last_error` / `body_markdown` の LLM Adapter 配送経路確認 | `feature/llm-adapter`（後続）| `<REDACTED:*>` を含む body_markdown をどう扱うか（配送停止 + ログ警告）契約を凍結する責務 |
| Task 後続申し送り #4 | `find_by_room` / `find_by_directive` の YAGNI 申し送り | 後続 HTTP API Issue | ページネーション仕様が確定したタイミングで Protocol 設計変更を伴う追加 |

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-TR-001〜006 すべてに 1 件以上のテストケースがあり、特に integration が Repository 契約 + Alembic + masking 配線 + CI 三層防衛を単独でカバーしている
- [ ] **save() 6 段階**（§確定 R1-B）が TC-UT-TR-005 / 005b / 005c で DELETE 先行 + UPSERT（ON CONFLICT DO UPDATE）+ INSERT の 3 経路を物理確認
- [ ] **2 masking カラム（6 経路）**（§確定 R1-E）が TC-IT-TR-020-masking-* で `tasks.last_error` / `deliverables.body_markdown` 各カラムに raw SQL SELECT での物理確認（§BUG-TR-002 凍結済みのため `conversation_messages` 除外）
- [ ] **find_blocked ORDER BY tiebreaker**（§確定 R1-H / BUG-EMR-001 準拠）が TC-UT-TR-008e で同時刻 BLOCKED Task の id DESC tiebreaker を物理確認
- [ ] **BUG-DRR-001 closure**（§確定 R1-C）が TC-IT-TR-008 で `PRAGMA foreign_key_list('directives')` に `tasks` 参照が存在することを物理確認（TC-IT-DRR-006 の反転）
- [ ] **§設計決定 TR-001（Aggregate 境界）**が TC-IT-TR-009 で `task_assigned_agents.agent_id` FK が 0007 時点で存在しないことを物理確認（Aggregate 境界設計決定、room_members.agent_id 前例と同論理）
- [ ] **4 テーブル DDL + 2 INDEX**（REQ-TR-003）が TC-IT-TR-001 / 002 / 003 で物理確認（§BUG-TR-002 凍結済みのため `conversations` / `conversation_messages` は 0007 に含まれないことも TC-IT-TR-001 で確認）
- [ ] **Alembic chain 一直線**: TC-IT-TR-006 で `0007.down_revision == "0006_directive_aggregate"` を物理確認
- [ ] **upgrade/downgrade idempotent**: TC-IT-TR-005 で双方向 migration を物理確認
- [ ] **CI 三層防衛**（§確定 R1-E）: Layer 1 grep（CI）+ Layer 2 arch（TC-UT-TR-arch）+ Layer 3 storage.md（TC-DOC-TR-001）の 3 つすべてに証拠
- [ ] **TypeDecorator 信頼**（§確定 R1-A）: TC-UT-TR-003 で UUIDStr 二重ラップなし / MaskedText 手動 mask なしの round-trip を確認
- [ ] **_from_rows 全子構造**（§確定 R1-J）: TC-UT-TR-003 で assigned_agent_ids（order_index順）/ deliverables（dict）/ attachments（sha256 順）の復元順序が §確定 R1-H と一致（§BUG-TR-002 凍結済みのため `conversations` / `messages` 除外）
- [ ] **save(task) 1 引数 + UPSERT セマンティクス**（empire §確定 A テンプレート継承、§確定 R1-B）: TC-UT-TR-005 で UPSERT の ON CONFLICT DO UPDATE + child table DELETE+re-INSERT を確認
- [ ] **テストファイル分割（5 ファイル: test_protocol_crud / test_find_blocked / test_count_methods / test_save_child_tables / test_masking_fields）が basic-design.md §モジュール構成と整合**
- [ ] §設計決定 TR-001（Aggregate 境界、FK closure 申し送りなし）が detailed-design.md §Known Issues に明記されている
- [ ] 受入基準 1〜9 すべてにテストケースがある
