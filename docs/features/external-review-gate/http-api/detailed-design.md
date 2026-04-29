# 詳細設計書

> feature: `external-review-gate` / sub-feature: `http-api`
> 親業務仕様: [`../feature-spec.md`](../feature-spec.md)
> 関連: [`basic-design.md`](basic-design.md)

## 本書の役割

本書は階層 3 [`basic-design.md`](basic-design.md) を、実装直前の構造契約・確定文言・API エンドポイント詳細として凍結する。実装 PR は本書を参照し、HTTP 層が Domain の状態を直接変更しないこと、reviewer 境界を application service に閉じること、API response は Issue #61 に従ってマスク解除後の原文を返すことを守る。

## 記述ルール（必ず守ること）

詳細設計に **疑似コード・サンプル実装（言語コードブロック）を書かない**。
ソースコードと二重管理になりメンテナンスコストしか生まない。
必要なのは「構造契約（属性名・型・制約）」と「確定文言（メッセージ文字列）」と「実装の意図（なぜこの API 形になるか）」であり、コードそのものは実装 PR で書く。

## クラス設計（詳細）

```mermaid
classDiagram
    class ExternalReviewGateDecisionRequest {
        +comment: str | None
        +feedback_text: str | None
        +reason: str | None
    }
    class AuthenticatedSubject {
        +owner_id: UUID
    }
    class ExternalReviewGateResponse {
        +id: str
        +task_id: str
        +stage_id: str
        +reviewer_id: str
        +decision: str
        +feedback_text: str
        +deliverable_snapshot: DeliverableSnapshotResponse
        +audit_trail: list~AuditEntryResponse~
        +created_at: str
        +decided_at: str | None
    }
    class ExternalReviewGateService {
        +list_pending(subject) list~ExternalReviewGate~
        +list_by_task(task_id, subject) list~ExternalReviewGate~
        +get_and_record_view(gate_id, subject) ExternalReviewGate
        +approve(gate_id, subject, comment) ExternalReviewGate
        +reject(gate_id, subject, feedback_text) ExternalReviewGate
        +cancel(gate_id, subject, reason) ExternalReviewGate
    }
```

### Aggregate Root: ExternalReviewGate

| 属性 | 型 | 制約 | 意図 |
|---|---|---|---|
| `id` | `GateId` | UUID | API パス識別子 |
| `task_id` | `TaskId` | UUID | Task 履歴 API の検索キー |
| `stage_id` | `StageId` | UUID | 対象 Stage |
| `deliverable_snapshot` | `Deliverable` | Gate 生成後不変 | CEO が判断した成果物本文 |
| `reviewer_id` | `OwnerId` | UUID | 認証済み subject と照合する認可境界 |
| `decision` | `ReviewDecision` | PENDING / APPROVED / REJECTED / CANCELLED | 状態遷移結果 |
| `feedback_text` | `str` | 0〜10000 文字 | approve comment / reject feedback / cancel reason |
| `audit_trail` | `list[AuditEntry]` | 追記のみ | 閲覧・判断の監査証跡 |
| `created_at` | `datetime` | tz-aware | Gate 作成時刻 |
| `decided_at` | `datetime | None` | PENDING は None、終端状態は set | 判断時刻 |

**不変条件**:
- `decision=PENDING` のみ approve / reject / cancel を許可する。
- `record_view` は 4 状態すべてで許可する。
- `deliverable_snapshot` は HTTP API から更新しない。
- `audit_trail` は HTTP API から直接編集しない。

**ふるまい**:
- `approve(by_owner_id, comment, decided_at)`: PENDING → APPROVED。
- `reject(by_owner_id, comment, decided_at)`: PENDING → REJECTED。
- `cancel(by_owner_id, reason, decided_at)`: PENDING → CANCELLED。
- `record_view(by_owner_id, viewed_at)`: decision 不変、VIEWED audit 追記。

### Entity within Aggregate: AuditEntry

| 属性 | 型 | 制約 |
|---|---|---|
| `id` | `UUID` | 一意 |
| `actor_id` | `OwnerId` | reviewer ID |
| `action` | `AuditAction` | VIEWED / APPROVED / REJECTED / CANCELLED |
| `comment` | `str` | 0〜10000 文字 |
| `occurred_at` | `datetime` | tz-aware |

### Value Object: DeliverableSnapshotResponse

| 属性 | 型 |
|---|---|
| `stage_id` | `str` |
| `body_markdown` | `str` |
| `submitted_by` | `str` |
| `submitted_at` | `str` |
| `attachments` | `list[AttachmentResponse]` |

## 確定事項（先送り撤廃）

### 確定 A: 認可境界

HTTP 契約は認証済み subject を唯一の reviewer / actor 根拠にする。`reviewer_id` / `viewer_id` / `actor_id` を query/body で受け取らない。Service は取得済み Gate の `reviewer_id` と `subject.owner_id` が一致しない操作を 403 で拒否する。これは OWASP API1:2023 の BOLA 対策として、パス ID だけで他人の Gate を読ませないためだ。

### 確定 B: `GET /api/gates/{id}` は閲覧記録を保存する

Gate 詳細取得は単なる read ではなく、親仕様 R1-C / R1-E の監査要件を満たすため `record_view` を呼び、保存後の Gate を返す。複数回閲覧は audit_trail に複数 VIEWED として残る。

### 確定 C: reject の `feedback_text` は必須

差し戻しは後続 Agent が修正するための業務情報なので、空文字を 422 で拒否する。approve comment と cancel reason は任意であり、未指定時は空文字を Domain に渡す。

### 確定 D: 既決 Gate の再判断は 409

Domain の `ExternalReviewGateInvariantViolation(kind="decision_already_decided")` は Service で `ExternalReviewGateDecisionConflictError` に変換する。HTTP クライアントから見ると入力形式ではなくリソース状態の競合だからだ。

### 確定 E: HTTP レスポンスはマスク解除後の原文を返す

Issue #61 は「API 層ではマスク解除後の値を返す」と明記しているため、`deliverable_snapshot.body_markdown` / `feedback_text` / `audit_trail[].comment` は認可済み reviewer に原文で返す。Repository の `MaskedText` は DB 保護が目的であり、CEO の判断 UI には原文が必要だ。API 層で再マスクすると同一 API の出力型が二重定義になり、承認 / 却下判断に必要な情報を失う。

### 確定 F: 状態変更 API は Origin / CSRF 境界を通す

`POST /api/gates/{id}/approve|reject|cancel` は既存 `CsrfOriginMiddleware` の対象であり、`Origin` が存在する場合は許可一覧と一致しないリクエストを 403 で拒否する。MVP は Cookie なし bearer / local client 前提のため Origin なしは通す。Cookie セッション導入時は `SameSite=Strict` と CSRF token 必須へ引き上げる。

### 確定 G: 依存 CVE 確認

HTTP API 実装 PR は依存監査を CI またはローカルで実行し、FastAPI / Starlette / Pydantic / SQLAlchemy / httpx / Uvicorn / aiosqlite / python-multipart の既知脆弱性を確認する。2026-04-29 時点の確認対象は `uv.lock` と `pnpm-lock.yaml` で、Python は `pip-audit` または `uv pip audit`、Node は `pnpm audit --audit-level moderate` を使う。検出がある場合は CVE / GHSA ID、影響範囲、MVP ブロック可否、修正バージョンを PR に記録する。

## 設計判断の補足

### なぜ decision を query で自由検索にしないか

Issue #61 の dashboard 要件は PENDING 一覧であり、Repository も `find_pending_by_reviewer` を持つ。APPROVED / REJECTED / CANCELLED の横断検索は MVP 最短路では不要なので、YAGNI として `decision=PENDING` のみ許可する。

### なぜ Task 履歴 API は reviewer_id でフィルタするか

`GET /api/tasks/{task_id}/gates` は複数ラウンドを見せるために必要だが、Task ID を知るだけで他 reviewer の snapshot を読めると BOLA になる。現時点では reviewer が自分の Gate 履歴だけ読む契約に絞る。

## ユーザー向けメッセージの確定文言

### プレフィックス統一

| プレフィックス | 意味 |
|---|---|
| `[FAIL]` | HTTP body には露出しない。domain 由来文言の前処理対象 |
| `[OK]` | 該当なし |
| `[SKIP]` | 該当なし |
| `[WARN]` | 該当なし |
| `[INFO]` | 該当なし |

### MSG 確定文言表

| ID | 出力先 | 文言（必要なら 2 行構造） |
|---|---|---|
| MSG-ERG-HTTP-001 | HTTP JSON | `External review gate not found.`<br>`Next: Verify the gate id and reload the pending review list.` |
| MSG-ERG-HTTP-002 | HTTP JSON | `Reviewer is not authorized for this gate.`<br>`Next: Sign in as the assigned reviewer or request reassignment before reviewing this gate.` |
| MSG-ERG-HTTP-003 | HTTP JSON | `External review gate has already been decided.`<br>`Next: Open the latest gate round; decided gates cannot be approved, rejected, or cancelled again.` |
| MSG-ERG-HTTP-004 | HTTP JSON | `Request validation failed: <detail>`<br>`Next: Correct the request path, query, or body and retry.` |

## データ構造（永続化キー）

### `external_review_gates` テーブル

| カラム | 型 | 制約 | 意図 |
|---|---|---|---|
| `id` | string | PK, NOT NULL | Gate 識別子 |
| `task_id` | string | NOT NULL, indexed | Task 履歴検索 |
| `stage_id` | string | NOT NULL | Stage 識別子 |
| `reviewer_id` | string | NOT NULL, indexed | reviewer dashboard / 認可境界 |
| `decision` | string | NOT NULL, indexed | PENDING 一覧 / 状態 |
| `snapshot_body_markdown` | MaskedText | NOT NULL | 成果物本文 |
| `feedback_text` | MaskedText | NOT NULL | 判断コメント |
| `created_at` | datetime | NOT NULL | 並び順 |
| `decided_at` | datetime | nullable | 判断時刻 |

### `/api/gates` リクエスト / レスポンス

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `decision` | string query | no | MVP は `PENDING` のみ |
| `items` | list | response | Gate response 配列 |
| `total` | int | response | `len(items)` と等価 |

## API エンドポイント詳細

### GET /api/gates

| 項目 | 内容 |
|---|---|
| 用途 | reviewer の PENDING Gate 一覧 |
| 認証 | 認証済み subject を使用。query/body の reviewer 自己申告は受理しない |
| リクエスト Body | なし |
| 成功レスポンス | 200 OK + `ExternalReviewGateListResponse` |
| 失敗レスポンス | 422 + `ErrorResponse` |
| 副作用 | なし |

### GET /api/tasks/{task_id}/gates

| 項目 | 内容 |
|---|---|
| 用途 | Task の Gate 履歴（複数ラウンド） |
| 認証 | 認証済み subject で自分の Gate のみ返す |
| リクエスト Body | なし |
| 成功レスポンス | 200 OK + `ExternalReviewGateListResponse` |
| 失敗レスポンス | 422 + `ErrorResponse` |
| 副作用 | なし |

### GET /api/gates/{id}

| 項目 | 内容 |
|---|---|
| 用途 | Gate 単件取得、閲覧監査記録 |
| 認証 | 認証済み subject と `gate.reviewer_id` を照合 |
| リクエスト Body | なし |
| 成功レスポンス | 200 OK + `ExternalReviewGateResponse` |
| 失敗レスポンス | 404 / 403 / 422 + `ErrorResponse` |
| 副作用 | `AuditEntry(action=VIEWED)` 追記、Gate 保存 |

### POST /api/gates/{id}/approve

| 項目 | 内容 |
|---|---|
| 用途 | 外部レビュー承認 |
| 認証 | 認証済み subject と `gate.reviewer_id` を照合 |
| リクエスト Body | `ApproveGateRequest(comment?)` |
| 成功レスポンス | 200 OK + `ExternalReviewGateResponse(decision=APPROVED)` |
| 失敗レスポンス | 404 / 403 / 409 / 422 + `ErrorResponse` |
| 副作用 | `AuditEntry(action=APPROVED)` 追記、Gate 保存 |

### POST /api/gates/{id}/reject

| 項目 | 内容 |
|---|---|
| 用途 | 外部レビュー差し戻し |
| 認証 | 認証済み subject と `gate.reviewer_id` を照合 |
| リクエスト Body | `RejectGateRequest(feedback_text)` |
| 成功レスポンス | 200 OK + `ExternalReviewGateResponse(decision=REJECTED)` |
| 失敗レスポンス | 404 / 403 / 409 / 422 + `ErrorResponse` |
| 副作用 | `AuditEntry(action=REJECTED)` 追記、Gate 保存 |

### POST /api/gates/{id}/cancel

| 項目 | 内容 |
|---|---|
| 用途 | 外部レビュー取消 |
| 認証 | 認証済み subject と `gate.reviewer_id` を照合 |
| リクエスト Body | `CancelGateRequest(reason?)` |
| 成功レスポンス | 200 OK + `ExternalReviewGateResponse(decision=CANCELLED)` |
| 失敗レスポンス | 404 / 403 / 409 / 422 + `ErrorResponse` |
| 副作用 | `AuditEntry(action=CANCELLED)` 追記、Gate 保存 |

## 出典・参考

- FastAPI response model: https://fastapi.tiangolo.com/tutorial/response-model/
- FastAPI path parameters: https://fastapi.tiangolo.com/tutorial/path-params/
- Pydantic field serializers: https://docs.pydantic.dev/latest/concepts/serialization/#field-serializers
- OWASP API1:2023 Broken Object Level Authorization: https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/
- OWASP API3:2023 Broken Object Property Level Authorization: https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/
- OWASP Cross-Site Request Forgery Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- GitHub Advisory Database: https://github.com/advisories
- OSV vulnerability database: https://osv.dev/
