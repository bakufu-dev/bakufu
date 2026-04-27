# 要件定義書

> feature: `external-review-gate`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/architecture/domain-model/aggregates.md`](../../architecture/domain-model/aggregates.md) §ExternalReviewGate / [`storage.md`](../../architecture/domain-model/storage.md) §snapshot 凍結方式 / [`docs/features/task/`](../task/) （PR #42 §確定 A-2 連携先）

## 機能要件

### REQ-GT-001: ExternalReviewGate 構築

| 項目 | 内容 |
|------|------|
| 入力 | `id: GateId` / `task_id: TaskId` / `stage_id: StageId` / `deliverable_snapshot: Deliverable` / `reviewer_id: OwnerId` / `decision: ReviewDecision`（既定 PENDING）/ `feedback_text: str`（既定 '', 0〜10000 文字）/ `audit_trail: list[AuditEntry]`（既定 []）/ `created_at: datetime`（UTC、tz-aware）/ `decided_at: datetime \| None`（既定 None）|
| 処理 | Pydantic 型バリデーション → `model_validator(mode='after')` で不変条件検査（5 種：`_validate_decided_at_consistency` / `_validate_feedback_text_range` / `_validate_audit_trail_append_only`（構築時は always pass）/ `_validate_snapshot_immutable`（構築時は always pass）/ `_validate_decision_immutable`（構築時は always pass））|
| 出力 | valid な `ExternalReviewGate` インスタンス（frozen） |
| エラー時 | `ExternalReviewGateInvariantViolation` を raise。`kind` は `decided_at_inconsistent` / `feedback_text_range` のいずれか（構築時に発動するもの）。型違反は `pydantic.ValidationError` |

### REQ-GT-002: approve

| 項目 | 内容 |
|------|------|
| 入力 | `by_owner_id: OwnerId` / `comment: str`（0〜10000 文字、NFC 正規化のみ・strip しない）/ `decided_at: datetime`（UTC）|
| 処理 | (1) `state_machine.lookup(self.decision, 'approve')` → PENDING のときのみ APPROVED 遷移を許可、他は `decision_already_decided` raise → (2) `feedback_text` を NFC 正規化 → range 検査 → (3) `audit_trail` に AuditEntry(actor_id=by_owner_id, action=APPROVED, comment=comment, occurred_at=decided_at) を append → (4) `_rebuild_with_state(decision=APPROVED, feedback_text=normalized_comment, audit_trail=updated_trail, decided_at=decided_at)` |
| 出力 | 新 Gate（pre-validate 方式、元 Gate は不変）|
| エラー時 | `ExternalReviewGateInvariantViolation(kind='decision_already_decided' / 'feedback_text_range')` |

### REQ-GT-003: reject

| 項目 | 内容 |
|------|------|
| 入力 | `by_owner_id: OwnerId` / `comment: str` / `decided_at: datetime` |
| 処理 | (1) `state_machine.lookup(self.decision, 'reject')` → PENDING のときのみ REJECTED 遷移を許可 → (2) feedback_text 正規化 + range 検査 → (3) audit_trail に REJECTED エントリ追加 → (4) `_rebuild_with_state(decision=REJECTED, feedback_text=normalized_comment, audit_trail=updated_trail, decided_at=decided_at)` |
| 出力 | 新 Gate |
| エラー時 | `ExternalReviewGateInvariantViolation(kind='decision_already_decided' / 'feedback_text_range')` |

### REQ-GT-004: cancel

| 項目 | 内容 |
|------|------|
| 入力 | `by_owner_id: OwnerId` / `reason: str`（0〜10000 文字）/ `decided_at: datetime` |
| 処理 | (1) `state_machine.lookup(self.decision, 'cancel')` → PENDING のときのみ CANCELLED 遷移を許可 → (2) reason 正規化 + range 検査 → (3) audit_trail に CANCELLED エントリ追加 → (4) `_rebuild_with_state(decision=CANCELLED, feedback_text=normalized_reason, audit_trail=updated_trail, decided_at=decided_at)` |
| 出力 | 新 Gate |
| エラー時 | `ExternalReviewGateInvariantViolation(kind='decision_already_decided' / 'feedback_text_range')` |

### REQ-GT-005: record_view（4 状態すべてで許可、§確定 R1-C 冪等性なし）

| 項目 | 内容 |
|------|------|
| 入力 | `by_owner_id: OwnerId` / `viewed_at: datetime` |
| 処理 | (1) `state_machine.lookup(self.decision, 'record_view')` → 4 状態すべてで自己遷移を許可 → (2) audit_trail に AuditEntry(actor_id=by_owner_id, action=VIEWED, comment='', occurred_at=viewed_at) を append → (3) `_rebuild_with_state(audit_trail=updated_trail)`（**`decision` / `decided_at` / `feedback_text` は不変**）|
| 出力 | 新 Gate（同 owner 複数回呼び出しで複数エントリ、§確定 R1-C 冪等性なし）|
| エラー時 | 該当なし（4 状態すべて許可、record_view は terminal でも可能）|

### REQ-GT-006: 不変条件検査（5 種）

| 項目 | 内容 |
|------|------|
| 入力 | Gate の現状属性 |
| 処理 | `_validate_decided_at_consistency`（PENDING ⇔ decided_at is None、他 ⇔ decided_at 非 None）/ `_validate_feedback_text_range`（NFC 後 0〜10000 文字）/ `_validate_audit_trail_append_only`（既存エントリ改変禁止、新規 append のみ）/ `_validate_snapshot_immutable`（コンストラクタ後の `deliverable_snapshot` 改変禁止）/ `_validate_decision_immutable`（PENDING → 1 回のみ遷移、再遷移禁止）を順次実行 |
| 出力 | 違反なしなら return、違反時は `ExternalReviewGateInvariantViolation` を raise |
| エラー時 | `ExternalReviewGateInvariantViolation` 単一例外、`kind` で違反種別識別 |

## 画面・CLI 仕様

### CLI レシピ / コマンド

該当なし — 理由: domain 層のみ。Admin CLI は `feature/admin-cli`（後続）で扱う（`bakufu admin gate show <gate_id>` で audit_trail 表示等）。

| コマンド | 概要 |
|---------|------|
| 該当なし | — |

### Web UI 画面

該当なし — 理由: UI は `feature/external-review-gate-ui`（後続）で扱う。

| 画面ID | 画面名 | 主要操作 |
|-------|-------|---------|
| 該当なし | — | — |

## API 仕様

該当なし — 理由: API は `feature/http-api` で扱う。本 feature は domain 層のみ。

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| 該当なし | — | — | — | — |

## データモデル

`docs/architecture/domain-model/aggregates.md` §ExternalReviewGate および `value-objects.md` §AuditEntry の凍結済み定義に従う。本 feature では新規 VO として `AuditEntry` を実体化、`ReviewDecision` / `AuditAction` enum を追加する（`Deliverable` は task PR #42 で実体化済み）。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| ExternalReviewGate | `id` | `GateId` | 不変、UUIDv4 | Aggregate Root |
| ExternalReviewGate | `task_id` | `TaskId` | UUIDv4。既存 Task を指す（参照整合性は application 層）| Task への参照 |
| ExternalReviewGate | `stage_id` | `StageId` | UUIDv4。EXTERNAL_REVIEW kind の Stage を指す（同上）| Stage への参照 |
| ExternalReviewGate | `deliverable_snapshot` | `Deliverable` | task PR #42 で実体化済み VO、Gate 生成時に inline コピー、以後不変 | Deliverable VO |
| ExternalReviewGate | `reviewer_id` | `OwnerId` | UUIDv4。既定 CEO | Owner への参照 |
| ExternalReviewGate | `decision` | `ReviewDecision` | enum 4 値（PENDING / APPROVED / REJECTED / CANCELLED）| — |
| ExternalReviewGate | `feedback_text` | `str` | 0〜10000 文字（NFC 正規化のみ、strip しない）| — |
| ExternalReviewGate | `audit_trail` | `list[AuditEntry]` | 0 件以上、append-only、順序保持 | AuditEntry VO 群 |
| ExternalReviewGate | `created_at` | `datetime` | UTC、tz-aware | — |
| ExternalReviewGate | `decided_at` | `datetime \| None` | UTC、tz-aware or None。`decision == PENDING` ⇔ None | — |
| AuditEntry | `id` | `UUID` | UUIDv4 | — |
| AuditEntry | `actor_id` | `OwnerId` | UUIDv4 | Owner への参照 |
| AuditEntry | `action` | `AuditAction` | enum（VIEWED / APPROVED / REJECTED / CANCELLED 等）| — |
| AuditEntry | `comment` | `str` | 0〜2000 文字（NFC 正規化のみ、strip しない）| — |
| AuditEntry | `occurred_at` | `datetime` | UTC、tz-aware | — |

## ユーザー向けメッセージ一覧

全 MSG は **2 行構造**を採用する（§確定 R1-G、room §確定 I 踏襲）:

- 1 行目: `[FAIL] <failure summary>`
- 2 行目: `Next: <action>`

「Next:」必須は test-design.md の TC-UT-GT-NNN で `assert "Next:" in str(exc)` により CI 物理保証する。

| ID | 種別 | 例外型 | kind | 表示条件 |
|----|------|------|------|---------|
| MSG-GT-001 | エラー | `ExternalReviewGateInvariantViolation` | `decision_already_decided` | PENDING 以外の Gate に approve / reject / cancel を呼び出し |
| MSG-GT-002 | エラー | `ExternalReviewGateInvariantViolation` | `decided_at_inconsistent` | `decision == PENDING` で `decided_at != None`、または `decision != PENDING` で `decided_at is None` |
| MSG-GT-003 | エラー | `ExternalReviewGateInvariantViolation` | `snapshot_immutable` | コンストラクタ後の `deliverable_snapshot` 改変試行 |
| MSG-GT-004 | エラー | `ExternalReviewGateInvariantViolation` | `feedback_text_range` | `feedback_text` の NFC 後 length が 10001 以上 |
| MSG-GT-005 | エラー | `ExternalReviewGateInvariantViolation` | `audit_trail_append_only` | `audit_trail` の既存エントリ改変、または prepend |
| MSG-GT-006 | エラー | `pydantic.ValidationError` | — | 型違反（None 渡し / tz-naive datetime / 不正 UUID / enum 範囲外 等）|
| MSG-GT-007 | エラー | `GateNotFoundError` | — | application 層 `GateService` で gate_id の Gate が存在しない |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | Pydantic v2.x | pyproject.toml（既存）| uv | 既存 |
| Python 依存 | unicodedata（標準ライブラリ）| — | — | NFC 正規化 |
| Python 依存 | enum.StrEnum（標準ライブラリ）| — | — | ReviewDecision / AuditAction |
| ドメイン | `GateId` / `TaskId` / `StageId` / `OwnerId` / `Deliverable` / `ReviewDecision` / `AuditAction` | `domain/value_objects.py` / `domain/task/` | 内部 import | 既存（task #37 で `Deliverable` 実体化、`ReviewDecision` / `AuditAction` enum は本 PR で Python 実体化）|
| ドメイン | `mask_discord_webhook` / `mask_discord_webhook_in` | `domain/exceptions.py`（6 兄弟と共有）| 内部 import | 既存 |
| 外部サービス | 該当なし | — | — | domain 層、外部通信なし |
