# ユニットテストケース詳細 — DeliverableTemplateService / RoleProfileService

> TC-UT-DTS-001〜009 / TC-UT-RPS-001〜006（主要ケースのみ詳細記載。他は index.md マトリクスを参照）
> 関連: [`index.md`](index.md) / [`../detailed-design.md §確定B/C/D/E`](../detailed-design.md)

## TC-UT-DTS-004: _check_dag 深度上限 10 超 → CompositionCycleError（§確定 D）

| 項目 | 内容 |
|---|---|
| 対応 | §確定 D |
| 種別 | 境界値 |
| モック | `DeliverableTemplateRepository.find_by_id` が 11 段のチェーンを返す（depth 11 で上限 10 超）|
| 操作 | `_check_dag(refs=[chain_start], root_id=...)` ※ 2 引数。depth / visited は内部局所状態（§確定 D 確定済み）|
| 期待結果 | `CompositionCycleError` raise。`err.reason == "depth_limit"` かつ `err.cycle_path == []` |

## TC-UT-DTS-005: _check_dag ノード上限 100 超 → CompositionCycleError（§確定 D）

| 項目 | 内容 |
|---|---|
| 対応 | §確定 D |
| 種別 | 境界値 |
| モック | `DeliverableTemplateRepository.find_by_id` が 101 ノードの幅広グラフを返す（各ノードが 1 段の子を持つ星型など）|
| 操作 | `_check_dag(refs=[...], root_id=...)` ※ 2 引数。visited の内部カウントが 100 超で打ち切り |
| 期待結果 | `CompositionCycleError` raise。`err.reason == "node_limit"` かつ `err.cycle_path == []` |

## TC-UT-DTS-006: update — version 降格 → DeliverableTemplateVersionDowngradeError（§確定 B）

| 項目 | 内容 |
|---|---|
| 対応 | §確定 B |
| 種別 | 異常系 |
| モック | `find_by_id` が version 2.0.0 の template を返す |
| 操作 | `update(id, ..., version=SemVer(major=1, minor=0, patch=0), ...)` |
| 期待結果 | `DeliverableTemplateVersionDowngradeError` raise。`current_version == "2.0.0"` / `provided_version == "1.0.0"` |

## TC-UT-DTS-007: update — version 同一 → create_new_version を呼ばない（§確定 B）

| 項目 | 内容 |
|---|---|
| 対応 | §確定 B |
| 種別 | 正常系 |
| モック | `find_by_id` が version 1.0.0 の template を返す。`template.create_new_version` に spy を設定 |
| 操作 | `update(id, ..., version=SemVer(major=1, minor=0, patch=0), ...)` |
| 期待結果 | 例外なし。`create_new_version` は呼ばれない |

## TC-UT-RPS-004: upsert — 既存あり → 既存 id 保持（§確定 C）

| 項目 | 内容 |
|---|---|
| 対応 | §確定 C |
| 種別 | 正常系 |
| モック | `find_by_empire_and_role` が既存の RoleProfile（`id=existing_id`）を返す |
| 操作 | `upsert(empire_id, role, refs=[])` |
| 期待結果 | `save` に渡された RoleProfile の `id == existing_id`（既存 id を継承）|
