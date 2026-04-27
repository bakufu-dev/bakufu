# 要件定義書

> feature: `workflow-repository`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源** / [`docs/features/workflow/`](../workflow/) （domain 設計済み）

## 機能要件

### REQ-WFR-001: WorkflowRepository Protocol 定義

| 項目 | 内容 |
|------|------|
| 入力 | 該当なし（Protocol 定義のため抽象） |
| 処理 | `application/ports/workflow_repository.py` で `WorkflowRepository(Protocol)` を定義。3 メソッド（empire-repo §確定 A 同 signature）: `find_by_id(workflow_id: WorkflowId) -> Workflow \| None` / `count() -> int` / `save(workflow: Workflow) -> None`。すべて `async def`、`@runtime_checkable` なし |
| 出力 | Protocol 定義。pyright strict で SqliteWorkflowRepository が満たすことを型レベル検証 |
| エラー時 | 該当なし |

### REQ-WFR-002: SqliteWorkflowRepository 実装

| 項目 | 内容 |
|------|------|
| 入力 | `AsyncSession`（コンストラクタ引数）、各メソッドに応じた引数（`workflow_id` / `workflow`） |
| 処理 | `find_by_id`: `workflows` SELECT → 不在なら None。存在すれば `workflow_stages` を `ORDER BY stage_id` / `workflow_transitions` を `ORDER BY transition_id` で SELECT（§Known Issues §BUG-EMR-001 規約）→ `_from_row()` で Workflow 復元。`count`: `select(func.count()).select_from(WorkflowRow)` で SQL レベル COUNT(*)（§確定 D 補強）。`save`: §確定 B の delete-then-insert（empire-repo と同パターン、本 PR §確定 G〜J で Workflow 固有差分を補強） |
| 出力 | `find_by_id`: `Workflow \| None`、`count`: `int`、`save`: `None` |
| エラー時 | SQLAlchemy `IntegrityError` / `OperationalError` を上位伝播。Repository 内で明示的 `commit` / `rollback` はしない（service の UoW 責務、§確定 B） |

### REQ-WFR-003: Alembic 0003 revision

| 項目 | 内容 |
|------|------|
| 入力 | empire-repo の 0002 revision（`down_revision="0002_empire_aggregate"` で chain 一直線、§確定 R1-C） |
| 処理 | `0003_workflow_aggregate.py` で 3 テーブル追加: (a) `workflows`（id PK、name String(80) NOT NULL、entry_stage_id UUIDStr NOT NULL — 循環参照のため FK は張らない、§確定 J）、(b) `workflow_stages`（workflow_id FK → workflows.id CASCADE、stage_id UUIDStr、name / kind / roles_csv / deliverable_template / completion_policy_json / notify_channels_json、UNIQUE(workflow_id, stage_id)、§確定 G/H/I で各カラム凍結）、(c) `workflow_transitions`（workflow_id FK CASCADE、transition_id UUIDStr、from_stage_id / to_stage_id / condition / label、UNIQUE(workflow_id, transition_id)） |
| 出力 | 3 テーブル + UNIQUE 制約 + INDEX が SQLite に存在する状態 |
| エラー時 | migration 失敗 → `BakufuMigrationError(MSG-PF-004)`、Bootstrap stage 3 で Fail Fast（M2 永続化基盤の規約） |

### REQ-WFR-004: CI 三層防衛の Workflow 拡張

| 項目 | 内容 |
|------|------|
| 入力 | M2 永続化基盤の `scripts/ci/check_masking_columns.sh`（Layer 1）と `backend/tests/architecture/test_masking_columns.py`（Layer 2）|
| 処理 | (a) Layer 1 grep guard: 対象テーブルリストに `workflows` / `workflow_stages` / `workflow_transitions` を**明示登録**。`workflow_stages.py` の `notify_channels_json` カラム宣言に `MaskedJSONEncoded` が含まれることを strict 検証（負のチェックではなく**正のチェック**、empire-repo の Empire は対象なしとは異なる）。その他カラムは masking 対象なしを assert。(b) Layer 2 arch test: parametrize に 3 テーブル追加、`workflow_stages.notify_channels_json` の `column.type.__class__` が `MaskedJSONEncoded` であることを assert |
| 出力 | CI が Workflow 3 テーブルで「`notify_channels_json` は `MaskedJSONEncoded` 必須、その他は masking なし」を物理保証する状態 |
| エラー時 | 後続 PR が誤って `notify_channels_json` を `JSONEncoded`（masking なし）に変更 → Layer 2 arch test で落下、PR ブロック |

### REQ-WFR-005: storage.md 逆引き表更新

| 項目 | 内容 |
|------|------|
| 入力 | `docs/architecture/domain-model/storage.md` §逆引き表（empire-repo PR #25 で Empire 行追加済み） |
| 処理 | §逆引き表に「Workflow 関連カラム」3 行を追加: (a) `workflow_stages.notify_channels_json: MaskedJSONEncoded`（webhook token マスキング、Schneier #6 実適用）、(b) `workflows` / `workflow_transitions` は masking 対象なし |
| 出力 | storage.md §逆引き表に Workflow 関連 3 行が追加された状態 |
| エラー時 | 該当なし（ドキュメント更新） |

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

本 Issue で導入する 3 テーブル + UNIQUE 制約。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `workflows` | `id` | `UUIDStr` | PK, NOT NULL | WorkflowId |
| `workflows` | `name` | `String(80)` | NOT NULL | 表示名 |
| `workflows` | `entry_stage_id` | `UUIDStr` | NOT NULL（FK 宣言なし、§確定 J で循環参照回避） | Stage への参照 |
| `workflow_stages` | `workflow_id` | `UUIDStr` | FK → `workflows.id` ON DELETE CASCADE | 所属 Workflow |
| `workflow_stages` | `stage_id` | `UUIDStr` | NOT NULL | StageId |
| `workflow_stages` | `name` | `String(80)` | NOT NULL | Stage 表示名 |
| `workflow_stages` | `kind` | `String(32)` | NOT NULL（enum string: `WORK` / `INTERNAL_REVIEW` / `EXTERNAL_REVIEW`） | StageKind |
| `workflow_stages` | `roles_csv` | `String(255)` | NOT NULL | `frozenset[Role]` をカンマ区切りシリアライズ（§確定 G） |
| `workflow_stages` | `deliverable_template` | `Text` | NOT NULL | Markdown テンプレ |
| `workflow_stages` | `completion_policy_json` | `JSONEncoded` | NOT NULL | CompletionPolicy VO の JSON シリアライズ（§確定 I、masking 対象外） |
| `workflow_stages` | `notify_channels_json` | **`MaskedJSONEncoded`** | NOT NULL DEFAULT '[]' | NotifyChannel リストの JSON、`process_bind_param` で webhook token をマスキング（§確定 H） |
| `workflow_stages` UNIQUE | `(workflow_id, stage_id)` | — | — | DB 制約で stage_id 一意 |
| `workflow_transitions` | `workflow_id` | `UUIDStr` | FK → `workflows.id` ON DELETE CASCADE | 所属 Workflow |
| `workflow_transitions` | `transition_id` | `UUIDStr` | NOT NULL | TransitionId |
| `workflow_transitions` | `from_stage_id` | `UUIDStr` | NOT NULL | from Stage |
| `workflow_transitions` | `to_stage_id` | `UUIDStr` | NOT NULL | to Stage |
| `workflow_transitions` | `condition` | `String(32)` | NOT NULL（enum: `APPROVED` / `REJECTED` / `CONDITIONAL` / `TIMEOUT`） | TransitionCondition |
| `workflow_transitions` | `label` | `String(80)` | NOT NULL | UI 表示ラベル |
| `workflow_transitions` UNIQUE | `(workflow_id, transition_id)` | — | — | DB 制約 |

**masking 対象カラム**: `workflow_stages.notify_channels_json` のみ（`MaskedJSONEncoded`、§確定 H）。その他 11 カラムは masking 対象なし、CI 三層防衛で「対象なし」を明示登録。

## ユーザー向けメッセージ一覧

該当なし — 理由: Repository は内部 API のみ提供、ユーザー向けメッセージは application 層 / HTTP API 層が定義する。

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|----|------|----------------|---------|
| 該当なし | — | — | — |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | SQLAlchemy 2.x / Alembic / aiosqlite | pyproject.toml | uv | 既存（M2 永続化基盤）|
| Python 依存 | typing.Protocol | 標準ライブラリ | — | Python 3.12 標準 |
| ドメイン | `Workflow` / `WorkflowId` / `Stage` / `StageId` / `Transition` / `TransitionId` / `Role` / `StageKind` / `TransitionCondition` / `NotifyChannel` / `CompletionPolicy` | `domain/workflow/` / `domain/value_objects.py` | 内部 import | 既存（workflow #16）|
| インフラ | `Base` / `UUIDStr` / `JSONEncoded` / `MaskedJSONEncoded` / `MaskedText` | `infrastructure/persistence/sqlite/base.py` | 内部 import | 既存（M2 永続化基盤、empire-repo で `MaskedJSONEncoded` パターン確立） |
| インフラ | `AsyncSession` / `async_sessionmaker` | `infrastructure/persistence/sqlite/session.py` | 内部 import | 既存 |
| 外部サービス | 該当なし | — | — | infrastructure 層、外部通信なし |
