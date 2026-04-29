# テスト設計書

> feature: `workflow` / sub-feature: `http-api`
> 関連 Issue: [#58 feat(workflow-http-api): Workflow + Stage HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/58)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../system-test-design.md`](../system-test-design.md)

## 本書の役割

本書は **テストケースで検証可能な単位までトレーサビリティを担保する**。`basic-design.md §モジュール契約` の REQ-WF-HTTP-NNN / `detailed-design.md §MSG 確定文言表` の MSG-WF-HTTP-NNN / 親 `feature-spec.md §9 受入基準` #13〜22 / 脅威 T1〜T5 を、それぞれ最低 1 件のテストケースで検証する。

**書くこと**:
- REQ-WF-HTTP-NNN / MSG-WF-HTTP-NNN / 受入基準 # / 脅威を実テストケース（TC-IT / TC-UT）に紐付けるマトリクス
- 外部 I/O 依存マップ（factory / raw fixture の characterization 状態を含む）
- 各レベルのテストケース定義（前提条件 / 操作 / 期待結果）
- モック方針
- カバレッジ基準

**書かないこと**:
- E2E テスト（TC-E2E-WF-003）→ 親 [`../system-test-design.md`](../system-test-design.md) が扱う
- 受入テスト → [`docs/acceptance-tests/scenarios/`](../../../acceptance-tests/scenarios/)

## テストケース ID 採番規則

本 sub-feature のテスト ID 体系:

| 番号帯 | 用途 |
|---|---|
| TC-IT-WFH-001〜030 | 結合テスト（HTTP リクエスト / DI / 例外ハンドラ）|
| TC-IT-WFH-031〜 | 予約番号帯（将来の workflow 拡張 API で利用）|
| TC-UT-WFH-001〜010 | ユニットテスト（スキーマ / 例外ハンドラ / サービス）|
| TC-UT-WFH-020〜 | 静的解析系テスト専用帯（依存方向 / import 解析）|

## テストマトリクス

| 要件 ID | 実装アーティファクト | テストケース ID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-WF-HTTP-001（JSON 定義）| `workflows_router` POST + `WorkflowService.create_for_room` | TC-IT-WFH-001 | 結合 | 正常系 | feature-spec.md §9 #13 |
| REQ-WF-HTTP-001（プリセット）| `workflows_router` POST + プリセット解決 | TC-IT-WFH-002 | 結合 | 正常系 | feature-spec.md §9 #14 |
| REQ-WF-HTTP-001（Room 不在）| `workflows_router` POST + `RoomNotFoundError` | TC-IT-WFH-011 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-001（Room archived）| `workflows_router` POST + `RoomArchivedError` | TC-IT-WFH-012 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-001（プリセット不明）| `workflows_router` POST + `WorkflowPresetNotFoundError` | TC-IT-WFH-013 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-001（DAG 違反）| `workflows_router` POST + `WorkflowInvariantViolation` | TC-IT-WFH-014 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-001（排他バリデーション：両方指定）| `WorkflowCreate` model_validator | TC-IT-WFH-015 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-001（排他バリデーション：両方 None）| `WorkflowCreate` model_validator | TC-IT-WFH-016 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-002（正常系）| `workflows_router` GET by room + `WorkflowService.find_by_room` | TC-IT-WFH-003 | 結合 | 正常系 | feature-spec.md §9 #15 |
| REQ-WF-HTTP-002（Room 不在）| `workflows_router` GET by room + `RoomNotFoundError` | TC-IT-WFH-017 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-003（正常系）| `workflows_router` GET by id + `WorkflowService.find_by_id` | TC-IT-WFH-004 | 結合 | 正常系 | feature-spec.md §9 #16 |
| REQ-WF-HTTP-003（不在）| `workflows_router` GET by id + `WorkflowNotFoundError` | TC-IT-WFH-018 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-004（name のみ更新）| `workflows_router` PATCH + `WorkflowService.update` | TC-IT-WFH-005 | 結合 | 正常系 | feature-spec.md §9 #17 |
| REQ-WF-HTTP-004（DAG 全置換）| `workflows_router` PATCH + `WorkflowService.update` | TC-IT-WFH-006 | 結合 | 正常系 | feature-spec.md §9 #18 |
| REQ-WF-HTTP-004（不在）| `workflows_router` PATCH + `WorkflowNotFoundError` | TC-IT-WFH-019 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-004（archived）| `workflows_router` PATCH + `WorkflowArchivedError(kind="update")` | TC-IT-WFH-020 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-004（DAG 違反）| `workflows_router` PATCH + `WorkflowInvariantViolation` | TC-IT-WFH-021 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-004（整合バリデーション違反）| `WorkflowUpdate` model_validator | TC-IT-WFH-022 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-005（正常系）| `workflows_router` DELETE + `WorkflowService.archive` | TC-IT-WFH-007 | 結合 | 正常系 | feature-spec.md §9 #19 |
| REQ-WF-HTTP-005（不在）| `workflows_router` DELETE + `WorkflowNotFoundError` | TC-IT-WFH-023 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-005（冪等性）| `workflows_router` DELETE × 2 | TC-IT-WFH-024 | 結合 | 正常系 | Q-3（R1-14 冪等）|
| REQ-WF-HTTP-006（正常系）| `workflows_router` GET stages + `WorkflowService.find_stages` | TC-IT-WFH-008 | 結合 | 正常系 | feature-spec.md §9 #20 |
| REQ-WF-HTTP-006（不在）| `workflows_router` GET stages + `WorkflowNotFoundError` | TC-IT-WFH-025 | 結合 | 異常系 | Q-3 |
| REQ-WF-HTTP-007（正常系）| `workflows_router` GET presets + `WorkflowService.get_presets` | TC-IT-WFH-009 | 結合 | 正常系 | feature-spec.md §9 #21 |
| REQ-WF-HTTP-007（ルーティング順序）| `GET /api/workflows/presets` リテラルパス優先 | TC-IT-WFH-027 | 結合 | 境界値 | Q-3 |
| T1（CSRF）| CSRF ミドルウェア → POST workflows | TC-IT-WFH-028 | 結合 | 異常系 | Q-3 |
| T3（不正 UUID パスインジェクション）| FastAPI UUID 型強制 → 422 | TC-IT-WFH-026 | 結合 | 異常系 | Q-3 |
| A02（notify_channels マスキング — POST/PATCH 経路）| `StageResponse.notify_channels` が POST 201 / PATCH 200 レスポンスで masked になること（`detailed-design.md §確定A`）| TC-IT-WFH-029 | 結合 | 正常系 | Q-3 |
| MSG-WF-HTTP-001 | `workflow_not_found_handler` | TC-IT-WFH-018 / TC-UT-WFH-006 | 結合 / ユニット | 異常系 | Q-3 |
| MSG-WF-HTTP-002 | `workflow_archived_handler(kind="update")` | TC-IT-WFH-020 / TC-UT-WFH-007 | 結合 / ユニット | 異常系 | Q-3 |
| MSG-WF-HTTP-004 | `workflow_preset_not_found_handler` | TC-IT-WFH-013 / TC-UT-WFH-008 | 結合 / ユニット | 異常系 | Q-3 |
| MSG-WF-HTTP-005 | `workflow_invariant_violation_handler`（前処理ルール）| TC-IT-WFH-014 / TC-UT-WFH-009 | 結合 / ユニット | 異常系 | Q-3 |
| `StageCreate` スキーマ | `schemas/workflow.py` | TC-UT-WFH-001 | ユニット | 正常系 / 異常系 | Q-3 |
| `TransitionCreate` スキーマ | `schemas/workflow.py` | TC-UT-WFH-002 | ユニット | 正常系 / 異常系 | Q-3 |
| `WorkflowCreate` スキーマ | `schemas/workflow.py` | TC-UT-WFH-003 | ユニット | 正常系 / 異常系 | Q-3 |
| `WorkflowUpdate` スキーマ | `schemas/workflow.py` | TC-UT-WFH-004 | ユニット | 正常系 / 異常系 | Q-3 |
| レスポンススキーマ群 | `schemas/workflow.py` | TC-UT-WFH-005 | ユニット | 正常系 | Q-3 |
| `WorkflowService.__init__`（3 引数）| `application/services/workflow_service.py` | TC-UT-WFH-010 | ユニット | 正常系 | Q-3 |
| 依存方向（interfaces → domain 直参照禁止）| `interfaces/http/routers/` + `interfaces/http/schemas/`（スコープ限定）| TC-UT-WFH-020 | ユニット（静的解析）| 異常系 | Q-3 |
| Q-1 | pyright / ruff | CI ジョブ | — | — | Q-1 |
| Q-2 | pytest --cov | CI ジョブ | — | — | Q-2 |

**マトリクス充足の証拠**:
- REQ-WF-HTTP-001〜007 すべてに最低 1 件の正常系テストケース（TC-IT-WFH-001〜009）
- REQ-WF-HTTP-001〜006 の主要な異常系（Room 不在 / Room archived / プリセット不明 / DAG 違反 / 排他バリデーション / Workflow 不在 / archived 操作 / UUID 注入）が各 TC-IT で網羅（001〜028）
- MSG-WF-HTTP-001/002/004/005 の全件が `response.json()["error"]["code"]` / `"message"` の静的照合テストで確認（IT + UT 二重検証）（MSG-WF-HTTP-003 は設計変更により削除済み）
- 親受入基準 #13〜21 のすべてが TC-IT-WFH-001〜009 で対応（受入基準 #22 は設計変更により削除済み — `WorkflowArchivedError(kind="assign")` は到達不能パスとして除去）
- T1（CSRF）/ T3（不正 UUID）脅威への対策が最低 1 件で有効性確認
- T4（SSRF: notify_channels allow list）は domain 層責務のため `domain/test-design.md` 参照（TC-UT-WF-006a/b — 孤児ではない）
- T5（static プリセット定数保護）は TC-IT-WFH-009（GET /api/workflows/presets が常に成功）で間接検証
- A02（notify_channels masking — POST/PATCH 経路）は TC-IT-WFH-029 で物理検証（`detailed-design.md §確定A` 凍結の実装保証）
- 孤児要件なし

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture / factory | characterization 状態 |
|---|---|---|---|
| SQLite（テスト用 DB）| `get_session()` DI / lifespan 経由の Session / WorkflowRepository / RoomRepository | `tests/factories/db.py`（http-api-foundation で定義済み）+ `tmp_path` tempfile | **済** |
| FastAPI ASGI | HTTP リクエスト送信（AsyncClient）| `httpx.AsyncClient(ASGITransport(app=app), base_url="http://test")`（`room_app_client` と同パターン — conftest.py に `workflow_app_client` fixture として追加）| **済**（conftest.py に追記要）|
| Empire SQLite レコード | Room 作成の前提（empire_id 取得）| `tests/factories/empire.py`（定義済み）— EmpireRow を tempdb に直接 INSERT | **済** |
| Room SQLite レコード | `WorkflowService.create_for_room` の Room 存在確認 | `tests/factories/room.py`（定義済み）— Room domain object を Repository 経由で tempdb に INSERT | **済** |
| Workflow SQLite レコード | `WorkflowService.find_by_id` / `update` / `archive` / `find_stages` 等の事前状態 | `tests/factories/workflow.py`（定義済み）— Workflow domain object を `SqliteWorkflowRepository.save()` 経由で tempdb に INSERT | **済** |

> **重要**: 上記 5 件の factory はすべて `済`（Issue #57 room http-api 実装時に完成済み）。assumed mock（`mock.return_value` にインライン辞書リテラルを渡す等）は禁止。全 IT テストは実 SQLite tempdb と factory 経由の事前シードで完結させること。factory 未定義のまま実装に入ったテストはレビューで却下する。

## モック方針

| 対象 | テストレベル | モック戦略 |
|---|---|---|
| SQLite DB | IT（結合）| モックなし — `tmp_path` 配下 tempfile を使用する実 SQLite。8 PRAGMA + WAL を production と同一設定で起動 |
| SQLite DB | UT（ユニット）| `MagicMock()` でリポジトリをモック（DB アクセスなし）|
| FastAPI ASGI | IT | `httpx.AsyncClient(ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test")` |
| Room / Empire（IT happy path）| IT | factory 経由で tempdb に直接 INSERT した実データを参照（assumed mock 禁止）|
| Workflow（IT happy path）| IT | `tests/factories/workflow.py` の `make_workflow()` + `SqliteWorkflowRepository.save()` で tempdb に INSERT |
| WorkflowRepository / RoomRepository 等 | UT | `MagicMock()` で代替（TC-UT-WFH-010 等）|
| `AsyncSession` | UT | `MagicMock()` で代替 |

## 結合テストケース

| テスト ID | 対象モジュール連携 | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|
| TC-IT-WFH-001 | `workflows_router` → `WorkflowService.create_for_room` → `SqliteWorkflowRepository.save` + `SqliteRoomRepository.save` | Empire 存在 / Room 存在（workflow_id 未設定可）| `POST /api/rooms/{room_id}/workflows` `{"name": "Vモデル開発フロー", "stages": [<valid StageCreate>], "transitions": [], "entry_stage_id": <stage_id>}` | HTTP 201, `WorkflowResponse`（id / name / stages / transitions / entry_stage_id / archived=false）/ Room.workflow_id が新 Workflow ID に更新されていること（後続 GET /api/rooms/{room_id} で確認）|
| TC-IT-WFH-002 | `workflows_router` → `WorkflowService.create_for_room` → プリセット解決 → `SqliteWorkflowRepository.save` | Empire 存在 / Room 存在 | `POST /api/rooms/{room_id}/workflows` `{"preset_name": "v-model"}` | HTTP 201, `WorkflowResponse`（name="Vモデル開発フロー" / stages 13 件 / transitions 15 件 / archived=false）|
| TC-IT-WFH-003 | `workflows_router` → `WorkflowService.find_by_room` → `SqliteRoomRepository.find_by_id` → `SqliteWorkflowRepository.find_by_id` | Empire 存在 / Room 存在 / Room.workflow_id が設定済み（TC-IT-WFH-001 後続状態）| `GET /api/rooms/{room_id}/workflows` | HTTP 200, `WorkflowListResponse(items=[WorkflowResponse], total=1)`（stages / transitions / entry_stage_id 含む）|
| TC-IT-WFH-004 | `workflows_router` → `WorkflowService.find_by_id` → `SqliteWorkflowRepository.find_by_id` | Workflow 存在（factory で tempdb に INSERT 済み）| `GET /api/workflows/{workflow_id}` | HTTP 200, `WorkflowResponse`（stages / transitions / entry_stage_id / archived=false 含む全フィールド）|
| TC-IT-WFH-005 | `workflows_router` → `WorkflowService.update`（name のみ）→ `SqliteWorkflowRepository.save` | Workflow 存在（archived=false）| `PATCH /api/workflows/{workflow_id}` `{"name": "新フロー名"}` | HTTP 200, `WorkflowResponse`（name="新フロー名" / stages / transitions は変更前と同一）|
| TC-IT-WFH-006 | `workflows_router` → `WorkflowService.update`（DAG 全置換）→ `SqliteWorkflowRepository.save` | Workflow 存在（archived=false）| `PATCH /api/workflows/{workflow_id}` `{"stages": [<新 StageCreate×2>], "transitions": [<新 TransitionCreate×1>], "entry_stage_id": <新 stage_id>}` | HTTP 200, `WorkflowResponse`（新 stages / transitions / entry_stage_id で更新されている）|
| TC-IT-WFH-007 | `workflows_router` → `WorkflowService.archive` → `SqliteWorkflowRepository.save` → 後続 PATCH で 409 確認 | Workflow 存在（archived=false）| `DELETE /api/workflows/{workflow_id}` → 後続 `PATCH /api/workflows/{workflow_id}` `{"name": "変更試み"}` | DELETE: HTTP 204 No Content / 後続 PATCH: HTTP 409 `{"error": {"code": "conflict", "message": "Workflow is archived and cannot be modified."}}` |
| TC-IT-WFH-008 | `workflows_router` → `WorkflowService.find_stages` → `SqliteWorkflowRepository.find_by_id` | Workflow 存在（多ステージ）| `GET /api/workflows/{workflow_id}/stages` | HTTP 200, `StageListResponse`（stages リスト / transitions リスト / entry_stage_id を含む）|
| TC-IT-WFH-009 | `workflows_router` → `WorkflowService.get_presets`（DB クエリなし）| なし | `GET /api/workflows/presets` | HTTP 200, `WorkflowPresetListResponse`（items に "v-model" と "agile" が含まれる / total=2）|
| TC-IT-WFH-011 | `workflows_router` → `WorkflowService.create_for_room` → `RoomNotFoundError` → room 既存ハンドラ | Room 不存在（ランダム UUID）| `POST /api/rooms/{random_uuid}/workflows` `{"name": "X", "stages": [...], "transitions": [], "entry_stage_id": <uuid>}` | HTTP 404, `{"error": {"code": "not_found", "message": "Room not found."}}` |
| TC-IT-WFH-012 | `workflows_router` → `WorkflowService.create_for_room` → `RoomArchivedError` → room 既存ハンドラ | Room 存在（archived=true）| `POST /api/rooms/{room_id}/workflows` `{"name": "X", "stages": [...], "transitions": [], "entry_stage_id": <uuid>}` | HTTP 409, `{"error": {"code": "conflict", "message": "Room is archived and cannot be modified."}}` |
| TC-IT-WFH-013 | `workflows_router` → `WorkflowService.create_for_room` → `WorkflowPresetNotFoundError` → `workflow_preset_not_found_handler` | Room 存在（archived=false）| `POST /api/rooms/{room_id}/workflows` `{"preset_name": "unknown-preset-xyz"}` | HTTP 404, `{"error": {"code": "not_found", "message": "Workflow preset not found."}}` |
| TC-IT-WFH-014 | `workflows_router` → `WorkflowService.create_for_room` → `WorkflowInvariantViolation` → `workflow_invariant_violation_handler` | Room 存在（archived=false）| `POST /api/rooms/{room_id}/workflows` `{"name": "テスト", "stages": [<StageCreate with id=A>], "transitions": [], "entry_stage_id": <存在しない UUID>}` （entry_stage_id が stages に存在しない — R1-4 違反）| HTTP 422, `{"error": {"code": "validation_error", "message": "entry_stage_id が stages に存在しません。"}}` — `[FAIL]` プレフィックスと `\nNext:.*` が HTTP レスポンスに露出しないこと |
| TC-IT-WFH-015 | `WorkflowCreate` model_validator 排他チェック（JSON 定義 + preset_name 同時指定）| Room 存在 | `POST /api/rooms/{room_id}/workflows` `{"name": "X", "stages": [...], "transitions": [], "entry_stage_id": <uuid>, "preset_name": "v-model"}` | HTTP 422（RequestValidationError — Pydantic model_validator 失敗）|
| TC-IT-WFH-016 | `WorkflowCreate` model_validator 排他チェック（JSON 定義も preset_name も None）| Room 存在 | `POST /api/rooms/{room_id}/workflows` `{}` | HTTP 422（RequestValidationError — 両方 None は無効）|
| TC-IT-WFH-017 | `workflows_router` → `WorkflowService.find_by_room` → `RoomNotFoundError` → room 既存ハンドラ | Room 不存在（ランダム UUID）| `GET /api/rooms/{random_uuid}/workflows` | HTTP 404, `{"error": {"code": "not_found", "message": "Room not found."}}` |
| TC-IT-WFH-018 | `workflows_router` → `WorkflowService.find_by_id` → `WorkflowNotFoundError` → `workflow_not_found_handler` | Workflow 不存在（ランダム UUID）| `GET /api/workflows/{random_uuid}` | HTTP 404, `{"error": {"code": "not_found", "message": "Workflow not found."}}` |
| TC-IT-WFH-019 | `workflows_router` → `WorkflowService.update` → `WorkflowNotFoundError` → `workflow_not_found_handler` | Workflow 不存在（ランダム UUID）| `PATCH /api/workflows/{random_uuid}` `{"name": "変更試み"}` | HTTP 404, `{"error": {"code": "not_found", "message": "Workflow not found."}}` |
| TC-IT-WFH-020 | `workflows_router` → `WorkflowService.update` → `WorkflowArchivedError(kind="update")` → `workflow_archived_handler` | Workflow 存在（archived=true）| `PATCH /api/workflows/{workflow_id}` `{"name": "変更試み"}` | HTTP 409, `{"error": {"code": "conflict", "message": "Workflow is archived and cannot be modified."}}` |
| TC-IT-WFH-021 | `workflows_router` → `WorkflowService.update` → `WorkflowInvariantViolation` → `workflow_invariant_violation_handler` | Workflow 存在（archived=false / 2 ステージ）| `PATCH /api/workflows/{workflow_id}` `{"stages": [<StageCreate A>], "transitions": [<A→B>], "entry_stage_id": <A>}` （B が stages に存在しない → R1-5 孤立検査違反）| HTTP 422, `{"error": {"code": "validation_error", "message": <DAG 違反メッセージ本文>}}` |
| TC-IT-WFH-022 | `WorkflowUpdate` model_validator 整合チェック（stages のみ設定、transitions=None）| Workflow 存在 | `PATCH /api/workflows/{workflow_id}` `{"stages": [...]}` （transitions / entry_stage_id が None — 整合バリデーション違反）| HTTP 422（RequestValidationError）|
| TC-IT-WFH-023 | `workflows_router` → `WorkflowService.archive` → `WorkflowNotFoundError` → `workflow_not_found_handler` | Workflow 不存在（ランダム UUID）| `DELETE /api/workflows/{random_uuid}` | HTTP 404, `{"error": {"code": "not_found", "message": "Workflow not found."}}` |
| TC-IT-WFH-024 | `workflows_router` → `WorkflowService.archive` × 2 回（冪等性）| Workflow 存在（archived=false）| `DELETE /api/workflows/{workflow_id}` を 2 回連続送信 | 1 回目: HTTP 204 / 2 回目: HTTP 204（archive() は冪等 — R1-14「再アーカイブは禁止されない」）|
| TC-IT-WFH-025 | `workflows_router` → `WorkflowService.find_stages` → `WorkflowNotFoundError` → `workflow_not_found_handler` | Workflow 不存在（ランダム UUID）| `GET /api/workflows/{random_uuid}/stages` | HTTP 404, `{"error": {"code": "not_found", "message": "Workflow not found."}}` |
| TC-IT-WFH-026 | FastAPI UUID パス検証 → `RequestValidationError` | — | (a) `GET /api/workflows/not-a-uuid` (b) `PATCH /api/workflows/not-a-uuid` (c) `DELETE /api/workflows/not-a-uuid` (d) `GET /api/workflows/not-a-uuid/stages` (e) `POST /api/rooms/not-a-uuid/workflows` (f) `GET /api/rooms/not-a-uuid/workflows` | (a)〜(f) すべて HTTP 422（500 ではないことを確認 — T3: UUID パスインジェクション防御）|
| TC-IT-WFH-027 | `GET /api/workflows/presets` リテラルパス優先（ルーティング順序検証）| — | `GET /api/workflows/presets` を `GET /api/workflows/{id}` より先に登録されているか確認（TestClient 経由）| HTTP 200（404 / パスパラメータ解釈エラーではないこと）— 設計書 §確定E「ルーティング登録順序」の物理保証 |
| TC-IT-WFH-028 | CSRF ミドルウェア → `POST /api/rooms/{room_id}/workflows` | Room 存在 | `Origin: http://evil.example.com` ヘッダ付きの `POST /api/rooms/{room_id}/workflows` | HTTP 403（T1: CSRF 保護 — http-api-foundation TC-IT-HAF-008 と同一パターン。workflows_router でも CSRF ミドルウェアが適用されることの物理保証）|
| TC-IT-WFH-029 | A02 masking — `StageResponse.notify_channels` が POST 201 / PATCH 200 レスポンスで masked になること（`detailed-design.md §確定A` 物理保証）| Empire 存在 / Room 存在（archived=false）/ テスト用 Discord webhook URL として `tests/factories/workflow.py` の `DEFAULT_DISCORD_WEBHOOK`（`"https://discord.com/api/webhooks/123456789012345678/SyntheticToken_-abcXYZ"`）を使用 | (a) `notify_channels=["https://discord.com/api/webhooks/123456789012345678/SyntheticToken_-abcXYZ"]` を持つ `EXTERNAL_REVIEW` kind Stage を含む JSON で `POST /api/rooms/{room_id}/workflows` を送信。(b) 作成した Workflow に対して `PATCH /api/workflows/{id}` で名前変更（DAG 維持）を送信。 | (a) HTTP 201 レスポンスの当該 Stage `notify_channels` フィールドが `<REDACTED:DISCORD_WEBHOOK>` を含む文字列であること — raw URL のトークン部（`SyntheticToken_-abcXYZ` 等）がレスポンス JSON に現れないことを `assert "SyntheticToken_-abcXYZ" not in ...` で確認。(b) HTTP 200 レスポンスでも同様に masked 文字列（POST 直後の in-memory domain object と PATCH 後 DB 再取得の両経路で masking が保証されることを物理検証 — A02 Cryptographic Failures 防御）|

## ユニットテストケース

| テスト ID | 対象 | 種別 | 入力（factory / mock）| 期待結果 |
|---|---|---|---|---|
| TC-UT-WFH-001 | `StageCreate` スキーマ | 正常系 / 異常系 | (a) 有効な StageCreate（kind="WORK", required_role=["DEVELOPER"] など）(b) `name=""` (c) `name="x"*81` (d) `required_role=[]`（R1-9 違反）(e) `kind="INVALID_KIND"` (f) `extra_field="z"` | (a) バリデーション通過 / (b) min_length 違反 → ValidationError / (c) max_length 違反 → ValidationError / (d) min_length 違反（空リスト不可）→ ValidationError / (e) 無効 enum 値 → ValidationError / (f) extra 禁止（`extra="forbid"`）→ ValidationError |
| TC-UT-WFH-002 | `TransitionCreate` スキーマ | 正常系 / 異常系 | (a) 有効な TransitionCreate（condition="SUCCESS"）(b) `condition="INVALID"` (c) `from_stage_id` と `to_stage_id` が同一 UUID（self-loop）(d) `extra_field="z"` | (a) 通過 / (b) 無効 enum 値 → ValidationError / (c) 通過（domain 層で DAG 検査するためスキーマ層は拒否しない）/ (d) extra 禁止 → ValidationError |
| TC-UT-WFH-003 | `WorkflowCreate` スキーマ（排他バリデーション）| 正常系 / 異常系 | (a) `preset_name="v-model"`, 他は None（プリセットモード）(b) `name="X", stages=[...], transitions=[], entry_stage_id=<uuid>`（JSON 定義モード）(c) `preset_name="v-model"` + `stages=[...]`（両方指定 — 排他違反）(d) 全フィールド None（両方 None — 排他違反）(e) `preset_name="v-model"` + `name="上書き名"`（name 上書きは許容）(f) `extra_field="z"` | (a)(b)(e) 通過 / (c)(d) model_validator → ValidationError / (f) extra 禁止 → ValidationError |
| TC-UT-WFH-004 | `WorkflowUpdate` スキーマ（整合バリデーション）| 正常系 / 異常系 | (a) `name="新名前"` のみ（DAG 更新なし）(b) `stages=[...], transitions=[...], entry_stage_id=<uuid>`（DAG 全置換）(c) 全フィールド None（変更なし）(d) `stages=[...]` のみ（transitions=None — 整合バリデーション違反）(e) `name=""`（min_length 違反）(f) `extra_field="z"` | (a)(b)(c) 通過 / (d) model_validator → ValidationError（DAG の部分更新は整合性を壊す）/ (e) min_length 違反 → ValidationError / (f) extra 禁止 → ValidationError |
| TC-UT-WFH-005 | `WorkflowResponse` / `StageListResponse` / `WorkflowPresetListResponse` レスポンススキーマ | 正常系 | `tests/factories/workflow.py` の `make_workflow()` から生成した domain オブジェクトをスキーマに渡す | `id` が str（UUID 文字列 `str(workflow.id)`）/ `stages` が `list[StageResponse]`（各 id / kind / required_role が str リスト）/ `transitions` が `list[TransitionResponse]` / `entry_stage_id` が str / `archived` が bool / `WorkflowListResponse.total` が `len(items)` と一致 / `StageListResponse` が stages + transitions + entry_stage_id を持つ / `WorkflowPresetListResponse.total=2`（v-model / agile）|
| TC-UT-WFH-006 | `workflow_not_found_handler`（`detailed-design.md §確定C`）| 異常系 | `WorkflowNotFoundError(workflow_id="test-id")` | HTTP 404, `{"error": {"code": "not_found", "message": "Workflow not found."}}` — MSG-WF-HTTP-001 確定文言と完全一致 |
| TC-UT-WFH-007 | `workflow_archived_handler`（`detailed-design.md §確定C`）| 異常系 | `WorkflowArchivedError(workflow_id="test-id", kind="update")` | HTTP 409, `{"error": {"code": "conflict", "message": "Workflow is archived and cannot be modified."}}` — MSG-WF-HTTP-002 確定文言と完全一致（`kind="assign"` は設計変更により削除済み）|
| TC-UT-WFH-008 | `workflow_preset_not_found_handler`（`detailed-design.md §確定C`）| 異常系 | `WorkflowPresetNotFoundError(preset_name="unknown")` | HTTP 404, `{"error": {"code": "not_found", "message": "Workflow preset not found."}}` — MSG-WF-HTTP-004 確定文言と完全一致 |
| TC-UT-WFH-009 | `workflow_invariant_violation_handler`（`detailed-design.md §確定C` 前処理ルール）| 異常系 | (a) `WorkflowInvariantViolation` で message=`"[FAIL] entry_stage_id が stages に存在しません。\nNext: 有効な stage_id を指定してください。"` (b) message=`"[FAIL] Stage 数が上限を超えています。"` （Next: なし）| (a) HTTP 422, `{"error": {"code": "validation_error", "message": "entry_stage_id が stages に存在しません。"}}` — `[FAIL]` プレフィックスと `\nNext:.*` が除去されていること / (b) HTTP 422, `{"error": {"code": "validation_error", "message": "Stage 数が上限を超えています。"}}` — strip 後に Next: が残らないこと |
| TC-UT-WFH-010 | `WorkflowService.__init__`（3 引数構造 — `detailed-design.md §確定G`）| 正常系 | `workflow_repo=MagicMock()` / `room_repo=MagicMock()` / `session=MagicMock()` | インスタンス生成成功 / `_workflow_repo` / `_room_repo` / `_session` に各 mock が格納される（http-api-foundation の単一 repo 骨格から 3 引数構造への拡張を検証）|
| TC-UT-WFH-020 | 依存方向（静的解析: `ast.walk()` 全ノード走査 — スコープ: `routers/` + `schemas/`）| 異常系 | `ast.walk(ast.parse(src))` で `interfaces/http/routers/workflows.py` + `interfaces/http/schemas/workflow.py` を全ノード（関数内・クラス内・メソッド内含む）走査する（`app.py` / `dependencies.py` / `error_handlers.py` は除外）| `bakufu.domain` / `bakufu.infrastructure` への import ノード（`ImportFrom` / `Import` の全出現、トップレベル限定でない）が存在しないことを `assert` で確認。**`tree.body` のみの走査では関数内遅延 import を見逃す。`ast.walk()` による全ノード走査が必須**（TC-UT-RM-HTTP-010 の同一 `ast.walk()` 走査方式に準拠。旧 `tree.body` パターンへの退行を禁止する）|

## カバレッジ基準

| 対象 | 方針 |
|---|---|
| `interfaces/http/routers/workflows.py` | TC-IT-WFH-001〜029 で全 7 エンドポイントを網羅。branch coverage 90% 以上 |
| `interfaces/http/schemas/workflow.py` | TC-UT-WFH-001〜005 で全スキーマの全フィールド / 全 validation ルール（排他バリデーション・整合バリデーション含む）を検証 |
| `interfaces/http/error_handlers.py`（workflow 追記分）| TC-IT-WFH-013/014/018/019/020/021/023 + TC-UT-WFH-006〜009 で全ハンドラ（`workflow_not_found_handler` / `workflow_archived_handler` / `workflow_preset_not_found_handler` / `workflow_invariant_violation_handler`）を網羅。TC-UT-WFH-007 で `kind="update"` を単独検証（`kind="assign"` は設計変更により削除済み）|
| `application/services/workflow_service.py` | TC-IT-WFH-001〜009/029 の結合テストで全メソッド（create_for_room / find_by_room / find_by_id / update / archive / find_stages / get_presets）を起動。TC-UT-WFH-010 でインスタンス化・3 引数構造を確認 |
| `application/exceptions/workflow_exceptions.py` | TC-IT-WFH-013/018/019/020/021/023/024/025 の結合テストで全例外クラス（`WorkflowNotFoundError` / `WorkflowArchivedError` / `WorkflowPresetNotFoundError`）が発火 → ハンドラを経由することを確認 |
| A02 masking（POST/PATCH 経路）| TC-IT-WFH-029 で EXTERNAL_REVIEW Stage を含む POST/PATCH レスポンスの `notify_channels` が `<REDACTED:DISCORD_WEBHOOK>` masked であることを物理検証（`detailed-design.md §確定A`）|
| 孤児要件なし | REQ-WF-HTTP-001〜007・MSG-WF-HTTP-001/002/004/005・受入基準 #13〜21 の全件がテストマトリクスに紐付けられている（MSG-WF-HTTP-003 / 受入基準 #22 は設計変更により削除済み）|
