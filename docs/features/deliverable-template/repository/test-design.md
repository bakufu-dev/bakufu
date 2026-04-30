# テスト設計書

> feature: `deliverable-template` / sub-feature: `repository`
> 親業務仕様: [`../feature-spec.md`](../feature-spec.md)
> 対象範囲: REQ-DTR-001〜007 / §9 受入基準 AC#14, #15 + 内部品質基準（§確定 A〜K）/
> Repository ポート + UPSERT 1 テーブル + domain↔row 変換（§D/E/F/G）+ schema type 判別 +
> SemVer TEXT + ORDER BY 規約 + UNIQUE 制約 + CI 三層防衛 no-mask

本 sub-feature は M2 Repository **4 番目の Aggregate Repository PR** であり、
empire-repository（PR #25）が凍結したテンプレート（§確定 A〜F）を**完全継承**する。
本 feature 固有の追加凍結条項は §確定 D（schema type 判別）/ §確定 E（SemVer TEXT）/
§確定 F（acceptance_criteria_json / composition_json JSONEncoded + A08）/
§確定 G（deliverable_template_refs_json JSONEncoded + A08）/ §確定 H（UNIQUE(empire_id, role)
IntegrityError 伝播）/ §確定 I（ORDER BY 規約）/ §確定 J（CI 三層防衛 no-mask 拡張）/
§確定 K（Alembic 0012 revision）の 8 件。

戦略ガイド §結合テスト方針「DB は実接続」「外部 API のみモック」に従い、本 sub-feature のテストは:

- **integration test 主導**: Alembic 0012 revision 適用 → AsyncSession で
  `find_by_id` / `find_all` / `save` / `find_by_empire_and_role` / `find_all_by_empire`
  の各メソッド契約検証（`tmp_path` で実 SQLite ファイル）。
  persistence-foundation conftest の `app_engine` / `session_factory` fixture を再利用。
- **CI 三層防衛 no-mask 拡張**: Layer 1（grep guard）+ Layer 2（arch test）+
  Layer 3（storage.md）の 3 層が「`deliverable_templates` / `role_profiles` の全カラムが
  masking 対象外」を物理保証（§確定 J / REQ-DTR-006）
- **schema type 判別の物理確認**: §確定 D が規定する type カラム判別ロジックを
  JSON_SCHEMA / OPENAPI（json.dumps）と MARKDOWN 等（plain text）の両経路で IT 物理確認
- **A08 防御（Unsafe Deserialization）の物理確認**: `_from_row` が
  `AcceptanceCriterion.model_validate` / `DeliverableTemplateRef.model_validate` を
  必ず経由することを DB 直 INSERT → find 経路で物理確認（§確定 F/G）
- **UNIQUE(empire_id, role) 制約違反の物理確認**: 同一 `(empire_id, role)` 別 id の
  二重 save が `IntegrityError` を raise することを実 SQLite で確認（§確定 H）
- **assumed mock 禁止規約**: `mock.return_value` インライン辞書は禁止、
  DeliverableTemplate / RoleProfile は既存 `tests/factories/deliverable_template.py`
  （domain sub-feature 由来）から取得

masking 配線（MaskedJSONEncoded / MaskedText）は **本 sub-feature には存在しない**。
feature-spec §13 の業務判断に従い全カラムが機密レベル「低」のため、masking 実装・テストは
不要（CI 三層防衛 Layer 1〜3 で「masking 対象なし」を物理保証、§確定 J）。

E2E は親 [`../system-test-design.md`](../system-test-design.md) が担当。
本テスト設計書は IT / UT のみ扱う。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|--------------|-----------|----|---------|
| REQ-DTR-001 | `DeliverableTemplateRepository(Protocol)` 定義 | TC-IT-DTR-001 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-001 | `SqliteDeliverableTemplateRepository` の Protocol 充足 | TC-IT-DTR-002 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-002 | `find_by_id(existing_id)` で DeliverableTemplate 取得 | TC-IT-DTR-003 | 結合 | 正常系 | AC#14 |
| REQ-DTR-002 | `find_by_id(unknown_id)` で None | TC-IT-DTR-004 | 結合 | 異常系 | 内部品質基準 |
| REQ-DTR-002（§確定 I, ORDER BY name） | `find_all()` が `ORDER BY name ASC` で決定論的順序を返す | TC-IT-DTR-005 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-002（§確定 I, ORDER BY name） | 0 件の場合 `find_all()` が空リストを返す | TC-IT-DTR-006 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-002（§確定 B, UPSERT 新規） | `save(template)` 新規挿入で `deliverable_templates` に行が入る | TC-IT-DTR-007 | 結合 | 正常系 | AC#14 |
| REQ-DTR-002（§確定 B, UPSERT 更新） | `save(template)` 既存上書きで全カラムが最新値に置換される | TC-IT-DTR-008 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-002（§確定 B, Tx 境界） | service 側 `async with session.begin()` で commit / rollback 両経路、Repository は明示的 commit/rollback しない | TC-IT-DTR-009 | 結合 | 正常系/異常系 | （責務境界） |
| REQ-DTR-002（§確定 D, schema JSON_SCHEMA） | `type=JSON_SCHEMA` の `schema(dict)` が `json.dumps` で Text 格納 → `json.loads` で dict 復元 | TC-IT-DTR-010 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-002（§確定 D, schema OPENAPI） | `type=OPENAPI` の `schema(dict)` が `json.dumps` で Text 格納 → `json.loads` で dict 復元 | TC-IT-DTR-011 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-002（§確定 D, schema MARKDOWN） | `type=MARKDOWN` の `schema(str)` が plain text 格納 → そのまま str 復元 | TC-IT-DTR-012 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-002（§確定 D, schema CODE_SKELETON） | `type=CODE_SKELETON` の `schema(str)` が plain text 格納 → そのまま str 復元 | TC-IT-DTR-013 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-002（§確定 D, schema PROMPT） | `type=PROMPT` の `schema(str)` が plain text 格納 → そのまま str 復元 | TC-IT-DTR-014 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-002（§確定 E, SemVer TEXT） | SemVer が `"major.minor.patch"` TEXT で格納 → `SemVer.from_str` で復元 | TC-IT-DTR-015 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-002（§確定 F, A08, acceptance_criteria） | `acceptance_criteria_json` 復元が `AcceptanceCriterion.model_validate` 経由（A08 防御） | TC-IT-DTR-016 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-002（§確定 F, A08, composition） | `composition_json` 復元が `DeliverableTemplateRef.model_validate` 経由（A08 防御） | TC-IT-DTR-017 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-002（§確定 F, A08, 不正 JSON） | `_from_row` で `acceptance_criteria_json` が不正データの場合 `ValidationError` / `ValueError` 上位伝播（A08 Fail-Fast） | TC-IT-DTR-018 | 結合 | 異常系 | 内部品質基準 |
| REQ-DTR-002（§確定 C, ラウンドトリップ） | `save(template) → find_by_id(template.id)` で全フィールド構造的等価 | TC-IT-DTR-019 | 結合 | 正常系 | AC#14 |
| REQ-DTR-003 | `RoleProfileRepository(Protocol)` 定義 | TC-IT-RPR-001 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-003 | `SqliteRoleProfileRepository` の Protocol 充足 | TC-IT-RPR-002 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-004 | `find_by_empire_and_role(empire_id, role)` 既存 RoleProfile 取得 | TC-IT-RPR-003 | 結合 | 正常系 | AC#15 |
| REQ-DTR-004 | `find_by_empire_and_role(empire_id, role)` 不在 → None | TC-IT-RPR-004 | 結合 | 異常系 | 内部品質基準 |
| REQ-DTR-004（§確定 I, ORDER BY role） | `find_all_by_empire(empire_id)` が `ORDER BY role ASC` で決定論的順序を返す | TC-IT-RPR-005 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-004（§確定 I） | `find_all_by_empire(empire_id)` は別 empire の行を返さない | TC-IT-RPR-006 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-004（§確定 B, UPSERT 新規） | `save(role_profile)` 新規挿入で `role_profiles` に行が入る | TC-IT-RPR-007 | 結合 | 正常系 | AC#15 |
| REQ-DTR-004（§確定 B, UPSERT 更新） | `save(role_profile)` 既存上書きで全カラムが最新値に置換される（同 id 上書き） | TC-IT-RPR-008 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-004（§確定 B, Tx 境界） | service 側 `async with session.begin()` で commit / rollback 両経路、Repository は明示的 commit/rollback しない | TC-IT-RPR-009 | 結合 | 正常系/異常系 | （責務境界） |
| REQ-DTR-004（§確定 G, A08, deliverable_template_refs） | `deliverable_template_refs_json` 復元が `DeliverableTemplateRef.model_validate` 経由（A08 防御） | TC-IT-RPR-010 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-004（§確定 G, A08, 不正 JSON） | `_from_row` で `deliverable_template_refs_json` が不正データの場合 `ValidationError` / `ValueError` 上位伝播（A08 Fail-Fast） | TC-IT-RPR-011 | 結合 | 異常系 | 内部品質基準 |
| REQ-DTR-004（§確定 H, UNIQUE 違反） | 同一 `(empire_id, role)` 別 id の `save()` が `IntegrityError` を raise（DB 最終防衛線） | TC-IT-RPR-012 | 結合 | 異常系 | 内部品質基準 |
| REQ-DTR-004（§確定 H, UNIQUE 同 id UPSERT） | 同一 id の `save()` 再呼び出しが `IntegrityError` を raise しない（正常 UPSERT） | TC-IT-RPR-013 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-004（FK CASCADE） | `empires` の CASCADE DELETE で `role_profiles` 行が連鎖削除される | TC-IT-RPR-014 | 結合 | 正常系 | （データモデル） |
| REQ-DTR-004（§確定 C, ラウンドトリップ） | `save(role_profile) → find_by_empire_and_role(empire_id, role)` で全フィールド構造的等価 | TC-IT-RPR-015 | 結合 | 正常系 | AC#15 |
| REQ-DTR-005（Alembic 0012 upgrade） | `upgrade head` で `deliverable_templates` / `role_profiles` 2 テーブル追加 | TC-IT-MIGR-012-001 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-005（Alembic 0012 UNIQUE 制約） | upgrade 後 `role_profiles` に `UNIQUE(empire_id, role)` 制約が存在する | TC-IT-MIGR-012-002 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-005（Alembic 0012 downgrade） | `downgrade` で `role_profiles` → `deliverable_templates` の逆順削除 | TC-IT-MIGR-012-003 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-005（Alembic 0012 round-trip） | upgrade → downgrade → upgrade が冪等 | TC-IT-MIGR-012-004 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-005（revision chain 一直線） | 0012 が単一 head / `down_revision == "0011_stage_required_deliverables"` | TC-IT-MIGR-012-005 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-006（Layer 1 grep） | `scripts/ci/check_masking_columns.sh` で両テーブルが Masked* 不在を pass | TC-CI-DTR-001 | CI script | 正常系 | 内部品質基準 |
| REQ-DTR-006（Layer 2 arch） | `tests/architecture/test_masking_columns.py` で両テーブルの全カラムが Masked* 不在を assert | TC-IT-DTR-020 | 結合 | 正常系 | 内部品質基準 |
| REQ-DTR-007（Layer 3 storage.md） | §逆引き表に `deliverable_templates` / `role_profiles` の 2 行（masking 対象なし）が存在 | TC-DOC-DTR-001 | doc 検証 | 正常系 | （Layer 3） |

**マトリクス充足の証拠**:

- REQ-DTR-001〜007 すべてに最低 1 件のテストケース
- **§9 受入基準 AC#14（DeliverableTemplate 永続化・再起動跨ぎ保持）**: TC-IT-DTR-003 / 007 / 019 で IT カバー。E2E（再起動跨ぎ）は親 system-test-design.md
- **§9 受入基準 AC#15（RoleProfile 永続化・再起動跨ぎ保持）**: TC-IT-RPR-003 / 007 / 015 で IT カバー。E2E は親 system-test-design.md
- **§確定 D（schema type 判別）**: TC-IT-DTR-010〜014 で JSON_SCHEMA / OPENAPI / MARKDOWN / CODE_SKELETON / PROMPT の 5 type すべてを物理確認
- **§確定 E（SemVer TEXT）**: TC-IT-DTR-015 でラウンドトリップ
- **§確定 F（JSONEncoded A08）**: TC-IT-DTR-016〜018 で正常系 model_validate 経由 + 不正 JSON Fail-Fast を物理確認
- **§確定 G（deliverable_template_refs_json A08）**: TC-IT-RPR-010〜011 で同上
- **§確定 H（UNIQUE 制約 IntegrityError 伝播）**: TC-IT-RPR-012 で IntegrityError、TC-IT-RPR-013 で正常 UPSERT を物理確認
- **§確定 I（ORDER BY 規約）**: TC-IT-DTR-005（name ASC）+ TC-IT-RPR-005（role ASC）で決定論的順序を物理確認
- **§確定 B（Tx 境界 UPSERT）**: TC-IT-DTR-009 + TC-IT-RPR-009 で commit / rollback 両経路、Repository が明示的 commit/rollback しないことを assert
- **§確定 K（Alembic 0012）**: TC-IT-MIGR-012-001〜005 で upgrade / downgrade / round-trip / chain 一直線を物理確認
- **CI 三層防衛 no-mask（§確定 J）**: Layer 1（TC-CI-DTR-001）+ Layer 2（TC-IT-DTR-020）+ Layer 3（TC-DOC-DTR-001）3 層すべてに証拠ケース
- 孤児要件ゼロ

## 外部 I/O 依存マップ

本 sub-feature は infrastructure 層の Repository 実装。empire-repository / workflow-repository と同方針で本物の SQLite + 本物の Alembic + 本物の SQLAlchemy AsyncSession を使う。

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **SQLite (sqlite+aiosqlite)** | engine / session / 2 テーブル / Alembic migration | 不要（実 DB を `tmp_path` 配下で起動、テストごとに使い捨て） | 不要 | **済（本物使用、persistence-foundation conftest.py の `app_engine` / `session_factory` fixture を再利用）** |
| **ファイルシステム** | `bakufu.db` / WAL/SHM ファイル | 不要（`pytest.tmp_path`） | 不要 | **済（本物使用）** |
| **Alembic** | 0012 revision の `upgrade head` / `downgrade` | 不要（本物の `alembic upgrade` を実 SQLite に対し実行） | 不要 | **済（本物使用、persistence-foundation の `run_upgrade_head` を再利用）** |
| **SQLAlchemy 2.x AsyncSession** | UoW 境界 / Repository メソッド経由の SQL 発行 | 不要 | 不要 | **済（本物使用）** |

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `make_deliverable_template`（既存、domain sub-feature 由来） | `DeliverableTemplate`（デフォルト: MARKDOWN 型、空 schema / acceptance_criteria / composition） | `True` |
| `make_role_profile`（既存） | `RoleProfile`（デフォルト: DEVELOPER ロール、空 deliverable_template_refs） | `True` |
| `make_acceptance_criterion`（既存） | `AcceptanceCriterion`（id=uuid4(), description="満たすべき条件", required=True） | `True` |
| `make_deliverable_template_ref`（既存） | `DeliverableTemplateRef`（template_id=uuid4(), minimum_version=SemVer(1,0,0)） | `True` |
| `make_semver`（既存） | `SemVer`（デフォルト: 1.0.0） | `True` |
| `make_empire`（既存、empire factory 由来） | `Empire`（role_profiles の FK 先 empire 行を `empires` テーブルに INSERT するために使用） | `True` |

`tests/factories/deliverable_template.py` は domain sub-feature（PR #127）で確立済み。本 PR では factory 追加なし。

**raw fixture / characterization は不要**: SQLite + SQLAlchemy + Alembic はすべて標準ライブラリ仕様 / 既存 conftest セット内動作で固定、外部観測（実 DB ファイル）が真実源として常時使える。masking gateway は不使用のため、masking 初期化 fixture も不要。

## 結合テストケース

「Repository 契約 + 実 SQLite + 実 Alembic」を contract testing する層。M2 永続化基盤の `app_engine` / `session_factory` fixture を再利用。

### Protocol 定義 + 充足（内部品質基準、§確定 A）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|------------|---------|------|---------|
| TC-IT-DTR-001 | `DeliverableTemplateRepository(Protocol)` 定義 | — | `application/ports/deliverable_template_repository.py` がインポート可能 | `from bakufu.application.ports.deliverable_template_repository import DeliverableTemplateRepository` | Protocol が `find_by_id` / `find_all` / `save` の 3 メソッドを宣言、すべて `async def`。`@runtime_checkable` なし |
| TC-IT-DTR-002 | `SqliteDeliverableTemplateRepository` の Protocol 充足 | `session_factory` | engine + Alembic 適用済み | `repo: DeliverableTemplateRepository = SqliteDeliverableTemplateRepository(session)` で型代入が pyright で通る | pyright strict pass。duck typing で `hasattr(repo, 'find_by_id') and hasattr(repo, 'find_all') and hasattr(repo, 'save')` 全 True |
| TC-IT-RPR-001 | `RoleProfileRepository(Protocol)` 定義 | — | `application/ports/role_profile_repository.py` がインポート可能 | `from bakufu.application.ports.role_profile_repository import RoleProfileRepository` | Protocol が `find_by_empire_and_role` / `find_all_by_empire` / `save` の 3 メソッドを宣言、すべて `async def`。`@runtime_checkable` なし |
| TC-IT-RPR-002 | `SqliteRoleProfileRepository` の Protocol 充足 | `session_factory` | engine + Alembic 適用済み | `repo: RoleProfileRepository = SqliteRoleProfileRepository(session)` で型代入が pyright で通る | pyright strict pass。duck typing で `hasattr(repo, 'find_by_empire_and_role') and hasattr(repo, 'find_all_by_empire') and hasattr(repo, 'save')` 全 True |

### DeliverableTemplate 基本 CRUD（AC#14 / 内部品質基準）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|------------|---------|------|---------|
| TC-IT-DTR-003 | `find_by_id(existing_id)` | `session_factory` + `make_deliverable_template` | `save(template)` で 1 件保存済み | 別 session で `find_by_id(template.id)` | 保存した DeliverableTemplate と同一 id を持つ Aggregate を返す |
| TC-IT-DTR-004 | `find_by_id(unknown_id)` | `session_factory` | DB 空 | `find_by_id(uuid4())` を呼ぶ | `None` を返す。例外を raise しない |
| TC-IT-DTR-005 | `find_all()` ORDER BY name ASC | `session_factory` + `make_deliverable_template` | 異なる name（"Z-template" / "A-template" / "M-template"）で 3 件 save 済み | `find_all()` を呼ぶ | name アルファベット昇順 `["A-template", "M-template", "Z-template"]` の順序で返す（§確定 I） |
| TC-IT-DTR-006 | `find_all()` 0 件 | `session_factory` | DB 空 | `find_all()` を呼ぶ | 空リスト `[]` を返す。例外を raise しない |
| TC-IT-DTR-007 | `save(template)` 新規 UPSERT | `session_factory` + `make_deliverable_template` | DB 空 | `save(template)` 後、別 session で raw SQL `SELECT * FROM deliverable_templates WHERE id=?` | 1 行が存在し、`name` / `type` / `version` / `schema` が Aggregate VO 値と一致 |
| TC-IT-DTR-008 | `save(template)` 既存上書き UPSERT | `session_factory` + `make_deliverable_template` | 1 度 save 済みの template | name を変更した同 id の template を再 `save(updated_template)` | `find_by_id(template.id)` で取得した Aggregate が更新後 name を返す。古い値は残らない（1 テーブル UPSERT §確定 B） |
| TC-IT-DTR-009 | Tx 境界の責務分離（§確定 B） | `session_factory` + `make_deliverable_template` | — | (1) **正常系**: `async with session.begin(): await repo.save(template)` → ブロック退出で commit、(2) **異常系**: 同ブロック内で `raise RuntimeError` → rollback | commit 経路で template が永続化、rollback 経路で原子的に消える。Repository は `await session.commit()` / `session.rollback()` を呼ばない（§確定 B） |

### §確定 D（schema type 判別、内部品質基準）

`type=JSON_SCHEMA` / `OPENAPI` は `json.dumps(dict)` で格納、
`MARKDOWN` / `CODE_SKELETON` / `PROMPT` は plain text のまま格納。
`_from_row` は `row['type']` を判別キーとして `json.loads` or 素通しを切り替える。

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|------------|---------|------|---------|
| TC-IT-DTR-010 | schema JSON_SCHEMA → json.dumps → json.loads ラウンドトリップ | `session_factory` + `make_deliverable_template` | — | `type=JSON_SCHEMA`, `schema={"$schema": "http://json-schema.org/draft-07/schema#", "type": "object"}` の template を save → find_by_id | 復元 `template.schema` が元の `dict` と等価。DB カラム `schema` は JSON 文字列（raw SQL で `{"$schema"` 等の文字列が観測できる）。`type(restored.schema) is dict` |
| TC-IT-DTR-011 | schema OPENAPI → json.dumps → json.loads ラウンドトリップ | `session_factory` + `make_deliverable_template` | — | `type=OPENAPI`, `schema={"openapi": "3.0.0", "info": {"title": "test"}}` の template を save → find_by_id | 復元 `template.schema` が元の `dict` と等価。`type(restored.schema) is dict` |
| TC-IT-DTR-012 | schema MARKDOWN → plain text ラウンドトリップ | `session_factory` + `make_deliverable_template` | — | `type=MARKDOWN`, `schema="# 設計書\n## 概要\n..."` の template を save → find_by_id | 復元 `template.schema` が元の `str` と等価（改行含む）。`type(restored.schema) is str` |
| TC-IT-DTR-013 | schema CODE_SKELETON → plain text ラウンドトリップ | `session_factory` + `make_deliverable_template` | — | `type=CODE_SKELETON`, `schema="def main(): pass"` の template を save → find_by_id | 復元 `template.schema` が元の `str` と等価。`type(restored.schema) is str` |
| TC-IT-DTR-014 | schema PROMPT → plain text ラウンドトリップ | `session_factory` + `make_deliverable_template` | — | `type=PROMPT`, `schema="あなたは...としてふるまいます"` の template を save → find_by_id | 復元 `template.schema` が元の `str` と等価。`type(restored.schema) is str` |

### §確定 E（SemVer TEXT ラウンドトリップ、内部品質基準）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|------------|---------|------|---------|
| TC-IT-DTR-015 | SemVer TEXT "major.minor.patch" ラウンドトリップ | `session_factory` + `make_deliverable_template` + `make_semver` | — | `version=SemVer(major=3, minor=14, patch=159)` の template を save → find_by_id、かつ raw SQL で `version` カラム文字列を取得 | (1) raw SQL `version` カラムが文字列 `"3.14.159"` そのものを格納、(2) `find_by_id` 復元後の `template.version == SemVer(3, 14, 159)` |

### §確定 F（acceptance_criteria_json / composition_json A08 防御、内部品質基準）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|------------|---------|------|---------|
| TC-IT-DTR-016 | `acceptance_criteria_json` A08 防御（model_validate 経由の物理確認） | `session_factory` | — | DB に valid な `acceptance_criteria_json` を直接 INSERT（UUID 文字列含む JSON）し、`find_by_id` で水和 | 復元 `template.acceptance_criteria[0]` が `AcceptanceCriterion` インスタンス。`type(restored.acceptance_criteria[0].id) is UUID`（str ではなく UUID 型）。model_validate が UUID 変換を保証したことの証拠 |
| TC-IT-DTR-017 | `composition_json` A08 防御（model_validate 経由の物理確認） | `session_factory` | — | DB に valid な `composition_json` を直接 INSERT（`template_id` UUID 文字列 + `minimum_version` dict を含む JSON）し、`find_by_id` で水和 | 復元 `template.composition[0]` が `DeliverableTemplateRef` インスタンス。`type(restored.composition[0].template_id) is UUID`（UUID 型）。`restored.composition[0].minimum_version == SemVer(major, minor, patch)` |
| TC-IT-DTR-018 | `_from_row` 不正 `acceptance_criteria_json` → ValidationError（A08 Fail-Fast） | `session_factory` | — | `acceptance_criteria_json` に `template_id` が UUID 形式でない壊れた JSON（`[{"id": "not-a-uuid", "description": "x", "required": true}]`）を直接 INSERT し、`find_by_id` を呼ぶ | `pydantic.ValidationError` または `ValueError` が raise される。Repository が Exception を握り潰さない（A08 Fail-Fast = DB 破損を起動時に検出） |

### §確定 C（DeliverableTemplate domain↔row ラウンドトリップ、内部品質基準）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|------------|---------|------|---------|
| TC-IT-DTR-019 | `save → find_by_id` 全フィールド構造的等価 | `session_factory` + `make_deliverable_template` + `make_acceptance_criterion` + `make_deliverable_template_ref` | — | `acceptance_criteria` 2 件 + `composition` 1 件 + SemVer(2,3,4) + `type=MARKDOWN` + `schema="test schema"` の template を save → find_by_id | `restored.id == template.id`、`restored.name == template.name`、`restored.version == SemVer(2,3,4)`、`restored.acceptance_criteria == template.acceptance_criteria`（tuple 順・等値）、`restored.composition == template.composition` |

### RoleProfile 基本 CRUD（AC#15 / 内部品質基準）

**前提**: `role_profiles.empire_id` は `empires.id` への FK。テスト前に `make_empire()` を使い empire 行を `empires` テーブルに直接 INSERT すること（または empire repository を使い save すること）。

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|------------|---------|------|---------|
| TC-IT-RPR-003 | `find_by_empire_and_role(empire_id, role)` 既存取得 | `session_factory` + `make_role_profile` | empire 行 + `save(role_profile)` で 1 件保存済み | 別 session で `find_by_empire_and_role(role_profile.empire_id, role_profile.role)` | 保存した RoleProfile と同一 id を持つ Aggregate を返す |
| TC-IT-RPR-004 | `find_by_empire_and_role` 不在 → None | `session_factory` | DB 空 | `find_by_empire_and_role(uuid4(), Role.DEVELOPER)` | `None` を返す。例外を raise しない |
| TC-IT-RPR-005 | `find_all_by_empire(empire_id)` ORDER BY role ASC | `session_factory` + `make_role_profile` | 同一 empire に `Role.TESTER` / `Role.DEVELOPER` / `Role.REVIEWER` の 3 件 save 済み | `find_all_by_empire(empire_id)` | role アルファベット昇順（"DEVELOPER", "REVIEWER", "TESTER" の順）で返す（§確定 I） |
| TC-IT-RPR-006 | `find_all_by_empire` 別 empire を除外 | `session_factory` + `make_role_profile` | empire A の DEVELOPER 1 件 + empire B の DEVELOPER 1 件 save 済み | `find_all_by_empire(empire_a_id)` | empire A の 1 件のみ返す。empire B の行は含まれない |
| TC-IT-RPR-007 | `save(role_profile)` 新規 UPSERT | `session_factory` + `make_role_profile` | empire 行あり、DB 空 | `save(role_profile)` 後、raw SQL `SELECT * FROM role_profiles WHERE id=?` | 1 行が存在し、`empire_id` / `role` / `deliverable_template_refs_json` が Aggregate VO 値と一致 |
| TC-IT-RPR-008 | `save(role_profile)` 既存上書き UPSERT（同 id） | `session_factory` + `make_role_profile` | 1 度 save 済みの role_profile | `deliverable_template_refs` を更新した同 id の role_profile を再 `save(updated_role_profile)` | `find_by_empire_and_role` で取得した Aggregate が更新後 refs を返す。古い refs は残らない |
| TC-IT-RPR-009 | Tx 境界の責務分離（§確定 B） | `session_factory` + `make_role_profile` | empire 行あり | (1) **正常系**: `async with session.begin(): await repo.save(role_profile)` → commit、(2) **異常系**: 同ブロック内で `raise RuntimeError` → rollback | commit 経路で role_profile が永続化、rollback 経路で消える。Repository は `await session.commit()` / `session.rollback()` を呼ばない |

### §確定 G（deliverable_template_refs_json A08 防御、内部品質基準）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|------------|---------|------|---------|
| TC-IT-RPR-010 | `deliverable_template_refs_json` A08 防御（model_validate 経由の物理確認） | `session_factory` | empire 行あり | DB に valid な `deliverable_template_refs_json`（`[{"template_id": "<uuid>", "minimum_version": {"major": 2, "minor": 1, "patch": 0}}]`）を直接 INSERT し、`find_by_empire_and_role` で水和 | 復元 `role_profile.deliverable_template_refs[0]` が `DeliverableTemplateRef` インスタンス。`type(restored.deliverable_template_refs[0].template_id) is UUID`。`minimum_version == SemVer(2, 1, 0)` |
| TC-IT-RPR-011 | `_from_row` 不正 `deliverable_template_refs_json` → ValidationError（A08 Fail-Fast） | `session_factory` | empire 行あり | `deliverable_template_refs_json` に UUID 形式でない壊れた JSON を直接 INSERT し、`find_by_empire_and_role` を呼ぶ | `pydantic.ValidationError` または `ValueError` が raise される |

### §確定 H（UNIQUE(empire_id, role) 制約違反、内部品質基準）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|------------|---------|------|---------|
| TC-IT-RPR-012 | 同一 `(empire_id, role)` 別 id → `IntegrityError` | `session_factory` + `make_role_profile` | empire 行あり + (empire_id=A, role=DEVELOPER) 1 件 save 済み | **別 id** で同じ `(empire_id=A, role=DEVELOPER)` の `RoleProfile` を `save()` | `sqlalchemy.IntegrityError`（または `UniqueViolation`）が raise される。DB の UNIQUE(empire_id, role) 制約が最終防衛線として機能（§確定 H） |
| TC-IT-RPR-013 | 同 id UPSERT は IntegrityError しない | `session_factory` + `make_role_profile` | empire 行あり + 1 件 save 済み | 同一 id、同一 `(empire_id, role)` の `save()` を再呼び出し | 例外を raise せず正常に完了する。`ON CONFLICT (id) DO UPDATE` が動作（§確定 B 設計根拠） |
| TC-IT-RPR-014 | FK CASCADE DELETE（`empires` DELETE → `role_profiles` 連鎖削除） | `session_factory` + `make_role_profile` | empire 行あり + role_profile save 済み | raw SQL で `DELETE FROM empires WHERE id=:empire_id` を実行 | `role_profiles` の対応行が CASCADE で削除される（FK ON DELETE CASCADE 物理確認） |

### §確定 C（RoleProfile domain↔row ラウンドトリップ、AC#15）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|------------|---------|------|---------|
| TC-IT-RPR-015 | `save → find_by_empire_and_role` 全フィールド構造的等価 | `session_factory` + `make_role_profile` + `make_deliverable_template_ref` | empire 行あり | `deliverable_template_refs` 2 件の RoleProfile（REVIEWER ロール）を save → `find_by_empire_and_role(empire_id, Role.REVIEWER)` | `restored.id == role_profile.id`、`restored.empire_id == role_profile.empire_id`、`restored.role == Role.REVIEWER`、`restored.deliverable_template_refs == role_profile.deliverable_template_refs`（tuple 順・等値） |

### Alembic 0012 revision（内部品質基準、§確定 K）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|------------|---------|------|---------|
| TC-IT-MIGR-012-001 | upgrade で 2 テーブル追加 | `tmp_path` 配下の bakufu.db | スキーマ未適用の新規 engine | `alembic upgrade head` を実行 | `SELECT name FROM sqlite_master WHERE type='table'` で `deliverable_templates` / `role_profiles` の 2 テーブルが存在する |
| TC-IT-MIGR-012-002 | upgrade 後 `role_profiles` UNIQUE 制約が存在する | `tmp_path` | upgrade 済み | `PRAGMA index_list(role_profiles)` を実行 | UNIQUE インデックス（名前または sqlite_autoindex_*）が `role_profiles` テーブルに存在する（§確定 H 物理確認） |
| TC-IT-MIGR-012-003 | downgrade で 2 テーブル削除（FK 安全順序） | `tmp_path` | upgrade 済み | `alembic downgrade` を `"0011_stage_required_deliverables"` まで実行 | (a) `role_profiles` が削除されている、(b) `deliverable_templates` が削除されている。`workflow_stages` / `workflow_transitions` など他テーブルは残る |
| TC-IT-MIGR-012-004 | upgrade → downgrade → upgrade の冪等性 | `tmp_path` | スキーマ未適用 | (1) upgrade head → 2 テーブル確認、(2) downgrade to 0011 → 2 テーブル削除確認、(3) 再 upgrade head | (3) 後に `deliverable_templates` / `role_profiles` が再度存在する。UNIQUE 制約も再作成される |
| TC-IT-MIGR-012-005 | revision chain 一直線（単一 head + 0012.down_revision） | Alembic config | versions/ に 0012 ファイルあり | `ScriptDirectory.get_heads()` + `script.get_revision("0012_deliverable_template_aggregate")` | (a) heads は 1 件のみ（head 分岐なし）、(b) `rev.down_revision == "0011_stage_required_deliverables"` |

### CI 三層防衛 no-mask（§確定 J / REQ-DTR-006）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|------------|---------|------|---------|
| TC-CI-DTR-001 | Layer 1: `scripts/ci/check_masking_columns.sh` の deliverable-template 拡張 | repo root | スクリプトが `deliverable_templates` / `role_profiles` 両テーブルを「masking 対象なし」として明示登録 | `bash scripts/ci/check_masking_columns.sh` を実行 | exit 0。両テーブルファイルに `MaskedJSONEncoded` / `MaskedText` が存在しないことを grep guard が確認し pass |
| TC-IT-DTR-020 | Layer 2: `tests/architecture/test_masking_columns.py` の no-mask parametrize | `Base.metadata` | arch test に両テーブルの parametrize を追加済み | test が parametrize で `deliverable_templates` / `role_profiles` の全カラムを順に検査 | 全カラムの `column.type.__class__` が `MaskedJSONEncoded` でも `MaskedText` でもない（`String` / `UUIDStr` / `Text` / `JSONEncoded` のみ）。後続 PR が誤って Masked* を追加した瞬間 CI がブロック |
| TC-DOC-DTR-001 | Layer 3: `docs/design/domain-model/storage.md` §逆引き表に 2 行追加 | repo root | `storage.md` 編集済み | `storage.md` 内で `deliverable_templates` / `role_profiles` の 2 行が存在することを確認 | 両テーブル名が「masking 対象なし」を明示した行として §逆引き表に記載されている（empire-repository / workflow-repository の no-mask テンプレートと同形式） |

## ユニットテストケース

`tests/factories/deliverable_template.py` の factory 経由で domain 層 Aggregate を生成する。Repository クラス内 private method (`_to_row` / `_from_row`) は実 DB アクセスを伴うため integration として扱い、純 unit としての追加ケースは設けない（§確定 D/E/F/G の format 検証が DB 経由でこそ価値があるため integration に集約。empire-repository の TC-UT-EMR-001〜003 パターン同様の判断）。

## カバレッジ基準

- REQ-DTR-001 〜 007 の各要件が**最低 1 件**のテストケースで検証されている（マトリクス参照）
- **§確定 D（schema type 判別 5 経路）**: TC-IT-DTR-010〜014 で JSON_SCHEMA / OPENAPI / MARKDOWN / CODE_SKELETON / PROMPT の 5 type すべてを物理確認
- **§確定 E（SemVer TEXT）**: TC-IT-DTR-015 でラウンドトリップ + raw SQL カラム値物理確認
- **§確定 F（acceptance_criteria_json / composition_json A08 防御）**: TC-IT-DTR-016〜018 で model_validate 経由 + 不正 JSON Fail-Fast の 2 経路を物理確認
- **§確定 G（deliverable_template_refs_json A08 防御）**: TC-IT-RPR-010〜011 で同上
- **§確定 H（UNIQUE 制約 IntegrityError 伝播）**: TC-IT-RPR-012 で IntegrityError、TC-IT-RPR-013 で正常 UPSERT の両経路を物理確認
- **§確定 I（ORDER BY 規約）**: TC-IT-DTR-005（name ASC）+ TC-IT-RPR-005（role ASC）で決定論的順序を実 DB で物理確認
- **§確定 B（Tx 境界 UPSERT）**: TC-IT-DTR-009 + TC-IT-RPR-009 で commit / rollback 両経路、Repository が明示的 commit/rollback しないことを assert
- **§確定 C（domain↔row ラウンドトリップ）**: TC-IT-DTR-019 + TC-IT-RPR-015 で実 DB 経由の全フィールド構造的等価
- **§確定 K（Alembic 0012 migration）**: TC-IT-MIGR-012-001〜005 で upgrade / downgrade / round-trip / chain 一直線を物理確認
- **CI 三層防衛 no-mask（§確定 J）**: Layer 1（TC-CI-DTR-001）+ Layer 2（TC-IT-DTR-020）+ Layer 3（TC-DOC-DTR-001）3 層すべてに証拠ケース
- **AC#14（DeliverableTemplate 永続化）**: TC-IT-DTR-003 / 007 / 019 で IT カバー
- **AC#15（RoleProfile 永続化）**: TC-IT-RPR-003 / 007 / 015 で IT カバー
- §確定 A〜K すべてに証拠ケース
- C0 目標: `application/ports/deliverable_template_repository.py` /
  `application/ports/role_profile_repository.py` /
  `infrastructure/persistence/sqlite/repositories/deliverable_template_repository.py` /
  `infrastructure/persistence/sqlite/repositories/role_profile_repository.py` で **90% 以上**

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で 7 ジョブ緑
- ローカル:
  ```
  bash scripts/setup.sh
  cd backend && uv run pytest \
    tests/infrastructure/persistence/sqlite/repositories/test_deliverable_template_repository \
    tests/infrastructure/persistence/sqlite/repositories/test_role_profile_repository \
    tests/infrastructure/persistence/sqlite/test_alembic_deliverable_template.py \
    tests/architecture/test_masking_columns.py \
    tests/docs/test_storage_md_back_index.py \
    -v
  ```
- Backend 実起動: `cd backend && uv run python -m bakufu`（`BAKUFU_DATA_DIR=/tmp/bakufu-test`）
  - 起動時 Alembic auto-migrate で 0012 が適用されることをログで目視
  - `sqlite3 <DATA_DIR>/bakufu.db ".tables"` で `deliverable_templates` / `role_profiles` が見える
  - `sqlite3 <DATA_DIR>/bakufu.db "PRAGMA index_list(role_profiles)"` で UNIQUE インデックスが見える
- カバレッジ確認:
  ```
  cd backend && uv run pytest \
    --cov=bakufu.application.ports.deliverable_template_repository \
    --cov=bakufu.application.ports.role_profile_repository \
    --cov=bakufu.infrastructure.persistence.sqlite.repositories.deliverable_template_repository \
    --cov=bakufu.infrastructure.persistence.sqlite.repositories.role_profile_repository \
    --cov-report=term-missing
  ```
  → 90% 以上

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      deliverable_template.py             # 既存（domain sub-feature PR #127）追加なし
    architecture/
      test_masking_columns.py             # 既存 + deliverable-template no-mask parametrize
                                          # TC-IT-DTR-020
    infrastructure/
      persistence/
        sqlite/
          repositories/
            test_deliverable_template_repository/
              __init__.py
              test_crud.py                # TC-IT-DTR-001〜019（Protocol/CRUD/type判別/SemVer/A08）
            test_role_profile_repository/
              __init__.py
              test_crud.py                # TC-IT-RPR-001〜015（Protocol/CRUD/UNIQUE/A08）
          test_alembic_deliverable_template.py  # TC-IT-MIGR-012-001〜005（0012 migration 検証）
    docs/
      test_storage_md_back_index.py       # 既存 + deliverable-template 行検証（TC-DOC-DTR-001）
```

**配置の根拠**:

- empire-repository / workflow-repository の `test_*_repository/` ディレクトリ分割パターンを継承
- masking 専用ファイル（`test_masking.py`）は不要（本 feature は masking 対象なし）。各 Repository の IT を `test_crud.py` 1 ファイルに集約（500 行 Norman ルールの範囲内）
- `test_alembic_deliverable_template.py` は empire の `test_alembic_empire.py` + workflow の `test_alembic_stage_required_deliverables.py` 同パターン
- `tests/architecture/test_masking_columns.py` + `tests/docs/test_storage_md_back_index.py` は既存ファイルを EDIT で拡張（no-mask テンプレートとして deliverable-template を追加）

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| （N/A） | 該当なし — SQLite + Alembic + SQLAlchemy は標準ライブラリ仕様で固定 | — | masking gateway は不使用のため characterization task なし |

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-DTR-001〜007 すべてに 1 件以上のテストケースがあり、AC#14 / AC#15 が IT カバーされている
- [ ] **§確定 D（schema type 判別）** が TC-IT-DTR-010〜014 で 5 type 全経路を物理確認している
- [ ] **§確定 E（SemVer TEXT）** が TC-IT-DTR-015 で raw SQL カラム値 `"3.14.159"` を物理確認している
- [ ] **§確定 F（acceptance_criteria_json A08 防御）** が TC-IT-DTR-016〜018 で model_validate 経由 + 不正 JSON Fail-Fast の 2 経路を物理確認している
- [ ] **§確定 G（deliverable_template_refs_json A08 防御）** が TC-IT-RPR-010〜011 で同上物理確認している
- [ ] **§確定 H（UNIQUE 制約 IntegrityError）** が TC-IT-RPR-012 で実 SQLite に対し IntegrityError を物理確認している
- [ ] **§確定 I（ORDER BY 規約）** が TC-IT-DTR-005（name ASC）+ TC-IT-RPR-005（role ASC）で物理確認している
- [ ] **§確定 B（Tx 境界）** が TC-IT-DTR-009 + TC-IT-RPR-009 で commit / rollback 両経路を確認し、Repository が明示的 commit/rollback しないことを assert している
- [ ] **§確定 C（domain↔row ラウンドトリップ）** が TC-IT-DTR-019 + TC-IT-RPR-015 で全フィールド構造的等価を確認している
- [ ] **§確定 K（Alembic 0012）** が TC-IT-MIGR-012-001〜005 で upgrade / downgrade / round-trip / chain 一直線を物理確認している
- [ ] **CI 三層防衛 no-mask（§確定 J）** が Layer 1（TC-CI-DTR-001）+ Layer 2（TC-IT-DTR-020）+ Layer 3（TC-DOC-DTR-001）の 3 層すべてに証拠ケースを持っている
- [ ] empire-repository / persistence-foundation の `app_engine` / `session_factory` fixture を再利用し、新 fixture を追加していない
- [ ] FK 先 empire 行を事前 INSERT する前提条件が `test_role_profile_repository/` の全テストケースで明記されている
- [ ] masking 配線テスト（`test_masking.py`）が**存在しない**ことが正しい（本 sub-feature は masking 対象なし。誤って追加した場合は CI 三層防衛 Layer 2 が検出する）
- [ ] §確定 A〜K すべてに証拠ケースが含まれる
