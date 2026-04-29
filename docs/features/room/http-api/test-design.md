# テスト設計書

> feature: `room` / sub-feature: `http-api`
> 関連 Issue: [#57 feat(room-http-api): Room + Agent assignment HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/57)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../system-test-design.md`](../system-test-design.md)

## 本書の役割

本書は **テストケースで検証可能な単位までトレーサビリティを担保する**。`basic-design.md §モジュール契約` の REQ-RM-HTTP-NNN / `detailed-design.md §MSG 確定文言表` の MSG-RM-HTTP-NNN / 親 `feature-spec.md §9 受入基準` #19〜31 / 脅威 T1〜T4 を、それぞれ最低 1 件のテストケースで検証する。

**書くこと**:
- REQ-RM-HTTP-NNN / MSG-RM-HTTP-NNN / 受入基準 # / 脅威を実テストケース（TC-IT / TC-UT）に紐付けるマトリクス
- 外部 I/O 依存マップ（factory / raw fixture の characterization 状態を含む）
- 各レベルのテストケース定義（前提条件 / 操作 / 期待結果）
- モック方針
- カバレッジ基準

**書かないこと**:
- E2E テスト（TC-E2E-RM-001〜003）→ 親 [`../system-test-design.md`](../system-test-design.md) が扱う
- 受入テスト → [`docs/acceptance-tests/scenarios/`](../../../acceptance-tests/scenarios/)

## テストケース ID 採番規則

本 sub-feature のテスト ID 体系:

| 番号帯 | 用途 |
|---|---|
| TC-IT-RM-HTTP-001〜020 | 結合テスト（HTTP リクエスト / DI / 例外ハンドラ）|
| TC-IT-RM-HTTP-021〜 | 予約番号帯（将来の room 拡張 API で利用）|
| TC-UT-RM-HTTP-001〜006 | ユニットテスト（スキーマ / 例外ハンドラ / サービス）|
| TC-UT-RM-HTTP-010〜 | 静的解析系テスト専用帯（依存方向 / import 解析）|

## テストマトリクス

| 要件 ID | 実装アーティファクト | テストケース ID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-RM-HTTP-001 | `rooms_router` POST + `RoomService.create` | TC-IT-RM-HTTP-001 | 結合 | 正常系 | feature-spec.md §9 #19 |
| REQ-RM-HTTP-001（name 重複）| `rooms_router` POST + `RoomNameAlreadyExistsError` | TC-IT-RM-HTTP-002 | 結合 | 異常系 | feature-spec.md §9 #20 |
| REQ-RM-HTTP-001（Empire 不在）| `rooms_router` POST + `EmpireNotFoundError` | TC-IT-RM-HTTP-003 | 結合 | 異常系 | feature-spec.md §9 #21 |
| REQ-RM-HTTP-001（Workflow 不在）| `rooms_router` POST + `WorkflowNotFoundError` | TC-IT-RM-HTTP-014 | 結合 | 異常系 | Q-3 |
| REQ-RM-HTTP-002 | `rooms_router` GET list + `RoomService.find_all_by_empire` | TC-IT-RM-HTTP-004 | 結合 | 正常系 | feature-spec.md §9 #22 |
| REQ-RM-HTTP-002（Empire 不在）| `rooms_router` GET list + `EmpireNotFoundError` | TC-IT-RM-HTTP-017 | 結合 | 異常系 | Q-3 |
| REQ-RM-HTTP-003 | `rooms_router` GET by id + `RoomService.find_by_id` | TC-IT-RM-HTTP-005 | 結合 | 正常系 | feature-spec.md §9 #23 |
| REQ-RM-HTTP-003（不在）| `rooms_router` GET by id + `RoomNotFoundError` | TC-IT-RM-HTTP-006 | 結合 | 異常系 | feature-spec.md §9 #24 |
| REQ-RM-HTTP-004 | `rooms_router` PATCH + `RoomService.update` | TC-IT-RM-HTTP-007 | 結合 | 正常系 | feature-spec.md §9 #25 |
| REQ-RM-HTTP-004（archived）| `rooms_router` PATCH + `RoomArchivedError` | TC-IT-RM-HTTP-008 | 結合 | 異常系 | feature-spec.md §9 #26 |
| REQ-RM-HTTP-004（不在）| `rooms_router` PATCH + `RoomNotFoundError` | TC-IT-RM-HTTP-018 | 結合 | 異常系 | Q-3 |
| REQ-RM-HTTP-005 | `rooms_router` DELETE + `RoomService.archive` | TC-IT-RM-HTTP-009 | 結合 | 正常系 | feature-spec.md §9 #27 |
| REQ-RM-HTTP-005（不在）| `rooms_router` DELETE + `RoomNotFoundError` | TC-IT-RM-HTTP-019 | 結合 | 異常系 | Q-3 |
| REQ-RM-HTTP-006 | `rooms_router` POST agents + `RoomService.assign_agent` | TC-IT-RM-HTTP-010 | 結合 | 正常系 | feature-spec.md §9 #28 |
| REQ-RM-HTTP-006（Room archived）| `rooms_router` POST agents + `RoomArchivedError` | TC-IT-RM-HTTP-011 | 結合 | 異常系 | feature-spec.md §9 #29 |
| REQ-RM-HTTP-006（Agent 不在）| `rooms_router` POST agents + `AgentNotFoundError` | TC-IT-RM-HTTP-015 | 結合 | 異常系 | Q-3 |
| REQ-RM-HTTP-007 | `rooms_router` DELETE agents/{agent_id}/roles/{role} + `RoomService.unassign_agent` | TC-IT-RM-HTTP-012 | 結合 | 正常系 | feature-spec.md §9 #30 |
| REQ-RM-HTTP-007（membership 不在）| `rooms_router` DELETE agents + `RoomInvariantViolation(kind='member_not_found')` | TC-IT-RM-HTTP-016 | 結合 | 異常系 | Q-3 |
| REQ-RM-HTTP-007（Room archived）| `rooms_router` DELETE agents + `RoomArchivedError` | TC-IT-RM-HTTP-020 | 結合 | 異常系 | Q-3 |
| R1-10（不正 UUID）| FastAPI UUID パス検証 → 422 | TC-IT-RM-HTTP-013 | 結合 | 異常系 | feature-spec.md §9 #31 |
| MSG-RM-HTTP-001 | `room_name_already_exists_handler` | TC-IT-RM-HTTP-002 | 結合 | 異常系 | Q-3 |
| MSG-RM-HTTP-002 | `room_not_found_handler` | TC-IT-RM-HTTP-006 | 結合 | 異常系 | Q-3 |
| MSG-RM-HTTP-003 | `room_archived_handler` | TC-IT-RM-HTTP-008 | 結合 | 異常系 | Q-3 |
| MSG-RM-HTTP-004 | `agent_not_found_handler` | TC-IT-RM-HTTP-015 | 結合 | 異常系 | Q-3 |
| MSG-RM-HTTP-005 | `room_invariant_violation_handler`（kind='member_not_found'）| TC-IT-RM-HTTP-016 | 結合 | 異常系 | Q-3 |
| MSG-RM-HTTP-006 | `workflow_not_found_handler` | TC-IT-RM-HTTP-014 | 結合 | 異常系 | Q-3 |
| MSG-RM-HTTP-007 | `room_invariant_violation_handler`（前処理ルール + kind 分岐）| TC-UT-RM-HTTP-005 | ユニット | 異常系 | Q-3 |
| `RoomCreate` スキーマ | `schemas/room.py` | TC-UT-RM-HTTP-001 | ユニット | 正常系 / 異常系 | Q-3 |
| `RoomUpdate` スキーマ | `schemas/room.py` | TC-UT-RM-HTTP-002 | ユニット | 正常系 / 異常系 | Q-3 |
| `AgentAssignRequest` スキーマ | `schemas/room.py` | TC-UT-RM-HTTP-003 | ユニット | 正常系 / 異常系 | Q-3 |
| `RoomResponse` / `MemberResponse` / `RoomListResponse` スキーマ | `schemas/room.py` | TC-UT-RM-HTTP-004 | ユニット | 正常系 | Q-3 |
| `RoomService.__init__`（4 repo）| `application/services/room_service.py` | TC-UT-RM-HTTP-006 | ユニット | 正常系 | Q-3 |
| T1（CSRF）| CSRF ミドルウェア → POST /api/empires/{empire_id}/rooms | TC-IT-RM-HTTP-001（CSRF バリアント）| 結合 | 異常系 | Q-3 |
| T3（不正 UUID パスインジェクション）| FastAPI UUID 型強制（basic-design.md §セキュリティ設計）| TC-IT-RM-HTTP-013 | 結合 | 異常系 | Q-3 |
| T4（PromptKit マスキング）| MaskedText TypeDecorator（repository layer）| TC-IT-RR-008-masking（[`../repository/test-design.md`](../repository/test-design.md)）| — | — | feature-spec.md §9 #18 |
| 依存方向（interfaces → domain 直参照禁止）| `interfaces/http/routers/` + `interfaces/http/schemas/`（スコープ限定）| TC-UT-RM-HTTP-010 | ユニット（静的解析）| 異常系 | Q-3 |
| Q-1 | pyright / ruff | CI ジョブ | — | — | Q-1 |
| Q-2 | pytest --cov | CI ジョブ | — | — | Q-2 |

**マトリクス充足の証拠**:
- REQ-RM-HTTP-001〜007 すべてに最低 1 件の正常系テストケース（TC-IT-RM-HTTP-001/004/005/007/009/010/012）
- REQ-RM-HTTP-001〜007 の主要な異常系（name 重複 / 不在 / archived / 不正 UUID / Agent 不在 / membership 不在 / Workflow 不在）が各 TC-IT で網羅（001〜020）
- MSG-RM-HTTP-001〜007 の全件が `response.json()["error"]["code"]` / `"message"` の静的照合テストで確認
- 親受入基準 #19〜31 のすべてが TC-IT-RM-HTTP-001〜013 で対応（1:1 網羅）
- T1（CSRF）/ T3（不正 UUID）脅威への対策が最低 1 件で有効性確認
- T4（PromptKit マスキング）は repository layer の責務のため repository test-design.md 参照（孤児ではない）
- 孤児要件なし

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture / factory | characterization 状態 |
|---|---|---|---|
| SQLite（テスト用 DB）| `get_session()` DI / lifespan 経由の Session / RoomRepository / EmpireRepository | `tests/factories/db.py`（http-api-foundation で定義済み）+ `tmp_path` tempfile | **済** |
| FastAPI ASGI | HTTP リクエスト送信（AsyncClient）| `httpx.AsyncClient(ASGITransport(app=app), base_url="http://test")`（`room_app_client` fixture — empire と同パターン）| **済**（conftest.py に追記要）|
| Workflow SQLite レコード | `RoomService.create` の Workflow 存在確認（TC-IT-RM-HTTP-001 / 014）| `tests/factories/workflow.py`（未作成）— WorkflowRow を tempdb に直接 INSERT | **要起票** |
| Agent SQLite レコード | `RoomService.assign_agent` の Agent 存在確認（TC-IT-RM-HTTP-010 / 015）| `tests/factories/agent.py`（未作成）— AgentRow を tempdb に直接 INSERT | **要起票** |

> **重要**: Workflow factory および Agent factory（上表「**要起票**」）が完成するまで
> TC-IT-RM-HTTP-001（POST happy path）および TC-IT-RM-HTTP-010（assign_agent happy path）のテスト実装に着手してはならない。
> `tests/factories/workflow.py` / `tests/factories/agent.py` を先行 task として起票すること。
> Workflow / Agent factory が未定義のまま実装に入ったテストは assumed mock（禁止）とみなしレビューで却下する。

## モック方針

| 対象 | テストレベル | モック戦略 |
|---|---|---|
| SQLite DB | IT（結合）| モックなし — `tmp_path` 配下 tempfile を使用する実 SQLite。8 PRAGMA + WAL を production と同一設定で起動 |
| SQLite DB | UT（ユニット）| `MagicMock()` でリポジトリをモック（DB アクセスなし）|
| FastAPI ASGI | IT | `httpx.AsyncClient(ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test")` |
| Workflow / Agent（happy path）| IT | 上表 factory で tempdb に直接 INSERT した実データを参照（assumed mock 禁止）|
| Workflow / Agent | UT | `MagicMock()` で代替 |
| EmpireRepository / RoomRepository 等 | UT | `MagicMock()` で代替（TC-UT-RM-HTTP-006 等）|

## 結合テストケース

| テスト ID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|---|
| TC-IT-RM-HTTP-001 | `rooms_router` → `RoomService.create` → `SqliteRoomRepository.save` | 実 SQLite tempdb + Workflow factory | Empire 存在 / Workflow 存在 | `POST /api/empires/{empire_id}/rooms` `{"name": "Vモデル開発室", "workflow_id": <wf_id>, "description": "", "prompt_kit_prefix_markdown": ""}` | HTTP 201, `{"id": <uuid>, "name": "Vモデル開発室", "description": "", "workflow_id": <wf_id_str>, "members": [], "prompt_kit_prefix_markdown": "", "archived": false}` |
| TC-IT-RM-HTTP-002 | `rooms_router` → `RoomService.create` → `RoomNameAlreadyExistsError` → `room_name_already_exists_handler` | 実 SQLite tempdb | Empire 存在 / Workflow 存在 / 同名 Room 存在（事前 POST 済）| `POST /api/empires/{empire_id}/rooms` `{"name": "Vモデル開発室", "workflow_id": <wf_id>, ...}` | HTTP 409, `{"error": {"code": "conflict", "message": "Room name already exists in this empire."}}` |
| TC-IT-RM-HTTP-003 | `rooms_router` → `RoomService.create` → `EmpireNotFoundError` → empire_not_found_handler（既存）| 実 SQLite tempdb | Empire 不存在（ランダム UUID）| `POST /api/empires/{random_uuid}/rooms` `{"name": "X", "workflow_id": <uuid>, ...}` | HTTP 404, `{"error": {"code": "not_found", "message": "Empire not found."}}` |
| TC-IT-RM-HTTP-004 | `rooms_router` → `RoomService.find_all_by_empire` → `SqliteRoomRepository.find_all_by_empire` | 実 SQLite tempdb | (a) Empire 存在 / Room 0 件 (b) Empire 存在 / Room 2 件（事前 POST 済）| (a)(b) `GET /api/empires/{empire_id}/rooms` | (a) HTTP 200, `{"items": [], "total": 0}` (b) HTTP 200, `{"items": [<RoomResponse>, <RoomResponse>], "total": 2}`（items の name 一致確認）|
| TC-IT-RM-HTTP-005 | `rooms_router` → `RoomService.find_by_id` → `SqliteRoomRepository.find_by_id` | 実 SQLite tempdb | Room 存在（事前 POST 済）| `GET /api/rooms/{room_id}` | HTTP 200, `RoomResponse`（name 一致 / archived=false 確認）|
| TC-IT-RM-HTTP-006 | `rooms_router` → `RoomService.find_by_id` → `RoomNotFoundError` → `room_not_found_handler` | 実 SQLite tempdb | Room 不存在（ランダム UUID）| `GET /api/rooms/{random_uuid}` | HTTP 404, `{"error": {"code": "not_found", "message": "Room not found."}}` |
| TC-IT-RM-HTTP-007 | `rooms_router` → `RoomService.update` → `SqliteRoomRepository.save` | 実 SQLite tempdb | Room 存在（archived=false）| `PATCH /api/rooms/{room_id}` `{"name": "新Vモデル開発室"}` | HTTP 200, `RoomResponse`（name="新Vモデル開発室"）|
| TC-IT-RM-HTTP-008 | `rooms_router` → `RoomService.update` → `RoomArchivedError` → `room_archived_handler` | 実 SQLite tempdb | Room 存在（archived=true）| `PATCH /api/rooms/{room_id}` `{"name": "変更試み"}` | HTTP 409, `{"error": {"code": "conflict", "message": "Room is archived and cannot be modified."}}` |
| TC-IT-RM-HTTP-009 | `rooms_router` → `RoomService.archive` → `SqliteRoomRepository.save` | 実 SQLite tempdb | Room 存在（archived=false）| `DELETE /api/rooms/{room_id}` → 後続 `GET /api/rooms/{room_id}` | HTTP 204 No Content / GET → `RoomResponse`（archived=true）|
| TC-IT-RM-HTTP-010 | `rooms_router` → `RoomService.assign_agent` → `SqliteRoomRepository.save` | 実 SQLite tempdb + Agent factory | Room 存在（archived=false）/ Agent 存在 | `POST /api/rooms/{room_id}/agents` `{"agent_id": <agent_id>, "role": "LEADER"}` | HTTP 201, `RoomResponse`（members に `{"agent_id": <agent_id_str>, "role": "LEADER", "joined_at": <iso8601>}` 含む）|
| TC-IT-RM-HTTP-011 | `rooms_router` → `RoomService.assign_agent` → `RoomArchivedError` → `room_archived_handler` | 実 SQLite tempdb | Room 存在（archived=true）| `POST /api/rooms/{room_id}/agents` `{"agent_id": <uuid>, "role": "LEADER"}` | HTTP 409, `{"error": {"code": "conflict", "message": "Room is archived and cannot be modified."}}` |
| TC-IT-RM-HTTP-012 | `rooms_router` → `RoomService.unassign_agent` → `SqliteRoomRepository.save` | 実 SQLite tempdb | Room 存在（archived=false）/ Agent membership 存在（事前 POST 済）| `DELETE /api/rooms/{room_id}/agents/{agent_id}/roles/LEADER` | HTTP 204 No Content / 後続 `GET /api/rooms/{room_id}` で members が空（membership 削除確認）|
| TC-IT-RM-HTTP-013 | FastAPI UUID パス検証 → `RequestValidationError` | 実 SQLite tempdb | — | (a) `GET /api/rooms/not-a-uuid` (b) `PATCH /api/rooms/not-a-uuid` (c) `DELETE /api/rooms/not-a-uuid` (d) `GET /api/empires/not-a-uuid/rooms` (e) `POST /api/empires/not-a-uuid/rooms` (f) `DELETE /api/rooms/{room_id}/agents/not-a-uuid/roles/LEADER` | (a)〜(f) すべて HTTP 422（500 ではないことを確認 — 業務ルール R1-10 / BUG-EM-SEC-001 準拠）|
| TC-IT-RM-HTTP-014 | `rooms_router` → `RoomService.create` → `WorkflowNotFoundError` → `workflow_not_found_handler` | 実 SQLite tempdb | Empire 存在 / Workflow 不存在（ランダム UUID）| `POST /api/empires/{empire_id}/rooms` `{"name": "X", "workflow_id": <random_uuid>, "description": "", "prompt_kit_prefix_markdown": ""}` | HTTP 404, `{"error": {"code": "not_found", "message": "Workflow not found."}}` |
| TC-IT-RM-HTTP-015 | `rooms_router` → `RoomService.assign_agent` → `AgentNotFoundError` → `agent_not_found_handler` | 実 SQLite tempdb | Room 存在（archived=false）/ Agent 不存在（ランダム UUID）| `POST /api/rooms/{room_id}/agents` `{"agent_id": <random_uuid>, "role": "REVIEWER"}` | HTTP 404, `{"error": {"code": "not_found", "message": "Agent not found."}}` |
| TC-IT-RM-HTTP-016 | `rooms_router` → `RoomService.unassign_agent` → `RoomInvariantViolation(kind='member_not_found')` → `room_invariant_violation_handler` | 実 SQLite tempdb | Room 存在（archived=false）/ 指定 membership 不存在（未割り当て）| `DELETE /api/rooms/{room_id}/agents/{agent_id}/roles/LEADER`（agent_id は未割り当て）| HTTP 404, `{"error": {"code": "not_found", "message": "Agent membership not found in this room."}}` |
| TC-IT-RM-HTTP-017 | `rooms_router` → `RoomService.find_all_by_empire` → `EmpireNotFoundError` → empire_not_found_handler（既存）| 実 SQLite tempdb | Empire 不存在（ランダム UUID）| `GET /api/empires/{random_uuid}/rooms` | HTTP 404, `{"error": {"code": "not_found", "message": "Empire not found."}}` |
| TC-IT-RM-HTTP-018 | `rooms_router` → `RoomService.update` → `RoomNotFoundError` → `room_not_found_handler` | 実 SQLite tempdb | Room 不存在（ランダム UUID）| `PATCH /api/rooms/{random_uuid}` `{"name": "変更試み"}` | HTTP 404, `{"error": {"code": "not_found", "message": "Room not found."}}` |
| TC-IT-RM-HTTP-019 | `rooms_router` → `RoomService.archive` → `RoomNotFoundError` → `room_not_found_handler` | 実 SQLite tempdb | Room 不存在（ランダム UUID）| `DELETE /api/rooms/{random_uuid}` | HTTP 404, `{"error": {"code": "not_found", "message": "Room not found."}}` |
| TC-IT-RM-HTTP-020 | `rooms_router` → `RoomService.unassign_agent` → `RoomArchivedError` → `room_archived_handler` | 実 SQLite tempdb | Room 存在（archived=true）| `DELETE /api/rooms/{room_id}/agents/{agent_id}/roles/LEADER` | HTTP 409, `{"error": {"code": "conflict", "message": "Room is archived and cannot be modified."}}` |

**CSRF 結合テスト補足**: TC-IT-RM-HTTP-001 の異常系バリアントとして、`Origin: http://evil.example.com` ヘッダ付きの `POST /api/empires/{empire_id}/rooms` が HTTP 403 を返すことを確認する（T1: CSRF 保護、http-api-foundation TC-IT-HAF-008 と同一パターン。room_router でも CSRF ミドルウェアが適用されることの物理保証）。

**部分更新検証補足**: PATCH で全フィールド `None`（省略）の場合に既存値が保持されることを TC-IT-RM-HTTP-021（予約番号帯）として追加することを推奨する（`detailed-design.md §確定G` 部分更新ルール凍結の検証）。

## ユニットテストケース

| テスト ID | 対象 | 種別 | 入力（factory / mock）| 期待結果 |
|---|---|---|---|---|
| TC-UT-RM-HTTP-001 | `RoomCreate` スキーマ | 正常系 / 異常系 | (a) `name="Vモデル開発室", workflow_id=uuid4()` (b) `name=""` (c) `name="x"*81` (d) `description="x"*501` (e) `prompt_kit_prefix_markdown="x"*10001` (f) `extra_field="z"` | (a) バリデーション通過 / (b) min_length 違反 → ValidationError / (c) max_length 違反 → ValidationError / (d) description max_length 違反 → ValidationError / (e) prompt_kit max_length 違反 → ValidationError / (f) extra 禁止 → ValidationError |
| TC-UT-RM-HTTP-002 | `RoomUpdate` スキーマ | 正常系 / 異常系 | (a) `name="新名前"` (b) `name=None` (c) `name=""` (d) `description=None` (e) 全フィールド `None` (f) `extra_field="z"` | (a) 通過 / (b) `name=None` で通過（変更なし）/ (c) min_length 違反 → ValidationError / (d) 通過（None は変更なし）/ (e) 全 None で通過 / (f) extra 禁止 → ValidationError |
| TC-UT-RM-HTTP-003 | `AgentAssignRequest` スキーマ | 正常系 / 異常系 | (a) `agent_id=uuid4(), role="LEADER"` (b) `role=""` (c) `role="x"*51` (d) `extra_field="z"` | (a) 通過 / (b) min_length 違反 → ValidationError / (c) max_length 違反 → ValidationError / (d) extra 禁止 → ValidationError |
| TC-UT-RM-HTTP-004 | `RoomResponse` / `MemberResponse` / `RoomListResponse` スキーマ | 正常系 | Room ドメインオブジェクト（id / name / description / workflow_id / members / prompt_kit_prefix_markdown / archived）| `id` が str（UUID 文字列）/ `workflow_id` が str / `members` が `list[MemberResponse]`（各 `agent_id` str / `role` str / `joined_at` ISO 8601 str）/ `archived` が bool / `RoomListResponse.total` が `len(items)` と一致 |
| TC-UT-RM-HTTP-005 | `room_invariant_violation_handler`（`detailed-design.md §確定C` 前処理ルール）| 異常系 | (a) `kind="name_range"`, message=`"[FAIL] Room name は 1〜80 文字でなければなりません。\nNext: 1〜80 文字の名前を指定してください。"` (b) `kind="member_not_found"`, message=任意 | (a) HTTP 422, `{"error": {"code": "validation_error", "message": "Room name は 1〜80 文字でなければなりません。"}}` — `[FAIL]` プレフィックスと `\nNext:.*` が除去されていること / (b) HTTP 404, `{"error": {"code": "not_found", "message": "Agent membership not found in this room."}}` — kind='member_not_found' 分岐（MSG-RM-HTTP-005）確認 |
| TC-UT-RM-HTTP-006 | `RoomService.__init__`（4 repo 構造 — `detailed-design.md §確定G`）| 正常系 | `room_repo=MagicMock()` / `empire_repo=MagicMock()` / `workflow_repo=MagicMock()` / `agent_repo=MagicMock()` | インスタンス生成成功 / `_room_repo` / `_empire_repo` / `_workflow_repo` / `_agent_repo` に各 mock が格納される（http-api-foundation の単一 repo 骨格からの拡張を検証）|
| TC-UT-RM-HTTP-010 | 依存方向（静的解析: `ast.walk()` 全ノード走査 — スコープ: `routers/` + `schemas/`）| 異常系 | `ast.walk(ast.parse(src))` で `interfaces/http/routers/` + `interfaces/http/schemas/` 配下の全 `.py` を全ノード（関数内・クラス内・メソッド内含む）走査する（`app.py` / `dependencies.py` / `error_handlers.py` は除外 — これらは基盤層でドメイン参照を持ち得るため別途管理）| `bakufu.domain` / `bakufu.infrastructure` への import ノード（`ImportFrom` / `Import` の全出現、トップレベル限定でない）が存在しないことを `assert` で確認。**`tree.body` のみの走査では関数内遅延 import（例: `def f(): from bakufu.domain import X`）を見逃す。`ast.walk()` による全ノード走査が必須**（TC-UT-EM-HTTP-010 の同一 `ast.walk()` 走査方式に準拠。旧 `tree.body` パターンへの退行を禁止する）|

## カバレッジ基準

| 対象 | 方針 |
|---|---|
| `interfaces/http/routers/rooms.py` | TC-IT-RM-HTTP-001〜020 で全 7 エンドポイントを網羅。branch coverage 90% 以上 |
| `interfaces/http/schemas/room.py` | TC-UT-RM-HTTP-001〜004 で全スキーマの全フィールド / 全 validation ルールを検証 |
| `interfaces/http/error_handlers.py`（room 追記分）| TC-IT-RM-HTTP-002/006/008/011/014/015/016/020 と TC-UT-RM-HTTP-005 で全ハンドラ（`room_not_found_handler` / `room_name_already_exists_handler` / `room_archived_handler` / `workflow_not_found_handler` / `agent_not_found_handler` / `room_invariant_violation_handler`）を網羅。`kind='member_not_found'` 分岐を TC-UT-RM-HTTP-005(b) で単独検証 |
| `application/services/room_service.py` | TC-IT-RM-HTTP-001〜020 の結合テストで全メソッド（create / find_all_by_empire / find_by_id / update / archive / assign_agent / unassign_agent）を起動。TC-UT-RM-HTTP-006 でインスタンス化・4 repo 格納を確認 |
| `application/exceptions/room_exceptions.py` | TC-IT-RM-HTTP-002/006/008/011/014/015/016/019/020 の結合テストで全例外クラス（`RoomNotFoundError` / `RoomNameAlreadyExistsError` / `RoomArchivedError` / `WorkflowNotFoundError` / `AgentNotFoundError`）が発火 → ハンドラを経由することを確認 |
| 孤児要件なし | REQ-RM-HTTP-001〜007・MSG-RM-HTTP-001〜007・受入基準 #19〜31 の全件がテストマトリクスに紐付けられている（上表 §テストマトリクス で確認）|
