# 基本設計書

> feature: `agent-repository`
> 関連: [requirements.md](requirements.md) / [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源** / [`docs/features/workflow-repository/`](../workflow-repository/) **2 件目テンプレート** / [`docs/features/agent/`](../agent/)

## 記述ルール（必ず守ること）

基本設計に**疑似コード・サンプル実装（python/ts/sh/yaml 等の言語コードブロック）を書かない**。
ソースコードと二重管理になりメンテナンスコストしか生まない。
必要なのは構造契約（クラス・モジュール・データの関係）であり、実装の細部は [detailed-design.md](detailed-design.md) で凍結する。

## モジュール構成

| 機能 ID | モジュール | ディレクトリ | 責務 |
|--------|----------|------------|------|
| REQ-AGR-001 | `AgentRepository` Protocol | `backend/src/bakufu/application/ports/agent_repository.py` | Repository ポート定義（4 method、empire-repo の 3 method + 第 4 method `find_by_name`、§確定 R1-C） |
| REQ-AGR-002 | `SqliteAgentRepository` | `backend/src/bakufu/infrastructure/persistence/sqlite/repositories/agent_repository.py` | SQLite 実装、§確定 R1-A〜D |
| REQ-AGR-003 | Alembic 0004 revision | `backend/alembic/versions/0004_agent_aggregate.py` | 3 テーブル + UNIQUE + partial unique index 追加、`down_revision="0003_workflow_aggregate"` |
| REQ-AGR-004 | CI 三層防衛拡張 Layer 1 | `scripts/ci/check_masking_columns.sh`（既存ファイル更新）| Agent 3 テーブル明示登録、`agents.prompt_body` の `MaskedText` 必須を assert（正のチェック）|
| REQ-AGR-004 | CI 三層防衛拡張 Layer 2 | `backend/tests/architecture/test_masking_columns.py`（既存ファイル更新）| parametrize に Agent 3 テーブル追加 |
| REQ-AGR-005 | storage.md 逆引き表更新 | `docs/architecture/domain-model/storage.md`（既存ファイル更新）| Agent 関連 2 行追加（既存 `Persona.prompt_body` 行を本 PR で実適用済みに更新） |
| 共通 | tables/agents.py / agent_providers.py / agent_skills.py | `backend/src/bakufu/infrastructure/persistence/sqlite/tables/` | 新規 3 ファイル |

```
ディレクトリ構造（本 feature で追加・変更されるファイル）:

.
├── backend/
│   ├── alembic/
│   │   └── versions/
│   │       └── 0004_agent_aggregate.py             # 新規: 3 テーブル + UNIQUE + partial unique index
│   ├── src/
│   │   └── bakufu/
│   │       ├── application/
│   │       │   └── ports/
│   │       │       └── agent_repository.py         # 新規: Protocol（4 method）
│   │       └── infrastructure/
│   │           └── persistence/
│   │               └── sqlite/
│   │                   ├── repositories/
│   │                   │   └── agent_repository.py # 新規: SqliteAgentRepository
│   │                   └── tables/
│   │                       ├── agents.py           # 新規（prompt_body は MaskedText、Schneier #3 実適用）
│   │                       ├── agent_providers.py  # 新規（partial unique index WHERE is_default=1）
│   │                       └── agent_skills.py     # 新規
│   └── tests/
│       ├── infrastructure/
│       │   └── persistence/
│       │       └── sqlite/
│       │           └── repositories/
│       │               └── test_agent_repository/   # 新規ディレクトリ（500 行ルール、最初から分割）
│       │                   ├── __init__.py
│       │                   ├── test_protocol_crud.py
│       │                   ├── test_save_semantics.py
│       │                   ├── test_constraints_arch.py
│       │                   └── test_masking_persona.py  # Schneier #3 実適用専用テスト
│       └── architecture/
│           └── test_masking_columns.py             # 既存更新: Agent 3 テーブル parametrize 追加
├── scripts/
│   └── ci/
│       └── check_masking_columns.sh                # 既存更新: Agent 3 テーブル明示登録
└── docs/
    ├── architecture/
    │   └── domain-model/
    │       └── storage.md                          # 既存更新: 逆引き表に Agent 行追加
    └── features/
        └── agent-repository/                       # 本 feature 設計書 5 本
```

## クラス設計（概要）

```mermaid
classDiagram
    class AgentRepository {
        <<Protocol>>
        +async find_by_id(agent_id) Agent | None
        +async count() int
        +async save(agent) None
        +async find_by_name(empire_id, name) Agent | None
    }
    class SqliteAgentRepository {
        +session: AsyncSession
        +async find_by_id(agent_id) Agent | None
        +async count() int
        +async save(agent) None
        +async find_by_name(empire_id, name) Agent | None
        -_to_row(agent) tuple
        -_from_row(agent_row, provider_rows, skill_rows) Agent
    }
    class Agent {
        <<Aggregate Root>>
        +id: AgentId
        +empire_id: EmpireId
        +name: str
        +role: Role
        +persona: Persona
        +providers: list~ProviderConfig~
        +skills: list~SkillRef~
        +archived: bool
    }

    SqliteAgentRepository ..|> AgentRepository : implements
    SqliteAgentRepository --> Agent : returns
    AgentRepository ..> Agent : returns
```

**凝集のポイント**:

- `AgentRepository` Protocol は application 層、domain は知らない（empire-repo §確定 A）
- `SqliteAgentRepository` は infrastructure 層、Protocol を型レベルで満たす
- domain ↔ row 変換は `_to_row()` / `_from_row()` の private method（empire-repo §確定 C）
- `save()` は同一 Tx 内で 3 テーブル delete-then-insert（empire-repo §確定 B、Agent では 5 段階手順）
- 呼び出し側 service が `async with session.begin():` で UoW 境界を管理
- **`find_by_name(empire_id, name)` は第 4 method**、Empire スコープ検索（§確定 R1-C）

## 処理フロー

### ユースケース 1: Agent の新規 hire（save 経路、`AgentService.hire()` 起点）

1. application 層 `AgentService.hire(empire_id, name, persona, providers, skills)` を呼ぶ（本 PR スコープ外、別 PR）
2. application 層が `AgentRepository.find_by_name(empire_id, name)` で重複検査 → None なら新規作成、既存なら `AgentNameAlreadyExistsError` で 409
3. `Agent(id=uuid4(), empire_id=..., name=name, persona=..., providers=..., skills=..., archived=False)` を構築（pre-validate）
4. service が `async with session.begin():` で UoW 境界を開く
5. service が `AgentRepository.save(agent)` を呼ぶ
6. `SqliteAgentRepository.save(agent)` が以下を順次実行（同一 Tx 内、5 段階）:
   - `_to_row(agent)` で `agents_row` / `provider_rows` / `skill_rows` に分離
   - agents UPSERT（`prompt_body` は `MaskedText` 経由で `MaskingGateway.mask()` 適用、Schneier #3 実適用）
   - agent_providers DELETE → bulk INSERT（partial unique index `WHERE is_default=1` が DB レベル一意性を保証）
   - agent_skills DELETE → bulk INSERT
7. `session.begin()` ブロック退出で commit

### ユースケース 2: Agent の取得（find_by_id 経路）

1. application 層が `AgentRepository.find_by_id(agent_id)` を呼ぶ
2. `SqliteAgentRepository.find_by_id(agent_id)` が以下を実行:
   - `SELECT * FROM agents WHERE id = :agent_id`（不在なら None）
   - `SELECT * FROM agent_providers WHERE agent_id = :agent_id ORDER BY provider_kind`（§BUG-EMR-001 規約）
   - `SELECT * FROM agent_skills WHERE agent_id = :agent_id ORDER BY skill_id`（同上）
   - `_from_row(agent_row, provider_rows, skill_rows)` で Agent 復元（**`prompt_body` は masked 文字列のまま** で `Persona` 構築、不可逆性、申し送り）
3. valid な Agent を返却（pre-validate 通過）

### ユースケース 3: Agent の Empire 内一意検索（find_by_name 経路、§確定 R1-C）

1. application 層 `AgentService.hire()` 内で `AgentRepository.find_by_name(empire_id, name)` を呼ぶ
2. `SqliteAgentRepository.find_by_name(empire_id, name)`:
   - `SELECT id FROM agents WHERE empire_id = :empire_id AND name = :name LIMIT 1`
   - 不在なら None
   - 存在すれば `find_by_id(found_id)` を呼んで子テーブル含めて Agent を復元
3. application 層が結果で重複判定（None → 新規作成可、Agent → 409）

### ユースケース 4: Agent の更新（save 経路、persona 変更等）

1. application 層が `find_by_id(agent_id)` で既存 Agent を取得
2. service が Agent のドメイン操作（例: `agent.set_default_provider(...)` / persona 変更で再構築）で新 Agent を構築（pre-validate 方式、agent #17 で凍結）
3. service が `AgentRepository.save(updated_agent)` を呼ぶ
4. ユースケース 1 と同じ手順で同一 Tx 内に delete-then-insert

### ユースケース 5: Agent 件数取得（count 経路）

1. application 層が `AgentRepository.count()` を呼ぶ
2. `SqliteAgentRepository.count()` が `select(func.count()).select_from(AgentRow)` で SQL `COUNT(*)` 発行（empire-repo §確定 D 踏襲）
3. `scalar_one()` で `int` 取得

## シーケンス図

```mermaid
sequenceDiagram
    participant Svc as AgentService（別 PR）
    participant Repo as SqliteAgentRepository
    participant Sess as AsyncSession
    participant Mask as MaskedText
    participant DB as SQLite

    Svc->>Repo: find_by_name(empire_id, name)
    Repo->>Sess: SELECT id FROM agents WHERE empire_id=? AND name=? LIMIT 1
    Sess->>DB: SQL
    DB-->>Sess: row or empty
    Sess-->>Repo: AgentId or None
    Repo-->>Svc: Agent or None（None なら新規作成可）

    Svc->>Sess: async with session.begin():
    Svc->>Repo: save(agent)
    Repo->>Repo: _to_row(agent)
    Repo->>Sess: INSERT INTO agents ON CONFLICT UPDATE (prompt_body bind)
    Sess->>Mask: process_bind_param(prompt_body)
    Mask-->>Sess: masked str（API key → <REDACTED:ANTHROPIC_KEY>）
    Sess->>DB: SQL
    Repo->>Sess: DELETE FROM agent_providers WHERE agent_id=?
    Sess->>DB: SQL
    Repo->>Sess: INSERT INTO agent_providers bulk (partial unique index 検査)
    Sess->>DB: SQL（is_default=True が複数あれば IntegrityError）
    Repo->>Sess: DELETE FROM agent_skills WHERE agent_id=?
    Sess->>DB: SQL
    Repo->>Sess: INSERT INTO agent_skills bulk
    Sess->>DB: SQL
    Repo-->>Svc: ok
    Svc->>Sess: session.begin() 退出 → commit
    Sess->>DB: COMMIT
```

## アーキテクチャへの影響

- `docs/architecture/domain-model.md` への変更: なし
- `docs/architecture/domain-model/storage.md` への変更: **§逆引き表に Agent 関連 2 行追加 + 既存 `Persona.prompt_body` 行を本 PR で実適用済みに更新**（§確定 R1-E、本 PR で同一コミット）
- `docs/architecture/migration-plan.md` への変更: なし（Agent は Postgres 移行論点なし、本 Aggregate の FK 構造に循環なし）
- `docs/architecture/tech-stack.md` への変更: なし
- 既存 feature への波及:
  - `feature/persistence-foundation`（PR #23）の `MaskedText` TypeDecorator + Schneier #3 hook 構造の上に乗る、本 PR で実適用配線
  - `feature/empire-repository`（PR #29 / #30）+ `feature/workflow-repository`（PR #41）テンプレート踏襲
  - `feature/agent`（PR #17）の domain 層 Agent / Persona / ProviderConfig / SkillRef を import するのみ、agent 設計書は変更しない

## 外部連携

該当なし — 理由: infrastructure 層に閉じる。

| 連携先 | 目的 | プロトコル | 認証 | タイムアウト / リトライ |
|-------|------|----------|-----|--------------------|
| 該当なし | — | — | — | — |

## UX 設計

該当なし — 理由: UI を持たない infrastructure 層。

| シナリオ | 期待される挙動 |
|---------|------------|
| 該当なし | — |

**アクセシビリティ方針**: 該当なし。

## セキュリティ設計

### 脅威モデル

詳細な信頼境界は [`docs/architecture/threat-model.md`](../../architecture/threat-model.md)。本 feature 範囲では以下の 3 件。

| 想定攻撃者 | 攻撃経路 | 保護資産 | 対策 |
|-----------|---------|---------|------|
| **T1: `agents.prompt_body` 経由の API key / GitHub PAT 漏洩**（Schneier #3 中核）| CEO が persona 設計時に prompt_body に「`環境変数 ANTHROPIC_API_KEY=sk-ant-...` を使え」と書く → Repository 経由で永続化 → DB 直読み / バックアップ / 監査ログ経路で token 流出 | API key / GitHub PAT / OAuth token | `agents.prompt_body` を **`MaskedText`** で宣言、`process_bind_param` で `MaskingGateway.mask()` 経由マスキング（`<REDACTED:ANTHROPIC_KEY>` / `<REDACTED:GITHUB_PAT>` 化）。**Schneier 申し送り #3 の実適用**。CI 三層防衛 Layer 1 + Layer 2 で `MaskedText` 必須を物理保証 |
| **T2: `is_default` 複数違反でデータ破損**（partial unique index による二重防衛）| Aggregate 内 `_validate_provider_is_default_unique` を迂回する経路（直 SQL 流入 / マイグレーション失敗 等）で `is_default=True` が複数行 INSERT される → Aggregate 復元時に valid 判定が壊れて非決定的挙動 | Agent の整合性 | DB レベル **partial unique index** (`UNIQUE WHERE is_default = 1`) で INSERT/UPDATE を物理拒否 → IntegrityError、application 層が catch して 500 にマッピング（§確定 R1-D 二重防衛） |
| **T3: 永続化 Tx の半端終了による参照整合性破損** | `save()` 中に SQLite クラッシュ → `agent_providers` 行のみ INSERT されて `agent_skills` が DELETE のみで終了 | Agent の整合性 | 同一 Tx 内の delete-then-insert（empire-repo §確定 B）+ M2 永続化基盤の WAL crash safety + foreign_keys ON。Tx 全体が ATOMIC、半端終了で rollback |

### OWASP Top 10 対応

| # | カテゴリ | 対応状況 |
|---|---------|---------|
| A01 | Broken Access Control | 該当なし（infrastructure 層、認可は別 feature） |
| A02 | Cryptographic Failures | **適用**: `agents.prompt_body` の API key / GitHub PAT を `MaskedText` で永続化前マスキング（**Schneier #3 実適用**） |
| A03 | Injection | **適用**: SQLAlchemy ORM 経由で SQL injection 防御。raw SQL は使わない |
| A04 | Insecure Design | **適用**: Repository ポート分離 + delete-then-insert + partial unique index による二重防衛 |
| A05 | Security Misconfiguration | M2 永続化基盤の PRAGMA 強制の上に乗る |
| A06 | Vulnerable Components | SQLAlchemy 2.x / Alembic / aiosqlite |
| A07 | Auth Failures | 該当なし |
| A08 | Data Integrity Failures | **適用**: foreign_keys ON + ON DELETE CASCADE で参照整合性、Tx 原子性、partial unique index で `is_default` 二重防衛 |
| A09 | Logging Failures | **適用**: `agents.prompt_body` のマスキングにより SQL ログ / 監査ログ経路で token 漏洩なし（Schneier #3 実適用の二次効果）|
| A10 | SSRF | 該当なし（外部 URL fetch なし）|

## ER 図

```mermaid
erDiagram
    AGENTS {
        UUIDStr id PK
        UUIDStr empire_id FK
        String name "1〜40 文字、Empire 内一意 (application 層責務)"
        String role "Role enum"
        String display_name "Persona.display_name"
        String archetype "Persona.archetype"
        MaskedText prompt_body "Schneier #3 実適用、API key / GitHub PAT マスキング"
        Boolean archived "DEFAULT FALSE"
    }
    AGENT_PROVIDERS {
        UUIDStr agent_id FK
        String provider_kind "ProviderKind enum (CLAUDE_CODE / CODEX / ...)"
        String model
        Boolean is_default "DEFAULT FALSE"
    }
    AGENT_SKILLS {
        UUIDStr agent_id FK
        UUIDStr skill_id "SkillId"
        String name "SkillRef.name"
        String path "SkillRef.path (H1〜H10 検証は VO 構築時)"
    }
    EMPIRES ||--o{ AGENTS : "has 0..N agents (CASCADE)"
    AGENTS ||--o{ AGENT_PROVIDERS : "has 1..N providers (CASCADE)"
    AGENTS ||--o{ AGENT_SKILLS : "has 0..N skills (CASCADE)"
```

UNIQUE 制約:

- `agent_providers(agent_id, provider_kind)`: 同 Agent 内で provider_kind 重複禁止
- `agent_providers (agent_id) WHERE is_default = 1`: **partial unique index、§確定 R1-D**
- `agent_skills(agent_id, skill_id)`: 同 Agent 内で skill_id 重複禁止

masking 対象カラム: `agents.prompt_body` のみ（`MaskedText`、§確定 R1-B）。CI 三層防衛で物理保証。

## エラーハンドリング方針

| 例外種別 | 処理方針 | ユーザーへの通知 |
|---------|---------|----------------|
| `sqlalchemy.IntegrityError`（FK / UNIQUE / partial unique index 違反）| application 層に伝播、HTTP API 層で 409 Conflict | application 層 / HTTP API の MSG（別 feature） |
| `sqlalchemy.OperationalError`（接続切断、ロック timeout）| application 層に伝播、HTTP API 層で 503 | 同上 |
| `pydantic.ValidationError`（domain Agent 構築時、`_from_row` 内で発生し得る）| Repository 内で catch せず application 層に伝播、データ破損として扱う | application 層 / HTTP API の MSG |
| その他 | 握り潰さない、application 層へ伝播 | 汎用エラーメッセージ |

**Repository 内で明示的な commit / rollback はしない**: 呼び出し側 service が `async with session.begin():` で UoW 境界を管理（empire-repo §確定 B 踏襲）。
