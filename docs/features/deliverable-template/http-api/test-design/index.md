# テスト設計書 — deliverable-template / http-api

> feature: `deliverable-template` / sub-feature: `http-api`
> 関連 Issue: [#122 feat(deliverable-template): DeliverableTemplate / RoleProfile HTTP API](https://github.com/bakufu-dev/bakufu/issues/122)
> 関連: [`basic-design.md §モジュール契約`](../basic-design.md) / [`detailed-design.md`](../detailed-design.md) / [`../../feature-spec.md`](../../feature-spec.md) / [`../../system-test-design.md`](../../system-test-design.md)

## 本書の役割

本書は `basic-design.md §モジュール契約` の REQ-DT-HTTP-001〜005 / REQ-RP-HTTP-001〜004 と、`detailed-design.md` の確定事項 A〜I を、PR #122 実装 PR の検証範囲に紐付ける。

**書くこと**:

- DeliverableTemplate / RoleProfile HTTP API の結合テスト（エンドポイントから DB まで通す）
- DeliverableTemplateService / RoleProfileService のユニットテスト（業務ロジックを Repository モックで分離）
- §確定 B（PUT version 制約）/ §確定 C（Upsert 冪等性）/ §確定 D（DAG ガード）/ §確定 G（エラーフォーマット）/ §確定 H（id 省略生成・重複禁止）/ §確定 I（schema 型判別）の物理確認
- 全 MSG-DT-HTTP / MSG-RP-HTTP の HTTP ステータスコードと `code` フィールド確認

**書かないこと**:

- 実装前の characterization fixture（外部 API 依存なし。SQLite 実接続のため不要）
- resolved / versions エンドポイント（YAGNI、MVP スコープ外）

## テストケース ID 採番規則

| 番号帯 | 用途 |
|---|---|
| TC-IT-DTH-001〜021 | DeliverableTemplate HTTP API 結合テスト |
| TC-IT-RPH-001〜013 | RoleProfile HTTP API 結合テスト |
| TC-IT-DTR-021〜022 | DeliverableTemplateRepository.delete() 単体（§確定 E 物理確認）|
| TC-IT-RPR-016〜017 | RoleProfileRepository.delete() 単体（§確定 E 物理確認）|
| TC-UT-DTS-001〜009 | DeliverableTemplateService ユニットテスト |
| TC-UT-RPS-001〜006 | RoleProfileService ユニットテスト |

## テストマトリクス

### DeliverableTemplate HTTP API — 結合テスト

| 要件 ID | 確定事項 | テストケース ID | テストレベル | 種別 | 期待する実装済みテスト |
|---|---|---|---|---|---|
| REQ-DT-HTTP-001 正常系 | — | TC-IT-DTH-001 | IT | 正常系 | `test_create.py::test_create_template_returns_201_with_all_fields` |
| REQ-DT-HTTP-001 ref 不在 | MSG-DT-HTTP-002 | TC-IT-DTH-002 | IT | 異常系 | `test_create.py::test_create_with_nonexistent_ref_returns_422` |
| REQ-DT-HTTP-001 自己参照 | MSG-DT-002（domain invariant）| TC-IT-DTH-003 | IT | 異常系 | `test_create.py::test_create_with_self_reference_returns_422` |
| REQ-DT-HTTP-001 推移的循環 | MSG-DT-HTTP-003a | TC-IT-DTH-004 | IT | 異常系 | `test_create.py::test_create_with_transitive_cycle_returns_422` |
| REQ-DT-HTTP-001 DAG 深度ガード | §確定D / MSG-DT-HTTP-003b | TC-IT-DTH-005 | IT | 境界値 | `test_create.py::test_create_dag_depth_limit_returns_422` |
| REQ-DT-HTTP-001 Pydantic 検証 | — | TC-IT-DTH-006 | IT | 異常系 | `test_create.py::test_create_with_invalid_name_returns_422` |
| REQ-DT-HTTP-001 schema 型判別 | §確定I | TC-IT-DTH-018 | IT | 正常系 | `test_create.py::test_create_json_schema_type_returns_dict_schema` |
| REQ-DT-HTTP-001 id 省略生成 | §確定H | TC-IT-DTH-019 | IT | 正常系 | `test_create.py::test_create_with_omitted_ac_id_generates_uuid` |
| REQ-DT-HTTP-001 AC id 重複 | §確定H | TC-IT-DTH-021 | IT | 異常系 | `test_create.py::test_create_with_duplicate_ac_id_returns_422` |
| REQ-DT-HTTP-002 空リスト | — | TC-IT-DTH-007 | IT | 正常系 | `test_read.py::test_list_returns_200_with_empty_items` |
| REQ-DT-HTTP-002 複数件昇順 | ORDER BY name ASC, id ASC | TC-IT-DTH-008 | IT | 正常系 | `test_read.py::test_list_returns_items_sorted_by_name_asc` |
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

### Repository.delete() — 結合テスト（§確定 E 物理確認）

| 要件 ID | 確定事項 | テストケース ID | テストレベル | 種別 | 期待する実装済みテスト |
|---|---|---|---|---|---|
| REQ-DT-HTTP-005 | §確定E | TC-IT-DTR-021 | IT | 正常系 | `test_protocol_and_crud.py::test_delete_removes_existing_template` |
| REQ-DT-HTTP-005 | §確定E（no-op）| TC-IT-DTR-022 | IT | 異常系 | `test_protocol_and_crud.py::test_delete_noop_on_unknown_id` |
| REQ-RP-HTTP-004 | §確定E | TC-IT-RPR-016 | IT | 正常系 | `test_crud_basic.py::test_delete_removes_existing_profile` |
| REQ-RP-HTTP-004 | §確定E（no-op）| TC-IT-RPR-017 | IT | 異常系 | `test_crud_basic.py::test_delete_noop_on_unknown_id` |

**設計判断**: HTTP DELETE（TC-IT-DTH-016/017 / TC-IT-RPH-011/012）では Service 経由でのエンドツーエンド確認を行う。Repository.delete() の no-op 挙動（存在しない id でも例外なし）は HTTP 層と分離して物理確認する必要があるため、TC-IT-DTR-021/022 / TC-IT-RPR-016/017 を Repository 直接呼び出しテストとして追加する。

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
| `EmpireRepository` モック | ユニットテスト: RoleProfileService の Empire 存在確認分離 | — | `tests/factories/empire.py`（存在確認済み）| `AsyncMock` で `find_by_id` を None / empire インスタンスに設定 | 済（物理確認済み）|

**モック設計の注意**:
- assumed mock（根拠なき仮定の返却値）禁止。factory 生成済みインスタンスを `return_value` に渡すこと
- `AsyncMock` は `unittest.mock` の `AsyncMock` を使用（await 互換）
- Repository 全モックは `spec=DeliverableTemplateRepository`（Protocol duck typing 保証）

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
├── integration/
│   ├── test_deliverable_template_http_api/       # TC-IT-DTH-001〜021
│   │   ├── __init__.py
│   │   ├── conftest.py                           # app fixture / ASGITransport / engine
│   │   ├── test_create.py                        # TC-IT-DTH-001〜006 / 018 / 019 / 021
│   │   ├── test_read.py                          # TC-IT-DTH-007〜011 / 020
│   │   ├── test_update.py                        # TC-IT-DTH-012〜015
│   │   └── test_delete.py                        # TC-IT-DTH-016〜017
│   └── test_role_profile_http_api/               # TC-IT-RPH-001〜013
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_upsert.py                        # TC-IT-RPH-006〜010 / 013
│       └── test_read_delete.py                   # TC-IT-RPH-001〜005 / 011〜012
├── infrastructure/persistence/sqlite/repositories/
│   ├── test_deliverable_template_repository/
│   │   └── test_crud/
│   │       ├── test_protocol_and_crud.py         # 既存 + TC-IT-DTR-021〜022 追加
│   │       └── test_schema_and_conversions.py    # 既存
│   └── test_role_profile_repository/
│       └── test_crud/
│           ├── test_crud_basic.py                # 既存 + TC-IT-RPR-016〜017 追加
│           └── test_crud_constraints.py          # 既存
└── unit/
    ├── test_deliverable_template_service.py      # TC-UT-DTS-001〜009
    └── test_role_profile_service.py              # TC-UT-RPS-001〜006
```

**注記**: HTTP API テストの配置パターンは `tests/integration/test_{feature}_http_api/`（ディレクトリ形式）に統一する（既存: `test_directive_http_api/` / `test_room_http_api/` / `test_agent_http_api/` 等と同一パターン）。`conftest.py` は各 `test_*_http_api/` ディレクトリ直下に配置し、`app` fixture と `ASGITransport` の共通セットアップを行う。

## カバレッジ基準

- REQ-DT-HTTP-001〜005 / REQ-RP-HTTP-001〜004 の全正常系を結合テストで 1 件以上検証する
- 全 MSG-DT-HTTP / MSG-RP-HTTP（404 / 422 両方）の HTTP ステータスコードを結合テストで確認する
- §確定 B（version 降格・同一・昇格 3 経路）/ §確定 C（冪等性・id 保持・refs 置換）/ §確定 D（深度・ノード上限）を物理確認する
- §確定 D の DAG 循環 3 分岐（MSG-DT-HTTP-003a: `transitive_cycle` / MSG-DT-HTTP-003b: `depth_limit` / MSG-DT-HTTP-003c: `node_limit`）は HTTP IT または UT で各 `reason` を物理確認する
- §確定 G（エラーレスポンスフォーマット：`{"error": {"code", "message", "detail"}}`）を 1 件以上確認する
- §確定 H（AcceptanceCriterion.id 省略時 UUID 生成 / 同一リクエスト内 id 重複 → 422）/ §確定 I（schema type 判別: JSON_SCHEMA/OPENAPI → dict、他 → str）を物理確認する
- Service の業務ロジック（DAG 走査・version 比較・upsert id 継承）はユニットテストで独立して検証する

## A09 監査ログ（テスト対象外）

**MVP スコープ外。UT / IT の対象なし。**

`basic-design.md §A09`: 操作監査ログ（誰が・いつ・何を）は MVP スコープ外とする（loopback バインドで認証なし・個人開発 CEO 1 人・操作者特定不可能）。将来の認証実装時に Service 層で audit log テーブルへの書き込みを追加する（別 Issue）。スタックトレースはレスポンスに含めない。

これにより本テスト設計書には監査ログ検証ケースを追加しない。将来の監査ログ Issue 実装時に、その PR のテスト設計書で改めて定義する。

## 人間が動作確認できるタイミング

CI 統合後（PR #122 の GitHub Actions 全ジョブ緑確認）:

```sh
# 結合テスト（DeliverableTemplate HTTP API）
uv run pytest backend/tests/integration/test_deliverable_template_http_api/ -v

# 結合テスト（RoleProfile HTTP API）
uv run pytest backend/tests/integration/test_role_profile_http_api/ -v

# Repository delete() 単体（§確定 E 物理確認）
uv run pytest backend/tests/infrastructure/persistence/sqlite/repositories/test_deliverable_template_repository/ backend/tests/infrastructure/persistence/sqlite/repositories/test_role_profile_repository/ -v -k "delete"

# ユニットテスト（Service 業務ロジック）
uv run pytest backend/tests/unit/test_deliverable_template_service.py backend/tests/unit/test_role_profile_service.py -v
```

## 未決課題・characterization task

| # | 内容 | 起票先 |
|---|---|---|
| 1 | `tests/factories/empire.py` の存在確認（RoleProfileService UT で Empire stub が必要）— **確定済み**: 物理確認済み。`make_empire()` 等を再利用する | 解決済み |
| 2 | 既存 http-api-foundation の `conftest.py` パターン確認— **確定済み**: 既存パターン（`test_directive_http_api/` 等）に `conftest.py` が存在することを確認。各 `test_*_http_api/` ディレクトリに独立 `conftest.py` を配置するパターンを採用 | 解決済み |
| 3 | TC-IT-DTH-003〜004（DAG 循環）の結合テスト構成が複雑（複数 POST が前提）。50 行超過の場合は conftest fixture に前提データ構築を移動する | 実装時判断 |
| characterization | 外部 API 依存なし。SQLite は実接続のため characterization fixture 不要 | — |

## テストケース詳細ファイル

| ファイル | 収録テストケース |
|---|---|
| [`it-deliverable-template-http.md`](it-deliverable-template-http.md) | TC-IT-DTH-001〜021（DeliverableTemplate HTTP API 結合テスト詳細）|
| [`it-role-profile-http.md`](it-role-profile-http.md) | TC-IT-RPH-006 / 007 / 010（RoleProfile HTTP API 主要ケース詳細）|
| [`it-repository.md`](it-repository.md) | TC-IT-DTR-021/022 / TC-IT-RPR-016/017（Repository.delete() 単体）|
| [`ut-service.md`](ut-service.md) | TC-UT-DTS-004〜009 / TC-UT-RPS-004（Service ユニットテスト詳細）|

## 関連

- [`basic-design.md §モジュール契約`](../basic-design.md) — REQ-DT-HTTP-001〜005 / REQ-RP-HTTP-001〜004
- [`detailed-design.md`](../detailed-design.md) — §確定 A〜I / MSG 確定文言 / データ構造
- [`../../feature-spec.md`](../../feature-spec.md) — 親業務仕様（UC-DT-001〜005 / R1-A〜F）
- [`../../system-test-design.md`](../../system-test-design.md) — feature 全体の E2E テスト
- [`../repository/basic-design.md`](../repository/basic-design.md) — Repository Protocol（`delete()` 拡張元）
