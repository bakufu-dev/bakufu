# 詳細設計書

> feature: `workflow` / sub-feature: `http-api`
> 関連 Issue: [#58 feat(workflow-http-api): Workflow + Stage HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/58)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../../http-api-foundation/http-api/detailed-design.md`](../../http-api-foundation/http-api/detailed-design.md)

## 本書の役割

**実装者が本書だけを読んで迷わず実装できる粒度** で構造契約を凍結する。`basic-design.md §モジュール契約` の各 REQ-WF-HTTP-NNN を、Pydantic スキーマ定義・例外マッピング・確定文言として展開する。

**書くこと**:
- Pydantic スキーマ（フィールド名・型・バリデーション制約）
- 例外マッピングテーブル（domain / application 例外 → HTTP ステータス + ErrorCode + MSG ID）
- MSG 確定文言（エラーレスポンスの `message` フィールド文字列）
- `dependencies.py` 追記内容（`get_workflow_service` 拡張）
- `error_handlers.py` 追記内容（workflow 専用例外ハンドラ群）
- `WorkflowService` メソッド一覧と raises 定義
- プリセット定義構造

**書かないこと**:
- 疑似コード / サンプル実装 → 設計書とソースコードの二重管理になる
- テストケース → `test-design.md`

## 確定 A: Pydantic スキーマ定義（`interfaces/http/schemas/workflow.py`）

`model_config = ConfigDict(extra="forbid")` を全スキーマに適用する（余分なフィールドを拒否、Q-3 物理保証）。

### リクエストスキーマ

#### `StageCreate`（ネスト用）

| フィールド | 型 | 制約 | 備考 |
|---|---|---|---|
| `id` | `UUID` | 必須 | Stage 識別子。クライアントが生成（UUID v4）|
| `name` | `str` | `min_length=1`, `max_length=80` | Stage 名（業務ルール R1-1 準拠）|
| `kind` | `str` | 有効値: `"WORK"` / `"EXTERNAL_REVIEW"` / `"INTERNAL_REVIEW"` | `StageKind` enum 値（StrEnum）|
| `required_role` | `list[str]` | `min_length=1`（要素数）、各要素は有効 `Role` StrEnum 値 | 空リスト → 422（業務ルール R1-9）|
| `completion_policy` | `dict \| None` | 任意 | `CompletionPolicy` の JSON 表現。None は default を適用 |
| `notify_channels` | `list[str]` | 各要素は Discord webhook URL 形式（業務ルール R1-10）。`EXTERNAL_REVIEW` 時は 1 件以上必須（R1-8）| domain `NotifyChannel` バリデーションに委譲 |
| `required_gate_roles` | `list[str]` | 各要素は slug 形式（1〜40 文字小文字英数字ハイフン）。空リスト許容（業務ルール R1-13）| domain `Stage` バリデーションに委譲 |

#### `TransitionCreate`（ネスト用）

| フィールド | 型 | 制約 | 備考 |
|---|---|---|---|
| `id` | `UUID` | 必須 | Transition 識別子 |
| `from_stage_id` | `UUID` | 必須 | 起点 Stage ID |
| `to_stage_id` | `UUID` | 必須 | 終点 Stage ID |
| `condition` | `str` | 有効値: `"SUCCESS"` / `"FAILURE"` / `"APPROVAL"` / `"REJECTION"` / `"ALWAYS"` | `TransitionCondition` enum 値 |

#### `WorkflowCreate`（POST /api/rooms/{room_id}/workflows Body）

| フィールド | 型 | 制約 | 備考 |
|---|---|---|---|
| `name` | `str \| None` | `min_length=1`, `max_length=80`（業務ルール R1-1）。`preset_name` 指定時は省略可 | プリセット使用時は省略 → プリセット定義の name を使用 |
| `stages` | `list[StageCreate] \| None` | `preset_name` が None の場合は必須 | JSON 定義モード |
| `transitions` | `list[TransitionCreate] \| None` | `preset_name` が None の場合は必須 | JSON 定義モード |
| `entry_stage_id` | `UUID \| None` | `preset_name` が None の場合は必須 | JSON 定義モード |
| `preset_name` | `str \| None` | None または有効プリセット名（`"v-model"` / `"agile"` 等）| プリセットモード |

**排他バリデーション（model_validator）**:
- `preset_name` が設定されている場合: `stages` / `transitions` / `entry_stage_id` が全て None でなければ 422
- `preset_name` が None の場合: `stages` / `transitions` / `entry_stage_id` が全て設定されていなければ 422

#### `WorkflowUpdate`（PATCH /api/workflows/{id} Body）

| フィールド | 型 | 制約 | 備考 |
|---|---|---|---|
| `name` | `str \| None` | `min_length=1`, `max_length=80`（適用時のみ）| None は変更なし |
| `stages` | `list[StageCreate] \| None` | None は変更なし。設定時は `transitions` / `entry_stage_id` も同時設定必須 | 部分置換禁止 — Stage を変更するなら Transition / entry も同時更新 |
| `transitions` | `list[TransitionCreate] \| None` | None は変更なし | 同上 |
| `entry_stage_id` | `UUID \| None` | None は変更なし | 同上 |

**整合バリデーション（model_validator）**: `stages` / `transitions` / `entry_stage_id` は全て同時に設定するか、全て None でなければならない（DAG の部分更新は不整合状態を生む）。

### レスポンスサブスキーマ

#### `StageResponse`

| フィールド | 型 | 備考 |
|---|---|---|
| `id` | `str` | UUID 文字列 |
| `name` | `str` | Stage.name |
| `kind` | `str` | StageKind StrEnum 値（例: `"WORK"`）|
| `required_role` | `list[str]` | Role StrEnum 値のリスト |
| `completion_policy` | `dict \| None` | CompletionPolicy の JSON 表現。None は default を意味する |
| `notify_channels` | `list[str]` | DB から復元した masked 文字列（`<REDACTED:DISCORD_WEBHOOK>` 含む）のまま返却（不可逆性）|
| `required_gate_roles` | `list[str]` | slug 文字列のリスト |

#### `TransitionResponse`

| フィールド | 型 | 備考 |
|---|---|---|
| `id` | `str` | UUID 文字列 |
| `from_stage_id` | `str` | UUID 文字列 |
| `to_stage_id` | `str` | UUID 文字列 |
| `condition` | `str` | TransitionCondition StrEnum 値 |

### レスポンススキーマ

#### `WorkflowResponse`

| フィールド | 型 | 備考 |
|---|---|---|
| `id` | `str` | WorkflowId（UUID 文字列）|
| `name` | `str` | Workflow.name |
| `stages` | `list[StageResponse]` | Workflow.stages のマップ |
| `transitions` | `list[TransitionResponse]` | Workflow.transitions のマップ |
| `entry_stage_id` | `str` | UUID 文字列 |
| `archived` | `bool` | Workflow.archived |

`model_config = ConfigDict(from_attributes=True)` を適用。domain `Workflow` からの変換時は `str(workflow.id)` / `str(workflow.entry_stage_id)` で UUID → 文字列変換。

#### `WorkflowListResponse`

| フィールド | 型 | 備考 |
|---|---|---|
| `items` | `list[WorkflowResponse]` | 0 件以上 |
| `total` | `int` | `len(items)` |

#### `StageListResponse`

| フィールド | 型 | 備考 |
|---|---|---|
| `stages` | `list[StageResponse]` | Workflow.stages |
| `transitions` | `list[TransitionResponse]` | Workflow.transitions |
| `entry_stage_id` | `str` | UUID 文字列 |

#### `WorkflowPresetResponse`

| フィールド | 型 | 備考 |
|---|---|---|
| `preset_name` | `str` | プリセット識別キー（例: `"v-model"`, `"agile"`）|
| `display_name` | `str` | 表示名（例: `"Vモデル開発フロー"`）|
| `description` | `str` | プリセットの説明 |
| `stage_count` | `int` | Stage 件数 |
| `transition_count` | `int` | Transition 件数 |

#### `WorkflowPresetListResponse`

| フィールド | 型 | 備考 |
|---|---|---|
| `items` | `list[WorkflowPresetResponse]` | 1 件以上（static データ）|
| `total` | `int` | `len(items)` |

## 確定 B: 例外マッピングテーブル

workflow http-api に関わるすべての例外と HTTP レスポンスの対応を凍結する。Router 内では `try/except` を書かない（http-api-foundation architecture 規律）。

| 例外クラス | 発生箇所 | HTTP ステータス | ErrorCode | MSG ID |
|---|---|---|---|---|
| `WorkflowNotFoundError` | `WorkflowService.find_by_id` / `archive` / `update`（None 時）| 404 | `not_found` | MSG-WF-HTTP-001 |
| `WorkflowArchivedError` | `WorkflowService.update`（archived=True 時）| 409 | `conflict` | MSG-WF-HTTP-002 |
| `WorkflowArchivedError`（create_for_room でアーカイブ済み Workflow 割り当て）| `WorkflowService.create_for_room` | 409 | `conflict` | MSG-WF-HTTP-003 |
| `WorkflowPresetNotFoundError` | `WorkflowService.create_for_room`（未知 preset_name）| 404 | `not_found` | MSG-WF-HTTP-004 |
| `WorkflowInvariantViolation` | domain Workflow 構築 / update（DAG / 容量 / SSRF 等）| 422 | `validation_error` | MSG-WF-HTTP-005（前処理済み本文）|
| `RoomNotFoundError` | `WorkflowService.create_for_room` / `find_by_room`（Room 不在）| 404 | `not_found` | room MSG-RM-HTTP-002（room 既存ハンドラが処理）|
| `RoomArchivedError` | `WorkflowService.create_for_room`（Room archived）| 409 | `conflict` | room MSG-RM-HTTP-003（room 既存ハンドラが処理）|
| `RequestValidationError` | FastAPI Pydantic デシリアライズ失敗 | 422 | `validation_error` | http-api-foundation MSG-HAF-002（既存ハンドラが処理）|
| `HTTPException` | CSRF ミドルウェア（`Origin` 不一致）| 403 | `forbidden` | http-api-foundation MSG-HAF-004（既存ハンドラが処理）|
| `Exception`（その他）| どこでも | 500 | `internal_error` | http-api-foundation MSG-HAF-003（既存ハンドラが処理）|

## 確定 C: 例外ハンドラ実装（`error_handlers.py` 追記）

http-api-foundation の `error_handlers.py` に以下のハンドラ関数を追記し、`app.py` の `_register_exception_handlers` で登録する。

| ハンドラ関数名 | 処理例外 | 返却する ErrorResponse |
|---|---|---|
| `workflow_not_found_handler` | `WorkflowNotFoundError` | `ErrorResponse(code="not_found", message=MSG-WF-HTTP-001)` + HTTP 404 |
| `workflow_archived_handler` | `WorkflowArchivedError` | `kind` 属性で分岐: `kind="update"` → MSG-WF-HTTP-002 / `kind="assign"` → MSG-WF-HTTP-003 + HTTP 409 |
| `workflow_preset_not_found_handler` | `WorkflowPresetNotFoundError` | `ErrorResponse(code="not_found", message=MSG-WF-HTTP-004)` + HTTP 404 |
| `workflow_invariant_violation_handler` | `WorkflowInvariantViolation` | HTTP 422, `ErrorResponse(code="validation_error", message=<前処理済みメッセージ>)` |

登録順は room ハンドラ群の直後（既存の `HTTPException` / `RequestValidationError` / `Exception` ハンドラより**前**）に登録する。

**`workflow_invariant_violation_handler` の前処理ルール（room http-api §確定C と同一パターン）**:
1. `[FAIL] ` プレフィックスを除去: `re.sub(r"^\[FAIL\]\s*", "", str(exc))`
2. `\nNext:` 以降を除去: `.split("\nNext:")[0].strip()`

これにより domain 内部の AI エージェント向けフォーマットが HTTP クライアントに露出しない。

**`workflow_archived_handler` の `kind` 判定ルール**:
- `WorkflowArchivedError` は `kind: str` 属性を持つ（`"update"` or `"assign"`）
- `kind="update"` → 409, MSG-WF-HTTP-002（PATCH / DELETE で archive済み Workflow を操作）
- `kind="assign"` → 409, MSG-WF-HTTP-003（POST /api/rooms/{room_id}/workflows で archive済み Workflow を再割り当て）

## 確定 D: プリセット定義構造

プリセットは **アプリ内 static データ** として `bakufu/interfaces/http/schemas/workflow.py`（または専用の `bakufu/application/presets/workflow_presets.py`）にモジュールレベル定数として定義する。DB クエリ / ファイル読み込みは不使用。

### 提供プリセット（MVP）

| `preset_name` | `display_name` | `description` | Stage 数 | Transition 数 |
|---|---|---|---|---|
| `"v-model"` | `"Vモデル開発フロー"` | V モデル開発プロセス（要件定義〜受け入れテスト）の標準フロー | 13 | 15 |
| `"agile"` | `"アジャイルスプリント"` | 2 週間スプリントを基本とするアジャイル開発フロー | 6 | 8 |

プリセットの Stage / Transition 定義詳細（UUIDs / 各フィールド値）は実装時に確定する（設計書への埋め込みは二重管理となるため省略）。

**プリセット解決ロジック（凍結）**:
1. `WorkflowService.create_for_room()` が `preset_name` を受け取る
2. `WORKFLOW_PRESETS: dict[str, WorkflowPresetDefinition]` から `preset_name` をキーとして検索
3. 不在 → `WorkflowPresetNotFoundError(preset_name=preset_name)` を raise（MSG-WF-HTTP-004）
4. 定義から Stage / Transition / entry_stage_id / name を取得し `Workflow(...)` を構築
5. 呼び出し元の `name` 引数が None でない場合は、プリセットデフォルト name を上書き可能

## 確定 E: エンドポイント定義（`routers/workflows.py`）

| メソッド | パス | パスパラメータ | リクエスト Body | レスポンス | ステータスコード |
|---|---|---|---|---|---|
| POST | `/api/rooms/{room_id}/workflows` | `room_id: UUID` | `WorkflowCreate` | `WorkflowResponse` | 201 |
| GET | `/api/rooms/{room_id}/workflows` | `room_id: UUID` | なし | `WorkflowListResponse` | 200 |
| GET | `/api/workflows/presets` | なし | なし | `WorkflowPresetListResponse` | 200 |
| GET | `/api/workflows/{id}` | `id: UUID` | なし | `WorkflowResponse` | 200 |
| PATCH | `/api/workflows/{id}` | `id: UUID` | `WorkflowUpdate` | `WorkflowResponse` | 200 |
| DELETE | `/api/workflows/{id}` | `id: UUID` | なし | なし（No Content）| 204 |
| GET | `/api/workflows/{id}/stages` | `id: UUID` | なし | `StageListResponse` | 200 |

Router は 2 つの `APIRouter` で構成する:
- `room_workflows_router`: `prefix="/api/rooms"`, `tags=["workflow"]`（room_id スコープのエンドポイント）
- `workflows_router`: `prefix="/api/workflows"`, `tags=["workflow"]`（workflow_id スコープ + presets）

**ルーティング登録順序**（workflows_router 内）:
1. `GET /presets`（リテラルパス — 先に登録）
2. `GET /{id}`
3. `PATCH /{id}`
4. `DELETE /{id}`
5. `GET /{id}/stages`

FastAPI はリテラルパスをパスパラメータより優先するが、登録順でも二重に担保する。

`http-api-foundation` の `app.py` に両 router を `app.include_router(...)` で追記する。

## 確定 F: application 例外定義（`application/exceptions/workflow_exceptions.py`）

| 例外クラス名 | 基底クラス | `__init__` 引数 | 用途 |
|---|---|---|---|
| `WorkflowNotFoundError` | `Exception` | `workflow_id: str` | find_by_id / archive / update で Workflow 不在 |
| `WorkflowArchivedError` | `Exception` | `workflow_id: str`, `kind: str` | update で archived=True の Workflow を操作 (`kind="update"`) / create_for_room でアーカイブ済み Workflow を割り当て (`kind="assign"`) |
| `WorkflowPresetNotFoundError` | `Exception` | `preset_name: str` | create_for_room で未知の preset_name |

**`WorkflowNotFoundError` の正式移転（room_exceptions.py との整合）**:
room http-api（Issue #57）で `room_exceptions.py` に暫定定義された `WorkflowNotFoundError` は、本 PR で `workflow_exceptions.py` に正式移転する。`room_exceptions.py` では `from bakufu.application.exceptions.workflow_exceptions import WorkflowNotFoundError` に変更し、暫定定義を削除する。

## 確定 G: `WorkflowService` メソッド一覧

http-api-foundation 確定F で骨格が確定済み（`WorkflowService.__init__(repo: WorkflowRepository)`）。本 PR で以下のシグネチャに変更し、メソッドを全て肉付けする。

コンストラクタ変更: `__init__(self, workflow_repo, room_repo, session)` に拡張（Room 割り当て更新のため `RoomRepository` と `AsyncSession` を追加）。

| メソッド名 | 引数 | 戻り値 | raises |
|---|---|---|---|
| `create_for_room` | `room_id: RoomId, workflow_create: WorkflowCreateDTO` | `Workflow` | `RoomNotFoundError` / `RoomArchivedError` / `WorkflowPresetNotFoundError` / `WorkflowInvariantViolation` |
| `find_by_room` | `room_id: RoomId` | `Workflow \| None` | `RoomNotFoundError` |
| `find_by_id` | `workflow_id: WorkflowId` | `Workflow` | `WorkflowNotFoundError` |
| `update` | `workflow_id: WorkflowId, name: str \| None, stages: list \| None, transitions: list \| None, entry_stage_id: StageId \| None` | `Workflow` | `WorkflowNotFoundError` / `WorkflowArchivedError(kind="update")` / `WorkflowInvariantViolation` |
| `archive` | `workflow_id: WorkflowId` | `None` | `WorkflowNotFoundError` |
| `find_stages` | `workflow_id: WorkflowId` | `tuple[list[Stage], list[Transition], StageId]` | `WorkflowNotFoundError` |
| `get_presets` | なし | `list[WorkflowPresetDefinition]` | 該当なし（static データ）|

`create_for_room` / `update` / `archive` は `async with session.begin()` を service 内で開く（UoW 責務は service 層が持つ）。

**`update` の部分更新ルール（凍結）**: `stages` が None の場合は既存 stages を維持。`stages` が非 None の場合は `transitions` / `entry_stage_id` も同時に更新する（詳細設計 §確定A §WorkflowUpdate 整合バリデーション参照）。`name` のみの更新は既存 DAG 構造を維持したまま name だけ差し替えて `Workflow(...)` を再構築する。

**`archive` の冪等性**: `workflow.archived` がすでに True の場合も `workflow.archive()` を呼び出し save する（冪等）。2 回目の DELETE も 204 を返す。

## 確定 H: `dependencies.py` 追記（DI ファクトリ拡張）

http-api-foundation の `dependencies.py` の `get_workflow_service` を以下に変更する。

| 関数名 | 型シグネチャ変更前 | 型シグネチャ変更後 |
|---|---|---|
| `get_workflow_service` | `(session: SessionDep) → WorkflowService`（WorkflowRepo のみ）| `(session: SessionDep) → WorkflowService`（WorkflowRepo + RoomRepo + session を渡す）|

`get_workflow_service` の実装変更点:
- `SqliteRoomRepository(session)` を生成し `RoomRepository` として渡す
- `session` を `WorkflowService` コンストラクタに渡す（UoW のため）
- `get_room_service()` への依存は持たない（循環依存を避けるため WorkflowService が RoomRepository を直接受け取る）

`WorkflowServiceDep = Annotated[WorkflowService, Depends(get_workflow_service)]` 型エイリアスを定義し、各エンドポイントで簡潔に使えるようにする。

## MSG 確定文言表

| MSG ID | `code` | `message`（確定文言）| HTTP ステータス |
|---|---|---|---|
| MSG-WF-HTTP-001 | `not_found` | `"Workflow not found."` | 404 |
| MSG-WF-HTTP-002 | `conflict` | `"Workflow is archived and cannot be modified."` | 409 |
| MSG-WF-HTTP-003 | `conflict` | `"Workflow is archived and cannot be assigned to a room."` | 409 |
| MSG-WF-HTTP-004 | `not_found` | `"Workflow preset not found."` | 404 |
| MSG-WF-HTTP-005 | `validation_error` | `WorkflowInvariantViolation.message` から `[FAIL]` プレフィックスと `\nNext:.*` を除去した本文のみ（例: `"entry_stage_id が stages に存在しません。"`）| 422 |

MSG-WF-HTTP-005 は domain 層の `WorkflowInvariantViolation.message` を **前処理したうえで** HTTP レスポンスに使用する（前処理ルールは §確定C 末尾に凍結）。

## 参照設計との整合確認

| http-api-foundation 確定事項 | workflow http-api での適用 |
|---|---|
| 確定A: ErrorCode 定数（`not_found` / `validation_error` / `internal_error` / `forbidden`）| `conflict` を empire / room と共通で使用（`error_handlers.py` の `ErrorCode` 定数に追加済み）|
| 確定B: `app.state.session_factory` / `engine` | `get_session()` DI 経由で `AsyncSession` を取得（変更なし）|
| 確定D: CSRF Origin 検証（MVP: Origin なし通過 / 不一致 403）| POST / PATCH / DELETE は CSRF ミドルウェアが適用される（追加設定不要）|
| 確定E: `get_session()` DI | `get_workflow_service(session=Depends(get_session))` で利用（変更なし）|
| 確定F: Service `__init__(repo)` 骨格 | `WorkflowService.__init__` の引数を workflow_repo + room_repo + session に拡張 |

## 開放論点

| # | 論点 | 起票先 |
|---|---|---|
| Q-OPEN-1 | `Workflow.archived` フィールドの domain 追加と Alembic revision（`0004_workflow_archived.py`）は本 PR スコープ内で対処。domain basic-design.md も同一 PR で更新する | 本 PR（Issue #58）|
| Q-OPEN-2 | プリセット定義の配置先（`schemas/workflow.py` 内 or `application/presets/workflow_presets.py`）。DDD 観点では application 層配置が望ましい（schemas は interfaces 層のため）。実装者が判断する | 本 PR（Issue #58）|
| Q-OPEN-3 | `GET /api/rooms/{room_id}/workflows` の返却形式: Room.workflow_id が未設定（None）の場合の対応。現設計では Room.workflow_id は必須なので 0 件のケースは発生しないが、将来 Room 作成時の workflow_id 任意化対応で変更が必要になる可能性がある | 将来 Issue |
| Q-OPEN-4 | `WorkflowUpdate` で DAG 部分更新（stages のみ更新、transitions は既存維持）を許可するか。本設計では DAG の整合性を担保するため同時更新を必須とした。将来の UI ワークフローエディタの要件次第では分割更新が必要になる可能性がある | 将来 Issue（workflow-ui）|
