# 詳細設計書

> feature: `task-repository`
> 関連: [basic-design.md](basic-design.md) / [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源** / [`docs/features/directive-repository/`](../directive-repository/) **直近テンプレート** / [`docs/features/task/`](../task/)

## 記述ルール（必ず守ること）

詳細設計に**疑似コード・サンプル実装（python/ts/sh/yaml 等の言語コードブロック）を書かない**。
ソースコードと二重管理になりメンテナンスコストしか生まない。
必要なのは「構造契約（属性名・型・制約）」と「確定文言（メッセージ文字列）」と「実装の意図」。

## クラス設計（詳細）

### `TaskRepository` Protocol

| method | シグネチャ | 戻り値 | 制約 |
|--------|---------|-------|------|
| `find_by_id` | `(task_id: TaskId) -> Task \| None` | `Task`（存在時）/ `None`（不在時） | async def |
| `count` | `() -> int` | `int`（全件数） | async def |
| `save` | `(task: Task) -> None` | `None` | async def、§確定 R1-B 9 段階実行 |
| `count_by_status` | `(status: TaskStatus) -> int` | `int`（ステータス別件数） | async def |
| `count_by_room` | `(room_id: RoomId) -> int` | `int`（Room 別件数） | async def |
| `find_blocked` | `() -> list[Task]` | `list[Task]`（空の場合 `[]`） | async def、ORDER BY updated_at DESC, id DESC |

### `SqliteTaskRepository`

| 属性 | 型 | 意図 |
|-----|----|----|
| `_session` | `AsyncSession` | コンストラクタ引数（依存性注入） |

| method | シグネチャ | 戻り値 | 処理の要点 |
|--------|---------|-------|-----------|
| `find_by_id` | `(task_id: TaskId) -> Task \| None` | `Task \| None` | tasks 1 行 SELECT → 不在は None。存在すれば 5 子テーブルを個別 SELECT（§確定 R1-H ORDER BY 各テーブル適用）→ `_from_rows()` |
| `count` | `() -> int` | `int` | `select(func.count()).select_from(TaskRow)` |
| `save` | `(task: Task) -> None` | `None` | `_to_rows()` → §確定 R1-B 9 段階 DELETE+UPSERT+INSERT |
| `count_by_status` | `(status: TaskStatus) -> int` | `int` | `SELECT COUNT(*) FROM tasks WHERE status = :status` |
| `count_by_room` | `(room_id: RoomId) -> int` | `int` | `SELECT COUNT(*) FROM tasks WHERE room_id = :room_id` |
| `find_blocked` | `() -> list[Task]` | `list[Task]` | `SELECT * FROM tasks WHERE status = 'BLOCKED' ORDER BY updated_at DESC, id DESC` → 各行で `find_by_id` 相当の子テーブル取得 → `_from_rows()` |
| `_to_rows` | `(task: Task) -> tuple[TaskRow, list[AssignedAgentRow], list[ConversationRow], list[MessageRow], list[DeliverableRow], list[AttachmentRow]]` | 6 種 Row の tuple | TypeDecorator 信頼（UUIDStr/MaskedText 二重変換しない、§確定 R1-A） |
| `_from_rows` | `(task_row, agent_rows, conv_rows, msg_rows, deliv_rows, attach_rows) -> Task` | `Task` | TypeDecorator 信頼。`TaskId(task_row.id)` のように直接構築（UUID 二重ラップしない） |

## 確定事項（先送り撤廃）

### §確定 A: TypeDecorator 信頼の徹底（Rams 指摘 R1 directive-repository v2 凍結の継承）

`UUIDStr` TypeDecorator は SELECT 時に `UUID` インスタンスを返す（SQLAlchemy TypeDecorator の `process_result_value` で変換済み）。`_from_rows()` 内で `TaskId(UUID(row.id))` と二重ラップせず、`TaskId(row.id)` で直接 `AgentId` 型に渡す。

`MaskedText` TypeDecorator は INSERT 時に `process_bind_param` でマスキング済み値を bind parameter に渡す。`_to_rows()` 内で `MaskingGateway.mask()` を手動呼び出しせず、TypeDecorator に委ねる（責務の重複排除）。

### §確定 B: save() 9 段階の順序と SQLite FK 整合性

§確定 R1-B で定義した 9 段階を詳細凍結する:

| 段階 | SQL 操作 | 対象 | 留意点 |
|------|---------|------|-------|
| 1 | `DELETE FROM deliverables WHERE task_id = :id` | deliverables + CASCADE | deliverable_attachments は CASCADE で自動削除。明示 DELETE 不要 |
| 2 | `DELETE FROM conversations WHERE task_id = :id` | conversations + CASCADE | conversation_messages は CASCADE で自動削除。明示 DELETE 不要 |
| 3 | `DELETE FROM task_assigned_agents WHERE task_id = :id` | task_assigned_agents | FK CASCADE 先がない。直接 DELETE |
| 4 | `INSERT OR REPLACE INTO tasks ...` | tasks（UPSERT） | `ON CONFLICT id DO UPDATE` でも可（SQLAlchemy merge() 相当）。新規・更新両対応 |
| 5 | `INSERT INTO task_assigned_agents ...` | 各 AgentId | order_index は Aggregate の `assigned_agent_ids` リスト添字（0-indexed） |
| 6 | `INSERT INTO conversations ...` | 各 Conversation | task_id FK が段階 4 で確定済みのため FK 制約通過 |
| 7 | `INSERT INTO conversation_messages ...` | 各 Message（Conversation ごと） | conversation_id FK が段階 6 で確定済みのため FK 制約通過 |
| 8 | `INSERT INTO deliverables ...` | 各 Deliverable | task_id FK が段階 4 で確定済み。`UNIQUE(task_id, stage_id)` は段階 1 の DELETE で先行クリア済みのため通過 |
| 9 | `INSERT INTO deliverable_attachments ...` | 各 Attachment（Deliverable ごと） | deliverable_id FK が段階 8 で確定済み |

**段階 4 の UPSERT を DELETE 前に行わない理由**: FK CASCADE により tasks 行削除が 5 子テーブルを連鎖削除する。tasks UPSERT を先に行うと新行 insert → 旧行 delete ができず UNIQUE PK 制約で衝突する（`INSERT OR REPLACE` は旧行を delete + 新行 insert の 2 ステップ）。よって子テーブルを先に DELETE してから tasks UPSERT が正しい順序。

### §確定 C: BUG-DRR-001 closure の実装詳細（`directives.task_id → tasks.id` FK）

`0007_task_aggregate.py` の `upgrade()` 末尾に追記する:

| 操作 | 内容 |
|------|------|
| batch_alter_table | `with op.batch_alter_table('directives', schema=None) as batch_op:` |
| FK 追加 | `batch_op.create_foreign_key('fk_directives_task_id', 'tasks', ['task_id'], ['id'], ondelete='RESTRICT')` |
| downgrade 対応 | `with op.batch_alter_table('directives', schema=None) as batch_op: batch_op.drop_constraint('fk_directives_task_id', type_='foreignkey')` |

**ON DELETE RESTRICT の意図**: `directives.task_id` が指す Task が削除される前に、application 層が必ず `directive.unlink_task()` + `save()` を呼ぶ責務を強制する。RESTRICT は参照整合性違反を「明示的な Fail Fast」として扱い、サイレントな null 化（ON DELETE SET NULL）や連鎖削除（ON DELETE CASCADE）より intent が明確（Fail Fast 原則）。

**batch_alter_table が必要な理由**: SQLite は `ALTER TABLE ADD CONSTRAINT FOREIGN KEY` を未サポート（[SQLite ALTER TABLE 公式ドキュメント](https://www.sqlite.org/lang_altertable.html)）。Alembic の `batch_alter_table` は内部でテーブルを再作成（TEMP テーブル → COPY → DROP → RENAME）することで制約変更を実現する。room-repository PR #47 BUG-EMR-001 closure と同パターン。

### §確定 D: `_from_rows` の子構造再組み立て（Task Aggregate 復元の詳細）

Task Aggregate 復元時の `_from_rows()` 処理の確定ルール:

| 子構造 | 再組み立て方法 | 根拠 |
|-------|-------------|------|
| `assigned_agent_ids: list[AgentId]` | `agent_rows` を `order_index ASC` でソート済みで受け取り、`[AgentId(r.agent_id) for r in agent_rows]` | §確定 R1-H の ORDER BY 保証でリスト順序が Aggregate と一致 |
| `deliverables: dict[StageId, Deliverable]` | `{StageId(r.stage_id): _row_to_deliverable(r, attach_rows_for(r.id)) for r in deliv_rows}` | UNIQUE(task_id, stage_id) 制約により dict key 衝突なし |
| `conversations: list[Conversation]` | `conv_rows` を `created_at ASC, id ASC` でソート済みで受け取り、各 `conv_id` に対応する `msg_rows` をフィルタして `Conversation` 再組み立て | §確定 R1-H の ORDER BY 保証 |

### §確定 E: CI 三層防衛の詳細実装仕様

#### Layer 1: `check_masking_columns.sh` 追加エントリ

`PARTIAL_MASK_FILES` 配列に以下を追加（正のチェック: MaskedText 必須）:

| エントリ | チェック対象 |
|---------|------------|
| `"tables/tasks.py:last_error:MaskedText"` | `tasks.last_error` の `MaskedText` 必須 |
| `"tables/conversation_messages.py:body_markdown:MaskedText"` | `conversation_messages.body_markdown` の `MaskedText` 必須 |
| `"tables/deliverables.py:body_markdown:MaskedText"` | `deliverables.body_markdown` の `MaskedText` 必須 |

負のチェック（過剰マスキング防止）: 各テーブルファイルで上記以外のカラムに `MaskedText` / `MaskedJSONEncoded` が登場しないことも assert する（directive-repository §確定 E パターン継承）。

#### Layer 2: `test_masking_columns.py` 追加 parametrize

```
parametrize に追加する 3 行:
  ("tasks", "last_error", MaskedText)
  ("conversation_messages", "body_markdown", MaskedText)
  ("deliverables", "body_markdown", MaskedText)
```

各パラメータについて `column.type.__class__ is MaskedText` を assert する。

#### Layer 3: storage.md 逆引き表（§確定 R1-F で実施）

`docs/architecture/domain-model/storage.md` §逆引き表の更新は REQ-TR-005 で実施済み（本 PR 設計書と同一コミット）。

### §確定 F: INDEX 設計の根拠

| INDEX | 対象カラム | 種別 | 根拠 |
|------|-----------|------|------|
| `ix_tasks_status` | `tasks.status` | 非 UNIQUE | `count_by_status` / `find_blocked` の WHERE status フィルタを最適化 |
| `ix_tasks_room_id` | `tasks.room_id` | 非 UNIQUE | `count_by_room` の WHERE room_id フィルタを最適化 |
| `ix_tasks_updated_at_id` | `(tasks.updated_at, tasks.id)` | 非 UNIQUE | `find_blocked` の `ORDER BY updated_at DESC, id DESC` を最適化（BUG-EMR-001 tiebreaker 込み複合 INDEX） |

**INDEX を張らない判断（YAGNI）**:
- `tasks.directive_id`: 1 Task につき 1 Directive（1:1 相当）のため低選択性。INDEX 効果薄。後続 HTTP API で必要になったら追加
- `conversations.task_id`: `find_by_id` 内の子テーブル SELECT で 1 task_id による 1 クエリ。テーブルサイズが巨大になるまで INDEX 不要
- その他子テーブルの FK カラム: 同様の理由で保留

## データ構造（永続化キー）

### `tasks` テーブル

| カラム | 型 | 制約 | 意図 |
|-------|----|----|----|
| `id` | `UUIDStr` | PK, NOT NULL | TaskId（UUIDv4） |
| `room_id` | `UUIDStr` | FK → `rooms.id` ON DELETE **CASCADE**, NOT NULL | 所属 Room |
| `directive_id` | `UUIDStr` | FK → `directives.id` ON DELETE **CASCADE**, NOT NULL | 起点 Directive |
| `current_stage_id` | `UUIDStr` | NOT NULL（**FK なし** — §確定 R1-G 循環参照問題） | 現 Stage（Workflow §確定 J 同方針） |
| `status` | `String(32)` | NOT NULL | TaskStatus 6 値（PENDING / IN_PROGRESS / AWAITING_EXTERNAL_REVIEW / BLOCKED / DONE / CANCELLED） |
| `last_error` | **`MaskedText`** | NULL | BLOCKED 隔離理由（LLM エラーメッセージ。secret 混入の可能性 → masking 必須） |
| `created_at` | `DateTime(timezone=True)` | NOT NULL | UTC 起票時刻 |
| `updated_at` | `DateTime(timezone=True)` | NOT NULL | UTC 最終更新時刻 |

**masking 対象カラム**: `tasks.last_error` のみ（MaskedText）。その他 7 カラムは masking 対象なし。

### `task_assigned_agents` テーブル

| カラム | 型 | 制約 | 意図 |
|-------|----|----|----|
| `task_id` | `UUIDStr` | FK → `tasks.id` ON DELETE **CASCADE**, NOT NULL | 親 Task |
| `agent_id` | `UUIDStr` | NOT NULL（**FK なし** — Aggregate 境界） | AgentId（参照のみ） |
| `order_index` | `Integer` | NOT NULL | `assigned_agent_ids` リスト順（0-indexed）。ORDER BY で復元順序保証 |
| UNIQUE | `(task_id, agent_id)` | — | 重複割り当て防止 |

### `conversations` テーブル

| カラム | 型 | 制約 | 意図 |
|-------|----|----|----|
| `id` | `UUIDStr` | PK, NOT NULL | ConversationId（UUIDv4） |
| `task_id` | `UUIDStr` | FK → `tasks.id` ON DELETE **CASCADE**, NOT NULL | 親 Task |
| `created_at` | `DateTime(timezone=True)` | NOT NULL | UTC 会話開始時刻（ORDER BY 基準） |

### `conversation_messages` テーブル

| カラム | 型 | 制約 | 意図 |
|-------|----|----|----|
| `id` | `UUIDStr` | PK, NOT NULL | MessageId（UUIDv4） |
| `conversation_id` | `UUIDStr` | FK → `conversations.id` ON DELETE **CASCADE**, NOT NULL | 親 Conversation |
| `speaker_kind` | `String(32)` | NOT NULL | 発話者種別（'AGENT' / 'SYSTEM' / 'USER' 等） |
| `body_markdown` | **`MaskedText`** | NOT NULL | メッセージ本文（subprocess 出力を含む可能性 → masking 必須） |
| `timestamp` | `DateTime(timezone=True)` | NOT NULL | UTC 発話時刻（ORDER BY 基準） |

**masking 対象カラム**: `body_markdown` のみ（MaskedText）。

### `deliverables` テーブル

| カラム | 型 | 制約 | 意図 |
|-------|----|----|----|
| `id` | `UUIDStr` | PK, NOT NULL | DeliverableId（UUIDv4）。Aggregate は `stage_id` で一意管理だが永続化には PK が必要 |
| `task_id` | `UUIDStr` | FK → `tasks.id` ON DELETE **CASCADE**, NOT NULL | 親 Task |
| `stage_id` | `UUIDStr` | NOT NULL（**FK なし** — §確定 R1-G workflow 循環参照問題） | 対象 Stage |
| `body_markdown` | **`MaskedText`** | NOT NULL | 成果物本文（Agent 出力を含む → masking 必須） |
| `committed_by` | `UUIDStr` | NOT NULL（**FK なし** — Aggregate 境界） | コミットした AgentId |
| `committed_at` | `DateTime(timezone=True)` | NOT NULL | UTC コミット時刻 |
| UNIQUE | `(task_id, stage_id)` | — | Stage 単位の最新 Deliverable 保証（Aggregate の `deliverables: dict[StageId, Deliverable]` に対応） |

**masking 対象カラム**: `body_markdown` のみ（MaskedText）。

### `deliverable_attachments` テーブル

| カラム | 型 | 制約 | 意図 |
|-------|----|----|----|
| `id` | `UUIDStr` | PK, NOT NULL | AttachmentId（UUIDv4） |
| `deliverable_id` | `UUIDStr` | FK → `deliverables.id` ON DELETE **CASCADE**, NOT NULL | 親 Deliverable |
| `sha256` | `String(64)` | NOT NULL（`^[a-f0-9]{64}$`）| ファイル内容ハッシュ（storage.md §filename サニタイズ規則で lowercase hex 64 文字検証済み） |
| `filename` | `String(255)` | NOT NULL | サニタイズ済みファイル名（Attachment VO の 6 段階検査済み） |
| `mime_type` | `String(128)` | NOT NULL | MIME 種別（ホワイトリスト 7 種、Attachment VO で検証済み） |
| `size_bytes` | `Integer` | NOT NULL（0 ≤ x ≤ 10485760） | ファイルサイズ（Attachment VO で検証済み） |

**masking 対象カラム**: なし（全カラム masking 対象外）。

### `0007_task_aggregate.py`（Alembic revision 構造）

| 操作 | 内容 |
|---|---|
| `upgrade()` — tasks | `op.create_table('tasks', ...)` + 3 INDEX（ix_tasks_status / ix_tasks_room_id / ix_tasks_updated_at_id） |
| `upgrade()` — 子テーブル | `op.create_table('task_assigned_agents', ...)` / `op.create_table('conversations', ...)` / `op.create_table('conversation_messages', ...)` / `op.create_table('deliverables', ...)` / `op.create_table('deliverable_attachments', ...)` |
| `upgrade()` — BUG-DRR-001 | `op.batch_alter_table('directives')` → `create_foreign_key('fk_directives_task_id', 'tasks', ['task_id'], ['id'], ondelete='RESTRICT')` |
| `downgrade()` | BUG-DRR-001 FK drop → 子テーブル 5 本 drop → tasks drop（CASCADE FK により子が先に消える）|
| `revision` | `"0007_task_aggregate"` |
| `down_revision` | `"0006_directive_aggregate"` |

## API エンドポイント詳細

該当なし — 理由: 本 feature は infrastructure 層のみ。API は `feature/http-api` で凍結する。

## §Known Issues

### §BUG-TR-001: `task_assigned_agents.agent_id` / `deliverables.committed_by` / `conversations` FK 未追加

| 項目 | 内容 |
|---|---|
| 状態 | **OPEN（申し送り中）** |
| 内容 | `task_assigned_agents.agent_id → agents.id` / `deliverables.committed_by → agents.id` FK は 0007 で張らない。`agents` テーブルは agent-repository（後続 Issue #32）で追加予定だが、task-repository と agent-repository のどちらが先にマージされるかに依存する forward reference 問題 |
| 対策（現状）| application 層 `TaskService.assign()` が `AgentRepository.find_by_id(agent_id)` で存在確認 |
| closure 責務 | agent-repository PR マージ後、`feature/task-agent-fk-closure`（未 Issue）で `op.batch_alter_table('task_assigned_agents')` / `op.batch_alter_table('deliverables')` 経由で FK 追加。BUG-DRR-001 / BUG-EMR-001 と同パターン |

## 出典・参考

- [SQLite — ALTER TABLE](https://www.sqlite.org/lang_altertable.html) — batch_alter_table の必要性（SQLite は ALTER TABLE ADD CONSTRAINT 非サポート）
- [SQLite — Foreign Key Actions](https://www.sqlite.org/foreignkeys.html#fk_actions) — CASCADE / RESTRICT 挙動の確認
- [SQLAlchemy 2.x — ORM Declarative Mapping](https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html) — DeclarativeBase / mapped_column の仕様
- [SQLAlchemy 2.x — Custom Types (TypeDecorator)](https://docs.sqlalchemy.org/en/20/core/custom_types.html#sqlalchemy.types.TypeDecorator) — `MaskedText` の TypeDecorator 配線方式
- [SQLAlchemy 2.x — DateTime type](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.DateTime) — timezone=True の挙動
- [Alembic — batch_alter_table](https://alembic.sqlalchemy.org/en/latest/batch.html) — SQLite 向け ALTER TABLE / FK 追加方法
- [`docs/features/empire-repository/detailed-design.md`](../empire-repository/detailed-design.md) §確定 A〜F — テンプレート真実源
- [`docs/features/directive-repository/detailed-design.md`](../directive-repository/detailed-design.md) — 直近テンプレート（§確定 R1-A〜E、BUG-DRR-001 申し送り元）
- [`docs/features/task/detailed-design.md`](../task/detailed-design.md) — Task Aggregate 凍結済み設計（§確定 A〜I）
- [`docs/architecture/domain-model/storage.md`](../../architecture/domain-model/storage.md) §シークレットマスキング規則 — MaskedText 配線方式と CI 三層防衛の根拠
