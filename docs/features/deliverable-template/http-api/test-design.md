# テスト設計書 — deliverable-template / http-api

> feature: `deliverable-template` / sub-feature: `http-api`
> 関連 Issue: [#122 feat(deliverable-template): DeliverableTemplate / RoleProfile HTTP API](https://github.com/bakufu-dev/bakufu/issues/122)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../system-test-design.md`](../system-test-design.md)

## 本書の役割

本書は `basic-design.md §モジュール契約` の REQ-DT-HTTP-001〜005 / REQ-RP-HTTP-001〜004 と、`detailed-design.md` の確定事項 A〜I を、PR #122 実装 PR の検証範囲に紐付ける。

**書くこと**:

- DeliverableTemplate / RoleProfile HTTP API の結合テスト（エンドポイントから DB まで通す）
- DeliverableTemplateService / RoleProfileService のユニットテスト（業務ロジックを Repository モックで分離）
- §確定 B（PUT version 制約）/ §確定 C（Upsert 冪等性）/ §確定 D（DAG ガード）/ §確定 G（エラーフォーマット）/ §確定 H（id 省略生成）/ §確定 I（schema 型判別）の物理確認
- 全 MSG-DT-HTTP / MSG-RP-HTTP の HTTP ステータスコードと `code` フィールド確認

**書かないこと**:

- 実装前の characterization fixture（外部 API 依存なし。SQLite 実接続のため不要）
- resolved / versions エンドポイント（YAGNI、MVP スコープ外）

## テストケース ID 採番規則

| 番号帯 | 用途 |
|---|---|
| TC-IT-DTH-001〜020 | DeliverableTemplate HTTP API 結合テスト |
| TC-IT-RPH-001〜013 | RoleProfile HTTP API 結合テスト |
| TC-UT-DTS-001〜009 | DeliverableTemplateService ユニットテスト |
| TC-UT-RPS-001〜006 | RoleProfileService ユニットテスト |

## テストマトリクス

### DeliverableTemplate HTTP API — 結合テスト

| 要件 ID | 確定事項 | テストケース ID | テストレベル | 種別 | 期待する実装済みテスト |
|---|---|---|---|---|---|
| REQ-DT-HTTP-001 正常系 | — | TC-IT-DTH-001 | IT | 正常系 | `test_create.py::test_create_template_returns_201_with_all_fields` |
| REQ-DT-HTTP-001 ref 不在 | MSG-DT-HTTP-002 | TC-IT-DTH-002 | IT | 異常系 | `test_create.py::test_create_with_nonexistent_ref_returns_422` |
| REQ-DT-HTTP-001 自己参照 | MSG-DT-HTTP-003 | TC-IT-DTH-003 | IT | 異常系 | `test_create.py::test_create_with_self_reference_returns_422` |
| REQ-DT-HTTP-001 推移的循環 | MSG-DT-HTTP-003 | TC-IT-DTH-004 | IT | 異常系 | `test_create.py::test_create_with_transitive_cycle_returns_422` |
| REQ-DT-HTTP-001 DAG 深度ガード | §確定D | TC-IT-DTH-005 | IT | 境界値 | `test_create.py::test_create_dag_depth_limit_returns_422` |
| REQ-DT-HTTP-001 Pydantic 検証 | — | TC-IT-DTH-006 | IT | 異常系 | `test_create.py::test_create_with_invalid_name_returns_422` |
| REQ-DT-HTTP-001 schema 型判別 | §確定I | TC-IT-DTH-018 | IT | 正常系 | `test_create.py::test_create_json_schema_type_returns_dict_schema` |
| REQ-DT-HTTP-001 id 省略生成 | §確定H | TC-IT-DTH-019 | IT | 正常系 | `test_create.py::test_create_with_omitted_ac_id_generates_uuid` |
| REQ-DT-HTTP-002 空リスト | — | TC-IT-DTH-007 | IT | 正常系 | `test_read.py::test_list_returns_200_with_empty_items` |
| REQ-DT-HTTP-002 複数件昇順 | §確定I | TC-IT-DTH-008 | IT | 正常系 | `test_read.py::test_list_returns_items_sorted_by_name_asc` |
| REQ-DT-HTTP-003 正常系 | — | TC-IT-DTH-009 | IT | 正常系 | `test_read.py::test_get_returns_200_with_template` |
| REQ-DT-HTTP-003 不在 | MSG-DT-HTTP-001 | TC-IT-DTH-010 | IT | 異常系 | `test_read.py::test_get_nonexistent_returns_404` |
| REQ-DT-HTTP-003 UUID 不正 | — | TC-IT-DTH-011 | IT | 異常系 | `test_read.py::test_get_with_invalid_uuid_returns_422` |
| REQ-DT-HTTP-004 version 同一 | §確定B | TC-IT-DTH-012 | IT | 正常系 | `test_update.py::test_update_with_same_version_returns_200` |
| REQ-DT-HTTP-004 version 昇格 | §確定B | TC-IT-DTH-013 | IT | 正常系 | `test_update.py::test_update_with_higher_version_returns_200` |
| REQ-DT-HTTP-004 version 降格 | §確定B / MSG-DT-HTTP-004 | TC-IT-DTH-014 | IT | 異常系 | `test_update.py::test_update_with_lower_version_returns_422` |
| REQ-DT-HTTP-004 不在 | MSG-DT-HTTP-001 | TC-IT-DTH-015 | IT | 異常系 | `test_update.py::test_update_nonexistent_returns_404` |
| REQ-DT-HTTP-005 正常系 | §確定E | TC-IT-DTH-016 | IT | 正常系 | `test_delete.py::test_delete_returns_204` |
| REQ-DT-HTTP-005 不在 | MSG-DT-HTTP-001 | TC-IT-DTH-017 | IT | 異常系 | `test_delete.py::test_delete_nonexistent_returns_404` |
| 全エンドポイント | §確定G | TC-IT-DTH-020 | IT | セキュリティ | `test_read.py::test_error_response_format_matches_confirmed_g` |

### RoleProfile HTTP API — 結合テスト

| 要件 ID | 確定事項 | テストケース ID | テストレベル | 種別 | 期待する実装済みテスト |
|---|---|---|---|---|---|
| REQ-RP-HTTP-001 空リスト | — | TC-IT-RPH-001 | IT | 正常系 | `test_read_delete.py::test_list_returns_200_with_empty_items` |
| REQ-RP-HTTP-001 Empire 不在 | MSG-RP-HTTP-003 | TC-IT-RPH-002 | IT | 異常系 | `test_read_delete.py::test_list_with_nonexistent_empire_returns_404` |
| REQ-RP-HTTP-002 正常系 | — | TC-IT-RPH-003 | IT | 正常系 | `test_read_delete.py::test_get_returns_200_with_profile` |
| REQ-RP-HTTP-002 不在 | MSG-RP-HTTP-001 | TC-IT-RPH-004 | IT | 異常系 | `test_read_delete.py::test_get_nonexistent_returns_404` |
| REQ-RP-HTTP-002 role 不正値 | — | TC-IT-RPH-005 | IT | 異常系 | `test_read_delete.py::test_get_with_invalid_role_returns_422` |
| REQ-RP-HTTP-003 新規 Upsert | §確定C | TC-IT-RPH-006 | IT | 正常系 | `test_upsert.py::test_upsert_creates_new_profile_returns_200` |
| REQ-RP-HTTP-003 冪等 Upsert | §確定C | TC-IT-RPH-007 | IT | 正常系 | `test_upsert.py::test_upsert_twice_preserves_same_id` |
| REQ-RP-HTTP-003 Empire 不在 | MSG-RP-HTTP-003 | TC-IT-RPH-008 | IT | 異常系 | `test_upsert.py::test_upsert_with_nonexistent_empire_returns_404` |
| REQ-RP-HTTP-003 ref 不在 | MSG-RP-HTTP-002 | TC-IT-RPH-009 | IT | 異常系 | `test_upsert.py::test_upsert_with_nonexistent_ref_returns_422` |
| REQ-RP-HTTP-003 refs 完全置換 | §確定C | TC-IT-RPH-010 | IT | 正常系 | `test_upsert.py::test_upsert_replaces_all_refs` |
| REQ-RP-HTTP-004 正常系 | §確定E | TC-IT-RPH-011 | IT | 正常系 | `test_read_delete.py::test_delete_returns_204` |
| REQ-RP-HTTP-004 不在 | MSG-RP-HTTP-001 | TC-IT-RPH-012 | IT | 異常系 | `test_read_delete.py::test_delete_nonexistent_returns_404` |
| REQ-RP-HTTP-003 role 不正値 | — | TC-IT-RPH-013 | IT | 異常系 | `test_upsert.py::test_upsert_with_invalid_role_returns_422` |

### Service ユニットテスト

| 対象クラス / メソッド | 確定事項 | テストケース ID | テストレベル | 種別 | 期待する実装済みテスト |
|---|---|---|---|---|---|
| `DeliverableTemplateService.find_by_id` None | — | TC-UT-DTS-001 | UT | 異常系 | `test_deliverable_template_service.py::test_find_by_id_raises_when_not_found` |
| `DeliverableTemplateService._check_dag` 自己参照 | §確定D | TC-UT-DTS-002 | UT | 異常系 | `test_deliverable_template_service.py::test_check_dag_raises_on_self_reference` |
| `DeliverableTemplateService._check_dag` 推移的循環 | §確定D | TC-UT-DTS-003 | UT | 異常系 | `test_deliverable_template_service.py::test_check_dag_raises_on_transitive_cycle` |
| `DeliverableTemplateService._check_dag` 深度上限（10超）| §確定D | TC-UT-DTS-004 | UT | 境界値 | `test_deliverable_template_service.py::test_check_dag_raises_on_depth_limit` |
| `DeliverableTemplateService._check_dag` ノード上限（100超）| §確定D | TC-UT-DTS-005 | UT | 境界値 | `test_deliverable_template_service.py::test_check_dag_raises_on_node_limit` |
| `DeliverableTemplateService.update` version 降格 | §確定B | TC-UT-DTS-006 | UT | 異常系 | `test_deliverable_template_service.py::test_update_raises_on_version_downgrade` |
| `DeliverableTemplateService.update` version 同一 | §確定B | TC-UT-DTS-007 | UT | 正常系 | `test_deliverable_template_service.py::test_update_same_version_does_not_call_create_new_version` |
| `DeliverableTemplateService.update` version 昇格 | §確定B | TC-UT-DTS-008 | UT | 正常系 | `test_deliverable_template_service.py::test_update_higher_version_calls_create_new_version` |
| `DeliverableTemplateService.delete` 不在 | §確定E | TC-UT-DTS-009 | UT | 異常系 | `test_deliverable_template_service.py::test_delete_raises_when_not_found` |
| `RoleProfileService.find_by_empire_and_role` None | — | TC-UT-RPS-001 | UT | 異常系 | `test_role_profile_service.py::test_find_raises_when_not_found` |
| `RoleProfileService.upsert` Empire 不在 | — | TC-UT-RPS-002 | UT | 異常系 | `test_role_profile_service.py::test_upsert_raises_on_empire_not_found` |
| `RoleProfileService.upsert` ref 不在 | — | TC-UT-RPS-003 | UT | 異常系 | `test_role_profile_service.py::test_upsert_raises_on_ref_not_found` |
| `RoleProfileService.upsert` 既存あり | §確定C | TC-UT-RPS-004 | UT | 正常系 | `test_role_profile_service.py::test_upsert_preserves_existing_id` |
| `RoleProfileService.upsert` 既存なし | §確定C | TC-UT-RPS-005 | UT | 正常系 | `test_role_profile_service.py::test_upsert_generates_new_id_when_not_exists` |
| `RoleProfileService.delete` 不在 | §確定E | TC-UT-RPS-006 | UT | 異常系 | `test_role_profile_service.py::test_delete_raises_when_not_found` |

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 | 状態 |
|---|---|---|---|---|---|
| SQLite（テスト用 DB）| 結合テスト: 実 DB で CREATE → GET → UPDATE → DELETE 確認 | `tmp_path` 配下の一時 DB（`conftest.py` の `app_engine` fixture）| `tests/factories/deliverable_template.py`（既存: `make_deliverable_template` / `make_role_profile` / `make_deliverable_template_ref` / `make_acceptance_criterion` / `make_semver`）| 実接続。テスト DB は Alembic `upgrade head` 済み | 済 |
| FastAPI ASGI | 結合テスト: HTTP リクエスト送信 | — | — | `httpx.AsyncClient(transport=ASGITransport(app=app))` + `base_url="http://test"` | 済（http-api-foundation パターン）|
| `DeliverableTemplateRepository` モック | ユニットテスト: Service の業務ロジック分離 | — | `tests/factories/deliverable_template.py` が返す `DeliverableTemplate` / `RoleProfile` インスタンス | `AsyncMock` で Repository Protocol をモック。返却値に factory 生成済みインスタンスを使用 | 要実装（factory 済み）|
| `RoleProfileRepository` モック | ユニットテスト: RoleProfileService の業務ロジック分離 | — | 同上 | 同上 | 要実装 |
| `EmpireRepository` モック | ユニットテスト: RoleProfileService の Empire 存在確認分離 | — | `tests/factories/empire.py` または inline Empire stub | `AsyncMock` で `find_by_id` を None / empire インスタンスに設定 | 要確認（empire factory 存在確認が必要）|

**モック設計の注意**:
- assumed mock（根拠なき仮定の返却値）禁止。factory 生成済みインスタンスを `return_value` に渡すこと
- `AsyncMock` は `unittest.mock` の `AsyncMock` を使用（await 互換）
- Repository 全モックは `spec=DeliverableTemplateRepository`（Protocol duck typing 保証）

## 結合テストケース詳細

### TC-IT-DTH-001: POST /api/deliverable-templates 正常系

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 |
| 種別 | 正常系 |
| 前提条件 | DB 空、FastAPI app 起動済み |
| 操作 | `POST /api/deliverable-templates` に `{name, description, type: "MARKDOWN", schema: "## test", version: {major:1, minor:0, patch:0}, acceptance_criteria:[], composition:[]}` を送信 |
| 期待結果 | HTTP 201。レスポンス body に `id`（UUID 形式）/ `name` / `description` / `type` / `schema` / `version: {major:1, minor:0, patch:0}` / `acceptance_criteria: []` / `composition: []` が存在する |
| 確認方法 | `httpx.AsyncClient` + `ASGITransport`、続けて GET で存在確認（ラウンドトリップ） |

### TC-IT-DTH-002: POST — composition ref 不在 → 422

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / MSG-DT-HTTP-002 |
| 種別 | 異常系 |
| 前提条件 | DB 空（参照先 template が存在しない） |
| 操作 | `composition: [{template_id: <unknown-uuid>, minimum_version: {major:1,minor:0,patch:0}}]` を含む POST |
| 期待結果 | HTTP 422。`response.json()["error"]["code"] == "ref_not_found"` |

### TC-IT-DTH-003: POST — 自己参照循環 → 422

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / MSG-DT-HTTP-003 |
| 種別 | 異常系 |
| 前提条件 | — |
| 操作 | `composition` に自分自身の `template_id` を含む POST（domain の不変条件チェックが先に発火） |
| 期待結果 | HTTP 422。`code` は `composition_cycle` または domain が raise する `DeliverableTemplateInvariantViolation` 由来のコード |
| 注記 | 自己参照は domain `DeliverableTemplate` が直接検出（service の `_check_dag` 実行前）。どちらの経路でも 422 を返すことを確認 |

### TC-IT-DTH-004: POST — 推移的循環（A→B→A）→ 422

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / MSG-DT-HTTP-003 |
| 種別 | 異常系 |
| 前提条件 | テンプレート B が先に作成済み。B は A を composition に含む予定で A はまだ存在しない → B 作成後、A を `composition: [ref_to_B]` で POST し、さらに B を PUT で `composition: [ref_to_A]` に更新する |
| 操作 | A を作成後、B の PUT で `composition: [ref_to_A]` を設定すると A→B→A 循環が完成 |
| 期待結果 | HTTP 422。`code == "composition_cycle"` |
| 注記 | POST 自体で循環が生じるシナリオを構成するには先行 template を複数作る必要あり |

### TC-IT-DTH-005: POST — DAG 深度ガード（§確定 D）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / §確定 D |
| 種別 | 境界値 |
| 前提条件 | 深度 10 以上の composition チェーン（T1 → T2 → ... → T11）を DB に構築済み |
| 操作 | T12 を作成し `composition: [ref_to_T11]` を指定（深度 11） |
| 期待結果 | HTTP 422。`code == "composition_cycle"`（`cycle_path=["depth_limit_exceeded"]`） |

### TC-IT-DTH-006: POST — name 空文字 → 422

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 |
| 種別 | 異常系 |
| 操作 | `name: ""` を含む POST |
| 期待結果 | HTTP 422（Pydantic バリデーション） |

### TC-IT-DTH-007: GET /api/deliverable-templates — 空リスト

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-002 |
| 種別 | 正常系 |
| 前提条件 | DB 空 |
| 操作 | `GET /api/deliverable-templates` |
| 期待結果 | HTTP 200。`{"items": [], "total": 0}` |

### TC-IT-DTH-008: GET /api/deliverable-templates — 複数件 name 昇順

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-002 |
| 種別 | 正常系 |
| 前提条件 | name = "Z-template" / "A-template" / "M-template" の 3 件を順不同で POST |
| 操作 | `GET /api/deliverable-templates` |
| 期待結果 | HTTP 200。`items[0].name == "A-template"` / `items[1].name == "M-template"` / `items[2].name == "Z-template"` |

### TC-IT-DTH-009: GET /api/deliverable-templates/{id} 正常系

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-003 |
| 種別 | 正常系 |
| 前提条件 | template が 1 件 POST 済み |
| 操作 | `GET /api/deliverable-templates/{id}` |
| 期待結果 | HTTP 200。`id` / `name` / `type` / `version` が POST 時と一致 |

### TC-IT-DTH-010: GET /api/deliverable-templates/{id} — 不在 → 404

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-003 / MSG-DT-HTTP-001 |
| 種別 | 異常系 |
| 操作 | 存在しない UUID で `GET /api/deliverable-templates/{unknown-uuid}` |
| 期待結果 | HTTP 404。`code == "not_found"` |

### TC-IT-DTH-011: GET — UUID 形式不正 → 422

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-003 |
| 種別 | 異常系 |
| 操作 | `GET /api/deliverable-templates/not-a-uuid` |
| 期待結果 | HTTP 422 |

### TC-IT-DTH-012: PUT — version 同一 → 200（§確定 B）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-004 / §確定 B |
| 種別 | 正常系 |
| 前提条件 | version 1.0.0 の template が存在 |
| 操作 | `PUT` で `version: {major:1, minor:0, patch:0}` を指定（同一 version） |
| 期待結果 | HTTP 200。`version.major == 1` / `version.minor == 0` / `version.patch == 0` |

### TC-IT-DTH-013: PUT — version 昇格 → 200（§確定 B）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-004 / §確定 B |
| 種別 | 正常系 |
| 前提条件 | version 1.0.0 の template が存在 |
| 操作 | `PUT` で `version: {major:2, minor:0, patch:0}` を指定（昇格） |
| 期待結果 | HTTP 200。`version.major == 2` |

### TC-IT-DTH-014: PUT — version 降格 → 422（§確定 B）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-004 / §確定 B / MSG-DT-HTTP-004 |
| 種別 | 異常系 |
| 前提条件 | version 2.0.0 の template が存在 |
| 操作 | `PUT` で `version: {major:1, minor:0, patch:0}` を指定（降格） |
| 期待結果 | HTTP 422。`code == "version_downgrade"` |

### TC-IT-DTH-015: PUT — 不在 → 404

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-004 / MSG-DT-HTTP-001 |
| 種別 | 異常系 |
| 操作 | 存在しない UUID で `PUT` |
| 期待結果 | HTTP 404。`code == "not_found"` |

### TC-IT-DTH-016: DELETE — 正常系 → 204（§確定 E）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-005 / §確定 E |
| 種別 | 正常系 |
| 前提条件 | template が 1 件 POST 済み |
| 操作 | `DELETE /api/deliverable-templates/{id}` |
| 期待結果 | HTTP 204 No Content。続けて GET で 404 になること |

### TC-IT-DTH-017: DELETE — 不在 → 404

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-005 / MSG-DT-HTTP-001 |
| 種別 | 異常系 |
| 操作 | 存在しない UUID で `DELETE` |
| 期待結果 | HTTP 404。`code == "not_found"` |

### TC-IT-DTH-018: POST — JSON_SCHEMA type → schema が dict（§確定 I）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / §確定 I |
| 種別 | 正常系 |
| 操作 | `type: "JSON_SCHEMA"`, `schema: {"$schema": "...", "type": "object"}` で POST |
| 期待結果 | HTTP 201。`response.schema` が dict 型で返却される |
| 注記 | OPENAPI type も同様に dict で返却されることを確認 |

### TC-IT-DTH-019: POST — AcceptanceCriterionCreate.id 省略 → UUID 自動生成（§確定 H）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / §確定 H |
| 種別 | 正常系 |
| 操作 | `acceptance_criteria: [{description: "条件1", required: true}]`（id 省略）で POST |
| 期待結果 | HTTP 201。`acceptance_criteria[0].id` が有効な UUID v4 形式の文字列 |

### TC-IT-DTH-020: エラーレスポンスフォーマット確認（§確定 G）

| 項目 | 内容 |
|---|---|
| 対応 | §確定 G |
| 種別 | セキュリティ |
| 操作 | 存在しない id で GET（404 が返る操作） |
| 期待結果 | レスポンス body が `{"error": {"code": str, "message": str, "detail": ...}}` 構造を持つ。スタックトレースを含まない |

### TC-IT-RPH-001〜013 の共通前提条件

結合テスト全体で `_seed_empire(session_factory, empire_id)` ヘルパ（repository テストで実装済みのパターン）または HTTP 経由の Empire 作成で empire_id を準備する。

### TC-IT-RPH-006: PUT — 新規 Upsert → 200（§確定 C）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-RP-HTTP-003 / §確定 C |
| 種別 | 正常系 |
| 前提条件 | Empire 存在、当該 role の RoleProfile なし |
| 操作 | `PUT /api/empires/{empire_id}/role-profiles/DEVELOPER` に `{deliverable_template_refs: []}` を送信 |
| 期待結果 | HTTP 200。`id`（UUID）/ `empire_id` / `role == "DEVELOPER"` / `deliverable_template_refs == []` |

### TC-IT-RPH-007: PUT — 2 回 Upsert で同一 id を保持（§確定 C）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-RP-HTTP-003 / §確定 C |
| 種別 | 正常系 |
| 前提条件 | 1 回目 PUT で RoleProfile 作成済み |
| 操作 | 同一 `PUT /api/empires/{empire_id}/role-profiles/DEVELOPER` を再度送信 |
| 期待結果 | HTTP 200（エラーなし）。`response.id` が 1 回目と同一 UUID |

### TC-IT-RPH-010: PUT — refs 完全置換（§確定 C）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-RP-HTTP-003 / §確定 C |
| 種別 | 正常系 |
| 前提条件 | ref を 2 件持つ RoleProfile が存在 |
| 操作 | refs を空リストにして PUT |
| 期待結果 | HTTP 200。`deliverable_template_refs == []`（完全置換されている） |

## ユニットテストケース詳細

### TC-UT-DTS-004: _check_dag 深度上限 10 超 → CompositionCycleError（§確定 D）

| 項目 | 内容 |
|---|---|
| 対応 | §確定 D |
| 種別 | 境界値 |
| モック | `DeliverableTemplateRepository.find_by_id` が 11 段のチェーンを返す（depth=11 で上限 10 超） |
| 操作 | `_check_dag(refs=[chain_start], root_id=..., depth=0, visited=set())` |
| 期待結果 | `CompositionCycleError` raise。`cycle_path == ["depth_limit_exceeded"]` |

### TC-UT-DTS-006: update — version 降格 → DeliverableTemplateVersionDowngradeError（§確定 B）

| 項目 | 内容 |
|---|---|
| 対応 | §確定 B |
| 種別 | 異常系 |
| モック | `find_by_id` が version 2.0.0 の template を返す |
| 操作 | `update(id, ..., version=SemVer(major=1, minor=0, patch=0), ...)` |
| 期待結果 | `DeliverableTemplateVersionDowngradeError` raise。`current_version == "2.0.0"` / `provided_version == "1.0.0"` |

### TC-UT-DTS-007: update — version 同一 → create_new_version を呼ばない（§確定 B）

| 項目 | 内容 |
|---|---|
| 対応 | §確定 B |
| 種別 | 正常系 |
| モック | `find_by_id` が version 1.0.0 の template を返す。`template.create_new_version` に spy を設定 |
| 操作 | `update(id, ..., version=SemVer(major=1, minor=0, patch=0), ...)` |
| 期待結果 | 例外なし。`create_new_version` は呼ばれない |

### TC-UT-RPS-004: upsert — 既存あり → 既存 id 保持（§確定 C）

| 項目 | 内容 |
|---|---|
| 対応 | §確定 C |
| 種別 | 正常系 |
| モック | `find_by_empire_and_role` が既存の RoleProfile（`id=existing_id`）を返す |
| 操作 | `upsert(empire_id, role, refs=[])` |
| 期待結果 | `save` に渡された RoleProfile の `id == existing_id`（既存 id を継承） |

## モック方針

| テストレベル | I/O | 方針 |
|---|---|---|
| **結合テスト（IT）** | SQLite | 実接続。`conftest.py` の `app_engine` + Alembic `upgrade head` 済み DB |
| **結合テスト（IT）** | FastAPI ASGI | `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` |
| **ユニットテスト（UT）** | `DeliverableTemplateRepository` | `AsyncMock(spec=DeliverableTemplateRepository)` / 返却値は factory 生成済みインスタンス |
| **ユニットテスト（UT）** | `RoleProfileRepository` | `AsyncMock(spec=RoleProfileRepository)` |
| **ユニットテスト（UT）** | `EmpireRepository` | `AsyncMock(spec=EmpireRepository)` |
| **ユニットテスト（UT）** | session / DB | DI でモック Repository を渡すため不要 |

**assumed mock 禁止の実施方法**: factory 生成済みインスタンスを `mock.return_value` に渡す。`MagicMock()` のデフォルト返却値を直接アサーションに使わない。

## テストディレクトリ構造

```
backend/tests/
├── infrastructure/persistence/sqlite/
│   └── routers/                                  # 結合テスト（HTTP API）
│       ├── test_deliverable_template/
│       │   ├── __init__.py
│       │   ├── test_create.py                    # TC-IT-DTH-001〜006 / 018 / 019
│       │   ├── test_read.py                      # TC-IT-DTH-007〜011 / 020
│       │   ├── test_update.py                    # TC-IT-DTH-012〜015
│       │   └── test_delete.py                    # TC-IT-DTH-016〜017
│       └── test_role_profile/
│           ├── __init__.py
│           ├── test_upsert.py                    # TC-IT-RPH-006〜010 / 013
│           └── test_read_delete.py               # TC-IT-RPH-001〜005 / 011〜012
└── unit/
    ├── test_deliverable_template_service.py      # TC-UT-DTS-001〜009
    └── test_role_profile_service.py              # TC-UT-RPS-001〜006
```

**注記**: bakufu リポジトリの既存テスト構造（`tests/infrastructure/persistence/sqlite/repositories/`）に準拠し、HTTP API テストは `tests/infrastructure/persistence/sqlite/routers/` 配下に配置する。既存の http-api-foundation テスト（`tests/interfaces/http/`）が存在する場合はそちらのパターンを優先する。実装 PR で既存パターンを確認の上、適切なディレクトリを選択する。

## カバレッジ基準

- REQ-DT-HTTP-001〜005 / REQ-RP-HTTP-001〜004 の全正常系を結合テストで 1 件以上検証する
- 全 MSG-DT-HTTP / MSG-RP-HTTP（404 / 422 両方）の HTTP ステータスコードを結合テストで確認する
- §確定 B（version 降格・同一・昇格 3 経路）/ §確定 C（冪等性・id 保持・refs 置換）/ §確定 D（深度・ノード上限）を物理確認する
- §確定 G（エラーレスポンスフォーマット：`{"error": {"code", "message", "detail"}}`）を 1 件以上確認する
- §確定 H（AcceptanceCriterion.id 省略時 UUID 生成）/ §確定 I（schema type 判別: JSON_SCHEMA/OPENAPI → dict、他 → str）を物理確認する
- Service の業務ロジック（DAG 走査・version 比較・upsert id 継承）はユニットテストで独立して検証する

## 人間が動作確認できるタイミング

CI 統合後（PR #122 の GitHub Actions 全ジョブ緑確認）:

```sh
# 結合テスト（DeliverableTemplate HTTP API）
uv run pytest backend/tests/infrastructure/persistence/sqlite/routers/test_deliverable_template/ -v

# 結合テスト（RoleProfile HTTP API）
uv run pytest backend/tests/infrastructure/persistence/sqlite/routers/test_role_profile/ -v

# ユニットテスト（Service 業務ロジック）
uv run pytest backend/tests/unit/test_deliverable_template_service.py backend/tests/unit/test_role_profile_service.py -v
```

**注記**: 実際のテストディレクトリは実装 PR での既存パターン確認後に確定する。上記パスは予定。

## 未決課題・characterization task

| # | 内容 | 起票先 |
|---|---|---|
| 1 | `tests/factories/empire.py` の存在確認（RoleProfileService UT で Empire stub が必要）。存在しない場合は inline stub で代替 | 実装 PR で確認 |
| 2 | 既存 http-api-foundation の `conftest.py` で `app` fixture / `ASGITransport` の共通セットアップがあるか確認。ある場合は再利用、ない場合は本 PR で追加 | 実装 PR で確認 |
| 3 | TC-IT-DTH-003〜004（DAG 循環）の結合テスト構成が複雑（複数 POST が前提）。50 行超過の場合は conftest fixture に前提データ構築を移動する | 実装時判断 |
| characterization | 外部 API 依存なし。SQLite は実接続のため characterization fixture 不要 | — |

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — REQ-DT-HTTP-001〜005 / REQ-RP-HTTP-001〜004
- [`detailed-design.md`](detailed-design.md) — §確定 A〜I / MSG 確定文言 / データ構造
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様（UC-DT-001〜005 / R1-A〜F）
- [`../system-test-design.md`](../system-test-design.md) — feature 全体の E2E テスト
- [`../repository/basic-design.md`](../repository/basic-design.md) — Repository Protocol（`delete()` 拡張元）
