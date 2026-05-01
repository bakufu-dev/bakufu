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
| `definitions.py` | `WELL_KNOWN_TEMPLATES` 12 件全件の不変条件（UUID5 一意性・type=MARKDOWN・version=1.0.0） | UT | TC-UT-TL-001 |
| `definitions.py` | `PRESET_ROLE_TEMPLATE_MAP` 4 Role × DeliverableTemplateRef の整合（各 ref が WELL_KNOWN_TEMPLATES 内の UUID を参照） | UT | TC-UT-TL-002 |
| `TemplateLibrarySeeder` | `seed_global_templates()` 初回起動で 12 件全件が DB に保存される | IT | TC-IT-TL-001 |
| `TemplateLibrarySeeder` | `seed_global_templates()` 2 回実行（再起動模倣）で DB レコード件数が 12 件のまま変わらない（冪等性） | IT | TC-IT-TL-002 |
| `TemplateLibrarySeeder` | `seed_global_templates()` で definitions.py の内容が DB に正確に反映される（name / type / version / schema の全フィールド確認） | IT | TC-IT-TL-003 |
| `TemplateLibrarySeeder` | `seed_role_profiles_for_empire()` 初回呼び出しで 4 件の RoleProfile が保存される | IT | TC-IT-TL-004 |
| `TemplateLibrarySeeder` | `seed_role_profiles_for_empire()` 2 回呼び出しで RoleProfile 件数が増えない（skip 戦略） | IT | TC-IT-TL-005 |
| `TemplateLibrarySeeder` | `seed_role_profiles_for_empire()` で CEO が手動設定した RoleProfile（DEVELOPER）が skip され上書きされない | IT | TC-IT-TL-006 |
| `Bootstrap._stage_3b_seed_template_library()` | Bootstrap.run() で Stage 3b が Stage 3（Alembic）後、Stage 4（pid_gc）前に実行される | IT | TC-IT-TL-007 |
| `TemplateLibrarySeeder` | `seed_global_templates()` で 1 件の UPSERT が失敗した場合、全件ロールバック（all-or-nothing 保証）| IT | TC-IT-TL-008 |

## テストケース詳細

### TC-UT-TL-001: WELL_KNOWN_TEMPLATES 12 件全件の不変条件

| 項目 | 内容 |
|---|---|
| 目的 | definitions.py import 時に全テンプレートが有効な DeliverableTemplate Aggregate として構築できることを確認 |
| 前提条件 | DB 不要（UT） |
| 手順 | `from bakufu.application.services.template_library.definitions import WELL_KNOWN_TEMPLATES` → 件数・各テンプレートの属性を assert |
| 期待結果 | (1) `len(WELL_KNOWN_TEMPLATES) == 12` (2) 各テンプレートの `type == TemplateType.MARKDOWN` (3) 各テンプレートの `version == SemVer(1, 0, 0)` (4) `id` が全件 `UUID5(BAKUFU_TEMPLATE_NS, slug)` と一致 (5) `id` が全 12 件で一意 |
| カバー要件 | §確定 A / §確定 C |

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
| 前提条件 | Bootstrap テスト用 fixture（minimal 設定） |
| 手順 | `Bootstrap.run()` をテストモードで実行 → Stage 実行ログの順序を確認 |
| 期待結果 | ログ順: `...stage 3/8: schema at head...` → `...stage 3b/8: template-library seed complete...` → `...stage 4/8: GC complete...` |
| カバー要件 | REQ-TL-002 |

### TC-IT-TL-008: seed 失敗時の全件ロールバック（all-or-nothing）

| 項目 | 内容 |
|---|---|
| 目的 | UPSERT 途中でエラーが発生した場合に全件ロールバックされ、DB が中途半端な状態にならないことを確認 |
| 前提条件 | 空の DB。`SqliteDeliverableTemplateRepository.save()` を 7 件目でエラーになるようにモック |
| 手順 | `seed_global_templates(session_factory)` を呼ぶ（例外を期待）→ `find_all()` で件数確認 |
| 期待結果 | 例外が raise される。`len(find_all()) == 0`（ロールバックで全件消える）|
| カバー要件 | §確定 E |

## カバレッジ基準

| 対象 | 目標 | 備考 |
|---|---|---|
| `application/services/template_library/seeder.py` | 90% 以上 | TC-IT-TL-001〜008 で主要パスをカバー |
| `application/services/template_library/definitions.py` | 100% | TC-UT-TL-001〜002 で全定数を検証 |
| `infrastructure/bootstrap.py`（Stage 3b 追加部分） | 90% 以上 | TC-IT-TL-007 + 既存 Bootstrap テストで確認 |

## レビュー観点

| # | 観点 | 確認方法 |
|---|------|---------|
| R1 | `WELL_KNOWN_TEMPLATES` の 12 件が全件一意な UUID5 を持つ（衝突なし） | TC-UT-TL-001 |
| R2 | PRESET_ROLE_TEMPLATE_MAP の参照が dangling reference を含まない | TC-UT-TL-002 |
| R3 | 再起動後に DB レコード数が 12 件を超えない（冪等性） | TC-IT-TL-002 |
| R4 | CEO 手動設定 RoleProfile が上書きされない | TC-IT-TL-006 |
| R5 | 部分失敗時に全件ロールバックされる（all-or-nothing） | TC-IT-TL-008 |
