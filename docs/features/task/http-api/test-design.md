# テスト設計書

> feature: `task` / sub-feature: `http-api`
> 関連 Issue: [#60 feat(task-http-api): Directive + Task lifecycle HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/60)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../system-test-design.md`](../system-test-design.md)

## 本書の役割

本書は **テストケースで検証可能な単位までトレーサビリティを担保する**。`basic-design.md §モジュール契約` の REQ-TS-HTTP-NNN / `detailed-design.md` の MSG-TS-HTTP-NNN / 親 `feature-spec.md` の受入基準 / 設計凍結事項（確定A〜G）を、それぞれ最低 1 件のテストケースで検証する。

**書くこと**:
- REQ-TS-HTTP-NNN / MSG-TS-HTTP-NNN / 受入基準 # / 確定A〜G を実テストケース（TC-IT / TC-UT）に紐付けるマトリクス
- 外部 I/O 依存マップ（raw fixture / factory / characterization 状態）
- 各レベルのテストケース定義（IT / UT）
- カバレッジ基準

**書かないこと**:
- E2E / システムテスト（TC-E2E-TS-003〜004 等）→ 親 [`../system-test-design.md`](../system-test-design.md) が扱う
- 受入テスト → [`docs/acceptance-tests/scenarios/`](../../../acceptance-tests/scenarios/)

## テストケース ID 採番規則

| 番号帯 | 用途 |
|---|---|
| TC-IT-TSH-001〜034 | 結合テスト（HTTP リクエスト / DI / 例外ハンドラ）|
| TC-IT-TSH-040〜 | 予約番号帯（将来の Task 拡張 API で利用）|
| TC-UT-TSH-001〜011 | ユニットテスト（スキーマ / ハンドラ / 依存方向）|

## テストマトリクス

| 要件 ID | 実装アーティファクト | テストケース ID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-TS-HTTP-001（正常系）| `task_router` GET + `TaskService.find_by_id` + `SqliteTaskRepository.find_by_id` | TC-IT-TSH-001〜003 | 結合 | 正常系 | — |
| REQ-TS-HTTP-001（Task 不在）| `TaskService.find_by_id` → `TaskNotFoundError` → `task_not_found_handler` | TC-IT-TSH-004〜006 | 結合 | 異常系 | feature-spec.md §9 #23 |
| REQ-TS-HTTP-001（確定A masking: last_error）| GET `last_error` → `<REDACTED:*>` (R1-12 / T4)  | TC-IT-TSH-007 | 結合 | セキュリティ | feature-spec.md §9 #18 |
| REQ-TS-HTTP-001（確定A masking: body_markdown）| GET deliverable `body_markdown` → `<REDACTED:*>` (R1-12 / T4 / R1-9 独立防御証明）| TC-IT-TSH-008 | 結合 | セキュリティ | feature-spec.md §9 #18 |
| REQ-TS-HTTP-002（正常系）| `task_router` GET list + `TaskService.find_all_by_room` + `SqliteTaskRepository.find_all_by_room` | TC-IT-TSH-009〜010 | 結合 | 正常系 | — |
| REQ-TS-HTTP-002（Room 不在 確定G）| `TaskService.find_all_by_room` → 空リスト（Room 不在でも 404 を返さない）| TC-IT-TSH-011 | 結合 | 正常系 | — |
| REQ-TS-HTTP-003（正常系）| `task_router` POST assign + `TaskService.assign` | TC-IT-TSH-012〜013 | 結合 | 正常系 | feature-spec.md §9 #19 |
| REQ-TS-HTTP-003（Task 不在）| `TaskService.assign` → `TaskNotFoundError` | TC-IT-TSH-014 | 結合 | 異常系 | — |
| REQ-TS-HTTP-003（terminal / UC-TS-015）| `TaskService.assign` → `TaskStateConflictError` → 409 | TC-IT-TSH-015 | 結合 | 異常系 | feature-spec.md §9 #19 |
| REQ-TS-HTTP-003（R1-6 違反: agent_ids=[]）| Pydantic `ValidationError` → 422 | TC-IT-TSH-016 | 結合 | 異常系 | — |
| REQ-TS-HTTP-004（正常系）| `task_router` PATCH cancel + `TaskService.cancel` | TC-IT-TSH-017〜018 | 結合 | 正常系 | feature-spec.md §9 #20 |
| REQ-TS-HTTP-004（Task 不在）| `TaskService.cancel` → `TaskNotFoundError` | TC-IT-TSH-019 | 結合 | 異常系 | — |
| REQ-TS-HTTP-004（terminal / UC-TS-015）| `TaskService.cancel` → `TaskStateConflictError` → 409 | TC-IT-TSH-020 | 結合 | 異常系 | feature-spec.md §9 #20 |
| REQ-TS-HTTP-005（正常系）| `task_router` PATCH unblock + `TaskService.unblock` | TC-IT-TSH-021〜022 | 結合 | 正常系 | feature-spec.md §9 #21 |
| REQ-TS-HTTP-005（Task 不在）| `TaskService.unblock` → `TaskNotFoundError` | TC-IT-TSH-023 | 結合 | 異常系 | — |
| REQ-TS-HTTP-005（terminal / UC-TS-015）| `TaskService.unblock` → `TaskStateConflictError` → 409 | TC-IT-TSH-024 | 結合 | 異常系 | feature-spec.md §9 #21 |
| REQ-TS-HTTP-005（非 BLOCKED 状態）| `TaskService.unblock` → `TaskStateConflictError` → 409 | TC-IT-TSH-025 | 結合 | 異常系 | — |
| REQ-TS-HTTP-006（正常系）| `task_router` POST deliverable + `TaskService.commit_deliverable` | TC-IT-TSH-026〜027 | 結合 | 正常系 | feature-spec.md §9 #22 |
| REQ-TS-HTTP-006（確定A masking: body_markdown）| commit_deliverable レスポンスの `body_markdown` masked | TC-IT-TSH-028 | 結合 | セキュリティ | feature-spec.md §9 #18 |
| REQ-TS-HTTP-006（Task 不在）| `TaskService.commit_deliverable` → `TaskNotFoundError` | TC-IT-TSH-029 | 結合 | 異常系 | — |
| REQ-TS-HTTP-006（terminal / UC-TS-015）| `TaskService.commit_deliverable` → `TaskStateConflictError` → 409 | TC-IT-TSH-030 | 結合 | 異常系 | feature-spec.md §9 #22 |
| T3（不正 UUID）| FastAPI `UUID` 型強制 → 422 | TC-IT-TSH-031 | 結合 | セキュリティ | — |
| T1（CSRF）| `Origin: http://evil.example.com` → POST → 403 | TC-IT-TSH-032 | 結合 | セキュリティ | — |
| T2（スタックトレース非露出）| generic_exception_handler → 500 body に stacktrace なし | TC-IT-TSH-033〜034 | 結合 | セキュリティ | — |
| MSG-TS-HTTP-001 | `task_not_found_handler` | TC-UT-TSH-001〜003 | ユニット | 異常系 | — |
| MSG-TS-HTTP-002 | `task_state_conflict_handler` | TC-UT-TSH-004〜005 | ユニット | 異常系 | — |
| `TaskAssign` スキーマ | `schemas/task.py` | TC-UT-TSH-006〜007 | ユニット | 正常系 / 異常系 | — |
| `DeliverableCreate` スキーマ | `schemas/task.py` | TC-UT-TSH-008 | ユニット | 正常系 | — |
| `TaskResponse` field_serializer masking（確定A / T4）| `TaskResponse.last_error` masked シリアライズ | TC-UT-TSH-009 | ユニット | セキュリティ | feature-spec.md §9 #18 |
| `DeliverableResponse` field_serializer masking（確定A / T4）| `DeliverableResponse.body_markdown` masked シリアライズ | TC-UT-TSH-010 | ユニット | セキュリティ | feature-spec.md §9 #18 |
| 依存方向（interfaces → domain / infrastructure 直参照禁止）| `interfaces/http/routers/` + `interfaces/http/schemas/` を `ast.walk()` 全ノード走査（PR #105 退行禁止ルール準拠）| TC-UT-TSH-011 | ユニット（静的解析）| 異常系 | — |

**マトリクス充足の証拠**:
- REQ-TS-HTTP-001〜006 すべてに最低 1 件の正常系テストケース（TC-IT-TSH-001/009/012/017/021/026）
- REQ-TS-HTTP-001〜006 の異常系（例外経路）が各々最低 1 件検証
- MSG-TS-HTTP-001〜003 の各 `code` / `message` 文字列が静的照合で確認
- 親受入基準 18〜23 のすべてが TC-IT-TSH-001〜030 で対応
- T1〜T4 脅威への対策が TC-IT-TSH-032/033/031/007+008+028/TC-UT-TSH-009+010 で有効性確認
- 確定A〜G の全項目が最低 1 件のテストケースでカバー（確定G=TC-IT-TSH-011）
- 孤児要件なし

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 |
|---|---|---|---|---|
| SQLite（テスト用 DB）| `get_session()` DI / lifespan 経由の Session / TaskRepository / DirectiveRepository / RoomRepository / EmpireRepository | `tests/fixtures/test_db.db`（tempdir）| `tests/factories/db.py`（http-api-foundation 定義済み）/ `tests/factories/task.py`（**要新規作成** — TBD-1 参照）| 実 DB（pytest `tmp_path` 配下 tempfile）|
| FastAPI ASGI | HTTP リクエスト送信 | — | — | `httpx.AsyncClient(app=app, base_url="http://test")`（http-api-foundation 確定済み）|

**`tests/factories/task.py` ステータス**: **要起票（TBD-1）**。`make_task()` / `make_deliverable()` / `make_attachment()` を実装着手前に作成すること。空欄のまま IT 実装に進むことはできない。

## 結合テストケース

| テストID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|---|
| TC-IT-TSH-001 | `task_router` → `TaskService.find_by_id` → `SqliteTaskRepository.find_by_id` | 実 SQLite tempdb | Directive 発行で作成済み Task 存在 | `GET /api/tasks/{task_id}` | HTTP 200, `TaskResponse`（id / room_id / status=PENDING / assigned_agent_ids=[] / deliverables=[]）|
| TC-IT-TSH-002 | `task_router` → `TaskService.find_by_id` | 実 SQLite tempdb | Task 存在 | `GET /api/tasks/{task_id}` | HTTP 200, response.id == task_id |
| TC-IT-TSH-003 | `task_router` → `TaskService.find_by_id` | 実 SQLite tempdb | Task 存在（room_id が既知）| `GET /api/tasks/{task_id}` | HTTP 200, response.room_id == room_id |
| TC-IT-TSH-004 | `TaskService.find_by_id` → `TaskNotFoundError` → `task_not_found_handler` | 実 SQLite tempdb | Task 未存在 | `GET /api/tasks/{ランダム UUID}` | HTTP 404, `{"error": {"code": "not_found", "message": "Task not found."}}` |
| TC-IT-TSH-005 | `task_not_found_handler` → code | 実 SQLite tempdb | Task 未存在 | `GET /api/tasks/{ランダム UUID}` | HTTP 404, error.code == "not_found" |
| TC-IT-TSH-006 | `task_not_found_handler` → message | 実 SQLite tempdb | Task 未存在 | `GET /api/tasks/{ランダム UUID}` | HTTP 404, error.message == "Task not found." |
| TC-IT-TSH-007 | GET `last_error` masking（確定A / T4 / R1-12）— **R1-9 独立防御証明** | 実 SQLite tempdb | BLOCKED 状態 Task を DB に直接シード（`last_error="GITHUB_PAT=ghp_xxxx"` を raw で INSERT）| `GET /api/tasks/{task_id}` | HTTP 200, response.last_error が `<REDACTED:GITHUB_PAT>` 形式（raw token 非露出）— field_serializer が R1-12 と独立して発火することを assert |
| TC-IT-TSH-008 | GET deliverable `body_markdown` masking（確定A / T4 / R1-12）— **R1-9 独立防御証明** | 実 SQLite tempdb | Task + Deliverable を DB に直接シード（`body_markdown="ANTHROPIC_API_KEY=sk-ant-xxxx"` を raw で INSERT）| `GET /api/tasks/{task_id}` | HTTP 200, response.deliverables[0].body_markdown が `<REDACTED:ANTHROPIC_KEY>` 形式 |
| TC-IT-TSH-009 | `task_router` → `TaskService.find_all_by_room` → `SqliteTaskRepository.find_all_by_room` | 実 SQLite tempdb | Room 存在・Task 2 件 | `GET /api/rooms/{room_id}/tasks` | HTTP 200, `{"items": [<TaskResponse>, <TaskResponse>], "total": 2}` |
| TC-IT-TSH-010 | `TaskService.find_all_by_room` → 空リスト | 実 SQLite tempdb | Room 存在・Task 0 件 | `GET /api/rooms/{room_id}/tasks` | HTTP 200, `{"items": [], "total": 0}` |
| TC-IT-TSH-011 | `TaskService.find_all_by_room` → 空リスト（Room 不在 / 確定G）| 実 SQLite tempdb | Room 未存在 | `GET /api/rooms/{ランダム UUID}/tasks` | HTTP 200, `{"items": [], "total": 0}`（404 ではなく空リストを返す）|
| TC-IT-TSH-012 | `task_router` → `TaskService.assign` → `SqliteTaskRepository.save` | 実 SQLite tempdb | PENDING Task 存在・Agent 存在 | `POST /api/tasks/{task_id}/assign` `{"agent_ids": ["{agent_id}"]}` | HTTP 200, `TaskResponse` |
| TC-IT-TSH-013 | `TaskService.assign` → status 遷移 | 実 SQLite tempdb | PENDING Task 存在 | `POST /api/tasks/{task_id}/assign` | HTTP 200, response.status == "IN_PROGRESS" |
| TC-IT-TSH-014 | `TaskService.assign` → `TaskNotFoundError` | 実 SQLite tempdb | Task 未存在 | `POST /api/tasks/{ランダム UUID}/assign` `{"agent_ids": ["{valid_uuid}"]}` | HTTP 404, error.code == "not_found" |
| TC-IT-TSH-015 | `TaskService.assign` → `TaskStateConflictError`（terminal / UC-TS-015）| 実 SQLite tempdb | CANCELLED Task 存在（terminal）| `POST /api/tasks/{task_id}/assign` `{"agent_ids": ["{valid_uuid}"]}` | HTTP 409, error.code == "conflict" |
| TC-IT-TSH-016 | Pydantic `ValidationError`（R1-6 違反: agent_ids=[]）| 実 SQLite tempdb | PENDING Task 存在 | `POST /api/tasks/{task_id}/assign` `{"agent_ids": []}` | HTTP 422, error.code == "validation_error" |
| TC-IT-TSH-017 | `task_router` → `TaskService.cancel` → `SqliteTaskRepository.save` | 実 SQLite tempdb | PENDING Task 存在 | `PATCH /api/tasks/{task_id}/cancel` | HTTP 200, `TaskResponse` |
| TC-IT-TSH-018 | `TaskService.cancel` → status 遷移 | 実 SQLite tempdb | PENDING Task 存在 | `PATCH /api/tasks/{task_id}/cancel` | HTTP 200, response.status == "CANCELLED" |
| TC-IT-TSH-019 | `TaskService.cancel` → `TaskNotFoundError` | 実 SQLite tempdb | Task 未存在 | `PATCH /api/tasks/{ランダム UUID}/cancel` | HTTP 404, error.code == "not_found" |
| TC-IT-TSH-020 | `TaskService.cancel` → `TaskStateConflictError`（terminal / UC-TS-015）| 実 SQLite tempdb | DONE Task 存在（terminal）| `PATCH /api/tasks/{task_id}/cancel` | HTTP 409, error.code == "conflict" |
| TC-IT-TSH-021 | `task_router` → `TaskService.unblock` → `SqliteTaskRepository.save` | 実 SQLite tempdb | BLOCKED Task 存在 | `PATCH /api/tasks/{task_id}/unblock` | HTTP 200, `TaskResponse` |
| TC-IT-TSH-022 | `TaskService.unblock` → status 遷移 + last_error リセット（R1-5）| 実 SQLite tempdb | BLOCKED Task 存在（last_error 非 null）| `PATCH /api/tasks/{task_id}/unblock` | HTTP 200, response.status == "IN_PROGRESS", response.last_error == null（R1-5）|
| TC-IT-TSH-023 | `TaskService.unblock` → `TaskNotFoundError` | 実 SQLite tempdb | Task 未存在 | `PATCH /api/tasks/{ランダム UUID}/unblock` | HTTP 404, error.code == "not_found" |
| TC-IT-TSH-024 | `TaskService.unblock` → `TaskStateConflictError`（terminal / UC-TS-015）| 実 SQLite tempdb | CANCELLED Task 存在（terminal）| `PATCH /api/tasks/{task_id}/unblock` | HTTP 409, error.code == "conflict" |
| TC-IT-TSH-025 | `TaskService.unblock` → `TaskStateConflictError`（非 BLOCKED）| 実 SQLite tempdb | PENDING Task 存在（BLOCKED でない）| `PATCH /api/tasks/{task_id}/unblock` | HTTP 409, error.code == "conflict"（PENDING から unblock は state machine で禁止）|
| TC-IT-TSH-026 | `task_router` → `TaskService.commit_deliverable` → `SqliteTaskRepository.save` | 実 SQLite tempdb | IN_PROGRESS Task 存在・stage_id 有効 | `POST /api/tasks/{task_id}/deliverables/{stage_id}` 正常 payload | HTTP 200, `TaskResponse`（deliverables に stage_id が追加）|
| TC-IT-TSH-027 | `TaskService.commit_deliverable` → deliverable 存在確認 | 実 SQLite tempdb | IN_PROGRESS Task 存在 | `POST /api/tasks/{task_id}/deliverables/{stage_id}` | HTTP 200, response.deliverables に stage_id のエントリが存在 |
| TC-IT-TSH-028 | commit_deliverable レスポンス `body_markdown` masking（確定A / T4）| 実 SQLite tempdb | IN_PROGRESS Task 存在 | `POST /api/tasks/{task_id}/deliverables/{stage_id}` payload `body_markdown="ANTHROPIC_API_KEY=sk-ant-xxxx"` | HTTP 200, response.deliverables[stage_id].body_markdown が `<REDACTED:ANTHROPIC_KEY>` 形式（raw token 非露出）|
| TC-IT-TSH-029 | `TaskService.commit_deliverable` → `TaskNotFoundError` | 実 SQLite tempdb | Task 未存在 | `POST /api/tasks/{ランダム UUID}/deliverables/{stage_id}` | HTTP 404, error.code == "not_found" |
| TC-IT-TSH-030 | `TaskService.commit_deliverable` → `TaskStateConflictError`（terminal / UC-TS-015）| 実 SQLite tempdb | CANCELLED Task 存在（terminal）| `POST /api/tasks/{task_id}/deliverables/{stage_id}` | HTTP 409, error.code == "conflict" |
| TC-IT-TSH-031 | FastAPI `UUID` 型強制（T3）| — | — | `GET /api/tasks/not-a-valid-uuid` / `POST /api/tasks/not-a-valid-uuid/assign` | HTTP 422 |
| TC-IT-TSH-032 | CSRF ミドルウェア（T1）| 実 SQLite tempdb | Task 存在 | `POST /api/tasks/{task_id}/assign` に `Origin: http://evil.example.com` ヘッダ付与 | HTTP 403, error.code == "forbidden" |
| TC-IT-TSH-033 | generic_exception_handler（T2 スタックトレース非露出）| 実 SQLite tempdb | — | 内部エラーを誘発（`/test/raise-exception` エンドポイント）| HTTP 500, response body に `"Traceback"` / `"stacktrace"` 含まれない |
| TC-IT-TSH-034 | T2 error code | 実 SQLite tempdb | — | 内部エラーを誘発 | HTTP 500, error.code == "internal_error" |

## ユニットテストケース

| テストID | 対象 | 種別 | 入力（factory / 直接）| 期待結果 |
|---|---|---|---|---|
| TC-UT-TSH-001 | `task_not_found_handler`（MSG-TS-HTTP-001）| 異常系 | `TaskNotFoundError(task_id="test-id")` | HTTP 404 |
| TC-UT-TSH-002 | `task_not_found_handler` → error code | 異常系 | `TaskNotFoundError(task_id="test-id")` | body.error.code == "not_found" |
| TC-UT-TSH-003 | `task_not_found_handler` → error message | 異常系 | `TaskNotFoundError(task_id="test-id")` | body.error.message == "Task not found." |
| TC-UT-TSH-004 | `task_state_conflict_handler`（MSG-TS-HTTP-002 / `[FAIL]` / `\nNext:` 前処理凍結）| 異常系 | (a) `TaskStateConflictError` — 内部メッセージが `"[FAIL] Cannot assign to terminal task.\nNext: do not attempt state transitions on terminal tasks."` の形式 (b) `[FAIL]` なし単純メッセージ | (a) HTTP 409, `message` に `[FAIL]` / `\nNext:` が含まれない（全先行 sub-feature と同一の `_FAIL_PREFIX_RE` 前処理ルール準拠）(b) HTTP 409, message はそのまま返る |
| TC-UT-TSH-005 | `task_state_conflict_handler` → error code（前処理後も code 不変）| 異常系 | `TaskStateConflictError(...)` | body.error.code == "conflict"（前処理は message のみに適用され code には影響しない）|
| TC-UT-TSH-006 | `TaskAssign` スキーマ（正常系）| 正常系 | `{"agent_ids": ["{valid_uuid}"]}` | バリデーション通過 |
| TC-UT-TSH-007 | `TaskAssign` スキーマ（agent_ids=[] / R1-6 違反）| 異常系 | `{"agent_ids": []}` | min_length 違反 `ValidationError` |
| TC-UT-TSH-008 | `DeliverableCreate` スキーマ（正常系）| 正常系 | `{"body_markdown": "成果物テキスト", "submitted_by": "{agent_uuid}", "attachments": []}` | バリデーション通過 |
| TC-UT-TSH-009 | `TaskResponse` field_serializer による `last_error` masking（確定A / T4）| セキュリティ | raw token 文字列（例: `"GITHUB_PAT=ghp_xxxx"`）を持つ Task オブジェクト → `TaskResponse` でシリアライズ | シリアライズ後の `last_error` に raw token が含まれない（`<REDACTED:GITHUB_PAT>` 形式）|
| TC-UT-TSH-010 | `DeliverableResponse` field_serializer による `body_markdown` masking（確定A / T4）| セキュリティ | raw token 文字列（例: `"ANTHROPIC_API_KEY=sk-ant-xxxx"`）を持つ Deliverable オブジェクト → `DeliverableResponse` でシリアライズ | シリアライズ後の `body_markdown` に raw token が含まれない（`<REDACTED:ANTHROPIC_KEY>` 形式）|
| TC-UT-TSH-011 | 依存方向（静的解析）| 異常系 | `ast.walk(tree)` で `interfaces/http/routers/` + `interfaces/http/schemas/` 配下の全 `.py` を全ノード走査（PR #105 退行禁止ルール準拠。`dependencies.py` は DI 配線として対象外）| `bakufu.domain` / `bakufu.infrastructure` への直接 import が存在しないこと。クラス名: `TestStaticDependencyAnalysisTask`（routers dir は `bakufu.interfaces.http.routers.tasks` 実装後に参照）|

## カバレッジ基準

- REQ-TS-HTTP-001〜006 の各要件が **最低 1 件の正常系** テストケース（TC-IT-TSH-001/009/012/017/021/026）で検証されている
- REQ-TS-HTTP-001〜006 の異常系（例外経路）が各々 **最低 1 件** 検証されている
- MSG-TS-HTTP-001〜003 の各 `code` / `message` 文字列が **静的文字列で照合** されている
- 親受入基準 18〜23（[`../feature-spec.md §9`](../feature-spec.md)）が TC-IT-TSH-001〜030 で対応
- T1〜T4 脅威への対策が TC-IT-TSH-032/033/031/007+008+028/TC-UT-TSH-009+010 で有効性確認
- 確定A masking: TC-IT-TSH-007/008/028 + TC-UT-TSH-009/010（field_serializer 独立動作）
- 確定G（Room 不在 → 空リスト 200）: TC-IT-TSH-011
- R1-5（unblock 後 last_error リセット）: TC-IT-TSH-022
- UC-TS-015（terminal 拒否）: TC-IT-TSH-015/020/024/030
- 行カバレッジ目標: **90% 以上**（`detailed-design.md §カバレッジ基準`）

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全 7 ジョブ緑であること
- ローカル:
  ```sh
  just test-backend   # pytest 実行（--cov で coverage 確認）
  ```
- 手動確認（uvicorn 起動後）:
  ```sh
  # Room 作成（Empire → Room の順）
  # Directive 発行 → Task が自動生成される
  curl -X POST http://localhost:8000/api/rooms/{room_id}/directives \
    -H "Content-Type: application/json" \
    -d '{"text": "ブログ分析機能を実装してください"}' | jq .
  # → 201 {"directive": {...}, "task": {"id": "<task_id>", "status": "PENDING"}}

  # Task 取得（body_markdown に secret を含む deliverable を含む場合 masked）
  curl http://localhost:8000/api/tasks/<task_id> | jq .
  # → 200 {"status": "PENDING", "last_error": null, ...}

  # Agent 割当
  curl -X POST http://localhost:8000/api/tasks/<task_id>/assign \
    -H "Content-Type: application/json" \
    -d '{"agent_ids": ["<agent_id>"]}' | jq .
  # → 200 {"status": "IN_PROGRESS", ...}
  ```

## テストディレクトリ構造

```
backend/tests/
├── factories/
│   └── task.py                                  # 要新規作成（TBD-1）: make_task / make_deliverable / make_attachment
├── unit/
│   └── test_task_http_api/
│       ├── __init__.py
│       └── test_handlers.py                     # TC-UT-TSH-001〜011
└── integration/
    └── test_task_http_api/
        ├── __init__.py
        ├── conftest.py                           # TsTestCtx fixture / wiring（TaskService DI）
        ├── helpers.py                            # _create_room / _create_directive / _seed_task_direct / _seed_blocked_task / _seed_task_with_raw_last_error 等
        ├── test_get.py                           # TC-IT-TSH-001〜008
        ├── test_list.py                          # TC-IT-TSH-009〜011
        ├── test_assign.py                        # TC-IT-TSH-012〜016
        ├── test_cancel.py                        # TC-IT-TSH-017〜020
        ├── test_unblock.py                       # TC-IT-TSH-021〜025
        ├── test_deliverable.py                   # TC-IT-TSH-026〜030
        └── test_security.py                      # TC-IT-TSH-031〜034
```

## 未決課題・要起票 characterization task

| # | 内容 | 起票先 |
|---|---|---|
| TBD-1 | `tests/factories/task.py` 新規作成（`make_task` / `make_deliverable` / `make_attachment`）。実装着手前に完了必須。空欄のまま IT 実装に進んだ場合レビューで却下する | 実装 PR 着手前 |
| TBD-2 | `SqliteTaskRepository.find_all_by_room` 実装完了確認（確定B / P-2）。TC-IT-TSH-009〜011 実行前に必須 | 実装担当確認 |
| TBD-3 | `task_exceptions.py` 新規作成（確定C / P-1）。`TaskNotFoundError(task_id)` / `TaskStateConflictError(task_id, current_status, action)` が定義済みであること | 実装着手前 |

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — 機能要件（REQ ID）
- [`detailed-design.md`](detailed-design.md) — MSG 確定文言 / スキーマ仕様 / 確定A〜G
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様（受入基準 §9 #18〜23）
- [`../system-test-design.md`](../system-test-design.md) — E2E テスト（TC-E2E-TS-003〜004）
- [`../../agent/http-api/test-design.md`](../../agent/http-api/test-design.md) — 共通テストパターン参照（masking 独立防御証明、依存方向静的解析）
