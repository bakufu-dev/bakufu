# 要件定義書

> feature: `agent-repository`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源** / [`docs/features/workflow-repository/`](../workflow-repository/) **2 件目テンプレート** / [`docs/features/agent/`](../agent/)

## 機能要件

### REQ-AGR-001: AgentRepository Protocol 定義

| 項目 | 内容 |
|------|------|
| 入力 | 該当なし（Protocol 定義） |
| 処理 | `application/ports/agent_repository.py` で `AgentRepository(Protocol)` を定義。**4 method**（empire-repo の 3 method + 第 4 method `find_by_name`、§確定 R1-C）: `find_by_id(agent_id: AgentId) -> Agent \| None` / `count() -> int` / `save(agent: Agent) -> None` / `find_by_name(empire_id: EmpireId, name: str) -> Agent \| None`。すべて `async def`、`@runtime_checkable` なし |
| 出力 | Protocol 定義。pyright strict で SqliteAgentRepository が満たすことを型レベル検証 |
| エラー時 | 該当なし |

### REQ-AGR-002: SqliteAgentRepository 実装

| 項目 | 内容 |
|------|------|
| 入力 | `AsyncSession`（コンストラクタ引数）、各 method の引数 |
| 処理 | `find_by_id`: `agents` SELECT → 不在なら None。存在すれば `agent_providers` を `ORDER BY provider_kind` / `agent_skills` を `ORDER BY skill_id` で SELECT（§BUG-EMR-001 規約） → `_from_row()` で Agent 復元。`count`: `select(func.count()).select_from(AgentRow)` で SQL `COUNT(*)`。`save`: §確定 R1-A の delete-then-insert（5 段階手順、empire-repo と同パターンで子テーブル数のみ拡張）。`find_by_name`: `SELECT ... WHERE empire_id=:empire_id AND name=:name LIMIT 1`、子テーブル含めて Agent 復元 or None |
| 出力 | `find_by_id` / `find_by_name`: `Agent \| None`、`count`: `int`、`save`: `None` |
| エラー時 | SQLAlchemy `IntegrityError`（partial unique index 違反等）/ `OperationalError` を上位伝播。Repository 内で明示的 `commit` / `rollback` はしない |

### REQ-AGR-003: Alembic 0004 revision

| 項目 | 内容 |
|------|------|
| 入力 | workflow-repo の 0003 revision（`down_revision="0003_workflow_aggregate"` で chain 一直線）|
| 処理 | `0004_agent_aggregate.py` で 3 テーブル追加: (a) `agents`（id PK / empire_id FK → empires.id CASCADE / name String(40) / role String(32) / display_name String(80) / archetype String(80) / **prompt_body Text MaskedText** / archived Boolean、UNIQUE 制約は張らない — name 一意は application 層責務）、(b) `agent_providers`（agent_id FK CASCADE / provider_kind String(32) / model String(80) / is_default Boolean、UNIQUE(agent_id, provider_kind)、**partial unique index `WHERE is_default = 1`**）、(c) `agent_skills`（agent_id FK CASCADE / skill_id UUIDStr / name String(80) / path String(500)、UNIQUE(agent_id, skill_id)） |
| 出力 | 3 テーブル + UNIQUE 制約 + partial unique index が SQLite に存在 |
| エラー時 | migration 失敗 → `BakufuMigrationError`、Bootstrap stage 3 で Fail Fast |

### REQ-AGR-004: CI 三層防衛の Agent 拡張（**正/負のチェック併用**、workflow-repo §確定 E パターン）

| 項目 | 内容 |
|------|------|
| 入力 | `scripts/ci/check_masking_columns.sh`（Layer 1）と `backend/tests/architecture/test_masking_columns.py`（Layer 2）|
| 処理 | (a) Layer 1 grep guard: `tables/agents.py` の `prompt_body` カラム宣言行に **`MaskedText` 必須**（正のチェック、Schneier #3 実適用 grep 物理保証）。`tables/agents.py` の `prompt_body` 以外のカラムに `MaskedText` / `MaskedJSONEncoded` が登場しない（過剰マスキング防止）。`tables/agent_providers.py` / `tables/agent_skills.py` 全体に登場しない（負のチェック）。(b) Layer 2 arch test: parametrize に Agent 3 テーブル追加、`agents.prompt_body` の `column.type.__class__ is MaskedText` を assert |
| 出力 | CI が Agent 3 テーブルで「`agents.prompt_body` は `MaskedText` 必須、その他は masking なし」を物理保証 |
| エラー時 | 後続 PR が誤って `prompt_body` を `Text`（masking なし）に変更 → Layer 2 arch test で落下、PR ブロック |

### REQ-AGR-005: storage.md 逆引き表更新

| 項目 | 内容 |
|------|------|
| 入力 | `docs/design/domain-model/storage.md` §逆引き表（既存 `Persona.prompt_body` 行は persistence-foundation #23 で「`feature/agent-repository`（後続）」と表記） |
| 処理 | §逆引き表に Agent 関連 2 行追加: (a) `agents.prompt_body: MaskedText`（Schneier #3 **実適用**、persistence-foundation #23 で hook 構造提供済みを本 PR で配線）、(b) `agents` 残カラム + `agent_providers` 全カラム + `agent_skills` 全カラムは masking 対象なし。既存の `Persona.prompt_body` 行は本 PR で**実適用済み**を明示するよう更新 |
| 出力 | storage.md §逆引き表が「Agent 関連の masking 対象は `agents.prompt_body` のみ、Schneier #3 実適用済み」状態 |
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

本 Issue で導入する 3 テーブル + UNIQUE 制約 + partial unique index。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `agents` | `id` | `UUIDStr` | PK, NOT NULL | AgentId |
| `agents` | `empire_id` | `UUIDStr` | FK → `empires.id` ON DELETE CASCADE, NOT NULL | 所属 Empire |
| `agents` | `name` | `String(40)` | NOT NULL（**DB UNIQUE は張らない、application 層責務**） | 表示名（Empire 内一意） |
| `agents` | `role` | `String(32)` | NOT NULL（Role enum） | 役割テンプレ |
| `agents` | `display_name` | `String(80)` | NOT NULL | Persona.display_name |
| `agents` | `archetype` | `String(80)` | NOT NULL DEFAULT '' | Persona.archetype |
| `agents` | `prompt_body` | **`MaskedText`** | NOT NULL DEFAULT '' | Persona.prompt_body（Schneier #3 実適用） |
| `agents` | `archived` | `Boolean` | NOT NULL DEFAULT FALSE | アーカイブ状態 |
| `agent_providers` | `agent_id` | `UUIDStr` | FK → `agents.id` ON DELETE CASCADE, NOT NULL | 所属 Agent |
| `agent_providers` | `provider_kind` | `String(32)` | NOT NULL（ProviderKind enum）| LLM プロバイダ |
| `agent_providers` | `model` | `String(80)` | NOT NULL | model 名 |
| `agent_providers` | `is_default` | `Boolean` | NOT NULL DEFAULT FALSE | 既定 provider |
| `agent_providers` UNIQUE | `(agent_id, provider_kind)` | — | — | 同 Agent 内で provider_kind 重複禁止 |
| `agent_providers` partial unique | `(agent_id) WHERE is_default = 1` | — | — | **§確定 R1-D 二重防衛** |
| `agent_skills` | `agent_id` | `UUIDStr` | FK → `agents.id` ON DELETE CASCADE, NOT NULL | 所属 Agent |
| `agent_skills` | `skill_id` | `UUIDStr` | NOT NULL | SkillId |
| `agent_skills` | `name` | `String(80)` | NOT NULL | SkillRef.name |
| `agent_skills` | `path` | `String(500)` | NOT NULL | SkillRef.path（H1〜H10 検証は VO 構築時に完了済み）|
| `agent_skills` UNIQUE | `(agent_id, skill_id)` | — | — | 同 Agent 内で skill_id 重複禁止 |

**masking 対象カラム**: `agents.prompt_body` のみ（`MaskedText`、§確定 R1-B）。その他 13 カラムは masking 対象なし、CI 三層防衛で「対象なし」を明示登録。

## ユーザー向けメッセージ一覧

該当なし — 理由: Repository は内部 API、ユーザー向けメッセージは application 層 / HTTP API 層が定義する（agent feature §確定 / `AgentService` の MSG-AG-NNN 系で扱う）。

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|----|------|----------------|---------|
| 該当なし | — | — | — |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | SQLAlchemy 2.x / Alembic / aiosqlite | pyproject.toml | uv | 既存（M2 永続化基盤）|
| Python 依存 | typing.Protocol | 標準ライブラリ | — | Python 3.12 標準 |
| ドメイン | `Agent` / `AgentId` / `EmpireId` / `Persona` / `ProviderConfig` / `ProviderKind` / `SkillRef` / `SkillId` / `Role` | `domain/agent/` / `domain/value_objects.py` | 内部 import | 既存（agent #17）|
| インフラ | `Base` / `UUIDStr` / `MaskedText` / `MaskingGateway` | `infrastructure/persistence/sqlite/base.py` / `infrastructure/security/masking.py` | 内部 import | 既存（M2 永続化基盤、persistence-foundation #23 で `MaskedText` の TypeDecorator + Schneier #3 hook 構造提供済み）|
| インフラ | `AsyncSession` / `async_sessionmaker` | `infrastructure/persistence/sqlite/session.py` | 内部 import | 既存 |
| 外部サービス | 該当なし | — | — | infrastructure 層、外部通信なし |
