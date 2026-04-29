# 詳細設計書

> feature: `task` / sub-feature: `http-api`
> 関連 Issue: [#60 feat(task-http-api): Directive + Task lifecycle HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/60)
> 関連: [`basic-design.md`](basic-design.md) / [`../feature-spec.md`](../feature-spec.md)
> 凍結済み設計参照: [`docs/design/architecture.md`](../../../design/architecture.md) / [`docs/design/threat-model.md`](../../../design/threat-model.md)

## 確定事項一覧（Issue #60 設計凍結）

| 記号 | 論点 | 決定内容 |
|-----|------|---------|
| 確定A | masking 要否（`last_error` / `body_markdown` の HTTP レスポンス） | `TaskResponse.last_error` / `DeliverableResponse.body_markdown` に `@field_serializer` で `ApplicationMasking.mask()` 適用（defense-in-depth）。`@field_serializer` は GET / POST / PATCH **全レスポンスパス**で発火する（mode 制限なし）。DB は MaskedText TypeDecorator で既にマスキング済み（R1-12）。`ApplicationMasking.mask()` は冪等性あり（二重 masking なし）。GET /api/tasks/{task_id} で BLOCKED Task を取得する場合も `last_error` に field_serializer が適用され、DB バイパス経路（raw 値直接 INSERT）でも HTTP レスポンスに secret が露出しない |
| 確定B | `find_all_by_room` の追加（P-2）| `TaskRepository` Protocol に `find_all_by_room(room_id: RoomId) -> list[Task]` を追加。Room 不在時は空リストを返す（`RoomNotFoundError` は raise しない）|
| 確定C | `task_exceptions.py` 新規作成（P-1）| `TaskNotFoundError(task_id)` / `TaskStateConflictError(task_id, current_status, action)` を定義。実装どおり `Exception` を基底クラスとし、HTTP 層で明示的に 404 / 409 へマッピングする |
| 確定D | `TaskInvariantViolation` の HTTP ステータス分岐 | `kind in ('terminal_violation', 'state_transition_invalid')` → service 層で catch して `TaskStateConflictError` に変換 → 409。その他 kind → `TaskInvariantViolation` のまま伝播 → error_handlers.py が 422 に変換 |
| 確定E | `TaskService` のコンストラクタ | `TaskRepository` / `RoomRepository` / `AgentRepository` / `WorkflowStageResolver` / `ExternalReviewGateRepository` / `ExternalReviewReviewerResolver` / `AsyncSession` を注入する。`assign` は Agent が active かつ `Room.members` 内であることを検証し、`commit_deliverable` は `submitted_by` が active かつ Task 担当 Agent であること、現 Stage が EXTERNAL_REVIEW の場合だけ reviewer resolver を経由して Gate を生成することを検証する |
| 確定F | deliverables の HTTP レスポンス形式 | `TaskResponse.deliverables` は `dict[str, DeliverableResponse]`（`stage_id` の str 表現をキーとする）。`stage_id` は UUID の str 表現 |
| 確定G | GET /api/rooms/{room_id}/tasks の Room 不在時ふるまい | 空リストを返す（404 しない）。Room が archived でも同様。Task 一覧は現状の DB 状態のみに基づく |

## Pydantic スキーマ定義

### `TaskAssign`（リクエスト Body）

| フィールド | 型 | バリデーション | 備考 |
|----------|---|-------------|------|
| `agent_ids` | `list[UUID]` | `min_length=1` | 空リストは domain 層の `assign()` が拒否（min 1 件）|

### `DeliverableCreate`（リクエスト Body）

| フィールド | 型 | バリデーション | 備考 |
|----------|---|-------------|------|
| `body_markdown` | `str` | `min_length=1`, `max_length=100000` | Agent 成果物本文（Markdown）|
| `submitted_by` | `UUID` | 必須 | 成果物を commit した AgentId |
| `attachments` | `list[AttachmentCreate] \| None` | デフォルト `None` | 添付ファイルなし可 |

### `AttachmentCreate`（リクエスト Body）

| フィールド | 型 | バリデーション | 備考 |
|----------|---|-------------|------|
| `sha256` | `str` | 64 文字 hex | Attachment domain VO の不変条件で検証（`AttachmentInvariantViolation` → 422）|
| `filename` | `str` | `min_length=1` | パストラバーサル（`../`）/ 不正文字はdomain VO が拒否 |
| `mime_type` | `str` | `min_length=1` | 不正 MIME 型は domain VO が拒否 |
| `size_bytes` | `int` | `gt=0` | 1 バイト以上 |

### `TaskResponse`（レスポンス）

| フィールド | 型 | 備考 |
|----------|---|------|
| `id` | `str` | `TaskId.value` を str で変換 |
| `room_id` | `str` | `RoomId.value` を str で変換 |
| `directive_id` | `str` | `DirectiveId.value` を str で変換 |
| `current_stage_id` | `str` | `StageId.value` を str で変換 |
| `status` | `str` | `TaskStatus.value`（`PENDING` / `IN_PROGRESS` / `AWAITING_EXTERNAL_REVIEW` / `BLOCKED` / `DONE` / `CANCELLED`）|
| `assigned_agent_ids` | `list[str]` | `AgentId.value` の list（順序保持）|
| `last_error` | `str \| None` | `@field_serializer('last_error')` で `ApplicationMasking.mask(value)` 適用。BLOCKED 以外では None |
| `deliverables` | `dict[str, DeliverableResponse]` | `stage_id（str）→ DeliverableResponse` の dict |
| `created_at` | `str` | ISO 8601 UTC（`datetime.isoformat() + 'Z'`）|
| `updated_at` | `str` | ISO 8601 UTC |

### `DeliverableResponse`（レスポンス）

| フィールド | 型 | 備考 |
|----------|---|------|
| `stage_id` | `str` | `StageId.value` を str で変換 |
| `body_markdown` | `str` | `@field_serializer('body_markdown')` で `ApplicationMasking.mask(value)` 適用（確定A）|
| `submitted_by` | `str` | `AgentId.value` を str で変換 |
| `submitted_at` | `str` | ISO 8601 UTC |
| `attachments` | `list[AttachmentResponse]` | 空リスト可 |

### `AttachmentResponse`（レスポンス）

| フィールド | 型 | 備考 |
|----------|---|------|
| `sha256` | `str` | 64 文字 hex |
| `filename` | `str` | ファイル名（パストラバーサルは永続化前に domain VO が拒否済み）|
| `mime_type` | `str` | MIME type |
| `size_bytes` | `int` | ファイルサイズ（バイト）|

### `TaskListResponse`（レスポンス）

| フィールド | 型 | 備考 |
|----------|---|------|
| `items` | `list[TaskResponse]` | 0 件以上 |
| `total` | `int` | `len(items)` と等価（ページネーションは本 PR のスコープ外）|

## MSG 確定文言表

| ID | 条件 | message | detail | HTTP |
|---|------|---------|--------|------|
| MSG-TS-HTTP-001 | `TaskNotFoundError` | `"Task not found."` | `{"task_id": "<uuid>"}` | 404 |
| MSG-TS-HTTP-002 | `TaskStateConflictError` | domain 層の `str(exc)` から **`[FAIL]` プレフィックスと `\nNext:.*` を除去した本文のみ**（`re.sub(r"^\[FAIL\]\s*", "", str(exc)).split("\nNext:")[0].strip()`）— empire / room / workflow / agent と同一前処理パターン | `{"task_id": "<uuid>", "current_status": "<status>", "requested_action": "<action>"}` | 409 |
| MSG-TS-HTTP-003 | `TaskInvariantViolation`（terminal / 遷移不可 以外）| domain 層の `str(exc)` から **`[FAIL]` プレフィックスと `\nNext:.*` を除去した本文のみ**（同一前処理パターン）| `{"kind": exc.kind}` | 422 |
| MSG-TS-HTTP-004 | `TaskAuthorizationError` | `"Agent is not a member of the Task room."` または `"Agent is not assigned to this Task."` | `{"task_id": "<uuid>", "requested_action": "<action>"}` | 403 |

**前処理ルール（empire / room / workflow / agent と同一パターン）**:
1. `[FAIL] ` プレフィックスを除去: `re.sub(r"^\[FAIL\]\s*", "", str(exc))`
2. `\nNext:` 以降を除去: `.split("\nNext:")[0].strip()`

これにより domain 内部の AI エージェント向けフォーマット（業務ルール R1-9）が HTTP クライアントに露出しない。`task_state_conflict_handler` / `task_invariant_violation_handler` はこの前処理を適用したうえで `ErrorResponse.message` を構築する。

## 例外マッピング詳細

```
TaskService メソッド内の例外発生元 → HTTP ステータス対応表

TaskNotFoundError           → 404 not_found      （task_exceptions.py で定義）
TaskStateConflictError      → 409 conflict        （task_exceptions.py で定義、TaskInvariantViolation を wrap）
TaskInvariantViolation      → 422 validation_error（種別に依らず上記 2 種類以外は全て 422）
AttachmentInvariantViolation → 422 validation_error（domain VO の不変条件違反）
TaskAuthorizationError       → 403 forbidden       （Room.members 外 assign / 未担当 submitted_by）
ValidationError (Pydantic)  → 422 validation_error（既存 http-api-foundation ハンドラ再利用）
```

### TaskStateConflictError のラップ条件

`TaskService` 内の各メソッドで `TaskInvariantViolation` を catch し、以下の条件で `TaskStateConflictError` に変換する:

| `exc.kind` | 変換先 |
|-----------|------|
| `terminal_violation` | `TaskStateConflictError` raise → 409 |
| `state_transition_invalid` | `TaskStateConflictError` raise → 409 |
| その他すべて | そのまま伝播 → 422 |

## `task_exceptions.py` 定義仕様（P-1）

`backend/src/bakufu/application/exceptions/task_exceptions.py` を新規作成する。

| クラス名 | 基底クラス | コンストラクタ引数 | 意味 |
|--------|----------|----------------|------|
| `TaskNotFoundError` | `Exception` | `task_id: TaskId \| str` | 指定 ID の Task が存在しない（404 マッピング）|
| `TaskStateConflictError` | `Exception` | `task_id: TaskId \| str`, `current_status: TaskStatus \| str`, `action: str`, `message: str \| None = None` | terminal 状態 / state machine 上の不正遷移（409 マッピング）|

## `TaskRepository` Protocol 拡張仕様（P-2）

`backend/src/bakufu/application/ports/task_repository.py` の `TaskRepository` Protocol に以下を追加:

| メソッド | シグネチャ | 意味 |
|--------|----------|------|
| `find_all_by_room` | `async def find_all_by_room(self, room_id: RoomId) -> list[Task]` | 指定 Room に紐付く Task 全件を返す。Room 不在時は空リスト（raise しない）|

既存 8 メソッド（`find_by_id` / `count` / `save` / `count_by_status` / `count_by_room` / `find_blocked` + 2）への変更なし。

## DI ファクトリ

`backend/src/bakufu/interfaces/http/dependencies.py` に以下を追記する:

| 関数名 | シグネチャ概要 | 責務 |
|-------|-------------|------|
| `get_task_service` | `(session=Depends(get_session)) -> TaskService` | `TaskRepository`（SQLite 実装）/ `RoomRepository`（SQLite 実装）/ `AgentRepository`（SQLite 実装）/ `WorkflowStageResolver`（SQLite 実装）/ `ExternalReviewGateRepository`（SQLite 実装）/ `ExternalReviewReviewerResolver`（HTTP 境界実装）/ `session` を注入して `TaskService` を生成する |

## `TaskService` メソッド実装仕様

| メソッド | 実装責務 |
|--------|--------|
| `find_by_id(task_id)` | `task_repo.find_by_id(TaskId(task_id))` → None → `TaskNotFoundError` raise。Task を返す |
| `find_all_by_room(room_id)` | `task_repo.find_all_by_room(RoomId(room_id))` → `list[Task]`。Room 不在は空リスト |
| `assign(task_id, agent_ids)` | `find_by_id` → `RoomRepository.find_by_id(task.room_id)` → 各 `AgentRepository.find_by_id(agent_id)` → active かつ `Room.members` 内であることを確認 → `task.assign([AgentId(a) for a in agent_ids])` → `TaskInvariantViolation` を kind 別に処理 → `session.begin()` 内で `task_repo.save(updated_task)` |
| `cancel(task_id)` | `find_by_id` → `task.cancel()` → `TaskInvariantViolation` を処理 → `task_repo.save` |
| `unblock_retry(task_id)` | `find_by_id` → `task.unblock_retry()` → `TaskInvariantViolation` を処理 → `task_repo.save` |
| `commit_deliverable(task_id, stage_id, deliverable_create)` | `find_by_id` → `AgentRepository.find_by_id(submitted_by)` → active かつ `submitted_by ∈ task.assigned_agent_ids` であることを確認 → `Deliverable(...)` 構築 → `task.commit_deliverable(stage_id, deliverable, submitted_by)` → `task_repo.save` |

## セキュリティ補足

### `last_error` / `body_markdown` の masking（確定A 詳細）

- DB 層（永続化前）: `MaskedText` TypeDecorator が `tasks.last_error` / `deliverables.body_markdown` への書き込み時に `MaskingGateway.mask()` を適用（repository sub-feature で確定済み、業務ルール R1-12）
- HTTP 層（レスポンス時）: `TaskResponse.last_error` / `DeliverableResponse.body_markdown` に `@field_serializer` を定義し `ApplicationMasking.mask(value)` を適用
- **全レスポンスパスで発火（mode 制限なし）**: `@field_serializer` は GET / POST / PATCH 全エンドポイントのレスポンス構築時に無条件で呼び出される。GET /api/tasks/{task_id} で BLOCKED Task を取得する場合も `last_error` に適用される
- `ApplicationMasking.mask()` の冪等性: `<REDACTED:DISCORD_WEBHOOK>` / `<REDACTED:ANTHROPIC_KEY>` 等のパターンは二重マスキングされない
- `last_error=None` の場合: `@field_serializer` は None をそのまま返す（masking しない）
- DB バイパス保証: DB への raw token 直接 INSERT バイパスが発生した場合でも、HTTP レスポンスでは field_serializer が独立して secret を除去する（R1-12 永続化 masking + HTTP レスポンス masking の二重防御）

### `TaskInvariantViolation` の webhook auto-mask

domain 層の `TaskInvariantViolation.__init__()` が `super().__init__` 前に `mask_discord_webhook(message)` + `mask_discord_webhook_in(detail)` を強制適用（業務ルール R1-8）。HTTP レスポンスの `detail` にも masked 値が通過する。

## カバレッジ基準（本 sub-feature の IT / UT）

| 観点 | 目標 |
|---|---|
| `TaskService` 全メソッド | UT: 正常系 + TaskNotFoundError / TaskStateConflictError / TaskInvariantViolation（各 kind）の各異常系 |
| `TaskRouter` 全エンドポイント | IT: TestClient 経由で 200 / 404 / 409 / 422 の各ステータスを検証 |
| masking | IT: `TaskResponse.last_error` / `DeliverableResponse.body_markdown` に secret を含む値を渡した場合、レスポンス JSON の各フィールドが `<REDACTED:*>` を含むことを確認 |
| `task_exceptions.py` | UT: `TaskNotFoundError` / `TaskStateConflictError` の `str(exc)` 形式確認 |
| 実装カバレッジ | 90% 以上（`task_service.py` + `tasks.py` router + `task.py` schemas + `task_exceptions.py`）|

詳細テストケースは [`test-design.md`](test-design.md) で凍結する。
