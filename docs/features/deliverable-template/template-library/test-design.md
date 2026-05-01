# テスト設計書

> feature: `deliverable-template` / sub-feature: `template-library`
> 関連: [basic-design.md](basic-design.md) / [detailed-design.md](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md)
>
> **担当**: ヤン・ルカン（テスト担当）— 設計書完成後に詳細を記入すること

## テスト戦略

本 sub-feature のテスト対象は「startup upsert による冪等性」と「RoleProfile プリセット適用の skip 戦略」の 2 軸。DB を使った結合テスト（IT）が主体。UoW 境界・Tx 原子性の検証も必須。

### Vモデル対応

| 設計工程 | テスト工程 |
|--------|---------|
| `TemplateLibrarySeeder` 基本設計（basic-design.md） | IT（結合テスト） |
| `definitions.py` / `TemplateLibrarySeeder` 詳細設計（detailed-design.md） | UT（ユニットテスト） |

### テストマトリクス

| 対象モジュール | テスト観点 | テスト種別 | TC ID |
|---|---|---|---|
| `definitions.py` | `WELL_KNOWN_TEMPLATES` 12 件全件の不変条件（UUID5 一意性・type=MARKDOWN・version=1.0.0・description 非空・schema 非空） | UT | TC-UT-TL-001 |
| `definitions.py` | `PRESET_ROLE_TEMPLATE_MAP` 4 Role × DeliverableTemplateRef の整合（各 ref が WELL_KNOWN_TEMPLATES 内の UUID を参照） | UT | TC-UT-TL-002 |
| `TemplateLibrarySeeder` | `seed_global_templates()` 初回起動で 12 件全件が DB に保存される | IT | TC-IT-TL-001 |
| `TemplateLibrarySeeder` | `seed_global_templates()` 2 回実行（再起動模倣）で DB レコード件数が 12 件のまま変わらない（冪等性） | IT | TC-IT-TL-002 |
| `TemplateLibrarySeeder` | `seed_global_templates()` で definitions.py の内容が DB に正確に反映される（name / type / version / schema の全フィールド確認） | IT | TC-IT-TL-003 |
| `TemplateLibrarySeeder` | `seed_role_profiles_for_empire()` 初回呼び出しで 4 件の RoleProfile が保存される | IT | TC-IT-TL-004 |
| `TemplateLibrarySeeder` | `seed_role_profiles_for_empire()` 2 回呼び出しで RoleProfile 件数が増えない（skip 戦略） | IT | TC-IT-TL-005 |
| `TemplateLibrarySeeder` | `seed_role_profiles_for_empire()` で CEO が手動設定した RoleProfile（DEVELOPER）が skip され上書きされない | IT | TC-IT-TL-006 |
| `Bootstrap._stage_3b_seed_template_library()` | Bootstrap.run() で Stage 3b が Stage 3（Alembic）後、Stage 4（pid_gc）前に実行される | IT | TC-IT-TL-007 |
| `TemplateLibrarySeeder` | `seed_global_templates()` で 1 件の UPSERT が失敗した場合、全件ロールバック（all-or-nothing 保証）・`SQLAlchemyError` が呼び出し元に伝播する | IT | TC-IT-TL-008 |
| `TemplateLibrarySeeder` | `seed_global_templates()` で手動編集済みテンプレートが再 seed 後に definitions.py 定義で上書きされる（§確定 D）| IT | TC-IT-TL-009 |

## テストケース詳細

### TC-UT-TL-001: WELL_KNOWN_TEMPLATES 12 件全件の不変条件

| 項目 | 内容 |
|---|---|
| 目的 | definitions.py import 時に全テンプレートが有効な DeliverableTemplate Aggregate として構築できることを確認 |
| 前提条件 | DB 不要（UT） |
| 手順 | `from bakufu.application.services.template_library.definitions import WELL_KNOWN_TEMPLATES, BAKUFU_TEMPLATE_NS` → 件数・各テンプレートの属性を assert |
| 期待結果 | (1) `len(WELL_KNOWN_TEMPLATES) == 12` (2) 各テンプレートの `type == TemplateType.MARKDOWN` (3) 各テンプレートの `version == SemVer(1, 0, 0)` (4) `id` が全件 `UUID5(BAKUFU_TEMPLATE_NS, slug)` と一致 (5) `id` が全 12 件で一意 (6) 各テンプレートの `description` が非空文字列 (7) 各テンプレートの `schema` が非空文字列（MARKDOWN ガイドライン文字列）|
| カバー要件 | §確定 A / §確定 C / §確定 G |

### TC-UT-TL-002: PRESET_ROLE_TEMPLATE_MAP の整合

| 項目 | 内容 |
|---|---|
| 目的 | `PRESET_ROLE_TEMPLATE_MAP` の各 DeliverableTemplateRef が `WELL_KNOWN_TEMPLATES` 内の実在 UUID を参照していることを確認（dangling reference なし）|
| 前提条件 | DB 不要（UT） |
| 手順 | `PRESET_ROLE_TEMPLATE_MAP` の全 `DeliverableTemplateRef.template_id` が `WELL_KNOWN_TEMPLATES` の `id` セットに含まれることを assert |
| 期待結果 | 全参照が実在 UUID。孤立参照（dangling reference）が 0 件 |
| カバー要件 | §確定 B |

### TC-IT-TL-001: 初回 seed で 12 件保存

| 項目 | 内容 |
|---|---|
| 目的 | `seed_global_templates()` が `deliverable_templates` テーブルに 12 件を正しく INSERT することを確認 |
| 前提条件 | 空の SQLite DB（`deliverable_templates` テーブルにレコードなし）|
| 手順 | `TemplateLibrarySeeder().seed_global_templates(session_factory)` を 1 回実行 → `find_all()` で全件取得 |
| 期待結果 | `len(templates) == 12`。各テンプレートの `id` が `WELL_KNOWN_TEMPLATES` の対応エントリと一致 |
| カバー要件 | REQ-TL-001 / §確定 E |

### TC-IT-TL-002: 冪等性（2 回実行でレコード数変化なし）

| 項目 | 内容 |
|---|---|
| 目的 | `seed_global_templates()` を 2 回実行しても `deliverable_templates` レコード数が 12 件のままであることを確認（UPSERT 冪等性） |
| 前提条件 | 空の SQLite DB |
| 手順 | `seed_global_templates()` を 2 回呼ぶ → `find_all()` で全件取得 |
| 期待結果 | `len(templates) == 12`（重複なし）|
| カバー要件 | REQ-TL-004 / §確定 C |

### TC-IT-TL-003: DB レコードと definitions.py の内容一致

| 項目 | 内容 |
|---|---|
| 目的 | seed 後の DB レコードが `WELL_KNOWN_TEMPLATES` と全フィールドで一致することを確認 |
| 前提条件 | TC-IT-TL-001 実行後の DB |
| 手順 | `find_by_id()` で各テンプレートを取得 → `WELL_KNOWN_TEMPLATES` の対応エントリと `name / description / type / version / schema` を比較 |
| 期待結果 | 全フィールドが structurally equal（`==`）。`acceptance_criteria` は `()` |
| カバー要件 | §確定 D |

### TC-IT-TL-004: 初回 Empire RoleProfile 適用（4 件保存）

| 項目 | 内容 |
|---|---|
| 目的 | `seed_role_profiles_for_empire(empire_id, session_factory)` が 4 件の RoleProfile を保存することを確認 |
| 前提条件 | Empire 作成済み（empire_id 取得）。`role_profiles` にレコードなし |
| 手順 | `seed_role_profiles_for_empire(empire_id, session_factory)` → `find_all_by_empire(empire_id)` で全件取得 |
| 期待結果 | `len(role_profiles) == 4`。LEADER / DEVELOPER / TESTER / REVIEWER の 4 Role が揃っている |
| カバー要件 | REQ-TL-003 |

### TC-IT-TL-005: RoleProfile skip 冪等性（2 回呼び出し）

| 項目 | 内容 |
|---|---|
| 目的 | `seed_role_profiles_for_empire()` を 2 回呼んでも RoleProfile 件数が増えないことを確認 |
| 前提条件 | TC-IT-TL-004 実行後の DB（4 件存在）|
| 手順 | `seed_role_profiles_for_empire(empire_id, session_factory)` を再度呼ぶ → `find_all_by_empire()` |
| 期待結果 | `len(role_profiles) == 4`（重複なし）|
| カバー要件 | REQ-TL-003 §確定 F |

### TC-IT-TL-006: CEO 手動設定 RoleProfile は上書きされない

| 項目 | 内容 |
|---|---|
| 目的 | CEO が DEVELOPER の RoleProfile を手動設定済みの場合、`seed_role_profiles_for_empire()` がそれを上書きしないことを確認 |
| 前提条件 | DEVELOPER Role の RoleProfile を手動で保存（`deliverable_template_refs` が PRESET と異なる内容）|
| 手順 | `seed_role_profiles_for_empire(empire_id, session_factory)` → DEVELOPER の `find_by_empire_and_role()` |
| 期待結果 | DEVELOPER RoleProfile の `deliverable_template_refs` が手動設定値のまま（プリセット値に上書きされていない）|
| カバー要件 | §確定 F |

### TC-IT-TL-007: Bootstrap Stage 3b の実行順序

| 項目 | 内容 |
|---|---|
| 目的 | Bootstrap の Stage 3（Alembic）完了後、Stage 4（pid_gc）前に seed が実行されることを確認 |
| 前提条件 | 既存 Bootstrap テストで使用している in-memory SQLite + `async_sessionmaker` fixture を流用。`TemplateLibrarySeeder.seed_global_templates` を `AsyncMock` でスタブ化（実際の DB 書き込みは本 TC の関心外） |
| 手順 | `Bootstrap.run()` を実行し、`_stage_3_migrate` / `_stage_3b_seed_template_library` / `_stage_4_pid_gc` の呼び出し順を `unittest.mock.patch` + `call_args_list` または caplog で確認する |
| 期待結果 | (1) `_stage_3b_seed_template_library` が `_stage_3_migrate` の完了後に呼ばれる (2) `_stage_3b_seed_template_library` が `_stage_4_pid_gc` の完了前に呼ばれる (3) Bootstrap ログに `stage 3b` の文字列が含まれる |
| カバー要件 | REQ-TL-002 |

### TC-IT-TL-008: seed 失敗時の全件ロールバック（all-or-nothing）

| 項目 | 内容 |
|---|---|
| 目的 | UPSERT 途中でエラーが発生した場合に全件ロールバックされ、DB が中途半端な状態にならないことを確認 |
| 前提条件 | 空の in-memory SQLite DB。`SqliteDeliverableTemplateRepository.save` を `patch.object` でラップし、7 件目（任意の中間点）のテンプレートに対する `save()` 呼び出し時に `SQLAlchemyError` を raise する。1〜6 件目は実際に SQL が発行され DB に書き込まれる。モックは `session.execute` の内部呼び出し回数ではなく `repository.save()` の呼び出し回数でエラー発火を制御すること（実装内部の SQL 発行数の変化に影響されない形式）|
| 手順 | `TemplateLibrarySeeder().seed_global_templates(session_factory)` を呼ぶ（例外を期待）→ 別セッションで `find_all()` を実行して件数確認 |
| 期待結果 | (1) `SQLAlchemyError` が呼び出し元に伝播する（`BakufuConfigError` ラップは Bootstrap レイヤーの責務のため、`TemplateLibrarySeeder` 直呼びでは生の `SQLAlchemyError` を期待する）(2) 別セッションの `find_all()` で `len(templates) == 0`（Tx ロールバックにより 1〜6 件目の書き込みも全件消える）|
| カバー要件 | §確定 E |

### TC-IT-TL-009: §確定 D — 再 seed で手動編集内容が上書きされる

| 項目 | 内容 |
|---|---|
| 目的 | CEO が well-known テンプレートを直接編集した後、再 seed（再起動）すると definitions.py 定義で上書きされることを物理確認する（§確定 D の核心：バージョンアップ時 DB 同期） |
| 前提条件 | `seed_global_templates()` を 1 回実行済み（12 件保存済み DB）|
| 手順 | (1) `find_by_id(WELL_KNOWN_TEMPLATES[0].id)` で取得 → `name` / `schema` を手動で書き換えて `save()`（DB 直接編集） (2) `seed_global_templates(session_factory)` を再度呼ぶ (3) `find_by_id(WELL_KNOWN_TEMPLATES[0].id)` で再取得 |
| 期待結果 | 再取得したテンプレートの `name` / `schema` が `WELL_KNOWN_TEMPLATES[0]` の定義値に戻っている（手動編集が上書きされる）|
| カバー要件 | §確定 D |

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | テスト方法 | 備考 |
|---------|------|----------|------|
| **SQLite DB** (`sqlalchemy.ext.asyncio.AsyncSession`) | `TemplateLibrarySeeder.seed_global_templates` / `seed_role_profiles_for_empire` | テスト用 in-memory SQLite（`:memory:`）実接続。pytest の `session`-scoped fixture でスキーマ作成済み DB を提供 | raw fixture 不要 |
| **Bootstrap** (既存 `_stage_3_migrate`, `_stage_4_pid_gc`) | TC-IT-TL-007 の実行順序確認 | `AsyncMock` でスタブ化 | Bootstrap 実体（Alembic 等）は本 TC の関心外 |

characterization fixture（raw / schema）は不要：外部 SaaS API を呼ばず、in-memory SQLite 実接続で完結する。

## カバレッジ基準

| 対象 | 目標 | カバーする TC |
|---|---|---|
| `application/services/template_library/seeder.py` | 90% 以上 | TC-IT-TL-001〜009 で主要パスをカバー |
| `application/services/template_library/definitions.py` | 100% | TC-UT-TL-001〜002 で全定数（UUID5・type・version・description・schema・dangling ref）を検証 |
| `infrastructure/bootstrap.py`（Stage 3b 追加部分） | 90% 以上 | TC-IT-TL-007 + 既存 Bootstrap テストで確認 |

**トレーサビリティ充足確認**:

| §確定 | カバー TC |
|---|---|
| §確定 A（12 件定義）| TC-UT-TL-001, TC-IT-TL-001, TC-IT-TL-003 |
| §確定 B（PRESET_ROLE_TEMPLATE_MAP 4 Role 定義）| TC-UT-TL-002, TC-IT-TL-004 |
| §確定 C（固定 UUID5 名前空間）| TC-UT-TL-001 |
| §確定 D（UPSERT は definitions.py 定義で上書き）| **TC-IT-TL-009** |
| §確定 E（all-or-nothing Tx）| TC-IT-TL-008 |
| §確定 F（skip 戦略）| TC-IT-TL-005, TC-IT-TL-006 |
| §確定 G（全件 MARKDOWN）| TC-UT-TL-001 |
| §確定 H（Bootstrap のみが呼ぶ）| 設計制約（実行時制約なし）— テスト不要 |
| REQ-TL-001 | TC-IT-TL-001 |
| REQ-TL-002 | TC-IT-TL-007 |
| REQ-TL-003 | TC-IT-TL-004, TC-IT-TL-005, TC-IT-TL-006 |
| REQ-TL-004 | TC-IT-TL-002 |

## レビュー観点

| # | 観点 | 確認方法 |
|---|------|---------|
| R1 | `WELL_KNOWN_TEMPLATES` の 12 件が全件一意な UUID5 を持つ（衝突なし）| TC-UT-TL-001 |
| R2 | PRESET_ROLE_TEMPLATE_MAP の参照が dangling reference を含まない | TC-UT-TL-002 |
| R3 | 再起動後に DB レコード数が 12 件を超えない（冪等性） | TC-IT-TL-002 |
| R4 | CEO 手動設定 RoleProfile が上書きされない | TC-IT-TL-006 |
| R5 | 部分失敗時に全件ロールバックされる（all-or-nothing） | TC-IT-TL-008 |
| R6 | 手動編集済みテンプレートが再 seed で definitions.py 定義に戻る（§確定 D）| TC-IT-TL-009 |
| R7 | description / schema が全 12 件で非空（§確定 A / §確定 G）| TC-UT-TL-001 |
