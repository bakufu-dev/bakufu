# テスト設計書 — directive / repository

<!-- feature: directive -->
<!-- sub-feature: repository -->
<!-- 配置先: docs/features/directive/repository/test-design.md -->
<!-- 対象範囲: REQ-DRR-001〜005 / 親 spec 受入基準 #10（E2E は system-test-design.md）/ #11（masking IT）/ 詳細設計 §確定 R1-A〜G / directive §確定 G 実適用物理確認 + §BUG-DRR-001 申し送り確認 -->

本 sub-feature は M2 Repository **6 番目の Aggregate Repository PR**（empire / workflow / agent / room 後）。directive Aggregate（M1、PR #24 マージ済み）に対する Repository 層を新規追加する。テンプレートは room-repository (PR #48) を 100% 継承し、**4-method Protocol**（`find_by_id` / `count` / `save(directive)` / `find_by_room`）と **full-mask テーブル**（`directives.text`）の構造を確立する。

room-repo のテンプレートを継承しつつ、directive-repository 固有の論点 3 件を**専用テストファイルで物理保証**する:

1. **`text` MaskedText**（directive §確定 G 実適用）— Schneier 多層防御 3 件目を Repository 経由で物理確認、不可逆性確認含む
2. **`find_by_room(room_id)` ORDER BY created_at DESC, id DESC**（§確定 R1-D）— Room スコープ検索・最新順・tiebreaker・INDEX(target_room_id, created_at) 活用
3. **`target_room_id` FK ON DELETE CASCADE + §BUG-DRR-001 `task_id` FK 申し送り**（§確定 R1-B / R1-C）— Room 削除で Directive 自動削除 / task_id FK は task-repository PR に申し送り

**最初から 3 ファイル分割**（room-repo PR #48 正規構成を継承。`test_masking_text.py` が directive §確定 G 実適用の物理確認を担う本 PR 固有のテストファイル）。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-DRR-001 | `DirectiveRepository` Protocol **4 method** 定義 | TC-UT-DRR-001 | 結合 | 正常系 | 内部品質基準 |
| REQ-DRR-002（find_by_id） | `find_by_id` 存在 / 不在 | TC-UT-DRR-002 | 結合 | 正常系 | 内部品質基準 |
| REQ-DRR-002（save round-trip） | `save(directive)` UPSERT → `find_by_id` round-trip | TC-UT-DRR-003 | 結合 | 正常系 | 内部品質基準 |
| REQ-DRR-002（save UPSERT 更新） | 既存 Directive を再 save で UPDATE | TC-UT-DRR-007 | 結合 | 正常系 | 内部品質基準 |
| REQ-DRR-002（save task_id 更新） | `link_task(task_id)` → re-save で `task_id` 更新 | TC-UT-DRR-008 | 結合 | 正常系 | 内部品質基準 |
| REQ-DRR-002（count SQL） | `count()` が SQL `COUNT(*)` を発行 | TC-UT-DRR-006 | 結合 | 正常系 | 内部品質基準 |
| REQ-DRR-002（find_by_room） | Room 内 Directive 一覧 ORDER BY created_at DESC, id DESC | TC-UT-DRR-004 / TC-UT-DRR-004b / TC-UT-DRR-004e | 結合 | 正常系 | 内部品質基準 |
| REQ-DRR-002（Tx boundary） | commit path 永続化 / rollback path 破棄 | TC-UT-DRR-009 | 結合 | 正常系 / 異常系 | — |
| **REQ-DRR-002（masking、§確定 R1-B / directive §確定 G）** | raw `text` → DB に `<REDACTED:*>` 永続化（**directive §確定 G 実適用**）| TC-IT-DRR-010-masking-* (7 経路) | 結合 | 正常系 | **#11** |
| REQ-DRR-003（Alembic 0006 DDL）| 1 テーブル + INDEX + FK 1 件作成 | TC-IT-DRR-001 | 結合 | 正常系 | 内部品質基準 |
| REQ-DRR-003（Alembic chain） | 0001→0002→...→0006 単一 head | TC-IT-DRR-002 | 結合 | 正常系 | — |
| REQ-DRR-003（upgrade/downgrade） | 双方向 migration が idempotent | TC-IT-DRR-003 | 結合 | 正常系 | 内部品質基準 |
| REQ-DRR-003（down_revision） | `0006.down_revision == "0005_room_aggregate"` | TC-IT-DRR-004 | 結合 | 正常系 | — |
| REQ-DRR-003（CASCADE FK 物理確認） | Room 削除で Directive 自動削除（§確定 R1-B） | TC-IT-DRR-005 | 結合 | 正常系 | 内部品質基準 |
| REQ-DRR-003（task_id FK なし確認） | 0006 時点で `task_id` FK が存在しないことを物理確認（§BUG-DRR-001）| TC-IT-DRR-006 | 結合 | 正常系 | 内部品質基準 |
| REQ-DRR-004（CI Layer 2）| arch test parametrize（`_FULL_MASK_TABLES` or 相当に `directives` 追加）| TC-UT-DRR-arch | 結合 | 正常系 | 内部品質基準 |
| REQ-DRR-004（CI Layer 1）| grep guard で `directives.text` の `MaskedText` 必須 | （CI ジョブ） | — | — | 内部品質基準 |
| REQ-DRR-005（storage.md） | §逆引き表更新（`directives.text: MaskedText` 追加）| TC-DOC-DRR-001 | doc 検証 | 正常系 | 内部品質基準 |
| AC-lint/typecheck | `pyright --strict` / `ruff check` エラーゼロ | （CI ジョブ） | — | — | — |
| **§確定 R1-A（テンプレ継承）** | empire/workflow/agent/room §確定 A〜F + §BUG-DRR-001 規約 | TC-UT-DRR-001〜009 全件 | 結合 | — | — |
| **§確定 R1-B（CASCADE FK）** | target_room_id → rooms.id ON DELETE CASCADE 物理確認 | TC-IT-DRR-005 | 結合 | 正常系 | 内部品質基準 |
| **§確定 R1-C（BUG-DRR-001 申し送り）** | 0006 時点で task_id FK なし（PRAGMA foreign_key_list 確認）| TC-IT-DRR-006 | 結合 | 正常系 | 内部品質基準 |
| **§確定 R1-D（find_by_room ORDER BY）** | created_at DESC, id DESC ORDER BY の SQL ログ物理確認（tiebreaker 含む）| TC-UT-DRR-004 / TC-UT-DRR-004e | 結合 | 正常系 | 内部品質基準 |
| **§確定 R1-E（CI 三層防衛）** | 正のチェック + 負のチェック | TC-UT-DRR-arch + TC-DOC-DRR-001 | 結合 / doc | 正常系 | 内部品質基準 |
| **§確定 R1-F（save 1 引数）** | `save(directive)` が `directive.target_room_id` から直接 FK 解決 | TC-UT-DRR-003 + TC-IT-DRR-LIFECYCLE | 結合 | 正常系 | — |
| **§確定 R1-G（_to_row / _from_row）** | `created_at` timezone-aware 往復 / `task_id` None↔UUID 往復 | TC-UT-DRR-003 + TC-UT-DRR-008 | 結合 | 正常系 | — |
| **directive §確定 G（masking 不可逆性、Repository 実適用）** | masked `text` 復元時に raw 戻らない | TC-IT-DRR-010-masking-roundtrip | 結合 | 正常系 | **#11** |
| **§BUG-DRR-001（task_id FK 申し送り）** | 0006 で task_id FK が `directives` テーブルに存在しないことを確認 | TC-IT-DRR-006 | 結合 | 正常系 | 内部品質基準 |
| **Lifecycle 統合** | save → find_by_room → save（更新）の 4 method 連携 | TC-IT-DRR-LIFECYCLE | 結合 | 正常系 | — |

**マトリクス充足の証拠**:

- REQ-DRR-001〜005 すべてに最低 1 件のテストケース
- **directive §確定 G 実適用 7 経路**（discord / anthropic / github / bearer / no-secret / roundtrip / multiple）すべてに TC-IT-DRR-010-masking-* で物理確認（受入基準 #11）
- 受入基準 #11（masking IT）はリポジトリ IT で検証済み。受入基準 #10（E2E: 永続化ラウンドトリップ）は親 [`../system-test-design.md`](../system-test-design.md) TC-E2E-DR-001/002 で管理
- **find_by_room ORDER BY created_at DESC, id DESC**（§確定 R1-D）: TC-UT-DRR-004 で複数 Directive の順序 + SQL ログ物理確認。TC-UT-DRR-004e で同時刻 tiebreaker（`id DESC`）を物理確認（BUG-EMR-001 規約、回帰検出経路）
- **target_room_id FK ON DELETE CASCADE**（§確定 R1-B）: TC-IT-DRR-005 で Room 削除時の Directive 自動削除を物理確認
- **§BUG-DRR-001 FK 申し送り確認**（§確定 R1-C）: TC-IT-DRR-006 で `PRAGMA foreign_key_list('directives')` が `tasks` テーブルへの参照を含まないことを物理確認
- **save(directive) 1 引数**（§確定 R1-F）: TC-UT-DRR-003 で `directive.target_room_id` 自身が持つ値から FK 解決されることを確認
- **created_at timezone-aware 往復**（§確定 R1-G）: TC-UT-DRR-003 で UTC aware datetime の round-trip equality 確認
- **CI 三層防衛**（§確定 R1-E）: Layer 1 grep（CI ジョブ）+ Layer 2 arch（TC-UT-DRR-arch）+ Layer 3 storage.md（TC-DOC-DRR-001）3 つすべてに証拠
- 孤児要件ゼロ

## 外部 I/O 依存マップ

本 sub-feature は infrastructure 層の Repository 実装。empire-repo / workflow-repo / agent-repo / room-repo と同方針で本物の SQLite + 本物の Alembic + 本物の SQLAlchemy AsyncSession を使う。

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **SQLite (sqlite+aiosqlite)** | engine / session / 1 テーブル / Alembic 0006 migration | 不要（実 DB を `tmp_path` 配下の bakufu.db で起動、テストごとに使い捨て）| 不要 | **済（M2 永続化基盤 conftest の `app_engine` / `session_factory` fixture を再利用）** |
| **ファイルシステム** | `BAKUFU_DATA_DIR` / `bakufu.db` / WAL/SHM | 不要（`pytest.tmp_path`）| 不要 | **済（本物使用）** |
| **Alembic** | 0006 revision の `upgrade head` / `downgrade -1` + chain 検証 | 不要（本物の `alembic upgrade` を実 SQLite に対し実行）| 不要 | **済（本物使用、persistence-foundation の `run_upgrade_head` を再利用）** |
| **SQLAlchemy 2.x AsyncSession** | UoW 境界 / Repository メソッド経由の SQL 発行 | 不要 | 不要 | **済（本物使用）** |
| **MaskingGateway (`mask`)** | `MaskedText.process_bind_param` 経由で `directives.text` をマスキング | 不要（実 init を `_initialize_masking` autouse fixture で実施）| 不要 | **済（persistence-foundation #23 で characterization 完了、本 PR で配線実適用）** |

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `make_directive`（**本 PR で追加**） | `Directive`（valid デフォルト: `text="test directive"`, `task_id=None`）| `True` |
| `make_directive_with_task`（**本 PR で追加**） | `Directive`（`task_id` 付き）| `True` |
| `make_directive_with_secret_text`（**本 PR で追加**） | `Directive`（`text` に raw secret 形式文字列を含む、`test_masking_text.py` 専用）| `True` |

`tests/factories/directive.py` を本 PR で新規作成（agent-repo / room-repo の `tests/factories/*.py` 同パターン）。

**raw fixture / characterization は不要**: SQLite + SQLAlchemy + Alembic + MaskingGateway はすべて標準ライブラリ仕様 / 既存 characterization 完了済みの動作で固定。

## E2E テストケース

**該当なし** — 理由:

- 本 sub-feature は infrastructure 層単独で、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない
- Repository は内部 API（Python module-level の Protocol / Class）のみ提供
- E2E は親 [`../system-test-design.md`](../system-test-design.md) が管理する（TC-E2E-DR-001, 002）

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — infrastructure 層のため公開 I/F なし | — | — |

## 結合テストケース

「Repository 契約 + 実 SQLite + 実 Alembic + 実 MaskingGateway」を contract testing する層。M2 永続化基盤の `app_engine` / `session_factory` fixture を再利用。

### Protocol 定義 + 充足（内部品質基準）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-UT-DRR-001 | `DirectiveRepository` Protocol が **4 method** を宣言 | — | `application/ports/directive_repository.py` がインポート可能 | `from bakufu.application.ports.directive_repository import DirectiveRepository` | Protocol が `find_by_id` / `count` / `save(directive)` / `find_by_room` の **4 method** を宣言、すべて `async def`、`@runtime_checkable` なし（empire §確定 A）|
| （TC-UT-DRR-001 内）| `SqliteDirectiveRepository` の Protocol 充足 | `session_factory` | engine + Alembic 適用済み | `repo: DirectiveRepository = SqliteDirectiveRepository(session)` で型代入が pyright で通る | pyright strict pass、duck typing で 4 method 全 `hasattr` 確認 |

### 基本 CRUD（内部品質基準）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-UT-DRR-002 | `find_by_id` 存在 / 不在 | `session_factory` + `make_directive` + `seeded_room_id` | seeded room | (1) `save(directive)` → `find_by_id(directive.id)` / (2) `find_by_id(uuid4())` | (1) 保存済み Directive を返す / (2) None を返す |
| TC-UT-DRR-003 | `save(directive)` → `find_by_id` round-trip 等価 | `session_factory` + `make_directive` + `seeded_room_id` | empty directives テーブル + seeded room | `save(directive)` → `find_by_id(directive.id)` | 復元 Directive が `id` / `text` / `target_room_id` / `created_at` / `task_id` すべて元 Directive と等価。`created_at` が UTC tz-aware datetime で往復（§確定 R1-G） |
| TC-UT-DRR-006 | `count()` SQL `COUNT(*)` 契約 | `session_factory` + `make_directive` + `seeded_room_id` + `before_cursor_execute` event | DB に複数 Directive 保存済 | `count()` 呼び出し + SQL ログ観測 | `SELECT count(*) FROM directives` が発行される、全行ロード経路が**ない**ことを assert |
| TC-UT-DRR-007 | `save` UPSERT 更新セマンティクス | `session_factory` + `seeded_room_id` | 既存 Directive 保存済み | 同 `directive.id` で `text` を変更して re-save → `find_by_id` | 最新の `text` が返る。古い行は残らない（UPSERT の ON CONFLICT UPDATE が機能する）|
| TC-UT-DRR-008 | `save` after `link_task(task_id)` — `task_id` カラム更新（§確定 R1-G） | `session_factory` + `seeded_room_id` + `make_directive` | task_id=None で保存済み Directive | `directive.link_task(task_id)` → `save(updated)` → `find_by_id` | 復元 Directive の `task_id` が更新済み TaskId と等価。旧 `task_id=None` 行が UPSERT で上書きされている |
| TC-UT-DRR-009 | Tx 境界の責務分離（§確定 R1-B、empire §確定 B 踏襲） | `session_factory` | — | (1) `async with session.begin(): save(directive)` → 別 session で `find_by_id` / (2) `async with session: save(directive)` を `begin()` なしで実行 → session.__aexit__ で rollback | (1) 永続化成功（外側 UoW commit）/ (2) `find_by_id` → None（auto-commit なし、§確定 R1-B 踏襲）|

### `find_by_room` ORDER BY created_at DESC, id DESC（内部品質基準）

**`test_find_by_room.py`** — §確定 R1-D `find_by_room` 専用テストファイル。room-repo の `find_by_name` テンプレートを応用し、新 method の物理確認を担う。

| テストID | 対象 | 種別 | 前提条件 | 操作 | 期待結果 |
|---------|-----|------|---------|------|---------|
| TC-UT-DRR-004 | `find_by_room(room_id)` ORDER BY created_at DESC, id DESC + SQL ログ観測 | 正常系 | seeded room + 3 件の Directive（created_at が意図的に異なる順序で save） | `find_by_room(room_id)` 呼び出し + `before_cursor_execute` event listener で SQL 観測 | (a) 戻り値 list の `created_at` が降順（最新 Directive が先頭）、(b) SQL ログに `ORDER BY created_at DESC, id DESC` が含まれる、(c) 戻り値件数が save した件数と一致 |
| TC-UT-DRR-004b | `find_by_room(room_id)` が空 Room に `[]` を返す | 正常系 | seeded room (Directive なし) | `find_by_room(room_id)` | `[]` 返却（Directive 不在 = リスト空、None 返却ではない）|
| TC-UT-DRR-004c | `find_by_room` が Room スコープを厳密に適用する（クロス Room 分離） | 正常系 | room_a / room_b それぞれに Directive を保存 | `find_by_room(room_a.id)` | room_a の Directive のみ返却、room_b の Directive が混入しない（Room スコープ分離の物理確認）|
| TC-UT-DRR-004d | `find_by_room` での Directive が `_from_row` で正しく復元される | 正常系 | seeded room + MaskedText なし Directive 1 件保存 | `find_by_room(room_id)` | 返却 `Directive` の全属性（id / text / target_room_id / created_at / task_id）が save 時と等価 |
| TC-UT-DRR-004e | `find_by_room` の id DESC tiebreaker — 同時刻 3 件で id 降順返却（**BUG-EMR-001 規約、回帰検出経路**）| 境界値 | seeded room + `created_at` が完全同一の Directive 3 件を save（id は UUID）| `find_by_room(room_id)` | 戻り値の id が `id DESC` 辞書降順で並ぶ。`id DESC` を実装から除去すると非決定的になる = 回帰検出経路として機能 |

### directive §確定 G 実適用 7 経路（受入基準 #11、本 PR の核心テストファイル）

**`test_masking_text.py`** — directive §確定 G を Repository 経由で実適用、room-repo `test_masking_prompt_kit.py` のテンプレート継承。

raw SELECT で `directives.text` の物理格納値を確認し、`MaskedText.process_bind_param` が確実に機能していることを byte-level で証明する。

| テストID | 対象 | 種別 | 入力（directive.text） | 期待結果（DB 物理格納値）|
|---------|-----|------|------|---------|
| TC-IT-DRR-010-masking-discord | Discord Bot Token in directive webhook URL（**本 PR の一次ケース**、directive §確定 G 不可逆性） | 正常系 | `"配信先: https://discord.com/api/webhooks/123456789/{DISCORD_TOKEN}\n通知プレフィックス: CEO 指令"` | raw SQL SELECT で `<REDACTED:DISCORD_TOKEN>` を含む。raw DISCORD_TOKEN 文字列が DB に一切残らない |
| TC-IT-DRR-010-masking-anthropic | Anthropic API key マスキング | 正常系 | `"ANTHROPIC_API_KEY=sk-ant-api03-XXX... を使ってClaude APIを呼ぶこと"` | raw SQL SELECT で `<REDACTED:ANTHROPIC_KEY>` を含む。raw `sk-ant-api03-XXX...` が残らない |
| TC-IT-DRR-010-masking-github | GitHub PAT マスキング | 正常系 | `"git push には ghp_XXX... を使うこと"` | raw SQL SELECT で `<REDACTED:GITHUB_PAT>`。raw `ghp_XXX...` が残らない |
| TC-IT-DRR-010-masking-bearer | Authorization Bearer トークン マスキング | 正常系 | `"APIコール時は Authorization: Bearer eyJhbGci... を使うこと"` | raw SQL SELECT で `<REDACTED:BEARER>`。raw Bearer token が残らない |
| TC-IT-DRR-010-masking-no-secret | secret なしの平文 passthrough | 正常系 | `"チームAにタスクXを割り当て、V モデル設計工程に入ること。"` | raw SQL SELECT で文字列が改変されない（masking が過剰適用されない）|
| TC-IT-DRR-010-masking-roundtrip | directive §確定 G: masking 不可逆性（**§確定 G 申し送り** Repository 経由実適用）| 正常系 | Discord webhook URL 含む directive text | save → `find_by_id` round-trip。復元 `Directive.text` が `<REDACTED:DISCORD_TOKEN>` を含む。raw token が復元不能。`restored != directive`（不可逆性の物理証拠）|
| TC-IT-DRR-010-masking-multiple | 複数 secret（Discord + Anthropic + GitHub）同時マスキング | 正常系 | 3 種の secret を含む directive text | raw SQL SELECT で 3 つの `<REDACTED:*>` センチネルすべて存在。3 つすべての raw token が消滅 |

### Alembic 0006 + target_room_id FK CASCADE + §BUG-DRR-001（内部品質基準）

**`test_alembic_directive.py`** — room-repo `test_alembic_room.py` のテンプレート継承。

| テストID | 対象 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|-----|--------------|---------|------|---------|
| TC-IT-DRR-001 | Alembic 0006 が `directives` テーブル + INDEX + FK を作成 | `empty_engine`（clean DB） | — | `alembic upgrade head` → `SELECT name FROM sqlite_master WHERE type='table'` | (a) `directives` テーブル存在、(b) `SELECT name FROM sqlite_master WHERE type='index'` に `ix_directives_room_created` 含む、(c) `PRAGMA foreign_key_list('directives')` に `rooms` への FK 含む |
| TC-IT-DRR-002 | Alembic chain 0001→...→0006 が単一 head（分岐なし）| — | alembic.ini 存在 | `ScriptDirectory.get_heads()` | `len(heads) == 1`（head 分岐なし）|
| TC-IT-DRR-003 | upgrade head → downgrade base → upgrade head が idempotent | `empty_engine` | — | 二重サイクル実行 | 最終状態で `directives` テーブルが存在、downgrade 後は消滅、再 upgrade 後に再出現 |
| TC-IT-DRR-004 | `0006_directive_aggregate.down_revision == "0005_room_aggregate"` | — | alembic.ini 存在 | `ScriptDirectory.get_revision("0006_directive_aggregate").down_revision` | `"0005_room_aggregate"` と等しい（chain 一直線の物理確認）|
| TC-IT-DRR-005 | `target_room_id` FK ON DELETE CASCADE（§確定 R1-B）| `session_factory` + `seeded_room_id` + `make_directive` | seeded room に Directive を保存済み | raw SQL `DELETE FROM rooms WHERE id = :room_id` 実行 → `SELECT * FROM directives WHERE target_room_id = :room_id` | Directive 行が自動削除（CASCADE 発火）。`SELECT` 結果が空になる |
| TC-IT-DRR-006 | §BUG-DRR-001: 0006 で `task_id → tasks.id` FK が存在しないことを物理確認 | `session_factory` | Alembic 0006 適用済み | `PRAGMA foreign_key_list('directives')` で FK 一覧取得 | FK 参照テーブル一覧に `tasks` が**含まれない**。0006 時点での forward reference 問題回避（task-repository PR で FK closure 申し送り）|

### CI 三層防衛 Directive 拡張（内部品質基準）

| テストID | 対象 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|-----|--------------|---------|------|---------|
| TC-UT-DRR-arch | Layer 2: `tests/architecture/test_masking_columns.py` の Directive parametrize 拡張 | `Base.metadata` | M2 永続化基盤の arch test に masking 検証構造あり | parametrize に `("directives", "text", MaskedText)` を追加。`column.type.__class__ is MaskedText` を assert、他カラムは Masked* 不在を assert | pass（`directives.text` は `MaskedText`、他 4 カラムは masking なし）。後続 PR が誤って `text` を `Text` に変更した瞬間に落下して PR ブロック |
| TC-DOC-DRR-001 | storage.md §逆引き表 Directive 行存在 | repo root | `docs/design/domain-model/storage.md` 編集済み | `tests/docs/test_storage_md_back_index.py` で Directive 行検証 | `directives.text: MaskedText`（directive §確定 G 実適用）行が §逆引き表に存在。`directives` 残カラム（id / target_room_id / created_at / task_id）が masking 対象なしとして登録 |

### Lifecycle 統合シナリオ

| テストID | 対象 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|-----|--------------|---------|------|---------|
| TC-IT-DRR-LIFECYCLE | 4 method 全経路 — save → find_by_room → save（更新）連携 | `session_factory` + `seeded_room_id` + `make_directive` | empty directives テーブル + seeded room | (1) `save(d1)` / `save(d2)` / `save(d3)` → (2) `find_by_room(room_id)` → 3 件、created_at DESC, id DESC 順 → (3) `d1.link_task(task_id)` → `save(d1_updated)` → (4) `count()` → 3 → (5) `find_by_id(d2.id)` → d2 | 各段階で valid Directive を返す。link_task → re-save が UPSERT で task_id を更新。masking なし（plain text）なので round-trip equality 成立。`count()` は `SELECT count(*)` 単独発行 |

## ユニットテストケース

**該当なし（DB 経由の物理確認に集約）** — 理由:

- agent-repo / workflow-repo / room-repo と同方針: Repository 層は SQLite + Alembic + MaskingGateway の実 I/O が責務の本質
- `_to_row` / `_from_row` のラウンドトリップは TC-UT-DRR-003 + TC-UT-DRR-008 で integration として物理確認
- domain layer のテストは directive domain sub-feature #24 で完了済み（本 sub-feature スコープ外）

## カバレッジ基準

- REQ-DRR-001〜005 すべてに最低 1 件のテストケース
- **directive §確定 G 実適用 7 経路**（discord / anthropic / github / bearer / no-secret / roundtrip / multiple）すべてに正常系ケース、TC-IT-DRR-010-masking-* で物理確認（受入基準 #11）
- **find_by_room ORDER BY created_at DESC, id DESC**（§確定 R1-D）: TC-UT-DRR-004 で 4 経路（降順確認 / 空リスト / Room スコープ分離 / _from_row 往復）すべてに証拠。TC-UT-DRR-004e で同時刻 tiebreaker（id DESC）の物理確認（BUG-EMR-001 規約、回帰検出経路）
- **target_room_id FK ON DELETE CASCADE**（§確定 R1-B）: TC-IT-DRR-005 で Room 削除時の Directive 自動削除を物理確認
- **§BUG-DRR-001 FK 申し送り確認**（§確定 R1-C）: TC-IT-DRR-006 で `PRAGMA foreign_key_list` に `tasks` 参照が存在しないことを物理確認
- **save(directive) 1 引数 + UPSERT セマンティクス**（§確定 R1-F）: TC-UT-DRR-003 + TC-UT-DRR-007 + TC-UT-DRR-008 で 3 経路（初回保存 / 更新 / task_id 更新）すべてに証拠
- **created_at UTC tz-aware 往復**（§確定 R1-G）: TC-UT-DRR-003 で timezone-aware datetime が SQLite `DateTime(timezone=True)` 経由で往復することを確認
- **Alembic chain 一直線**: TC-IT-DRR-004 で head 分岐なし + `0006.down_revision == "0005_room_aggregate"` を物理確認
- **upgrade/downgrade idempotent**: TC-IT-DRR-003 で双方向 migration を物理確認
- **CI 三層防衛**（§確定 R1-E）: Layer 1 grep（CI ジョブ）+ Layer 2 arch（TC-UT-DRR-arch）+ Layer 3 storage.md（TC-DOC-DRR-001）3 つすべてに証拠
- C0 目標: `infrastructure/persistence/sqlite/repositories/directive_repository.py` で **90% 以上**（room-repo 同水準）

## 人間が動作確認できるタイミング

本 sub-feature は infrastructure 層単独だが、**M2 永続化基盤と同じく Backend プロセスを実起動して動作確認できる**。

- CI 統合後: `gh pr checks` で 7 ジョブ緑
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/infrastructure/persistence/sqlite/repositories/test_directive_repository tests/infrastructure/persistence/sqlite/test_alembic_directive.py tests/architecture/test_masking_columns.py tests/docs/test_storage_md_back_index.py -v` → 全テスト緑
- Backend 実起動: `cd backend && uv run python -m bakufu`（環境変数 `BAKUFU_DATA_DIR=/tmp/bakufu-test` を設定）
  - 起動時に Alembic auto-migrate で 0001〜0006 が適用されることをログで目視
  - `sqlite3 <DATA_DIR>/bakufu.db ".tables"` で `directives` テーブルが存在することを目視
  - `sqlite3 <DATA_DIR>/bakufu.db "PRAGMA foreign_key_list(directives)"` で `rooms.id` への FK 1 件が存在、`tasks` への FK が存在しないことを目視
- masking 物理確認: `uv run pytest tests/.../test_masking_text.py -v` → 7 ケース緑、raw token が DB に残らないことを目視
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.application.ports.directive_repository --cov=bakufu.infrastructure.persistence.sqlite.repositories.directive_repository --cov-report=term-missing` → 90% 以上

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      directive.py                                  # 新規（make_directive / make_directive_with_task / make_directive_with_secret_text）
    architecture/
      test_masking_columns.py                       # 既存更新: Directive full-mask parametrize 拡張
                                                    # TC-UT-DRR-arch
    infrastructure/
      persistence/
        sqlite/
          repositories/
            test_directive_repository/              # 新規ディレクトリ（3 ファイル分割）
              __init__.py
              conftest.py                            # seed_room helper（FK 解決用: empire + workflow + room をシード）
              test_protocol_crud.py                  # TC-UT-DRR-001〜009 + TC-IT-DRR-LIFECYCLE
              test_find_by_room.py                   # TC-UT-DRR-004 / 004b / 004c / 004d / 004e
              test_masking_text.py                   # TC-IT-DRR-010-masking-* (7 ケース、directive §確定 G 実適用核心)
          test_alembic_directive.py                  # TC-IT-DRR-001〜006（Alembic 0006 chain + DDL + FK CASCADE + §BUG-DRR-001）
    docs/
      test_storage_md_back_index.py                  # 既存更新: Directive 行検証（TC-DOC-DRR-001）
```

### `conftest.py` 設計: `seed_room` helper

`directives.target_room_id → rooms.id ON DELETE CASCADE` FK を満たすため、Directive を INSERT する前に `rooms` 行が存在している必要がある。`rooms` 行は `empires` / `workflows` の FK 先も必要。

```
conftest.py 提供内容:
  - seeded_room_id: UUID (fixture)   — empire + workflow + room を raw SQL で seed し room_id を返す
  - seed_room(session_factory, ...) — 複数 Room が必要なテスト用 helper (make_directive_with_room cross-isolation テスト等)
```

`seed_room` helper は empire-repository の `seed_rooms()` と同パターン（raw SQL INSERT OR IGNORE でシードし、既存行との衝突を idempotent に回避）。Directive テスト固有の依存グラフ:

```
empires (INSERT OR IGNORE)
  └── workflows (INSERT OR IGNORE)
        └── rooms (INSERT OR IGNORE)  ← seed_room が提供
              └── directives          ← テスト本体が save
```

**配置の根拠**:
- `test_masking_text.py` を独立ファイルにするのは **directive §確定 G 実適用が本 PR の核心**であり、room-repo `test_masking_prompt_kit.py` の full-mask masking テストパターンを継承するため
- `test_find_by_room.py` を独立ファイルにするのは `find_by_room` が本 PR 固有の拡張 method であり、500 行ルール（empire-repo PR #29 / agent-repo PR #45 教訓）に従い最初から分割するため（`find_by_task_id` は YAGNI — task-repository PR で method + INDEX + FK closure を同時追加）
- `test_alembic_directive.py` は agent / workflow / room の `test_alembic_*.py` 同パターン + **§BUG-DRR-001 FK 未追加の物理確認**（TC-IT-DRR-006）を担う

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| Directive 後続申し送り #1 | masked `text` の LLM Adapter 配送経路（directive §確定 G 不可逆性）| `feature/llm-adapter`（後続） | 「`<REDACTED:*>` を含む Directive.text は配送停止 + ログ警告」契約を凍結する責務（room-repo 申し送り #1 と同パターン）|
| Directive 後続申し送り #2 | §BUG-DRR-001: `directives.task_id → tasks.id` FK closure | `feature/task-repository`（後続 Issue #35）| task-repository PR で `op.batch_alter_table('directives')` + `create_foreign_key('fk_directives_task_id', 'tasks', ['task_id'], ['id'], ondelete='RESTRICT')` を追加。詳細設計 §確定 R1-C / §BUG-DRR-001 参照 |
| Directive 後続申し送り #3 | `find_by_task_id` の method 追加 + `task_id` INDEX 追加 | `feature/task-repository`（後続 Issue #35）| YAGNI — 現時点で `find_by_task_id` の呼び出し元が存在しない。task-repository PR で FK closure と同時に method + INDEX を追加し、対応するテストケース（TC-UT-DRR-005 系）も起票する |

**Schneier 申し送り（本 PR 固有）**:

- **directive §確定 G 実適用**: agent-repo `Persona.prompt_body` / room-repo `PromptKit.prefix_markdown` パターン継承 3 件目。persistence-foundation #23 で hook 構造提供済み → 本 PR で `directives.text` に配線完了
- **§BUG-DRR-001 forward reference**: empire-repo §BUG-EMR-001 → room-repo §確定 R1-C で確立した申し送りパターンの 3 件目。task-repository PR で物理 close

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-DRR-001〜005 すべてに 1 件以上のテストケースがあり、特に integration が Repository 契約 + Alembic + masking 配線 + CI 三層防衛を単独でカバーしている
- [ ] **directive §確定 G 実適用 7 経路**（discord / anthropic / github / bearer / no-secret / roundtrip / multiple）すべてに TC-IT-DRR-010-masking-* で物理確認（受入基準 #11）
- [ ] **find_by_room ORDER BY created_at DESC, id DESC**（§確定 R1-D）が TC-UT-DRR-004 で SQL ログ `ORDER BY created_at DESC, id DESC` + 降順一覧 + Room スコープ分離を物理確認。TC-UT-DRR-004e で同時刻 tiebreaker（id DESC 回帰検出）を物理確認
- [ ] **target_room_id FK ON DELETE CASCADE**（§確定 R1-B）が TC-IT-DRR-005 で Room 削除時の Directive 自動削除を物理確認
- [ ] **§BUG-DRR-001 FK 申し送り確認**（§確定 R1-C）が TC-IT-DRR-006 で `PRAGMA foreign_key_list('directives')` に `tasks` 参照が存在しないことを物理確認
- [ ] **save(directive) 1 引数 + UPSERT セマンティクス**（§確定 R1-F）が TC-UT-DRR-003 / 007 / 008 で 3 経路（初回 / 更新 / task_id 更新）すべて確認
- [ ] **created_at UTC tz-aware 往復**（§確定 R1-G）が TC-UT-DRR-003 で確認
- [ ] **CI 三層防衛**（§確定 R1-E）: Layer 1 grep（CI）+ Layer 2 arch（TC-UT-DRR-arch）+ Layer 3 storage.md（TC-DOC-DRR-001）の 3 つすべてに証拠
- [ ] **Alembic chain 一直線**: TC-IT-DRR-004 で `0006.down_revision == "0005_room_aggregate"` を物理確認
- [ ] **upgrade/downgrade idempotent**: TC-IT-DRR-003 で双方向 migration を物理確認
- [ ] **§確定 R1-A〜G すべてに証拠ケース**（empire §確定 A〜F 継承確認）
- [ ] **テストファイル分割（3 ファイル）が basic-design.md §モジュール構成と整合**
- [ ] directive §確定 G 実適用クローズが PR 本文に明示されている
- [ ] §BUG-DRR-001 の申し送り先（task-repository PR）が detailed-design.md §Known Issues に明記されている
