# 詳細設計書

> feature: `external-review-gate` / sub-feature: `http-api`
> 関連 Issue: [#61 feat(external-review-gate-http-api): ExternalReviewGate HTTP API (approve/reject/cancel, M3)](https://github.com/bakufu-dev/bakufu/issues/61)
> 関連: [`basic-design.md`](basic-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../../http-api-foundation/http-api/detailed-design.md`](../../http-api-foundation/http-api/detailed-design.md)

## 記述ルール（必ず守ること）

詳細設計に**疑似コード・サンプル実装（python/ts/sh/yaml 等の言語コードブロック）を書かない**。
ソースコードと二重管理になりメンテナンスコストしか生まない。
必要なのは「構造契約（属性名・型・制約）」と「確定文言（メッセージ文字列）」と「実装の意図（なぜこの API 形になるか）」であり、コードそのものは実装 PR で書く。

## クラス設計（詳細）

### ExternalReviewGateService（application 層）

http-api-foundation で骨格定義済みの `external_review_gate_service.py` に以下のメソッドを追加する。

| メソッド | シグネチャ | 戻り値 | 意図 |
|---|---|---|---|
| `find_by_id_or_raise` | `(gate_id: GateId) -> ExternalReviewGate` | `ExternalReviewGate` | `find_by_id` が None → `GateNotFoundError` を raise。404 経路の共通化 |
| `find_pending_for_reviewer` | `(reviewer_id: OwnerId) -> list[ExternalReviewGate]` | `list[ExternalReviewGate]` | `ExternalReviewGateRepository.find_pending_by_reviewer(reviewer_id)` の薄い委譲 |
| `find_by_task` | `(task_id: TaskId) -> list[ExternalReviewGate]` | `list[ExternalReviewGate]` | `ExternalReviewGateRepository.find_by_task_id(task_id)` の薄い委譲（時系列昇順）|
| `approve` | `(gate: ExternalReviewGate, reviewer_id: OwnerId, comment: str, decided_at: datetime) -> ExternalReviewGate` | `ExternalReviewGate` | **reviewer_id 照合責務の凍結: Service 内で `gate.reviewer_id != reviewer_id` を照合し `GateAuthorizationError` を raise（Router / domain に委ねない）**。照合通過後に domain の `gate.approve()` に委譲。`ExternalReviewGateInvariantViolation(kind='decision_already_decided')` → `GateAlreadyDecidedError` に変換 |
| `reject` | `(gate: ExternalReviewGate, reviewer_id: OwnerId, feedback_text: str, decided_at: datetime) -> ExternalReviewGate` | `ExternalReviewGate` | approve と同構造。reviewer_id 照合 → `GateAuthorizationError`。domain の `gate.reject(comment=feedback_text, ...)` に委譲（domain の引数名は `comment`、Schema フィールド名 `feedback_text` と区別）|
| `cancel` | `(gate: ExternalReviewGate, reviewer_id: OwnerId, reason: str, decided_at: datetime) -> ExternalReviewGate` | `ExternalReviewGate` | approve と同構造。reviewer_id 照合 → `GateAuthorizationError`。domain の `gate.cancel()` に委譲 |
| `save` | `(gate: ExternalReviewGate) -> None` | `None` | `ExternalReviewGateRepository.save(gate)` への薄委譲。Router が `session.begin()` 内から呼ぶ。Service 内で `commit()` / `rollback()` は呼ばない（UoW 管理は Router 責務）|

**設計上の意図**: `approve` / `reject` / `cancel` は「reviewer_id 照合 + domain メソッド呼び出し + 例外変換」を担う。`save()` は独立メソッドで薄委譲。Router が `async with session.begin():` 内で `find_by_id_or_raise` → `approve` → `save` をシーケンスで呼ぶことでUoW境界を管理する（§確定E 参照）。

### GateNotFoundError / GateAlreadyDecidedError / GateAuthorizationError（application 例外）

| 例外クラス | 属性 | 意図 |
|---|---|---|
| `GateNotFoundError` | `gate_id: GateId` | `find_by_id()` が None を返した場合。HTTP 404 に変換 |
| `GateAlreadyDecidedError` | `gate_id: GateId`, `current_decision: ReviewDecision` | domain `ExternalReviewGateInvariantViolation(kind='decision_already_decided')` を wrap。HTTP 409 に変換 |
| `GateAuthorizationError` | `gate_id: GateId`, `reviewer_id: OwnerId`, `expected_reviewer_id: OwnerId` | reviewer_id 照合失敗。HTTP 403 に変換 |

### GateSchemas（schemas/external_review_gate.py）

**リクエストモデル**:

| クラス | フィールド | 型 | 制約 | 意図 |
|---|---|---|---|---|
| `GateApprove` | `comment` | `str` | デフォルト `""`、0〜10000 文字 | approve コメント（任意。空文字は有効）|
| `GateReject` | `feedback_text` | `str` | 1〜10000 文字（空文字不可）| 差し戻し理由（業務的に必須、空文字不可）|
| `GateCancel` | `reason` | `str` | デフォルト `""`、0〜10000 文字 | キャンセル理由（任意）|

**レスポンスモデル**:

| クラス | フィールド | 型 | 制約 / 意図 |
|---|---|---|---|
| `AuditEntryResponse` | `actor_id` | `str` | OwnerId を str 化 |
| | `action` | `str` | `ReviewDecision.value` または `AuditAction.value` |
| | `comment` | `str` | DB 値そのまま（書き込み時 mask() 済み — §確定B）|
| | `occurred_at` | `str` | ISO 8601 UTC（`Z` suffix）|
| `AttachmentResponse` | `sha256` | `str` | 64 hex |
| | `filename` | `str` | — |
| | `mime_type` | `str` | — |
| | `size_bytes` | `int` | — |
| `DeliverableSnapshotResponse` | `stage_id` | `str` | StageId を str 化 |
| | `body_markdown` | `str` | DB 値そのまま（書き込み時 mask() 済み — §確定B）|
| | `committed_by` | `str` | OwnerId を str 化 |
| | `committed_at` | `str` | ISO 8601 UTC |
| | `attachments` | `list[AttachmentResponse]` | — |
| `GateResponse`（一覧用）| `id` | `str` | GateId を str 化 |
| | `task_id` | `str` | — |
| | `stage_id` | `str` | — |
| | `reviewer_id` | `str` | — |
| | `decision` | `str` | `ReviewDecision.value`（`"PENDING"` / `"APPROVED"` 等）|
| | `created_at` | `str` | ISO 8601 UTC |
| | `decided_at` | `str \| None` | PENDING の場合 `null` |
| `GateDetailResponse`（単件・操作後）| `GateResponse` のすべてのフィールド + 以下 | — | — |
| | `feedback_text` | `str` | DB 値そのまま（書き込み時 mask() 済み — §確定B）|
| | `deliverable_snapshot` | `DeliverableSnapshotResponse` | — |
| | `audit_trail` | `list[AuditEntryResponse]` | 全閲覧・判断記録（occurred_at 昇順）|
| `GateListResponse` | `items` | `list[GateResponse]` | — |
| | `total` | `int` | `len(items)`（MVP では COUNT クエリなし、YAGNI）|

### get_reviewer_id() Depends

| 関数 | シグネチャ | 戻り値 | 意図 |
|---|---|---|---|
| `get_reviewer_id` | `(authorization: str | None = Header(None, alias="Authorization")) -> OwnerId` | `OwnerId` | `Authorization: Bearer <owner-id>` を解析。ヘッダー不在 / 形式不正 / UUID 不正 → `HTTPException(422)` |

**Bearer トークン解析規則**:
1. `Authorization` ヘッダーが存在しない → `HTTPException(status_code=422, detail=MSG-ERG-HTTP-004)`
2. 値が `"Bearer "` で始まらない → 同上
3. トークン部分が UUID 形式でない → 同上（OwnerId の生成方式は `docs/design/domain-model/value-objects.md §OwnerId` を参照）
4. UUID 形式であれば `OwnerId(token_part)` として `get_reviewer_id()` が返す

**MVP 設計意図**: Bearer トークン = OwnerId（UUID）という単純な識別方式を採用する。本格的な JWT / OIDC 認証は Phase 2 スコープ（YAGNI）。loopback バインドにより外部到達不能であるため、この単純化はセキュリティ的に許容できる（http-api-foundation §A07 参照）。

**`get_reviewer_id()` を公開関数とする根拠**: FastAPI の `Depends()` は callable を受け取る。標準的なパターンは公開関数（FastAPI 公式 https://fastapi.tiangolo.com/tutorial/dependencies/ 参照）。Dependable クラスへの昇格は状態保持や複数 method が必要な場合に有効だが、本 Depends は解析ロジックのみで状態を持たない。MVP スコープでは公開関数で十分（KISS）。将来 JWT 検証等が加わった場合に Dependable クラスへリファクタリングする。

## 確定事項（先送り撤廃）

### 確定A: `decision != PENDING` のクエリ（GET /api/gates）

MVP では `GET /api/gates?decision=PENDING` のみ実装（`find_pending_by_reviewer()` を使用）。`decision=APPROVED` 等のリクエストには空リストを返す。Repository Protocol に `find_all_by_decision(reviewer_id, decision)` の追加は YAGNI（単一ユーザー + 少量データ）。将来の実装者が `detailed-design.md §確定A` を見て「MVP では空リストが仕様」と把握できるよう凍結する。

### 確定B: `deliverable_snapshot.body_markdown` / `feedback_text` / `audit_trail[*].comment` の API 返却

**一意確定**: `MaskedText` TypeDecorator は書き込み時に `mask()` を適用し、読み出し時はそのまま返す（`process_result_value` がアンマスク処理を含まない）。よって API 応答値 = DB に保存されている mask() 済み文字列（`<REDACTED:...>` パターンが含まれることがある）。アンマスク済み・秘匿前の文字列を返すという表現は本書で使用禁止。

実装者は該当 Schema フィールドに `# NOTE: DB は MaskedText で保存（書き込み時 mask() 適用済み）。読み出し値をそのまま返す（アンマスクなし）— basic-design.md §確定B 参照` のコメントを添えること（コメント記載義務を確定事項として凍結）。

### 確定C: `GateListResponse.total` は `len(items)` のみ

`GET /api/gates` / `GET /api/tasks/{task_id}/gates` の `total` フィールドは Repository の `count()` を呼ばず `len(items)` を使用する。理由: MVP では `find_pending_by_reviewer()` / `find_by_task_id()` が全件を返すため、別途 COUNT クエリは不要（YAGNI）。将来のページネーション対応時は本書 §確定C を更新してから実装すること。

### 確定D: `GET /api/gates/{id}` は `record_view()` を呼ばない

HTTP GET リクエストは副作用を持つべきでない（RFC 9110 §9.3.1）。`record_view()` による audit_trail 追記は UI 操作（CEO が UI で Gate を開く）のトリガーで呼び出すべきであり、REST GET レスポンスで自動呼び出しすることは避ける。UI sub-feature 実装時に再検討する。

### 確定E: `approve` / `reject` / `cancel` の UoW 境界（改訂）

Router handler が `async with session.begin():` 内で以下をシーケンスで呼ぶ: (1) `ExternalReviewGateService.find_by_id_or_raise()` → (2) `ExternalReviewGateService.approve()` → (3) `ExternalReviewGateService.save()`。`Service.save()` が `ExternalReviewGateRepository.save()` に委譲する（薄委譲）。

**改訂理由（autobegin 問題の解消）**: SQLAlchemy `AsyncSession` は `Session.execute()` 等の初回 DB 操作で暗黙的にトランザクションを開始する（autobegin）。`find_by_id_or_raise()` を `session.begin()` ブロックの外で呼ぶと SELECT 発行時に autobegin が走り、直後の `async with session.begin():` が「既にトランザクション開始済み」例外を返す（HTTP 500）。この問題を回避するため `find_by_id_or_raise()` を `session.begin()` ブロック内に統合した（ヤン・ルカン工程4 PR #114 発見 / 修正）。

**UoW 責務**: Service は `commit()` / `rollback()` を呼ばない。`session.begin()` コンテキストマネージャが正常終了時に自動 commit、例外発生時に自動 rollback する。**依存方向は Router → Service → Repository**（Router が Repository Protocol に直接依存しない）。

### 確定F: `decided_at` の値

`POST /api/gates/{id}/approve` 等の操作時、`decided_at` は **サーバー側 UTC 現在時刻**（`datetime.now(UTC)` / `datetime.utcnow().replace(tzinfo=timezone.utc)`）を使用する。クライアントから送信させない（タイムスタンプ偽造防止）。

## 設計判断の補足

### なぜ `POST /api/gates/{id}/approve` のような動詞 URL か

REST 純粋主義では `PATCH /api/gates/{id}` + Body `{"decision": "APPROVED"}` が理想だが、bakufu の Gate は `decision` を直接 PATCH で書き換えるモデルではなく、domain メソッド（`approve()` / `reject()` / `cancel()`）を呼び出して不変条件を保証しながら遷移するモデルである。エンドポイントを動詞で分けることで「承認操作」「差し戻し操作」「キャンセル操作」の意図をクライアントに明示できる（task の `assign` / `cancel` / `unblock` と同パターン）。

### なぜ `Authorization: Bearer <owner_id>` か

MVP は個人開発者 CEO のシングルユーザー + loopback バインドが前提。JWT / Cognito / Auth0 を導入するコストは MVP 価値に対して過大（YAGNI）。UUIDv4 をトークンとする単純識別は「誰が承認したか」を記録できれば十分であり、外部到達不能環境では安全に機能する。CORS ヘッダーに `Authorization` を事前配線済み（http-api-foundation §A05）なので追加インフラ変更なしで導入できる。

### なぜ `GateListResponse.total = len(items)` か

`find_pending_by_reviewer()` / `find_by_task_id()` は既に全件を返す（LIMIT なし）。MVP での Gate 数は人間 CEO のレビュー数に比例するため最大でも数十件程度。別途 `COUNT(*)` クエリを追加するオーバーヘッドに対して価値がない。PaginatedResponse フォーマットとの型互換性を維持するために `total: int` フィールドは保持する。

## ユーザー向けメッセージの確定文言

### プレフィックス統一

| プレフィックス | 意味 |
|---|---|
| `[FAIL]` | 処理中止を伴う失敗 |
| `[OK]` | 成功完了 |
| `[WARN]` | 警告（処理は継続）|

### MSG 確定文言表

業務ルール R1-G 準拠: 全エラーは「失敗事実（1 行目）+ 次に取るべき行動（2 行目）」の 2 行構造。形式は `[FAIL] <事実>\nNext: <行動>`。

| ID | 出力先 | 文言 |
|---|---|---|
| MSG-ERG-HTTP-001 | HTTP 404 response body | `[FAIL] Gate not found.\nNext: Verify the gate ID and retry, or list available gates via GET /api/gates.` |
| MSG-ERG-HTTP-002 | HTTP 409 response body | `[FAIL] Gate decision is already finalized and cannot be changed.\nNext: To restart the review process, create a new gate for this task via the application layer.` |
| MSG-ERG-HTTP-003 | HTTP 403 response body | `[FAIL] Not authorized to decide on this gate.\nNext: Retry with the Bearer token corresponding to the gate's reviewer_id.` |
| MSG-ERG-HTTP-004 | HTTP 422 response body | `[FAIL] Invalid or missing Authorization header.\nNext: Set the header as: Authorization: Bearer <owner-id> (UUID format).` |

## データ構造（永続化キー）

### `/api/gates` レスポンス（GateListResponse）

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `items` | `array[GateResponse]` | 必須 | Gate 一覧（0 件以上）|
| `total` | `integer` | 必須 | `len(items)`（§確定C 参照）|

### `GateResponse`（一覧要素 / 操作レスポンスの基底）

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `id` | `string` (UUID v4) | 必須 | Gate ID |
| `task_id` | `string` (UUID v4) | 必須 | 紐付く Task ID |
| `stage_id` | `string` (UUID v4) | 必須 | 紐付く Stage ID |
| `reviewer_id` | `string` (UUID v4) | 必須 | レビュー担当者 OwnerId |
| `decision` | `string` | 必須 | `"PENDING"` / `"APPROVED"` / `"REJECTED"` / `"CANCELLED"` |
| `created_at` | `string` (ISO 8601 UTC) | 必須 | Gate 生成時刻 |
| `decided_at` | `string \| null` (ISO 8601 UTC) | 必須 | 決済時刻（PENDING は `null`）|

### `GateDetailResponse`（単件取得 / approve / reject / cancel 応答）

`GateResponse` の全フィールド + 以下を追加:

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `feedback_text` | `string` | 必須 | 判断コメント（PENDING 時は `""`）。DB 値をそのまま返す（§確定B）|
| `deliverable_snapshot` | `DeliverableSnapshotResponse` | 必須 | Gate 生成時の成果物スナップショット |
| `audit_trail` | `array[AuditEntryResponse]` | 必須 | 全閲覧・判断記録（`occurred_at` 昇順）|

### `DeliverableSnapshotResponse`

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `stage_id` | `string` (UUID v4) | 必須 | スナップショット元の Stage ID |
| `body_markdown` | `string` | 必須 | Agent 成果物本文（DB 値そのまま（書き込み時 mask() 済み — §確定B））|
| `committed_by` | `string` (UUID v4) | 必須 | 成果物コミット者 OwnerId |
| `committed_at` | `string` (ISO 8601 UTC) | 必須 | コミット時刻 |
| `attachments` | `array[AttachmentResponse]` | 必須 | 添付ファイルメタデータ（0 件以上）|

### `AuditEntryResponse`

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `actor_id` | `string` (UUID v4) | 必須 | 操作者 OwnerId |
| `action` | `string` | 必須 | `"VIEWED"` / `"APPROVED"` / `"REJECTED"` / `"CANCELLED"` |
| `comment` | `string` | 必須 | 操作コメント（DB 値そのまま（書き込み時 mask() 済み — §確定B））|
| `occurred_at` | `string` (ISO 8601 UTC) | 必須 | 操作時刻 |

## API エンドポイント詳細

### GET /api/gates

| 項目 | 内容 |
|---|---|
| 用途 | PENDING Gate 一覧（reviewer 視点ダッシュボード）|
| 認証 | なし（loopback バインド前提）|
| クエリパラメータ | `reviewer_id: UUID`（必須）/ `decision: str`（省略時 `"PENDING"`）|
| 成功レスポンス | 200 OK + `GateListResponse` |
| 失敗レスポンス | 422 + `{"error": {"code": "validation_error", "message": "..."}}` |
| 副作用 | なし |

### GET /api/tasks/{task_id}/gates

| 項目 | 内容 |
|---|---|
| 用途 | Task の Gate 履歴（複数ラウンド対応、created_at 昇順）|
| 認証 | なし |
| パスパラメータ | `task_id: UUID` |
| 成功レスポンス | 200 OK + `GateListResponse` |
| 失敗レスポンス | 422 + `{"error": {"code": "validation_error", "message": "..."}}` |
| 副作用 | なし |

### GET /api/gates/{id}

| 項目 | 内容 |
|---|---|
| 用途 | Gate 単件詳細取得（deliverable snapshot + audit_trail 含む）|
| 認証 | なし |
| パスパラメータ | `id: UUID` |
| 成功レスポンス | 200 OK + `GateDetailResponse` |
| 失敗レスポンス | 404 `not_found` / 422 `validation_error` |
| 副作用 | なし（§確定D 参照）|

### POST /api/gates/{id}/approve

| 項目 | 内容 |
|---|---|
| 用途 | Gate 承認 |
| 認証 | `Authorization: Bearer <owner-id>` ヘッダー必須 |
| パスパラメータ | `id: UUID` |
| リクエスト Body | `GateApprove`（`comment: str`、省略可）|
| 成功レスポンス | 200 OK + `GateDetailResponse`（decision=APPROVED）|
| 失敗レスポンス | 404 `not_found` / 403 `forbidden` (MSG-ERG-HTTP-003) / 409 `conflict` (MSG-ERG-HTTP-002) / 422 `validation_error` |
| 副作用 | Gate.decision が APPROVED に遷移。`audit_trail` に APPROVED エントリ追加。DB に永続化 |

### POST /api/gates/{id}/reject

| 項目 | 内容 |
|---|---|
| 用途 | Gate 差し戻し |
| 認証 | `Authorization: Bearer <owner-id>` ヘッダー必須 |
| パスパラメータ | `id: UUID` |
| リクエスト Body | `GateReject`（`feedback_text: str`、1 文字以上必須）|
| 成功レスポンス | 200 OK + `GateDetailResponse`（decision=REJECTED）|
| 失敗レスポンス | 404 `not_found` / 403 `forbidden` / 409 `conflict` / 422 `validation_error` |
| 副作用 | Gate.decision が REJECTED に遷移。`audit_trail` に REJECTED エントリ追加。DB に永続化 |

### POST /api/gates/{id}/cancel

| 項目 | 内容 |
|---|---|
| 用途 | Gate キャンセル |
| 認証 | `Authorization: Bearer <owner-id>` ヘッダー必須 |
| パスパラメータ | `id: UUID` |
| リクエスト Body | `GateCancel`（`reason: str`、省略可）|
| 成功レスポンス | 200 OK + `GateDetailResponse`（decision=CANCELLED）|
| 失敗レスポンス | 404 `not_found` / 403 `forbidden` / 409 `conflict` / 422 `validation_error` |
| 副作用 | Gate.decision が CANCELLED に遷移。`audit_trail` に CANCELLED エントリ追加。DB に永続化 |

## 出典・参考

- FastAPI 公式: https://fastapi.tiangolo.com/tutorial/path-params/ （パスパラメータ UUID 型強制）
- FastAPI Depends: https://fastapi.tiangolo.com/tutorial/dependencies/ （get_reviewer_id() Depends パターン）
- RFC 9110 §9.3.1 GET: https://www.rfc-editor.org/rfc/rfc9110#section-9.3.1 （GET の副作用禁止、§確定D 根拠）
- OWASP REST Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html
- http-api-foundation detailed-design.md §確定B（session scope = request）/ §確定E（エラーコード体系）: [`../../http-api-foundation/http-api/detailed-design.md`](../../http-api-foundation/http-api/detailed-design.md)
- task/http-api basic-design.md（動詞 URL / UoW 境界 / 例外分岐パターン): [`../../task/http-api/basic-design.md`](../../task/http-api/basic-design.md)
