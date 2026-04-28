# 要件定義書

> feature: `external-review-gate-repository`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源** / [`docs/features/task-repository/`](../task-repository/) **直近テンプレート** / [`docs/features/external-review-gate/`](../external-review-gate/)

## 機能要件

### REQ-ERGR-001: ExternalReviewGateRepository Protocol 定義

| 項目 | 内容 |
|------|------|
| 入力 | 該当なし（Protocol 定義） |
| 処理 | `application/ports/external_review_gate_repository.py` で `ExternalReviewGateRepository(Protocol)` を定義。**6 method**（empire-repo の基底 3 + §確定 R1-D の 3 method）: `find_by_id(gate_id: GateId) -> ExternalReviewGate \| None` / `count() -> int` / `save(gate: ExternalReviewGate) -> None` / `find_pending_by_reviewer(reviewer_id: OwnerId) -> list[ExternalReviewGate]` / `find_by_task_id(task_id: TaskId) -> list[ExternalReviewGate]` / `count_by_decision(decision: ReviewDecision) -> int`。すべて `async def`、`@runtime_checkable` なし |
| 出力 | Protocol 定義。pyright strict で `SqliteExternalReviewGateRepository` が満たすことを型レベル検証 |
| エラー時 | 該当なし（Protocol は実行時例外を持たない） |

### REQ-ERGR-002: SqliteExternalReviewGateRepository 実装

| 項目 | 内容 |
|------|------|
| 入力 | `AsyncSession`（コンストラクタ引数）、各 method の引数 |
| 処理 | `find_by_id`: `external_review_gates` SELECT → 不在なら None。存在すれば `external_review_gate_attachments` / `external_review_audit_entries` を個別 SELECT（§確定 R1-H ORDER BY 適用）→ `_from_rows()` で ExternalReviewGate 復元。`count`: `SELECT COUNT(*) FROM external_review_gates`。`save`: §確定 R1-B の 5 段階を順次実行。`find_pending_by_reviewer`: `SELECT * FROM external_review_gates WHERE reviewer_id = :reviewer_id AND decision = 'PENDING' ORDER BY created_at DESC, id DESC` → 各行を `find_by_id` 相当の子テーブル取得 → `_from_rows()`。`find_by_task_id`: `SELECT * FROM external_review_gates WHERE task_id = :task_id ORDER BY created_at ASC, id ASC` → 同様。`count_by_decision`: `SELECT COUNT(*) FROM external_review_gates WHERE decision = :decision` |
| 出力 | `find_by_id`: `ExternalReviewGate \| None`、`count`: `int`、`save`: `None`、`find_pending_by_reviewer`: `list[ExternalReviewGate]`（空の場合 `[]`）、`find_by_task_id`: `list[ExternalReviewGate]`（空の場合 `[]`）、`count_by_decision`: `int` |
| エラー時 | SQLAlchemy `IntegrityError`（FK 違反等）/ `OperationalError` を上位伝播。Repository 内で明示的 `commit` / `rollback` はしない |

### REQ-ERGR-003: Alembic 0008 revision

| 項目 | 内容 |
|------|------|
| 入力 | task-repo の 0007 revision（`down_revision="0007_task_aggregate"` で chain 一直線） |
| 処理 | `0008_external_review_gate_aggregate.py` で以下を実行: (a) `external_review_gates` テーブル作成（id PK / task_id FK CASCADE / stage_id / reviewer_id / decision / feedback_text / snapshot スカラ 4 カラム / created_at / decided_at）、(b) `external_review_gate_attachments` テーブル作成（id PK / gate_id FK CASCADE / sha256 / filename / mime_type / size_bytes + UNIQUE(gate_id, sha256)）、(c) `external_review_audit_entries` テーブル作成（id PK / gate_id FK CASCADE / actor_id / action / comment / occurred_at）、(d) INDEX 3 件追加（§確定 R1-K） |
| 出力 | 3 テーブル + INDEX が SQLite に存在する状態 |
| エラー時 | migration 失敗 → `BakufuMigrationError`、Bootstrap stage 3 で Fail Fast |

### REQ-ERGR-004: CI 三層防衛の Gate 拡張（**正/負のチェック併用**）

| 項目 | 内容 |
|------|------|
| 入力 | `scripts/ci/check_masking_columns.sh`（Layer 1）と `backend/tests/architecture/test_masking_columns.py`（Layer 2） |
| 処理 | (a) Layer 1 grep guard: `PARTIAL_MASK_FILES` に 3 エントリ追加（`tables/external_review_gates.py:snapshot_body_markdown:MaskedText` / `tables/external_review_gates.py:feedback_text:MaskedText` / `tables/external_review_audit_entries.py:comment:MaskedText`）。正のチェック（MaskedText 必須）と負のチェック（過剰マスキング防止）を各テーブルで実施。(b) Layer 2 arch test: parametrize に 3 行追加（`external_review_gates.snapshot_body_markdown` / `external_review_gates.feedback_text` / `external_review_audit_entries.comment` の `column.type.__class__ is MaskedText` を assert） |
| 出力 | CI が「3 カラムは MaskedText 必須、その他は masking なし」を物理保証 |
| エラー時 | 後続 PR が誤って masking カラムを `Text` に変更 → Layer 2 arch test で落下、PR ブロック |

### REQ-ERGR-005: storage.md 逆引き表更新

| 項目 | 内容 |
|------|------|
| 入力 | `docs/architecture/domain-model/storage.md` §逆引き表（Task 残カラム行が現時点の最終行） |
| 処理 | §逆引き表に ExternalReviewGate 関連行を追加: (a) `deliverable_snapshot_body_markdown` / `comment` を `（後続）` から **本 PR で配線完了** に更新、(b) ExternalReviewGate 残カラム（masking 非対象）を明示追加 |
| 出力 | storage.md §逆引き表が「ExternalReviewGate 2 masking カラムは本 PR で配線完了、残カラムは masking 対象なし」状態 |
| エラー時 | 該当なし（ドキュメント更新） |

## 画面・CLI 仕様

### CLI レシピ / コマンド

該当なし — 理由: 本 feature は infrastructure 層（Repository 実装）。Admin CLI は `feature/admin-cli` で扱う。

| コマンド | 概要 |
|---------|------|
| 該当なし | — |

### Web UI 画面

該当なし — 理由: UI を持たない。

| 画面ID | 画面名 | 主要操作 |
|-------|-------|---------|
| 該当なし | — | — |

## API 仕様

該当なし — 理由: HTTP API は `feature/http-api` で扱う。本 PR は内部 API（Python module-level の Protocol / Class）のみ提供する。

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| 該当なし | — | — | — | — |

## データモデル

本 Issue で導入する 3 テーブル + INDEX 群。

### `external_review_gates` テーブル

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `external_review_gates` | `id` | `UUIDStr` | PK, NOT NULL | GateId（UUIDv4） |
| `external_review_gates` | `task_id` | `UUIDStr` | **FK → `tasks.id` ON DELETE CASCADE, NOT NULL** | 対象 Task |
| `external_review_gates` | `stage_id` | `UUIDStr` | NOT NULL（**FK なし** — §確定 R1-G: Workflow Aggregate 境界） | EXTERNAL_REVIEW kind の Stage |
| `external_review_gates` | `reviewer_id` | `UUIDStr` | NOT NULL（**FK なし** — Owner Aggregate 未実装、参照のみ） | 人間レビュワー（CEO） |
| `external_review_gates` | `decision` | `String(32)` | NOT NULL（4 値: PENDING / APPROVED / REJECTED / CANCELLED） | 判断結果 |
| `external_review_gates` | `feedback_text` | **`MaskedText`** | NOT NULL（0〜10000 文字、NFC 正規化済み）| 差し戻し理由・承認コメント（CEO 入力経路 → masking 必須） |
| `external_review_gates` | `snapshot_stage_id` | `UUIDStr` | NOT NULL | `deliverable_snapshot.stage_id`（Deliverable VO inline コピー） |
| `external_review_gates` | `snapshot_body_markdown` | **`MaskedText`** | NOT NULL | `deliverable_snapshot.body_markdown`（masking 必須。snapshot 生成時点でマスキング済み本文）|
| `external_review_gates` | `snapshot_committed_by` | `UUIDStr` | NOT NULL | `deliverable_snapshot.committed_by`（AgentId） |
| `external_review_gates` | `snapshot_committed_at` | `DateTime(timezone=True)` | NOT NULL | `deliverable_snapshot.committed_at`（UTC） |
| `external_review_gates` | `created_at` | `DateTime(timezone=True)` | NOT NULL | UTC 起票時刻 |
| `external_review_gates` | `decided_at` | `DateTime(timezone=True)` | NULL（`decision == PENDING` ⇔ NULL） | UTC 判断時刻 |
| INDEX | `(reviewer_id, decision)` | 非 UNIQUE | — | `find_pending_by_reviewer` の WHERE reviewer_id + decision フィルタ最適化 |
| INDEX | `(task_id, created_at)` | 非 UNIQUE | — | `find_by_task_id` の WHERE task_id フィルタ + ORDER BY created_at 最適化 |
| INDEX | `decision` | 非 UNIQUE | — | `count_by_decision` の WHERE decision フィルタ最適化（§確定 R1-K） |

### `external_review_gate_attachments` テーブル

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `external_review_gate_attachments` | `id` | `UUIDStr` | PK, NOT NULL | 内部識別子（save() ごとに uuid4() 再生成。ビジネスキーは UNIQUE(gate_id, sha256)） |
| `external_review_gate_attachments` | `gate_id` | `UUIDStr` | **FK → `external_review_gates.id` ON DELETE CASCADE, NOT NULL** | 親 Gate |
| `external_review_gate_attachments` | `sha256` | `String(64)` | NOT NULL（`^[a-f0-9]{64}$`） | ファイル内容ハッシュ（content-addressable） |
| `external_review_gate_attachments` | `filename` | `String(255)` | NOT NULL | サニタイズ済みファイル名 |
| `external_review_gate_attachments` | `mime_type` | `String(128)` | NOT NULL | MIME 種別（ホワイトリスト 7 種） |
| `external_review_gate_attachments` | `size_bytes` | `Integer` | NOT NULL（0 ≤ x ≤ 10485760） | ファイルサイズ |
| UNIQUE | `(gate_id, sha256)` | — | — | 同一 Gate 内で同 sha256 の重複参照を禁止 |

### `external_review_audit_entries` テーブル

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `external_review_audit_entries` | `id` | `UUIDStr` | PK, NOT NULL | AuditEntry.id（UUIDv4） |
| `external_review_audit_entries` | `gate_id` | `UUIDStr` | **FK → `external_review_gates.id` ON DELETE CASCADE, NOT NULL** | 親 Gate |
| `external_review_audit_entries` | `actor_id` | `UUIDStr` | NOT NULL | 操作者（OwnerId） |
| `external_review_audit_entries` | `action` | `String(32)` | NOT NULL（4 値: VIEWED / APPROVED / REJECTED / CANCELLED） | AuditAction enum |
| `external_review_audit_entries` | `comment` | **`MaskedText`** | NOT NULL（0〜2000 文字、NFC 正規化済み）| 操作コメント（CEO 入力経路 → masking 必須） |
| `external_review_audit_entries` | `occurred_at` | `DateTime(timezone=True)` | NOT NULL | UTC 発生時刻 |

**masking 対象カラム**: `external_review_gates.snapshot_body_markdown` / `external_review_gates.feedback_text` / `external_review_audit_entries.comment`（各 `MaskedText`、3 カラム）。その他カラムは masking 対象なし、CI 三層防衛で「対象なし」を明示登録。

## ユーザー向けメッセージ一覧

該当なし — 理由: Repository は内部 API。ユーザー向けメッセージは application 層 / HTTP API 層が定義する。

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|----|------|----------------|---------|
| 該当なし | — | — | — |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | SQLAlchemy 2.x / Alembic / aiosqlite | pyproject.toml | uv | 既存（M2 永続化基盤）|
| Python 依存 | typing.Protocol | 標準ライブラリ | — | Python 3.12 標準 |
| ドメイン | `ExternalReviewGate` / `GateId` / `ReviewDecision` / `AuditEntry` / `AuditAction` / `Deliverable` / `Attachment` / `OwnerId` / `TaskId` / `StageId` | `domain/external_review_gate/` / `domain/value_objects.py` | 内部 import | 既存（external-review-gate PR #46）|
| インフラ | `Base` / `UUIDStr` / `MaskedText` / `MaskingGateway` | `infrastructure/persistence/sqlite/base.py` / `infrastructure/security/masking.py` | 内部 import | 既存（M2 永続化基盤）|
| インフラ | `AsyncSession` / `async_sessionmaker` | `infrastructure/persistence/sqlite/session.py` | 内部 import | 既存 |
| 外部参照テーブル | `tasks` | Alembic 0007 で先行追加済み（task-repo PR #52 マージ済み） | — | 既存 |
| 外部サービス | 該当なし | — | — | infrastructure 層、外部通信なし |
