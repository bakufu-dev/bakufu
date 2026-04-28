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
| `save` | `(task: Task) -> None` | `None` | async def、§確定 R1-B 6 段階実行（詳細設計 §確定 R1-B で凍結） |
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
| `save` | `(task: Task) -> None` | `None` | `_to_rows()` → §確定 R1-B 6 段階 DELETE+UPSERT+INSERT |
| `count_by_status` | `(status: TaskStatus) -> int` | `int` | `SELECT COUNT(*) FROM tasks WHERE status = :status` |
| `count_by_room` | `(room_id: RoomId) -> int` | `int` | `SELECT COUNT(*) FROM tasks WHERE room_id = :room_id` |
| `find_blocked` | `() -> list[Task]` | `list[Task]` | `SELECT * FROM tasks WHERE status = 'BLOCKED' ORDER BY updated_at DESC, id DESC` → 各行で `find_by_id` 相当の子テーブル取得 → `_from_rows()` |
| `_to_rows` | `(task: Task) -> tuple[TaskRow, list[AssignedAgentRow], list[DeliverableRow], list[AttachmentRow]]` | 4 種 Row の tuple | TypeDecorator 信頼（UUIDStr/MaskedText 二重変換しない、§確定 R1-A 詳細）。`conversations` 関連 Row は §BUG-TR-002 凍結済みのため除外 |
| `_from_rows` | `(task_row, agent_rows, deliv_rows, attach_rows) -> Task` | `Task` | TypeDecorator 信頼。`TaskId(task_row.id)` のように直接構築（UUID 二重ラップしない）。`conversations` 再組み立ては §BUG-TR-002 凍結済みのため除外 |

## 確定事項（先送り撤廃）

### §確定 R1-A: TypeDecorator 信頼の徹底（Rams 指摘 R1 directive-repository v2 凍結の継承）

`UUIDStr` TypeDecorator は SELECT 時に `UUID` インスタンスを返す（SQLAlchemy TypeDecorator の `process_result_value` で変換済み）。`_from_rows()` 内で `TaskId(UUID(row.id))` と二重ラップせず、`TaskId(row.id)` で直接 `AgentId` 型に渡す。

`MaskedText` TypeDecorator は INSERT 時に `process_bind_param` でマスキング済み値を bind parameter に渡す。`_to_rows()` 内で `MaskingGateway.mask()` を手動呼び出しせず、TypeDecorator に委ねる（責務の重複排除）。

### §確定 R1-B: save() 6 段階の順序と SQLite FK 整合性

§確定 R1-B で定義した 6 段階を詳細凍結する（`conversations` / `conversation_messages` は §BUG-TR-002 凍結済みのため除外）:

| 段階 | SQL 操作 | 対象 | 留意点 |
|------|---------|------|-------|
| 1 | `DELETE FROM deliverables WHERE task_id = :id` | deliverables + CASCADE | deliverable_attachments は CASCADE で自動削除。明示 DELETE 不要 |
| 2 | `DELETE FROM task_assigned_agents WHERE task_id = :id` | task_assigned_agents | FK CASCADE 先がない。直接 DELETE |
| 3 | `INSERT ... ON CONFLICT (id) DO UPDATE SET ...` | tasks（UPSERT） | SQLAlchemy `sqlite_insert(...).on_conflict_do_update(...)` で既存 tasks 行を UPDATE する（empire / room / directive-repository の既存実装パターンと一致）。新規・更新両対応 |
| 4 | `INSERT INTO task_assigned_agents ...` | 各 AgentId | order_index は Aggregate の `assigned_agent_ids` リスト添字（0-indexed） |
| 5 | `INSERT INTO deliverables ...` | 各 Deliverable | task_id FK が段階 3 で確定済み。`UNIQUE(task_id, stage_id)` は段階 1 の DELETE で先行クリア済みのため通過 |
| 6 | `INSERT INTO deliverable_attachments ...` | 各 Attachment（Deliverable ごと） | deliverable_id FK が段階 5 で確定済み |

**段階 3 の UPSERT を DELETE 前に行わない理由**: `ON CONFLICT DO UPDATE` は既存行を IN-PLACE 更新するため tasks 行そのものは残り、段階 1〜2 の DELETE が済んでいれば子テーブルへの CASCADE 削除は発生しない。しかし UPSERT を先に行うと `UNIQUE(task_id, stage_id)` 等の制約で INSERT 段階 5 が衝突する可能性がある（段階 1 の DELETE で先行クリアしてから INSERT するのが正しい順序）。

### §確定 R1-C: BUG-DRR-001 closure の実装詳細（`directives.task_id → tasks.id` FK）

`0007_task_aggregate.py` の `upgrade()` 末尾に追記する:

| 操作 | 内容 |
|------|------|
| batch_alter_table | `with op.batch_alter_table('directives', schema=None) as batch_op:` |
| FK 追加 | `batch_op.create_foreign_key('fk_directives_task_id', 'tasks', ['task_id'], ['id'], ondelete='RESTRICT')` |
| downgrade 対応 | `with op.batch_alter_table('directives', schema=None) as batch_op: batch_op.drop_constraint('fk_directives_task_id', type_='foreignkey')` |

**ON DELETE RESTRICT の意図**: `directives.task_id` が指す Task が削除される前に、application 層が必ず `directive.unlink_task()` + `save()` を呼ぶ責務を強制する。RESTRICT は参照整合性違反を「明示的な Fail Fast」として扱い、サイレントな null 化（ON DELETE SET NULL）や連鎖削除（ON DELETE CASCADE）より intent が明確（Fail Fast 原則）。

**batch_alter_table が必要な理由**: SQLite は `ALTER TABLE ADD CONSTRAINT FOREIGN KEY` を未サポート（[SQLite ALTER TABLE 公式ドキュメント](https://www.sqlite.org/lang_altertable.html)）。Alembic の `batch_alter_table` は内部でテーブルを再作成（TEMP テーブル → COPY → DROP → RENAME）することで制約変更を実現する。room-repository PR #47 BUG-EMR-001 closure と同パターン。

### §確定 R1-J: `_from_rows` の子構造再組み立て（Task Aggregate 復元の詳細）

Task Aggregate 復元時の `_from_rows()` 処理の確定ルール:

| 子構造 | 再組み立て方法 | 根拠 |
|-------|-------------|------|
| `assigned_agent_ids: list[AgentId]` | `agent_rows` を `order_index ASC` でソート済みで受け取り、`[AgentId(r.agent_id) for r in agent_rows]` | §確定 R1-H の ORDER BY 保証でリスト順序が Aggregate と一致 |
| `deliverables: dict[StageId, Deliverable]` | `{StageId(r.stage_id): _row_to_deliverable(r, attach_rows_for(r.id)) for r in deliv_rows}` | UNIQUE(task_id, stage_id) 制約により dict key 衝突なし |

> `conversations: list[Conversation]` の再組み立ては **§BUG-TR-002 凍結済みのため除外**。Task domain が `conversations` 属性を獲得した将来 PR で本表に追記する。

### §確定 R1-E: CI 三層防衛の詳細実装仕様

#### Layer 1: `check_masking_columns.sh` 追加エントリ

`PARTIAL_MASK_FILES` 配列に以下を追加（正のチェック: MaskedText 必須）:

| エントリ | チェック対象 |
|---------|------------|
| `"tables/tasks.py:last_error:MaskedText"` | `tasks.last_error` の `MaskedText` 必須 |
| `"tables/deliverables.py:body_markdown:MaskedText"` | `deliverables.body_markdown` の `MaskedText` 必須 |

`conversation_messages.body_markdown` は §BUG-TR-002 凍結済みのため除外。将来追加時に `"tables/conversation_messages.py:body_markdown:MaskedText"` を追記する。

負のチェック（過剰マスキング防止）: 各テーブルファイルで上記以外のカラムに `MaskedText` / `MaskedJSONEncoded` が登場しないことも assert する（directive-repository §確定 E パターン継承）。

#### Layer 2: `test_masking_columns.py` 追加 parametrize

```
parametrize に追加する 2 行:
  ("tasks", "last_error", MaskedText)
  ("deliverables", "body_markdown", MaskedText)
```

`("conversation_messages", "body_markdown", MaskedText)` は §BUG-TR-002 凍結済みのため除外。各パラメータについて `column.type.__class__ is MaskedText` を assert する。

#### Layer 3: storage.md 逆引き表（§確定 R1-F で実施）

`docs/architecture/domain-model/storage.md` §逆引き表の更新は REQ-TR-005 で実施済み（本 PR 設計書と同一コミット）。

### §確定 R1-K: INDEX 設計の根拠

| INDEX | 対象カラム | 種別 | 根拠 |
|------|-----------|------|------|
| `ix_tasks_room_id` | `tasks.room_id` | 非 UNIQUE | `count_by_room` の WHERE room_id フィルタを最適化 |
| `ix_tasks_status_updated_id` | `(tasks.status, tasks.updated_at, tasks.id)` | 非 UNIQUE | `find_blocked` の `WHERE status = 'BLOCKED' ORDER BY updated_at DESC, id DESC` を WHERE + ORDER BY 一括最適化（status フィルタで先絞り → updated_at / id で決定論的ソート。`ix_tasks_status` 単独では ORDER BY が最適化されず、`ix_tasks_updated_at_id` 単独では WHERE status が効かない。複合 INDEX で両方をカバー） |

**採用根拠の詳細 — `ix_tasks_status_updated_id` の 3 カラム複合 INDEX**:

`find_blocked` クエリは `WHERE status = 'BLOCKED' ORDER BY updated_at DESC, id DESC` の構造を持つ。単純な `(updated_at, id)` INDEX は WHERE status フィルタに効かない（Halsenberg 指摘 R4）。`(status)` 単独 INDEX はフィルタには効くが ORDER BY ソートが最適化されない。複合 INDEX `(status, updated_at, id)` は WHERE 等価一致（status）→ 範囲ソート（updated_at, id）を一つの B-tree で処理し、`count_by_status` も同 INDEX の prefix `(status)` で効く。

**INDEX を張らない判断（YAGNI）**:
- `tasks.status` 単体 INDEX: 廃止。`ix_tasks_status_updated_id` の prefix `(status)` で `count_by_status` も最適化されるため単体 INDEX は冗長
- `tasks.directive_id`: 1 Task につき 1 Directive（1:1 相当）のため低選択性。INDEX 効果薄
- `conversations.task_id`: `find_by_id` 内の子テーブル SELECT で 1 task_id による 1 クエリ。テーブルサイズが巨大になるまで INDEX 不要
- その他子テーブルの FK カラム: 同様の理由で保留

## データ構造（永続化キー）

### `tasks` テーブル

| カラム | 型 | 制約 | 意図 |
|-------|----|----|----|
| `id` | `UUIDStr` | PK, NOT NULL | TaskId（UUIDv4） |
| `room_id` | `UUIDStr` | FK → `rooms.id` ON DELETE **CASCADE**, NOT NULL | 所属 Room |
| `directive_id` | `UUIDStr` | FK → `directives.id` ON DELETE **CASCADE**, NOT NULL | 起点 Directive |
| `current_stage_id` | `UUIDStr` | NOT NULL（**FK なし** — §確定 R1-G: Workflow Aggregate 境界、存在検証は application 層責務） | 現 Stage（Workflow §確定 J 同方針） |
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

### `deliverables` テーブル

| カラム | 型 | 制約 | 意図 |
|-------|----|----|----|
| `id` | `UUIDStr` | PK, NOT NULL | **内部識別子。save() ごとに uuid4() で再生成される（DELETE-then-INSERT パターン）。外部参照禁止。** ビジネスナチュラルキーは `UNIQUE(task_id, stage_id)` を使うこと |
| `task_id` | `UUIDStr` | FK → `tasks.id` ON DELETE **CASCADE**, NOT NULL | 親 Task |
| `stage_id` | `UUIDStr` | NOT NULL（**FK なし** — §確定 R1-G: Workflow Aggregate 境界、存在検証は application 層責務） | 対象 Stage |
| `body_markdown` | **`MaskedText`** | NOT NULL | 成果物本文（Agent 出力を含む → masking 必須） |
| `committed_by` | `UUIDStr` | NOT NULL（**FK なし** — Aggregate 境界） | コミットした AgentId |
| `committed_at` | `DateTime(timezone=True)` | NOT NULL | UTC コミット時刻 |
| UNIQUE | `(task_id, stage_id)` | — | Stage 単位の最新 Deliverable 保証（Aggregate の `deliverables: dict[StageId, Deliverable]` に対応）。**外部から Deliverable を参照する場合はこの複合キーを使う** |

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
| `upgrade()` — tasks | `op.create_table('tasks', ...)` + 2 INDEX（ix_tasks_room_id / ix_tasks_status_updated_id） |
| `upgrade()` — 子テーブル | `op.create_table('task_assigned_agents', ...)` / `op.create_table('deliverables', ...)` / `op.create_table('deliverable_attachments', ...)` （`conversations` / `conversation_messages` は §BUG-TR-002 凍結済みのため除外）|
| `upgrade()` — BUG-DRR-001 | `op.batch_alter_table('directives')` → `create_foreign_key('fk_directives_task_id', 'tasks', ['task_id'], ['id'], ondelete='RESTRICT')` |
| `downgrade()` | BUG-DRR-001 FK drop → 子テーブル 3 本 drop → tasks drop（CASCADE FK により子が先に消える）|
| `revision` | `"0007_task_aggregate"` |
| `down_revision` | `"0006_directive_aggregate"` |

## API エンドポイント詳細

該当なし — 理由: 本 feature は infrastructure 層のみ。API は `feature/http-api` で凍結する。

## §Known Issues

### §BUG-TR-002: `conversations` / `conversation_messages` テーブル — YAGNI 違反凍結（申し送り）

| 項目 | 内容 |
|---|---|
| 状態 | **FROZEN（申し送り凍結）** |
| 内容 | `conversations` / `conversation_messages` テーブルは Alembic 0007 で誤って先行作成されたが、Task Aggregate（PR #42）は現時点で `conversations: list[Conversation]` 属性を持たない。YAGNI 違反として本 PR より削除する |
| 影響 | `conversations.py` / `conversation_messages.py` ORM ファイルは本 PR でリポジトリから削除。`_to_rows()` / `_from_rows()` に conversations 関連引数なし。`check_masking_columns.sh` / `test_masking_columns.py` に `conversation_messages.body_markdown` エントリなし |
| 解除条件 | Task domain PR で `Task.conversations: list[Conversation]` 属性が追加された時点でフリーズ解除。その PR が本 §BUG-TR-002 を RESOLVED に更新し、0008 migration で 2 テーブルを追加する |
| 閉鎖申し送り | Conversation-Repository feature（未 Issue）が担当。当 PR への closure 申し送りなし |

### §設計決定 TR-001: `task_assigned_agents.agent_id` / `deliverables.committed_by` は Aggregate 境界として永続的に FK 張らない

| 項目 | 内容 |
|---|---|
| 状態 | **RESOLVED（設計決定として凍結）** |
| 内容 | `task_assigned_agents.agent_id` / `deliverables.committed_by` に `agents.id` への FK を張らない。これは forward reference 問題ではなく **Aggregate 境界の設計決定**。`agents` テーブルは agent-repository PR #45 でマージ済みであり、技術的には FK を張ることは可能 |
| 根拠 | room-repository §確定 R1-B の `room_members.agent_id` 前例と同論理: **archived agent の CASCADE 危険性**。Agent が削除（archived）される際に ON DELETE CASCADE を適用すると task_assigned_agents 行が消え、Task Aggregate の復元が壊れる（IN_PROGRESS Task の assigned_agent_ids が空になり業務不整合）。ON DELETE RESTRICT なら Agent 削除前に必ず Task を DONE/CANCELLED にする連鎖が必要だが、これは Agent Aggregate と Task Aggregate の Aggregate 間依存を生む設計違反。**FK を張らないことで Aggregate の独立性を保ち、参照整合性は application 層の `AgentRepository.find_by_id(agent_id)` で補完する** |
| 対策 | application 層 `TaskService.assign()` が `AgentRepository.find_by_id(agent_id)` で存在確認してから `task.assign(agent_ids)` → `save()` を呼ぶ（Aggregate 境界を越えた参照整合性は application 層の責務） |
| 閉鎖 | FK closure 申し送りなし。この設計決定は **変更しない** |

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
