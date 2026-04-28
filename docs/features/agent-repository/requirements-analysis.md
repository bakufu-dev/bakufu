# 要求分析書

> feature: `agent-repository`
> Issue: [#32 feat(agent-repository): Agent SQLite Repository (M2, 0004, Schneier #3 実適用)](https://github.com/bakufu-dev/bakufu/issues/32)
> 関連: [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源**（§確定 A〜F + §Known Issues §BUG-EMR-001 規約） / [`docs/features/workflow-repository/`](../workflow-repository/) **2 件目テンプレート**（masking 対象あり版で正のチェック CI 三層防衛 + `migration-plan.md` 流入元の先例） / [`docs/features/agent/`](../agent/) （domain 設計済み、PR #17 マージ済み）

## 人間の要求

> Issue #32:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の後続 Repository PR（empire-repository #25 のテンプレート責務継承）。**Agent Aggregate** の SQLite 永続化を実装する。Alembic revision **0004_agent_aggregate** で `agents` / `agent_providers` / `agent_skills` の 3 テーブルを追加。**Schneier 申し送り #3（`Persona.prompt_body` Repository マスキング）の実適用が本 PR の核心**。

## 背景・目的

### 現状の痛点

1. M2 永続化基盤（PR #23）+ empire-repository（PR #29 / #30）+ workflow-repository（PR #41 マージ済み）が 3 件 chain で揃ったが、Agent は domain 層（PR #17）が完了していても **`Persona.prompt_body` の永続化経路がない**。MVP 核心ユースケース「CEO directive → Task → Agent が成果物 commit」のうち Agent 側の Repository が塞がれている
2. **Schneier 申し送り #3**: persistence-foundation PR #23 で `MaskedText` の TypeDecorator 構造は提供されたが、`Persona.prompt_body` への**実適用**は agent-repository PR で行うとして hook 構造のみ凍結。本 PR で実適用に移行しないと「Persona に API key / GitHub PAT が混入したらマスキングされない」状態が継続する
3. agent feature §確定 R1-B で「`name` の Empire 内一意は application 層責務（`AgentService.hire()` で検査）」と凍結したが、Repository に `find_by_name(empire_id, name)` を追加しないと application 層の検査経路が成立しない。**empire-repo の 3 method（find_by_id / count / save）を超える初の Repository PR**
4. agent feature §確定 K で `providers` の `is_default == True` は 1 件のみという Aggregate 不変条件を凍結したが、**DB レベル制約（partial unique index）**を張らないと「Repository が壊れた行を返したときに Aggregate 構築で初めて気づく」二重防衛の物理保証が抜ける

### 解決されれば変わること

- `feature/dispatcher` / `feature/llm-adapter`（後続）が Agent を `AgentRepository.find_by_id` で復元 → Persona / ProviderConfig / SkillRef を valid な状態で受け取れる
- application 層 `AgentService.hire(empire_id, name, ...)` が `find_by_name(empire_id, name)` で重複検査 → Empire 内一意性を保証
- Persona.prompt_body に CEO が誤って API key / GitHub PAT を貼り付けても DB には `<REDACTED:ANTHROPIC_KEY>` / `<REDACTED:GITHUB_PAT>` で永続化、ログ・監査経路への流出を防ぐ（**Schneier 申し送り #3 完了**）
- empire-repo / workflow-repo に続く **3 件目のテンプレート** として、後続 4 件 Repository PR（room / directive / task / external-review-gate-repository）が `find_by_name` 系の追加 method パターンを真似できる経路が確立

### ビジネス価値

- bakufu の核心思想「AI 協業」の主体である Agent を**安全に永続化**する。Persona に CEO が貼り付けたシステムプロンプトに secret が混入する経路を物理的に塞ぐ（Defense in Depth、persistence-foundation §シークレットマスキング規則の Repository 経路実適用）
- `find_by_name` 第 4 method の追加で「Aggregate 不変条件のうち DB SELECT を要する集合知識（Empire 内一意）」を application 層で安全に検査できる Repository 契約のテンプレートを確立

## 議論結果

### 設計担当による採用前提

- empire-repository PR #29 / #30 §確定 A〜F + §Known Issues §BUG-EMR-001 規約を **100% 継承**
- workflow-repository PR #41 §確定 G〜J + §確定 E（CI 三層防衛で **正のチェック導入**）を継承（masking 対象あり版テンプレート）
- Aggregate Root: Agent、3 テーブル: `agents` / `agent_providers` / `agent_skills`
- Alembic revision: `0004_agent_aggregate`、`down_revision="0003_workflow_aggregate"`（chain 一直線）
- masking 対象カラム: **`agents.prompt_body` のみ**（`MaskedText`、Schneier #3 実適用）
- find_by_id 子テーブル SELECT は `ORDER BY provider_kind` / `ORDER BY skill_id`（§Known Issues §BUG-EMR-001 規約）
- save() は delete-then-insert で 3 テーブル（empire-repo §確定 B 踏襲、5 段階手順 → Agent では 5 段階に拡張: agents UPSERT + agent_providers DELETE/INSERT + agent_skills DELETE/INSERT）
- count() は SQL `COUNT(*)`（empire-repo §確定 D 踏襲）

### 却下候補と根拠

| 候補 | 却下理由 |
|---|---|
| `agents.prompt_body` を `JSONEncoded` で保存（masking なし）+ application 層でマスキング | application 層実装漏れで raw 永続化リスク、Schneier 申し送り #3 違反。`MaskedText` 強制 |
| `agents.name` に DB レベル UNIQUE 制約 (`UNIQUE(empire_id, name)`) を張る | empire feature §確定 R1-B で「name は application 層責務」と凍結済み。DB UNIQUE を張ると application 層の MSG-AG-NNN を出す前に IntegrityError が raise され、ユーザー向けメッセージが汚れる。`find_by_name` で application 層検査の経路を残す |
| `is_default` partial unique index は使わず application 層検査のみ | Aggregate 内不変条件 + application 層検査のみだと、Repository が壊れた行を返した場合の最終防衛線が抜ける。SQLite `CREATE UNIQUE INDEX ... WHERE is_default = 1` で**二重防衛** |
| `agent_skills` テーブルで `path` カラムに正規表現 CHECK 制約 | SkillRef.path の H1〜H10 検証は domain VO 構築時に既に走っている（agent feature §確定 H 凍結済み）。Repository は valid な SkillRef のみ受け取る契約、DB レベル CHECK は冗長で portability も下がる |
| `find_by_name(empire_id, name) -> Agent \| None` を Protocol に追加せず application 層が `find_by_id` を全件 SELECT して filter | N+1 / 全件ロードで MVP の数十 Agent は耐えられるが、後続 PR が「ある Empire の全 Agent を一覧」で同パターンを真似すると数千 Agent でメモリ枯渇。empire-repo §確定 D の `count()` 教訓と同じ理由で **SQL レベル WHERE で済ませる** |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: empire / workflow テンプレート 100% 継承（再凍結）

| 継承項目 | 本 PR への適用 |
|---|---|
| empire §確定 A | `application/ports/agent_repository.py` 新規、Protocol、`@runtime_checkable` なし |
| empire §確定 B | save() で agents UPSERT + agent_providers DELETE/INSERT + agent_skills DELETE/INSERT、Repository 内 commit/rollback なし |
| empire §確定 C | `_to_row` / `_from_row` を private method に閉じる |
| empire §確定 D | `count()` は SQL `COUNT(*)` 限定 |
| empire §確定 E | CI 三層防衛 Layer 1 + Layer 2 + Layer 3 全部に Agent 3 テーブル明示登録 |
| empire §Known Issues §BUG-EMR-001 規約 | `find_by_id` 子テーブル SELECT は `ORDER BY provider_kind` / `ORDER BY skill_id` 必須 |
| workflow §確定 E | **正のチェック CI 三層防衛**（`agents.prompt_body` の `MaskedText` 必須を grep + arch test で物理保証） |
| workflow §確定 J | DB FK 不採用論点は本 Aggregate にはなし（agent_providers / agent_skills は agent_id への FK CASCADE で循環なし）、ただし migration-plan.md 流入元の先例は踏襲（必要に応じて TODO-MIG-NNN を追記） |

#### 確定 R1-B: Schneier 申し送り #3 の実適用（本 PR の核心）

`agents.prompt_body` カラムを **`MaskedText`** で宣言、`process_bind_param` で `MaskingGateway.mask()` 経由マスキング:

| 経路 | 動作 |
|---|---|
| `_to_row(agent)` | `agents_row['prompt_body'] = agent.persona.prompt_body`（raw 文字列） |
| `MaskedText.process_bind_param` | INSERT/UPDATE 直前に `MaskingGateway.mask(prompt_body)` を呼ぶ → `<REDACTED:*>` 化された文字列を DB に保存 |
| `_from_row(agent_row, ...)` | DB から masked 文字列を取得、`Persona(prompt_body=masked_string)` で復元（masking 不可逆性は workflow-repo §確定 H と同方針、復元時の元 token 復元は不可） |

**復元不可逆性の申し送り**: `find_by_id` で復元される Agent の `Persona.prompt_body` には masked 文字列が入る。Agent が LLM Adapter にこれを送ると `<REDACTED:*>` がそのまま prompt に流れ、LLM 出力品質が下がる経路が生じる。MVP では「CEO が再 hire する運用」で吸収、後続 `feature/llm-adapter` で「prompt_body に `<REDACTED:*>` を含む Agent はログ警告 + 配送停止」契約を凍結する申し送り（workflow-repo §確定 H 申し送り #1 と同パターン）。

#### 確定 R1-C: `find_by_name(empire_id, name) -> Agent | None` 第 4 method 追加

empire-repo の Protocol は 3 method（find_by_id / count / save）だが、本 PR で **第 4 method として `find_by_name` を追加**する:

| メソッド | 引数 | 戻り値 | 用途 |
|---|---|---|---|
| `find_by_name(empire_id: EmpireId, name: str) -> Agent \| None` | EmpireId + name 文字列 | 該当 Agent or None | application 層 `AgentService.hire()` の Empire 内一意検査 |

##### Empire スコープでの検索を必須とする理由

`name` 一意性は Empire 内（`(empire_id, name)` の複合一意）のため、`find_by_name(name)` だけでは不十分。`empire_id` も引数に取って `WHERE empire_id = :empire_id AND name = :name` で SELECT する。

##### 後続 Repository PR への申し送り（テンプレート責務）

本 §確定 R1-C は「Aggregate 不変条件のうち DB SELECT を要する集合知識（Empire 内一意 / Room 内一意 等）を Repository 第 4+ method として追加するテンプレート」を確立する。後続 PR が同パターンを採用する場合:

| 後続 PR 候補 | 想定される追加 method |
|---|---|
| `feature/room-repository` | `find_by_name(empire_id, name)` 同パターン |
| `feature/directive-repository` | `find_by_target_room_id(room_id, after: datetime)` 等の Room 別検索（業務要件次第） |
| `feature/task-repository`（Issue #35） | `find_blocked() -> list[Task]`（admin CLI `list-blocked` の経路）|

#### 確定 R1-D: `is_default` partial unique index による二重防衛

agent feature §確定 K で「`providers` のうち `is_default == True` は 1 件のみ」を Aggregate 内不変条件として凍結済み。本 PR で **DB レベル partial unique index** を追加して二重防衛:

```sql
CREATE UNIQUE INDEX uq_agent_providers_default
  ON agent_providers (agent_id)
  WHERE is_default = 1;
```

| 防衛層 | 検査内容 | 違反時 |
|---|---|---|
| Aggregate 内（既存）| `_validate_provider_is_default_unique` で list を走査 | `AgentInvariantViolation(kind='default_provider_uniqueness')` |
| **DB partial unique index（本 PR 新規）** | INSERT/UPDATE で `WHERE is_default=1` の集合に違反する行が来たら IntegrityError | `sqlalchemy.IntegrityError`、application 層が catch して 500 にマッピング（データ破損として扱う） |

##### partial unique index を選ぶ根拠

| 採用 | 不採用 | 理由 |
|---|---|---|
| **partial unique index** (`UNIQUE WHERE is_default = 1`) | フル UNIQUE 制約 (`UNIQUE(agent_id, is_default)`) | フル UNIQUE は `is_default=False` の行が複数あったとき重複を許せない（`(agent_a, False)` を 2 件持てなくなる）。partial で「True の行に限る」が正解 |
| | アプリ層検査のみ | Aggregate 内検査が壊れた場合の最終防衛線が消える、Defense in Depth 違反 |

SQLite は partial index をサポート（[公式ドキュメント](https://www.sqlite.org/partialindex.html)）。Alembic は `op.create_index('...', '...', ['agent_id'], unique=True, sqlite_where=sa.text('is_default = 1'))` で生成可能。

#### 確定 R1-E: storage.md 逆引き表更新（Schneier #3 実適用の物理保証）

`docs/design/domain-model/storage.md` §逆引き表に Agent 関連 2 行追加:

| 行 | 内容 |
|---|---|
| `agents.prompt_body` | `MaskedText`、Schneier 申し送り #3 **実適用**、persistence-foundation #23 で hook 構造提供済みを本 PR で配線 |
| `agents` 残カラム + `agent_providers` 全カラム + `agent_skills` 全カラム | masking 対象なし（`UUIDStr` / `String` / `Boolean` / `Integer` のみ。CI Layer 2 で `MaskedText` でないことを arch test で保証）|

storage.md §逆引き表の既存 `Persona.prompt_body` 行（persistence-foundation #23 時点で「`feature/agent-repository`（後続）」と表記）を **本 PR で配線済みに更新**する責務。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 個人開発者 CEO（堀川さん想定） | Agent を Web UI / CLI で hire | GitHub / Docker / CLI 日常使用 | UI で「Senior Backend Engineer」persona の Agent を hire → DB 永続化 → Dispatcher が復元して LLM Adapter 経由で起動 | Persona / Provider / Skills を一度設定すれば永続化される |
| 後続 Issue 担当（バックエンド開発者） | `feature/dispatcher` / `feature/llm-adapter` 実装者 | DDD 経験あり、SQLAlchemy 2.x async / Pydantic v2 経験あり | 本 PR の設計書を真実源として読み、Agent 復元経路を実装 | empire-repo / workflow-repo / 本 PR テンプレートを直接参照して同パターンで Repository を増やせる |
| セキュリティレビュワー（Schneier 想定） | persistence-foundation #23 の Schneier 申し送り #3 を本 PR で完了確認 | secret マスキング Defense in Depth | `agents.prompt_body` カラムが `MaskedText` で宣言、SQL 直読みで raw token が出ないことを物理確認 | 永続化前マスキングの単一ゲートウェイが Agent 経路でも機能、ログ・監査経路に raw 流出しない |

##### ペルソナ別ジャーニー（個人開発者 CEO）

1. **Agent 設定**: UI で persona / providers / skills を入力 → `AgentService.hire(empire_id, name, persona, providers, skills)` を呼ぶ
2. **Empire 内一意検査**: application 層 `AgentService.hire()` が `AgentRepository.find_by_name(empire_id, name)` を呼び、None なら新規作成、既存なら `AgentNameAlreadyExistsError` で 409 Conflict
3. **永続化**: `AgentRepository.save(agent)` → SQLite に書き込み（`agents.prompt_body` は `MaskedText` 経由で masking 適用、CEO が persona に API key を含めても `<REDACTED:*>` 化）
4. **Dispatcher 起動時**: `AgentRepository.find_by_id(agent_id)` で復元 → `Persona.prompt_body` には masked 文字列、LLM Adapter 配送時に警告経路（後続 feature 責務、申し送り）

##### ジャーニーから逆算した受入要件

- ジャーニー 2: `find_by_name(empire_id, name) -> Agent | None` が Empire スコープで動作（§確定 R1-C）
- ジャーニー 3: `agents.prompt_body` に raw API key を渡しても DB には `<REDACTED:ANTHROPIC_KEY>` で永続化（§確定 R1-B、Schneier #3 実適用）
- ジャーニー 4: `find_by_id` で復元される Agent は valid（Pydantic 構築通過）、ただし `Persona.prompt_body` は masked 文字列（不可逆性、後続 LLM Adapter 警告経路の申し送り）

## 前提条件・制約

| 区分 | 内容 |
|-----|------|
| 既存技術スタック | Python 3.12+ / SQLAlchemy 2.x async / Alembic / aiosqlite / Pydantic v2 / pyright strict / pytest |
| 既存 CI | lint / typecheck / test-backend / audit |
| 既存ブランチ戦略 | GitFlow（CONTRIBUTING.md §ブランチ戦略） |
| コミット規約 | Conventional Commits |
| ライセンス | MIT |
| ネットワーク | 該当なし — infrastructure 層、外部通信なし |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |

## 機能一覧

| 機能ID | 機能名 | 概要 | 優先度 |
|--------|-------|------|--------|
| REQ-AGR-001 | AgentRepository Protocol 定義 | `application/ports/agent_repository.py` で 4 method（find_by_id / count / save / find_by_name）を `async def` で宣言 | 必須 |
| REQ-AGR-002 | SqliteAgentRepository 実装 | `infrastructure/persistence/sqlite/repositories/agent_repository.py` で SQLite 実装、§確定 R1-A〜D を満たす | 必須 |
| REQ-AGR-003 | Alembic 0004 revision | `0004_agent_aggregate.py` で 3 テーブル + UNIQUE 制約 + partial unique index 追加、`down_revision="0003_workflow_aggregate"` | 必須 |
| REQ-AGR-004 | CI 三層防衛の Agent 拡張 | Layer 1 grep guard（agents.prompt_body 行に `MaskedText` 必須、正のチェック）+ Layer 2 arch test + Layer 3 storage.md 更新 | 必須 |
| REQ-AGR-005 | storage.md 逆引き表更新 | Agent 関連 2 行追加（§確定 R1-E） | 必須 |

## Sub-issue 分割計画

本 Issue は単一 Aggregate Repository に閉じる粒度のため Sub-issue 分割は不要。1 PR で 5 設計書 + 実装 + ユニットテストを完結させる（empire-repo / workflow-repo と同方針）。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 単一 PR | REQ-AGR-001〜005 | Agent SQLite Repository + ユニットテスト + storage.md 更新 | M1 agent（PR #17）+ M2 永続化基盤（PR #23）+ empire-repo（PR #29/#30）+ workflow-repo（PR #41）マージ済み |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | `count()` は O(1) SQL `COUNT(*)`。`find_by_id` は子テーブル含めて O(1) Tx で 3 SELECT。`find_by_name` は `(empire_id, name)` で SELECT、index 必要なら別 PR |
| 可用性 | 該当なし — infrastructure 層 |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 95% 以上（empire-repo / workflow-repo 実績水準） |
| 可搬性 | SQLite 単一前提、Postgres 移行時は migration-plan.md §TODO-MIG-NNN として追記 |
| セキュリティ | `agents.prompt_body` の API key / GitHub PAT を `MaskedText` で永続化前マスキング（Schneier 申し送り #3 実適用）。CI 三層防衛で物理保証。詳細は [`threat-model.md`](../../design/threat-model.md) §A02 / §A09 |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | `AgentRepository` Protocol が 4 method（find_by_id / count / save / find_by_name）を `async def` で定義、`@runtime_checkable` なし | TC-UT-AGR-001 |
| 2 | `SqliteAgentRepository` が Protocol を型レベルで満たす（pyright strict） | CI typecheck |
| 3 | `save(agent)` が agents UPSERT + agent_providers DELETE/INSERT + agent_skills DELETE/INSERT を同一 Tx 内で実行 | TC-UT-AGR-002 |
| 4 | `find_by_id` の子テーブル SELECT が `ORDER BY provider_kind` / `ORDER BY skill_id` を発行（§BUG-EMR-001 規約） | TC-UT-AGR-003 |
| 5 | `count()` が SQL `COUNT(*)` を発行（全行ロード+ Python `len()` 禁止） | TC-UT-AGR-004 |
| 6 | `find_by_name(empire_id, name)` が `WHERE empire_id=:empire_id AND name=:name` で SELECT、不在なら None | TC-UT-AGR-005 |
| 7 | `agents.prompt_body` が `MaskedText` で宣言、raw API key を保存しても DB には `<REDACTED:ANTHROPIC_KEY>` で永続化（Schneier #3 実適用） | TC-IT-AGR-006-masking |
| 8 | `agent_providers` の partial unique index `WHERE is_default=1` が DB レベルで一意性を保証（同 agent_id で is_default=True が 2 件あったら IntegrityError） | TC-IT-AGR-007 |
| 9 | Alembic 0004 revision で 3 テーブル + UNIQUE 制約 + partial unique index が SQLite に作成される | TC-IT-AGR-008 |
| 10 | CI 三層防衛 Layer 1（grep guard で agents.prompt_body の `MaskedText` 必須）+ Layer 2（arch test）+ Layer 3（storage.md 更新）が pass | CI ジョブ |
| 11 | `pyright --strict` および `ruff check` がエラーゼロ | CI lint / typecheck |
| 12 | カバレッジが Agent Repository 配下で 95% 以上 | pytest --cov |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| `agents.prompt_body` | Persona の自然言語、システムプロンプトに展開される | **高**（API key / GitHub PAT が混入し得る、Schneier #3 実適用、`MaskedText` 配線必須） |
| `agents.id` / `empire_id` / `name` / `archetype` / `display_name` / `role` / `archived` | 識別子・表示名・enum・bool | 低 |
| `agent_providers.*`（provider_kind / model / is_default） | LLM 設定 | 低（model 名は ASCII 識別子、secret なし） |
| `agent_skills.*`（skill_id / name / path） | Skill ファイル参照 | 低（path は `BAKUFU_DATA_DIR/skills/` 内、H1〜H10 検証で path traversal 防御済み） |
