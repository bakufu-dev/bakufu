# 要件定義書

> feature: `task`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/architecture/domain-model/aggregates.md`](../../architecture/domain-model/aggregates.md) §Task / [`storage.md`](../../architecture/domain-model/storage.md) §Deliverable / §Attachment

## 機能要件

### REQ-TS-001: Task 構築

| 項目 | 内容 |
|------|------|
| 入力 | `id: TaskId` / `room_id: RoomId` / `directive_id: DirectiveId` / `current_stage_id: StageId` / `deliverables: dict[StageId, Deliverable]`（既定 `{}`）/ `status: TaskStatus`（既定 `PENDING`）/ `assigned_agent_ids: list[AgentId]`（既定 `[]`、最大 5 件）/ `created_at: datetime`（UTC、tz-aware）/ `updated_at: datetime`（UTC）/ `last_error: str \| None`（既定 None） |
| 処理 | Pydantic 型バリデーション → `model_validator(mode='after')` で不変条件検査（`assigned_agent_ids` 重複禁止 / `last_error` consistency / `last_error` 空文字列禁止 / `created_at` ≤ `updated_at`） |
| 出力 | valid な `Task` インスタンス（frozen） |
| エラー時 | `TaskInvariantViolation` を raise。`message` は MSG-TS-NNN（2 行構造、§確定 R1-G）、`kind` は `assigned_agents_unique` / `last_error_consistency` / `blocked_requires_last_error` / `timestamp_order` のいずれか。型違反は `pydantic.ValidationError`（MSG-TS-003） |

### REQ-TS-002: Agent 割当（assign）

| 項目 | 内容 |
|------|------|
| 入力 | `agent_ids: list[AgentId]`（最大 5 件、重複なし） |
| 処理 | (1) terminal 検査 → (2) state machine table lookup `(self.status, 'assign')` → IN_PROGRESS でなければ `state_transition_invalid` で raise → (3) `_rebuild_with_state(status=IN_PROGRESS, assigned_agent_ids=agent_ids, updated_at=now)` で新インスタンス構築 → (4) `model_validator` 走行 |
| 出力 | 新 `Task` インスタンス（pre-validate 方式、元 Task は不変） |
| エラー時 | `TaskInvariantViolation(kind='terminal_violation' / 'state_transition_invalid' / 'assigned_agents_unique')` |

### REQ-TS-003: 成果物 commit（commit_deliverable）

| 項目 | 内容 |
|------|------|
| 入力 | `stage_id: StageId` / `deliverable: Deliverable` / `by_agent_id: AgentId` |
| 処理 | (1) terminal 検査 → (2) state machine 上 `IN_PROGRESS` のときのみ許可 → (3) `deliverables[stage_id] = deliverable` で dict 更新 → (4) `_rebuild_with_state(deliverables=updated_dict, updated_at=now)` |
| 出力 | 新 Task |
| エラー時 | `TaskInvariantViolation(kind='terminal_violation' / 'state_transition_invalid')`（IN_PROGRESS 以外で commit を試みた場合） |

### REQ-TS-004: External Review 要求（request_external_review）

| 項目 | 内容 |
|------|------|
| 入力 | なし（self.current_stage_id を見る） |
| 処理 | (1) terminal 検査 → (2) state machine table lookup `(self.status, 'request_external_review')` → AWAITING_EXTERNAL_REVIEW でなければ raise → (3) `_rebuild_with_state(status=AWAITING_EXTERNAL_REVIEW, updated_at=now)` |
| 出力 | 新 Task。Gate Aggregate の生成は application 層責務（本 Aggregate は state 遷移のみ） |
| エラー時 | `TaskInvariantViolation(kind='state_transition_invalid')`（IN_PROGRESS 以外） |

### REQ-TS-005: Stage 進行（advance）

| 項目 | 内容 |
|------|------|
| 入力 | `transition_id: TransitionId` / `by_owner_id: OwnerId` / `next_stage_id: StageId` / `is_terminal: bool` |
| 処理 | (1) terminal 検査 → (2) state machine table lookup `(self.status, 'gate_approved' or 'gate_rejected' or 'advance_to_done')` → (3) `is_terminal=True` なら `_rebuild_with_state(status=DONE, current_stage_id=next_stage_id, updated_at=now)`、False なら `_rebuild_with_state(status=IN_PROGRESS, current_stage_id=next_stage_id, updated_at=now)` |
| 出力 | 新 Task |
| エラー時 | `TaskInvariantViolation(kind='terminal_violation' / 'state_transition_invalid')` |

`transition_id` の Workflow 内存在検証 / `next_stage_id` の Workflow 内存在検証は **application 層責務**（§確定 R1-A の責務分離）。

### REQ-TS-006: 中止（cancel）

| 項目 | 内容 |
|------|------|
| 入力 | `by_owner_id: OwnerId` / `reason: str`（1〜2000 文字、NFC 正規化のみ・strip しない） |
| 処理 | (1) terminal 検査（DONE / CANCELLED は raise） → (2) state machine table lookup `(self.status, 'cancel')` → CANCELLED 遷移を許可（PENDING / IN_PROGRESS / AWAITING_EXTERNAL_REVIEW / BLOCKED の 4 状態 × cancel） → (3) `_rebuild_with_state(status=CANCELLED, last_error=None, updated_at=now)` |
| 出力 | 新 Task（terminal、以後変更不可） |
| エラー時 | `TaskInvariantViolation(kind='terminal_violation')`（DONE / CANCELLED の Task に再 cancel） |

`reason` 自体は Aggregate 属性として保持しない（audit_log に application 層が記録する責務）。

### REQ-TS-007: BLOCKED 化（block）

| 項目 | 内容 |
|------|------|
| 入力 | `reason: str` / `last_error: str`（**1〜10000 文字、NFC 正規化のみ・strip しない、空文字列禁止**、§確定 R1-C） |
| 処理 | (1) terminal 検査 → (2) state machine table lookup `(self.status, 'block')` → BLOCKED 遷移は IN_PROGRESS のときのみ許可 → (3) `last_error` の NFC 正規化 → 空文字列検査 → (4) `_rebuild_with_state(status=BLOCKED, last_error=normalized_last_error, updated_at=now)` |
| 出力 | 新 Task |
| エラー時 | `TaskInvariantViolation(kind='terminal_violation' / 'state_transition_invalid' / 'blocked_requires_last_error')` |

### REQ-TS-008: BLOCKED 復旧（unblock_retry）

| 項目 | 内容 |
|------|------|
| 入力 | なし |
| 処理 | (1) terminal 検査 → (2) state machine table lookup `(self.status, 'unblock_retry')` → IN_PROGRESS 遷移は BLOCKED のときのみ許可 → (3) `_rebuild_with_state(status=IN_PROGRESS, last_error=None, updated_at=now)`（§確定 R1-D） |
| 出力 | 新 Task |
| エラー時 | `TaskInvariantViolation(kind='terminal_violation' / 'state_transition_invalid')`（BLOCKED 以外） |

### REQ-TS-009: 不変条件検査

| 項目 | 内容 |
|------|------|
| 入力 | Task の現状属性 |
| 処理 | `_validate_assigned_agents_unique`（`assigned_agent_ids` 重複なし）/ `_validate_last_error_consistency`（status と last_error の整合）/ `_validate_blocked_has_last_error`（status=BLOCKED ⇔ last_error 非空）/ `_validate_timestamp_order`（created_at ≤ updated_at）/ `_validate_assigned_agents_capacity`（最大 5 件）を順次実行。命名対称性: empire / workflow / agent / room / directive と並ぶ `_validate_*` helper |
| 出力 | 違反なしなら return（None）、違反時は `TaskInvariantViolation` を raise |
| エラー時 | `TaskInvariantViolation` 単一例外。`kind` で違反種別を識別 |

### REQ-TS-010: `Deliverable` / `Attachment` VO 導入（§確定 R1-E）

| 項目 | 内容 |
|------|------|
| 入力 | `Deliverable(stage_id, body_markdown, attachments, committed_by, committed_at)` / `Attachment(sha256, filename, mime_type, size_bytes)` |
| 処理 | Pydantic v2 BaseModel + frozen + extra='forbid'。`Attachment` は `field_validator` で sha256 形式（64 hex 小文字）/ filename サニタイズ（[`storage.md`](../../architecture/domain-model/storage.md) §filename サニタイズ規則）/ MIME ホワイトリスト（同 §MIME タイプ検証）/ size_bytes ≤ 10MiB を検査 |
| 出力 | valid な `Deliverable` / `Attachment` インスタンス（frozen） |
| エラー時 | `pydantic.ValidationError`（型違反、サニタイズ違反、ホワイトリスト違反、サイズ超過） |

### REQ-TS-011: `TaskStatus` / `LLMErrorKind` enum 追加

| 項目 | 内容 |
|------|------|
| 入力 | 該当なし（enum 定義） |
| 処理 | `domain/value_objects.py` に `TaskStatus(StrEnum)` で 6 値（PENDING / IN_PROGRESS / AWAITING_EXTERNAL_REVIEW / BLOCKED / DONE / CANCELLED）+ `LLMErrorKind(StrEnum)` で 5 値（SESSION_LOST / RATE_LIMITED / AUTH_EXPIRED / TIMEOUT / UNKNOWN）を追加 |
| 出力 | StrEnum 型（既存 `Role` / `StageKind` / `TransitionCondition` と同様） |
| エラー時 | 該当なし |

## 画面・CLI 仕様

### CLI レシピ / コマンド

該当なし — 理由: 本 feature は domain 層のみ。Admin CLI は `feature/admin-cli` で扱う。BLOCKED Task の retry / cancel コマンド（`bakufu admin task retry-task <task_id>` / `bakufu admin task cancel-task <task_id>`）は `feature/admin-cli` 責務。

| コマンド | 概要 |
|---------|------|
| 該当なし | — |

### Web UI 画面

該当なし — 理由: UI は `feature/chat-ui`（Phase 2）で扱う。

| 画面ID | 画面名 | 主要操作 |
|-------|-------|---------|
| 該当なし | — | — |

## API 仕様

該当なし — 理由: API は `feature/http-api` で扱う。本 feature は domain 層のみ。

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| 該当なし | — | — | — | — |

## データモデル

`docs/architecture/domain-model/aggregates.md` §Task および `storage.md` §Deliverable / §Attachment の凍結済み定義に従う。本 feature では新規 VO として `Deliverable` / `Attachment` を実体化、`TaskStatus` / `LLMErrorKind` enum を追加する（`TaskId` は既存）。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| Task | `id` | `TaskId` | 不変、UUIDv4 | Aggregate Root |
| Task | `room_id` | `RoomId` | UUIDv4。既存 Room を指す（参照整合性は application 層） | Room への参照 |
| Task | `directive_id` | `DirectiveId` | UUIDv4。既存 Directive を指す（同上） | Directive への参照 |
| Task | `current_stage_id` | `StageId` | UUIDv4。Room の Workflow 内 Stage を指す（同上） | Stage への参照 |
| Task | `deliverables` | `dict[StageId, Deliverable]` | キー一意（dict 型レベル）、空 dict 既定 | Deliverable VO への参照群 |
| Task | `status` | `TaskStatus` | enum 6 値 | — |
| Task | `assigned_agent_ids` | `list[AgentId]` | 重複なし、最大 5 件 | Agent への参照群 |
| Task | `created_at` | `datetime` | UTC、tz-aware | — |
| Task | `updated_at` | `datetime` | UTC、tz-aware、`created_at ≤ updated_at` | — |
| Task | `last_error` | `str \| None` | 1〜10000 文字（NFC 正規化のみ、strip しない、空文字列禁止）or None。`status == BLOCKED` ⇔ 非空文字列 | — |
| Deliverable | `stage_id` | `StageId` | UUIDv4 | — |
| Deliverable | `body_markdown` | `str` | 0〜1,000,000 文字。永続化前マスキング対象（task-repository PR で `MaskedText` 配線） | — |
| Deliverable | `attachments` | `list[Attachment]` | 0 件以上、Task あたり総和 100 MiB 以下（§Attachment）。Aggregate 集計検証は application 層責務 | Attachment VO 群 |
| Deliverable | `committed_by` | `AgentId` | UUIDv4 | Agent への参照 |
| Deliverable | `committed_at` | `datetime` | UTC、tz-aware | — |
| Attachment | `sha256` | `str` | 64 文字 hex 小文字（`^[a-f0-9]{64}$`） | — |
| Attachment | `filename` | `str` | 1〜255 文字、§filename サニタイズ規則準拠 | — |
| Attachment | `mime_type` | `str` | §MIME ホワイトリスト 7 種のいずれか | — |
| Attachment | `size_bytes` | `int` | 0 ≤ x ≤ 10485760（10 MiB） | — |

## ユーザー向けメッセージ一覧

全 MSG は **2 行構造**を採用する（§確定 R1-G「フィードバック原則」、確定文言は detailed-design.md §MSG 確定文言表 で凍結）:

- 1 行目: `[FAIL] <failure summary>` — 何が失敗したか
- 2 行目: `Next: <action>` — 次に何をすべきか

「Next:」必須は test-design.md の TC-UT-TS-NNN で `assert "Next:" in str(exc)` により CI 物理保証する。

| ID | 種別 | 例外型 | kind | 表示条件 |
|----|------|------|------|---------|
| MSG-TS-001 | エラー | `TaskInvariantViolation` | `terminal_violation` | DONE / CANCELLED の Task に対する全 7 ふるまい呼び出し |
| MSG-TS-002 | エラー | `TaskInvariantViolation` | `state_transition_invalid` | state machine table に存在しない `(current_status, action)` の組み合わせ |
| MSG-TS-003 | エラー | `TaskInvariantViolation` | `assigned_agents_unique` | `assigned_agent_ids` に重複あり |
| MSG-TS-004 | エラー | `TaskInvariantViolation` | `assigned_agents_capacity` | `assigned_agent_ids` が 6 件以上 |
| MSG-TS-005 | エラー | `TaskInvariantViolation` | `last_error_consistency` | `status != BLOCKED` なのに `last_error != None`、または `status == BLOCKED` なのに `last_error is None` |
| MSG-TS-006 | エラー | `TaskInvariantViolation` | `blocked_requires_last_error` | `block(reason, last_error='')` または NFC 正規化後に空文字列 |
| MSG-TS-007 | エラー | `TaskInvariantViolation` | `timestamp_order` | `created_at > updated_at` |
| MSG-TS-008 | エラー | `pydantic.ValidationError` | — | 型違反（None 渡し / tz-naive datetime / 不正 UUID 等） |
| MSG-TS-009 | エラー | `pydantic.ValidationError` | — | `Attachment.sha256` 形式違反 / `filename` サニタイズ違反 / `mime_type` ホワイトリスト違反 / `size_bytes` 超過 |
| MSG-TS-010 | エラー | `TaskNotFoundError` | — | application 層 `TaskService` で task_id の Task が存在しない |

MSG-TS-008 / 009 / 010 は範囲外（Pydantic 標準 / application 層）だが MSG ID 表に明示。

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | Pydantic v2.x | pyproject.toml（既存） | uv | 既存 |
| Python 依存 | unicodedata（標準ライブラリ） | — | — | NFC 正規化 |
| Python 依存 | enum.StrEnum（標準ライブラリ） | — | — | TaskStatus / LLMErrorKind |
| ドメイン | `TaskId` / `RoomId` / `DirectiveId` / `StageId` / `TransitionId` / `AgentId` / `OwnerId` | `domain/value_objects.py` | 内部 import | 既存 |
| ドメイン | `mask_discord_webhook` / `mask_discord_webhook_in` | `domain/exceptions.py`（5 兄弟と共有） | 内部 import | 既存 |
| 外部サービス | 該当なし | — | — | domain 層のため外部通信なし |
