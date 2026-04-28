# テスト設計書

<!-- feature: room-repository -->
<!-- 配置先: docs/features/room-repository/test-design.md -->
<!-- 対象範囲: REQ-RR-001〜006 / 受入基準 1〜18 / 詳細設計 §確定 A〜H / room §確定 G 実適用物理確認 + BUG-EMR-001 Stage 2 closure -->

本 feature は M2 Repository **5 番目の Aggregate Repository PR**（empire / workflow / agent 後）。room Aggregate（M1、PR #22 マージ済み）に対する Repository 層を新規追加する。テンプレートは agent-repository (PR #45) を 100% 継承し、**5 method Protocol**（`find_by_id` / `count` / `save` / `find_by_name` / `count_by_empire`）と **2 つの masking 対象を扱う partial-mask テーブル**（`rooms.prompt_kit_prefix_markdown`）の構造を確立する。

agent-repo のテンプレートを継承しつつ、room-repository 固有の論点 5 件を**専用テストファイルで物理保証**する:

1. **`prompt_kit_prefix_markdown` MaskedText**（room §確定 G 実適用）— Schneier 多層防御を Repository 経由で物理確認、不可逆性は LLM Adapter 申し送り
2. **`find_by_name(empire_id, name)` Empire スコープ強制**（§確定 R1-F）— IDOR 防御、INDEX(empire_id, name) 利用
3. **`(room_id, agent_id, role)` UNIQUE 二重防衛**（§確定 R1-D）— Aggregate 検査 + DB 物理拒否
4. **BUG-EMR-001 Stage 2 closure**（§確定 R1-C）— `empire_room_refs.room_id → rooms.id` FK が Alembic 0005 で `op.batch_alter_table` 経由で追加されることを物理確認
5. **`workflow_id` FK ON DELETE RESTRICT**（§確定 R1-B）— Workflow 削除が Room 存在時に拒否されることを物理確認

**最初から 4 ファイル分割**（empire-repo PR #29 / agent-repo PR #45 Norman R-N1 教訓継承）。`test_masking_prompt_kit.py` が room §確定 G 実適用の物理確認を担う本 PR 固有のテストファイル。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-RR-001 | `RoomRepository` Protocol 5 method 定義 | TC-UT-RR-001 | ユニット | 正常系 | 1, 2 |
| REQ-RR-002（save 3 段階） | `SqliteRoomRepository.save(room, empire_id)` の delete-then-insert | TC-UT-RR-002 | ユニット | 正常系 | 3 |
| REQ-RR-002（find_by_id ORDER BY） | `room_members` SELECT の `ORDER BY agent_id, role` | TC-UT-RR-003 | ユニット | 正常系 | 4 |
| REQ-RR-002（count SQL）| `count()` が SQL `COUNT(*)` を発行 | TC-UT-RR-004 | ユニット | 正常系 | 5 |
| REQ-RR-002（find_by_name）| Empire スコープ検索（4th method） | TC-UT-RR-005 | ユニット | 正常系 / 異常系 | 6 |
| REQ-RR-002（count_by_empire）| Empire スコープ COUNT(*)（5th method） | TC-UT-RR-006 | ユニット | 正常系 | 7 |
| REQ-RR-002（save 引数 §確定 H）| `save(room, empire_id)` で empire_id 引数経由（Room に empire_id 属性なし） | TC-UT-RR-007 | ユニット | 正常系 | （責務境界） |
| **REQ-RR-002（masking、§確定 R1-E）** | raw `prompt_kit.prefix_markdown` → DB に `<REDACTED:*>` 永続化（**room §確定 G 実適用**）| TC-IT-RR-008-masking-* (7 経路) | 結合 | 正常系 | 8 |
| REQ-RR-003（UNIQUE 二重防衛）| `(room_id, agent_id, role)` 重複 INSERT で `IntegrityError`（§確定 R1-D）| TC-IT-RR-009 | 結合 | 異常系 | 9 |
| REQ-RR-003（workflow_id FK RESTRICT）| Room 存在時に `DELETE FROM workflows` で `IntegrityError`（§確定 R1-B）| TC-IT-RR-010 | 結合 | 異常系 | 10 |
| REQ-RR-003（BUG-EMR-001 closure）| Alembic 0005 で `empire_room_refs.room_id → rooms.id` FK が追加（§確定 R1-C）| TC-IT-RR-011 | 結合 | 正常系 | 12 |
| REQ-RR-003（Alembic 0005）| 2 テーブル + UNIQUE + INDEX(empire_id, name) + 3 FK + empire_room_refs FK closure | TC-IT-RR-012 | 結合 | 正常系 | 11, 12, 13, 14 |
| REQ-RR-004（CI Layer 1）| grep guard で `rooms.prompt_kit_prefix_markdown` の `MaskedText` 必須 | （CI ジョブ） | — | — | 15 |
| REQ-RR-004（CI Layer 2）| arch test parametrize（`_PARTIAL_MASK_TABLES` に `rooms` 追加） | TC-UT-RR-013-arch | ユニット | 正常系 | 15 |
| REQ-RR-005（storage.md） | §逆引き表更新（`rooms` partial-mask + `room_members` no-mask） | TC-DOC-RR-001 | doc 検証 | 正常系 | 15 |
| REQ-RR-006（empire-repo BUG-EMR-001 sync） | empire-repository §Known Issues §BUG-EMR-001 status を RESOLVED に更新 | （コードレビュー）| — | — | 16 |
| AC-17（依存方向・lint/typecheck）| `pyright --strict` / `ruff check` エラーゼロ（依存方向違反含む） | （CI ジョブ）| — | — | 17 |
| AC-18（coverage）| カバレッジが Room Repository 配下で 95% 以上 | （CI ジョブ）| — | — | 18 |
| 確定 A（テンプレ継承） | empire/workflow/agent §確定 A〜F + §BUG-EMR-001 + agent §確定 R1-C | TC-UT-RR-001〜007 全件 | ユニット | — | — |
| 確定 B（save 3 段階） | DML 順序の物理確認 | TC-UT-RR-002 | ユニット | 正常系 | 3 |
| 確定 C（_to_row / _from_row）| 双方向変換 + empire_id 引数経由 | TC-UT-RR-014-roundtrip | ユニット | 正常系 | — |
| 確定 D（count SQL）| `select(func.count())` の物理確認 | TC-UT-RR-004 / TC-UT-RR-006 | ユニット | 正常系 | 5, 7 |
| 確定 E（CI 三層防衛 partial-mask 拡張） | 正のチェック + 負のチェック併用 | TC-UT-RR-013-arch + TC-DOC-RR-001 | ユニット / doc | 正常系 | 15 |
| 確定 F（find_by_name 契約） | Empire スコープで RoomId → find_by_id 委譲 | TC-UT-RR-005 | ユニット | 正常系 / 異常系 | 6 |
| 確定 G（count_by_empire 契約） | Empire スコープで SQL COUNT(*) | TC-UT-RR-006 | ユニット | 正常系 | 7 |
| **確定 H（save(room, empire_id) signature）** | Room に empire_id 属性なし、引数で受け取る | TC-UT-RR-007 + TC-UT-RR-014-roundtrip | ユニット | 正常系 | （責務境界） |
| 確定 I（4 ファイル分割） | test_*.py 全ファイル 500 行未満 | （静的確認） | — | — | — |
| **room §確定 G（masking 不可逆性、Repository 実適用）** | masked `prompt_kit_prefix_markdown` 復元時に raw 戻らない | TC-IT-RR-008-masking-roundtrip | 結合 | 正常系 | 8 |
| **§BUG-EMR-001 Stage 2 closure** | Alembic 0005 で empire_room_refs.room_id FK 追加、empire 削除で room_members CASCADE 削除 | TC-IT-RR-011 + TC-IT-RR-012 | 結合 | 正常系 | 11, 12 |
| **lifecycle 統合** | save → find_by_name → find_by_id → save（更新）の 5 method 連携 | TC-IT-RR-LIFECYCLE | 結合 | 正常系 | 1, 6, 7 |

**マトリクス充足の証拠**:

- REQ-RR-001〜006 すべてに最低 1 件のテストケース（REQ-RR-006 はコードレビューで確認）
- **room §確定 G 実適用 7 経路**（anthropic / github / openai / bearer / no-secret / roundtrip / multiple）すべてに TC-IT-RR-008-masking-* で物理確認、raw token が DB に残らないことを assert（agent-repo `prompt_body` のテンプレート継承）
- **find_by_name Empire スコープ強制**（§確定 R1-F、IDOR 防御）: TC-UT-RR-005 で 3 経路（ヒット / 不在 / 異 Empire 同 name）+ SQL ログ観測で `WHERE empire_id=?` + `LIMIT 1` の物理確認
- **count_by_empire** （§確定 R1-G）: TC-UT-RR-006 で SQL `COUNT(*)` + `WHERE empire_id=?` の物理確認、INDEX(empire_id, name) 左端プリフィックス利用
- **(room_id, agent_id, role) UNIQUE 二重防衛**（§確定 R1-D）: TC-IT-RR-009 で直接 INSERT 経路で `IntegrityError` 物理確認（Aggregate 経由しない）
- **workflow_id FK ON DELETE RESTRICT**（§確定 R1-B）: TC-IT-RR-010 で Room 存在時の Workflow 削除拒否を物理確認
- **BUG-EMR-001 Stage 2 closure**（§確定 R1-C）: TC-IT-RR-011 で Alembic 0005 適用後 `empire_room_refs.room_id` FK が SQLite に追加されたことを `PRAGMA foreign_key_list` で物理確認 + `op.batch_alter_table(recreate='always')` 経由の冪等性
- **save(room, empire_id) signature**（§確定 H）: TC-UT-RR-007 で empire_id 引数経由の保存 + Room domain の empire_id 属性不在を確認
- empire-repo / workflow-repo / agent-repo テンプレート継承（§確定 A〜F + §BUG-EMR-001）を TC-UT-RR-001〜007 全件で確認
- 受入基準 1〜18 のうち 1〜11 は unit/integration ケース、12〜14（Migration/DB 制約物理確認）は TC-IT-RR-011/012 で担保、15〜16（CI 三層防衛・doc・empire-repo sync）は CI/コードレビュー担保、17〜18（lint/typecheck/coverage）は CI ジョブ担保
- 確定 A〜H すべてに証拠ケース
- 孤児要件ゼロ

## 外部 I/O 依存マップ

本 feature は infrastructure 層の Repository 実装。empire-repo / workflow-repo / agent-repo と同方針で本物の SQLite + 本物の Alembic + 本物の SQLAlchemy AsyncSession を使う。

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **SQLite (sqlite+aiosqlite)** | engine / session / 2 テーブル / Alembic 0005 migration | 不要（実 DB を `tmp_path` 配下の bakufu.db で起動、テストごとに使い捨て） | 不要 | **済（M2 永続化基盤 conftest の `app_engine` / `session_factory` fixture を再利用）** |
| **ファイルシステム** | `BAKUFU_DATA_DIR` / `bakufu.db` / WAL/SHM | 不要（`pytest.tmp_path`） | 不要 | **済（本物使用）** |
| **Alembic** | 0005 revision の `upgrade head` / `downgrade base` + `op.batch_alter_table` 経由の empire_room_refs FK closure | 不要（本物の `alembic upgrade` を実 SQLite に対し実行） | 不要 | **済（本物使用、persistence-foundation の `run_upgrade_head` を再利用）** |
| **SQLAlchemy 2.x AsyncSession** | UoW 境界 / Repository メソッド経由の SQL 発行 | 不要 | 不要 | **済（本物使用）** |
| **MaskingGateway (`mask`)** | `MaskedText.process_bind_param` 経由で `prompt_kit_prefix_markdown` をマスキング | 不要（実 init を `_initialize_masking` autouse fixture で実施） | 不要 | **済（persistence-foundation #23 で characterization 完了、本 PR で配線実適用）** |

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `make_room`（既存、room feature #22 由来） | `Room`（valid デフォルト = LeaderMembership 1 件 + 空 prompt_kit） | `True` |
| `make_populated_room`（既存） | `Room`（複数 member、Repository round-trip 用） | `True` |
| `make_room_with_secret_prompt_kit`（**本 PR で追加**） | `Room`（`prompt_kit.prefix_markdown` に raw secret 形式文字列を含む、`test_masking_prompt_kit.py` 専用） | `True` |
| `make_agent_membership`（既存） | `AgentMembership` | `True` |
| `make_leader_membership`（既存） | `AgentMembership(role=LEADER)` | `True` |
| `make_prompt_kit`（既存） | `PromptKit` | `True` |

`tests/factories/room.py` は room feature #22 で確立済み。本 PR では `make_room_with_secret_prompt_kit` を 1 件追加（`test_masking_prompt_kit.py` 専用、agent-repo の `AgentWithSecretsFactory` 同パターン）。

**raw fixture / characterization は不要**: SQLite + SQLAlchemy + Alembic + MaskingGateway はすべて標準ライブラリ仕様 / 既存 characterization 完了済みの動作で固定、外部観測（実 DB ファイル）が真実源として常時使える。

## E2E テストケース

**該当なし** — 理由:

- 本 feature は infrastructure 層単独で、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない
- Repository は内部 API（Python module-level の Protocol / Class）のみ提供
- 戦略ガイド §E2E対象の判断「内部 API・ライブラリなどエンドユーザー操作がない場合は結合テストで代替可」に従い、E2E は本 feature 範囲外
- 後続 `feature/room-application` / `feature/admin-cli`（`bakufu admin room list` 等）/ `feature/http-api`（Room CRUD）が公開 I/F を実装した時点で E2E を起票

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — infrastructure 層のため公開 I/F なし | — | — |

## 結合テストケース

「Repository 契約 + 実 SQLite + 実 Alembic + 実 MaskingGateway」を contract testing する層。M2 永続化基盤の `app_engine` / `session_factory` fixture を再利用。

### Protocol 定義 + 充足（受入基準 1, 2、§確定 A）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-UT-RR-001 | `RoomRepository` Protocol が **5 method** を宣言 | — | `application/ports/room_repository.py` がインポート可能 | `from bakufu.application.ports.room_repository import RoomRepository` | Protocol が `find_by_id` / `count` / `save` / `find_by_name` / `count_by_empire` の **5 method** を宣言、すべて `async def`、`@runtime_checkable` なし |
| （TC-UT-RR-001 内） | `SqliteRoomRepository` の Protocol 充足 | `app_engine` + `session_factory` | engine + Alembic 適用済み | `repo: RoomRepository = SqliteRoomRepository(session)` で型代入が pyright で通る | pyright strict pass、duck typing で 5 method 全 hasattr 確認 |

### 基本 CRUD（受入基準 3〜7、§確定 B / D / F / G / H）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-UT-RR-002 | `save(room, empire_id)` の 3 段階 DML 順序（§確定 B） | `session_factory` + `app_engine` + `before_cursor_execute` event listener + `make_populated_room` | empty DB（empires 行 seed 済） | (1) `save(room, empire_id)` → 既存 room を members 変更で再 save | DML 順序が `INSERT INTO rooms (UPSERT)` → `DELETE FROM room_members` → `INSERT INTO room_members` の 3 段階。SQL ログで物理確認 |
| TC-UT-RR-003 | `find_by_id` の `ORDER BY agent_id, role` 規約（§BUG-EMR-001 継承） | `session_factory` + `app_engine` | 同 room_id で複数 member（順序逆挿入）| `find_by_id(room.id)` を呼びつつ SQL ログ観測 | (a) 戻り値 members が `(agent_id, role)` 昇順、(b) SQL ログに `ORDER BY agent_id, role` が含まれる |
| TC-UT-RR-004 | `count()` SQL 契約（§確定 D） | `session_factory` + `app_engine` | DB に複数 Room 保存済 | `count()` 呼び出し + SQL ログ観測 | `SELECT count(*) FROM rooms` 単独発行、全行ロード経路（`SELECT id FROM rooms`）が**ない**ことを assert |
| TC-UT-RR-005 | `find_by_name(empire_id, name)` 契約（§確定 F、IDOR 防御） | `session_factory` + `app_engine` + `make_room` | (1) DB に `(empire_a, 'room_a')` の Room / (2) 不在 / (3) 異 Empire で同 name | (1) `find_by_name(empire_a, 'room_a')` → Room 取得 / (2) `find_by_name(empire_a, 'nonexistent')` → None / (3) `find_by_name(empire_b, 'room_a')` → **None**（IDOR guard）+ SQL ログで `WHERE empire_id=?` + `LIMIT 1` 物理確認 | 3 経路すべて期待通り、cross-Empire isolation 物理保証 |
| TC-UT-RR-006 | `count_by_empire(empire_id)` 契約（§確定 G） | `session_factory` + `app_engine` | DB に empire_a で 3 件、empire_b で 2 件の Room | (1) `count_by_empire(empire_a)` → 3、(2) `count_by_empire(empire_b)` → 2、(3) SQL ログで `SELECT count(*) FROM rooms WHERE empire_id=?` 物理確認 | Empire-scoped COUNT(*) 動作、INDEX(empire_id, name) 左端プリフィックス利用 |
| TC-UT-RR-007 | `save(room, empire_id)` 引数経由の保存（§確定 H） | `session_factory` + `make_room` | Room domain に empire_id 属性なし | (1) `save(room, empire_id_a)` 保存、(2) raw SQL `SELECT empire_id FROM rooms WHERE id=?` で確認 | empire_id 引数の値が `rooms.empire_id` カラムに永続化、Room VO 自体は empire_id を持たない |

### room §確定 G 実適用 7 経路（受入基準 8、本 PR の核心テストファイル）

**`test_masking_prompt_kit.py`** — room §確定 G を Repository 経由で実適用、agent-repo `test_masking_persona.py` のテンプレート継承。

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-IT-RR-008-masking-anthropic | Anthropic API key マスキング | 正常系 | raw `prompt_kit.prefix_markdown='Use ANTHROPIC_API_KEY=sk-ant-api03-XXX...'` | DB raw SELECT で `<REDACTED:ANTHROPIC_KEY>` を含む、raw `sk-ant-api03-XXX...` が一切残らない（grep で 0 hit） |
| TC-IT-RR-008-masking-github | GitHub PAT マスキング | 正常系 | raw `prefix_markdown='Use ghp_XXX... for git push'` | DB raw SELECT で `<REDACTED:GITHUB_PAT>`、raw `ghp_XXX...` が残らない |
| TC-IT-RR-008-masking-openai | OpenAI key マスキング | 正常系 | raw `prefix_markdown='OPENAI_API_KEY=sk-XXX...'`（non-Anthropic） | DB raw SELECT で `<REDACTED:OPENAI_KEY>` |
| TC-IT-RR-008-masking-bearer | Bearer token マスキング | 正常系 | raw `prefix_markdown='Authorization: Bearer XXX'` | DB raw SELECT で `<REDACTED:BEARER>` |
| TC-IT-RR-008-masking-no-secret | secret なしの passthrough | 正常系 | raw `prefix_markdown='You are a helpful assistant.'` | DB raw SELECT で文字列が改変されない（masking 適用範囲外） |
| TC-IT-RR-008-masking-roundtrip | room §確定 G: masking 不可逆性（Repository 実適用） | 正常系 | save → find_by_id 経路 | 復元 `Room.prompt_kit.prefix_markdown` が `<REDACTED:*>` を含む、元 token が復元不能、`restored != room`（不可逆性の物理証拠） |
| TC-IT-RR-008-masking-multiple | 複数 secret 同時マスキング | 正常系 | raw `prefix_markdown` に 3 種 secret 混在 | すべて `<REDACTED:*>` 化、raw token 全消滅 |

### DB 制約 二重防衛（受入基準 9, 10、§確定 R1-B / R1-D）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-RR-009 | §確定 R1-D: `(room_id, agent_id, role)` UNIQUE 二重防衛 | `session_factory` + 直接 INSERT 経路（Aggregate 経由しない） | save 済 Room | 同じ `(room_id, agent_id, role)` トリプルを 2 行 raw SQL で INSERT | 2 行目で `sqlalchemy.exc.IntegrityError`（UNIQUE 違反）、Aggregate 検査を迂回した経路で DB が物理拒否 |
| TC-IT-RR-010 | §確定 R1-B: `workflow_id` FK ON DELETE RESTRICT | `session_factory` + `make_room` | Room が `workflow_id=workflow_a` で存在 | raw SQL `DELETE FROM workflows WHERE id=:workflow_a` を実行 | `IntegrityError`（FK RESTRICT 違反）、Workflow 削除が拒否される（Workflow は Room の参照先であり owner ではない） |

### Alembic 0005 + BUG-EMR-001 Stage 2 closure（受入基準 11〜14、§確定 R1-C）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-RR-011 | §確定 R1-C: BUG-EMR-001 Stage 2 closure（empire_room_refs.room_id FK 追加） | `tmp_path` 配下の bakufu.db | M1 + M2 + 0001〜0004 適用済み | (1) `alembic upgrade head` で 0005 適用、(2) `PRAGMA foreign_key_list(empire_room_refs)` で FK 一覧取得、(3) raw SQL `INSERT INTO empire_room_refs (empire_id, room_id, name, archived) VALUES (...)` で **存在しない room_id を渡す** | (a) FK 一覧に `(room_id, rooms, id)` が含まれる、(b) 存在しない room_id 経路で `IntegrityError`（FK 違反）。BUG-EMR-001 物理 close |
| TC-IT-RR-012 | Alembic 0005 マイグレーション全体 | clean DB | initial revision 適用済み | (1) `alembic upgrade head` 実行、(2) `SELECT name FROM sqlite_master WHERE type='table'` で `rooms` / `room_members` の 2 テーブル追加確認、(3) `SELECT name, sql FROM sqlite_master WHERE type='index'` で `INDEX(empire_id, name)` non-UNIQUE + `UNIQUE(room_id, agent_id, role)` 確認、(4) `alembic downgrade base` で逆順削除 | 2 テーブル + UNIQUE 制約 + INDEX(empire_id, name) + 3 FK が SQLite に作成、`empire_room_refs.room_id` FK closure 含む。`alembic downgrade -1` で逆順削除（rooms テーブル削除前に room_members + empire_room_refs FK drop が走る） |

### CI 三層防衛 partial-mask 拡張（受入基準 15、§確定 E）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-UT-RR-013-arch | Layer 2: `tests/architecture/test_masking_columns.py` の Room parametrize 拡張 | `Base.metadata` | M2 永続化基盤の arch test に `_PARTIAL_MASK_TABLES` 構造あり | parametrize に `("rooms", "prompt_kit_prefix_markdown")` を追加、`column.type.__class__ is MaskedText` を assert、他カラムは Masked* 不在を assert | 全 2 テーブルで pass（`rooms` partial-mask + `room_members` no-mask）。後続 PR が誤って `MaskedText` を Room の他カラムに追加した瞬間、この test が落下して PR ブロック |
| TC-DOC-RR-001 | storage.md §逆引き表 Room 行存在 | repo root | `docs/architecture/domain-model/storage.md` 編集済み | `tests/docs/test_storage_md_back_index.py` で Room 行検証 | partial-mask 1 行（`rooms.prompt_kit_prefix_markdown` + `MaskedText`）+ no-mask 行（`room_members` + Room 残カラム）が co-located |

### Lifecycle 統合シナリオ

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-RR-LIFECYCLE | save → find_by_name → find_by_id → save（更新） + count_by_empire | `session_factory` + `make_room` | empty DB（empire seed 済） | (1) `save(room_a, empire_id)` → (2) `find_by_name(empire_id, room_a.name)` → Room 取得 → (3) `find_by_id(room.id)` で再取得 → (4) member 追加で再構築 → `save(updated_room, empire_id)` → (5) `count_by_empire(empire_id)` → 1 | 各段階で valid Room を返す、member 変更が delete-then-insert で永続化、`prompt_kit_prefix_markdown` masking が再 save でも適用 |
| TC-UT-RR-014-roundtrip | `_to_row(room, empire_id)` / `_from_row` 双方向変換（§確定 C, H） | `make_room` | members を含む Room | `_from_row(_to_row(room, empire_id))` が元 Room と構造的等価（masking なしの場合） | Pydantic frozen `==` 判定で等価、empire_id は dict 経由で受け渡される（Room VO に empire_id を含めない §確定 H） |

## ユニットテストケース

**該当なし（DB 経由の物理確認に集約）** — 理由:

- agent-repo / workflow-repo と同方針: Repository 層は SQLite + Alembic + MaskingGateway の実 I/O が責務の本質、純粋ロジックの単体テストは値が薄い
- `_to_row` / `_from_row` のラウンドトリップは TC-UT-RR-014-roundtrip で integration として物理確認
- domain layer のラウンドトリップ等は room feature #22 で完了済み（本 PR スコープ外）

## カバレッジ基準

- REQ-RR-001〜006 すべてに最低 1 件のテストケース（REQ-RR-006 はコードレビューで確認）
- **room §確定 G 実適用 7 経路**（anthropic / github / openai / bearer / no-secret / roundtrip / multiple）すべてに正常系ケース、TC-IT-RR-008-masking-* で物理確認
- **find_by_name Empire スコープ強制（§確定 F、IDOR 防御）**: TC-UT-RR-005 で 3 経路（ヒット / 不在 / 異 Empire 同 name）すべて + SQL ログで `WHERE empire_id=?` + `LIMIT 1` 物理確認
- **count_by_empire（§確定 G）**: TC-UT-RR-006 で SQL `COUNT(*) WHERE empire_id=?` の物理確認
- **`(room_id, agent_id, role)` UNIQUE 二重防衛（§確定 R1-D）**: TC-IT-RR-009 で直接 INSERT 経路で IntegrityError
- **`workflow_id` FK ON DELETE RESTRICT（§確定 R1-B）**: TC-IT-RR-010 で Workflow 削除拒否を物理確認
- **BUG-EMR-001 Stage 2 closure（§確定 R1-C）**: TC-IT-RR-011 で `empire_room_refs.room_id` FK が `op.batch_alter_table` 経由で追加されたことを `PRAGMA foreign_key_list` で物理確認
- **`save(room, empire_id)` signature（§確定 H）**: TC-UT-RR-007 で empire_id 引数経由保存 + Room VO に empire_id 属性不在を確認
- **CI 三層防衛 partial-mask 拡張（§確定 E）**: Layer 1 grep（CI ジョブ）+ Layer 2 arch（TC-UT-RR-013-arch）+ Layer 3 storage.md（TC-DOC-RR-001）3 つすべてに証拠
- empire-repo / workflow-repo / agent-repo §確定 A〜F + §BUG-EMR-001 規約の継承を TC-UT-RR-001〜007 全件で確認
- 受入基準 1〜11 すべてに unit/integration ケース（12〜14 は Migration/DB 物理確認、15〜16 は CI/コードレビュー、17〜18 は CI ジョブ）
- 確定 A〜H すべてに証拠ケース
- C0 目標: `infrastructure/persistence/sqlite/repositories/room_repository.py` で **90% 以上**

## 人間が動作確認できるタイミング

本 feature は infrastructure 層単独だが、**M2 永続化基盤と同じく Backend プロセスを実起動して動作確認できる**。

- CI 統合後: `gh pr checks` で 7 ジョブ緑（lint / typecheck / test-backend / audit / fmt / commit-msg / no-ai-footer）
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/infrastructure/persistence/sqlite/repositories/test_room_repository tests/infrastructure/persistence/sqlite/test_alembic_room.py tests/architecture/test_masking_columns.py tests/docs/test_storage_md_back_index.py -v` → 全テスト緑
- Backend 実起動: `cd backend && uv run python -m bakufu`（環境変数 `BAKUFU_DATA_DIR=/tmp/bakufu-test` を設定）
  - 起動時に Alembic auto-migrate で 0001〜0005 が適用されることをログで目視
  - `sqlite3 <DATA_DIR>/bakufu.db ".tables"` で `rooms` / `room_members` の 2 テーブル + `empire_room_refs` の FK 含む状態を目視
  - `sqlite3 <DATA_DIR>/bakufu.db "PRAGMA foreign_key_list(empire_room_refs)"` で BUG-EMR-001 closure FK が含まれることを目視
- masking 物理確認: `uv run pytest tests/.../test_masking_prompt_kit.py -v` → 7 ケース緑、raw token が DB に残らないことを目視
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.application.ports.room_repository --cov=bakufu.infrastructure.persistence.sqlite.repositories.room_repository --cov-report=term-missing` → 90% 以上

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      room.py                                  # 既存（room feature #22）+ make_room_with_secret_prompt_kit 追加
    architecture/
      test_masking_columns.py                  # 既存 + Room partial-mask parametrize 拡張（_MASKING_CONTRACT / _NO_MASK_TABLES / _PARTIAL_MASK_TABLES）
                                               # TC-UT-RR-013-arch
    infrastructure/
      persistence/
        sqlite/
          repositories/
            test_room_repository/              # 新規ディレクトリ（4 ファイル分割、最初から）
              __init__.py
              conftest.py                       # seed_empire helper（agent-repo パターン継承、FK CASCADE 解決用）
              test_protocol_crud.py            # TC-UT-RR-001 / 004 / 005 / 006 / 007 + TC-IT-RR-LIFECYCLE
              test_save_semantics.py           # TC-UT-RR-002 / 003 / 014-roundtrip + Tx 境界
              test_constraints_arch.py         # TC-IT-RR-009 / 010 / 011 / 013-arch + Alembic 0005 補強
              test_masking_prompt_kit.py       # TC-IT-RR-008-masking-* (7 ケース、room §確定 G 実適用核心)
          test_alembic_room.py                 # TC-IT-RR-012（Alembic 0005 chain 0001→...→0005 + BUG-EMR-001 closure）
    docs/
      test_storage_md_back_index.py            # 既存 + Room 行検証（TC-DOC-RR-001）
```

**配置の根拠**:
- empire / workflow / agent テンプレ 100% 継承
- `test_masking_prompt_kit.py` を独立ファイルにするのは **room §確定 G 実適用が本 PR の核心**であり、agent-repo `test_masking_persona.py` の partial-mask masking テストパターンを再利用するため
- `test_alembic_room.py` は agent / workflow の `test_alembic_*.py` 同パターン + **BUG-EMR-001 Stage 2 closure 物理確認**を担う
- `conftest.py` の `seed_empire` helper は agent-repo PR #45 で確立した FK CASCADE 解決パターンを継承

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| Room 後続申し送り #1 | masked `prompt_kit_prefix_markdown` の LLM Adapter 配送経路（room §確定 G 不可逆性）| `feature/llm-adapter`（後続） | 「`<REDACTED:*>` を含む PromptKit は配送停止 + ログ警告」契約を凍結する責務（agent-repo 申し送り #1 と同パターン）|
| Room 後続申し送り #2 | Room.empire_id 属性不在の application 層補強 | `feature/room-application`（後続） | save(room, empire_id) の empire_id を呼出元 service が決定する経路を `RoomService.create()` で凍結（§確定 H 連携先）|

**Schneier 申し送り（前 PR から継承 + 本 PR 固有）**:

- **room §確定 G 実適用**: agent-repo `Persona.prompt_body` パターン継承、persistence-foundation #23 で hook 構造提供 → 本 PR で配線完了
- **BUG-EMR-001 Stage 2 closure**: empire-repo PR #29 で起票、本 PR で `op.batch_alter_table` 経由 FK 追加で物理 close。empire-repository detailed-design.md §Known Issues §BUG-EMR-001 に **RESOLVED** marker を同 PR で同期更新（ダリオ作業済み）
- **`workflow_id` FK RESTRICT**: Workflow は Room の参照先であり owner ではない（Empire が owner）。CASCADE は Workflow 削除で大量 Room 消失のリスクがあるため RESTRICT を採用（§確定 R1-B）。後続 application 層 `WorkflowService.delete()` で「Room 存在時の削除拒否 → CEO に Room の archive を促すフロー」を実装する申し送り
- **`(room_id, agent_id, role)` UNIQUE 二重防衛**: agent-repo `is_default` partial unique index と異なり、Room の member は **全件 UNIQUE 対象**（partial 性質なし）。`__table_args__` で UNIQUE 明示、Aggregate `_validate_member_unique` と DB 物理拒否の二重防衛（§確定 R1-D）

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-RR-001〜005 すべてに 1 件以上のテストケースがあり、特に integration が Repository 契約 + Alembic + masking 配線 + CI 三層防衛を単独でカバーしている
- [ ] **room §確定 G 実適用 7 経路** すべてに TC-IT-RR-008-masking-* で物理確認、raw token が DB に残らないことを assert
- [ ] **find_by_name Empire スコープ強制（§確定 F、IDOR 防御）** が TC-UT-RR-005 で 3 経路（ヒット / 不在 / 異 Empire 同 name）+ SQL ログ `WHERE empire_id=?` + `LIMIT 1` で物理確認
- [ ] **count_by_empire（§確定 G）** が TC-UT-RR-006 で SQL `COUNT(*) WHERE empire_id=?` の物理確認
- [ ] **`(room_id, agent_id, role)` UNIQUE 二重防衛（§確定 R1-D）** が TC-IT-RR-009 で物理確認（直 INSERT 経路で IntegrityError）
- [ ] **`workflow_id` FK ON DELETE RESTRICT（§確定 R1-B）** が TC-IT-RR-010 で物理確認（Room 存在時の Workflow 削除拒否）
- [ ] **BUG-EMR-001 Stage 2 closure（§確定 R1-C）** が TC-IT-RR-011 で物理確認（`PRAGMA foreign_key_list(empire_room_refs)` で `room_id → rooms.id` FK 確認 + 存在しない room_id INSERT で IntegrityError）
- [ ] **`save(room, empire_id)` signature（§確定 H）** が TC-UT-RR-007 で物理確認（empire_id 引数経由保存 + Room VO に empire_id 属性不在）
- [ ] **CI 三層防衛 partial-mask 拡張（§確定 E）**: Layer 1 grep（CI）+ Layer 2 arch（TC-UT-RR-013-arch）+ Layer 3 storage.md（TC-DOC-RR-001）の 3 つすべてに証拠
- [ ] **Alembic chain 一直線**: TC-IT-RR-012 で head 分岐なし、`0005.down_revision == "0004_agent_aggregate"` を物理確認
- [ ] **upgrade/downgrade idempotent**: TC-IT-RR-012 で双方向 migration を物理確認
- [ ] 確定 A〜H すべてに証拠ケース
- [ ] empire-repo / workflow-repo / agent-repo テンプレート継承（§確定 A〜F + §BUG-EMR-001）が崩れていない
- [ ] **テストファイル分割（4 ファイル）が basic-design.md §モジュール構成と整合**（empire-repo PR #29 / agent-repo PR #45 教訓を最初から反映）
- [ ] room §確定 G 実適用クローズが PR 本文に明示されている
- [ ] BUG-EMR-001 Stage 2 RESOLVED が empire-repository detailed-design.md §Known Issues に同期されている
