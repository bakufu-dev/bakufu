# 要求分析書

> feature: `external-review-gate-repository`
> Issue: [#36 feat(external-review-gate-repository): ExternalReviewGate SQLite Repository (M2, 0008)](https://github.com/bakufu-dev/bakufu/issues/36)
> 関連: [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源**（§確定 A〜F + §Known Issues §BUG-EMR-001 規約） / [`docs/features/task-repository/`](../task-repository/) **直近テンプレート**（多段階子テーブル + masking 対象カラムあり版） / [`docs/features/external-review-gate/`](../external-review-gate/) （domain 設計済み、PR #46 マージ済み） / [`docs/architecture/domain-model/storage.md`](../../architecture/domain-model/storage.md) §snapshot 凍結方式（inline コピー、sha256 参照）

## 記述ルール（必ず守ること）

要求分析書に**疑似コード・サンプル実装（python/ts/sh/yaml 等の言語コードブロック）を書かない**。
必要なのは「何を作るか・なぜ作るか・どう作るかの方針」の言語的記述であり、実装の細部は [detailed-design.md](detailed-design.md) で凍結する。

## 背景と目的

ExternalReviewGate Aggregate（`domain/external_review_gate/`、PR #46）は M1 ドメインモデルの第 7 集約（最後）であり、bakufu MVP の核心要件「人間チェックポイント」を実現する。本 feature（Issue #36）はその SQLite 永続化基盤（M2 層）を実装する Repository PR であり、**M2 マイルストーンの最後の PR** となる。

empire-repository（PR #25）で確立したテンプレートパターン（Protocol / SqliteXxxRepository / `_to_row` / `_from_row` / Alembic revision）を 100% 継承しつつ、ExternalReviewGate 固有の要件を追加凍結する:

- **独立 Aggregate Root**: Task の子ではなく `task_id` で参照のみ（差し戻し後も履歴保持、複数ラウンド対応）
- **snapshot inline コピー**: `deliverable_snapshot` は Gate 生成時に Deliverable VO を inline コピー（`storage.md §snapshot 凍結方式` で凍結済み）
- **3 テーブル永続化**: `external_review_gates`（Gate 本体 + snapshot スカラ）/ `external_review_gate_attachments`（snapshot 添付ファイルメタデータ）/ `external_review_audit_entries`（監査ログ）
- **2 masking カラム**: `external_review_gates.deliverable_snapshot_body_markdown`（MaskedText）/ `external_review_audit_entries.comment`（MaskedText）

## 要求一覧

| 要求 ID | 要求文 | 優先度 | 出典 |
|--------|-------|-------|------|
| RQ-ERGR-001 | ExternalReviewGate Aggregate を SQLite に永続化・復元できる | Must | ExternalReviewGate Aggregate PR #46 後続課題 |
| RQ-ERGR-002 | 3 テーブルにまたがる save() を DB 整合性を保ちながら原子的に実行できる | Must | snapshot inline コピー方式（storage.md §snapshot 凍結方式） |
| RQ-ERGR-003 | reviewer 視点の PENDING Gate 一覧を取得できる（人間チェックポイント UI） | Must | GateService.find_pending_for_reviewer（後続 Issue） |
| RQ-ERGR-004 | Task の Gate 履歴を全件取得できる（複数ラウンド対応） | Must | 差し戻し後の再レビュー追跡 |
| RQ-ERGR-005 | decision 別の Gate 件数を SQL レベルで取得できる（ダッシュボード） | Must | admin 監視後続要件 |
| RQ-ERGR-006 | `deliverable_snapshot_body_markdown` / `audit_entries.comment` を MaskedText で永続化し、DB に raw secret が保存されないことを CI で物理保証する | Must | MaskingGateway §確定 G（persistence-foundation PR #23 TypeDecorator hook 提供済み）+ external-review-gate §申し送り #1 |
| RQ-ERGR-007 | Alembic revision chain に 0008 を追加する（down_revision = "0007_task_aggregate"） | Must | bakufu Bootstrap M2 migration chain 連続性 |

## §確定事項（先送り撤廃）

要求分析フェーズで判断が確定した事項を以下に凍結する。後続フェーズで再議なし。

### §確定 R1-A: empire §確定 A テンプレートを 100% 継承

empire-repository / task-repository の実績パターンを継承する:

| 継承ルール | 内容 |
|-----------|------|
| Protocol 定義 | `typing.Protocol`、`@runtime_checkable` なし |
| コンストラクタ | `AsyncSession` を引数受け取り（依存性注入） |
| private mapping | `_to_rows()` / `_from_rows()` を private に閉じる |
| 型変換信頼 | TypeDecorator（`UUIDStr` / `MaskedText`）が処理済みの値を返す前提で二重変換しない |
| UPSERT | SQLAlchemy `sqlite_insert(...).on_conflict_do_update(...)` パターン |
| Transaction | Repository 内で `commit` / `rollback` しない（UoW 責務は application 層） |

### §確定 R1-B: save() 5 段階 DELETE+UPSERT+INSERT 順序

empire §確定 B の「子テーブル DELETE → 親 UPSERT → 子 INSERT」パターンを ExternalReviewGate の 3 テーブル構造に適用する:

| 段階 | 操作 | 対象テーブル | 理由 |
|------|------|------------|------|
| 1 | DELETE | `external_review_gate_attachments WHERE gate_id = :id` | CASCADE なし、直接 DELETE |
| 2 | DELETE | `external_review_audit_entries WHERE gate_id = :id` | audit_trail 全削除（append-only は Domain 制約、DB 永続化は delete-then-insert で一貫性保証） |
| 3 | UPSERT | `external_review_gates` | 親行先行。段階 1〜2 で子クリア済みのため FK 制約問題なし |
| 4 | INSERT | `external_review_gate_attachments`（snapshot.attachments の各 Attachment） | 親 Gate 確定後 |
| 5 | INSERT | `external_review_audit_entries`（audit_trail の各 AuditEntry） | 親 Gate 確定後 |

**注意**: `deliverable_snapshot` は Domain 不変条件により Gate 生成後は変更されない。段階 1 の DELETE + 段階 4 の INSERT は新規 Gate では DELETE が 0 件になるが、コード単純性のため既存 Gate と同一パスを通る（task-repository §確定 R1-B パターン踏襲）。

**根拠**: `external_review_gate_attachments → external_review_gates` / `external_review_audit_entries → external_review_gates` の FK 制約から、DELETE は子テーブル優先（FK 参照先の親を先に操作しない）、INSERT は親テーブル優先でなければ `IntegrityError` が発生する。Fail Fast 設計として順序を静的に凍結する。

### §確定 R1-C: snapshot attachments の保存方式 — 子テーブル正規化

`deliverable_snapshot.attachments`（`Attachment` VO のリスト）は `external_review_gate_attachments` 子テーブルで正規化して保存する。JSON カラム inline 方式は不採用:

| 候補 | 採否 | 根拠 |
|---|---|---|
| 子テーブル `external_review_gate_attachments`（採用） | ✓ | `deliverable_attachments` と同スキーマ（sha256 / filename / mime_type / size_bytes）で一貫性。孤児 GC クエリ（storage.md §孤児ファイル GC）が単純な JOIN で全 sha256 集合を取れる。UNIQUE(gate_id, sha256) で重複防止 |
| JSON カラム `snapshot_attachments_json` | ✗ | JSON の中の sha256 を GC クエリで列挙するために JSON_EACH / JSON_EXTRACT が必要（SQLite 3.38+）。MVP 期の SQLite バージョン制約と GC クエリ複雑性を避けるため不採用 |

### §確定 R1-D: Protocol method 6 メソッド（empire 基底 3 + Gate 固有 3）

empire §確定 B の 3 method（`find_by_id` / `count` / `save`）に加え、Gate 固有の 3 method を追加する:

| method | 根拠 |
|--------|------|
| `find_pending_by_reviewer(reviewer_id: OwnerId) -> list[ExternalReviewGate]` | CEO が自分宛の PENDING Gate 一覧を取得する UI（GateService 後続 Issue）。`reviewer_id` INDEX + `decision = 'PENDING'` フィルタで効率検索 |
| `find_by_task_id(task_id: TaskId) -> list[ExternalReviewGate]` | 差し戻し後の複数ラウンド対応。同一 Task の Gate 履歴を全件取得（ORDER BY created_at ASC で時系列順）|
| `count_by_decision(decision: ReviewDecision) -> int` | ダッシュボード（PENDING 件数表示）+ admin 監視（REJECTED 件数等）で SQL COUNT(*) を提供 |

追加しない方法（YAGNI 拒否済み）:

| 拒否した method | 拒否理由 |
|--------------|---------|
| `find_by_id_all_including_decided` | `find_by_id` で APPROVED / REJECTED / CANCELLED も返る（decision でフィルタしない）。同 method で全状態取得可能 |
| `find_all_pending` | reviewer を問わず全 PENDING を返す。MVP では CEO 一人が reviewer のため `find_pending_by_reviewer(ceo_id)` で代替可能。multi-reviewer 対応は別 Issue で |

### §確定 R1-E: CI 三層防衛の 2 masking カラム対応

ExternalReviewGate の 2 masking カラムを CI 三層防衛に登録する:

| カラム | テーブル | TypeDecorator | Layer 1（grep guard） | Layer 2（arch test） |
|-------|---------|------------|--------------------|---------------------|
| `deliverable_snapshot_body_markdown` | `external_review_gates` | `MaskedText` | `tables/external_review_gates.py:deliverable_snapshot_body_markdown:MaskedText` | `external_review_gates.deliverable_snapshot_body_markdown: MaskedText` |
| `comment` | `external_review_audit_entries` | `MaskedText` | `tables/external_review_audit_entries.py:comment:MaskedText` | `external_review_audit_entries.comment: MaskedText` |

**補足 — `feedback_text` の masking 扱い**: external-review-gate domain 設計書（§申し送り #1）は `feedback_text` もマスキング対象と示しているが、Issue #36 §masking 対象カラムは 2 カラム（snapshot_body_markdown + audit_entries.comment）と明示している。`feedback_text` の値は `approve` / `reject` / `cancel` 呼び出し時の `comment` 引数と同一値であり、`audit_entries.comment` としてマスキング済みで保存される。Issue #36 の仕様に従い本 PR では `feedback_text` を `Text` で永続化し、CI 三層防衛は 2 カラムを保証する。将来 `feedback_text` へのマスキング要件が確定した場合は本設計書を更新して 3 カラムに拡張する。

**Layer 1（grep guard）**: `scripts/ci/check_masking_columns.sh` の `PARTIAL_MASK_FILES` に 2 エントリ追加（正のチェック: 必須確認 + 負のチェック: 過剰マスキング防止）。

**Layer 2（arch test）**: `backend/tests/architecture/test_masking_columns.py` の parametrize に 2 行追加（各 `column.type.__class__ is MaskedText` を assert）。

**Layer 3（storage.md）**: `docs/architecture/domain-model/storage.md` §逆引き表を本 PR で更新（§確定 R1-F）。

### §確定 R1-F: storage.md 逆引き表の更新内容

`docs/architecture/domain-model/storage.md` §逆引き表に追加・更新する行:

| 追加行 | 更新内容 |
|------|---------|
| `ExternalReviewGate.deliverable_snapshot.body_markdown` | `（後続）` → `feature/external-review-gate-repository`（Issue #36、**本 PR で配線完了**） |
| `ExternalReviewGate.audit_trail[].comment` | `（後続）` → `feature/external-review-gate-repository`（Issue #36、**本 PR で配線完了**） |
| ExternalReviewGate 残カラム（masking 非対象） | masking 対象なし。CI Layer 2 で arch test 保証 |

### §確定 R1-G: `task_id` / `stage_id` / `reviewer_id` FK 設計

| カラム | FK 設計 | 根拠 |
|-------|---------|------|
| `external_review_gates.task_id → tasks.id` | **ON DELETE CASCADE** | Gate は Task の寿命に従う（Task 削除時に Gate も削除。Task が消えれば Gate の審査対象が存在しないため保持意味なし） |
| `external_review_gates.stage_id` | **FK なし** | Workflow Aggregate 境界（task-repository §確定 R1-G と同方針。`workflow_stages` は Workflow Aggregate の内部構造、Task / Gate が直接依存すると Aggregate 間結合が生まれる） |
| `external_review_gates.reviewer_id` | **FK なし** | Owner Aggregate は M2 未実装（CEO は `owner_id` として UUID で参照のみ。参照整合性は application 層 `GateService.create()` が `OwnerRepository.find_by_id` で保証） |

### §確定 R1-H: 子テーブル SELECT の ORDER BY 決定論性（BUG-EMR-001 準拠）

BUG-EMR-001 規約を全子テーブル SELECT に適用する:

| テーブル / 操作 | ORDER BY | tiebreaker 根拠 |
|------------|---------|----------------|
| `external_review_gate_attachments` | `ORDER BY sha256 ASC` | `UNIQUE(gate_id, sha256)` 制約より gate scope 内で一意。ソート安定 |
| `external_review_audit_entries` | `ORDER BY occurred_at ASC, id ASC` | `occurred_at` が時系列順（Domain の append-only 不変条件を物理保証）。同一時刻は `id`（PK, UUID）で決定論的順序 |
| `find_pending_by_reviewer` | `ORDER BY created_at DESC, id DESC` | 最近起票された未決 Gate を優先表示（review UI UX）。同タイムスタンプは id で決定論的順序 |
| `find_by_task_id` | `ORDER BY created_at ASC, id ASC` | 差し戻し → 再起票の時系列順（ラウンド番号の代替として created_at 昇順）。同タイムスタンプは id で決定論的順序 |

## 技術的判断・選定根拠

| 判断項目 | 採用 | 不採用 | 根拠 |
|---------|------|-------|------|
| snapshot attachments 保存方式 | 子テーブル（§確定 R1-C） | JSON カラム inline | GC クエリ単純性 + `deliverable_attachments` との設計一貫性 |
| `task_id` FK | ON DELETE CASCADE（§確定 R1-G） | ON DELETE RESTRICT / ON DELETE SET NULL | Gate は Task の寿命に従う意味論。RESTRICT は Task 削除前に全 Gate を消す手順が必要で application 層複雑化。SET NULL は `task_id NOT NULL` 制約違反 |
| save() 段数 | 5 段階（§確定 R1-B） | 3 段階（CASCADE のみ依存） | 明示的 DELETE で Tx 中の状態可視化。INSERT OR REPLACE の CASCADE 副作用に依存しない設計（task-repository §確定 R1-B パターン踏襲） |
| `feedback_text` masking | 本 PR では Text（Issue #36 仕様準拠） | MaskedText | Issue #36 が 2 カラムと明示。将来拡張が必要な場合は §確定 R1-E 補足参照 |

## 関連 Issue / PR

| Issue/PR | 関係 |
|---------|------|
| PR #46 | ExternalReviewGate Aggregate 実装（M1 domain layer、本 PR の前提） |
| PR #25 (empire-repository) | テンプレート真実源（§確定 A〜F） |
| PR #52 (task-repository) | 直近テンプレート（多段階子テーブル、masking 対象あり、down_revision=0007）|
| `storage.md §snapshot 凍結方式` | deliverable_snapshot inline コピー設計の凍結源 |
| Issue（後続, 未番号） | GateService application 層（`find_pending_by_reviewer` の呼び出し元） |
