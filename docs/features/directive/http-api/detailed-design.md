# 詳細設計書

> feature: `directive` / sub-feature: `http-api`
> 関連 Issue: [#60 feat(task-http-api): Directive + Task lifecycle HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/60)
> 関連: [`basic-design.md`](basic-design.md) / [`../feature-spec.md`](../feature-spec.md)
> 凍結済み設計参照: [`docs/design/architecture.md`](../../../design/architecture.md) / [`docs/design/threat-model.md`](../../../design/threat-model.md)

## 確定事項一覧（Issue #60 設計凍結）

| 記号 | 論点 | 決定内容 |
|-----|------|---------|
| 確定A | masking 要否（`text` の HTTP レスポンス） | `DirectiveResponse.text` に `@field_serializer` で `mask()` 適用（defense-in-depth）。`@field_serializer` は POST **全レスポンスパス**で発火（mode 制限なし）。DB は MaskedText TypeDecorator で既にマスキング済み。GET レスポンスでも masked 値を返す |
| 確定B | アトミック UoW | `DirectiveService.issue()` 内で `async with session.begin()` を 1 ブロックで包む。Directive 保存 → link_task → Directive UPSERT → Task 保存の 4 操作が同一トランザクション |
| 確定C | `$` プレフィックス正規化 | `DirectiveService.issue()` が `text = raw_text if raw_text.startswith('$') else '$' + raw_text` で正規化（業務ルール R1-A）。Aggregate 側は valid な text しか受け取らない契約 |
| 確定D | DirectiveInvariantViolation → 422 | domain 層の `DirectiveInvariantViolation` は application 層でそのまま伝播させ、error_handlers.py が 422 に変換 |
| 確定E | Room archived 確認 | `DirectiveService.issue()` が Room を取得し `room.archived` を確認。`RoomArchivedError` を raise → 409 |
| 確定F | DirectiveService のコンストラクタ | `__init__(self, directive_repo: DirectiveRepository, task_repo: TaskRepository, room_repo: RoomRepository, workflow_repo: WorkflowRepository, session: AsyncSession) -> None`。Task の `current_stage_id` は `Workflow.entry_stage_id` でなければならず、Room は `workflow_id` だけを保持するため、WorkflowRepository 参照を application 層責務として明示する |

## Pydantic スキーマ定義

### `DirectiveCreate`（リクエスト Body）

| フィールド | 型 | バリデーション | 備考 |
|----------|---|-------------|------|
| `text` | `str` | `min_length=1`, `max_length=10000` | `$` プレフィックスは application 層で付加（R1-A）。Pydantic 段階では min 1 文字のみ強制 |

### `DirectiveResponse`（レスポンス）

| フィールド | 型 | 備考 |
|----------|---|------|
| `id` | `str` | `DirectiveId` を `str(directive_id.value)` で変換 |
| `text` | `str` | `@field_serializer` で `mask()` 適用（確定A）。DB から取得した masked 値をそのまま返す |
| `target_room_id` | `str` | `RoomId.value` を str で変換 |
| `created_at` | `str` | ISO 8601 UTC（`datetime.isoformat() + 'Z'`）|
| `task_id` | `str \| None` | `TaskId.value` を str で変換。None は Task 未紐付け初期状態（POST 直後は必ず存在）|

### `TaskResponse`（レスポンス）

※ Task HTTP API 側の共通スキーマを参照（[`../../task/http-api/detailed-design.md §TaskResponse`](../../task/http-api/detailed-design.md)）。本スキーマは `interfaces/http/schemas/task.py` に定義し、directive スキーマからインポートして再利用する。

### `DirectiveWithTaskResponse`（POST レスポンス）

| フィールド | 型 | 備考 |
|----------|---|------|
| `directive` | `DirectiveResponse` | 発行された Directive |
| `task` | `TaskResponse` | 同時に起票された Task（status=PENDING）|

## MSG 確定文言表

| ID | 条件 | message | detail | HTTP |
|---|------|---------|--------|------|
| MSG-DR-HTTP-001 | `DirectiveInvariantViolation` — テキスト超過・NFC 問題等 | domain 層の `str(exc)` から **`[FAIL]` プレフィックスと `\nNext:.*` を除去した本文のみ**（`re.sub(r"^\[FAIL\]\s*", "", str(exc)).split("\nNext:")[0].strip()`）— empire / room / workflow / agent と同一前処理パターン | `{"kind": exc.kind}` | 422 |

**前処理ルール（empire / room / workflow / agent と同一パターン）**:
1. `[FAIL] ` プレフィックスを除去: `re.sub(r"^\[FAIL\]\s*", "", str(exc))`
2. `\nNext:` 以降を除去: `.split("\nNext:")[0].strip()`

これにより domain 内部の AI エージェント向けフォーマット（業務ルール R1-E）が HTTP クライアントに露出しない。`directive_invariant_violation_handler` はこの前処理を適用したうえで `ErrorResponse.message` を構築する。

## 例外マッピング詳細

```
DirectiveService.issue() 内の例外発生元 → HTTP ステータス対応表

RoomNotFoundError          → 404 not_found      （既存 room ハンドラ再利用）
RoomArchivedError          → 409 conflict        （既存 room ハンドラ再利用）
DirectiveInvariantViolation → 422 validation_error（本 PR で error_handlers.py に追記）
TaskInvariantViolation      → 422 validation_error（task http-api 側で error_handlers.py に追記）
ValidationError (Pydantic)  → 422 validation_error（既存 http-api-foundation ハンドラ再利用）
```

## DI ファクトリ

`backend/src/bakufu/interfaces/http/dependencies.py` に以下を追記する:

| 関数名 | シグネチャ概要 | 責務 |
|-------|-------------|------|
| `get_directive_service` | `(session=Depends(get_session)) -> DirectiveService` | `DirectiveRepository`（SQLite 実装）/ `TaskRepository`（SQLite 実装）/ `RoomRepository`（SQLite 実装）/ `WorkflowRepository`（SQLite 実装）/ `session` を注入して `DirectiveService` を生成する |

## 確定G: `DirectiveService.issue()` の例外優先順位（凍結）

複数条件が同時に満たされる場合（archived Room に空テキストを POST する等）に対して、例外の発生順序を凍結する:

| 優先順 | 確認内容 | 発生例外 | HTTP |
|-------|---------|---------|------|
| 1 | Room 存在確認（`room_repo.find_by_id` → None）| `RoomNotFoundError` | 404 |
| 2 | Room archived 確認（`room.archived == True`）| `RoomArchivedError` | 409 |
| 3 | Workflow 存在確認（`workflow_repo.find_by_id(room.workflow_id)` → None）| `WorkflowNotFoundError` | 404 |
| 4 | `$` プレフィックス正規化（R1-A） | — （例外なし、補完するのみ）| — |
| 5 | `Directive(...)` 構築・不変条件検査 | `DirectiveInvariantViolation` | 422 |
| 6 | `Task(...)` 構築・不変条件検査 | `TaskInvariantViolation` | 422 |
| 7 | `async with session.begin()` UoW | DB 例外 → 自動ロールバック | 500 |

**Room 不在は archived より先に確認する**（存在しない Room に archived 確認は無意味）。Directive 構築は Room 確認後。この順序を実装者が守らないと、テストが揺れる。

## アトミック UoW 実装契約

`DirectiveService.issue()` の UoW ブロックの操作順序を凍結する:

1. `DirectiveRepository.save(directive)` — task_id=None の初期状態で永続化
2. `directive_with_task = directive.link_task(task_id)` — pre-validate で task_id セット済み新インスタンス生成
3. `DirectiveRepository.save(directive_with_task)` — UPSERT で task_id を更新
4. `TaskRepository.save(task)` — Task を永続化（directive_id FK が directives.id を参照）

全 4 操作は `async with session.begin()` ブロック内に収める。例外発生時は自動ロールバック。

**制約**: 手順 1 を省略して手順 3 だけにできない理由: `Task.directive_id` が `directives.id` への FK を持つため、Task 保存（手順 4）の前に Directive が DB に存在している必要がある。手順 1→3 の UPSERT は FK 整合性のために必要。

## セキュリティ補足

### Directive.text の masking（確定A 詳細）

- DB 層（永続化前）: `MaskedText` TypeDecorator が `directives.text` カラムへの書き込み時に `mask()` を適用（repository sub-feature で確定済み、業務ルール R1-F）
- HTTP 層（レスポンス時）: `DirectiveResponse.text` に `@field_serializer('text')` を定義し、`mask(value)` を適用する。既に masked の値（`<REDACTED:*>` パターン）は `mask()` の冪等性により二重 masking されない
- 目的: DB が何らかの原因で raw 値を返した場合でも HTTP レスポンスに secret が漏洩しない（defense-in-depth）

### UoW ロールバックによる整合性保証

- Directive 保存成功 + Task 保存失敗 → セッション全体がロールバック → directives テーブルに孤立レコードが残らない
- 逆（Task 先行）は FK 制約により物理的に不可能

## カバレッジ基準（本 sub-feature の IT / UT）

| 観点 | 目標 |
|---|---|
| `DirectiveService.issue()` | UT: 正常系 + Room 不在 / archived / DirectiveInvariantViolation / TaskInvariantViolation / UoW ロールバックの各異常系 |
| `DirectiveRouter` POST | IT: TestClient 経由で HTTP 201 + 404 + 409 + 422 の各ステータスを検証 |
| masking | IT: `DirectiveResponse.text` に secret を含む text を渡した場合、レスポンス JSON の `text` フィールドが `<REDACTED:*>` を含むことを確認 |
| 実装カバレッジ | 90% 以上（`directive_service.py` + `directives.py` router + `directive.py` schemas）|

詳細テストケースは [`test-design.md`](test-design.md) で凍結する。
