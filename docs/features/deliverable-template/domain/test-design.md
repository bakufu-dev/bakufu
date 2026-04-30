# テスト設計書 — deliverable-template / domain

<!-- feature: deliverable-template / sub-feature: domain -->
<!-- 配置先: docs/features/deliverable-template/domain/test-design.md -->
<!-- 対象範囲: REQ-DT-001〜006 / MSG-DT-001〜005 / 親 spec §9 受入基準 / 詳細設計 §確定 A〜E / 5 不変条件 + RoleProfile 1 不変条件 + VO 3 種 -->

本 sub-feature は domain 層の Aggregate Root（`DeliverableTemplate` / `RoleProfile`）+ VO（`SemVer` / `DeliverableTemplateRef` / `AcceptanceCriterion`）+ enum（`TemplateType`）+ 例外（`DeliverableTemplateInvariantViolation` / `RoleProfileInvariantViolation`）+ Port インターフェース（`AbstractJSONSchemaValidator`）に閉じる。HTTP API / repository は持たないため、E2E は親 [`../system-test-design.md`](../system-test-design.md) が管理する。本 sub-feature のテストは **ユニット主体 + Aggregate 内 module 連携 + 不変条件全種網羅 + MSG 2 行構造物理保証** で構成する。

外部 I/O ゼロ。factory に `_meta.synthetic = True` の `WeakValueDictionary` レジストリ（external-review-gate domain 同パターン）。**最初から 6 ファイル分割**（500 行ルール、task PR #42 / external-review-gate PR 教訓継承）。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 親 spec 受入基準 |
|--------|-------------------|---------------|------------|------|----------------|
| REQ-DT-001（DeliverableTemplate 構築） | `DeliverableTemplate.__init__` / `model_validator(mode='after')` | TC-UT-DT-001〜007 | ユニット | 正常系 / 異常系 | AC#1 |
| REQ-DT-001（TemplateType 5 値全種） | `TemplateType` StrEnum | TC-UT-DT-001〜005 | ユニット | 正常系 | AC#1, 2 |
| REQ-DT-001（frozen / extra='forbid'） | `model_config` | TC-UT-DT-006, TC-UT-DT-007 | ユニット | 異常系 | 内部品質基準 |
| REQ-DT-001（型違反） | Pydantic 型バリデーション | TC-UT-DT-017 | ユニット | 異常系 | AC#2 |
| REQ-DT-002（create_new_version） | `DeliverableTemplate.create_new_version` | TC-UT-DT-018〜022 | ユニット | 正常系 / 異常系 | AC#3 |
| REQ-DT-003（compose） | `DeliverableTemplate.compose` | TC-UT-DT-023〜025 | ユニット | 正常系 / 異常系 | AC#4 |
| REQ-DT-004（RoleProfile 構築） | `RoleProfile.__init__` / `model_validator(mode='after')` | TC-UT-RP-001〜005 | ユニット | 正常系 / 異常系 | AC#5 |
| REQ-DT-005（add_template_ref） | `RoleProfile.add_template_ref` | TC-UT-RP-006, TC-UT-RP-007 | ユニット | 正常系 / 異常系 | AC#6 |
| REQ-DT-005（remove_template_ref） | `RoleProfile.remove_template_ref` | TC-UT-RP-008, TC-UT-RP-009 | ユニット | 正常系 / 異常系 | AC#7 |
| REQ-DT-005（get_all_acceptance_criteria） | `RoleProfile.get_all_acceptance_criteria` | TC-UT-RP-010〜012 | ユニット | 正常系 | AC#5, 6 |
| REQ-DT-006（_validate_schema_format） | `_validate_schema_format` | TC-UT-DT-008〜011 | ユニット | 正常系 / 異常系 | AC#2 |
| REQ-DT-006（_validate_composition_no_self_ref） | `_validate_composition_no_self_ref` | TC-UT-DT-012〜014 | ユニット | 正常系 / 異常系 | AC#4 |
| REQ-DT-006（_validate_version_non_negative） | `_validate_version_non_negative` | TC-UT-DT-015 | ユニット | 異常系 | AC#2 |
| REQ-DT-006（_validate_acceptance_criteria_non_empty_descriptions） | `_validate_acceptance_criteria_non_empty_descriptions` | TC-UT-DT-016, TC-UT-DT-017 | ユニット | 正常系 / 異常系 | AC#2 |
| REQ-DT-006（_validate_acceptance_criteria_no_duplicate_ids） | `_validate_acceptance_criteria_no_duplicate_ids` | TC-UT-DT-016c | ユニット | 異常系 | AC#2 |
| REQ-DT-006（_validate_no_duplicate_refs） | `_validate_no_duplicate_refs` | TC-UT-RP-003 | ユニット | 異常系 | AC#5 |
| §確定A09（detail フィールドホワイトリスト） | `DeliverableTemplateInvariantViolation.detail` / `RoleProfileInvariantViolation.detail` | TC-UT-A09-001〜003 | ユニット | 異常系 | A09 |
| 確定 A（pre-validate 方式） | 失敗時の元インスタンス不変 | TC-UT-DT-022, TC-UT-RP-014 | ユニット | 異常系 | — |
| 確定 B（compose は acceptance_criteria 引き継がない） | `DeliverableTemplate.compose` | TC-UT-DT-025 | ユニット | 正常系 | — |
| 確定 C（Validation Port パターン） | `AbstractJSONSchemaValidator` DI 可能 | TC-UT-DT-011, TC-IT-DT-005 | ユニット / 結合 | 正常系 | — |
| 確定 D（RoleProfile 一意性は application 層責務） | `RoleProfile` が empire-scope 一意性を強制しないこと | TC-UT-RP-013 | ユニット | 正常系 | — |
| 確定 E（get_all_acceptance_criteria は RoleProfile 自身のメソッド） | `RoleProfile.get_all_acceptance_criteria` | TC-UT-RP-010〜012 | ユニット | 正常系 | — |
| `SemVer` VO | `SemVer` 全メソッド | TC-UT-SV-001〜009 | ユニット | 正常系 / 異常系 | AC#2, 3 |
| `DeliverableTemplateRef` VO | `DeliverableTemplateRef` 構築・frozen | TC-UT-DRef-001, TC-UT-DRef-002 | ユニット | 正常系 / 異常系 | — |
| `AcceptanceCriterion` VO | `AcceptanceCriterion` 構築・制約・frozen | TC-UT-AC-001〜005 | ユニット | 正常系 / 異常系 | AC#2 |
| MSG-DT-001〜005（Next: hint 物理保証） | 全 5 MSG で `assert "Next:" in str(exc)` | TC-UT-MSG-001〜005 | ユニット | 異常系 | AC#12（room §確定 I 踏襲）|
| 結合シナリオ 1（DT lifecycle） | 構築 → compose → create_new_version | TC-IT-DT-001 | 結合 | 正常系 | AC#1, 3, 4 |
| 結合シナリオ 2（RP lifecycle） | 構築 → add × 2 → remove → get_all_acceptance_criteria | TC-IT-DT-002 | 結合 | 正常系 | AC#5, 6, 7 |
| 結合シナリオ 3（union / dedup / ordering） | 複数テンプレート、重複 AcceptanceCriterion あり | TC-IT-DT-003 | 結合 | 正常系 | AC#5 |
| 結合シナリオ 4（pre-validate 安全性） | 中間失敗でも状態不変 | TC-IT-DT-004 | 結合 | 異常系 | — |
| 結合シナリオ 5（§確定 C stub 経由 E2E） | DI stub validator + 構築チェーン完走 | TC-IT-DT-005 | 結合 | 正常系 | — |

**マトリクス充足の証拠**:

- REQ-DT-001〜006 すべてに最低 1 件のテストケース
- **TemplateType 5 値全種**（MARKDOWN / JSON_SCHEMA / OPENAPI / CODE_SKELETON / PROMPT）が TC-UT-DT-001〜005 で正常構築を網羅
- **5 不変条件 helper 全種**（schema_format / composition_self_ref / version_non_negative / acceptance_criteria_empty_description / acceptance_criteria_no_duplicate_ids）が独立 unit ケースで網羅
- **RoleProfile 不変条件**（_validate_no_duplicate_refs）が TC-UT-RP-003 で網羅
- **§確定A09 detail ホワイトリスト**: TC-UT-A09-001〜003 で例外 detail フィールドにsecret/description本文が混入しないことを物理確認
- **§確定 A pre-validate**: TC-UT-DT-022 / TC-UT-RP-014 で失敗時の元インスタンス不変を物理確認
- **§確定 B compose の acceptance_criteria 非継承**: TC-UT-DT-025 で物理確認
- **§確定 C Validation Port**: TC-UT-DT-011 + TC-IT-DT-005 でスタブ DI 可能性を物理確認
- **§確定 D application 層責務**: TC-UT-RP-013 で domain 層が empire-scope 一意性を強制しないことを物理確認
- **§確定 E RoleProfile 自身のメソッド**: TC-UT-RP-010〜012 で呼び元が lookup を渡すだけで動作確認
- **MSG 2 行構造 + Next: hint**: TC-UT-MSG-001〜005 で全 5 MSG-DT で `assert "Next:" in str(exc)` を CI 強制
- 確定 A〜E すべてに証拠ケース、孤児要件ゼロ
- frozen / extra='forbid' / 型違反が独立検証

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **該当なし** | `DeliverableTemplate` / `RoleProfile` は domain 層単独で外部 I/O を持たない（HTTP / DB / ファイル / 時刻 / LLM いずれも未依存）| — | — | **不要（外部 I/O ゼロ）** |
| `unicodedata.normalize('NFC', ...)` | name の NFC 正規化 | — | — | 不要（CPython 標準ライブラリ仕様、external-review-gate 同方針）|
| `AbstractJSONSchemaValidator`（Port インターフェース）| JSON Schema バリデーション（§確定 C）| — | `StubJSONSchemaValidatorFactory`（テスト用スタブ）| 不要（Port への DI で差し替え可能）|

`_meta.synthetic = True` は external-review-gate domain 同パターン（`WeakValueDictionary[int, BaseModel]` レジストリ + `id(instance)` をキーに `is_synthetic()` 判定）。

**factory（合成データ）**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `DeliverableTemplateFactory` | `DeliverableTemplate`（valid デフォルト: `type=MARKDOWN`, `schema=''`, `acceptance_criteria=()`, `version=SemVer(1,0,0)`, `composition=()`) | `True` |
| `RoleProfileFactory` | `RoleProfile`（valid デフォルト: `role=Role.DEVELOPER`, `deliverable_template_refs=()`) | `True` |
| `SemVerFactory` | `SemVer`（valid デフォルト: `major=1, minor=0, patch=0`) | `True` |
| `AcceptanceCriterionFactory` | `AcceptanceCriterion`（valid デフォルト: `description='満たすべき条件'`, `required=True`) | `True` |
| `DeliverableTemplateRefFactory` | `DeliverableTemplateRef`（valid デフォルト: ランダム `template_id`, `minimum_version=SemVer(1,0,0)`) | `True` |
| `StubJSONSchemaValidatorFactory` | `AbstractJSONSchemaValidator` テスト用スタブ（valid: 何も raise しない / invalid: 任意例外を raise する）| `True` |

## 結合テストケース

domain 層単独の本 feature では「結合」を **Aggregate 内 module 連携 + lifecycle 完走シナリオ** と定義。外部 I/O ゼロ。

| テストID | 対象モジュール連携 | 使用 factory | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-DT-001 | DT lifecycle 完走（構築 → compose → create_new_version） | DeliverableTemplateFactory + DeliverableTemplateRefFactory | `version=SemVer(1,0,0)`, `composition=()` の DeliverableTemplate | 1) `compose(refs=[ref_a, ref_b])` → composition が [ref_a, ref_b] に更新、acceptance_criteria は空のまま（§確定 B）→ 2) `create_new_version(SemVer(1,1,0))` → 新インスタンス、version=1.1.0、composition 引き継ぎ → 3) 元インスタンスの version が 1.0.0 のまま不変（§確定 A） | 3 段階 lifecycle 完走、各ステップで新インスタンス返却、元インスタンス不変 |
| TC-IT-DT-002 | RP lifecycle 完走（構築 → add × 2 → remove → get_all_acceptance_criteria） | RoleProfileFactory + DeliverableTemplateRefFactory + DeliverableTemplateFactory | `deliverable_template_refs=()` の RoleProfile | 1) `add_template_ref(ref_a)` → refs=[ref_a] の新 RP → 2) `add_template_ref(ref_b)` → refs=[ref_a, ref_b] の新 RP → 3) `remove_template_ref(ref_a.template_id)` → refs=[ref_b] の新 RP → 4) `get_all_acceptance_criteria(lookup={ref_b.template_id: tmpl_b})` → tmpl_b の acceptance_criteria を返す | 4 段階 lifecycle 完走、最終 refs=[ref_b]、criteria に tmpl_b の内容 |
| TC-IT-DT-003 | get_all_acceptance_criteria — union / dedup / ordering | RoleProfileFactory + DeliverableTemplateFactory + AcceptanceCriterionFactory | RoleProfile with refs=[ref_a, ref_b, ref_c]。tmpl_a.acceptance_criteria=[criterion_x(required=True), criterion_y(required=False)]。tmpl_b.acceptance_criteria=[criterion_x(required=True)]（criterion_x は同一 id で重複）。tmpl_c.acceptance_criteria=[criterion_z(required=True)] | `get_all_acceptance_criteria(lookup)` 呼び出し | required=True グループ: [criterion_x, criterion_z]（重複排除済み criterion_x は 1 件のみ） + required=False グループ: [criterion_y]。合計 3 件、走査順保持 |
| TC-IT-DT-004 | pre-validate 安全性（§確定 A） | DeliverableTemplateFactory + RoleProfileFactory | valid な DT と RP | DT: `compose` に自己参照 ref を渡して失敗後、元 DT の composition が不変。RP: `add_template_ref` で重複 ref を渡して失敗後、元 RP の deliverable_template_refs が不変 | 失敗後も全属性が完全に変化なし |
| TC-IT-DT-005 | §確定 C — DI stub validator + 構築チェーン完走 | StubJSONSchemaValidatorFactory + DeliverableTemplateFactory | valid スタブ（raise しない）と invalid スタブ（例外を raise）を用意 | 1) valid スタブを DI して `type=JSON_SCHEMA`, valid dict schema で構築 → 成功 → 2) invalid スタブを DI して同一入力で構築 → `DeliverableTemplateInvariantViolation(kind='schema_format_invalid')` | スタブ差し替えで動作が切り替わる。domain 層が concrete validator に依存していない |

## ユニットテストケース

`tests/factories/deliverable_template.py` / `tests/factories/template_vos.py` の factory 経由で入力を生成。

### DeliverableTemplate 構築（test_deliverable_template/test_construction.py、受入基準 AC#1, AC#2）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-DT-001 | `type=MARKDOWN`, `schema=str` | 正常系 | `type=MARKDOWN, schema='# テンプレート'` | 構築成功、frozen インスタンス、acceptance_criteria=() |
| TC-UT-DT-002 | `type=JSON_SCHEMA`, `schema=dict`（有効）| 正常系 | `type=JSON_SCHEMA, schema={"type": "object"}` | 構築成功 |
| TC-UT-DT-003 | `type=OPENAPI`, `schema=dict`（有効）| 正常系 | `type=OPENAPI, schema={"openapi": "3.0.0"}` | 構築成功 |
| TC-UT-DT-004 | `type=CODE_SKELETON`, `schema=str` | 正常系 | `type=CODE_SKELETON, schema='def main(): ...'` | 構築成功 |
| TC-UT-DT-005 | `type=PROMPT`, `schema=str` | 正常系 | `type=PROMPT, schema='あなたは…'` | 構築成功 |
| TC-UT-DT-006 | frozen 不変性 | 異常系 | `template.name = '変更'` 直接代入 | `pydantic.ValidationError`（frozen instance への代入拒否）|
| TC-UT-DT-007 | `extra='forbid'` | 異常系 | `DeliverableTemplate.model_validate({...,'unknown': 'x'})` | `pydantic.ValidationError`（extra 違反）|
| TC-UT-DT-017 | 型違反（§確定 I 相当） | 異常系 | `version='not-semver-type'` / `type='UNKNOWN_TYPE'` / `id='not-uuid'` | 各々で `pydantic.ValidationError` |

### DeliverableTemplate 不変条件（test_deliverable_template/test_invariants.py、受入基準 AC#2, AC#4）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-DT-008 | `_validate_schema_format` — JSON_SCHEMA + str（非 dict）| 異常系 | `type=JSON_SCHEMA, schema='not a dict'` | `DeliverableTemplateInvariantViolation(kind='schema_format_invalid')` + MSG-DT-001 |
| TC-UT-DT-009 | `_validate_schema_format` — JSON_SCHEMA + 無効 dict | 異常系 | `type=JSON_SCHEMA, schema={"invalid": True}` + invalid スタブ DI | `DeliverableTemplateInvariantViolation(kind='schema_format_invalid')` + MSG-DT-001 |
| TC-UT-DT-010 | `_validate_schema_format` — MARKDOWN + dict（str 期待違反）| 異常系 | `type=MARKDOWN, schema={"key": "value"}` | `DeliverableTemplateInvariantViolation(kind='schema_format_invalid')` + MSG-DT-001 |
| TC-UT-DT-011 | `_validate_schema_format` — §確定 C: AbstractJSONSchemaValidator DI 可能 | 正常系 | valid スタブを DI、`type=JSON_SCHEMA, schema={"type":"object"}` | 構築成功。スタブが呼ばれたことを verify |
| TC-UT-DT-012 | `_validate_composition_no_self_ref` — 自己 ID を含む composition | 異常系 | composition に `self.id` と同一 template_id を持つ ref を含む | `DeliverableTemplateInvariantViolation(kind='composition_self_ref')` + MSG-DT-002 |
| TC-UT-DT-013 | `_validate_composition_no_self_ref` — 空 tuple | 正常系 | `composition=()` | 構築成功 |
| TC-UT-DT-014 | `_validate_composition_no_self_ref` — 他テンプレートへの ref（非自己）| 正常系 | composition に別 template_id の ref のみ含む | 構築成功 |
| TC-UT-DT-015 | `_validate_version_non_negative` — 負の major | 異常系 | `SemVer(major=-1, minor=0, patch=0)` | `pydantic.ValidationError`（SemVer の `ge=0` 制約）または `DeliverableTemplateInvariantViolation(kind='version_non_negative')`（多層防御）|
| TC-UT-DT-016 | `_validate_acceptance_criteria_non_empty_descriptions` — 空 description | 異常系 | `acceptance_criteria=[AcceptanceCriterion(description='', required=True)]` | `DeliverableTemplateInvariantViolation(kind='acceptance_criteria_empty_description')` |
| TC-UT-DT-016b | `_validate_acceptance_criteria_non_empty_descriptions` — 空 tuple | 正常系 | `acceptance_criteria=()` | 構築成功（0 件は許容）|
| TC-UT-DT-016c | `_validate_acceptance_criteria_no_duplicate_ids` — 同一 id を持つ 2 件 | 異常系 | `acceptance_criteria=(AcceptanceCriterion(id=uuid_x, ...), AcceptanceCriterion(id=uuid_x, ...))` | `DeliverableTemplateInvariantViolation(kind='acceptance_criteria_duplicate_id')` |

### DeliverableTemplate ふるまい（test_deliverable_template/test_behaviors.py、受入基準 AC#3, AC#4）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-DT-018 | `create_new_version` — new_version > current（patch bump）| 正常系 | `current=1.2.3`, `new_version=SemVer(1,2,4)` | 新インスタンス、`version=1.2.4`。`name` / `description` / `composition` 等の他属性は引き継ぎ |
| TC-UT-DT-019 | `create_new_version` — new_version > current（major bump）| 正常系 | `current=1.5.3`, `new_version=SemVer(2,0,0)` | 新インスタンス、`version=2.0.0`。他属性は引き継ぎ |
| TC-UT-DT-020 | `create_new_version` — new_version == current | 異常系 | `current=1.2.3`, `new_version=SemVer(1,2,3)` | `DeliverableTemplateInvariantViolation(kind='version_not_greater')` + MSG-DT-003 |
| TC-UT-DT-021 | `create_new_version` — new_version < current | 異常系 | `current=1.2.3`, `new_version=SemVer(1,2,2)` | `DeliverableTemplateInvariantViolation(kind='version_not_greater')` + MSG-DT-003 |
| TC-UT-DT-022 | `create_new_version` — pre-validate: 失敗時の元インスタンス不変（§確定 A） | 異常系 | `current=1.0.0`, `new_version=SemVer(0,9,0)` で失敗後、元インスタンスの全属性を検査 | 失敗後も元インスタンスの `version` / `name` / 他全属性が完全に変化なし |
| TC-UT-DT-023 | `compose` — 正常系（非自己参照 refs） | 正常系 | refs=[ref_a, ref_b]（自己参照なし）| 新インスタンス、`composition=(ref_a, ref_b)` |
| TC-UT-DT-024 | `compose` — 自己参照 refs | 異常系 | refs に `self.id` と同一 template_id の ref を含む | `DeliverableTemplateInvariantViolation(kind='composition_self_ref')` + MSG-DT-002 |
| TC-UT-DT-025 | `compose` — §確定 B: acceptance_criteria は引き継がない | 正常系 | 元 DT の `acceptance_criteria` が非空。`compose(refs)` を呼ぶ | 新インスタンスの `acceptance_criteria` が**空 tuple**（元の criteria を引き継がない） |

### RoleProfile 構築（test_role_profile/test_construction.py、受入基準 AC#5）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-RP-001 | `RoleProfile(...)` — 空 refs | 正常系 | `deliverable_template_refs=()` | 構築成功 |
| TC-UT-RP-002 | `RoleProfile(...)` — 重複なし refs | 正常系 | `deliverable_template_refs=(ref_a, ref_b)` | 構築成功 |
| TC-UT-RP-003 | `_validate_no_duplicate_refs` — 同一 template_id を 2 件 | 異常系 | `deliverable_template_refs=(ref_a, ref_a_dup)`（同一 template_id）| `RoleProfileInvariantViolation(kind='duplicate_template_ref')` + MSG-DT-004 |
| TC-UT-RP-004 | frozen 不変性 | 異常系 | `profile.role = Role.LEADER` 直接代入 | `pydantic.ValidationError`（frozen 拒否）|
| TC-UT-RP-005 | `extra='forbid'` | 異常系 | `RoleProfile.model_validate({...,'unknown': 'x'})` | `pydantic.ValidationError`（extra 違反）|

### RoleProfile ふるまい（test_role_profile/test_behaviors.py、受入基準 AC#6, AC#7）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-RP-006 | `add_template_ref` — 新規 ref | 正常系 | RoleProfile with refs=() + ref_a を追加 | 新 RP で `deliverable_template_refs=(ref_a,)`（末尾追加） |
| TC-UT-RP-007 | `add_template_ref` — 既存 template_id の重複 | 異常系 | RoleProfile with refs=(ref_a,) + ref_a_dup（同一 template_id）を追加 | `RoleProfileInvariantViolation(kind='duplicate_template_ref')` + MSG-DT-004 |
| TC-UT-RP-008 | `remove_template_ref` — 存在する template_id を削除 | 正常系 | RoleProfile with refs=(ref_a, ref_b) + `ref_a.template_id` を削除 | 新 RP で `deliverable_template_refs=(ref_b,)` |
| TC-UT-RP-009 | `remove_template_ref` — 存在しない template_id | 異常系 | RoleProfile with refs=() + ランダム template_id を削除 | `RoleProfileInvariantViolation(kind='template_ref_not_found')` + MSG-DT-005 |
| TC-UT-RP-010 | `get_all_acceptance_criteria` — required=True 先頭ソート | 正常系 | tmpl_a=[criterion_required=True, criterion_optional=False], lookup に tmpl_a のみ | 返却リスト: [required, optional] の順 |
| TC-UT-RP-011 | `get_all_acceptance_criteria` — 同一 id による重複排除 | 正常系 | ref_a, ref_b 両方のテンプレートが同一 `AcceptanceCriterion.id` を持つ | 重複排除済みリスト（最初に出現した 1 件のみ保持） |
| TC-UT-RP-012 | `get_all_acceptance_criteria` — required=False のみ | 正常系 | tmpl_a.acceptance_criteria=[criterion(required=False)のみ] | 全件が後続グループとして返却、required=True 先頭グループは空 |
| TC-UT-RP-013 | §確定 D: RoleProfile が empire-scope 一意性を強制しない | 正常系 | 同一 `role=Role.DEVELOPER` で 2 つの RoleProfile を構築（異なる id） | 両方とも構築成功。domain 層は empire-scope 一意性制約を持たない |
| TC-UT-RP-014 | pre-validate — add_template_ref 失敗時の元インスタンス不変（§確定 A） | 異常系 | refs=(ref_a,) の RP で `add_template_ref(ref_a_dup)` 失敗後、元 RP の全属性を検査 | 失敗後も元 RP の `deliverable_template_refs` が完全に変化なし |

### VO: SemVer（test_value_objects/test_semver.py）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-SV-001 | `SemVer` 正常構築 | 正常系 | `SemVer(major=1, minor=2, patch=3)` | 構築成功、各属性が正しく設定 |
| TC-UT-SV-002 | `SemVer` — 負の major（ge=0 制約） | 異常系 | `SemVer(major=-1, minor=0, patch=0)` | `pydantic.ValidationError` |
| TC-UT-SV-003 | `SemVer.from_str` — 正常 | 正常系 | `SemVer.from_str("1.2.3")` | `SemVer(major=1, minor=2, patch=3)` |
| TC-UT-SV-004 | `SemVer.from_str` — 形式不正 | 異常系 | `SemVer.from_str("invalid")` | `ValueError` |
| TC-UT-SV-005 | `SemVer.from_str` — 非負整数違反 | 異常系 | `SemVer.from_str("1.-1.0")` | `ValueError` |
| TC-UT-SV-006 | `SemVer.from_str` — 2 フィールドのみ | 異常系 | `SemVer.from_str("1.2")` | `ValueError`（major.minor.patch の 3 フィールド必須）|
| TC-UT-SV-007 | `SemVer.is_compatible_with` — 同 major | 正常系 | `SemVer(1,0,0).is_compatible_with(SemVer(1,5,3))` | `True` |
| TC-UT-SV-008 | `SemVer.is_compatible_with` — 異なる major | 正常系 | `SemVer(1,0,0).is_compatible_with(SemVer(2,0,0))` | `False` |
| TC-UT-SV-009 | `SemVer.__str__` | 正常系 | `str(SemVer(1, 2, 3))` | `"1.2.3"` |
| TC-UT-SV-010 | `SemVer` frozen | 異常系 | `semver.major = 99` 直接代入 | `pydantic.ValidationError`（frozen 拒否）|
| TC-UT-SV-011 | `SemVer` extra='forbid' | 異常系 | `SemVer.model_validate({..., 'extra': 'x'})` | `pydantic.ValidationError` |
| TC-UT-SV-012 | create_new_version 用 tuple 比較 — boundary | 正常系 | `SemVer(1,0,0)` < `SemVer(1,0,1)` < `SemVer(1,1,0)` < `SemVer(2,0,0)` | 辞書的順序が一致。`(major,minor,patch)` tuple 比較と等価 |

### VO: DeliverableTemplateRef / AcceptanceCriterion（test_value_objects/test_semver.py に同梱）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-DRef-001 | `DeliverableTemplateRef` 正常構築 | 正常系 | `template_id=uuid4()`, `minimum_version=SemVer(1,0,0)` | 構築成功 |
| TC-UT-DRef-002 | `DeliverableTemplateRef` frozen | 異常系 | `ref.template_id = uuid4()` 直接代入 | `pydantic.ValidationError` |
| TC-UT-AC-001 | `AcceptanceCriterion` 正常構築 | 正常系 | `description='正常な受入基準'`, `required=True` | 構築成功 |
| TC-UT-AC-002 | `AcceptanceCriterion` — description 空文字 | 異常系 | `description=''` | `pydantic.ValidationError`（min_length=1 制約）|
| TC-UT-AC-003 | `AcceptanceCriterion` — description 501 文字 | 異常系 | `description='a' * 501` | `pydantic.ValidationError`（max_length=500 制約）|
| TC-UT-AC-004 | `AcceptanceCriterion` — required デフォルト | 正常系 | `required` 未指定 | `required=True`（デフォルト値）|
| TC-UT-AC-005 | `AcceptanceCriterion` frozen | 異常系 | `criterion.required = False` 直接代入 | `pydantic.ValidationError` |

### MSG 確定文言 / Next: hint 物理保証（test_deliverable_template/test_invariants.py に同梱）

| テストID | 対象 MSG | 例外型 | 例外発生条件 | 検証内容 |
|---------|---------|-------|------------|---------|
| TC-UT-MSG-001 | MSG-DT-001（schema_format_invalid）| `DeliverableTemplateInvariantViolation` | `type=JSON_SCHEMA, schema='str'` | `"[FAIL]" in str(exc)` かつ `"Next:" in str(exc)` かつ `"json-schema.org" in str(exc)` |
| TC-UT-MSG-002 | MSG-DT-002（composition_self_ref）| `DeliverableTemplateInvariantViolation` | composition に自己参照 ref | `"[FAIL]" in str(exc)` かつ `"Next:" in str(exc)` かつ `"self-referential" in str(exc)` |
| TC-UT-MSG-003 | MSG-DT-003（version_not_greater）| `DeliverableTemplateInvariantViolation` | `new_version <= current` | `"[FAIL]" in str(exc)` かつ `"Next:" in str(exc)` かつ current version 文字列が含まれる（f-string プレースホルダ充足確認）|
| TC-UT-MSG-004 | MSG-DT-004（duplicate_template_ref）| `RoleProfileInvariantViolation` | 同一 template_id の ref を add | `"[FAIL]" in str(exc)` かつ `"Next:" in str(exc)` かつ template_id 文字列が含まれる |
| TC-UT-MSG-005 | MSG-DT-005（template_ref_not_found）| `RoleProfileInvariantViolation` | 存在しない template_id を remove | `"[FAIL]" in str(exc)` かつ `"Next:" in str(exc)` かつ template_id 文字列が含まれる |

### A09 detail フィールドホワイトリスト（test_deliverable_template/test_invariants.py に同梱、Tabriz §確定A09）

| テストID | 対象例外 | 種別 | 違反シナリオ | 検証内容 |
|---------|---------|------|------------|---------|
| TC-UT-A09-001 | `DeliverableTemplateInvariantViolation(kind='schema_format_invalid')` | 異常系 | `type=JSON_SCHEMA, schema='長い説明文付きの任意テキスト ...'`（description 本文に 50 文字以上含む） | `exc.detail` に schema 本文が含まれない。`exc.detail` に許可フィールド（`schema_type: str`）のみ存在することを assert |
| TC-UT-A09-002 | `DeliverableTemplateInvariantViolation(kind='composition_self_ref')` | 異常系 | 自己参照 ref を composition に含む | `exc.detail` に `name` / `description` 等の任意テキストが含まれない。`template_id` (str 形式の UUID) のみ含まれることを assert |
| TC-UT-A09-003 | `RoleProfileInvariantViolation(kind='duplicate_template_ref')` | 異常系 | 同一 template_id の ref を add | `exc.detail` に任意テキストが含まれない。`template_id` (str 形式の UUID) のみ含まれることを assert |

## E2E テストケース

E2E は親 [`../system-test-design.md`](../system-test-design.md) が管理する。本 sub-feature（domain）は domain 層単独で外部 I/O を持たないため、E2E テストケースは定義しない。

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| 該当なし — E2E は親 system-test-design.md が管理 | — | — | — | — |

## カバレッジ基準

- REQ-DT-001〜006 すべてに最低 1 件のテストケース
- **TemplateType 5 値全種**（MARKDOWN / JSON_SCHEMA / OPENAPI / CODE_SKELETON / PROMPT）が TC-UT-DT-001〜005 で正常構築を網羅
- **5 不変条件 helper 全種**（schema_format / composition_self_ref / version_non_negative / acceptance_criteria_empty_description / acceptance_criteria_no_duplicate_ids）が独立 unit ケースで網羅
- **RoleProfile 不変条件**（_validate_no_duplicate_refs）が TC-UT-RP-003 で網羅
- **§確定A09 detail ホワイトリスト**: TC-UT-A09-001〜003 で例外 detail フィールドにsecret/description本文が混入しないことを物理確認
- **§確定 A pre-validate**: TC-UT-DT-022 / TC-UT-RP-014 で失敗時の元インスタンス不変を物理確認
- **§確定 B compose の acceptance_criteria 非継承**: TC-UT-DT-025 で物理確認
- **§確定 C Validation Port DI**: TC-UT-DT-011 + TC-IT-DT-005 でスタブ差し替え可能性を物理確認
- **§確定 D application 層責務**: TC-UT-RP-013 で domain 層が empire-scope 一意性を強制しないことを物理確認
- **§確定 E get_all_acceptance_criteria**: TC-UT-RP-010〜012 + TC-IT-DT-003 で union / dedup / ordering を物理確認
- **MSG 2 行構造 + Next: hint**: TC-UT-MSG-001〜005 で全 5 MSG-DT で `assert "Next:" in str(exc)` を CI 強制
- **frozen 不変性 + extra='forbid' + 型違反**: DT / RP / SemVer / DeliverableTemplateRef / AcceptanceCriterion 全 VO で独立検証
- C0 目標: `domain/deliverable_template/` および `domain/value_objects/template_vos.py` で **95% 以上**

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全ジョブ緑
- ローカル: `cd backend && uv run pytest tests/domain/deliverable_template/ -v` → 全テスト緑
- 不変条件違反の実観測: `type=JSON_SCHEMA, schema='not dict'` で `[FAIL] Template schema is not valid JSON Schema.` + `Next: ...` が出ることを目視
- compose 自己参照の実観測: 自己 ID を composition に含めて `[FAIL] Template cannot include itself in composition.` が出ることを目視
- pre-validate 安全性の実観測: 失敗後の元インスタンスで全属性が変化なしを assert で目視
- §確定 C DI の実観測: テスト用 stub を渡して JSON Schema バリデーションが差し替わることを目視

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      deliverable_template.py           # DeliverableTemplateFactory / RoleProfileFactory /
                                        # SemVerFactory / AcceptanceCriterionFactory
      template_vos.py                   # DeliverableTemplateRefFactory / StubJSONSchemaValidatorFactory
    domain/
      deliverable_template/
        __init__.py
        test_deliverable_template/      # 3 ファイル分割
          __init__.py
          test_construction.py          # TC-UT-DT-001〜007, TC-UT-DT-017（構築 + frozen + extra='forbid' + 型違反）
          test_invariants.py            # TC-UT-DT-008〜016b, TC-UT-MSG-001〜005（不変条件 4 種 + MSG 2 行構造）
          test_behaviors.py             # TC-UT-DT-018〜025（create_new_version + compose）
        test_role_profile/              # 2 ファイル分割
          __init__.py
          test_construction.py          # TC-UT-RP-001〜005（構築 + frozen + extra='forbid'）
          test_behaviors.py             # TC-UT-RP-006〜014（add / remove / get_all_acceptance_criteria + §確定 D + pre-validate）
        test_value_objects/             # 1 ファイル
          __init__.py
          test_semver.py                # TC-UT-SV-001〜012, TC-UT-DRef-001〜002, TC-UT-AC-001〜005
        test_integration/               # 結合テスト
          __init__.py
          test_lifecycle.py             # TC-IT-DT-001〜005（lifecycle + pre-validate 安全性 + §確定 C stub）
```

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| DT 後続申し送り #1 | `acceptance_criteria[*].description` / `schema` への `MaskedText` 配線（A02 対応） | `feature/deliverable-template-repository`（Sub-issue #107-B 以降）| 基本設計 §セキュリティ設計 T4 参照。domain 層は raw 保持、repository 層でマスキング |
| DT 後続申し送り #2 | `AbstractJSONSchemaValidator` concrete 実装（`infrastructure/validation/json_schema_validator.py`）の DI 配線 | `feature/deliverable-template-domain` 実装フェーズ | §確定 C: application 層の設計確定後に DI 方式（コンストラクタ注入 / module-level / ContextVar 等）を決定 |
| DT 後続申し送り #3 | composition の transitive 解決（既知申し送り #2） | `feature/deliverable-template-application`（後続）| §確定 B: 現設計はシャロー解決。transitive が必要になった場合は application 層サービスで実装 |
| DT 後続申し送り #4 | `(empire_id, role)` DB 一意制約（既知申し送り #3） | `feature/deliverable-template-repository` | §確定 D: repository sub-feature のマイグレーションで一意制約を追加 |

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-DT-001〜006 すべてに 1 件以上のテストケース
- [ ] **TemplateType 5 値全種**（MARKDOWN / JSON_SCHEMA / OPENAPI / CODE_SKELETON / PROMPT）が独立した正常系で網羅
- [ ] **5 不変条件 helper 全種**（schema_format / composition_self_ref / version_non_negative / acceptance_criteria_empty_description / acceptance_criteria_no_duplicate_ids）が独立 unit ケースで網羅（TC-UT-DT-008〜016c）
- [ ] **§確定 A pre-validate**: 失敗時の元インスタンス不変を DT / RP 両方で物理確認（TC-UT-DT-022 / TC-UT-RP-014）
- [ ] **§確定 B compose の acceptance_criteria 非継承**: TC-UT-DT-025 で物理確認
- [ ] **§確定 C Validation Port**: TC-UT-DT-011 + TC-IT-DT-005 で DI 可能性を物理確認
- [ ] **§確定 D application 層責務**: TC-UT-RP-013 で domain 層が empire-scope 一意性を強制しないことを物理確認
- [ ] **§確定 E get_all_acceptance_criteria**: union / dedup / ordering が TC-UT-RP-010〜012 + TC-IT-DT-003 で物理確認
- [ ] **MSG 2 行構造 + Next: hint**: TC-UT-MSG-001〜005 で全 5 MSG-DT で `assert "Next:" in str(exc)` を CI 強制
- [ ] **§確定A09 detail ホワイトリスト**: TC-UT-A09-001〜003 で `exc.detail` に description/schema 本文が混入しないことを物理確認（Tabriz 指摘3）
- [ ] frozen / extra='forbid' / 型違反が DT / RP / SemVer / DeliverableTemplateRef / AcceptanceCriterion 全 VO で独立検証
- [ ] **テストファイル分割（6 ファイル）が basic-design.md §モジュール構成と整合**（Norman R-N1 教訓を最初から反映）
- [ ] 後続申し送り 4 件（マスキング配線 / DI 配線 / transitive 解決 / DB 一意制約）が PR 本文に明示
