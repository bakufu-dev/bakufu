# 結合テストケース詳細 — Repository.delete() 単体（§確定 E 物理確認）

> TC-IT-DTR-021/022 / TC-IT-RPR-016/017
> 関連: [`index.md`](index.md) / [`../basic-design.md §確定E`](../basic-design.md) / [`../detailed-design.md §確定E`](../detailed-design.md)

## 設計判断

HTTP DELETE（TC-IT-DTH-016/017 / TC-IT-RPH-011/012）では Service 経由でのエンドツーエンド確認を行う。Repository.delete() の no-op 挙動（存在しない id でも例外なし）は HTTP 層と分離して物理確認する必要があるため、TC-IT-DTR-021/022 / TC-IT-RPR-016/017 を Repository 直接呼び出しテストとして追加する。

## TC-IT-DTR-021: SqliteDeliverableTemplateRepository.delete() — 存在する id → 行削除

| 項目 | 内容 |
|---|---|
| 対応 | §確定 E / REQ-DT-HTTP-005 |
| テストレベル | IT（Repository 直接呼び出し）|
| 種別 | 正常系 |
| 前提条件 | テスト用 SQLite DB に `DeliverableTemplate` が 1 件 INSERT 済み（Alembic upgrade head 適用済み）|
| 操作 | `await repository.delete(template.id)` |
| 期待結果 | 例外なし。`await repository.find_by_id(template.id)` が `None` を返す（物理削除確認）|
| 配置ファイル | `tests/infrastructure/persistence/sqlite/repositories/test_deliverable_template_repository/test_crud/test_protocol_and_crud.py` |

## TC-IT-DTR-022: SqliteDeliverableTemplateRepository.delete() — 存在しない id → no-op

| 項目 | 内容 |
|---|---|
| 対応 | §確定 E / REQ-DT-HTTP-005 |
| テストレベル | IT（Repository 直接呼び出し）|
| 種別 | 異常系 |
| 前提条件 | DB 空 |
| 操作 | `await repository.delete(uuid4())` |
| 期待結果 | 例外なし（no-op）。DB に変化なし |
| 配置ファイル | `tests/infrastructure/persistence/sqlite/repositories/test_deliverable_template_repository/test_crud/test_protocol_and_crud.py` |

## TC-IT-RPR-016: SqliteRoleProfileRepository.delete() — 存在する id → 行削除

| 項目 | 内容 |
|---|---|
| 対応 | §確定 E / REQ-RP-HTTP-004 |
| テストレベル | IT（Repository 直接呼び出し）|
| 種別 | 正常系 |
| 前提条件 | テスト用 SQLite DB に `RoleProfile` が 1 件 INSERT 済み |
| 操作 | `await repository.delete(profile.id)` |
| 期待結果 | 例外なし。`await repository.find_by_id(profile.id)` が `None` を返す（物理削除確認）|
| 配置ファイル | `tests/infrastructure/persistence/sqlite/repositories/test_role_profile_repository/test_crud/test_crud_basic.py` |

## TC-IT-RPR-017: SqliteRoleProfileRepository.delete() — 存在しない id → no-op

| 項目 | 内容 |
|---|---|
| 対応 | §確定 E / REQ-RP-HTTP-004 |
| テストレベル | IT（Repository 直接呼び出し）|
| 種別 | 異常系 |
| 前提条件 | DB 空 |
| 操作 | `await repository.delete(uuid4())` |
| 期待結果 | 例外なし（no-op）。DB に変化なし |
| 配置ファイル | `tests/infrastructure/persistence/sqlite/repositories/test_role_profile_repository/test_crud/test_crud_basic.py` |
