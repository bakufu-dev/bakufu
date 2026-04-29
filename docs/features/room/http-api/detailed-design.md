# 詳細設計書

> feature: `room` / sub-feature: `http-api`
> 関連 Issue: [#57 feat(room-http-api): Room + Agent assignment HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/57)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../../http-api-foundation/http-api/detailed-design.md`](../../http-api-foundation/http-api/detailed-design.md)

## 本書の役割

**実装者が本書だけを読んで迷わず実装できる粒度** で構造契約を凍結する。`basic-design.md §モジュール契約` の各 REQ-RM-HTTP-NNN を、Pydantic スキーマ定義・例外マッピング・確定文言として展開する。

**書くこと**:
- Pydantic スキーマ（フィールド名・型・バリデーション制約）
- 例外マッピングテーブル（domain / application 例外 → HTTP ステータス + ErrorCode + MSG ID）
- MSG 確定文言（エラーレスポンスの `message` フィールド文字列）
- `dependencies.py` 追記内容（`get_room_repository` / `get_room_service`）
- `error_handlers.py` 追記内容（room 専用例外ハンドラ群）
- `RoomService` メソッド一覧と raises 定義

**書かないこと**:
- 疑似コード / サンプル実装 → 設計書とソースコードの二重管理になる
- テストケース → `test-design.md`

## 確定 A: Pydantic スキーマ定義（`interfaces/http/schemas/room.py`）

http-api-foundation 確定A の `ErrorResponse` / `ErrorDetail` と同一ファイル分割方針に従い、room 専用スキーマを `schemas/room.py` に配置する。`model_config = ConfigDict(extra="forbid")` を全スキーマに適用する（余分なフィールドを拒否、Q-3 物理保証）。

### リクエストスキーマ

| スキーマ名 | フィールド | 型 | 制約 | 用途 |
|---|---|---|---|---|
| `RoomCreate` | `name` | `str` | `min_length=1`, `max_length=80`（業務ルール R1-1）| POST /api/empires/{empire_id}/rooms Body |
| | `description` | `str` | `max_length=500`（業務ルール R1-2）, default `""` | 同上 |
| | `workflow_id` | `UUID` | 必須 | 同上 |
| | `prompt_kit_prefix_markdown` | `str` | `max_length=10000`, default `""` | 同上 |
| `RoomUpdate` | `name` | `str \| None` | `min_length=1`, `max_length=80`（適用時のみ）| PATCH /api/rooms/{room_id} Body |
| | `description` | `str \| None` | `max_length=500`（適用時のみ）| 同上 |
| | `prompt_kit_prefix_markdown` | `str \| None` | `max_length=10000`（適用時のみ）| 同上 |
| `AgentAssignRequest` | `agent_id` | `UUID` | 必須 | POST /api/rooms/{room_id}/agents Body |
| | `role` | `str` | `min_length=1`, `max_length=50` | 同上 |

`RoomUpdate` の全フィールドが `None` の場合は変更なし（部分更新 PATCH パターン）。

### レスポンスサブスキーマ

| スキーマ名 | フィールド | 型 | 備考 |
|---|---|---|---|
| `MemberResponse` | `agent_id` | `str` | UUID 文字列 |
| | `role` | `str` | Role enum の値 |
| | `joined_at` | `str` | ISO 8601 UTC 文字列（`datetime.isoformat()`）|

### レスポンススキーマ

| スキーマ名 | フィールド | 型 | 備考 |
|---|---|---|---|
| `RoomResponse` | `id` | `str` | Room.id（UUID 文字列）|
| | `name` | `str` | Room.name |
| | `description` | `str` | Room.description |
| | `workflow_id` | `str` | Room.workflow_id（UUID 文字列）|
| | `members` | `list[MemberResponse]` | Room.members のマップ |
| | `prompt_kit_prefix_markdown` | `str` | Room.prompt_kit.prefix_markdown（masked 文字列のまま返却、不可逆性）|
| | `archived` | `bool` | Room.archived |
| `RoomListResponse` | `items` | `list[RoomResponse]` | 0 件以上 |
| | `total` | `int` | `len(items)` |

`RoomResponse` は `model_config = ConfigDict(from_attributes=True)` を適用。domain `Room` からの変換時は `str(room.id)` / `str(room.workflow_id)` で UUID → 文字列変換する点に注意（`RoomId` は UUID wrapper のため）。

## 確定 B: 例外マッピングテーブル

room http-api に関わるすべての例外と HTTP レスポンスの対応を凍結する。Router 内では `try/except` を書かない（http-api-foundation architecture 規律）。

| 例外クラス | 発生箇所 | HTTP ステータス | ErrorCode | MSG ID |
|---|---|---|---|---|
| `RoomNotFoundError` | `RoomService.find_by_id`（None 時）/ archive（None 時）/ unassign_agent（Room 不在時）| 404 | `not_found` | MSG-RM-HTTP-002 |
| `RoomNameAlreadyExistsError` | `RoomService.create`（name 重複時）| 409 | `conflict` | MSG-RM-HTTP-001 |
| `RoomArchivedError` | `RoomService.update` / `assign_agent` / `unassign_agent`（archived=True 時）| 409 | `conflict` | MSG-RM-HTTP-003 |
| `WorkflowNotFoundError` | `RoomService.create`（Workflow 不在時）| 404 | `not_found` | MSG-RM-HTTP-006 |
| `AgentNotFoundError` | `RoomService.assign_agent`（Agent 不在時）| 404 | `not_found` | MSG-RM-HTTP-004 |
| `EmpireNotFoundError` | `RoomService.create` / `find_all_by_empire`（Empire 不在時）| 404 | `not_found` | empire MSG-EM-HTTP-002（既存ハンドラが処理）|
| `RoomInvariantViolation(kind='member_not_found')` | `room.remove_member`（不在 membership 時）| 404 | `not_found` | MSG-RM-HTTP-005 |
| `RoomInvariantViolation`（その他 kind）| domain Room（name_range / description_too_long / member_duplicate / capacity_exceeded / room_archived）| 422 | `validation_error` | MSG-RM-HTTP-007（str(exc) を前処理して使用）|
| `RequestValidationError` | FastAPI Pydantic デシリアライズ失敗 | 422 | `validation_error` | http-api-foundation MSG-HAF-002（既存ハンドラが処理）|
| `HTTPException` | CSRF ミドルウェア（`Origin` 不一致）| 403 | `forbidden` | http-api-foundation MSG-HAF-004（既存ハンドラが処理）|
| `Exception`（その他）| どこでも | 500 | `internal_error` | http-api-foundation MSG-HAF-003（既存ハンドラが処理）|

## 確定 C: 例外ハンドラ実装（`error_handlers.py` 追記）

http-api-foundation の `error_handlers.py` に以下のハンドラ関数を追記し、`app.py` の `_register_exception_handlers` で登録する。

| ハンドラ関数名 | 処理例外 | 返却する ErrorResponse |
|---|---|---|
| `room_not_found_handler` | `RoomNotFoundError` | `ErrorResponse(code="not_found", message=MSG-RM-HTTP-002)` + HTTP 404 |
| `room_name_already_exists_handler` | `RoomNameAlreadyExistsError` | `ErrorResponse(code="conflict", message=MSG-RM-HTTP-001)` + HTTP 409 |
| `room_archived_handler` | `RoomArchivedError` | `ErrorResponse(code="conflict", message=MSG-RM-HTTP-003)` + HTTP 409 |
| `workflow_not_found_handler` | `WorkflowNotFoundError` | `ErrorResponse(code="not_found", message=MSG-RM-HTTP-006)` + HTTP 404 |
| `agent_not_found_handler` | `AgentNotFoundError` | `ErrorResponse(code="not_found", message=MSG-RM-HTTP-004)` + HTTP 404 |
| `room_invariant_violation_handler` | `RoomInvariantViolation` | `kind='member_not_found'` → HTTP 404 (MSG-RM-HTTP-005) / その他 → HTTP 422 (MSG-RM-HTTP-007 前処理済み本文)|

登録順は既存の `HTTPException` / `RequestValidationError` / `Exception` ハンドラより**前**（empire ハンドラ群の直後）に登録する。

**`room_invariant_violation_handler` の処理ルール（凍結）**:

1. `exc.kind == 'member_not_found'` の場合 → HTTP 404, `ErrorResponse(code="not_found", message=MSG-RM-HTTP-005)`
2. それ以外の場合 → HTTP 422, `ErrorResponse(code="validation_error", message=<前処理済みメッセージ>)`

前処理ルール（empire http-api §確定C と同一パターン）:
1. `[FAIL] ` プレフィックスを除去: `re.sub(r"^\[FAIL\]\s*", "", str(exc))`
2. `\nNext:` 以降を除去: `.split("\nNext:")[0].strip()`

これにより domain 内部の AI エージェント向けフォーマットが HTTP クライアントに露出しない。

## 確定 D: `dependencies.py` 追記（DI ファクトリ）

http-api-foundation の `dependencies.py` に以下を追記する。

| 関数名 | 型シグネチャ | 依存 |
|---|---|---|
| `get_room_repository` | `(session: AsyncSession = Depends(get_session)) → RoomRepository` | `get_session()` |
| `get_room_service` | `(room_repo: RoomRepository = Depends(get_room_repository), empire_repo: EmpireRepository = Depends(get_empire_repository), workflow_repo: WorkflowRepository = Depends(get_workflow_repository), agent_repo: AgentRepository = Depends(get_agent_repository)) → RoomService` | 複数 repo を受け取り `RoomService` を構築 |

`get_room_service` は `Annotated[RoomService, Depends(get_room_service)]` 型エイリアスを定義し、各エンドポイントで簡潔に使えるようにする。

`get_workflow_repository` / `get_agent_repository` は workflow / agent http-api PR でそれぞれ追加予定。本 PR 時点で未定義の場合は、本 PR で先行して追記する。

## 確定 E: エンドポイント定義（`routers/rooms.py`）

| メソッド | パス | パスパラメータ | クエリパラメータ | リクエスト Body | レスポンス | ステータスコード |
|---|---|---|---|---|---|---|
| POST | `/api/empires/{empire_id}/rooms` | `empire_id: UUID` | なし | `RoomCreate` | `RoomResponse` | 201 |
| GET | `/api/empires/{empire_id}/rooms` | `empire_id: UUID` | なし | なし | `RoomListResponse` | 200 |
| GET | `/api/rooms/{room_id}` | `room_id: UUID` | なし | なし | `RoomResponse` | 200 |
| PATCH | `/api/rooms/{room_id}` | `room_id: UUID` | なし | `RoomUpdate` | `RoomResponse` | 200 |
| DELETE | `/api/rooms/{room_id}` | `room_id: UUID` | なし | なし | なし（No Content）| 204 |
| POST | `/api/rooms/{room_id}/agents` | `room_id: UUID` | なし | `AgentAssignRequest` | `RoomResponse` | 201 |
| DELETE | `/api/rooms/{room_id}/agents/{agent_id}` | `room_id: UUID`, `agent_id: UUID` | `role: str`（必須）| なし | なし（No Content）| 204 |

パスパラメータはすべて `UUID` 型で宣言し、FastAPI の path validation で不正形式を 422 に変換する（業務ルール R1-10、empire http-api BUG-EM-SEC-001 解消方針に準拠）。

Router は 2 つの `prefix` で構成する:
- `empire_rooms_router`: `prefix="/api/empires"`, `tags=["room"]`（empire_id スコープのエンドポイント）
- `rooms_router`: `prefix="/api/rooms"`, `tags=["room"]`（room_id スコープのエンドポイント）

`http-api-foundation` の `app.py` に両 router を `app.include_router(...)` で追記する。

## 確定 F: application 例外定義（`application/exceptions/room_exceptions.py`）

| 例外クラス名 | 基底クラス | `__init__` 引数 | 用途 |
|---|---|---|---|
| `RoomNotFoundError` | `Exception` | `room_id: str` | find_by_id / archive / unassign_agent で Room 不在 |
| `RoomNameAlreadyExistsError` | `Exception` | `name: str, empire_id: str` | create で同 Empire 内 name 重複（R1-8）|
| `RoomArchivedError` | `Exception` | `room_id: str` | update / assign_agent / unassign_agent で archived=True（R1-5）|
| `WorkflowNotFoundError` | `Exception` | `workflow_id: str` | create で Workflow 不在。workflow_exceptions.py で定義済みの場合はそこから import |
| `AgentNotFoundError` | `Exception` | `agent_id: str` | assign_agent で Agent 不在。agent_exceptions.py で定義済みの場合はそこから import |

`WorkflowNotFoundError` / `AgentNotFoundError` は workflow / agent http-api PR（将来 Issue）で既に定義される場合、その定義を import して使う。本 PR 時点で未定義の場合は `room_exceptions.py` に暫定定義し、将来 PR で統合先に移動する（開放論点 Q-OPEN-1 参照）。

これらは application 層の例外であり、domain 例外（`RoomInvariantViolation`）とは独立する。

## 確定 G: `RoomService` メソッド一覧

http-api-foundation 確定F で骨格が確定済み（`RoomService.__init__(repo: RoomRepository)`）。本 PR で以下のシグネチャに変更し、メソッドを全て肉付けする。

コンストラクタ変更: `__init__(self, room_repo, empire_repo, workflow_repo, agent_repo)` に拡張（複数 Repo を受け取る形に変更）。

| メソッド名 | 引数 | 戻り値 | raises |
|---|---|---|---|
| `create` | `empire_id: RoomId, name: str, description: str, workflow_id: WorkflowId, prompt_kit_prefix_markdown: str` | `Room` | `EmpireNotFoundError` / `WorkflowNotFoundError` / `RoomNameAlreadyExistsError` / `RoomInvariantViolation` |
| `find_all_by_empire` | `empire_id: RoomId` | `list[Room]` | `EmpireNotFoundError` |
| `find_by_id` | `room_id: RoomId` | `Room` | `RoomNotFoundError` |
| `update` | `room_id: RoomId, name: str \| None, description: str \| None, prompt_kit_prefix_markdown: str \| None` | `Room` | `RoomNotFoundError` / `RoomArchivedError` / `RoomInvariantViolation` |
| `archive` | `room_id: RoomId` | `None` | `RoomNotFoundError` |
| `assign_agent` | `room_id: RoomId, agent_id: AgentId, role: str` | `Room` | `RoomNotFoundError` / `RoomArchivedError` / `AgentNotFoundError` / `RoomInvariantViolation` |
| `unassign_agent` | `room_id: RoomId, agent_id: AgentId, role: str` | `None` | `RoomNotFoundError` / `RoomArchivedError` / `RoomInvariantViolation(kind='member_not_found')` |

`create` / `update` / `archive` / `assign_agent` / `unassign_agent` は `async with session.begin()` を service 内で開く（UoW 責務は service 層が持つ）。

**`update` の部分更新ルール（凍結）**: 引数が `None` のフィールドは変更しない。既存 `Room` の値をそのまま引き継いで `Room(...)` 再構築する。全フィールドが `None` の場合は変更なし（save せず既存 Room を返す）。

**`unassign_agent` の membership 不在処理**: `room.remove_member(agent_id, role)` が `RoomInvariantViolation(kind='member_not_found')` を raise した場合、`RoomService.unassign_agent` はそのまま上位に伝播させる（service 層での catch なし）。`room_invariant_violation_handler` が `kind` で分岐して 404 を返す（確定C 参照）。

## 確定 H: `RoomRepository` Protocol 拡張（`application/ports/room_repository.py`）

| メソッド名 | 型シグネチャ | 用途 |
|---|---|---|
| `find_all_by_empire` | `async def find_all_by_empire(empire_id: RoomId) → list[Room]` | Empire スコープの Room 全件取得（UC-RM-009）|

本 PR で既存 Protocol に追記する。`SqliteRoomRepository.find_all_by_empire` は `SELECT * FROM rooms WHERE empire_id = :empire_id ORDER BY name ASC` + `find_by_id` の内部実装に委譲（詳細は実装担当者判断）。

## MSG 確定文言表

| MSG ID | `code` | `message`（確定文言）| HTTP ステータス |
|---|---|---|---|
| MSG-RM-HTTP-001 | `conflict` | `"Room name already exists in this empire."` | 409 |
| MSG-RM-HTTP-002 | `not_found` | `"Room not found."` | 404 |
| MSG-RM-HTTP-003 | `conflict` | `"Room is archived and cannot be modified."` | 409 |
| MSG-RM-HTTP-004 | `not_found` | `"Agent not found."` | 404 |
| MSG-RM-HTTP-005 | `not_found` | `"Agent membership not found in this room."` | 404 |
| MSG-RM-HTTP-006 | `not_found` | `"Workflow not found."` | 404 |
| MSG-RM-HTTP-007 | `validation_error` | `RoomInvariantViolation.message` から `[FAIL]` プレフィックスと `\nNext:.*` を除去した本文のみ（例: `"Room name は 1〜80 文字でなければなりません。"`）| 422 |

MSG-RM-HTTP-007 は domain 層の `RoomInvariantViolation.message` を **前処理したうえで** HTTP レスポンスに使用する（前処理ルールは §確定C 末尾に凍結）。

## 参照設計との整合確認

| http-api-foundation 確定事項 | room http-api での適用 |
|---|---|
| 確定A: ErrorCode 定数（`not_found` / `validation_error` / `internal_error` / `forbidden`）| `conflict` を empire と共通で使用（`error_handlers.py` の `ErrorCode` 定数は empire PR で追記済み）|
| 確定B: `app.state.session_factory` / `engine` | `get_session()` DI 経由で `AsyncSession` を取得（変更なし）|
| 確定D: CSRF Origin 検証（MVP: Origin なし通過 / 不一致 403）| POST / PATCH / DELETE は CSRF ミドルウェアが適用される（追加設定不要）|
| 確定E: `get_session()` DI | `get_room_repository(session=Depends(get_session))` で利用（変更なし）|
| 確定F: Service `__init__(repo)` 骨格 | `RoomService.__init__` の引数を 4 repo に拡張（http-api-foundation の単一 repo 骨格から変更）|

## 開放論点

| # | 論点 | 起票先 |
|---|---|---|
| Q-OPEN-1 | `WorkflowNotFoundError` / `AgentNotFoundError` の定義先（本 PR で暫定定義 → workflow / agent http-api PR で統合）| 将来 Issue（workflow-http-api / agent-http-api）|
| Q-OPEN-2 | `find_all_by_empire` の返却順（name 昇順 / 作成日降順 / ID 順）。本 PR では name ASC を暫定とし、将来の UI 要件で変更可 | 将来 Issue（room-ui）|
| Q-OPEN-3 | アーカイブ済み Room への `DELETE /api/rooms/{room_id}` の冪等性。本 PR では `archive()` が冪等（domain 設計）なので 204 を返す（実質 no-op）。ユーザーへの告知が必要か | 将来 Issue（UX review）|
