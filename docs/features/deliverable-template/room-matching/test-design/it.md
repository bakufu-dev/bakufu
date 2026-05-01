# テスト設計書（結合テスト）— deliverable-template / room-matching

> feature: `deliverable-template` / sub-feature: `room-matching`
> 関連 Issue: [#120 feat(room-matching): Room matching (107-F)](https://github.com/bakufu-dev/bakufu/issues/120)
> インデックス: [`index.md`](index.md) / UT: [`ut.md`](ut.md)

## 結合テスト（IT）— TC-IT-RMM-001〜012

結合テストは実際の SQLite DB（`tmp_path` 配下）と FastAPI ASGI クライアントを使用する。外部モックは使用しない。

---

### TC-IT-RMM-001: assign_agent + カバレッジ充足 → 201

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定A, E）/ UC-RM-015 |
| 種別 | 正常系 |
| 前提条件 | Empire / Room / Workflow（Stage に required_deliverable optional=False あり）/ Agent 存在。RoleProfile に対象 template_id を持つ deliverable_template_refs が設定済み |
| 操作 | `POST /api/rooms/{room_id}/agents` body: `{"agent_id": ..., "role": ..., "custom_refs": null}` |
| 期待結果 | HTTP 201。Room に Agent が正しく割り当てられる（ラウンドトリップで GET により確認）|

---

### TC-IT-RMM-002: assign_agent + カバレッジ不足 → 422

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定A, E, F）/ UC-RM-015 / R1-11 |
| 種別 | 異常系 |
| 前提条件 | Empire / Room / Workflow（Stage に required_deliverable optional=False あり）/ Agent 存在。RoleProfile の deliverable_template_refs が空（カバレッジ不足状態）|
| 操作 | `POST /api/rooms/{room_id}/agents` body: `{"agent_id": ..., "role": ...}` |
| 期待結果 | HTTP 422。`error.code == "deliverable_matching_failed"` |

---

### TC-IT-RMM-003: 422 レスポンスの missing 構造確認

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001（§確定C, F）|
| 種別 | 異常系（構造検証）|
| 前提条件 | TC-IT-RMM-002 と同じ設定 |
| 操作 | `POST /api/rooms/{room_id}/agents`（カバレッジ不足）|
| 期待結果 | `error.detail.room_id` が対象 Room の UUID と一致する。`error.detail.role` が割り当て対象 role と一致する。`error.detail.missing[0]` に `stage_id` / `stage_name` / `template_id` が全て含まれる |

---

### TC-IT-RMM-004: custom_refs で充足 → 201（RoleProfile より優先）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001/002（§確定B 優先1）/ UC-RM-015 |
| 種別 | 正常系 |
| 前提条件 | RoleProfile の deliverable_template_refs は空（§確定B 優先3 = 充足しない状態）。Workflow に required_deliverable optional=False あり |
| 操作 | `POST /api/rooms/{room_id}/agents` body: `{"agent_id": ..., "role": ..., "custom_refs": [{"template_id": "<required_id>", "minimum_version": {...}}]}` |
| 期待結果 | HTTP 201。custom_refs が RoleProfile より優先されマッチング成功 |

---

### TC-IT-RMM-005: custom_refs 空タプル + required → 422

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001/002（§確定B 優先1）|
| 種別 | 異常系 |
| 前提条件 | RoleProfile には充足する refs あり（デフォルトでは成功する状態）。Workflow に required optional=False あり |
| 操作 | `POST /api/rooms/{room_id}/agents` body: `{"agent_id": ..., "role": ..., "custom_refs": []}` （空配列 = 明示的な「提供なし」宣言）|
| 期待結果 | HTTP 422。`custom_refs=[]` は RoleProfile を無視し「提供しない」を宣言するため不足 |

---

### TC-IT-RMM-006: RoomOverride 設定後の assign_agent → override refs で充足 → 201

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-001/002（§確定B 優先2）|
| 種別 | 正常系 |
| 前提条件 | RoleProfile の refs は空（充足しない）。RoomOverride に required template_id を設定済み（事前に PUT role-overrides/{role} 実施）|
| 操作 | `POST /api/rooms/{room_id}/agents` body: `{"agent_id": ..., "role": ..., "custom_refs": null}` |
| 期待結果 | HTTP 201。RoomOverride が RoleProfile より優先され充足 |

---

### TC-IT-RMM-007: PUT role-overrides/{role} → 200（upsert）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-003 / UC-RM-016 |
| 種別 | 正常系 |
| 前提条件 | Room 存在（archived でない）|
| 操作 | `PUT /api/rooms/{room_id}/role-overrides/{role}` body: `{"deliverable_template_refs": [...]}` |
| 期待結果 | HTTP 200。GET role-overrides でラウンドトリップ確認 |

---

### TC-IT-RMM-008: PUT role-overrides/{role} 2 回目 → 200（上書き）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-003（idempotent upsert）|
| 種別 | 正常系 |
| 前提条件 | RoomOverride が既に存在する状態 |
| 操作 | 同じ role で異なる refs を PUT |
| 期待結果 | HTTP 200。GET で新しい refs に上書きされていることを確認 |

---

### TC-IT-RMM-009: DELETE role-overrides/{role} → 204

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-004 / UC-RM-016 |
| 種別 | 正常系 |
| 前提条件 | RoomOverride が存在する状態 |
| 操作 | `DELETE /api/rooms/{room_id}/role-overrides/{role}` |
| 期待結果 | HTTP 204。GET role-overrides でその role のエントリが消えていることを確認 |

---

### TC-IT-RMM-010: DELETE 不在 override → 204（no-op）

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-004（no-op 仕様）|
| 種別 | 境界値 |
| 前提条件 | 対象 role の RoomOverride が存在しない |
| 操作 | `DELETE /api/rooms/{room_id}/role-overrides/{role}` |
| 期待結果 | HTTP 204。エラーなし（no-op）|

---

### TC-IT-RMM-011: GET role-overrides → 200 一覧

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-005 / UC-RM-017 |
| 種別 | 正常系 |
| 前提条件 | 2 件以上の RoomOverride が設定済み |
| 操作 | `GET /api/rooms/{room_id}/role-overrides` |
| 期待結果 | HTTP 200。`items` が登録件数分含まれ、各要素に `role` / `deliverable_template_refs` が含まれる |

---

### TC-IT-RMM-012: GET role-overrides → 200 空リスト

| 項目 | 内容 |
|---|---|
| 対応要件 | REQ-RM-MATCH-005（境界値）|
| 種別 | 境界値 |
| 前提条件 | RoomOverride が 0 件 |
| 操作 | `GET /api/rooms/{room_id}/role-overrides` |
| 期待結果 | HTTP 200。`items: []`（空リストも正常）|
