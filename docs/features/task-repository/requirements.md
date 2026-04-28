# 要件定義書

> feature: `task-repository`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源** / [`docs/features/directive-repository/`](../directive-repository/) **直近テンプレート** / [`docs/features/task/`](../task/)

## 機能要件

### REQ-TR-001: TaskRepository Protocol 定義

| 項目 | 内容 |
|------|------|
| 入力 | 該当なし（Protocol 定義） |
| 処理 | `application/ports/task_repository.py` で `TaskRepository(Protocol)` を定義。**6 method**（empire-repo の 3 method + §確定 R1-D の 3 method）: `find_by_id(task_id: TaskId) -> Task \| None` / `count() -> int` / `save(task: Task) -> None` / `count_by_status(status: TaskStatus) -> int` / `count_by_room(room_id: RoomId) -> int` / `find_blocked() -> list[Task]`。すべて `async def`、`@runtime_checkable` なし |
| 出力 | Protocol 定義。pyright strict で `SqliteTaskRepository` が満たすことを型レベル検証 |
| エラー時 | 該当なし |

### REQ-TR-002: SqliteTaskRepository 実装

| 項目 | 内容 |
|------|------|
| 入力 | `AsyncSession`（コンストラクタ引数）、各 method の引数 |
| 処理 | `find_by_id`: `tasks` SELECT → 不在なら None。存在すれば 3 子テーブルを個別 SELECT して `_from_rows()` で Task 復元（§確定 R1-H 各テーブルの ORDER BY 適用）。`count`: `select(func.count()).select_from(TaskRow)` で SQL `COUNT(*)`。`save`: §確定 R1-B の 6 段階（2 DELETE + tasks UPSERT + 3 INSERT）を順次実行。`count_by_status`: `SELECT COUNT(*) FROM tasks WHERE status = :status`。`count_by_room`: `SELECT COUNT(*) FROM tasks WHERE room_id = :room_id`。`find_blocked`: `SELECT * FROM tasks WHERE status = 'BLOCKED' ORDER BY updated_at DESC, id DESC`（§確定 R1-H）→ 各行を `find_by_id` 同様に子テーブルと組み合わせて Task 復元 |
| 出力 | `find_by_id`: `Task \| None`、`count`: `int`、`save`: `None`、`count_by_status`: `int`、`count_by_room`: `int`、`find_blocked`: `list[Task]`（空の場合 `[]`） |
| エラー時 | SQLAlchemy `IntegrityError`（FK RESTRICT 違反 / NOT NULL 違反 / UNIQUE 違反等）/ `OperationalError` を上位伝播。Repository 内で明示的 `commit` / `rollback` はしない |

### REQ-TR-003: Alembic 0007 revision

| 項目 | 内容 |
|------|------|
| 入力 | directive-repo の 0006 revision（`down_revision="0006_directive_aggregate"` で chain 一直線） |
| 処理 | `0007_task_aggregate.py` で以下を実行: (a) 4 テーブル作成（tasks / task_assigned_agents / deliverables / deliverable_attachments）、(b) INDEX 追加（`tasks.room_id` 単体 / `(tasks.status, tasks.updated_at, tasks.id)` 複合 — §確定 R1-K）、(c) **BUG-DRR-001 closure**: `op.batch_alter_table('directives')` で `fk_directives_task_id`（`directives.task_id → tasks.id` ON DELETE RESTRICT）追加（§確定 R1-C）。各テーブルの FK / UNIQUE 制約は REQ-TR-005 データモデル参照。`conversations` / `conversation_messages` テーブルは §BUG-TR-002 凍結済みのため除外 |
| 出力 | 4 テーブル + INDEX + FK が SQLite に存在。`directives.task_id` への FK closure 済み |
| エラー時 | migration 失敗 → `BakufuMigrationError`、Bootstrap stage 3 で Fail Fast |

### REQ-TR-004: CI 三層防衛の Task 拡張（**正/負のチェック併用**、directive-repository §確定 E パターン継承）

| 項目 | 内容 |
|------|------|
| 入力 | `scripts/ci/check_masking_columns.sh`（Layer 1）と `backend/tests/architecture/test_masking_columns.py`（Layer 2）|
| 処理 | (a) Layer 1 grep guard: `PARTIAL_MASK_FILES` に 2 エントリ追加（`tables/tasks.py:last_error:MaskedText` / `tables/deliverables.py:body_markdown:MaskedText`）。正のチェック（MaskedText 必須）と負のチェック（過剰マスキング防止）を各テーブルで実施。`conversation_messages.body_markdown` は §BUG-TR-002 凍結済みのため除外。(b) Layer 2 arch test: parametrize に 2 行追加（`tasks.last_error` / `deliverables.body_markdown` の `column.type.__class__ is MaskedText` を assert） |
| 出力 | CI が「2 カラムは MaskedText 必須、その他は masking なし」を物理保証 |
| エラー時 | 後続 PR が誤って 2 カラムのいずれかを `Text` に変更 → Layer 2 arch test で落下、PR ブロック |

### REQ-TR-005: storage.md 逆引き表更新

| 項目 | 内容 |
|------|------|
| 入力 | `docs/design/domain-model/storage.md` §逆引き表（Directive 残カラム行が最終行） |
| 処理 | §逆引き表に Task 関連行を追加・更新: (a) `Task.last_error`（`tasks.last_error`）を `（後続）` から **本 PR で配線完了** に更新、(b) `Deliverable.body_markdown`（`deliverables.body_markdown`）を同様に更新、(c) `Conversation.messages[].body_markdown` は §BUG-TR-002 凍結済みのため `feature/conversation-repository`（後続）のまま据え置き、(d) Task 残カラム（masking 非対象）を明示追加 |
| 出力 | storage.md §逆引き表が「Task 関連 2 masking カラムは本 PR で配線完了、Task 残カラムは masking 対象なし」状態 |
| エラー時 | 該当なし |

### REQ-TR-006: directive-repository 詳細設計 §BUG-DRR-001 を closure 済みに更新

| 項目 | 内容 |
|------|------|
| 入力 | `docs/features/directive-repository/detailed-design.md` §BUG-DRR-001 |
| 処理 | 状態を `OPEN（申し送り中）` から `RESOLVED（0007 で closure 済み）` に更新。closure 実施内容（0007 revision / batch_alter_table / fk_directives_task_id）を記録 |
| 出力 | directive-repository 詳細設計書の §BUG-DRR-001 が closure 済み状態を記録 |
| エラー時 | 該当なし |

## 画面・CLI 仕様

### CLI レシピ / コマンド

該当なし — 理由: 本 feature は infrastructure 層（Repository 実装）。

| コマンド | 概要 |
|---------|------|
| 該当なし | — |

### Web UI 画面

該当なし — 理由: UI を持たない。

| 画面ID | 画面名 | 主要操作 |
|-------|-------|---------|
| 該当なし | — | — |

## API 仕様

該当なし — 理由: HTTP API は `feature/http-api` で扱う。

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| 該当なし | — | — | — | — |

## データモデル

本 Issue で導入する 4 テーブル + INDEX + FK 群。`conversations` / `conversation_messages` テーブルは §BUG-TR-002 凍結済みのため除外。

### `tasks` テーブル

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `tasks` | `id` | `UUIDStr` | PK, NOT NULL | TaskId |
| `tasks` | `room_id` | `UUIDStr` | **FK → `rooms.id` ON DELETE CASCADE, NOT NULL** | 所属 Room |
| `tasks` | `directive_id` | `UUIDStr` | **FK → `directives.id` ON DELETE CASCADE, NOT NULL** | 起点 Directive |
| `tasks` | `current_stage_id` | `UUIDStr` | NOT NULL（**FK なし** — §確定 R1-G: Aggregate 境界設計決定、workflow §確定 J 同方針） | 現 Stage（application 層が Workflow 内存在を検証） |
| `tasks` | `status` | `String(32)` | NOT NULL（TaskStatus 6 値: PENDING / IN_PROGRESS / AWAITING_EXTERNAL_REVIEW / BLOCKED / DONE / CANCELLED） | 全体状態 |
| `tasks` | `last_error` | **`MaskedText`** | NULL（BLOCKED ⇔ 非 NULL 不変条件は Aggregate 層で保証） | BLOCKED 隔離理由（LLM エラーメッセージ） |
| `tasks` | `created_at` | `DateTime(timezone=True)` | NOT NULL | UTC 起票時刻 |
| `tasks` | `updated_at` | `DateTime(timezone=True)` | NOT NULL | UTC 最終更新時刻 |
| INDEX | `tasks.room_id` | 非 UNIQUE | — | `count_by_room` 最適化 |
| INDEX | `(tasks.status, tasks.updated_at, tasks.id)` | 非 UNIQUE | — | `find_blocked` の WHERE status フィルタ + ORDER BY updated_at DESC, id DESC を一括最適化（§確定 R1-K） |

### `task_assigned_agents` テーブル

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `task_assigned_agents` | `task_id` | `UUIDStr` | **FK → `tasks.id` ON DELETE CASCADE, NOT NULL** | 親 Task |
| `task_assigned_agents` | `agent_id` | `UUIDStr` | NOT NULL（**FK なし** — Aggregate 境界設計決定。room_members.agent_id 前例と同論理: archived agent の CASCADE 危険性回避。§設計決定 TR-001） | AgentId（参照のみ） |
| `task_assigned_agents` | `order_index` | `Integer` | NOT NULL（割り当て順序保持） | — |
| UNIQUE | `(task_id, agent_id)` | — | — | 重複割り当て防止（Aggregate 不変条件と 2 層防衛） |

### `deliverables` テーブル

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `deliverables` | `id` | `UUIDStr` | PK, NOT NULL | DeliverableId |
| `deliverables` | `task_id` | `UUIDStr` | **FK → `tasks.id` ON DELETE CASCADE, NOT NULL** | 親 Task |
| `deliverables` | `stage_id` | `UUIDStr` | NOT NULL（**FK なし** — §確定 R1-G 同方針） | 対象 Stage |
| `deliverables` | `body_markdown` | **`MaskedText`** | NOT NULL | 成果物本文（Agent 出力を含む → masking 必須） |
| `deliverables` | `committed_by` | `UUIDStr` | NOT NULL（**FK なし** — Aggregate 境界） | コミットした AgentId |
| `deliverables` | `committed_at` | `DateTime(timezone=True)` | NOT NULL | UTC コミット時刻 |
| UNIQUE | `(task_id, stage_id)` | — | — | Stage 単位に最新 Deliverable のみ保持（Aggregate §確定 R1-E の dict 上書きに対応） |

### `deliverable_attachments` テーブル

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `deliverable_attachments` | `id` | `UUIDStr` | PK, NOT NULL | AttachmentId |
| `deliverable_attachments` | `deliverable_id` | `UUIDStr` | **FK → `deliverables.id` ON DELETE CASCADE, NOT NULL** | 親 Deliverable |
| `deliverable_attachments` | `sha256` | `String(64)` | NOT NULL（`^[a-f0-9]{64}$`） | ファイル内容ハッシュ |
| `deliverable_attachments` | `filename` | `String(255)` | NOT NULL | サニタイズ済みファイル名（storage.md §filename サニタイズ規則 6 項目） |
| `deliverable_attachments` | `mime_type` | `String(128)` | NOT NULL（ホワイトリスト 7 種） | MIME 種別 |
| `deliverable_attachments` | `size_bytes` | `Integer` | NOT NULL（0 ≤ x ≤ 10485760） | ファイルサイズ |

**masking 対象カラム**: `tasks.last_error` / `deliverables.body_markdown`（各 `MaskedText`、2 カラム）。`conversation_messages.body_markdown` は §BUG-TR-002 凍結済みのため除外。その他カラムは masking 対象なし、CI 三層防衛で「対象なし」を明示登録。

## ユーザー向けメッセージ一覧

該当なし — 理由: Repository は内部 API、ユーザー向けメッセージは application 層 / HTTP API 層が定義する。

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|----|------|----------------|---------|
| 該当なし | — | — | — |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | SQLAlchemy 2.x / Alembic / aiosqlite | pyproject.toml | uv | 既存（M2 永続化基盤）|
| Python 依存 | typing.Protocol | 標準ライブラリ | — | Python 3.12 標準 |
| ドメイン | `Task` / `TaskId` / `TaskStatus` / `RoomId` / `DirectiveId` / `AgentId` / `StageId` / `Deliverable` / `Attachment` | `domain/task/` / `domain/value_objects.py` | 内部 import | 既存（task PR #42）|
| インフラ | `Base` / `UUIDStr` / `MaskedText` / `MaskingGateway` | `infrastructure/persistence/sqlite/base.py` / `infrastructure/security/masking.py` | 内部 import | 既存（M2 永続化基盤、persistence-foundation #23 で TypeDecorator hook 提供済み）|
| インフラ | `AsyncSession` / `async_sessionmaker` | `infrastructure/persistence/sqlite/session.py` | 内部 import | 既存 |
| 外部参照テーブル | `rooms` / `directives` | Alembic 0005 / 0006 で先行追加済み | — | 既存（room-repo PR #47 / directive-repo PR #50 マージ済み）|
| 外部サービス | 該当なし | — | — | infrastructure 層、外部通信なし |
