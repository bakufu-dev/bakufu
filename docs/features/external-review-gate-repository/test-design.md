# テスト設計書

<!-- feature: external-review-gate-repository -->
<!-- 配置先: docs/features/external-review-gate-repository/test-design.md -->
<!-- 対象範囲: RQ-ERGR-001〜007 / 詳細設計 §確定 R1-A〜R1-K / 5段階 save() / 2 masking カラム物理保証 / §設計決定 ERGR-001（reviewer_id FK 非存在） -->

本 feature は M2 Repository **最後の Aggregate Repository PR**（empire / workflow / agent / room / directive / task 後）。ExternalReviewGate Aggregate（M1、PR #46 マージ済み）に対する Repository 層を新規追加する。テンプレートは task-repository (PR #52) を 100% 継承しつつ、**6-method Protocol**（`find_by_id` / `count` / `save(gate)` / `find_pending_by_reviewer` / `find_by_task_id` / `count_by_decision`）と **Gate 固有の 5-step save()**（3 テーブル構造: gate + attachments + audit_entries）および **2 masking カラム**（`external_review_gates.snapshot_body_markdown` / `external_review_audit_entries.comment`）の構造を確立する。

外部レビューゲート固有の論点 5 件を**専用テストファイルで物理保証**する:

1. **save() 5 段階**（§確定 R1-B）— 2 DELETE（attachments + audit_entries）→ gate UPSERT → 2 INSERT の順序強制と子テーブル完全往復
2. **2 masking カラム**（§確定 R1-E）— `snapshot_body_markdown` / `audit_entries.comment` に raw secret が DB に残らないことを raw SQL で物理確認
3. **find_pending_by_reviewer ORDER BY created_at DESC, id DESC + tiebreaker**（§確定 R1-H）— 同時刻複数 PENDING Gate で id DESC が tiebreaker として機能することを物理確認
4. **find_by_task_id ORDER BY created_at ASC, id ASC**（§確定 R1-H）— 差し戻し後の複数ラウンドが時系列昇順で返ることを物理確認
5. **§設計決定 ERGR-001: `reviewer_id` / `snapshot_committed_by` FK 非存在**（Aggregate 境界設計決定）— 0008 時点でこれらのカラムが FK を持たないことを物理確認

**5 ファイル分割**（500行ルール準拠・task-repository §正規構成 継承）:

| ファイル | 担当テストケース |
|--------|----------------|
| `test_protocol_crud.py` | TC-UT-ERGR-001〜004 / 009 + TC-IT-ERGR-LIFECYCLE |
| `test_find_methods.py` | TC-UT-ERGR-006 / 006b / 006c / 006d / 007 / 007b / 007c（find_pending_by_reviewer + find_by_task_id）|
| `test_count_by_decision.py` | TC-UT-ERGR-008（count_by_decision SQL 保証）|
| `test_save_child_tables.py` | TC-UT-ERGR-005 / 005b / 005c（5 段階 save() 物理確認）|
| `test_masking_fields.py` | TC-IT-ERGR-020-masking-* (6 ケース、2 masking カラム核心) |

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| RQ-ERGR-001 | `ExternalReviewGateRepository` Protocol **6 method** 定義 | TC-UT-ERGR-001 | 結合 | 正常系 | 1, 2 |
| RQ-ERGR-001（find_by_id） | `find_by_id` 存在 / 不在 | TC-UT-ERGR-002 | 結合 | 正常系 | 3 |
| RQ-ERGR-002（save round-trip） | `save(gate)` 5 段階 → `find_by_id` round-trip | TC-UT-ERGR-003 | 結合 | 正常系 | 4 |
| RQ-ERGR-002（save 5 段階 DELETE+UPSERT+INSERT） | 5 段階順序の物理確認（child table 完全往復） | TC-UT-ERGR-005 / TC-UT-ERGR-005b / TC-UT-ERGR-005c | 結合 | 正常系 | 4 |
| RQ-ERGR-002（count SQL） | `count()` が SQL `COUNT(*)` を発行 | TC-UT-ERGR-004 | 結合 | 正常系 | — |
| RQ-ERGR-003（find_pending_by_reviewer） | `find_pending_by_reviewer(reviewer_id)` が PENDING Gate のみ ORDER BY created_at DESC, id DESC で返す | TC-UT-ERGR-006 / TC-UT-ERGR-006b / TC-UT-ERGR-006c / TC-UT-ERGR-006d | 結合 | 正常系 | — |
| RQ-ERGR-004（find_by_task_id） | `find_by_task_id(task_id)` が同一 Task の Gate 全件を ORDER BY created_at ASC, id ASC で返す | TC-UT-ERGR-007 / TC-UT-ERGR-007b / TC-UT-ERGR-007c | 結合 | 正常系 | — |
| RQ-ERGR-005（count_by_decision） | `count_by_decision(decision)` が SQL `COUNT(*) WHERE decision = :decision` を発行 | TC-UT-ERGR-008 | 結合 | 正常系 | — |
| RQ-ERGR-002（Tx boundary）| commit path 永続化 / rollback path 破棄 | TC-UT-ERGR-009 | 結合 | 正常系 / 異常系 | — |
| **RQ-ERGR-006（masking、§確定 R1-E）** | raw `snapshot_body_markdown` / `comment` → DB に `<REDACTED:*>` 永続化（**2 masking カラム物理保証**）| TC-IT-ERGR-020-masking-* (6 経路) | 結合 | 正常系 | 5 |
| RQ-ERGR-007（Alembic 0008 DDL）| 3 テーブル + INDEX 3 件 + FK 群作成 | TC-IT-ERGR-001 / TC-IT-ERGR-002 / TC-IT-ERGR-003 | 結合 | 正常系 | 6 |
| RQ-ERGR-007（Alembic chain） | 0001→...→0008 単一 head | TC-IT-ERGR-004 | 結合 | 正常系 | — |
| RQ-ERGR-007（upgrade/downgrade） | 双方向 migration が idempotent | TC-IT-ERGR-005 | 結合 | 正常系 | 6 |
| RQ-ERGR-007（down_revision） | `0008.down_revision == "0007_task_aggregate"` | TC-IT-ERGR-006 | 結合 | 正常系 | — |
| RQ-ERGR-007（Task CASCADE FK）| Task 削除で Gate 自動削除（CASCADE）| TC-IT-ERGR-007 | 結合 | 正常系 | 7 |
| **RQ-ERGR-007（§設計決定 ERGR-001）**| 0008 で `reviewer_id` / `snapshot_committed_by` FK が存在しない（Aggregate 境界設計決定）| TC-IT-ERGR-008 | 結合 | 正常系 | 8 |
| RQ-ERGR-006（CI Layer 2）| arch test parametrize（2 カラム追加）| TC-UT-ERGR-arch | 結合 | 正常系 | 5 |
| RQ-ERGR-006（CI Layer 1）| grep guard で 2 カラムの `MaskedText` 必須 | （CI ジョブ） | — | — | 5 |
| RQ-ERGR-001（storage.md）| §逆引き表更新（ExternalReviewGate 関連行追加）| TC-DOC-ERGR-001 | doc 検証 | 正常系 | 9 |
| **§確定 R1-A（テンプレ継承）** | empire/workflow/agent/room/directive/task §確定 A 継承 | TC-UT-ERGR-001〜009 全件 | 結合 | — | — |
| **§確定 R1-B（save 5 段階）** | DELETE 逆順 → gate UPSERT → 2 INSERT 順序の物理確認 | TC-UT-ERGR-005 | 結合 | 正常系 | 4 |
| **§確定 R1-D（6-method Protocol）** | find_pending_by_reviewer / find_by_task_id / count_by_decision の 3 新 method 追加 | TC-UT-ERGR-006 / TC-UT-ERGR-007 / TC-UT-ERGR-008 | 結合 | 正常系 | — |
| **§確定 R1-E（CI 三層防衛 2 カラム）** | 正のチェック + 負のチェック 2 カラム分 | TC-UT-ERGR-arch + TC-DOC-ERGR-001 | 結合 / doc | 正常系 | 5 |
| **§確定 R1-H（ORDER BY 決定論性）** | 全子テーブルの ORDER BY + find_pending_by_reviewer / find_by_task_id の tiebreaker | TC-UT-ERGR-003 + TC-UT-ERGR-006c + TC-UT-ERGR-007b | 結合 | 正常系 | — |
| **§確定 R1-K（INDEX 3 件）** | ix_external_review_gates_task_id_created / ix_external_review_gates_reviewer_decision / ix_external_review_gates_decision | TC-IT-ERGR-002 | 結合 | 正常系 | 6 |
| **§確定 R1-C（_from_rows 子構造再組み立て）** | snapshot スカラ + attach_rows → Deliverable VO 復元 / audit_rows → AuditEntry list 復元 | TC-UT-ERGR-003 | 結合 | 正常系 | 4 |
| **§設計決定 ERGR-001（reviewer_id FK 非存在）** | 0008 で `external_review_gates.reviewer_id` FK が存在しない（Aggregate 境界） | TC-IT-ERGR-008 | 結合 | 正常系 | 8 |
| **Lifecycle 統合** | save → find_by_id → find_pending_by_reviewer → find_by_task_id → count_by_decision → save（更新）の 6 method 連携 | TC-IT-ERGR-LIFECYCLE | 結合 | 正常系 | 1, 4, 6 |

**マトリクス充足の証拠**:

- RQ-ERGR-001〜007 すべてに最低 1 件のテストケース
- **save() 5 段階の順序確認**: TC-UT-ERGR-005 で child table DELETE → gate UPSERT → child INSERT の順序違反が `IntegrityError` になることを物理確認
- **2 masking カラム全経路**: TC-IT-ERGR-020-masking-* で `snapshot_body_markdown` / `comment` の各カラムに masked + passthrough + roundtrip を確認
- **find_pending_by_reviewer ORDER BY tiebreaker（BUG-EMR-001 準拠）**: TC-UT-ERGR-006d で同時刻 PENDING Gate の id DESC tiebreaker を物理確認
- **find_by_task_id ORDER BY 時系列昇順**: TC-UT-ERGR-007b で差し戻し + 再起票の複数ラウンドが created_at ASC で正しく返ることを確認
- **§設計決定 ERGR-001（Aggregate 境界）**: TC-IT-ERGR-008 で `reviewer_id` / `snapshot_committed_by` FK が 0008 時点で存在しないことを確認
- 受入基準 1〜8 すべてに unit/integration ケース、9 は CI / doc 確認
- 孤児要件ゼロ

## 外部 I/O 依存マップ

本 feature は infrastructure 層の Repository 実装。task-repository と同方針で本物の SQLite + 本物の Alembic + 本物の SQLAlchemy AsyncSession + 本物の MaskingGateway を使う。

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **SQLite (sqlite+aiosqlite)** | engine / session / 3 テーブル / Alembic 0008 migration | 不要（実 DB を `tmp_path` 配下の bakufu.db で起動、テストごとに使い捨て）| 不要 | **済（M2 永続化基盤 conftest の `app_engine` / `session_factory` fixture を再利用）** |
| **ファイルシステム** | `BAKUFU_DATA_DIR` / `bakufu.db` / WAL/SHM | 不要（`pytest.tmp_path`）| 不要 | **済（本物使用）** |
| **Alembic** | 0008 revision の `upgrade head` / `downgrade base` + chain 検証 | 不要（本物の `alembic upgrade` を実 SQLite に対し実行）| 不要 | **済（本物使用、persistence-foundation の `run_upgrade_head` を再利用）** |
| **SQLAlchemy 2.x AsyncSession** | UoW 境界 / Repository メソッド経由の SQL 発行 | 不要 | 不要 | **済（本物使用）** |
| **MaskingGateway (`mask`)** | `MaskedText.process_bind_param` 経由で 2 カラムをマスキング | 不要（実 init を `_initialize_masking` autouse fixture で実施）| 不要 | **済（persistence-foundation #23 で characterization 完了、本 PR で配線実適用）** |

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 | 備考 |
|--------|-----|------------------|------|
| `make_gate`（**本 PR で追加**） | `ExternalReviewGate`（valid デフォルト: `decision=PENDING`, `audit_trail=[]`, `attachments=[]`）| `True` | PR #46 の ExternalReviewGate Aggregate factory |
| `make_gate_with_attachments`（**本 PR で追加**） | `ExternalReviewGate`（`snapshot.attachments` に 2 Attachment 付き）| `True` | save() 段階 4 の INSERT テスト用。`UNIQUE(gate_id, sha256)` 制約確認用 |
| `make_approved_gate`（**本 PR で追加**） | `ExternalReviewGate`（`decision=APPROVED`, `audit_trail` に APPROVED エントリ付き）| `True` | 状態遷移後 save / find_by_task_id ラウンド確認用 |
| `make_rejected_gate`（**本 PR で追加**） | `ExternalReviewGate`（`decision=REJECTED`, `audit_trail` に REJECTED エントリ付き）| `True` | count_by_decision / find_by_task_id テスト用 |
| `make_audit_entry`（**本 PR で追加**） | `AuditEntry`（`action=VIEWED/APPROVED/REJECTED/CANCELLED`）| `True` | audit_trail 複数エントリテスト用 |

`tests/factories/external_review_gate.py` を本 PR で新規作成（task-repository `tests/factories/task.py` 同パターン）。

**raw fixture / characterization は不要**: SQLite + SQLAlchemy + Alembic + MaskingGateway はすべて標準ライブラリ仕様 / 既存 characterization 完了済みの動作で固定。

## E2E テストケース

**該当なし** — 理由:

- 本 feature は infrastructure 層単独で、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない
- Repository は内部 API（Python module-level の Protocol / Class）のみ提供
- テスト戦略ガイド §E2E対象の判断「内部 API・ライブラリなどエンドユーザー操作がない場合は結合テストで代替可」に従い、E2E は本 feature 範囲外
- 後続 `feature/external-review-gate-application` / `feature/http-api` が公開 I/F を実装した時点で E2E を起票

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — infrastructure 層のため公開 I/F なし | — | — |

## 結合テストケース

「Repository 契約 + 実 SQLite + 実 Alembic + 実 MaskingGateway」を contract testing する層。M2 永続化基盤の `app_engine` / `session_factory` fixture を再利用。

### Protocol 定義 + 充足（§確定 R1-A / §確定 R1-D）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-UT-ERGR-001 | `ExternalReviewGateRepository` Protocol が **6 method** を宣言 | — | `application/ports/external_review_gate_repository.py` がインポート可能 | `from bakufu.application.ports.external_review_gate_repository import ExternalReviewGateRepository` | Protocol が `find_by_id` / `count` / `save(gate)` / `find_pending_by_reviewer` / `find_by_task_id` / `count_by_decision` の **6 method** を宣言。すべて `async def`、`@runtime_checkable` なし（empire §確定 A）|
| （TC-UT-ERGR-001 内）| `SqliteExternalReviewGateRepository` の Protocol 充足 | `session_factory` | engine + Alembic 適用済み | `repo: ExternalReviewGateRepository = SqliteExternalReviewGateRepository(session)` で型代入が pyright で通る | pyright strict pass。duck typing で 6 method 全 `hasattr` 確認 |
| （TC-UT-ERGR-001 内）| Protocol に YAGNI 拒否済み method が**存在しない** | — | — | `hasattr(ExternalReviewGateRepository, 'find_all_pending')` 等 | YAGNI 拒否済み method が Protocol に宣言されていない（§確定 R1-D の `find_all_pending` / `find_by_id_all_including_decided` 等）|

### 基本 CRUD — save round-trip / count（§確定 R1-A / §確定 R1-B / §確定 R1-C）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-UT-ERGR-002 | `find_by_id` 存在 / 不在 | `session_factory` + `make_gate` + `seeded_gate_context` | seeded task（task_id FK 依存）| (1) `save(gate)` → `find_by_id(gate.id)` / (2) `find_by_id(uuid4())` | (1) 保存済み Gate を返す / (2) None を返す |
| TC-UT-ERGR-003 | `save(gate)` → `find_by_id` round-trip 全属性（§確定 R1-C）| `session_factory` + `make_gate_with_attachments` + `seeded_gate_context` | seeded task | `save(gate_with_attachments_and_audit)` → `find_by_id(gate.id)` | 復元 Gate が以下全属性と等価: `id` / `task_id` / `stage_id` / `reviewer_id` / `decision` / `feedback_text` / `snapshot_stage_id` / `snapshot_body_markdown` / `snapshot_committed_by` / `snapshot_committed_at` / `created_at`（UTC tz-aware）/ `decided_at` / `deliverable_snapshot.attachments`（sha256 ASC 順）/ `audit_trail`（occurred_at ASC, id ASC 順）|
| TC-UT-ERGR-004 | `count()` SQL `COUNT(*)` 契約 | `session_factory` + `make_gate` + `seeded_gate_context` + `before_cursor_execute` event | DB に複数 Gate 保存済 | `count()` 呼び出し + SQL ログ観測 | `SELECT count(*) FROM external_review_gates` が発行される。全行ロード経路が**ない**ことを assert |
| TC-UT-ERGR-009 | Tx 境界の責務分離（empire §確定 B 踏襲）| `session_factory` + `seeded_gate_context` | seeded task | (1) `async with session.begin(): save(gate)` → 別 session で `find_by_id` / (2) `async with session: save(gate)` を `begin()` なしで実行 | (1) 永続化成功（外側 UoW commit）/ (2) `find_by_id` → None（auto-commit なし）|

### save() 5 段階 DELETE+UPSERT+INSERT（§確定 R1-B）

**`test_save_child_tables.py`** — 5 段階順序の物理確認（§確定 R1-B 専用ファイル）。

| テストID | 対象 | 種別 | 前提条件 | 操作 | 期待結果 |
|---------|-----|------|---------|------|---------|
| TC-UT-ERGR-005 | save(gate) → approve → re-save で audit_entries が DELETE+再INSERT される（§確定 R1-B）| 正常系 | `make_gate` を保存済み | `gate.approve(...)` で新 Gate → re-save → `find_by_id` | 再 save 後の `audit_trail` が更新済み（APPROVED エントリあり）。古い audit_entries 行が残らない（DELETE + 再 INSERT の物理確認）|
| TC-UT-ERGR-005b | UNIQUE(gate_id, sha256) 制約: attachment を更新しても重複行が発生しない（§確定 R1-B 段階 1 + 4）| 正常系 | `make_gate_with_attachments` を保存済み | 同 sha256 の attachment を含む gate を re-save → raw SQL で `external_review_gate_attachments` 行数確認 | `SELECT COUNT(*) FROM external_review_gate_attachments WHERE gate_id = :id` = 期待行数。古い行が段階 1 の DELETE で先行消去済みのため UNIQUE 違反なし |
| TC-UT-ERGR-005c | 全子テーブル空 Gate → audit_trail 付き Gate への更新（段階 3〜5 全実行）| 正常系 | `audit_trail=[]` の Gate を保存済み | `make_approved_gate` 相当の Gate を同 id で re-save → `find_by_id` | `audit_trail` に AuditEntry が存在。`external_review_audit_entries` の行数が factory と一致 |

### find_pending_by_reviewer / find_by_task_id（§確定 R1-D / §確定 R1-H）

**`test_find_methods.py`** — 6-method Protocol の Gate 固有 2 method 専用テストファイル。

| テストID | 対象 | 種別 | 前提条件 | 操作 | 期待結果 |
|---------|-----|------|---------|------|---------|
| TC-UT-ERGR-006 | `find_pending_by_reviewer(reviewer_id)` が PENDING Gate のみ返す | 正常系 | 同 reviewer に PENDING 2件 + APPROVED 1件を保存済み | `find_pending_by_reviewer(reviewer_id)` | 戻り値 list に PENDING Gate が 2件。APPROVED Gate が混入しない |
| TC-UT-ERGR-006b | `find_pending_by_reviewer` が空リストを返す（PENDING Gate なし）| 正常系 | APPROVED / REJECTED Gate のみ | `find_pending_by_reviewer(reviewer_id)` | `[]` 返却（None ではない）|
| TC-UT-ERGR-006c | `find_pending_by_reviewer` SQL ログに `WHERE reviewer_id = ? AND decision = 'PENDING' ORDER BY created_at DESC` が含まれる | 正常系 | PENDING Gate 1件 + event listener | `find_pending_by_reviewer(reviewer_id)` | SQL ログに `reviewer_id` フィルタ + `decision` フィルタ + `ORDER BY created_at` が含まれる（§確定 R1-H 物理確認）|
| **TC-UT-ERGR-006d** | `find_pending_by_reviewer` id DESC tiebreaker — 同時刻 PENDING Gate の id DESC 降順（§確定 R1-H、BUG-EMR-001 準拠）| 正常系 | 同一 `created_at` の PENDING Gate 3件を保存済み | `find_pending_by_reviewer(reviewer_id)` | 結果の id が UUID hex 降順（`sorted(ids, key=lambda u: u.hex, reverse=True)` と一致）。tiebreaker なしだと非決定論的になる回帰検出テスト |
| TC-UT-ERGR-007 | `find_by_task_id(task_id)` が同一 Task の Gate 全件を返す | 正常系 | 同 task_id に Gate 2件（PENDING + REJECTED）を保存済み | `find_by_task_id(task_id)` | 戻り値 list に 2件の Gate が含まれる |
| **TC-UT-ERGR-007b** | `find_by_task_id` が複数ラウンドを created_at ASC で返す（差し戻し対応）| 正常系 | 同 task_id に時系列順で Gate 3件（REJECTED → 再起票 PENDING → 再起票 PENDING）を保存済み | `find_by_task_id(task_id)` | 結果が `created_at` 昇順（ラウンド順）。最初の REJECTED Gate が [0] に来る（§確定 R1-H: ORDER BY created_at ASC, id ASC 物理確認）|
| TC-UT-ERGR-007c | `find_by_task_id` が別 task_id の Gate を返さない（cross-task isolation）| 正常系 | task_A に 2件、task_B に 1件を保存済み | `find_by_task_id(task_a_id)` | 戻り値 list に task_A の Gate が 2件。task_B の Gate が混入しない |

### count_by_decision（§確定 R1-D）

**`test_count_by_decision.py`** — count_by_decision SQL 保証専用ファイル。

| テストID | 対象 | 種別 | 前提条件 | 操作 | 期待結果 |
|---------|-----|------|---------|------|---------|
| TC-UT-ERGR-008 | `count_by_decision(decision)` が SQL `COUNT(*) WHERE decision = :decision` を発行 | 正常系 | PENDING 2件 + APPROVED 1件 + REJECTED 1件を保存済み + SQL event listener | `count_by_decision(ReviewDecision.PENDING)` | 戻り値 = 2。SQL ログに `WHERE decision =` が含まれる。全行ロード経路なし |
| （TC-UT-ERGR-008 内）| `count_by_decision(APPROVED)` = 1 / `count_by_decision(REJECTED)` = 1 / `count_by_decision(CANCELLED)` = 0 | 正常系 | 同上 | 各 decision で `count_by_decision` 呼び出し | 各戻り値が期待数と一致。status で隔離されている |

### 2 masking カラム物理保証（§確定 R1-E / §確定 R1-A、本 PR の核心テストファイル）

**`test_masking_fields.py`** — `snapshot_body_markdown` / `audit_entries.comment` の 2 カラムに raw secret が DB に残らないことを raw SQL SELECT で byte-level 証明する。task-repository `test_masking_fields.py` のテンプレート継承。

| テストID | 対象カラム | 種別 | 入力（secret を含む値）| 期待結果（DB 物理格納値）|
|---------|-----------|------|------|---------|
| TC-IT-ERGR-020-masking-snapshot-masked | `external_review_gates.snapshot_body_markdown` — Discord Bot Token マスキング | 正常系 | `snapshot_body_markdown` に Discord Bot Token を含む Gate を save | raw SQL `SELECT snapshot_body_markdown FROM external_review_gates WHERE id = :id` で `<REDACTED:DISCORD_TOKEN>` を含む。raw token が残らない |
| TC-IT-ERGR-020-masking-snapshot-plain | `external_review_gates.snapshot_body_markdown` — secret なし passthrough | 正常系 | `snapshot_body_markdown` に plain text（"タスク設計が完成した。"）を含む Gate を save | raw SQL SELECT で文字列が改変されない（masking 過剰適用なし）|
| TC-IT-ERGR-020-masking-snapshot-roundtrip | `external_review_gates.snapshot_body_markdown` — 不可逆性（§確定 R1-A）| 正常系 | Discord Bot Token を含む `snapshot_body_markdown` で save → `find_by_id` | 復元 Gate の `deliverable_snapshot.body_markdown` が `<REDACTED:DISCORD_TOKEN>` を含む。raw token が `find_by_id` 経由で復元不能 |
| TC-IT-ERGR-020-masking-comment-masked | `external_review_audit_entries.comment` — GitHub PAT マスキング | 正常系 | `audit_entry.comment` に `ghp_XXX...` を含む Gate を save（approve 経由で AuditEntry 追加）| raw SQL `SELECT comment FROM external_review_audit_entries WHERE gate_id = :id` で `<REDACTED:GITHUB_PAT>` を含む。raw PAT が残らない |
| TC-IT-ERGR-020-masking-comment-plain | `external_review_audit_entries.comment` — secret なし passthrough | 正常系 | `audit_entry.comment` に plain text（"設計品質が基準を満たしている。承認する。"）を含む Gate を save | raw SQL SELECT で文字列が改変されない |
| TC-IT-ERGR-020-masking-2columns | 2 masking カラム同時マスキング（同一 save サイクル）| 正常系 | `snapshot_body_markdown` に Discord Token / `audit_entry.comment` に GitHub PAT を含む Gate を save | raw SQL で両カラムともに masked。Discord Token は `<REDACTED:DISCORD_TOKEN>`、GitHub PAT は `<REDACTED:GITHUB_PAT>`。各カラムに raw secret が残らない（§確定 R1-E 2 カラム同時物理保証）|

### Alembic 0008 + FK CASCADE + §設計決定 ERGR-001（受入基準 6〜8）

**`test_alembic_external_review_gate.py`** — task-repository `test_alembic_task.py` のテンプレート継承。

| テストID | 対象 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|-----|--------------|---------|------|---------|
| TC-IT-ERGR-001 | 0008 が 3 テーブルを作成（受入基準 6）| `empty_engine`（clean DB） | — | `alembic upgrade head` → `SELECT name FROM sqlite_master WHERE type='table'` | `external_review_gates` / `external_review_gate_attachments` / `external_review_audit_entries` の 3 テーブルが存在 |
| TC-IT-ERGR-002 | 0008 が INDEX 3 件を作成（§確定 R1-K）| `empty_engine` | — | `upgrade head` → `SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='external_review_gates'` | `ix_external_review_gates_task_id_created` / `ix_external_review_gates_reviewer_decision` / `ix_external_review_gates_decision` の 3 INDEX が存在 |
| TC-IT-ERGR-003 | `external_review_gates` の FK（→ tasks CASCADE）| `empty_engine` | — | `upgrade head` → `PRAGMA foreign_key_list('external_review_gates')` | `tasks` への FK が存在。ON DELETE CASCADE |
| TC-IT-ERGR-004 | Alembic chain 0001→...→0008 が単一 head（分岐なし）| — | alembic.ini 存在 | `ScriptDirectory.get_heads()` | `len(heads) == 1`（head 分岐なし）|
| TC-IT-ERGR-005 | upgrade head → downgrade base → upgrade head が idempotent（受入基準 6）| `empty_engine` | — | 双方向サイクル実行 | 最終状態で 3 テーブルが存在。downgrade base 後は全テーブル消滅。再 upgrade 後に再出現 |
| TC-IT-ERGR-006 | `0008_external_review_gate_aggregate.down_revision == "0007_task_aggregate"` | — | alembic.ini 存在 | `ScriptDirectory.get_revision("0008_external_review_gate_aggregate").down_revision` | `"0007_task_aggregate"` と等しい（chain 一直線の物理確認）|
| TC-IT-ERGR-007 | `external_review_gates.task_id` FK ON DELETE CASCADE（受入基準 7）| `empty_engine` | — | raw SQL で empire → workflow → room → directive → task → gate を INSERT → `DELETE FROM tasks WHERE id = :id` | Gate 行が CASCADE で自動削除。`SELECT * FROM external_review_gates WHERE task_id = :task_id` が空 |
| **TC-IT-ERGR-008** | **§設計決定 ERGR-001: `external_review_gates.reviewer_id` / `snapshot_committed_by` FK が存在しない（受入基準 8）** | `empty_engine` | — | `upgrade head` → `PRAGMA foreign_key_list('external_review_gates')` | FK 参照テーブル一覧に `owners`（または相当する Aggregate テーブル）が**存在しない**（Aggregate 境界設計決定。reviewer_id は Owner Aggregate 未実装のため FK 非保証。参照整合性は application 層 GateService で保証）|

### CI 三層防衛 ExternalReviewGate 拡張（受入基準 9、§確定 R1-E）

| テストID | 対象 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|-----|--------------|---------|------|---------|
| TC-UT-ERGR-arch | Layer 2: `tests/architecture/test_masking_columns.py` の ExternalReviewGate parametrize 拡張（2 カラム）| `Base.metadata` | M2 永続化基盤の arch test に masking 検証構造あり | parametrize に `("external_review_gates", "snapshot_body_markdown", MaskedText)` / `("external_review_audit_entries", "comment", MaskedText)` を追加 | pass（2 カラムは MaskedText、その他カラムは masking なし）。後続 PR が誤ってカラム型を変更した瞬間に落下して PR ブロック |
| TC-DOC-ERGR-001 | storage.md §逆引き表 ExternalReviewGate 行存在（受入基準 9）| repo root | `docs/architecture/domain-model/storage.md` 編集済み（本 PR で実施）| `tests/docs/test_storage_md_back_index.py` で ExternalReviewGate 行検証 | (a) `external_review_gates.snapshot_body_markdown: MaskedText` が §逆引き表に存在、(b) `external_review_audit_entries.comment: MaskedText` が存在、(c) ExternalReviewGate 残カラム（masking 対象なし）行が存在 |

### Lifecycle 統合シナリオ

| テストID | 対象 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|-----|--------------|---------|------|---------|
| TC-IT-ERGR-LIFECYCLE | 6 method 全経路連携 — save → find_pending_by_reviewer → find_by_task_id → find_by_id → count_by_decision → approve → re-save | `session_factory` + `seeded_gate_context` + `make_gate` | seeded task | (1) `save(gate1)` / `save(gate2)`（別 task）→ (2) `find_pending_by_reviewer(reviewer_id)` = [gate1] → (3) `find_by_task_id(task_id)` = [gate1] → (4) `find_by_id(gate1.id)` = gate1 → (5) `count_by_decision(PENDING)` = 1 → (6) `gate1.approve(...)` → re-save → (7) `count_by_decision(PENDING)` = 0 / `find_pending_by_reviewer` = [] / `count_by_decision(APPROVED)` = 1 | 各段階で期待値と一致。approve 後の count / find_pending が正しく更新される。6 method 全経路が 1 シナリオで連携 |

## ユニットテストケース

**該当なし（DB 経由の物理確認に集約）** — 理由:

- empire-repo / task-repo と同方針: Repository 層は SQLite + Alembic + MaskingGateway の実 I/O が責務の本質
- `_to_rows` / `_from_rows` のラウンドトリップは TC-UT-ERGR-003 + TC-UT-ERGR-005 で integration として物理確認
- domain layer のテストは external-review-gate feature PR #46 で完了済み（本 PR スコープ外）

## カバレッジ基準

- RQ-ERGR-001〜007 すべてに最低 1 件のテストケース
- **save() 5 段階**: TC-UT-ERGR-005 / 005b / 005c で DELETE 先行 + UPSERT + INSERT 順序・child table 完全往復・UNIQUE 制約 3 経路すべてに証拠
- **2 masking カラム（6 経路）**: TC-IT-ERGR-020-masking-* で `snapshot_body_markdown` / `comment` の各カラムに masked + passthrough + roundtrip（snapshot_body_markdown のみ）+ 2 カラム同時を確認
- **find_pending_by_reviewer ORDER BY tiebreaker**: TC-UT-ERGR-006d で同時刻 PENDING Gate の id DESC tiebreaker を物理確認（BUG-EMR-001 準拠回帰検出）
- **find_by_task_id 時系列昇順**: TC-UT-ERGR-007b で差し戻し + 再起票の複数ラウンドが created_at ASC で正しく返ることを確認（§確定 R1-H 物理確認）
- **§設計決定 ERGR-001（Aggregate 境界）**: TC-IT-ERGR-008 で `reviewer_id` FK が 0008 時点で存在しないことを確認
- **Alembic chain 一直線**: TC-IT-ERGR-006 で `0008.down_revision == "0007_task_aggregate"` を物理確認
- **3 テーブル DDL + 3 INDEX**: TC-IT-ERGR-001 / 002 / 003 で 3 テーブルの存在・INDEX・FK を物理確認
- **upgrade/downgrade idempotent**: TC-IT-ERGR-005 で双方向 migration を物理確認
- **CI 三層防衛**: Layer 1 grep（CI ジョブ）+ Layer 2 arch（TC-UT-ERGR-arch）+ Layer 3 storage.md（TC-DOC-ERGR-001）3 層すべてに証拠
- C0 目標: `infrastructure/persistence/sqlite/repositories/external_review_gate_repository.py` で **90% 以上**（task-repo 同水準）

## 人間が動作確認できるタイミング

本 feature は infrastructure 層単独だが、M2 永続化基盤と同じく Backend プロセスを実起動して動作確認できる。

- CI 統合後: `gh pr checks` で全ジョブ緑
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/infrastructure/persistence/sqlite/repositories/test_external_review_gate_repository tests/infrastructure/persistence/sqlite/test_alembic_external_review_gate.py tests/architecture/test_masking_columns.py tests/docs/test_storage_md_back_index.py -v` → 全テスト緑（5ファイル分割: test_protocol_crud / test_find_methods / test_count_by_decision / test_save_child_tables / test_masking_fields）
- Backend 実起動: `cd backend && uv run python -m bakufu`（環境変数 `BAKUFU_DATA_DIR=/tmp/bakufu-test` を設定）
  - 起動時に Alembic auto-migrate で 0001〜0008 が適用されることをログで目視
  - `sqlite3 <DATA_DIR>/bakufu.db ".tables"` で 3 テーブルが存在することを目視
  - `sqlite3 <DATA_DIR>/bakufu.db "PRAGMA foreign_key_list(external_review_gates)"` で `tasks.id` への FK が存在することを目視
  - `sqlite3 <DATA_DIR>/bakufu.db "PRAGMA foreign_key_list(external_review_gates)"` で `owners` への FK が存在しないことを目視（§設計決定 ERGR-001: Aggregate 境界設計決定の確認）
- masking 物理確認: `uv run pytest tests/.../test_masking_fields.py -v` → 6 ケース緑、raw token が DB に残らないことを目視
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.application.ports.external_review_gate_repository --cov=bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository --cov-report=term-missing` → 90% 以上

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      external_review_gate.py              # 新規（make_gate / make_gate_with_attachments /
                                           #        make_approved_gate / make_rejected_gate /
                                           #        make_audit_entry）
    architecture/
      test_masking_columns.py              # 既存更新: ExternalReviewGate 2 カラム parametrize 拡張
                                           # TC-UT-ERGR-arch
    infrastructure/
      persistence/
        sqlite/
          repositories/
            test_external_review_gate_repository/   # 新規ディレクトリ（5 ファイル分割）
              __init__.py
              conftest.py                           # seeded_gate_context helper
                                                    # （empire + workflow + room + directive + task をシード）
              test_protocol_crud.py                  # TC-UT-ERGR-001〜004 / 009 + TC-IT-ERGR-LIFECYCLE
              test_find_methods.py                   # TC-UT-ERGR-006 / 006b / 006c / 006d / 007 / 007b / 007c
              test_count_by_decision.py              # TC-UT-ERGR-008（count_by_decision SQL 保証）
              test_save_child_tables.py              # TC-UT-ERGR-005 / 005b / 005c（5段階 save() 物理確認）
              test_masking_fields.py                 # TC-IT-ERGR-020-masking-* (6 ケース、2 masking カラム核心)
          test_alembic_external_review_gate.py       # TC-IT-ERGR-001〜008（Alembic 0008 + §設計決定 ERGR-001）
    docs/
      test_storage_md_back_index.py                  # 既存更新: ExternalReviewGate 行検証（TC-DOC-ERGR-001）
```

### `conftest.py` 設計: `seeded_gate_context` fixture

ExternalReviewGate を INSERT する前に以下の FK 依存グラフを満たす必要がある:

- `external_review_gates.task_id → tasks.id`（CASCADE）
- `tasks.room_id → rooms.id`（CASCADE）
- `tasks.directive_id → directives.id`（CASCADE）

依存グラフ:
```
empires
  └── workflows
        └── rooms  ← tasks.room_id FK
              └── directives  ← tasks.directive_id FK
                    └── tasks  ← external_review_gates.task_id FK
                          └── external_review_gates  ← テスト本体が save
```

```
conftest.py 提供内容:
  - seeded_gate_context: tuple[UUID, UUID, UUID]  (task_id, stage_id, reviewer_id) fixture
    empire + workflow + room + directive + task を Repository 経由でシードし
    (task.id, uuid4() stage_id, uuid4() reviewer_id) を返す
    ※ stage_id / reviewer_id は FK なしのため uuid4() で生成して固定
  - seed_gate_context(session_factory, ...) → tuple[UUID, UUID, UUID]
    複数 task / reviewer が必要なテスト用 helper（count_by_decision / cross-task isolation 等）
```

`seed_gate_context` helper は task-repository の `seed_task_context` と同パターン（Repository 経由でシードし、FK 依存グラフを満たす）。

### `test_masking_fields.py` の `_read_persisted_*` helper 設計

```
_read_persisted_snapshot_body(session_factory, gate_id) -> str
  raw SQL: SELECT snapshot_body_markdown FROM external_review_gates WHERE id = :id
  task-repo _read_last_error と同パターン

_read_persisted_audit_comment(session_factory, gate_id) -> str
  raw SQL: SELECT comment FROM external_review_audit_entries WHERE gate_id = :id LIMIT 1
  task-repo _read_deliverable_body と同パターン
```

各 helper は TypeDecorator の `process_result_value` をバイパスし、SQLite に物理格納されたバイト列を直接取得する。これにより MaskedText の `process_bind_param`（書き込み時マスキング）が確実に機能していることを byte-level で証明する。

## 未決課題・申し送り

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| §申し送り ERGR-001 | `external_review_gates.feedback_text` の masking 追加検討 | `feature/external-review-gate-application`（後続）| 現在は `Text` 型（Issue #36 仕様準拠）。`audit_entries.comment` と異なる値が必要になった場合に本設計書を更新して 3 カラムに拡張 |
| §設計決定 ERGR-001 | `reviewer_id` / `snapshot_committed_by` FK 非存在（Aggregate 境界）| なし | Aggregate 境界として**永続的に**凍結済み。詳細設計 §Known Issues §設計決定 ERGR-001 参照 |
| M2 完了申し送り | 本 PR（0008）マージで M2 全 7 Aggregate Repository が完成。M3 HTTP API / Application 層への接続では ExternalReviewGateRepository の Protocol をそのまま DI で注入可能 | `feature/http-api`（後続）| GateService.find_pending_for_reviewer → `find_pending_by_reviewer` の接続が M3 の主要タスク |

## レビュー観点（テスト設計レビュー時）

- [ ] RQ-ERGR-001〜007 すべてに 1 件以上のテストケースがあり、特に integration が Repository 契約 + Alembic + masking 配線 + CI 三層防衛を単独でカバーしている
- [ ] **save() 5 段階**（§確定 R1-B）が TC-UT-ERGR-005 / 005b / 005c で DELETE 先行 + UPSERT（ON CONFLICT DO UPDATE）+ INSERT の 3 経路を物理確認
- [ ] **2 masking カラム（6 経路）**（§確定 R1-E）が TC-IT-ERGR-020-masking-* で `snapshot_body_markdown` / `comment` 各カラムに raw SQL SELECT での物理確認
- [ ] **find_pending_by_reviewer ORDER BY tiebreaker**（§確定 R1-H / BUG-EMR-001 準拠）が TC-UT-ERGR-006d で同時刻 PENDING Gate の id DESC tiebreaker を物理確認
- [ ] **find_by_task_id 時系列昇順**（§確定 R1-H）が TC-UT-ERGR-007b で差し戻し + 再起票の複数ラウンドが created_at ASC で正しく返ることを物理確認
- [ ] **§設計決定 ERGR-001（Aggregate 境界）**が TC-IT-ERGR-008 で `reviewer_id` FK が 0008 時点で存在しないことを物理確認（Owner Aggregate 未実装のため FK 非保証）
- [ ] **3 テーブル DDL + 3 INDEX**（RQ-ERGR-007）が TC-IT-ERGR-001 / 002 / 003 で物理確認
- [ ] **Alembic chain 一直線**: TC-IT-ERGR-006 で `0008.down_revision == "0007_task_aggregate"` を物理確認
- [ ] **Task CASCADE FK**: TC-IT-ERGR-007 で `external_review_gates.task_id` ON DELETE CASCADE を物理確認
- [ ] **upgrade/downgrade idempotent**: TC-IT-ERGR-005 で双方向 migration を物理確認
- [ ] **CI 三層防衛**（§確定 R1-E）: Layer 1 grep（CI）+ Layer 2 arch（TC-UT-ERGR-arch）+ Layer 3 storage.md（TC-DOC-ERGR-001）の 3 つすべてに証拠
- [ ] **TypeDecorator 信頼**（§確定 R1-A）: TC-UT-ERGR-003 で UUIDStr 二重ラップなし / MaskedText 手動 mask なしの round-trip を確認
- [ ] **_from_rows 全子構造**（§確定 R1-C）: TC-UT-ERGR-003 で snapshot スカラ + attach_rows → Deliverable VO 復元 / audit_rows → AuditEntry list（occurred_at ASC 順）の復元が §確定 R1-H と一致することを確認
- [ ] **テストファイル分割（5 ファイル: test_protocol_crud / test_find_methods / test_count_by_decision / test_save_child_tables / test_masking_fields）が basic-design.md §モジュール構成と整合**
- [ ] §設計決定 ERGR-001（Aggregate 境界、FK 非存在）が detailed-design.md §Known Issues に明記されている
- [ ] 受入基準 1〜8 すべてにテストケースがある
