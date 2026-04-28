# テスト設計書

<!-- feature: workflow-repository -->
<!-- 配置先: docs/features/workflow-repository/test-design.md -->
<!-- 対象範囲: REQ-WFR-001〜005 / 受入基準 1〜15 / 詳細設計 確定 A〜J / Repository ポート + delete-then-insert + domain↔row 変換（§G/H/I）+ ORDER BY 規約 + CI 三層防衛 + partial-mask テンプレート -->

本 feature は M2 Repository **2 番目の Aggregate Repository PR**であり、empire-repository（PR #25）が凍結したテンプレート（§確定 A〜F）を**完全継承**する。Workflow 固有の追加凍結条項は §確定 G（`roles_csv` sorted CSV）/ §確定 H（`notify_channels_json` MaskedJSONEncoded、不可逆性）/ §確定 I（`completion_policy_json` 平 JSONEncoded）/ §確定 J（`workflows.entry_stage_id` 非 FK 戦略）の 4 件。

戦略ガイド §結合テスト方針「DB は実接続」「外部 API のみモック」に従い、本 feature のテストは:

- **integration test 主導**: Alembic 3rd revision 適用 → AsyncSession で `find_by_id` / `count` / `save` の 3 メソッド契約検証（`tmp_path` で実 SQLite ファイル）。empire-repository の `app_engine` / `session_factory` fixture を再利用
- **CI 三層防衛の partial-mask 拡張**: Layer 1（grep guard）+ Layer 2（arch test `_PARTIAL_MASK_TABLES`）+ Layer 3（storage.md）の 3 層が「`workflow_stages.notify_channels_json` のみマスキング、他カラムは対象外」を物理保証
- **MaskedJSONEncoded 配線の物理確認**: 実 SQLite に対する raw SQL SELECT で `notify_channels_json` カラムの中身に `<REDACTED:DISCORD_WEBHOOK>` が含まれ、元の token が含まれないことを assert（Schneier 申し送り #6 実適用、§確定 H）
- **§確定 H §不可逆性**: 保存後 `find_by_id` で `EXTERNAL_REVIEW` ステージ（notify_channels 必須）を含む Workflow を再構築すると `pydantic.ValidationError` が発生することを物理確認
- **assumed mock 禁止規約**: `mock.return_value` インライン辞書は禁止、Workflow / Stage / Transition / NotifyChannel / CompletionPolicy は既存 `tests/factories/workflow.py`（workflow feature #16 で確立）から取得

外部 I/O は SQLite + ファイルシステム + Alembic が本物。masking gateway（M2 永続化基盤の Layer 1〜3）は **本 feature が初の実適用**であり、`MaskedJSONEncoded.process_bind_param` フックを実 INSERT 経路で動作確認する。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-WFR-001 | `WorkflowRepository(Protocol)` 定義 | TC-IT-WFR-001 | 結合 | 正常系 | 1 |
| REQ-WFR-001 | `SqliteWorkflowRepository` の Protocol 充足 | TC-IT-WFR-002 | 結合 | 正常系 | 2 |
| REQ-WFR-002 | `find_by_id(workflow_id)` 既存 Workflow 取得 | TC-IT-WFR-003 | 結合 | 正常系 | 3 |
| REQ-WFR-002 | `find_by_id(unknown_id)` で None | TC-IT-WFR-004 | 結合 | 異常系 | 3 |
| REQ-WFR-002（ORDER BY、§確定 G/H 規約 + BUG-EMR-001 継承） | `find_by_id` の `workflow_stages` SELECT に `ORDER BY stage_id` が含まれる | TC-IT-WFR-005 | 結合 | 正常系 | 4 |
| REQ-WFR-002（ORDER BY） | `find_by_id` の `workflow_transitions` SELECT に `ORDER BY transition_id` が含まれる | TC-IT-WFR-006 | 結合 | 正常系 | 5 |
| REQ-WFR-002（§確定 D 補強） | `count()` が SQL レベル `SELECT COUNT(*)` を発行 | TC-IT-WFR-007 | 結合 | 正常系 | 6 |
| REQ-WFR-002（§確定 B） | `save(workflow)` 新規挿入で 3 テーブルに行が入る | TC-IT-WFR-008 | 結合 | 正常系 | 7 |
| REQ-WFR-002（§確定 B、delete-then-insert） | `save(workflow)` 既存更新で stage / transition が delete-then-insert で全置換される | TC-IT-WFR-009 | 結合 | 正常系 | 7 |
| REQ-WFR-002（§確定 B、5 段階 SQL 順序） | save 内で workflows UPSERT → workflow_stages DELETE → INSERT → workflow_transitions DELETE → INSERT の順序検証 | TC-IT-WFR-010 | 結合 | 正常系 | 7 |
| REQ-WFR-002（§確定 G） | `Stage.required_role: frozenset[Role]` が `roles_csv` ソート済み CSV で永続化、`_from_row` で frozenset に復元 | TC-IT-WFR-011 | 結合 | 正常系 | 8 |
| REQ-WFR-002（§確定 G、決定論化） | 異なる順序で生成された同一 frozenset が同一 `roles_csv` バイト列を生み、delete-then-insert で diff noise を出さない | TC-IT-WFR-012 | 結合 | 正常系 | 8 |
| REQ-WFR-002（§確定 H、masking 配線） | `save(workflow)` 後の raw SQL SELECT で `notify_channels_json` 内に `<REDACTED:DISCORD_WEBHOOK>` が現れ、原 token が含まれない（Schneier #6 物理確認） | TC-IT-WFR-013 | 結合 | 正常系 | 9 |
| REQ-WFR-002（§確定 H §不可逆性） | `EXTERNAL_REVIEW` を含む Workflow を save → find_by_id で `pydantic.ValidationError` raise（masked URL が G7 regex に合致せず） | TC-IT-WFR-014 | 結合 | 異常系 | 9 |
| REQ-WFR-002（§確定 C、ラウンドトリップ） | notify_channels 不在の Workflow を `save(workflow) → find_by_id(workflow.id)` で `sorted(...)` 比較構造的等価 | TC-IT-WFR-015 | 結合 | 正常系 | 10 |
| REQ-WFR-002（Tx 境界、§確定 B） | service 側 `async with session.begin()` で commit / rollback 両経路、Repository は明示的 commit/rollback しない | TC-IT-WFR-016 | 結合 | 正常系/異常系 | （責務境界） |
| REQ-WFR-002（FK CASCADE） | `DELETE FROM workflows WHERE id=?` で workflow_stages / workflow_transitions が CASCADE 削除 | TC-IT-WFR-017 | 結合 | 正常系 | （データモデル） |
| REQ-WFR-002（UNIQUE 制約） | `(workflow_id, stage_id)` / `(workflow_id, transition_id)` 重複 INSERT で `IntegrityError` | TC-IT-WFR-018 | 結合 | 異常系 | （データモデル） |
| REQ-WFR-002（責務分離） | Repository はシングルトン強制せず、複数 Workflow を save 可能（`count()` は事実報告のみ） | TC-IT-WFR-019 | 結合 | 正常系 | （責務境界） |
| REQ-WFR-003 | Alembic 0003 で 3 テーブル + UNIQUE 制約が追加 | TC-IT-WFR-020 | 結合 | 正常系 | 11 |
| REQ-WFR-003 | `alembic upgrade head` ↔ `downgrade base` 双方向 idempotent | TC-IT-WFR-021 | 結合 | 正常系 | 11 |
| REQ-WFR-003（chain 一直線、§確定 R1-C） | revision 0001 → 0002 → 0003 が一直線（CI 検査で head 分岐なし、`0003.down_revision == "0002_empire_aggregate"`） | TC-IT-WFR-022 | 結合 | 正常系 | 11 |
| REQ-WFR-004（Layer 1 grep） | `scripts/ci/check_masking_columns.sh` で `workflow_stages.notify_channels_json` が `MaskedJSONEncoded` 必須を pass、他カラムは対象なしを pass | TC-CI-WFR-001 | CI script | 正常系 | 12 |
| REQ-WFR-004（Layer 2 arch、partial-mask） | `tests/architecture/test_masking_columns.py` で `workflow_stages.notify_channels_json` の `column.type.__class__ is MaskedJSONEncoded` を assert、他カラムは Masked* 不在を assert | TC-IT-WFR-023 | 結合 | 正常系 | 13 |
| REQ-WFR-005（storage.md 逆引き表） | §逆引き表に Workflow 3 行（partial-mask 1 + no-mask 2）が存在 | TC-DOC-WFR-001 | doc 検証 | 正常系 | （Layer 3） |
| AC-14（依存方向） | `domain` 層から `application` / `infrastructure` への import がゼロ件 | （既存 CI script） | — | — | 14 |
| AC-15（lint/typecheck/coverage） | `pyright --strict` / `ruff check` / coverage 90% | （CI ジョブ） | — | — | 15 |

**マトリクス充足の証拠**:

- REQ-WFR-001〜005 すべてに最低 1 件のテストケース
- **delete-then-insert 5 段階順序（§確定 B）**: TC-IT-WFR-010 で実 SQLite に対し UPSERT → DELETE → INSERT × 2 の順序を物理確認（empire-repository の TC-IT-EMR-011 と同パターン）
- **ORDER BY 規約（§確定 G/H 補強 + BUG-EMR-001 継承）**: TC-IT-WFR-005 / 006 で `ORDER BY stage_id` / `ORDER BY transition_id` の SQL ログ観測 + TC-IT-WFR-015 でリスト順序の構造的等価
- **§確定 G（roles_csv 決定論化）**: TC-IT-WFR-011 で `frozenset[Role] → CSV → frozenset` ラウンドトリップ + TC-IT-WFR-012 で「異なる挿入順序で生成された同一 frozenset が同一バイト列」を物理確認
- **§確定 H（notify_channels_json マスキング配線、masking gateway 実適用）**: TC-IT-WFR-013 で実 SQLite に対する raw SQL SELECT で `<REDACTED:DISCORD_WEBHOOK>` 出現 + 原 token 不在を 2 経路で同時 assert
- **§確定 H §不可逆性**: TC-IT-WFR-014 で「masking 後 find_by_id が ValidationError を raise」契約を物理確認
- **Tx 境界（§確定 B）**: TC-IT-WFR-016 で commit / rollback 両経路、Repository が明示的 commit/rollback しないことを assert
- **DB 制約**: FK CASCADE（TC-IT-WFR-017）+ UNIQUE 制約（TC-IT-WFR-018）で Alembic 0003 DDL の正しさを物理確認
- **CI 三層防衛 partial-mask 拡張（§確定 H + テンプレート責務）**: Layer 1 grep（TC-CI-WFR-001）+ Layer 2 arch（TC-IT-WFR-023、`_PARTIAL_MASK_TABLES` parametrize）+ Layer 3 storage.md（TC-DOC-WFR-001）の 3 層すべてで partial-mask の物理保証
- 受入基準 1〜13 すべてに unit/integration ケース（14〜15 は CI ジョブ）
- 確定 A〜F（empire-repo 継承）/ G〜J（Workflow 固有）すべてに証拠ケース
- 孤児要件ゼロ

## 外部 I/O 依存マップ

本 feature は infrastructure 層の Repository 実装。empire-repository と同方針で本物の SQLite + 本物の Alembic + 本物の SQLAlchemy AsyncSession を使う。

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **SQLite (sqlite+aiosqlite)** | engine / session / 3 テーブル / Alembic migration | 不要（実 DB を `tmp_path` 配下の bakufu.db で起動、テストごとに使い捨て） | 不要 | **済（本物使用、persistence-foundation conftest.py の `app_engine` / `session_factory` fixture を再利用）** |
| **ファイルシステム** | `BAKUFU_DATA_DIR` / `bakufu.db` / WAL/SHM | 不要（`pytest.tmp_path`） | 不要 | **済（本物使用）** |
| **Alembic** | 0003 revision の `upgrade head` / `downgrade base` | 不要（本物の `alembic upgrade` を実 SQLite に対し実行） | 不要 | **済（本物使用、persistence-foundation の `run_upgrade_head` を再利用）** |
| **SQLAlchemy 2.x AsyncSession** | UoW 境界 / Repository メソッド経由の SQL 発行 | 不要 | 不要 | **済（本物使用）** |
| **MaskingGateway (`mask_in`)** | `MaskedJSONEncoded.process_bind_param` 経由で notify_channels_json をマスキング | 不要（実 init を `_initialize_masking` autouse fixture で実施） | 不要 | **済（本物使用、infrastructure/conftest.py で init）** |

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `make_workflow`（既存、workflow feature #16 由来） | `Workflow`（valid デフォルト = 単一 WORK ステージ、entry == sink） | `True` |
| `make_stage`（既存） | `Stage`（kind=WORK, role={DEVELOPER}、`EXTERNAL_REVIEW` 時は notify_channels 自動注入） | `True` |
| `make_transition`（既存） | `Transition`（from / to 必須、condition=APPROVED デフォルト） | `True` |
| `make_notify_channel`（既存） | `NotifyChannel`（DEFAULT_DISCORD_WEBHOOK = `https://discord.com/api/webhooks/.../SyntheticToken_-abcXYZ`） | `True` |
| `make_completion_policy`（既存） | `CompletionPolicy`（kind=approved_by_reviewer, description="review approval"） | `True` |
| `build_v_model_payload`（既存） | dict（13 ステージ + 15 transition、Workflow.from_dict 用） | — |

`tests/factories/workflow.py` は workflow feature #16 で確立済み。本 PR では factory 追加なし（既存 5 関数 + 1 payload で full coverage）。

**raw fixture / characterization は不要**: SQLite + SQLAlchemy + Alembic + MaskingGateway はすべて標準ライブラリ仕様 / 既存 Cuckoo セット内動作で固定、外部観測（実 DB ファイル）が真実源として常時使える。

## E2E テストケース

**該当なし** — 理由:

- 本 feature は infrastructure 層単独で、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない（[`requirements.md`](requirements.md) §画面・CLI 仕様 / §API 仕様 で「該当なし」と凍結）
- Repository は内部 API（Python module-level の Protocol / Class）のみ提供
- 戦略ガイド §E2E対象の判断「内部 API・ライブラリなどエンドユーザー操作がない場合は結合テストで代替可」に従い、E2E は本 feature 範囲外
- 後続 `feature/workflow-application`（`WorkflowService.create() / get()` 等）/ `feature/admin-cli`（`bakufu admin workflow show`） / `feature/http-api`（Workflow CRUD）が公開 I/F を実装した時点で E2E を起票
- 受入基準 1〜13 はすべて unit/integration テストで検証可能（14〜15 は CI ジョブ）

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — infrastructure 層のため公開 I/F なし | — | — |

## 結合テストケース

「Repository 契約 + 実 SQLite + 実 Alembic + 実 MaskingGateway」を contract testing する層。M2 永続化基盤の `app_engine` / `session_factory` fixture を再利用。

### Protocol 定義 + 充足（受入基準 1, 2、§確定 A）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-WFR-001 | `WorkflowRepository(Protocol)` 定義 | — | `application/ports/workflow_repository.py` がインポート可能 | `from bakufu.application.ports.workflow_repository import WorkflowRepository` | Protocol が `find_by_id` / `count` / `save` の 3 メソッドを宣言、すべて `async def`。`@runtime_checkable` なし |
| TC-IT-WFR-002 | `SqliteWorkflowRepository` の Protocol 充足 | `app_engine` + `session_factory` | engine + Alembic 適用済み | `repo: WorkflowRepository = SqliteWorkflowRepository(session)` で型代入が pyright で通る | pyright strict pass。さらに duck typing で `hasattr(repo, 'find_by_id') and hasattr(repo, 'count') and hasattr(repo, 'save')` 全 True |

### 基本 CRUD（受入基準 3〜7）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-WFR-003 | `find_by_id(existing_workflow_id)` | `session_factory` + `make_workflow` | `save(workflow)` で 1 件保存済み | 同 session_factory で別 session を開き `find_by_id(workflow.id)` | 保存した Workflow と構造的等価な Workflow を返す（notify_channels 不在 Workflow なら `==` True） |
| TC-IT-WFR-004 | `find_by_id(unknown_id)` | `session_factory` | DB 空 | `find_by_id(uuid4())` を呼ぶ | `None` を返す。例外を raise しない |
| TC-IT-WFR-005 | `find_by_id` の `workflow_stages` SELECT に `ORDER BY stage_id` | `session_factory` + `before_cursor_execute` event listener | save 済み Workflow（複数ステージ） | `find_by_id(workflow.id)` を呼びつつ SQL ログを観測 | `SELECT ... FROM workflow_stages WHERE workflow_id = ? ORDER BY stage_id` が観測される |
| TC-IT-WFR-006 | `find_by_id` の `workflow_transitions` SELECT に `ORDER BY transition_id` | 同上 | save 済み Workflow（複数 transition） | 同上 | `SELECT ... FROM workflow_transitions WHERE workflow_id = ? ORDER BY transition_id` が観測される |
| TC-IT-WFR-007 | `count()` が SQL レベル `SELECT COUNT(*)` 発行 | `session_factory` + event listener | DB に複数 Workflow 保存済み | `count()` を呼びつつ SQL ログを観測 | `SELECT count(*) FROM workflows` が単独発行され、`SELECT id FROM workflows` のような全行ロード SQL は発行されない |

### `save()` 基本（受入基準 7、§確定 B）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-WFR-008 | `save(workflow)` 新規挿入で 3 テーブルに行が入る | `session_factory` + V-model payload | rooms 0 件、stages 13 件 + transitions 15 件の Workflow（V-model） | `save(workflow)` 後、別 session で 3 テーブル直接 SELECT | `workflows` 1 行 + `workflow_stages` 13 行 + `workflow_transitions` 15 行が存在、各カラムが Workflow VO の値と一致 |
| TC-IT-WFR-009 | `save(workflow)` 既存更新（delete-then-insert） | `session_factory` + `make_workflow` | 1 度 save 済みの Workflow（複数ステージ） | (1) Workflow を `add_stage` / `remove_stage` で更新、(2) 再度 `save(updated_workflow)` を呼ぶ | workflow_stages / workflow_transitions が **delete-then-insert** で全置換される。古い Stage / Transition は残らず、新 VO が SELECT で取得される |
| TC-IT-WFR-010 | `save()` 内 SQL 発行順序（5 段階） | `session_factory` + V-model payload + `before_cursor_execute` event listener | save 1 度実施済 | 再 save 時の SQL 文を順序で観測 | 順序が §確定 B 通り: (1) UPSERT workflows、(2) DELETE workflow_stages WHERE workflow_id=?、(3) bulk INSERT workflow_stages、(4) DELETE workflow_transitions WHERE workflow_id=?、(5) bulk INSERT workflow_transitions |

### §確定 G（roles_csv 決定論化、受入基準 8）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-WFR-011 | `frozenset[Role] → CSV → frozenset` ラウンドトリップ | `session_factory` + `make_stage(required_role=frozenset({...}))` | 複数 Role を持つステージ | `save → find_by_id → restored.stages[0].required_role` を抽出 | 元の `frozenset[Role]` と等価。途中の DB カラムは sorted CSV 文字列 |
| TC-IT-WFR-012 | sorted CSV の決定論化 | `session_factory` + raw SQL SELECT | 同一 frozenset を異なる挿入順 `frozenset({A, B, C})` / `frozenset({C, B, A})` で 2 つの Workflow に save | raw SQL で `roles_csv` カラムを取得 | 両 Workflow の `roles_csv` が**バイト同一**（diff noise を出さない、§確定 G の決定論化契約） |

### §確定 H（notify_channels_json マスキング配線、受入基準 9）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-WFR-013 | `MaskedJSONEncoded` 配線の物理確認 | `session_factory` + raw SQL SELECT | `EXTERNAL_REVIEW` ステージ + 実 Discord webhook URL（real-shape token） を持つ Workflow | (1) `save(workflow)`、(2) raw SQL `SELECT notify_channels_json FROM workflow_stages WHERE workflow_id = ?` で生 JSON 文字列を取得 | (a) `<REDACTED:DISCORD_WEBHOOK>` が JSON 内に出現、(b) 原 token（`SyntheticToken_-abcXYZ` などの synthetic 文字列）が JSON 内に**出現しない**（Schneier 申し送り #6 物理確認） |
| TC-IT-WFR-014 | §確定 H §不可逆性（masked URL のラウンドトリップ失敗） | `session_factory` + `make_stage(kind=EXTERNAL_REVIEW)` | save 済 Workflow（notify_channels あり） | `find_by_id(workflow.id)` を呼ぶ | `pydantic.ValidationError` が raise される（masked URL `<REDACTED:DISCORD_WEBHOOK>` が NotifyChannel G7 regex `[A-Za-z0-9_\-]+` に合致しない）。これが §確定 H §不可逆性 の物理証拠 |

### §確定 C（domain↔row ラウンドトリップ、受入基準 10）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-WFR-015 | ラウンドトリップ（`save → find_by_id` 構造的等価） | `session_factory` + `make_workflow`（notify_channels 不在） | 任意の valid Workflow（複数ステージ + 複数 transition、ただし `EXTERNAL_REVIEW` 不在 = notify_channels 不要） | (1) `save(workflow)`、(2) 別 session で `find_by_id(workflow.id)`、(3) 復元 Workflow を `sorted(stages, key=lambda s: s.id)` でソートして比較 | 構造的等価が成立。Stage / Transition のリスト順序は ORDER BY で決定論化、`sorted()` 比較で `==` True |

### Tx 境界の責務分離（§確定 B、受入基準 7 補強）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-WFR-016 | service 層 `async with session.begin()` 配下の commit / rollback | `session_factory` + `make_workflow` | service スタブ（`async def save_workflow(repo, workflow)`） | (1) **正常系**: `async with session.begin(): await repo.save(workflow)` → ブロック退出で commit、(2) **異常系**: 同ブロック内で `raise RuntimeError` → ブロック退出で rollback | commit 経路で Workflow が永続化、rollback 経路で原子的に消える。Repository は `await session.commit()` / `session.rollback()` を呼ばない（責務境界、§確定 B） |

### FK CASCADE + UNIQUE 制約（受入基準 11 補強）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-WFR-017 | `workflows` DELETE → 子テーブル CASCADE | `session_factory` + `make_workflow` | save 済み Workflow（複数ステージ + transition） | raw SQL で `DELETE FROM workflows WHERE id=:id` を実行 | workflow_stages / workflow_transitions の対応行が CASCADE で削除される（FK ON DELETE CASCADE 制約の物理確認） |
| TC-IT-WFR-018 | UNIQUE(workflow_id, stage_id) / (workflow_id, transition_id) 違反 | `session_factory` | save 済み Workflow | raw SQL で同じ `(workflow_id, stage_id)` ペアを 2 度 INSERT、`(workflow_id, transition_id)` ペアも同様 | 両ケースで `IntegrityError`（または UniqueViolation）が raise |

### 責務分離（§確定 D 継承）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-WFR-019 | Repository は `count()` で事実報告のみ、シングルトン強制しない | `session_factory` | DB 空 | (1) 1 件目 `save(workflow_a)`、(2) 別 id の `save(workflow_b)`、(3) `count()` を確認 | (a) 2 件目 save が **例外を raise せず**正常に通る、(b) `count()` が 2 を返す。集合知識（シングルトン制約等）は application 層の責務 |

### Alembic 0003 revision（受入基準 11、§確定 F）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-WFR-020 | Alembic 0003 revision 適用 | `tmp_path` 配下の bakufu.db | M1 + M2 + 0002_empire_aggregate 適用済み | `alembic upgrade head` を実行 | (a) `0002_empire_aggregate` から `0003_workflow_aggregate` への進行、(b) `SELECT name FROM sqlite_master WHERE type='table'` で `workflows` / `workflow_stages` / `workflow_transitions` の 3 テーブルが追加、(c) UNIQUE INDEX `(workflow_id, stage_id)` / `(workflow_id, transition_id)` が存在 |
| TC-IT-WFR-021 | upgrade / downgrade 双方向 idempotent | `tmp_path` | initial revision 適用済み | (1) `alembic upgrade head`、(2) `alembic downgrade base`、(3) 再 `alembic upgrade head` | (1) で 3 テーブル追加、(2) で 3 テーブル削除（empire / persistence-foundation テーブルは残る）、(3) で再追加 |
| TC-IT-WFR-022 | revision chain 一直線（§確定 R1-C） | Alembic config | versions/0001_init.py + 0002_empire_aggregate.py + 0003_workflow_aggregate.py | `ScriptDirectory.get_heads()` を実行 | head は単一（`0003_workflow_aggregate`）、`0003_workflow_aggregate.down_revision == "0002_empire_aggregate"` で chain 一直線。head 分岐がないことを物理確認 |

### CI 三層防衛（受入基準 12, 13、§確定 H + テンプレート責務）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-CI-WFR-001 | Layer 1: `scripts/ci/check_masking_columns.sh` の Workflow 拡張 | repo root | スクリプトが Workflow 3 テーブルを明示登録、`workflow_stages.notify_channels_json` の `MaskedJSONEncoded` 必須を検査 | `bash scripts/ci/check_masking_columns.sh` を実行 | exit 0。grep guard が `workflow_stages.py` の `notify_channels_json` カラム宣言に `MaskedJSONEncoded` が登場することを確認、未登場なら exit 非 0 |
| TC-IT-WFR-023 | Layer 2: `tests/architecture/test_masking_columns.py` の Workflow parametrize（partial-mask） | `Base.metadata` | M2 永続化基盤の arch test が `_PARTIAL_MASK_TABLES` を持つ | parametrize に `(workflow_stages, notify_channels_json)` を追加し、`column.type.__class__ is MaskedJSONEncoded` を assert、他カラムは Masked* 不在を assert | 全 3 テーブルで pass。後続 PR が誤って `MaskedText` を Workflow 他カラムに追加した瞬間、この test が落下して PR ブロック |

### storage.md 逆引き表（Layer 3）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-DOC-WFR-001 | storage.md §逆引き表に Workflow 行存在 | repo root | `docs/design/domain-model/storage.md` 編集済み | `storage.md` 内に "Workflow" を含む行で「`MaskedJSONEncoded`」または「partial mask」相当の宣言、および「masking 対象なし」を含む Workflow 行（workflows / workflow_transitions）の存在を確認 | partial-mask の 1 行 + no-mask 2 行が co-located（後続 Repository PR が同様の行を追加するテンプレート） |

## ユニットテストケース

`tests/factories/workflow.py` の factory 経由で domain 層 Workflow を生成する。Repository クラス内 private method (`_to_row` / `_from_row`) は実 DB アクセスを伴うため integration として扱い、純 unit としての追加ケースは作らない（empire-repository の TC-UT-EMR-001〜003 は domain↔row dict 変換のみだったが、本 PR では §確定 G/H/I の format 検証が DB 経由でこそ価値があるため integration に集約）。

## カバレッジ基準

- REQ-WFR-001 〜 005 の各要件が**最低 1 件**のテストケースで検証されている（マトリクス参照）
- **delete-then-insert 5 段階順序（§確定 B）**: TC-IT-WFR-010 で実 SQL ログ観測
- **ORDER BY 規約（§確定 G/H 補強 + BUG-EMR-001 継承）**: TC-IT-WFR-005 / 006 で SQL ログ観測 + TC-IT-WFR-015 でリスト順序の構造的等価
- **§確定 G（roles_csv sorted CSV）**: TC-IT-WFR-011 ラウンドトリップ + TC-IT-WFR-012 決定論化（バイト同一）
- **§確定 H（notify_channels_json マスキング + 不可逆性）**: TC-IT-WFR-013 物理確認 + TC-IT-WFR-014 不可逆性
- **§確定 C（domain↔row ラウンドトリップ）**: TC-IT-WFR-015 で実 DB 経由の構造的等価
- **§確定 B Tx 境界**: TC-IT-WFR-016 で commit / rollback 両経路、Repository が明示的 commit/rollback しないことを assert
- **DB 制約**: FK CASCADE（TC-IT-WFR-017）+ UNIQUE 制約（TC-IT-WFR-018）+ Alembic chain（TC-IT-WFR-022）で migration の正しさを物理確認
- **upgrade/downgrade idempotent**: TC-IT-WFR-021 で双方向 migration を物理確認
- **CI 三層防衛 partial-mask 拡張（§確定 H + テンプレート責務）**: Layer 1 grep（TC-CI-WFR-001）+ Layer 2 arch test（TC-IT-WFR-023）+ Layer 3 storage.md（TC-DOC-WFR-001）3 つすべてに証拠
- 受入基準 1 〜 13 の各々が**最低 1 件のユニット/結合ケース**で検証されている（E2E 不在のため戦略ガイドの「結合代替可」に従う）
- 受入基準 14（依存方向）/ 15（pyright/ruff/coverage 90%）は CI ジョブで担保
- 確定 A〜J すべてに証拠ケース
- C0 目標: `application/ports/workflow_repository.py` / `infrastructure/persistence/sqlite/repositories/workflow_repository.py` で **90% 以上**

## 人間が動作確認できるタイミング

本 feature は infrastructure 層単独だが、**M2 永続化基盤と同じく Backend プロセスを実起動して動作確認できる**。

- CI 統合後: `gh pr checks` で 7 ジョブ緑（lint / typecheck / test-backend / audit / fmt / commit-msg / no-ai-footer）
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/infrastructure/persistence/sqlite/repositories/test_workflow_repository tests/infrastructure/persistence/sqlite/test_alembic_workflow.py tests/architecture/test_masking_columns.py tests/docs/test_storage_md_back_index.py -v` → 全テスト緑
- Backend 実起動: `cd backend && uv run python -m bakufu`（環境変数 `BAKUFU_DATA_DIR=/tmp/bakufu-test` を設定）
  - 起動時に Alembic auto-migrate で 0001_init + 0002_empire_aggregate + 0003_workflow_aggregate が適用されることをログで目視
  - `sqlite3 <DATA_DIR>/bakufu.db ".tables"` で `workflows` / `workflow_stages` / `workflow_transitions` の 3 テーブルが見える
  - `sqlite3 <DATA_DIR>/bakufu.db "SELECT * FROM sqlite_master WHERE type='index'"` で UNIQUE INDEX が見える
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.application.ports.workflow_repository --cov=bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository --cov-report=term-missing` → 90% 以上
- masking gateway 実適用の物理観測: `tests/infrastructure/persistence/sqlite/repositories/test_workflow_repository/test_masking.py::test_discord_webhook_token_masked_in_db` を `-v -s` で実行 → raw JSON 出力に `<REDACTED:DISCORD_WEBHOOK>` 出現を目視

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      workflow.py                            # 既存（workflow feature #16）追加なし
    architecture/
      test_masking_columns.py                # 既存 + Workflow partial-mask parametrize（実装側で _PARTIAL_MASK_TABLES + TestPartialMaskContract 追加済み）
                                             # TC-IT-WFR-023
    infrastructure/
      persistence/
        sqlite/
          repositories/
            test_workflow_repository/
              __init__.py
              test_protocol_crud.py          # TC-IT-WFR-001〜007, 019
              test_save_semantics.py         # TC-IT-WFR-008〜012, 015, 016
              test_constraints_arch.py       # TC-IT-WFR-017, 018, 023
              test_masking.py                # TC-IT-WFR-013, 014（§確定 H 物理確認）
          test_alembic_workflow.py           # TC-IT-WFR-020〜022（Alembic 0003 検証）
    docs/
      test_storage_md_back_index.py          # 既存 + Workflow 行検証（TC-DOC-WFR-001）
```

**配置の根拠**:
- empire-repository の `test_empire_repository/` ディレクトリ分割パターン（Norman 500 行ルール）を継承
- `test_masking.py` を独立ファイルにするのは **Workflow が masking gateway の初実適用 PR**であり、TC-IT-WFR-013 / 014 が後続 Repository PR（agent / room / directive / task / external-review-gate）で masking 対象を持つときのテンプレートになるため
- `test_alembic_workflow.py` は empire の `test_alembic_empire.py` 同パターン
- `tests/docs/test_storage_md_back_index.py` は既存 + Workflow 行検証を追加（empire-repo で確立）

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| （N/A） | 該当なし — SQLite + Alembic + SQLAlchemy + MaskingGateway は標準ライブラリ仕様で固定 | — | 後続 5 件 Repository PR は本 PR を参照して同パターン実装。Aggregate 別の masking 対象カラムが存在する PR（agent / room / directive / task / external-review-gate）では `MaskedJSONEncoded` / `MaskedText` の Layer 2 arch test 検証が動作確認の対象になる |

**Schneier 申し送り（前 PR レビューより継承）**:

- **CI 三層防衛の Workflow 拡張**: 本 PR で「partial-mask」テンプレートを正式凍結（empire-repo は no-mask テンプレート、本 PR は partial-mask テンプレート）。`_PARTIAL_MASK_TABLES`（実装側で追加済み）+ `TestPartialMaskContract` の構造で「`workflow_stages.notify_channels_json` のみマスキング、他カラムは対象外」を物理保証
- **`storage.md` §逆引き表のテンプレート化**: §確定 H の Layer 3 で「Workflow 関連カラム」3 行（partial-mask 1 + no-mask 2）を追加。後続 Repository PR は同形式で「対象あり / 対象なし」を区別して追加する責務
- **本 feature 固有の申し送り**:
  - notify_channel re-registration responsibility は `feature/workflow-application` の責務（§確定 H §不可逆性）。本 PR は Repository が `pydantic.ValidationError` を raise する経路を担保するのみ、CEO への再入力フロー実装は application 層
  - `WorkflowService.create()` の Tx 境界は **本 PR で凍結した「Repository は session 受け取り、commit/rollback は service 側」契約に従う**こと（§確定 B）
  - エラー文言（`WorkflowNotFoundError` 等）は infrastructure には定義しない（内部 API、ユーザー向けメッセージは application / API 層責務）

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-WFR-001〜005 すべてに 1 件以上のテストケースがあり、特に integration が Repository 契約 + Alembic + masking 配線 + CI 三層防衛を単独でカバーしている
- [ ] **delete-then-insert 5 段階順序（§確定 B）**が TC-IT-WFR-010 で実 SQL 発行順を物理観測している
- [ ] **ORDER BY 規約（§確定 G/H + BUG-EMR-001 継承）**が TC-IT-WFR-005 / 006 で SQL ログ観測されている
- [ ] **§確定 G（roles_csv sorted CSV）**が TC-IT-WFR-011 ラウンドトリップ + TC-IT-WFR-012 決定論化（バイト同一）の 2 経路で物理確認
- [ ] **§確定 H（notify_channels_json マスキング配線）**が TC-IT-WFR-013 で実 SQLite に対する raw SQL SELECT で `<REDACTED:DISCORD_WEBHOOK>` 出現 + 原 token 不在を物理確認
- [ ] **§確定 H §不可逆性**が TC-IT-WFR-014 で `pydantic.ValidationError` raise を物理確認
- [ ] **Tx 境界（§確定 B）**が TC-IT-WFR-016 で commit / rollback 両経路、Repository が明示的 commit/rollback しないことを assert
- [ ] **DB 制約**: FK CASCADE（TC-IT-WFR-017）+ UNIQUE 制約（TC-IT-WFR-018）の物理確認
- [ ] **CI 三層防衛 partial-mask 拡張**: Layer 1 grep（TC-CI-WFR-001）+ Layer 2 arch（TC-IT-WFR-023）+ Layer 3 storage.md（TC-DOC-WFR-001）の 3 つすべてに証拠ケース
- [ ] **Alembic chain 一直線**（§確定 R1-C）: TC-IT-WFR-022 で head 分岐なし、`0003.down_revision == "0002_empire_aggregate"` を物理確認
- [ ] **upgrade/downgrade idempotent**: TC-IT-WFR-021 で双方向 migration を物理確認
- [ ] 確定 A〜J すべてに証拠ケースが含まれる
- [ ] empire-repository / persistence-foundation の `app_engine` / `session_factory` fixture を再利用、新 fixture は追加していない
- [ ] Schneier 申し送り（CI 三層防衛 partial-mask テンプレート / notify_channel re-registration の application 層責務 / Tx 境界の Repository / service 分離 / storage.md §逆引き表の Workflow 行）が次レビュー時に確認可能な形で test-design および設計書に記録されている
- [ ] **後続 5 件 Repository PR のテンプレート責務（§確定 F 継承）**: empire-repo の確定 A〜F + 本 PR の確定 G〜J を本 PR が満たすことが test-design.md レビュー観点で凍結されている
