# 結合テストケース詳細 — DeliverableTemplate HTTP API

> TC-IT-DTH-001〜022
> 関連: [`index.md`](index.md) / [`../basic-design.md §REQ-DT-HTTP`](../basic-design.md) / [`../detailed-design.md §MSG 確定文言`](../detailed-design.md)

## TC-IT-DTH-001: POST /api/deliverable-templates 正常系

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 |
| 種別 | 正常系 |
| 前提条件 | DB 空、FastAPI app 起動済み |
| 操作 | `POST /api/deliverable-templates` に `{name, description, type: "MARKDOWN", schema: "## test", version: {major:1, minor:0, patch:0}, acceptance_criteria:[], composition:[]}` を送信 |
| 期待結果 | HTTP 201。レスポンス body に `id`（UUID 形式）/ `name` / `description` / `type` / `schema` / `version: {major:1, minor:0, patch:0}` / `acceptance_criteria: []` / `composition: []` が存在する |
| 確認方法 | `httpx.AsyncClient` + `ASGITransport`、続けて GET で存在確認（ラウンドトリップ）|

## TC-IT-DTH-002: POST — composition ref 不在 → 422

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / MSG-DT-HTTP-002 |
| 種別 | 異常系 |
| 前提条件 | DB 空（参照先 template が存在しない）|
| 操作 | `composition: [{template_id: <unknown-uuid>, minimum_version: {major:1,minor:0,patch:0}}]` を含む POST |
| 期待結果 | HTTP 422。`response.json()["error"]["code"] == "ref_not_found"` |

## TC-IT-DTH-003: POST — 自己参照循環 → 422

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / MSG-DT-002（domain invariant）|
| 種別 | 異常系 |
| 前提条件 | — |
| 操作 | `composition` に自分自身の `template_id` を含む POST（domain の不変条件チェックが先に発火）|
| 期待結果 | HTTP 422。`code` は domain `DeliverableTemplateInvariantViolation` 由来のコード |
| 注記 | 自己参照は domain `DeliverableTemplate` が直接検出（service の `_check_dag` 実行前）。422 が返ることを確認する。`code` の具体値は domain detailed-design.md §MSG-DT-002 の確定文言に従う |

## TC-IT-DTH-004: POST — 推移的循環（A→B→A）→ 422

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / MSG-DT-HTTP-003a |
| 種別 | 異常系 |
| 前提条件 | テンプレート B が先に作成済み。B の composition に A の ref を持たせるため A 作成後 B を PUT で更新する |
| 操作 | A を POST 作成後、B の PUT で `composition: [ref_to_A]` を設定すると A→B→A 循環が完成する PUT が発火 |
| 期待結果 | HTTP 422。`code == "composition_cycle"`。`response["error"]["detail"]["reason"] == "transitive_cycle"`。`cycle_path` はセキュリティ上の理由でレスポンスには含まれない（内部ログ専用）|

## TC-IT-DTH-005: POST — DAG 深度ガード（§確定 D / MSG-DT-HTTP-003b）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / §確定 D / MSG-DT-HTTP-003b |
| 種別 | 境界値 |
| 前提条件 | 深度 10 以上の composition チェーン（T1 → T2 → ... → T11）を DB に構築済み |
| 操作 | T12 を作成し `composition: [ref_to_T11]` を指定（深度 11）|
| 期待結果 | HTTP 422。`code == "composition_cycle"`。`response["error"]["detail"]["reason"] == "depth_limit"`。`cycle_path` はレスポンスに含まれない（内部ログ専用）|

## TC-IT-DTH-006: POST — name 空文字 → 422

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 |
| 種別 | 異常系 |
| 操作 | `name: ""` を含む POST |
| 期待結果 | HTTP 422（Pydantic バリデーション）|

## TC-IT-DTH-007: GET /api/deliverable-templates — 空リスト

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-002 |
| 種別 | 正常系 |
| 前提条件 | DB 空 |
| 操作 | `GET /api/deliverable-templates` |
| 期待結果 | HTTP 200。`{"items": [], "total": 0}` |

## TC-IT-DTH-008: GET /api/deliverable-templates — 複数件 name 昇順 / 同一 name は id 昇順

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-002 |
| 種別 | 正常系 |
| 前提条件 | name = "Z-template" / "A-template" / "M-template" の 3 件を順不同で POST |
| 操作 | `GET /api/deliverable-templates` |
| 期待結果 | HTTP 200。`items[0].name == "A-template"` / `items[1].name == "M-template"` / `items[2].name == "Z-template"` |
| 注記 | ソート仕様: ORDER BY name ASC、同一 name は id ASC（`basic-design.md` REQ-DT-HTTP-002 確定）。同名テンプレートが生じるケースは conftest fixture で UUID の昇順を確認する別ケースを必要に応じ追加する |

## TC-IT-DTH-009: GET /api/deliverable-templates/{id} 正常系

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-003 |
| 種別 | 正常系 |
| 前提条件 | template が 1 件 POST 済み |
| 操作 | `GET /api/deliverable-templates/{id}` |
| 期待結果 | HTTP 200。`id` / `name` / `type` / `version` が POST 時と一致 |

## TC-IT-DTH-010: GET /api/deliverable-templates/{id} — 不在 → 404

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-003 / MSG-DT-HTTP-001 |
| 種別 | 異常系 |
| 操作 | 存在しない UUID で `GET /api/deliverable-templates/{unknown-uuid}` |
| 期待結果 | HTTP 404。`code == "not_found"` |

## TC-IT-DTH-011: GET — UUID 形式不正 → 422

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-003 |
| 種別 | 異常系 |
| 操作 | `GET /api/deliverable-templates/not-a-uuid` |
| 期待結果 | HTTP 422 |

## TC-IT-DTH-012: PUT — version 同一 → 200（§確定 B）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-004 / §確定 B |
| 種別 | 正常系 |
| 前提条件 | version 1.0.0 の template が存在 |
| 操作 | `PUT` で `version: {major:1, minor:0, patch:0}` を指定（同一 version）|
| 期待結果 | HTTP 200。`version.major == 1` / `version.minor == 0` / `version.patch == 0` |

## TC-IT-DTH-013: PUT — version 昇格 → 200（§確定 B）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-004 / §確定 B |
| 種別 | 正常系 |
| 前提条件 | version 1.0.0 の template が存在 |
| 操作 | `PUT` で `version: {major:2, minor:0, patch:0}` を指定（昇格）|
| 期待結果 | HTTP 200。`version.major == 2` |

## TC-IT-DTH-014: PUT — version 降格 → 422（§確定 B）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-004 / §確定 B / MSG-DT-HTTP-004 |
| 種別 | 異常系 |
| 前提条件 | version 2.0.0 の template が存在 |
| 操作 | `PUT` で `version: {major:1, minor:0, patch:0}` を指定（降格）|
| 期待結果 | HTTP 422。`code == "version_downgrade"` |

## TC-IT-DTH-015: PUT — 不在 → 404

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-004 / MSG-DT-HTTP-001 |
| 種別 | 異常系 |
| 操作 | 存在しない UUID で `PUT` |
| 期待結果 | HTTP 404。`code == "not_found"` |

## TC-IT-DTH-016: DELETE — 正常系 → 204（§確定 E）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-005 / §確定 E |
| 種別 | 正常系 |
| 前提条件 | template が 1 件 POST 済み |
| 操作 | `DELETE /api/deliverable-templates/{id}` |
| 期待結果 | HTTP 204 No Content。続けて GET で 404 になること |

## TC-IT-DTH-017: DELETE — 不在 → 404

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-005 / MSG-DT-HTTP-001 |
| 種別 | 異常系 |
| 操作 | 存在しない UUID で `DELETE` |
| 期待結果 | HTTP 404。`code == "not_found"` |

## TC-IT-DTH-018: POST — JSON_SCHEMA type → schema が dict（§確定 I）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / §確定 I |
| 種別 | 正常系 |
| 操作 | `type: "JSON_SCHEMA"`, `schema: {"$schema": "...", "type": "object"}` で POST |
| 期待結果 | HTTP 201。`response.schema` が dict 型で返却される |
| 注記 | OPENAPI type も同様に dict で返却されることを確認 |

## TC-IT-DTH-019: POST — AcceptanceCriterionCreate.id 省略 → UUID 自動生成（§確定 H）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / §確定 H |
| 種別 | 正常系 |
| 操作 | `acceptance_criteria: [{description: "条件1", required: true}]`（id 省略）で POST |
| 期待結果 | HTTP 201。`acceptance_criteria[0].id` が有効な UUID v4 形式の文字列 |

## TC-IT-DTH-020: エラーレスポンスフォーマット確認（§確定 G）

| 項目 | 内容 |
|---|---|
| 対応 | §確定 G |
| 種別 | セキュリティ |
| 操作 | 存在しない id で GET（404 が返る操作）|
| 期待結果 | レスポンス body が `{"error": {"code": str, "message": str, "detail": ...}}` 構造を持つ。スタックトレースを含まない |

## TC-IT-DTH-022: POST — 合法な菱形 DAG（diamond DAG）→ 201（DFS + 経路スタック正常系）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / §確定 D |
| 種別 | 正常系（境界値）|
| 前提条件 | テンプレート B / C が先に作成済み。B の composition に C への ref を持たせる（B→C）|
| 操作 | A を POST 作成する際に `composition: [ref_to_B, ref_to_C]` を指定（A→B, A→C, B→C の菱形 DAG）|
| 期待結果 | HTTP 201 Created。菱形 DAG は合法な DAG であり循環参照ではない。`code == "composition_cycle"` にならないこと |
| 注記 | ヘルスバーグ・レビュー指摘（致命的欠陥 1）対応。BFS + `visited` のみによる誤検出を防ぐため `_check_dag` は DFS + 経路スタック方式に変更済み（§確定 D）。同一ノード C への複数経路（B 経由 / 直接）が存在しても `path`（祖先集合）に C が含まれない限り循環と判定しない |

## TC-IT-DTH-021: POST — acceptance_criteria 内 id 重複 → 422（§確定 H）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-DT-HTTP-001 / §確定 H |
| 種別 | 異常系 |
| 前提条件 | — |
| 操作 | `acceptance_criteria: [{id: "<uuid-X>", description: "条件1", required: true}, {id: "<uuid-X>", description: "条件2", required: true}]`（同一 `id` 重複）で POST |
| 期待結果 | HTTP 422。domain `DeliverableTemplate` の `AcceptanceCriterion id 重複禁止` 不変条件が発火し、`code` が domain 由来のエラーコードになる |
| 注記 | `detailed-design.md §確定 H` に「同一リクエスト内で id が重複した場合は domain の不変条件が 422 を返す」と凍結されている。具体的な `code` 値は domain detailed-design.md §MSG を参照 |
