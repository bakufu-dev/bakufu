# テスト設計書

<!-- feature: empire-repository -->
<!-- 配置先: docs/features/empire-repository/test-design.md -->
<!-- 対象範囲: REQ-EMR-001〜005 / 受入基準 1〜14 / 詳細設計 確定 A〜F / Repository ポート + delete-then-insert + domain↔row 変換 + シングルトン強制責務分離 + CI 三層防衛 + テンプレート責務 -->

本 feature は M2 Repository **最初の Aggregate Repository PR**であり、後続 6 件（workflow / agent / room / directive / task / external-review-gate）の**実装パターンを test 層でも凍結する**責務を持つ。テストの主役は **integration**（実 SQLite + 実 Alembic + 実 SQLAlchemy AsyncSession）であり、unit は domain ↔ row 変換 / Protocol 充足チェックなど契約周辺に絞る。

戦略ガイド §結合テスト方針「DB は実接続」「外部 API のみモック」に従い、本 feature のテストは:

- **integration test 主導**: Alembic 2nd revision 適用 → AsyncSession で `find_by_id` / `count` / `save` の 3 メソッド契約検証（`tmp_path` で実 SQLite ファイル）
- **CI 三層防衛の物理保証**: Layer 1（grep guard）+ Layer 2（arch test）の両方を本 PR で同時起票し、後続 Repository PR の masking 対象漏れを構造で塞ぐ
- **assumed mock 禁止規約**: `mock.return_value` インライン辞書は禁止、Empire / RoomRef / AgentRef は既存 `tests/factories/empire.py`（empire feature #8 で確立）から取得

外部 I/O は SQLite + ファイルシステム + Alembic が本物。masking gateway（M2 永続化基盤の Layer 1〜3）は Empire スコープでは「対象なし」だが、グローバル init は実行されるため実 init 経路で動作確認する。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-EMR-001 | `EmpireRepository(Protocol)` 定義 | TC-IT-EMR-001 | 結合 | 正常系 | 1 |
| REQ-EMR-001 | Protocol 充足（pyright 型レベル + isinstance 風 duck typing） | TC-IT-EMR-010 | 結合 | 正常系 | 2 |
| REQ-EMR-002 | `find_by_id(empire_id)` 既存 Empire 取得 | TC-IT-EMR-002 | 結合 | 正常系 | 3 |
| REQ-EMR-002 | `find_by_id(unknown_id)` で None | TC-IT-EMR-003 | 結合 | 異常系 | 4 |
| REQ-EMR-002 | `count()` 0 件 / 1 件 | TC-IT-EMR-004 | 結合 | 正常系 | 5 |
| REQ-EMR-002 | `save(empire)` 新規挿入（3 テーブルに行が入る） | TC-IT-EMR-005 | 結合 | 正常系 | 6 |
| REQ-EMR-002 | `save(empire)` 既存更新（delete-then-insert で rooms / agents 反映、確定 B） | TC-IT-EMR-006 | 結合 | 正常系 | 7 |
| REQ-EMR-002（ラウンドトリップ） | `save(empire)` → `find_by_id(empire.id)` の構造的等価 | TC-IT-EMR-007 | 結合 | 正常系 | 8 |
| REQ-EMR-002（delete-then-insert 5 段階） | save 内で empires UPSERT → empire_room_refs DELETE → INSERT → empire_agent_refs DELETE → INSERT の順序検証 | TC-IT-EMR-011 | 結合 | 正常系 | 7（確定 B） |
| REQ-EMR-002（Tx 境界） | service 側で `async with session.begin()` を持つ正常 commit / 例外時 rollback で Empire 永続化が原子的 | TC-IT-EMR-012 | 結合 | 正常系/異常系 | （確定 B Tx 境界） |
| REQ-EMR-002（FK CASCADE） | `DELETE FROM empires WHERE id=...` で empire_room_refs / empire_agent_refs が CASCADE 削除される | TC-IT-EMR-013 | 結合 | 正常系 | （データモデル制約） |
| REQ-EMR-002（UNIQUE 制約） | `(empire_id, room_id)` / `(empire_id, agent_id)` の重複 INSERT で `IntegrityError` | TC-IT-EMR-014 | 結合 | 異常系 | （データモデル制約） |
| REQ-EMR-002（domain↔row 変換、確定 C） | `_to_row(empire)` が tuple[dict, list, list] を返す | TC-UT-EMR-001 | ユニット | 正常系 | （確定 C） |
| REQ-EMR-002（domain↔row 変換、確定 C） | `_from_row(empire_row, room_refs, agent_refs)` が valid Empire を構築 | TC-UT-EMR-002 | ユニット | 正常系 | （確定 C） |
| REQ-EMR-002（domain↔row 双方向） | `_from_row(_to_row(e)) == e` の構造的等価 | TC-UT-EMR-003 | ユニット | 正常系 | 8（確定 C） |
| REQ-EMR-003 | Alembic 2nd revision で 3 テーブル + INDEX が追加される | TC-IT-EMR-008 | 結合 | 正常系 | 9 |
| REQ-EMR-003 | `alembic upgrade head` → `downgrade base` 双方が緑（idempotent） | TC-IT-EMR-015 | 結合 | 正常系 | 9 |
| REQ-EMR-003（chain 完整性） | revision 0001 → 0002 の down_revision が一直線（CI 検査で head 分岐なし） | TC-IT-EMR-016 | 結合 | 正常系 | 9（確定 F） |
| REQ-EMR-004（Layer 1 grep） | `scripts/ci/check_masking_columns.sh` で Empire 3 テーブルが「masking 対象なし」を pass | TC-CI-EMR-001 | CI script | 正常系 | 10 |
| REQ-EMR-004（Layer 2 arch） | `tests/architecture/test_masking_columns.py` で Empire 3 テーブルの全カラムが MaskedJSONEncoded / MaskedText でないことを assert | TC-IT-EMR-009 | 結合 | 正常系 | 11 |
| REQ-EMR-004（後続 PR テンプレート） | 「対象なし」を明示登録できる構造で Layer 1 / 2 が parametrize されている | TC-IT-EMR-017 | 結合 | 正常系 | 11（確定 E / F） |
| REQ-EMR-005（storage.md 逆引き表） | §逆引き表に「Empire 関連カラム: masking 対象なし」行が存在 | TC-DOC-EMR-001 | doc 検証 | 正常系 | （確定 E Layer 3） |
| 確定 D（シングルトン責務分離） | `count()` 単体で 0 / 1 / 2+ を返すのみ、Aggregate 内 / Repository 内でシングルトン強制しない | TC-IT-EMR-018 | 結合 | 正常系 | （責務境界） |
| 確定 F（テンプレート責務） | チェックリスト 11 項目（A〜E）を本 PR が満たすことを test-design.md で凍結 | （本マトリクス全体） | — | — | 11 項目 |
| AC-12（依存方向） | `domain` 層から `application` / `infrastructure` への import がゼロ件 | （既存 CI script） | — | — | 12 |
| AC-13（lint/typecheck） | `pyright --strict` / `ruff check` | （CI ジョブ） | — | — | 13 |
| AC-14（カバレッジ） | `pytest --cov=bakufu.application.ports.empire_repository --cov=bakufu.infrastructure.persistence.sqlite.repositories.empire_repository` で 90% 以上 | （CI ジョブ） | — | — | 14 |

**マトリクス充足の証拠**:

- REQ-EMR-001〜005 すべてに最低 1 件のテストケース
- **delete-then-insert 5 段階順序（確定 B）**: TC-IT-EMR-011 で実 SQLite に対し UPSERT → DELETE → INSERT の順序を物理確認（`sqlalchemy.event.listen(engine, "after_cursor_execute", ...)` で SQL 発行順を観測する経路）
- **domain↔row ラウンドトリップ（確定 C）**: TC-UT-EMR-003（unit 純粋ロジック）+ TC-IT-EMR-007（実 DB 経由）の 2 経路で構造的等価を物理確認
- **Aggregate 集合知識の責務分離（確定 D）**: TC-IT-EMR-018 で「Repository 自身はシングルトン強制しない、`count()` は事実報告のみ」を物理確認
- **CI 三層防衛の物理保証（確定 E）**: Layer 1 grep（TC-CI-EMR-001）+ Layer 2 arch test（TC-IT-EMR-009）+ Layer 3 storage.md（TC-DOC-EMR-001）の 3 つすべてで Empire テーブル群が「masking 対象なし」を凍結。後続 Repository PR が誤って `MaskedText` 指定 → CI で arch test 落下、PR ブロック
- **テンプレート責務（確定 F）**: 後続 6 件 Repository PR が確定 A〜E を直接参照して実装する旨を test-design.md レビュー観点で凍結
- **Tx 境界の正常系/異常系（確定 B）**: TC-IT-EMR-012 で `async with session.begin()` の commit / rollback 両経路を物理確認、Repository が明示的 commit / rollback しないことを assert
- **DB 制約**: FK CASCADE（TC-IT-EMR-013）+ UNIQUE 制約（TC-IT-EMR-014）で Alembic 2nd revision の DDL が正しいことを物理確認
- 受入基準 1〜11 すべてに unit/integration ケース（12〜14 は CI ジョブ）
- 確定 A（Protocol 配置）/ B（delete-then-insert + Tx 境界）/ C（domain↔row 変換）/ D（シングルトン責務分離）/ E（CI 三層防衛）/ F（テンプレート責務）すべてに証拠ケース
- 孤児要件ゼロ

## 外部 I/O 依存マップ

本 feature は infrastructure 層の Repository 実装であり、本物の SQLite + 本物の Alembic + 本物の SQLAlchemy AsyncSession を使う（M2 永続化基盤と同方針）。

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **SQLite (sqlite+aiosqlite)** | engine / session / 3 テーブル / Alembic migration | 不要（実 DB を `tmp_path` 配下の bakufu.db で起動、テストごとに使い捨て） | 不要（DB は本物） | **済（本物使用、persistence-foundation conftest.py の app_engine / session_factory fixture を再利用）** |
| **ファイルシステム** | `BAKUFU_DATA_DIR` / `bakufu.db` / WAL/SHM | 不要（`pytest.tmp_path`） | 不要（FS は本物） | **済（本物使用）** |
| **Alembic** | 2nd revision の `upgrade head` / `downgrade base` | 不要（本物の `alembic upgrade` を実 SQLite に対し実行） | 不要 | **済（本物使用、persistence-foundation の `run_upgrade_head` を再利用）** |
| **SQLAlchemy 2.x AsyncSession** | UoW 境界 / Repository メソッド経由の SQL 発行 | 不要 | 不要 | **済（本物使用）** |
| **環境変数** | `BAKUFU_DATA_DIR` / `BAKUFU_DB_PATH` | 不要 | 不要 | **済（`monkeypatch.setenv` で test 用 tmp_path）** |

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `EmpireFactory`（既存、empire feature #8 由来） | `Empire`（valid デフォルト = name="bakufu-empire"、rooms=[], agents=[]） | `True` |
| `PopulatedEmpireFactory`（新規） | `Empire`（rooms 2 件 + agents 3 件、ラウンドトリップ test 用） | `True` |
| `RoomRefFactory`（既存） | `RoomRef` | `True` |
| `AgentRefFactory`（既存） | `AgentRef` | `True` |

`tests/factories/empire.py` は empire feature #8 で確立済み、本 PR では `PopulatedEmpireFactory` を 1 件追加するのみ（rooms / agents 含む Empire の実 DB ラウンドトリップ test 用）。

**raw fixture / characterization は不要**: SQLite + SQLAlchemy + Alembic の挙動は標準ライブラリ仕様で固定、外部観測（実 DB ファイル）が真実源として常時使える。M2 永続化基盤と同じ判断。

## E2E テストケース

**該当なし** — 理由:

- 本 feature は infrastructure 層単独で、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない（[`basic-design.md §モジュール契約`](basic-design.md) §画面・CLI 仕様 / §API 仕様 で「該当なし」と凍結）
- Repository は内部 API（Python module-level の Protocol / Class）のみ提供
- 戦略ガイド §E2E対象の判断「内部 API・ライブラリなどエンドユーザー操作がない場合は結合テストで代替可」に従い、E2E は本 feature 範囲外
- 後続 `feature/admin-cli`（`bakufu admin empire show` 等）/ `feature/http-api`（Empire CRUD）が公開 I/F を実装した時点で E2E を起票
- 受入基準 1〜11 はすべて unit/integration テストで検証可能（12〜14 は CI ジョブ）

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — infrastructure 層のため公開 I/F なし | — | — |

## 結合テストケース

**「Repository 契約 + 実 SQLite + 実 Alembic」を contract testing する**層。M2 永続化基盤の `app_engine` / `session_factory` fixture を再利用。

### Protocol 定義 + 充足（受入基準 1, 2、確定 A）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-EMR-001 | `EmpireRepository(Protocol)` 定義 | — | `application/ports/empire_repository.py` がインポート可能 | `from bakufu.application.ports.empire_repository import EmpireRepository` | Protocol が `find_by_id` / `count` / `save` の 3 メソッドを宣言、すべて `async def`。`@runtime_checkable` なし（duck typing） |
| TC-IT-EMR-010 | `SqliteEmpireRepository` の Protocol 充足 | `app_engine` + `session_factory` | engine + Alembic 適用済み | `repo: EmpireRepository = SqliteEmpireRepository(session)` で型代入が pyright で通る | pyright strict pass。さらに duck typing で `hasattr(repo, 'find_by_id') and hasattr(repo, 'count') and hasattr(repo, 'save')` 全 True |

### 基本 CRUD（受入基準 3〜8、確定 B / C）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-EMR-002 | `find_by_id(existing_empire_id)` | `session_factory` + `EmpireFactory` | `save(empire)` で 1 件保存済み | 同 session_factory で別 session を開き `find_by_id(empire.id)` | 保存した Empire と構造的等価な Empire を返す（`==` True、frozen 構造体）。rooms / agents 件数も一致 |
| TC-IT-EMR-003 | `find_by_id(unknown_id)` | `session_factory` | DB 空 | `find_by_id(uuid4())` を呼ぶ | `None` を返す。例外を raise しない |
| TC-IT-EMR-004 | `count()` 0 → 1 遷移 | `session_factory` + `EmpireFactory` | DB 空 | (1) `count()` → 0 を確認、(2) `save(empire)` 後に `count()` → 1 を確認 | 遷移が正しく観測される（contract: シングルトン強制は application 層、本 PR は事実報告のみ） |
| TC-IT-EMR-005 | `save(empire)` 新規挿入で 3 テーブルに行が入る | `session_factory` + `PopulatedEmpireFactory` | rooms 2 件 + agents 3 件の Empire | `save(empire)` 後、別 session で 3 テーブル直接 SELECT | `empires` 1 行（id, name）+ `empire_room_refs` 2 行 + `empire_agent_refs` 3 行が存在、各カラムが Empire VO の値と一致 |
| TC-IT-EMR-006 | `save(empire)` 既存更新（rooms / agents 変更） | `session_factory` | 1 度 save 済みの Empire（rooms 2 件 + agents 3 件） | (1) Empire を `add_room` / `archive_room` / `add_agent` で更新（empire feature #8 のふるまい）、(2) 再度 `save(updated_empire)` を呼ぶ | empire_room_refs / empire_agent_refs が **delete-then-insert** で全置換される（確定 B 戦略）。古い RoomRef / AgentRef は残らず、新 VO が SELECT で取得される |
| TC-IT-EMR-007 | ラウンドトリップ（save → find_by_id 構造的等価） | `session_factory` + `PopulatedEmpireFactory` | 任意の valid Empire | (1) `save(empire)`、(2) 別 session で `find_by_id(empire.id)`、(3) 復元 Empire == 元 Empire | 構造的等価が成立。RoomRef / AgentRef の順序は domain 層で sort されるため一致（empire feature §確定 で凍結済み） |

### delete-then-insert 5 段階順序（確定 B、受入基準 7）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-EMR-011 | `save()` 内 SQL 発行順序 | `session_factory` + `PopulatedEmpireFactory` + `sqlalchemy.event.listen(engine, "after_cursor_execute", ...)` で SQL ログ収集 | 1 度 save 済み Empire を更新 | 再 save 時の SQL 文を順序で観測 | 順序が確定 B 通り: (1) UPSERT empires、(2) DELETE empire_room_refs WHERE empire_id=?、(3) bulk INSERT empire_room_refs、(4) DELETE empire_agent_refs WHERE empire_id=?、(5) bulk INSERT empire_agent_refs |

### Tx 境界の責務分離（確定 B）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-EMR-012 | service 層 `async with session.begin()` 配下の commit / rollback | `session_factory` | service スタブ（`async def save_empire(repo, empire)`） | (1) **正常系**: `async with session.begin(): await repo.save(empire)` → ブロック退出で commit、別 session で SELECT すると行が取得可能。(2) **異常系**: `async with session.begin(): await repo.save(empire); raise RuntimeError` → ブロック退出で rollback、別 session で SELECT すると行が取得不可 | commit 経路で Empire が永続化、rollback 経路で原子的に消える。Repository は `await session.commit()` / `session.rollback()` を呼ばない（責務境界、確定 B） |

### FK CASCADE + UNIQUE 制約（データモデル契約、受入基準 9 補強）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-EMR-013 | `empires` DELETE → 子テーブル CASCADE | `session_factory` + `PopulatedEmpireFactory` | save 済み Empire | raw SQL で `DELETE FROM empires WHERE id=:id` を実行 | empire_room_refs / empire_agent_refs の対応行が CASCADE で削除される（FK ON DELETE CASCADE 制約の物理確認） |
| TC-IT-EMR-014 | UNIQUE(empire_id, room_id) 違反 | `session_factory` | save 済み Empire | raw SQL で同じ `(empire_id, room_id)` ペアを 2 度 INSERT | `IntegrityError`（または UniqueViolation）が raise。同様に `(empire_id, agent_id)` も検証 |

### Alembic 2nd revision（受入基準 9、確定 F）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-EMR-008 | Alembic 2nd revision 適用 | `tmp_path` 配下の bakufu.db | M1 + M2 永続化基盤の initial revision 適用済み | `alembic upgrade head` を実行 | (a) `0001_init` から `0002_empire_aggregate` への進行、(b) `SELECT name FROM sqlite_master WHERE type='table'` で `empires` / `empire_room_refs` / `empire_agent_refs` の 3 テーブルが追加、(c) UNIQUE INDEX `(empire_id, room_id)` / `(empire_id, agent_id)` が存在 |
| TC-IT-EMR-015 | upgrade / downgrade 双方向 | `tmp_path` | initial revision 適用済み | (1) `alembic upgrade head`、(2) `alembic downgrade base`、(3) 再 `alembic upgrade head` | (1) で 3 テーブル追加、(2) で 3 テーブル削除（initial revision テーブルは残る）、(3) で再追加。idempotent な migration |
| TC-IT-EMR-016 | revision chain 一直線 | Alembic config | versions/0001_init.py + versions/0002_empire_aggregate.py | `alembic heads` を実行 | head は単一（`0002_empire_aggregate`）、`0001_init` の down_revision is None、`0002_empire_aggregate.down_revision == "0001_init"` で chain が一直線。head 分岐がないことを物理確認（確定 F の後続 PR テンプレート要件） |

### CI 三層防衛（受入基準 10, 11、確定 E）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-CI-EMR-001 | Layer 1: `scripts/ci/check_masking_columns.sh` の Empire 拡張 | repo root | スクリプトが Empire 3 テーブルを明示登録 | `bash scripts/ci/check_masking_columns.sh` を実行 | exit 0。grep guard が Empire 3 テーブル定義ファイル（`tables/empires.py` 等）に `MaskedJSONEncoded` / `MaskedText` が登場しないことを確認、登場すると exit 非 0 |
| TC-IT-EMR-009 | Layer 2: `tests/architecture/test_masking_columns.py` の Empire parametrize | `Base.metadata` | M2 永続化基盤の arch test が parametrize 形式 | parametrize に `empires` / `empire_room_refs` / `empire_agent_refs` を追加し、各カラムの `column.type.__class__` が `MaskedJSONEncoded` でも `MaskedText` でもないことを assert | 全 3 テーブルで pass。後続 PR が誤って `MaskedText` を Empire に追加した瞬間、この test が落下して PR ブロック |
| TC-IT-EMR-017 | 「対象なし」明示登録の構造（後続 PR テンプレート） | parametrize リスト | Layer 1 / 2 の登録形式が「(table_name, expected_masked_columns: set)」のタプル | empires に `expected_masked_columns=set()` で登録、test 内で `actual_masked_columns == expected_masked_columns` を assert | 「空集合 = 対象なし」の明示登録経路が動作。後続 Repository PR が「対象あり」を `expected_masked_columns={'prompt_body'}` のように登録できる構造であることを物理確認 |

### storage.md 逆引き表（確定 E Layer 3）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-DOC-EMR-001 | storage.md §逆引き表に Empire 行存在 | repo root | `docs/design/domain-model/storage.md` 編集済み | `grep -E '^\| Empire' docs/design/domain-model/storage.md` を実行 | 「Empire 関連カラム: masking 対象なし」を示す行がヒット（後続 Repository PR が同様の行を追加するテンプレート） |

### シングルトン強制責務分離（確定 D）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-EMR-018 | Repository は `count()` で事実報告のみ、シングルトン強制しない | `session_factory` | DB 空 | (1) 1 件目 `save(empire_a)`、(2) **同じ id でない別 Empire** `save(empire_b)` を続けて呼ぶ、(3) `count()` を確認 | (a) 2 件目 save が **例外を raise せず**正常に通る（Repository はシングルトン強制を持たない）、(b) `count()` が 2 を返す。Aggregate 集合知識（シングルトン制約）は `EmpireService.create()` 責務であり、本 PR スコープ外（確定 D） |

## ユニットテストケース

`tests/factories/empire.py` の factory 経由で domain 層 Empire を生成する。Repository クラス内 private method (`_to_row` / `_from_row`) は純粋ロジック（dict 変換）なので unit でテスト可能、DB アクセスは伴わない。

### domain↔row 変換（確定 C、受入基準 8 補強）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-EMR-001 | `SqliteEmpireRepository._to_row(empire)` | 正常系 | `PopulatedEmpireFactory()` で生成した Empire（rooms 2 件 + agents 3 件） | (a) 戻り値が `tuple[dict, list[dict], list[dict]]`、(b) `empires_row == {'id': str, 'name': str}`、(c) `room_refs` が rooms 2 件分の dict、(d) `agent_refs` が agents 3 件分の dict、(e) Empire VO の各属性値が dict に正しく転写されている |
| TC-UT-EMR-002 | `SqliteEmpireRepository._from_row(empire_row, room_refs, agent_refs)` | 正常系 | dict / list[dict] の 3 引数（factory で組み立て） | 戻り値が valid な Empire、`Empire.model_validator(mode='after')` を経由して構築。RoomRef / AgentRef も VO として復元 |
| TC-UT-EMR-003 | `_from_row(_to_row(empire))` ラウンドトリップ | 正常系 | `PopulatedEmpireFactory()` | 復元 Empire == 元 Empire（構造的等価、frozen + `==` True）。empire feature #8 で凍結された RoomRef / AgentRef の sort 規約に従い順序も一致 |

### Protocol 充足の型レベル検証（確定 A、受入基準 2 補強）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| （TC-IT-EMR-010 で実施） | `SqliteEmpireRepository: EmpireRepository = SqliteEmpireRepository(session)` の型代入 | 正常系 | — | pyright strict pass。`@runtime_checkable` なしのため isinstance 検査は使わない |

## カバレッジ基準

- REQ-EMR-001 〜 005 の各要件が**最低 1 件**のテストケースで検証されている（マトリクス参照）
- **delete-then-insert 5 段階順序（確定 B）**: TC-IT-EMR-011 で実 SQL ログ観測、UPSERT → DELETE → INSERT × 2 の順序を物理確認
- **Tx 境界の責務分離（確定 B）**: TC-IT-EMR-012 で commit / rollback 両経路、Repository が明示的 commit / rollback しないことを assert
- **domain↔row 変換ラウンドトリップ（確定 C）**: TC-UT-EMR-003（unit 純粋）+ TC-IT-EMR-007（実 DB 経由）の 2 経路で構造的等価を物理確認
- **シングルトン責務分離（確定 D）**: TC-IT-EMR-018 で「Repository 自身はシングルトン強制しない」物理確認
- **CI 三層防衛（確定 E）**: Layer 1 grep（TC-CI-EMR-001）+ Layer 2 arch test（TC-IT-EMR-009）+ Layer 3 storage.md（TC-DOC-EMR-001）3 つすべて起票
- **テンプレート責務（確定 F）**: 後続 6 件 Repository PR が確定 A〜E を直接参照することを test-design.md レビュー観点で凍結
- **DB 制約**: FK CASCADE（TC-IT-EMR-013）+ UNIQUE 制約（TC-IT-EMR-014）+ Alembic chain（TC-IT-EMR-016）で migration の正しさを物理確認
- **upgrade/downgrade idempotent**: TC-IT-EMR-015 で双方向 migration を物理確認
- 受入基準 1 〜 11 の各々が**最低 1 件のユニット/結合ケース**で検証されている（E2E 不在のため戦略ガイドの「結合代替可」に従う）
- 受入基準 12（依存方向）/ 13（pyright/ruff）/ 14（カバレッジ 90%）は CI ジョブで担保
- 確定 A〜F すべてに証拠ケース
- C0 目標: `application/ports/empire_repository.py` / `infrastructure/persistence/sqlite/repositories/empire_repository.py` で **90% 以上**（infrastructure 層基準、要件分析書 §非機能要求準拠）

## 人間が動作確認できるタイミング

本 feature は infrastructure 層単独だが、**M2 永続化基盤と同じく Backend プロセスを実起動して動作確認できる**。

- CI 統合後: `gh pr checks` で 7 ジョブ緑（lint / typecheck / test-backend / audit / fmt / commit-msg / no-ai-footer）
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/infrastructure/persistence/sqlite/repositories/test_empire_repository.py tests/architecture/test_masking_columns.py -v` → 全テスト緑
- Backend 実起動: `cd backend && uv run python -m bakufu`（環境変数 `BAKUFU_DATA_DIR=/tmp/bakufu-test` を設定）
  - 起動時に Alembic auto-migrate で 0001_init + 0002_empire_aggregate が適用されることをログで目視
  - `sqlite3 <DATA_DIR>/bakufu.db ".tables"` で `empires` / `empire_room_refs` / `empire_agent_refs` の 3 テーブルが見えることを目視
  - `sqlite3 <DATA_DIR>/bakufu.db "SELECT * FROM sqlite_master WHERE type='index'"` で UNIQUE INDEX が見えることを目視
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.application.ports.empire_repository --cov=bakufu.infrastructure.persistence.sqlite.repositories.empire_repository --cov-report=term-missing` → 90% 以上
- CI 三層防衛の実観測: `bash scripts/ci/check_masking_columns.sh` を手動実行 → exit 0 + Empire 3 テーブルが「対象なし」で pass する出力を目視
- masking 対象漏れ test の挙動確認: 一時的に `tables/empires.py` の `name` カラムを `String(80)` から `MaskedText` に変えてみる → arch test が落ちることを目視（修正後元に戻す。後続 Repository PR の漏れ防止が物理層で機能していることの実観測）

後段で `feature/empire-application`（`EmpireService.create() / get()` 等）/ `feature/admin-cli`（`bakufu admin empire show`）/ `feature/http-api`（Empire CRUD）が完成したら、本 feature の Repository を経由して `curl` 経由の手動シナリオで E2E 観測可能になる。

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      __init__.py
      empire.py                            # 既存（empire feature #8）+ PopulatedEmpireFactory 追加
    architecture/
      test_masking_columns.py              # 既存（M2 永続化基盤）+ Empire 3 テーブル parametrize 追加
                                           # TC-IT-EMR-009 / 017
    infrastructure/
      persistence/
        sqlite/
          repositories/
            __init__.py
            test_empire_repository.py      # TC-IT-EMR-001〜007 / 010〜018, TC-UT-EMR-001〜003
          test_alembic_empire.py           # TC-IT-EMR-008 / 015 / 016（Alembic 2nd revision 検証）
    docs/
      test_storage_md_back_index.py        # TC-DOC-EMR-001（storage.md 逆引き表検証、grep ベース）
```

**配置の根拠**:
- 戦略ガイド §テストディレクトリ構造 の Python 標準慣習に従う
- `repositories/` サブディレクトリを新設（後続 6 件 Repository PR が同様に追加）
- `architecture/test_masking_columns.py` は M2 永続化基盤で既に新設済み、本 PR は parametrize に Empire 3 テーブル追加のみ
- `test_alembic_empire.py` を独立ファイルにするのは Alembic 2nd revision の chain / upgrade / downgrade を 1 ファイルに集約し、後続 PR が `test_alembic_workflow.py` 等で同パターンを踏襲しやすくするため
- `docs/test_storage_md_back_index.py` は storage.md §逆引き表が「11 行 + Empire 行追加」で構造的に検証可能であることを保証（後続 Repository PR が新行を追加した時の自動検証経路）

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| （N/A） | 該当なし — SQLite + Alembic + SQLAlchemy は標準ライブラリ仕様で固定 | — | 後続 6 件 Repository PR は本 PR を参照して同パターン実装。Aggregate 別の masking 対象カラムが存在する PR（agent / room / directive / task / external-review-gate）では `MaskedJSONEncoded` / `MaskedText` の Layer 2 arch test 検証が動作確認の対象になる |

**Schneier 申し送り（前 PR レビューより継承）**:

- **CI 三層防衛の Empire 拡張**: 本 PR で確定 E として正式凍結（M2 永続化基盤レビュー時の「後続 PR で各 Aggregate に拡張」申し送りに対応）。Layer 1 + Layer 2 + Layer 3 の 3 層が「対象なし」明示登録を含む構造で完備、後続 Repository PR の漏れを物理保証
- **`storage.md` §逆引き表のテンプレート化**: 確定 E Layer 3 で「Empire は対象なし」を明示。後続 Repository PR は同形式で「対象あり」「対象なし」を区別して追加する責務（テンプレート参照源、確定 F）
- **本 feature 固有の申し送り**:
  - シングルトン強制（`EmpireAlreadyExistsError`）は `feature/empire-application` 責務、本 PR は `count()` メソッド提供のみ。後続 application PR で `EmpireService.create()` の Fail Fast 検査を漏れなく実装する申し送り
  - `EmpireService.create()` の Tx 境界は **本 PR で凍結した「Repository は session 受け取り、commit/rollback は service 側」契約に従う**こと（確定 B）
  - `feature/empire-application` がエラー文言（`EmpireAlreadyExistsError`）を実装する際、本 PR の Repository は文言定義を持たない（infrastructure は内部 API、ユーザー向けメッセージは application / API 層責務）

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-EMR-001〜005 すべてに 1 件以上のテストケースがあり、特に integration が Repository 契約 + Alembic + CI 三層防衛を単独でカバーしている
- [ ] **delete-then-insert 5 段階順序（確定 B）**が TC-IT-EMR-011 で実 SQL 発行順を物理観測している
- [ ] **Tx 境界の責務分離（確定 B）**が TC-IT-EMR-012 で commit / rollback 両経路で確認、Repository が明示的 commit / rollback しないことを assert している
- [ ] **domain↔row 変換ラウンドトリップ（確定 C）**が TC-UT-EMR-003（unit 純粋）+ TC-IT-EMR-007（実 DB 経由）の 2 経路で物理確認
- [ ] **シングルトン責務分離（確定 D）**が TC-IT-EMR-018 で「Repository 自身は強制しない」物理確認
- [ ] **CI 三層防衛（確定 E）**: Layer 1 grep（TC-CI-EMR-001）+ Layer 2 arch test（TC-IT-EMR-009）+ Layer 3 storage.md（TC-DOC-EMR-001）の 3 つすべてに証拠ケース
- [ ] **「対象なし」明示登録のテンプレート構造（確定 E / F）**: TC-IT-EMR-017 で parametrize リスト形式が後続 Repository PR の「対象あり」登録にも対応できる構造であることを確認
- [ ] **Alembic 2nd revision の chain 一直線**（確定 F）: TC-IT-EMR-016 で head 分岐なし、down_revision が `0001_init` を指していることを物理確認
- [ ] **upgrade/downgrade idempotent**: TC-IT-EMR-015 で双方向 migration を物理確認
- [ ] **DB 制約検証**: FK CASCADE（TC-IT-EMR-013）+ UNIQUE 制約（TC-IT-EMR-014）の Alembic 2nd revision DDL の正しさを物理確認
- [ ] 確定 A〜F すべてに証拠ケースが含まれる
- [ ] empire / persistence-foundation の WeakValueDictionary レジストリ + tmp_path 経由の実 DB 規約と整合した fixture 設計
- [ ] Schneier 申し送り（CI 三層防衛拡張テンプレート / シングルトン強制の application 層責務 / Tx 境界の Repository / service 分離 / storage.md §逆引き表の Empire 行）が次レビュー時に確認可能な形で test-design および設計書に記録されている
- [ ] **後続 6 件 Repository PR のテンプレート責務（確定 F）**: チェックリスト 11 項目（A〜E）を本 PR が満たすことが test-design.md レビュー観点で凍結されている
