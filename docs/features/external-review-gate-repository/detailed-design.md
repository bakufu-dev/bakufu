# 詳細設計書

> feature: `external-review-gate-repository`
> 関連: [basic-design.md](basic-design.md) / [`docs/features/empire-repository/detailed-design.md`](../empire-repository/detailed-design.md) **テンプレート真実源** / [`docs/features/task-repository/detailed-design.md`](../task-repository/detailed-design.md) **直近テンプレート** / [`docs/features/external-review-gate/detailed-design.md`](../external-review-gate/detailed-design.md)

## 記述ルール（必ず守ること）

詳細設計に**疑似コード・サンプル実装（python/ts/sh/yaml 等の言語コードブロック）を書かない**。
ソースコードと二重管理になりメンテナンスコストしか生まない。
必要なのは「構造契約（属性名・型・制約）」と「確定文言（メッセージ文言）」と「実装の意図」。

## クラス設計（詳細）

### `ExternalReviewGateRepository` Protocol

| method | シグネチャ | 戻り値 | 制約 |
|--------|---------|-------|------|
| `find_by_id` | `(gate_id: GateId) -> ExternalReviewGate \| None` | `ExternalReviewGate`（存在時）/ `None`（不在時） | async def |
| `count` | `() -> int` | `int`（全件数） | async def |
| `save` | `(gate: ExternalReviewGate) -> None` | `None` | async def、§確定 R1-B 5 段階実行 |
| `find_pending_by_reviewer` | `(reviewer_id: OwnerId) -> list[ExternalReviewGate]` | `list[ExternalReviewGate]`（空の場合 `[]`）| async def、ORDER BY created_at DESC, id DESC |
| `find_by_task_id` | `(task_id: TaskId) -> list[ExternalReviewGate]` | `list[ExternalReviewGate]`（空の場合 `[]`）| async def、ORDER BY created_at ASC, id ASC |
| `count_by_decision` | `(decision: ReviewDecision) -> int` | `int`（decision 別件数）| async def |

### `SqliteExternalReviewGateRepository`

| 属性 | 型 | 意図 |
|-----|----|-----|
| `_session` | `AsyncSession` | コンストラクタ引数（依存性注入） |

| method | シグネチャ | 戻り値 | 処理の要点 |
|--------|---------|-------|-----------|
| `find_by_id` | `(gate_id: GateId) -> ExternalReviewGate \| None` | `ExternalReviewGate \| None` | `external_review_gates` 1 行 SELECT → 不在は None。存在すれば 2 子テーブルを個別 SELECT（§確定 R1-H ORDER BY 適用）→ `_from_rows()` |
| `count` | `() -> int` | `int` | `select(func.count()).select_from(ExternalReviewGateRow)` |
| `save` | `(gate: ExternalReviewGate) -> None` | `None` | `_to_rows()` → §確定 R1-B 5 段階 DELETE+UPSERT+INSERT |
| `find_pending_by_reviewer` | `(reviewer_id: OwnerId) -> list[ExternalReviewGate]` | `list[ExternalReviewGate]` | `SELECT * FROM external_review_gates WHERE reviewer_id = :id AND decision = 'PENDING' ORDER BY created_at DESC, id DESC` → 各行で `find_by_id` 相当の子テーブル取得 → `_from_rows()` |
| `find_by_task_id` | `(task_id: TaskId) -> list[ExternalReviewGate]` | `list[ExternalReviewGate]` | `SELECT * FROM external_review_gates WHERE task_id = :id ORDER BY created_at ASC, id ASC` → 各行で同様に子テーブル取得 → `_from_rows()` |
| `count_by_decision` | `(decision: ReviewDecision) -> int` | `int` | `SELECT COUNT(*) FROM external_review_gates WHERE decision = :decision`（SQLAlchemy `func.count()` 経由） |
| `_to_rows` | `(gate: ExternalReviewGate) -> tuple[GateRow, list[AttachRow], list[AuditRow]]` | 3 種 Row の tuple | TypeDecorator 信頼（UUIDStr/MaskedText 二重変換しない、§確定 R1-A 詳細）。`snapshot` スカラは Gate row の各カラムに展開、`snapshot.attachments` は AttachRow リスト、`audit_trail` は AuditRow リスト |
| `_from_rows` | `(gate_row, attach_rows, audit_rows) -> ExternalReviewGate` | `ExternalReviewGate` | TypeDecorator 信頼。`snapshot` は Gate row のスカラカラム + `attach_rows` から `Deliverable(stage_id=..., body_markdown=..., attachments=[...], ...)` として復元 |

## 確定事項（先送り撤廃）

### §確定 R1-A: TypeDecorator 信頼の徹底（task-repository §確定 R1-A 踏襲）

`UUIDStr` TypeDecorator は SELECT 時に変換済みの値を返す。`_from_rows()` 内で二重ラップしない。

`MaskedText` TypeDecorator は INSERT 時に `process_bind_param` でマスキング済み値を bind parameter に渡す。`_to_rows()` 内で `MaskingGateway.mask()` を手動呼び出しせず、TypeDecorator に委ねる（責務の重複排除）。

### §確定 R1-B: save() 5 段階の順序と SQLite FK 整合性

§確定 R1-B（requirements-analysis.md）で定義した 5 段階を詳細凍結する:

| 段階 | SQL 操作 | 対象 | 留意点 |
|------|---------|------|-------|
| 1 | `DELETE FROM external_review_gate_attachments WHERE gate_id = :id` | gate_attachments | FK CASCADE 先がない。直接 DELETE。新規 Gate では 0 件（問題なし） |
| 2 | `DELETE FROM external_review_audit_entries WHERE gate_id = :id` | audit_entries | 同上 |
| 3 | `INSERT ... ON CONFLICT (id) DO UPDATE SET ...` | external_review_gates（UPSERT） | SQLAlchemy `sqlite_insert(...).on_conflict_do_update(...)` で既存行を UPDATE。新規・更新両対応 |
| 4 | `INSERT INTO external_review_gate_attachments ...` | 各 Attachment（snapshot.attachments）| gate_id FK が段階 3 で確定済み。`UNIQUE(gate_id, sha256)` は段階 1 の DELETE でクリア済み |
| 5 | `INSERT INTO external_review_audit_entries ...` | 各 AuditEntry（audit_trail）| gate_id FK が段階 3 で確定済み |

**段階 3 の UPSERT を DELETE 前に行わない理由**: UPSERT（ON CONFLICT DO UPDATE）は既存行を IN-PLACE 更新するため gate 行そのものは残る。しかし段階 4〜5 の INSERT で UNIQUE 制約衝突が発生しないよう、段階 1〜2 で子テーブルを先にクリアしてから UPSERT する正しい順序を守る。

### §確定 R1-C: `_from_rows` の子構造再組み立て

Gate Aggregate 復元時の `_from_rows()` 処理の確定ルール:

| 子構造 | 再組み立て方法 | 根拠 |
|-------|-------------|------|
| `deliverable_snapshot: Deliverable` | gate_row のスカラカラム（snapshot_stage_id / snapshot_body_markdown / snapshot_committed_by / snapshot_committed_at）+ `attach_rows` から `Attachment` リストを構築して `Deliverable(...)` を生成 | Deliverable VO は stage_id / body_markdown / attachments / committed_by / committed_at の 5 属性 |
| `audit_trail: list[AuditEntry]` | `audit_rows` を `occurred_at ASC, id ASC` でソート済みで受け取り、`[AuditEntry(id=..., actor_id=..., action=AuditAction(r.action), comment=r.comment, occurred_at=r.occurred_at) for r in audit_rows]` | §確定 R1-H の ORDER BY 保証でリスト順序が Domain の append-only 不変条件に準拠 |

### §確定 R1-E: CI 三層防衛の詳細実装仕様

#### Layer 1: `check_masking_columns.sh` 追加エントリ

`PARTIAL_MASK_FILES` 配列に以下を追加（正のチェック: MaskedText 必須）:

| エントリ | チェック対象 |
|---------|------------|
| `"tables/external_review_gates.py:snapshot_body_markdown:MaskedText"` | `external_review_gates.snapshot_body_markdown` の `MaskedText` 必須 |
| `"tables/external_review_audit_entries.py:comment:MaskedText"` | `external_review_audit_entries.comment` の `MaskedText` 必須 |

負のチェック（過剰マスキング防止）: 各テーブルファイルで上記以外のカラムに `MaskedText` / `MaskedJSONEncoded` が登場しないことも assert する（task-repository §確定 R1-E パターン継承）。

#### Layer 2: `test_masking_columns.py` 追加 parametrize

```
parametrize に追加する 2 行:
  ("external_review_gates", "snapshot_body_markdown", MaskedText)
  ("external_review_audit_entries", "comment", MaskedText)
```

各パラメータについて `column.type.__class__ is MaskedText` を assert する。

#### Layer 3: storage.md 逆引き表（REQ-ERGR-005 で実施済み）

`docs/architecture/domain-model/storage.md` §逆引き表の更新は REQ-ERGR-005 で実施済み（本 PR 設計書と同一コミット）。

### §確定 R1-K: INDEX 設計の根拠

| INDEX | 対象カラム | 種別 | 根拠 |
|------|-----------|------|------|
| `ix_external_review_gates_task_id_created` | `(external_review_gates.task_id, created_at)` | 非 UNIQUE | `find_by_task_id` の WHERE task_id フィルタ + ORDER BY created_at を一括最適化。task_id 単体 INDEX では ORDER BY ソートが追加コストになるため複合 INDEX で解決 |
| `ix_external_review_gates_reviewer_decision` | `(external_review_gates.reviewer_id, decision)` | 非 UNIQUE | `find_pending_by_reviewer` の WHERE reviewer_id + decision フィルタ最適化（PENDING 絞り込みが主なユースケース）。decision 単体 INDEX では reviewer フィルタに効かない |
| `ix_external_review_gates_decision` | `external_review_gates.decision` | 非 UNIQUE | `count_by_decision` の WHERE decision フィルタ最適化（`ix_external_review_gates_reviewer_decision` の prefix では COUNT(*) 全体には効かない場合があるため単体 INDEX も追加） |

**INDEX を張らない判断（YAGNI）**:
- `external_review_gates.id` 単体: PK のため自動 INDEX 済み
- `external_review_gate_attachments.gate_id`: `find_by_id` 内の子テーブル SELECT で 1 gate_id による 1 クエリ。MVP スケールでは不要
- `external_review_audit_entries.gate_id`: 同上

## データ構造（永続化キー）

### `external_review_gates` テーブル

| カラム | 型 | 制約 | 意図 |
|-------|----|----|-----|
| `id` | `UUIDStr` | PK, NOT NULL | GateId（UUIDv4） |
| `task_id` | `UUIDStr` | **FK → `tasks.id` ON DELETE CASCADE, NOT NULL** | 対象 Task（Gate は Task の寿命に従う） |
| `stage_id` | `UUIDStr` | NOT NULL（**FK なし** — Workflow Aggregate 境界、§確定 R1-G）| EXTERNAL_REVIEW kind の Stage |
| `reviewer_id` | `UUIDStr` | NOT NULL（**FK なし** — Owner Aggregate 未実装、§確定 R1-G）| 人間レビュワー（CEO） |
| `decision` | `String(32)` | NOT NULL | ReviewDecision 4 値（PENDING / APPROVED / REJECTED / CANCELLED） |
| `feedback_text` | `Text` | NOT NULL | 差し戻し理由・承認コメント（0〜10000 文字 NFC 正規化済み。masking は Issue #36 仕様で 2 カラムに限定、§確定 R1-E 補足参照） |
| `snapshot_stage_id` | `UUIDStr` | NOT NULL | `deliverable_snapshot.stage_id`（Deliverable VO inline コピー） |
| `snapshot_body_markdown` | **`MaskedText`** | NOT NULL | `deliverable_snapshot.body_markdown`（masking 必須。Agent 出力 / secret 混入経路） |
| `snapshot_committed_by` | `UUIDStr` | NOT NULL | `deliverable_snapshot.committed_by`（AgentId、FK なし — Aggregate 境界） |
| `snapshot_committed_at` | `DateTime(timezone=True)` | NOT NULL | `deliverable_snapshot.committed_at`（UTC） |
| `created_at` | `DateTime(timezone=True)` | NOT NULL | UTC 起票時刻 |
| `decided_at` | `DateTime(timezone=True)` | NULL（`decision == PENDING` ⇔ NULL）| UTC 判断時刻 |

**masking 対象カラム**: `snapshot_body_markdown`（MaskedText）。その他 11 カラムは masking 対象なし。

### `external_review_gate_attachments` テーブル

| カラム | 型 | 制約 | 意図 |
|-------|----|----|-----|
| `id` | `UUIDStr` | PK, NOT NULL | **内部識別子。save() ごとに uuid4() で再生成（DELETE-then-INSERT パターン）。外部参照禁止。ビジネスキーは UNIQUE(gate_id, sha256)** |
| `gate_id` | `UUIDStr` | **FK → `external_review_gates.id` ON DELETE CASCADE, NOT NULL** | 親 Gate |
| `sha256` | `String(64)` | NOT NULL（`^[a-f0-9]{64}$`）| ファイル内容ハッシュ（content-addressable、物理ファイルは Gate と Deliverable が共有参照） |
| `filename` | `String(255)` | NOT NULL | サニタイズ済みファイル名（storage.md §filename サニタイズ規則準拠） |
| `mime_type` | `String(128)` | NOT NULL | MIME 種別（ホワイトリスト 7 種、Attachment VO で検証済み） |
| `size_bytes` | `Integer` | NOT NULL（0 ≤ x ≤ 10485760）| ファイルサイズ |
| UNIQUE | `(gate_id, sha256)` | — | 同一 Gate 内で同 sha256 の重複添付参照を禁止 |

**masking 対象カラム**: なし（全カラム masking 対象外）。

### `external_review_audit_entries` テーブル

| カラム | 型 | 制約 | 意図 |
|-------|----|----|-----|
| `id` | `UUIDStr` | PK, NOT NULL | AuditEntry.id（UUIDv4）。Domain の AuditEntry が保持する UUID をそのまま保存 |
| `gate_id` | `UUIDStr` | **FK → `external_review_gates.id` ON DELETE CASCADE, NOT NULL** | 親 Gate |
| `actor_id` | `UUIDStr` | NOT NULL | 操作者（OwnerId、FK なし — Owner Aggregate 未実装） |
| `action` | `String(32)` | NOT NULL | AuditAction 4 値（VIEWED / APPROVED / REJECTED / CANCELLED） |
| `comment` | **`MaskedText`** | NOT NULL | 操作コメント（0〜2000 文字 NFC 正規化済み。CEO 入力経路 → masking 必須） |
| `occurred_at` | `DateTime(timezone=True)` | NOT NULL | UTC 発生時刻 |

**masking 対象カラム**: `comment`（MaskedText）。その他 5 カラムは masking 対象なし。

### `0008_external_review_gate_aggregate.py`（Alembic revision 構造）

| 操作 | 内容 |
|---|---|
| `upgrade()` — external_review_gates | `op.create_table('external_review_gates', ...)` + INDEX 3 件（§確定 R1-K） |
| `upgrade()` — 子テーブル | `op.create_table('external_review_gate_attachments', ...)` / `op.create_table('external_review_audit_entries', ...)` |
| `downgrade()` | 子テーブル 2 本 drop → external_review_gates drop（CASCADE FK により子が先に消える逆順）|
| `revision` | `"0008_external_review_gate_aggregate"` |
| `down_revision` | `"0007_task_aggregate"` |

## API エンドポイント詳細

該当なし — 理由: 本 feature は infrastructure 層のみ。HTTP API は `feature/http-api` で凍結する。

## §Known Issues

### §設計決定 ERGR-001: `external_review_gates.reviewer_id` / `snapshot_committed_by` は Aggregate 境界として永続的に FK 張らない

| 項目 | 内容 |
|---|---|
| 状態 | **RESOLVED（設計決定として凍結）** |
| 内容 | `reviewer_id` は Owner Aggregate（M2 未実装）への参照。`snapshot_committed_by` は Agent Aggregate への参照。両カラムは FK を張らず UUIDStr として保持 |
| 根拠 | Owner Aggregate が M2 スコープ外（MVP では CEO = システム唯一オーナーとして UUID 固定運用）。`snapshot_committed_by` は Agent 削除時の CASCADE 危険性（task-repository §設計決定 TR-001 と同論理）。参照整合性は application 層 `GateService.create()` が `OwnerRepository.find_by_id` / `AgentRepository.find_by_id` で保証 |
| 閉鎖 | FK closure 申し送りなし。この設計決定は **変更しない**（Owner Aggregate 実装時も同方針） |

### §申し送り ERGR-001: `external_review_gates.feedback_text` の masking 追加検討

| 項目 | 内容 |
|---|---|
| 状態 | **OPEN（将来検討）** |
| 内容 | external-review-gate domain 設計書 §申し送り #1 は `feedback_text` も masking 対象と示しているが、Issue #36 §masking 対象カラムは 2 カラムと明示している。`feedback_text` の値は `approve` / `reject` / `cancel` の `comment` 引数と同一値であり、`audit_entries.comment` としてマスキング済みで保存される |
| 解除条件 | CEO が `feedback_text` に secret を直接入力するユースケースが確認された場合、または `audit_entries.comment` と `feedback_text` が異なる値を持つ設計変更が入った場合 |
| 閉鎖申し送り | `feature/external-review-gate-application` が担当。本 PR での変更不要 |

## 出典・参考

- [SQLAlchemy 2.x — async / AsyncEngine / AsyncSession](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [SQLAlchemy 2.x — Custom Types (TypeDecorator)](https://docs.sqlalchemy.org/en/20/core/custom_types.html)
- [SQLite — Foreign Key Actions](https://www.sqlite.org/foreignkeys.html#fk_actions) — CASCADE 挙動の確認
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [`docs/features/empire-repository/detailed-design.md`](../empire-repository/detailed-design.md) §確定 A〜F — テンプレート真実源
- [`docs/features/task-repository/detailed-design.md`](../task-repository/detailed-design.md) — 直近テンプレート（多段階子テーブル、masking 対象あり）
- [`docs/features/external-review-gate/detailed-design.md`](../external-review-gate/detailed-design.md) — Domain 凍結済み設計（§確定 A〜K、§申し送り #1〜#2）
- [`docs/architecture/domain-model/storage.md`](../../architecture/domain-model/storage.md) §snapshot 凍結方式 — inline コピー設計の凍結源
- [`docs/architecture/threat-model.md`](../../architecture/threat-model.md) — A02 / A04 / A08 / A09 対応根拠
