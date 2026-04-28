# テスト設計書

<!-- feature: agent / sub-feature: repository -->
<!-- 配置先: docs/features/agent/repository/test-design.md -->
<!-- 対象範囲: REQ-AGR-001〜005 / feature-spec.md §9 受入基準 #4（DB二重防衛）#10〜#12 / 詳細設計 §確定 A〜I / Schneier #3 実適用物理確認 -->

本 feature は M2 永続化基盤の上で動く Agent Aggregate Repository。empire-repo (PR #29/#30) / workflow-repo (PR #41) と同じ規約で、**最初から 4 ファイル分割** で test を構成（Norman R-N1 教訓継承）。**`test_masking_persona.py` が Schneier #3 実適用の物理確認を担う本 PR 固有のテストファイル**。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-AGR-001 | `AgentRepository` Protocol 4 method 定義 | TC-UT-AGR-001 | ユニット | 正常系 | 10, 11, 12 |
| REQ-AGR-002（save） | `SqliteAgentRepository.save` の delete-then-insert | TC-UT-AGR-002 | ユニット | 正常系 | 10 |
| REQ-AGR-002（find_by_id ORDER BY） | 子テーブル SELECT の `ORDER BY provider_kind` / `ORDER BY skill_id` | TC-UT-AGR-003 | ユニット | 正常系 | 10 |
| REQ-AGR-002（count SQL）| `count()` が SQL `COUNT(*)` を発行 | TC-UT-AGR-004 | ユニット | 正常系 | — |
| REQ-AGR-002（find_by_name）| Empire スコープ検索 | TC-UT-AGR-005 | ユニット | 正常系 / 異常系 | 11 |
| **REQ-AGR-002（masking、§確定 R1-B / H）** | raw `prompt_body` → DB に `<REDACTED:*>` 永続化（**Schneier #3 実適用**）| TC-IT-AGR-006-masking-anthropic / TC-IT-AGR-006-masking-github / TC-IT-AGR-006-masking-roundtrip | 結合 | 正常系 | 12 |
| REQ-AGR-003（partial unique index）| `is_default=True` 重複で IntegrityError（内部品質基準: DB 二重防衛）| TC-IT-AGR-007 | 結合 | 異常系 | 4 |
| REQ-AGR-003（Alembic）| 0004 revision で 3 テーブル + 制約作成 | TC-IT-AGR-008 | 結合 | 正常系 | — |
| REQ-AGR-004（CI Layer 1）| grep guard で `agents.prompt_body` の `MaskedText` 必須 | （CI ジョブ） | — | — | 12 |
| REQ-AGR-004（CI Layer 2）| arch test parametrize | TC-UT-AGR-009-arch | ユニット | 正常系 | 12 |
| REQ-AGR-005（storage.md） | §逆引き表更新 | （手動レビュー）| — | — | 12 |
| 品質基準（lint/typecheck）| pyright strict / ruff | （CI ジョブ）| — | — | — |
| 品質基準（カバレッジ） | `pytest --cov=bakufu.infrastructure.persistence.sqlite.repositories.agent_repository` | （CI ジョブ）| — | — | — |
| 確定 A（テンプレ継承） | empire/workflow §確定 A〜F + §BUG-EMR-001 | TC-UT-AGR-001〜005 全件 | ユニット | — | — |
| 確定 B（5 段階 save） | DML 順序の物理確認 | TC-UT-AGR-002, TC-UT-AGR-010-sql-order | ユニット | 正常系 | 10 |
| 確定 C（_to_row / _from_row）| 双方向変換 | TC-UT-AGR-011-roundtrip | ユニット | 正常系 | 10 |
| 確定 D（count SQL） | `select(func.count())` の物理確認 | TC-UT-AGR-004 | ユニット | 正常系 | — |
| 確定 E（CI 三層防衛）| 正のチェック + 負のチェック併用 | TC-UT-AGR-009-arch | ユニット | 正常系 | 12 |
| 確定 F（find_by_name 契約） | Empire スコープで AgentId → find_by_id 委譲 | TC-UT-AGR-005 | ユニット | 正常系 / 異常系 | 11 |
| 確定 G（partial unique index 二重防衛）| Aggregate 検査 + DB 検査（内部品質基準: domain 層 AC #4 の DB 層二重防衛）| TC-IT-AGR-007 | 結合 | 異常系 | 4 |
| **確定 H（masking 不可逆性）** | masked `prompt_body` 復元時に raw 戻らない | TC-IT-AGR-006-masking-roundtrip | 結合 | 正常系 | 12 |
| 確定 I（4 ファイル分割） | test_*.py 全ファイル 500 行未満 | （静的確認） | — | — | — |

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| SQLite (aiosqlite, in-memory) | Repository 永続化テスト | — | `tests/factories/agent.py`（`AgentFactory` 既存）+ AsyncSession fixture | 不要（M2 永続化基盤 conftest が提供）|
| `MaskingGateway.mask()` | `MaskedText.process_bind_param` 経路 | — | — | 不要（persistence-foundation #23 で characterization 完了）|

`tests/factories/agent.py`（agent #17 で導入）の `AgentFactory` を再利用。`prompt_body` に raw API key 形式文字列を含む `AgentWithSecretsFactory` を本 PR で追加（`test_masking_persona.py` 専用、`_meta.synthetic = True` 付与）。

## E2E テストケース

該当なし — 理由: infrastructure 層、HTTP API / CLI / UI なし。

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| 該当なし | — | — | — | — |

## 結合テストケース

実 SQLite + Alembic マイグレーション + Repository の往復シナリオ。empire-repo / workflow-repo のテンプレートを継承。

| テストID | 対象 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------|--------------|---------|------|---------|
| TC-IT-AGR-006-masking-anthropic | T1: `prompt_body` の Anthropic API key マスキング（**Schneier #3 中核**）| AgentFactory + raw `prompt_body='Use ANTHROPIC_API_KEY=sk-ant-api03-XXX...'` | empty DB | save(agent) → raw SQL `SELECT prompt_body FROM agents WHERE id=?` で永続化値確認 | DB 上の `prompt_body` が `<REDACTED:ANTHROPIC_KEY>` or `<REDACTED:ENV:ANTHROPIC_API_KEY>` を含む（適用順序は storage.md §マスキング規則）、**raw `sk-ant-api03-XXX...` が DB に一切残らない**ことを assert |
| TC-IT-AGR-006-masking-github | T1: GitHub PAT マスキング | AgentFactory + raw `prompt_body='Use ghp_XXX... for git push'` | empty DB | save(agent) → raw SQL SELECT | DB 上に `<REDACTED:GITHUB_PAT>` を含む、raw `ghp_XXX...` が残らない |
| TC-IT-AGR-006-masking-roundtrip | §確定 H: masking 不可逆性 | Agent factory（raw secret 含み）| save 済み Agent | `find_by_id(agent.id)` で復元 → `Persona.prompt_body` を取得 | 復元値は `<REDACTED:*>` を含む文字列、raw secret を復元できないことを assert（不可逆性の物理確認）|
| TC-IT-AGR-007 | §確定 G: partial unique index 二重防衛 | 直接 INSERT 経路（Aggregate 経由しない）| empty DB | 同 agent_id で `is_default=True` を 2 行 INSERT | 2 行目で `sqlalchemy.exc.IntegrityError`（partial unique index 違反）。Aggregate 検査を迂回した経路で DB が物理拒否することを確認 |
| TC-IT-AGR-008 | Alembic 0004 マイグレーション | clean DB | `alembic upgrade head` 実行 | 3 テーブル + UNIQUE 制約 + partial unique index が SQLite に作成、`alembic downgrade -1` で逆順削除 |
| TC-IT-AGR-LIFECYCLE | Lifecycle: save → find_by_name → find_by_id → save（更新）| AgentFactory | empty DB | (1) `save(agent_a)` → (2) `find_by_name(empire_id, 'agent_a')` → Agent 取得 → (3) `find_by_id(agent.id)` で再取得 → (4) persona 変更で再構築 → `save(updated_agent)` | 各段階で valid Agent を返す、persona 変更が永続化される、`prompt_body` masking が再 save でも適用 |

## ユニットテストケース

`tests/factories/agent.py` の factory 経由で入力を生成。

### Protocol / CRUD 正常系（test_protocol_crud.py）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-AGR-001 | `AgentRepository` Protocol 型レベル充足 | 正常系 | `SqliteAgentRepository` インスタンス | `isinstance(repo, AgentRepository)` 不採用（`@runtime_checkable` なし）、pyright strict で `repo: AgentRepository = SqliteAgentRepository(session)` が pass |
| TC-UT-AGR-004 | `count()` SQL 契約 | 正常系 | DB に 5 件 Agent | `count()` の戻り値が 5、SQL ログに `SELECT count(*)` が含まれる、全行ロード経路（`SELECT id FROM agents`）が**ない**ことを SQL ログで assert |
| TC-UT-AGR-005 | `find_by_name(empire_id, name)` 契約（§確定 F）| 正常系 / 異常系 | (1) DB に `(empire_a, 'agent_a')` の Agent / (2) 不在 / (3) 異 Empire で同 name | (1) Agent を返す / (2) None を返す / (3) None を返す（Empire スコープ）|

### save delete-then-insert（test_save_semantics.py）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-AGR-002 | save の 5 段階 DML 順序 | 正常系 | 既存 Agent + providers 2 件 + skills 3 件 を providers 1 件 + skills 2 件に更新 | save 後 DB の providers が 1 件、skills が 2 件、削除された行が消えている。SQL ログで agents UPSERT → agent_providers DELETE → INSERT → agent_skills DELETE → INSERT の 5 段階順序を確認 |
| TC-UT-AGR-003 | `find_by_id` の `ORDER BY` 規約（§BUG-EMR-001）| 正常系 | 同 agent_id で provider_kind 順序逆 / skill_id 順序逆で INSERT | `find_by_id` の戻り値で providers が `provider_kind` 昇順、skills が `skill_id` 昇順、SQL ログに `ORDER BY provider_kind` / `ORDER BY skill_id` が出る |
| TC-UT-AGR-010-sql-order | save の Tx 境界 | 正常系 | service 側で `async with session.begin()` で囲む | Repository 内では commit/rollback なし、Tx 全体が ATOMIC、半端終了で rollback |
| TC-UT-AGR-011-roundtrip | `_to_row` / `_from_row` 双方向変換 | 正常系 | AgentFactory（providers / skills 含む）| `_from_row(_to_row(agent))` が元 Agent と構造的等価（Pydantic frozen `==` 判定）|

### 制約 / アーキテクチャ（test_constraints_arch.py）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-AGR-009-arch | CI Layer 2 arch test 自身 | 正常系 | `Base.metadata.tables['agents']` の `prompt_body` カラム | `column.type.__class__ is MaskedText` を assert（**正のチェック**）。他カラムは masking なし |

### Schneier #3 実適用専用（test_masking_persona.py、feature-spec.md §9 受入基準 12）

**本 PR の核心テストファイル**。Schneier 申し送り #3 実適用の物理保証。

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-IT-AGR-006-masking-anthropic | Anthropic API key マスキング | 正常系 | raw `prompt_body='ANTHROPIC_API_KEY=sk-ant-api03-XXX...'` | DB raw SELECT で `<REDACTED:*>` を含む、raw `sk-ant-api03-XXX...` が一切残らない（grep で 0 hit）|
| TC-IT-AGR-006-masking-github | GitHub PAT マスキング | 正常系 | raw `prompt_body='Use ghp_XXX... for git push'` | DB raw SELECT で `<REDACTED:GITHUB_PAT>`、raw `ghp_XXX...` が残らない |
| TC-IT-AGR-006-masking-openai | OpenAI key マスキング | 正常系 | raw `prompt_body='OPENAI_API_KEY=sk-XXX...'` | DB raw SELECT で `<REDACTED:OPENAI_KEY>` |
| TC-IT-AGR-006-masking-bearer | Bearer token マスキング | 正常系 | raw `prompt_body='Authorization: Bearer XXX'` | DB raw SELECT で `<REDACTED:BEARER>` |
| TC-IT-AGR-006-masking-no-secret | secret なしの passthrough | 正常系 | raw `prompt_body='You are a helpful agent.'` | DB raw SELECT で文字列が改変されない（masking 適用範囲外）|
| TC-IT-AGR-006-masking-roundtrip | §確定 H: masking 不可逆性 | 正常系 | save → find_by_id 経路 | 復元 `Persona.prompt_body` が `<REDACTED:*>` を含む、元 token が復元不能 |
| TC-IT-AGR-006-masking-multiple | 複数 secret 同時マスキング | 正常系 | raw `prompt_body` に 3 種 secret 混在 | すべて `<REDACTED:*>` 化、raw token 全消滅 |

## カバレッジ基準

- REQ-AGR-001〜005 すべてに最低 1 件のテストケース
- **Schneier #3 実適用 7 経路**（anthropic / github / openai / bearer / no-secret / roundtrip / multiple）すべてに正常系ケース、TC-IT-AGR-006-masking-* で物理確認
- **partial unique index 二重防衛**（§確定 G）: 直接 INSERT 経路で IntegrityError が出ることを TC-IT-AGR-007 で確認
- empire-repo §確定 A〜F + §BUG-EMR-001 規約の継承を TC-UT-AGR-002〜005 全件で確認
- C0 目標: `infrastructure/persistence/sqlite/repositories/agent_repository.py` で **95% 以上**

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全ジョブ緑
- ローカル: `cd backend && uv run pytest tests/infrastructure/persistence/sqlite/repositories/test_agent_repository/ -v` → 全テスト緑
- masking 物理確認: `uv run pytest tests/.../test_masking_persona.py -v` → 7 ケース緑、raw token が DB に残らないことを目視
- Alembic: `uv run alembic upgrade head` → 0004_agent_aggregate 適用、`sqlite3 bakufu.db ".schema agents"` で `prompt_body` 列の型確認

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      agent.py                                  # 既存 + AgentWithSecretsFactory 追加（_meta.synthetic）
    infrastructure/
      persistence/
        sqlite/
          repositories/
            test_agent_repository/              # 新規ディレクトリ（4 ファイル分割、最初から）
              __init__.py
              test_protocol_crud.py             # TC-UT-AGR-001/004/005
              test_save_semantics.py            # TC-UT-AGR-002/003/010/011
              test_constraints_arch.py          # TC-UT-AGR-009 + TC-IT-AGR-007/008
              test_masking_persona.py           # TC-IT-AGR-006-masking-* (7 ケース、Schneier #3 中核)
```

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| Agent 後続申し送り #1 | masked `prompt_body` の LLM Adapter 配送経路（§確定 H）| `feature/llm-adapter`（後続） | 「`<REDACTED:*>` を含む Persona は配送停止 + ログ警告」契約を凍結する責務 |

**Schneier 申し送り（前 PR から継承）**:

- **Schneier #3 (`Persona.prompt_body` Repository マスキング)**: persistence-foundation #23 で hook 構造提供、本 PR で実適用配線完了 → **Schneier 申し送り #3 クローズ**

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-AGR-001〜005 すべてに 1 件以上のテストケース
- [ ] **Schneier #3 実適用 7 経路**すべてに TC-IT-AGR-006-masking-* で物理確認、raw token が DB に残らないことを assert
- [ ] **partial unique index 二重防衛**を TC-IT-AGR-007 で物理確認（直 INSERT 経路で IntegrityError）
- [ ] `find_by_name` Empire スコープ検索を TC-UT-AGR-005 で 3 経路（ヒット / 不在 / 異 Empire 同 name）すべて確認
- [ ] empire-repo / workflow-repo テンプレート継承（§確定 A〜F + §BUG-EMR-001）が崩れていない
- [ ] **テストファイル分割（4 ファイル）が basic-design.md §モジュール構成と整合**（empire-repo PR #29 / workflow-repo PR #41 教訓を最初から反映）
- [ ] Schneier 申し送り #3 クローズが PR 本文に明示されている
