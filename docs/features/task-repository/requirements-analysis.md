# 要求分析書

> feature: `task-repository`
> 関連: [requirements.md](requirements.md) / [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源** / [`docs/features/directive-repository/`](../directive-repository/) **直近テンプレート** / [`docs/features/task/`](../task/) **Task Aggregate 凍結済み設計**

## 記述ルール（必ず守ること）

要求分析書に**疑似コード・サンプル実装（python/ts/sh/yaml 等の言語コードブロック）を書かない**。
必要なのは「何を作るか・なぜ作るか・どう作るかの方針」の言語的記述であり、実装の細部は [detailed-design.md](detailed-design.md) で凍結する。

## 背景と目的

Task Aggregate（`domain/task/`、PR #42）は M1 ドメインモデルの第 6 集約であり、`tasks` / `task_assigned_agents` / `deliverables` / `deliverable_attachments` の **4 テーブル**にまたがる複合永続化構造を持つ。本 feature（Issue #35）はその SQLite 永続化基盤（M2 層）を実装する Repository PR である。

empire-repository（PR #25）で確立したテンプレートパターン（Protocol / SqliteXxxRepository / `_to_row` / `_from_row` / Alembic revision）を 100% 継承しつつ、Task Aggregate 固有の多段階永続化要件・masking 2 カラム・BUG-DRR-001 closure を追加凍結する。

> **§BUG-TR-002 申し送り（凍結）**: `conversations` / `conversation_messages` テーブルは Alembic 0007 で誤って先行作成されたが、Task Aggregate（PR #42）は現時点で `conversations` 属性を持たない（YAGNI 違反）。両テーブルはこの PR から削除し、Task domain が `conversations: list[Conversation]` 属性を獲得する将来 PR で改めて追加する。それまで本テーブル群・関連 Repository コード・masking 配線を凍結禁止とする。

## 要求一覧

| 要求 ID | 要求文 | 優先度 | 出典 |
|--------|-------|-------|------|
| RQ-TR-001 | Task Aggregate を SQLite に永続化・復元できる | Must | Task Aggregate PR #42 後続課題 |
| RQ-TR-002 | 4 テーブルにまたがる save() を DB 整合性を保ちながら原子的に実行できる（§BUG-TR-002凍結済み） | Must | Task の複合ドメインモデル（tasks + 3 子テーブル） |
| RQ-TR-003 | BLOCKED 状態の Task 一覧を取得できる（障害隔離用） | Must | Task.block() + TaskService 要件（後続 Issue #38） |
| RQ-TR-004 | Room スコープ・ステータス別の Task 件数を取得できる | Must | Room ダッシュボード後続要件（後続 HTTP API） |
| RQ-TR-005 | `directives.task_id → tasks.id` FK 未追加（BUG-DRR-001）を closure する | Must | directive-repository PR #50 §BUG-DRR-001 申し送り |
| RQ-TR-006 | `tasks.last_error` / `deliverables.body_markdown` を MaskedText で永続化し、DB に raw secret が保存されないことを CI で物理保証する（2 カラム。`conversation_messages.body_markdown` は §BUG-TR-002 凍結済み） | Must | MaskingGateway §確定 G（persistence-foundation PR #23 で TypeDecorator hook 提供済み） |
| RQ-TR-007 | Alembic revision chain に 0007 を追加する（down_revision = "0006_directive_aggregate"） | Must | bakufu Bootstrap M2 migration chain 連続性 |

## §確定事項（先送り撤廃）

要求分析フェーズで判断が確定した事項を以下に凍結する。後続フェーズで再議なし。

### §確定 R1-A: empire §確定 A テンプレートを 100% 継承（Task Aggregate 固有の差分のみ追加）

empire-repository / room-repository / directive-repository の 3 PR で実績を積んだパターンを継承する:

| 継承ルール | 内容 |
|-----------|------|
| Protocol 定義 | `typing.Protocol`、`@runtime_checkable` なし |
| コンストラクタ | `AsyncSession` を引数受け取り（依存性注入） |
| private mapping | `_to_row()` / `_from_row()` を private に閉じる |
| 型変換信頼 | TypeDecorator（`UUIDStr` / `MaskedText`）が処理済みの値を返す前提で二重変換しない（directive-repository v2 §確定 G、Rams 指摘 R1 凍結） |
| UPSERT | `INSERT OR REPLACE` / SQLAlchemy `merge()` パターン |
| Transaction | Repository 内で `commit` / `rollback` しない（UoW 責務は application 層） |

### §確定 R1-B: save() 多段階 DELETE+UPSERT+INSERT 順序（4 テーブル対応、6 段階）

empire §確定 B の「子テーブル DELETE → 親 UPSERT → 子 INSERT」パターンを Task の 4 テーブル構造に適用する。FK CASCADE を活用して DELETE 段数を削減する:

| 段階 | 操作 | 対象テーブル | 理由 |
|------|------|------------|------|
| 1 | DELETE | `deliverables WHERE task_id = :id` | CASCADE で `deliverable_attachments` も自動削除 |
| 2 | DELETE | `task_assigned_agents WHERE task_id = :id` | CASCADE なし、直接 DELETE |
| 3 | UPSERT | `tasks` | ON CONFLICT id DO UPDATE（親テーブル先行） |
| 4 | INSERT | `task_assigned_agents`（各 AgentId / order_index） | 親 tasks 確定後 |
| 5 | INSERT | `deliverables`（各 Deliverable） | 親 tasks 確定後。`UNIQUE(task_id, stage_id)` は段階 1 DELETE で先行クリア済み |
| 6 | INSERT | `deliverable_attachments`（各 Attachment per Deliverable） | 親 deliverables 確定後 |

**根拠**: `deliverable_attachments → deliverables → tasks` / `task_assigned_agents → tasks` の FK 制約から、DELETE は深いテーブル優先（CASCADE 活用）、INSERT は浅いテーブル優先でなければ `IntegrityError` が発生する。Fail Fast 設計として順序を静的に凍結する。`conversations` / `conversation_messages` テーブルは §BUG-TR-002 凍結済みのため本スコープから除外。

### §確定 R1-C: BUG-DRR-001 closure — `directives.task_id → tasks.id` FK 追加

directive-repository PR #50 の §BUG-DRR-001 で申し送り済みの forward reference 問題を本 PR で解消する:

| 項目 | 内容 |
|-----|------|
| 対象 | `directives.task_id → tasks.id` FK（ON DELETE RESTRICT） |
| 手法 | `op.batch_alter_table('directives')` + `create_foreign_key('fk_directives_task_id', 'tasks', ['task_id'], ['id'], ondelete='RESTRICT')` |
| 理由 | SQLite は `ALTER TABLE ADD CONSTRAINT` を未サポート。`batch_alter_table` によるテーブル再作成が唯一の手法（room-repository PR #47 BUG-EMR-001 closure と同パターン） |
| downgrade | `drop_constraint('fk_directives_task_id', 'directives', type_='foreignkey')` |
| 配置 | Alembic `0007_task_aggregate.py` の `upgrade()` / `downgrade()` に task テーブル作成後に追記 |

**RESTRICT を採用する理由**: `directives.task_id` が指す Task が削除された場合、Directive の task_id に NULL を入れるのではなく参照整合性違反として明示的に Fail させる（application 層が Task を削除する際は先に `directive.unlink_task()` / `save()` を呼ぶ責務を強制）。ON DELETE CASCADE や ON DELETE SET NULL より intent が明確。

### §確定 R1-D: 追加 Protocol method（YAGNI 境界の明示）

empire §確定 B の 3 method（`find_by_id` / `count` / `save`）に加え、Task 固有の 3 method を追加する:

| method | 根拠 |
|--------|------|
| `count_by_status(status: TaskStatus) -> int` | Room ダッシュボード（後続 HTTP API）で「BLOCKED 件数」等のステータス別集計が確定要件 |
| `count_by_room(room_id: RoomId) -> int` | Room 詳細ページの Task 件数表示（後続 HTTP API 確定要件） |
| `find_blocked() -> list[Task]` | 障害隔離用（`TaskService.find_blocked_tasks()`、後続 Issue #38 の確定前提条件） |

追加しない方法（YAGNI 拒否済み）:

| 拒否した method | 拒否理由 |
|--------------|---------|
| `find_by_room(room_id)` | 後続 HTTP API で Task 一覧ページネーションが必要になるが、現時点では full list の仕様が未確定。ページネーション対応は Protocol 設計を変える（引数追加）ため、YAGNI として申し送り |
| `find_by_directive(directive_id)` | 呼び出し箇所なし。directive-repository と同様の YAGNI 違反（directive v1 で §確定 G 却下済み） |

### §確定 R1-E: CI 三層防衛の 2 masking カラム対応

Task Aggregate の 2 masking カラムを CI 三層防衛に登録する（`conversation_messages.body_markdown` は §BUG-TR-002 凍結済みのため除外）:

| カラム | テーブル | TypeDecorator | Layer 1（grep guard） | Layer 2（arch test） |
|-------|---------|------------|---------------------|---------------------|
| `last_error` | `tasks` | `MaskedText` | `tables/tasks.py:last_error:MaskedText` | `tasks.last_error: MaskedText` |
| `body_markdown` | `deliverables` | `MaskedText` | `tables/deliverables.py:body_markdown:MaskedText` | `deliverables.body_markdown: MaskedText` |

**Layer 1（grep guard）**: `scripts/ci/check_masking_columns.sh` の `PARTIAL_MASK_FILES` に 2 エントリ追加（正のチェック: 必須確認 + 負のチェック: 過剰マスキング防止）。

**Layer 2（arch test）**: `backend/tests/architecture/test_masking_columns.py` の parametrize に 2 行追加（`column.type.__class__ is MaskedText` を assert）。

**Layer 3（storage.md）**: `docs/design/domain-model/storage.md` §逆引き表を本 PR で更新（§確定 R1-F）。

### §確定 R1-F: storage.md 逆引き表の更新内容

`docs/design/domain-model/storage.md` §逆引き表に追加する行:

| 追加行 | 更新内容 |
|------|---------|
| `Task.last_error` | `（後続）` → `feature/task-repository`（Issue #35、**task §確定 G 実適用、本 PR で配線完了**） |
| `Deliverable.body_markdown` | `（後続）` → `feature/task-repository`（Issue #35、**task §確定 G 実適用、本 PR で配線完了**） |
| `Conversation.messages[].body_markdown` | `feature/conversation-repository`（後続）のまま据え置き。§BUG-TR-002 凍結済み: Task domain が `conversations` 属性を獲得する将来 PR で配線する |
| `Task 残カラム（tasks / task_assigned_agents / deliverables / deliverable_attachments の masking 非対象カラム）` | masking 対象なし。CI Layer 2 で arch test 保証 |

### §確定 R1-G: `tasks.current_stage_id` に FK を張らない理由（Aggregate 境界 + application 層保証）

`tasks.current_stage_id → workflow_stages.id` FK は **0007 では張らない**:

| 根拠 | 内容 |
|-----|------|
| **Aggregate 境界** | `workflow_stages` は Workflow Aggregate（PR #41）の子構造であり、Task Aggregate とは独立した Aggregate 境界を持つ。Task が Workflow Aggregate の内部構造（stage）に直接 FK 依存することは Aggregate 間の結合を生み、Workflow Aggregate の変更（Stage 削除 / リネーム）が Task に波及する設計違反になる |
| **ON DELETE の困難** | FK を張る場合の ON DELETE 選択肢はどれも不整合: CASCADE（Task が消えてしまう）/ RESTRICT（Stage 削除前に全 Task を終了させる連鎖義務）/ SET NULL（`current_stage_id` が NULL になり Task が壊れる）。いずれも Aggregate 独立性を損なう |
| **workflow §確定 J 同方針** | `workflow_stages` 内の遷移先 Stage 参照（workflow §確定 J）で「Aggregate 内部参照は FK を張らない」と同方針。`current_stage_id` は Task の業務的な「現在地」であり、Workflow Aggregate が保有するデータへの参照整合性は application 層責務 |
| application 層保証 | `current_stage_id` の Workflow 内存在検証は `TaskService` が `WorkflowRepository.find_by_id()` で行う（task §確定 R1-A 不変条件欄） |

本 PR では `tasks.current_stage_id` は NOT NULL UUIDStr として存在（FK なし）。FK closure の申し送りなし（`room_members.agent_id` と同様、Aggregate 境界として永続的に FK を張らない設計決定）。

### §確定 R1-H: 子テーブル SELECT の ORDER BY 決定論性（BUG-EMR-001 準拠）

room-repository PR #47 BUG-EMR-001 規約（`ORDER BY` は PK を tiebreaker に使い決定論的順序を保証）を全子テーブルに適用する:

| テーブル | ORDER BY | tiebreaker 根拠 |
|---------|---------|----------------|
| `task_assigned_agents` | `ORDER BY order_index ASC` | order_index は Agent 割り当て順の業務意味を持つ（tiebreaker 兼 primary key） |
| `deliverables` | `ORDER BY stage_id ASC` | UNIQUE(task_id, stage_id) 制約より stage_id は task scope 内で一意。ソート安定 |
| `deliverable_attachments` | `ORDER BY sha256 ASC` | `UNIQUE(deliverable_id, sha256)` 制約より deliverable scope 内で一意。ソート安定 |
| `find_blocked()` | `ORDER BY updated_at DESC, id DESC` | 最近 BLOCKED になった Task を優先表示（障害隔離 UX）。同タイムスタンプは id で決定論的順序 |

> `conversations` / `conversation_messages` テーブルの ORDER BY は §BUG-TR-002 凍結済みのため除外。将来 Task domain に `conversations` 属性が追加された時点で本表に追記する。

### §確定 R1-I: Attachment 物理ファイルはスコープ外（metadata のみ）

`deliverable_attachments` テーブルはファイルの **metadata のみ** を永続化する:

| 範囲 | 内容 |
|-----|------|
| 本 PR の範囲 | sha256 / filename / mime_type / size_bytes の metadata 4 カラム |
| 本 PR の範囲外 | 物理ファイルの保存先（local filesystem / S3 等）は `feature/attachment-storage`（未 Issue）が決定する |
| 理由 | storage backend の選定（local / S3 / R2 等）は未確定。Attachment metadata だけ先行して永続化することで Task Aggregate の復元が可能 |

## 技術的判断・選定根拠

| 判断項目 | 採用 | 不採用 | 根拠 |
|---------|------|-------|------|
| Protocol method 数 | 6（empire 3 + Task 固有 3） | 2（find_by_id / save のみ） | count_by_status / count_by_room / find_blocked はダッシュボード + 障害隔離の確定要件、YAGNI ではない |
| save() DELETE 戦略 | CASCADE 活用（2 段 DELETE → 2 親テーブル、§BUG-TR-002 凍結済み） | 全子テーブル明示 DELETE（3 段） | CASCADE を使うことで DELETE 段数を削減し、コード量と FK 制約の重複を避ける |
| Alembic revision 方式 | 1 ファイル（0007_task_aggregate.py）に 4 テーブル + BUG-DRR-001 FK closure を全収録（§BUG-TR-002 凍結済みのため conversations/conversation_messages 除外） | 7 ファイル分割 | 1 ファイル atomic migration。テーブル群が 1 Aggregate に属するため分割する業務理由なし |
| `current_stage_id` FK | なし（Aggregate 境界 + application 層保証） | `workflow_stages.id` FK | Workflow Aggregate と Task Aggregate の Aggregate 境界。ON DELETE 選択肢がどれも不整合（§確定 R1-G） |

## 関連 Issue / PR

| Issue/PR | 関係 |
|---------|------|
| PR #42 | Task Aggregate 実装（M1 domain layer、本 PR の前提） |
| PR #50 (directive-repository) | §BUG-DRR-001 申し送り元（本 PR で closure） |
| Issue #38 | TaskService（後続、`find_blocked()` を呼ぶ application 層） |
| PR #25 (empire-repository) | テンプレート真実源 |
| PR #47 (room-repository) | BUG-EMR-001 ORDER BY 規約 + batch_alter_table パターン |
