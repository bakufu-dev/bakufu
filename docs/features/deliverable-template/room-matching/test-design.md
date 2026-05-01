# テスト設計書 — deliverable-template / room-matching

> feature: `deliverable-template` / sub-feature: `room-matching`
> 関連 Issue: [#120 feat(room-matching): Room matching (107-F)](https://github.com/bakufu-dev/bakufu/issues/120)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../../room/feature-spec.md`](../../room/feature-spec.md) / [`../../room/http-api/basic-design.md`](../../room/http-api/basic-design.md)

## 本書の役割

本書は `basic-design.md §モジュール契約 REQ-RM-MATCH-001〜005` および `detailed-design.md §確定 A〜H` に対応する IT / UT テストケースを凍結する。

**書くこと**:
- `validate_coverage` / `resolve_effective_refs` のユニットテスト（純粋関数 + 境界値）
- `upsert_override` / `delete_override` / `find_overrides` のユニットテスト
- HTTP API 経由（`assign_agent` + RoleOverride CRUD）の結合テスト
- 外部 I/O 依存マップ（factory 状況）

**書かないこと**:
- `validate_coverage` が純粋関数であるため E2E 重複検証は不要。結合テストで充足・不足・override フローの観察で代替
- DB スキーマ migration の直接 assert（alembic autogenerate テストで代替）

## テストケース ID 採番規則

| 番号帯 | 用途 |
|---|---|
| TC-IT-RMM-001〜099 | 結合テスト: HTTP API 経由（assign_agent + RoleOverride CRUD）|
| TC-UT-RMS-001〜099 | ユニットテスト: `RoomMatchingService` 全メソッド |

## テストマトリクス

### 結合テスト（IT）

| 要件 ID | 確定事項 | テストケース ID | 種別 | 対象操作 |
|---|---|---|---|---|
| REQ-RM-MATCH-001 | §確定A, C, E | TC-IT-RMM-001 | 正常系 | assign_agent + カバレッジ充足 → 201 |
| REQ-RM-MATCH-001 | §確定A, E, F | TC-IT-RMM-002 | 異常系 | assign_agent + カバレッジ不足 → 422 |
| REQ-RM-MATCH-001 | §確定C, F | TC-IT-RMM-003 | 異常系 | 422 レスポンスの missing 構造確認 |
| REQ-RM-MATCH-001/002 | §確定B（優先1）| TC-IT-RMM-004 | 正常系 | custom_refs で充足 → 201（RoleProfile より優先）|
| REQ-RM-MATCH-001/002 | §確定B（優先1）| TC-IT-RMM-005 | 異常系 | custom_refs 空タプル + required → 422（空は「提供なし」宣言）|
| REQ-RM-MATCH-001/002 | §確定B（優先2）| TC-IT-RMM-006 | 正常系 | RoomOverride 設定後の assign_agent → override refs で充足 → 201 |
| REQ-RM-MATCH-003 | §確定B（優先2）| TC-IT-RMM-007 | 正常系 | PUT role-overrides/{role} → 201（upsert）|
| REQ-RM-MATCH-003 | — | TC-IT-RMM-008 | 正常系 | PUT role-overrides/{role} 2 回目 → 201（上書き）|
| REQ-RM-MATCH-004 | — | TC-IT-RMM-009 | 正常系 | DELETE role-overrides/{role} → 204 |
| REQ-RM-MATCH-004 | no-op | TC-IT-RMM-010 | 境界値 | DELETE 不在 override → 204（エラーなし）|
| REQ-RM-MATCH-005 | — | TC-IT-RMM-011 | 正常系 | GET role-overrides → 200 一覧 |
| REQ-RM-MATCH-005 | 境界値 | TC-IT-RMM-012 | 境界値 | GET role-overrides → 200 空リスト |

### ユニットテスト（UT）

#### validate_coverage（純粋関数 — I/O なし）

| 要件 ID | 確定事項 | テストケース ID | 種別 | 入力 / 期待 |
|---|---|---|---|---|
| REQ-RM-MATCH-001 | §確定A, E | TC-UT-RMS-001 | 正常系 | 全 Stage 充足 → None |
| REQ-RM-MATCH-001 | 境界値 | TC-UT-RMS-002 | 境界値 | workflow.stages 空 → None |
| REQ-RM-MATCH-001 | §確定E | TC-UT-RMS-003 | 境界値 | optional=True のみ不足 → None（検証対象外）|
| REQ-RM-MATCH-001 | §確定A | TC-UT-RMS-004 | 異常系 | 1 Stage 1 件不足 → RoomDeliverableMatchingError（missing=[1件]）|
| REQ-RM-MATCH-001 | §確定C | TC-UT-RMS-005 | 異常系 | 複数 Stage 複数件不足 → 全不足一括収集（missing=[N件]）|
| REQ-RM-MATCH-001 | §確定A, C | TC-UT-RMS-006 | 境界値 | effective_refs 空タプル + required_deliverable あり → 全件不足 |
| REQ-RM-MATCH-001 | §確定F | TC-UT-RMS-007 | 異常系 | missing 要素の stage_id / stage_name / template_id が正しく設定される |

#### resolve_effective_refs（§確定B フォールバック）

| 要件 ID | 確定事項 | テストケース ID | 種別 | 入力 / 期待 |
|---|---|---|---|---|
| REQ-RM-MATCH-002 | §確定B（優先1）| TC-UT-RMS-008 | 正常系 | custom_refs が not None → リポジトリ呼び出しなしで即返却 |
| REQ-RM-MATCH-002 | §確定B（優先1）| TC-UT-RMS-009 | 境界値 | custom_refs が空タプル → 空タプルをそのまま返す（I/O なし）|
| REQ-RM-MATCH-002 | §確定B（優先2）| TC-UT-RMS-010 | 正常系 | custom_refs=None, RoomOverride あり → override.deliverable_template_refs を返す |
| REQ-RM-MATCH-002 | §確定B（優先3）| TC-UT-RMS-011 | 正常系 | custom_refs=None, RoomOverride なし, RoleProfile あり → role_profile.deliverable_template_refs を返す |
| REQ-RM-MATCH-002 | §確定B（優先4）| TC-UT-RMS-012 | 境界値 | custom_refs=None, 両方なし → 空タプルを返す |
| REQ-RM-MATCH-002 | §確定B 優先順位 | TC-UT-RMS-013 | 境界値 | RoomOverride が存在するとき RoleProfile は参照されない（短絡評価） |

#### upsert_override

| 要件 ID | 確定事項 | テストケース ID | 種別 | 入力 / 期待 |
|---|---|---|---|---|
| REQ-RM-MATCH-003 | — | TC-UT-RMS-014 | 異常系 | Room 不在 → RoomNotFoundError |
| REQ-RM-MATCH-003 | — | TC-UT-RMS-015 | 異常系 | Room archived → RoomArchivedError |
| REQ-RM-MATCH-003 | — | TC-UT-RMS-016 | 正常系 | 正常 upsert → RoomRoleOverride を返す（room_id / role 一致） |

#### delete_override

| 要件 ID | 確定事項 | テストケース ID | 種別 | 入力 / 期待 |
|---|---|---|---|---|
| REQ-RM-MATCH-004 | — | TC-UT-RMS-017 | 異常系 | Room 不在 → RoomNotFoundError |
| REQ-RM-MATCH-004 | no-op | TC-UT-RMS-018 | 境界値 | override 不在 → no-op（例外なし）|

#### find_overrides

| 要件 ID | 確定事項 | テストケース ID | 種別 | 入力 / 期待 |
|---|---|---|---|---|
| REQ-RM-MATCH-005 | — | TC-UT-RMS-019 | 異常系 | Room 不在 → RoomNotFoundError |
| REQ-RM-MATCH-005 | 境界値 | TC-UT-RMS-020 | 境界値 | 空リスト → 正常（[] を返す）|

## テストケース詳細

### 結合テスト（IT）

---

#### TC-IT-RMM-001: assign_agent + カバレッジ充足 → 201

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定A, E）/ UC-RM-015 |
| 種別 | 正常系 |
| 前提条件 | Empire / Room / Workflow（Stage に required_deliverable optional=False あり）/ Agent 存在。RoleProfile に対象 template_id を持つ deliverable_template_refs が設定済み |
| 操作 | `PUT /api/rooms/{room_id}/assign-agent` body: `{agent_id, role, custom_refs: null}` |
| 期待結果 | HTTP 201。Room に Agent が正しく割り当てられる（ラウンドトリップで GET により確認）|

---

#### TC-IT-RMM-002: assign_agent + カバレッジ不足 → 422

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定A, E, F）/ UC-RM-015 / R1-11 |
| 種別 | 異常系 |
| 前提条件 | Empire / Room / Workflow（Stage に required_deliverable optional=False あり）/ Agent 存在。RoleProfile の deliverable_template_refs が空（カバレッジ不足状態）|
| 操作 | `PUT /api/rooms/{room_id}/assign-agent` body: `{agent_id, role}` |
| 期待結果 | HTTP 422。`error.code == "deliverable_matching_failed"` |

---

#### TC-IT-RMM-003: 422 レスポンスの missing 構造確認

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定C, F）|
| 種別 | 異常系（構造検証）|
| 前提条件 | TC-IT-RMM-002 と同じ設定 |
| 操作 | `PUT /api/rooms/{room_id}/assign-agent`（カバレッジ不足）|
| 期待結果 | `error.detail.missing[0]` に `stage_id` / `stage_name` / `template_id` が全て含まれる。`error.detail.role` が割り当て対象 role と一致 |

---

#### TC-IT-RMM-004: custom_refs で充足 → 201（RoleProfile より優先）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001/002（§確定B 優先1）/ UC-RM-015 |
| 種別 | 正常系 |
| 前提条件 | RoleProfile の deliverable_template_refs は空（§確定B 優先3 = 充足しない状態）。Workflow に required_deliverable optional=False あり |
| 操作 | `PUT /api/rooms/{room_id}/assign-agent` body: `{agent_id, role, custom_refs: [{template_id: <required_id>, minimum_version: {...}}]}` |
| 期待結果 | HTTP 201。custom_refs が RoleProfile より優先されマッチング成功 |

---

#### TC-IT-RMM-005: custom_refs 空タプル + required → 422

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001/002（§確定B 優先1）|
| 種別 | 異常系 |
| 前提条件 | RoleProfile には充足する refs あり（デフォルトでは成功する状態）。Workflow に required optional=False あり |
| 操作 | `custom_refs: []`（空タプル = 明示的な「提供なし」宣言）で assign_agent |
| 期待結果 | HTTP 422。`custom_refs=[]` は RoleProfile を無視し「提供しない」を宣言するため不足 |

---

#### TC-IT-RMM-006: RoomOverride 設定後の assign_agent → override refs で充足 → 201

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001/002（§確定B 優先2）|
| 種別 | 正常系 |
| 前提条件 | RoleProfile の refs は空（充足しない）。RoomOverride に required template_id を設定済み |
| 操作 | `PUT /api/rooms/{room_id}/assign-agent` body: `{agent_id, role, custom_refs: null}` |
| 期待結果 | HTTP 201。RoomOverride が RoleProfile より優先され充足 |

---

#### TC-IT-RMM-007: PUT role-overrides/{role} → 201（upsert）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-003 / UC-RM-016 |
| 種別 | 正常系 |
| 前提条件 | Room 存在（archived でない）|
| 操作 | `PUT /api/rooms/{room_id}/role-overrides/{role}` body: `{deliverable_template_refs: [...]}` |
| 期待結果 | HTTP 201。GET role-overrides でラウンドトリップ確認 |

---

#### TC-IT-RMM-008: PUT role-overrides/{role} 2 回目 → 201（上書き）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-003（idempotent upsert）|
| 種別 | 正常系 |
| 前提条件 | RoomOverride が既に存在する状態 |
| 操作 | 同じ role で異なる refs を PUT |
| 期待結果 | HTTP 201。GET で新しい refs に上書きされていることを確認 |

---

#### TC-IT-RMM-009: DELETE role-overrides/{role} → 204

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-004 / UC-RM-016 |
| 種別 | 正常系 |
| 前提条件 | RoomOverride が存在する状態 |
| 操作 | `DELETE /api/rooms/{room_id}/role-overrides/{role}` |
| 期待結果 | HTTP 204。GET role-overrides でその role のエントリが消えていることを確認 |

---

#### TC-IT-RMM-010: DELETE 不在 override → 204（no-op）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-004（no-op 仕様）|
| 種別 | 境界値 |
| 前提条件 | 対象 role の RoomOverride が存在しない |
| 操作 | `DELETE /api/rooms/{room_id}/role-overrides/{role}` |
| 期待結果 | HTTP 204。エラーなし（no-op）|

---

#### TC-IT-RMM-011: GET role-overrides → 200 一覧

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-005 / UC-RM-017 |
| 種別 | 正常系 |
| 前提条件 | 2 件以上の RoomOverride が設定済み |
| 操作 | `GET /api/rooms/{room_id}/role-overrides` |
| 期待結果 | HTTP 200。`items` が登録件数分含まれ、各要素に `role` / `deliverable_template_refs` が含まれる |

---

#### TC-IT-RMM-012: GET role-overrides → 200 空リスト

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-005（境界値）|
| 種別 | 境界値 |
| 前提条件 | RoomOverride が 0 件 |
| 操作 | `GET /api/rooms/{room_id}/role-overrides` |
| 期待結果 | HTTP 200。`items: []`（空リストも正常）|

---

### ユニットテスト（UT）

#### TC-UT-RMS-001: validate_coverage — 全 Stage 充足 → None

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定A, E）|
| 種別 | 正常系 |
| 前提条件 | Workflow に 2 Stage。各 Stage に required_deliverable（optional=False）が 1 件。effective_refs に両方の template_id を含む |
| 操作 | `service.validate_coverage(workflow, role, effective_refs)` |
| 期待結果 | 例外なし（None を返す）|

---

#### TC-UT-RMS-002: validate_coverage — workflow.stages 空 → None

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（境界値）|
| 種別 | 境界値 |
| 前提条件 | Workflow の stages が空リスト |
| 操作 | `service.validate_coverage(workflow_with_no_stages, role, effective_refs)` |
| 期待結果 | 例外なし（None を返す）|

---

#### TC-UT-RMS-003: validate_coverage — optional=True のみ不足 → None（§確定E）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定E）|
| 種別 | 境界値 |
| 前提条件 | Stage に `optional=True` の required_deliverable のみ。effective_refs は空タプル |
| 操作 | `service.validate_coverage(workflow, role, effective_refs=())` |
| 期待結果 | 例外なし。optional=True は検証対象外 |

---

#### TC-UT-RMS-004: validate_coverage — 1 Stage 1 件不足 → RoomDeliverableMatchingError

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定A）|
| 種別 | 異常系 |
| 前提条件 | Stage に optional=False の required_deliverable 1 件。effective_refs はその template_id を含まない |
| 操作 | `service.validate_coverage(workflow, role, effective_refs)` |
| 期待結果 | `RoomDeliverableMatchingError` が raise される。`exc.missing` の長さが 1 |

---

#### TC-UT-RMS-005: validate_coverage — 複数 Stage 複数件不足 → 全不足一括収集（§確定C）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定C）|
| 種別 | 異常系 |
| 前提条件 | 2 Stage × 各 2 件の required_deliverable（optional=False）。effective_refs は空 |
| 操作 | `service.validate_coverage(workflow, role, effective_refs=())` |
| 期待結果 | `RoomDeliverableMatchingError` が raise される。`exc.missing` の長さが 4（全件収集、第一発見で止まらない）|

---

#### TC-UT-RMS-006: validate_coverage — effective_refs 空タプル + required あり → 全件不足

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（境界値）|
| 種別 | 境界値 |
| 前提条件 | Stage 1 件 / required_deliverable 1 件（optional=False）。effective_refs=() |
| 操作 | `service.validate_coverage(workflow, role, effective_refs=())` |
| 期待結果 | `RoomDeliverableMatchingError` が raise される |

---

#### TC-UT-RMS-007: validate_coverage — missing 要素の属性が正しく設定される

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定F）|
| 種別 | 異常系（構造検証）|
| 前提条件 | TC-UT-RMS-004 と同設定 |
| 操作 | `service.validate_coverage(...)` → RoomDeliverableMatchingError をキャッチ |
| 期待結果 | `exc.missing[0].stage_id` / `exc.missing[0].stage_name` / `exc.missing[0].template_id` が期待値と一致 |

---

#### TC-UT-RMS-008: resolve_effective_refs — custom_refs not None → 即返却（優先1）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-002（§確定B 優先1）|
| 種別 | 正常系 |
| 前提条件 | override_repo / role_profile_repo は AsyncMock（呼ばれないことを確認する）|
| 操作 | `await service.resolve_effective_refs(room_id, empire_id, role, custom_refs=<non_empty_tuple>)` |
| 期待結果 | custom_refs がそのまま返る。`_override_repo.find_by_room_and_role` は呼ばれない |

---

#### TC-UT-RMS-009: resolve_effective_refs — custom_refs 空タプル → 空タプルを返す（優先1）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-002（§確定B 優先1: 空タプルは有効な指定）|
| 種別 | 境界値 |
| 前提条件 | override_repo に override あり（呼ばれれば値が返るはずだが呼ばれない）|
| 操作 | `await service.resolve_effective_refs(..., custom_refs=())` |
| 期待結果 | 空タプル `()` が返る。override_repo は呼ばれない |

---

#### TC-UT-RMS-010: resolve_effective_refs — RoomOverride あり → override.refs（優先2）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-002（§確定B 優先2）|
| 種別 | 正常系 |
| 前提条件 | `_override_repo.find_by_room_and_role` が `make_room_role_override()` を返す |
| 操作 | `await service.resolve_effective_refs(..., custom_refs=None)` |
| 期待結果 | override の `deliverable_template_refs` が返る。`role_profile_repo` は呼ばれない |

---

#### TC-UT-RMS-011: resolve_effective_refs — RoomOverride なし / RoleProfile あり → role_profile.refs（優先3）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-002（§確定B 優先3）|
| 種別 | 正常系 |
| 前提条件 | override_repo は None を返す。role_profile_repo は `make_role_profile()` を返す |
| 操作 | `await service.resolve_effective_refs(..., custom_refs=None)` |
| 期待結果 | role_profile の `deliverable_template_refs` が返る |

---

#### TC-UT-RMS-012: resolve_effective_refs — 両方なし → 空タプル（優先4/フォールバック）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-002（§確定B 優先4）|
| 種別 | 境界値 |
| 前提条件 | override_repo は None を返す。role_profile_repo は None を返す |
| 操作 | `await service.resolve_effective_refs(..., custom_refs=None)` |
| 期待結果 | 空タプル `()` が返る（例外なし）|

---

#### TC-UT-RMS-013: resolve_effective_refs — RoomOverride 存在時 RoleProfile は参照されない（短絡評価）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-002（§確定B 優先順位の短絡評価）|
| 種別 | 境界値 |
| 前提条件 | override_repo が override を返す。role_profile_repo はモック（呼ばれれば検出できる）|
| 操作 | `await service.resolve_effective_refs(..., custom_refs=None)` |
| 期待結果 | `_role_profile_repo.find_by_empire_and_role` が一度も呼ばれない |

---

#### TC-UT-RMS-014: upsert_override — Room 不在 → RoomNotFoundError

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-003 |
| 種別 | 異常系 |
| 前提条件 | `_room_repo.find_by_id` が None を返す |
| 操作 | `await service.upsert_override(room_id, role, refs)` |
| 期待結果 | `RoomNotFoundError` が raise される |

---

#### TC-UT-RMS-015: upsert_override — Room archived → RoomArchivedError

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-003 |
| 種別 | 異常系 |
| 前提条件 | `_room_repo.find_by_id` が `make_archived_room()` を返す |
| 操作 | `await service.upsert_override(room_id, role, refs)` |
| 期待結果 | `RoomArchivedError` が raise される |

---

#### TC-UT-RMS-016: upsert_override — 正常 → RoomRoleOverride 返却

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-003 |
| 種別 | 正常系 |
| 前提条件 | `_room_repo.find_by_id` が正常 Room を返す。`_override_repo.save` は AsyncMock |
| 操作 | `await service.upsert_override(room_id, role, refs=make_refs())` |
| 期待結果 | 返り値の `room_id` / `role` が引数と一致する `RoomRoleOverride` |

---

#### TC-UT-RMS-017: delete_override — Room 不在 → RoomNotFoundError

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-004 |
| 種別 | 異常系 |
| 前提条件 | `_room_repo.find_by_id` が None を返す |
| 操作 | `await service.delete_override(room_id, role)` |
| 期待結果 | `RoomNotFoundError` が raise される |

---

#### TC-UT-RMS-018: delete_override — override 不在 → no-op（例外なし）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-004（no-op 仕様）|
| 種別 | 境界値 |
| 前提条件 | Room は存在。`_override_repo.delete` は何も返さない AsyncMock |
| 操作 | `await service.delete_override(room_id, role)` |
| 期待結果 | 例外なし。None を返す |

---

#### TC-UT-RMS-019: find_overrides — Room 不在 → RoomNotFoundError

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-005 |
| 種別 | 異常系 |
| 前提条件 | `_room_repo.find_by_id` が None を返す |
| 操作 | `await service.find_overrides(room_id)` |
| 期待結果 | `RoomNotFoundError` が raise される |

---

#### TC-UT-RMS-020: find_overrides — 空リスト → 正常（境界値）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-005（境界値）|
| 種別 | 境界値 |
| 前提条件 | Room は存在。`_override_repo.find_all_by_room` が `[]` を返す |
| 操作 | `await service.find_overrides(room_id)` |
| 期待結果 | `[]` が返る（例外なし）|

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | 状態 |
|---|---|---|---|---|
| SQLite（テスト用 DB）| IT 全ケース: 実 DB を使用 | `tmp_path` 配下 DB | `tests/factories/db.py`（実装済み）| ✅ 済 |
| `RoomRepository` | UT mock: Room 存在確認 / archived 確認 | — | `tests/factories/room.py` `make_room()` / `make_archived_room()`（実装済み）| ✅ 済 |
| `WorkflowRepository` | UT mock: Workflow.stages 取得 | — | `tests/factories/workflow.py` `make_workflow()` / `make_stage()`（実装済み）| ✅ 済 |
| `RoleProfileRepository` | UT mock: empire-level RoleProfile 取得 | — | `tests/factories/deliverable_template.py` `make_role_profile()`（実装済み）| ✅ 済 |
| `RoomRoleOverrideRepository` | UT mock: Room-level override 取得 / save / delete | — | `tests/factories/room.py` への `make_room_role_override()` 追加（**要作成**）| ⚠️ 要起票 |
| `Workflow` with `required_deliverables` | UT: validate_coverage のテスト用 Workflow 生成 | — | `tests/factories/workflow.py` への `make_stage_with_deliverables(required_deliverables=...)` 追加（**要作成**）| ⚠️ 要起票 |
| FastAPI ASGI | IT: HTTP リクエスト送信 | — | — | ✅ 既存パターン踏襲 |

### factory 要作成タスク（実装工程前に完了必須）

実装工程（ヴァンロッサム担当）着手前に以下の factory を追加する必要がある:

| factory | 追加先ファイル | 生成するもの | 必要ケース |
|---|---|---|---|
| `make_room_role_override(room_id, role, refs)` | `tests/factories/room.py` | `RoomRoleOverride` VO | TC-UT-RMS-010/013/016 |
| `make_stage_with_deliverables(optional=False, ...)` | `tests/factories/workflow.py` | `required_deliverables` を持つ `Stage` | TC-UT-RMS-001/003〜007 |

これらのオブジェクトは外部 API を呼ばないため characterization fixture は不要。factory 生成のみ。

## モック方針

| メソッド | テストレベル | モック対象 | モック手段 |
|---|---|---|---|
| `validate_coverage` | UT | なし（純粋関数）| モック不要。factories で Workflow / refs を直接構築 |
| `resolve_effective_refs` | UT | `_override_repo.find_by_room_and_role` / `_role_profile_repo.find_by_empire_and_role` | `AsyncMock` + factory 返却値 |
| `upsert_override` | UT | `_room_repo.find_by_id` / `_override_repo.save` | `AsyncMock` + factory 返却値 |
| `delete_override` | UT | `_room_repo.find_by_id` / `_override_repo.delete` | `AsyncMock` |
| `find_overrides` | UT | `_room_repo.find_by_id` / `_override_repo.find_all_by_room` | `AsyncMock` |
| 全メソッド | IT | なし（DB 実接続）| テスト用 SQLite `tmp_path` DB |

**重要**: UT では `AsyncMock.return_value` にインライン辞書リテラルを使わない。必ず factory（`make_room_role_override()` / `make_role_profile()` 等）経由で生成したオブジェクトを返却値とする（assumed mock 禁止）。

## カバレッジ基準

- REQ-RM-MATCH-001〜005 の全正常系を IT または UT で 1 件以上検証する
- §確定 B（3 段フォールバック）の全 4 分岐（custom_refs / override / role_profile / 空）を UT で確認する
- §確定 C（全不足一括収集）を UT で Stage × 複数不足 ケースで確認する
- §確定 E（optional=True 除外）を境界値 UT で確認する
- IT では HTTP ステータスコード・レスポンス構造（`error.code` / `error.detail.missing`）を具体的に assert してよい（contract testing）
- DB を直接 assert しない。ラウンドトリップ（PUT → GET）で確認する

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全ジョブ緑であること
- ローカル確認:
  ```sh
  # UT
  uv run pytest backend/tests/unit/test_room_matching_service.py -v
  # IT
  uv run pytest backend/tests/integration/test_room_matching_http_api/ -v
  ```
