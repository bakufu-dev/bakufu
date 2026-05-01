# テスト設計書（ユニットテスト）— deliverable-template / room-matching

> feature: `deliverable-template` / sub-feature: `room-matching`
> 関連 Issue: [#120 feat(room-matching): Room matching (107-F)](https://github.com/bakufu-dev/bakufu/issues/120)
> インデックス: [`index.md`](index.md) / IT: [`it.md`](it.md)

## ユニットテスト（UT）— TC-UT-RMS-001〜020

TC-UT-RMS-001〜013 は `RoomMatchingService`、TC-UT-RMS-014〜020 は `RoomRoleOverrideService` のテストケースである。

---

## validate_coverage（RoomMatchingService — 純粋関数・I/O なし）

`validate_coverage(workflow, effective_refs)` は同期純粋関数。`role` を引数として受け取らない（§詳細設計 §確定G 参照）。

---

### TC-UT-RMS-001: validate_coverage — 全 Stage 充足 → []

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定A, E）|
| 種別 | 正常系 |
| 前提条件 | Workflow に 2 Stage。各 Stage に required_deliverable（optional=False）が 1 件。effective_refs に両方の template_id を含む（`make_stage_with_deliverables()` factory 使用）|
| 操作 | `service.validate_coverage(workflow, effective_refs)` |
| 期待結果 | 空リスト `[]` が返る（例外なし）|

---

### TC-UT-RMS-002: validate_coverage — workflow.stages 空 → []

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（境界値）|
| 種別 | 境界値 |
| 前提条件 | Workflow の stages が空リスト |
| 操作 | `service.validate_coverage(workflow_with_no_stages, effective_refs)` |
| 期待結果 | 空リスト `[]` が返る（例外なし）|

---

### TC-UT-RMS-003: validate_coverage — optional=True のみ不足 → []（§確定E）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定E）|
| 種別 | 境界値 |
| 前提条件 | Stage に `optional=True` の required_deliverable のみ。effective_refs は空タプル（`make_stage_with_deliverables(optional=True)` factory 使用）|
| 操作 | `service.validate_coverage(workflow, effective_refs=())` |
| 期待結果 | 空リスト `[]` が返る。optional=True は検証対象外 |

---

### TC-UT-RMS-004: validate_coverage — 1 Stage 1 件不足 → missing=[1件]

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定A）|
| 種別 | 異常系 |
| 前提条件 | Stage に optional=False の required_deliverable 1 件。effective_refs はその template_id を含まない（`make_stage_with_deliverables(optional=False)` factory 使用）|
| 操作 | `service.validate_coverage(workflow, effective_refs)` |
| 期待結果 | 長さ 1 の `list[RoomDeliverableMismatch]` が返る |

---

### TC-UT-RMS-005: validate_coverage — 複数 Stage 複数件不足 → 全不足一括収集（§確定C）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定C）|
| 種別 | 異常系 |
| 前提条件 | 2 Stage × 各 2 件の required_deliverable（optional=False）。effective_refs は空 |
| 操作 | `service.validate_coverage(workflow, effective_refs=())` |
| 期待結果 | 長さ 4 の `list[RoomDeliverableMismatch]` が返る（全件収集、第一発見で止まらない）|

---

### TC-UT-RMS-006: validate_coverage — effective_refs 空タプル + required あり → 全件不足

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（境界値）|
| 種別 | 境界値 |
| 前提条件 | Stage 1 件 / required_deliverable 1 件（optional=False）。effective_refs=() |
| 操作 | `service.validate_coverage(workflow, effective_refs=())` |
| 期待結果 | 長さ 1 以上の `list[RoomDeliverableMismatch]` が返る |

---

### TC-UT-RMS-007: validate_coverage — missing 要素の属性が正しく設定される

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定F）|
| 種別 | 異常系（構造検証）|
| 前提条件 | TC-UT-RMS-004 と同設定。Stage の stage_id / stage_name / required template_id が既知の値 |
| 操作 | `result = service.validate_coverage(...)` |
| 期待結果 | `result[0].stage_id` / `result[0].stage_name` / `result[0].template_id` が期待値と一致 |

---

## resolve_effective_refs（RoomMatchingService — §確定B フォールバック）

`resolve_effective_refs(room_id, empire_id, role, custom_refs)` は async。

---

### TC-UT-RMS-008: resolve_effective_refs — custom_refs not None → 即返却（優先1）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-002（§確定B 優先1）|
| 種別 | 正常系 |
| 前提条件 | override_repo / role_profile_repo は AsyncMock（呼ばれないことを確認する）|
| 操作 | `await service.resolve_effective_refs(room_id, empire_id, role, custom_refs=<non_empty_tuple>)` |
| 期待結果 | custom_refs がそのまま返る。`_override_repo.find_by_room_and_role` は呼ばれない |

---

### TC-UT-RMS-009: resolve_effective_refs — custom_refs 空タプル → 空タプルを返す（優先1）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-002（§確定B 優先1: 空タプルは有効な指定）|
| 種別 | 境界値 |
| 前提条件 | override_repo に override あり（呼ばれれば値が返るはずだが呼ばれない）|
| 操作 | `await service.resolve_effective_refs(..., custom_refs=())` |
| 期待結果 | 空タプル `()` が返る。override_repo は呼ばれない |

---

### TC-UT-RMS-010: resolve_effective_refs — RoomOverride あり → override.refs（優先2）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-002（§確定B 優先2）|
| 種別 | 正常系 |
| 前提条件 | `_override_repo.find_by_room_and_role` が `make_room_role_override()` の返却値を返す（⚠️ factory 要作成）|
| 操作 | `await service.resolve_effective_refs(..., custom_refs=None)` |
| 期待結果 | override の `deliverable_template_refs` が返る。`role_profile_repo` は呼ばれない |

---

### TC-UT-RMS-011: resolve_effective_refs — RoomOverride なし / RoleProfile あり → role_profile.refs（優先3）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-002（§確定B 優先3）|
| 種別 | 正常系 |
| 前提条件 | override_repo は None を返す。role_profile_repo は `make_role_profile()` を返す |
| 操作 | `await service.resolve_effective_refs(..., custom_refs=None)` |
| 期待結果 | role_profile の `deliverable_template_refs` が返る |

---

### TC-UT-RMS-012: resolve_effective_refs — 両方なし → 空タプル（優先4/フォールバック）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-002（§確定B 優先4）|
| 種別 | 境界値 |
| 前提条件 | override_repo は None を返す。role_profile_repo は None を返す |
| 操作 | `await service.resolve_effective_refs(..., custom_refs=None)` |
| 期待結果 | 空タプル `()` が返る（例外なし）|

---

### TC-UT-RMS-013: resolve_effective_refs — RoomOverride 存在時 RoleProfile は参照されない（短絡評価）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-002（§確定B 優先順位の短絡評価）|
| 種別 | 境界値 |
| 前提条件 | override_repo が `make_room_role_override()` を返す（⚠️ factory 要作成）。role_profile_repo はモック（呼ばれれば検出できる）|
| 操作 | `await service.resolve_effective_refs(..., custom_refs=None)` |
| 期待結果 | `_role_profile_repo.find_by_empire_and_role` が一度も呼ばれない |

---

## upsert_override（RoomRoleOverrideService）

---

### TC-UT-RMS-014: upsert_override — Room 不在 → RoomNotFoundError

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-003 |
| 種別 | 異常系 |
| 前提条件 | `_room_repo.find_by_id` が None を返す |
| 操作 | `await service.upsert_override(room_id, role, refs)` |
| 期待結果 | `RoomNotFoundError` が raise される |

---

### TC-UT-RMS-015: upsert_override — Room archived → RoomArchivedError

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-003 |
| 種別 | 異常系 |
| 前提条件 | `_room_repo.find_by_id` が `make_archived_room()` を返す |
| 操作 | `await service.upsert_override(room_id, role, refs)` |
| 期待結果 | `RoomArchivedError` が raise される |

---

### TC-UT-RMS-016: upsert_override — 正常 → RoomRoleOverride 返却

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-003 |
| 種別 | 正常系 |
| 前提条件 | `_room_repo.find_by_id` が正常 Room を返す。`_override_repo.save` は AsyncMock（⚠️ `make_room_role_override()` factory 要作成）|
| 操作 | `await service.upsert_override(room_id, role, refs=make_refs())` |
| 期待結果 | 返り値の `room_id` / `role` が引数と一致する `RoomRoleOverride` |

---

## delete_override（RoomRoleOverrideService）

---

### TC-UT-RMS-017: delete_override — Room 不在 → RoomNotFoundError

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-004 |
| 種別 | 異常系 |
| 前提条件 | `_room_repo.find_by_id` が None を返す |
| 操作 | `await service.delete_override(room_id, role)` |
| 期待結果 | `RoomNotFoundError` が raise される |

---

### TC-UT-RMS-018: delete_override — override 不在 → no-op（例外なし）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-004（no-op 仕様）|
| 種別 | 境界値 |
| 前提条件 | Room は存在。`_override_repo.delete` は何も返さない AsyncMock |
| 操作 | `await service.delete_override(room_id, role)` |
| 期待結果 | 例外なし。None を返す |

---

## find_overrides（RoomRoleOverrideService）

---

### TC-UT-RMS-019: find_overrides — Room 不在 → RoomNotFoundError

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-005 |
| 種別 | 異常系 |
| 前提条件 | `_room_repo.find_by_id` が None を返す |
| 操作 | `await service.find_overrides(room_id)` |
| 期待結果 | `RoomNotFoundError` が raise される |

---

### TC-UT-RMS-020: find_overrides — 空リスト → 正常（境界値）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-005（境界値）|
| 種別 | 境界値 |
| 前提条件 | Room は存在。`_override_repo.find_all_by_room` が `[]` を返す |
| 操作 | `await service.find_overrides(room_id)` |
| 期待結果 | `[]` が返る（例外なし）|
