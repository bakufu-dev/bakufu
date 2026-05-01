# テスト設計書 — external-review-gate / domain

<!-- feature: external-review-gate / sub-feature: domain -->
<!-- 配置先: docs/features/external-review-gate/domain/test-design.md -->
<!-- 対象範囲: REQ-GT-001〜007 / MSG-GT-001〜008 / 親 spec §9 受入基準 1〜12, 16 / 詳細設計 §確定 A〜K, D' / state machine 7 遷移 + 6 不変条件 + audit_trail append-only + snapshot 不変 + criteria 不変 + record_view 冪等性なし + auto-mask -->

本 sub-feature は domain 層の Aggregate Root（ExternalReviewGate）+ VO（AuditEntry）+ enum（ReviewDecision / AuditAction）+ 例外（ExternalReviewGateInvariantViolation）に閉じる **M1 7 兄弟目（最後）**。HTTP API / CLI / UI の公開エントリポイントは持たないため、E2E は親 [`../system-test-design.md`](../system-test-design.md) が管理する（TC-E2E-ERG-001〜003）。本 sub-feature のテストは **ユニット主体 + Aggregate 内 module 連携 + state machine 全 7 遷移網羅 + 監査要件物理保証** で構成する。

6 兄弟と完全に同じ規約を踏襲（外部 I/O ゼロ・factory に `_meta.synthetic = True` の `WeakValueDictionary` レジストリ）。**最初から 4 ファイル分割**（500 行ルール、empire-repo PR #29 / workflow-repo PR #41 / task PR #42 の Norman R-N1 教訓継承）。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-GT-001（構築） | `ExternalReviewGate.__init__` / `model_validator(mode='after')` | TC-UT-GT-001 | ユニット | 正常系 | 1 |
| REQ-GT-001（永続化復元）| ReviewDecision 4 種で構築可能 | TC-UT-GT-002 | ユニット | 正常系 / 境界 | 2 |
| REQ-GT-002（approve） | `Gate.approve` 正常系 | TC-UT-GT-003 | ユニット | 正常系 | 3 |
| REQ-GT-003（reject）| `Gate.reject` 正常系 | TC-UT-GT-004 | ユニット | 正常系 | 4 |
| REQ-GT-004（cancel） | `Gate.cancel` 正常系 | TC-UT-GT-013 | ユニット | 正常系 | 4 |
| REQ-GT-005（record_view） | `Gate.record_view` 4 状態すべて + 冪等性なし | TC-UT-GT-006 | ユニット | 正常系 | 6 |
| REQ-GT-002〜004（terminal） | PENDING 以外からの approve / reject / cancel | TC-UT-GT-005 | ユニット | 異常系 | 5 |
| REQ-GT-006（不変条件 6 種） | `_validate_*` helper 経路 | TC-UT-GT-007〜010 | ユニット | 正常系 / 異常系 | 7, 8, 9, 10 |
| REQ-GT-007（criteria 不変条件）| `_validate_criteria_immutable` / `required_deliverable_criteria` snapshot | TC-UT-GT-026〜028 | ユニット | 正常系 / 異常系 | 16 |
| 確定 A（dispatch 表） | method × current_decision → action 名の 1:1 対応 7 ✓ + 9 ✗ セルすべて | TC-UT-GT-005 + TC-UT-GT-003/004/006/013 | ユニット | 正常系 / 異常系 | 3〜6 |
| 確定 B（state machine ロック）| `state_machine.TABLE` の `Final` / `MappingProxyType` 性質 | TC-UT-GT-014 | ユニット | 異常系 | — |
| 確定 C（audit_trail append-only）| 既存改変 / prepend / 削除 → raise | TC-UT-GT-009 | ユニット | 異常系 | 9 |
| 確定 D（snapshot 不変性）| `_rebuild_with_state` で snapshot 渡さない契約の物理確認 | TC-UT-GT-008 | ユニット | 異常系 | 8 |
| 確定 D'（criteria 不変性）| `_rebuild_with_state` で criteria 渡さない契約の物理確認 | TC-UT-GT-026〜028 | ユニット | 正常系 / 異常系 | 16 |
| 確定 E（pre-validate） | `approve` 失敗時の元 Gate 不変 | TC-UT-GT-015 | ユニット | 異常系 | — |
| 確定 F（NFC + strip しない）| `feedback_text` の合成形 / 分解形 / 前後改行保持 | TC-UT-GT-016 | ユニット | 正常系 | — |
| 確定 G（record_view 冪等性なし）| 同 owner 複数回 / 同時刻で複数エントリ | TC-UT-GT-006 | ユニット | 正常系 | 6 |
| 確定 H（webhook auto-mask） | `ExternalReviewGateInvariantViolation` の auto-mask | TC-UT-GT-011 | ユニット | 異常系 | 11 |
| 確定 I（例外型統一）| 不変条件違反は `ExternalReviewGateInvariantViolation`、型違反は `pydantic.ValidationError` | TC-UT-GT-005, TC-UT-GT-017 | ユニット | 異常系 | （確定 I）|
| 確定 J（責務分離マトリクス） | application 層責務 5 件すべてが Aggregate 内で強制されないこと | TC-UT-GT-018 | ユニット | 正常系 | （責務境界）|
| 確定 K（4 ファイル分割） | test_*.py 全ファイル 500 行未満 | （静的確認） | — | — | — |
| frozen 不変性 | `gate.decision = X` 直接代入拒否 | TC-UT-GT-019 | ユニット | 異常系 | 内部品質基準 |
| frozen 構造的等価 | 同一属性 Gate 2 インスタンスが `==` True | TC-UT-GT-012 | ユニット | 正常系 | 内部品質基準 |
| `extra='forbid'` | 未知フィールド拒否 | TC-UT-GT-020 | ユニット | 異常系 | 内部品質基準 |
| MSG-GT-001〜005（2 行構造） | 全 5 MSG で `assert "Next:" in str(exc)` | TC-UT-GT-021〜025 | ユニット | 異常系 | 12 |
| **Next: hint 物理保証**（確定 I） | 全 MSG-GT-001〜005 で hint を CI 強制 | TC-UT-GT-021〜025 | ユニット | 異常系 | 12（room §確定 I 踏襲） |
| AC-14（lint/typecheck） | `pyright --strict` / `ruff check` | （CI ジョブ）| — | — | 内部品質基準 |
| AC-15（カバレッジ）| `pytest --cov=bakufu.domain.external_review_gate` | （CI ジョブ）| — | — | 内部品質基準 |
| 結合シナリオ 1 | Gate lifecycle 完走（PENDING → APPROVED + record_view 履歴）| TC-IT-GT-001 | 結合 | 正常系 | 1, 3, 6 |
| 結合シナリオ 2 | REJECTED 経路 + 後日 record_view（terminal でも閲覧記録）| TC-IT-GT-002 | 結合 | 正常系 | 4, 6 |
| 結合シナリオ 3 | snapshot 不変性 + audit_trail append-only の連続安全性 | TC-IT-GT-003 | 結合 | 異常系 | 8, 9 |

**マトリクス充足の証拠**:

- REQ-GT-001〜007 すべてに最低 1 件のテストケース
- **state machine 全 7 ✓ 遷移網羅**: TC-UT-GT-003（approve）/ TC-UT-GT-004（reject）/ TC-UT-GT-013（cancel）/ TC-UT-GT-006（record_view 4 状態）= 7 遷移すべて
- **dispatch 表 9 ✗ セル**: TC-UT-GT-005 で PENDING 以外からの approve / reject / cancel = 9 経路すべて `decision_already_decided`
- **6 不変条件 helper**: `_validate_decided_at_consistency`（TC-UT-GT-007）/ `_validate_snapshot_immutable`（TC-UT-GT-008）/ `_validate_audit_trail_append_only`（TC-UT-GT-009）/ `_validate_feedback_text_range`（TC-UT-GT-010）/ `_validate_decision_immutable`（TC-UT-GT-005）/ `_validate_criteria_immutable`（TC-UT-GT-026〜028）全 6 種に独立 unit
- **§確定 G record_view 冪等性なし**: TC-UT-GT-006 で同 owner 複数回 / 同時刻でも複数エントリ追加を物理確認
- **§確定 D snapshot 不変性**: TC-UT-GT-008 で `_rebuild_with_state` 経路で snapshot が変わらないことを assert
- **§確定 D' criteria 不変性**: TC-UT-GT-026〜028 で `required_deliverable_criteria` が Gate 生成後に変わらないことを物理確認（受入基準 16）
- **§確定 C audit_trail append-only**: TC-UT-GT-009 で既存改変 / prepend / 削除が `audit_trail_append_only` で raise
- **auto-mask（§確定 H）**: TC-UT-GT-011 で webhook URL 含む feedback_text で例外発生 → message + detail 両方が伏字化
- **MSG 2 行構造 + Next: hint（§確定 I、room §確定 I 踏襲）**: TC-UT-GT-021〜028 で全 MSG-GT で `assert "Next:" in str(exc)` を CI 強制（028 は MSG-GT-008 criteria_immutable）
- 親 spec 受入基準 1〜12, 16 すべてに unit/integration ケース（14/15 は system-test-design.md / repository/test-design.md で管理、frozen・CI 品質基準は内部品質基準）
- 確定 A〜K, D' すべてに証拠ケース、孤児要件ゼロ

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **該当なし** | Gate / AuditEntry は domain 層単独で外部 I/O を持たない（HTTP / DB / ファイル / 時刻 / LLM / Discord いずれも未依存）| — | — | **不要（外部 I/O ゼロ）** |
| `unicodedata.normalize('NFC', ...)` | feedback_text / comment 正規化 | — | — | 不要（CPython 標準ライブラリ仕様、6 兄弟と同方針）|
| `datetime.now(UTC)` | `created_at` / `decided_at` / `viewed_at`（呼び出し側 application 層で生成して引数渡し） | — | — | 不要（Aggregate 内で時刻を取得しない、§設計判断補足）|

`_meta.synthetic = True` は 6 兄弟と同パターン（`WeakValueDictionary[int, BaseModel]` レジストリ + `id(instance)` をキーに `is_synthetic()` 判定）。

**factory（合成データ）**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `GateFactory` | `ExternalReviewGate`（valid デフォルト = `decision=PENDING`、`feedback_text=''`、`audit_trail=[]`、`decided_at=None`、`required_deliverable_criteria=()`） | `True` |
| `ApprovedGateFactory` | `ExternalReviewGate`（decision=APPROVED、`decided_at` 設定、audit_trail に APPROVED エントリ 1 件） | `True` |
| `RejectedGateFactory` | 同上、REJECTED | `True` |
| `CancelledGateFactory` | 同上、CANCELLED | `True` |
| `AuditEntryFactory` | `AuditEntry`（valid デフォルト = action=VIEWED、comment=''） | `True` |
| `DeliverableFactory` | `Deliverable`（task PR #42 で実体化済み、再利用） | `True` |

## E2E テストケース

E2E は親 [`../system-test-design.md`](../system-test-design.md) が管理する（TC-E2E-ERG-001〜003）。本 sub-feature（domain）は domain 層単独で外部 I/O を持たないため、E2E テストケースは定義しない。

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| 該当なし — E2E は親 system-test-design.md が管理 | — | — | — | — |

## 結合テストケース

domain 層単独の本 feature では「結合」を **Aggregate 内 module 連携 + Gate lifecycle 完走シナリオ** と定義。外部 I/O ゼロ。

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-GT-001 | Gate lifecycle 完走（PENDING → APPROVED + record_view 履歴）| GateFactory + DeliverableFactory | task_id=t_1, decision=PENDING の Gate | 1) `record_view(owner_a, t_1)` → audit_trail += 1 → 2) `record_view(owner_a, t_2)` → audit_trail += 1（**冪等性なし、§確定 G**）→ 3) `approve(owner_a, comment='OK', decided_at=t_3)` → APPROVED、audit_trail += 1（合計 3 件）→ 4) APPROVED 状態で `approve(...)` 試行 → MSG-GT-001 raise → 5) APPROVED 状態で `record_view(owner_b, t_4)` → audit_trail += 1（**4 状態すべて record_view 許可、§確定 R1-C**）| 5 段階 lifecycle 完走、最終 audit_trail 4 件、APPROVED 状態でも record_view が成立 |
| TC-IT-GT-002 | REJECTED 経路 + 後日 record_view（terminal でも閲覧記録）| GateFactory | task_id=t_1, decision=PENDING | 1) `reject(owner_a, comment='need rework', decided_at=t_1)` → REJECTED、audit_trail += 1 → 2) 翌日 `record_view(owner_a, t_2)` → audit_trail += 1 → 3) 翌々日 `record_view(owner_b, t_3)` → audit_trail += 1 | REJECTED の Gate にも record_view が残る、監査要件成立、複数 owner の閲覧履歴が時系列保持 |
| TC-IT-GT-003 | snapshot 不変性 + audit_trail append-only 連続安全性 | GateFactory + DeliverableFactory | task_id=t_1, decision=PENDING + 既存 audit_trail 2 件 | 1) `record_view(owner_a, t_1)` → 元 Gate の `deliverable_snapshot` が不変、audit_trail 既存 2 件が同一順序で残る + 1 件 append（合計 3 件）→ 2) `approve(...)` → snapshot 不変、audit_trail 既存 3 件 + APPROVED 1 件 = 4 件 → 3) 直接代入で snapshot を変更しようとする → frozen で `pydantic.ValidationError` | snapshot は構築後 frozen で守られ、audit_trail は append のみで成長、既存エントリは絶対に変わらない |

## ユニットテストケース

`tests/factories/external_review_gate.py` の factory 経由で入力を生成。

### 構築（test_construction.py、受入基準 1, 2, 13）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-GT-001 | `Gate(...)` 既定値で構築 | 正常系 | factory デフォルト | 構築成功、`decision=PENDING`、`feedback_text=''`、`audit_trail=[]`、`decided_at=None`、`created_at` tz-aware UTC |
| TC-UT-GT-002 | ReviewDecision 4 種で構築可能（永続化復元）| 正常系 / 境界 | 各 ReviewDecision + 整合する decided_at + audit_trail | 4 件すべて構築成功（PENDING は decided_at=None、他は decided_at 非 None）|
| TC-UT-GT-012 | frozen 構造的等価 / hash | 正常系 | 全属性同値の Gate 2 インスタンス | `==` True、`hash()` 一致 |
| TC-UT-GT-016 | feedback_text の NFC + strip しない（§確定 F）| 正常系 | feedback_text='approval comment\nwith preceding/trailing whitespace\n'（前後改行）| 構築成功、改行・空白保持、NFC 合成形 / 分解形が同一視 |
| TC-UT-GT-019 | frozen 不変性 | 異常系 | `gate.decision = APPROVED` / `gate.audit_trail = [...]` 等の直接代入 | `pydantic.ValidationError`（frozen instance への代入拒否）|
| TC-UT-GT-020 | `extra='forbid'` 未知フィールド拒否 | 異常系 | `Gate.model_validate({...,'unknown': 'x'})` | `pydantic.ValidationError`（extra 違反）|
| TC-UT-GT-017 | 型違反は `pydantic.ValidationError` | 異常系 | `created_at=datetime.now()`（naive）/ `decision='UNKNOWN_DECISION'` / `id='not-uuid'` | 各々で `pydantic.ValidationError` |

### state machine 全 7 遷移 + 9 ✗ セル網羅（test_state_machine.py、受入基準 3〜6）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-GT-003 | `approve` 正常系（PENDING → APPROVED）| 正常系 | PENDING の Gate | 新 Gate の decision=APPROVED、decided_at 設定、audit_trail += APPROVED エントリ |
| TC-UT-GT-004 | `reject` 正常系（PENDING → REJECTED）| 正常系 | PENDING の Gate | 新 Gate の decision=REJECTED、decided_at 設定、audit_trail += REJECTED エントリ |
| TC-UT-GT-013 | `cancel` 正常系（PENDING → CANCELLED）| 正常系 | PENDING の Gate | 新 Gate の decision=CANCELLED、decided_at 設定、audit_trail += CANCELLED エントリ |
| TC-UT-GT-006 | `record_view` 4 状態すべて + 冪等性なし（§確定 G、受入基準 6）| 正常系 | 4 状態の Gate × 同 owner 2 回 record_view | 各々 audit_trail に 2 件追加（同 owner / 同時刻でも複数エントリ）、decision / decided_at / feedback_text 不変 |
| TC-UT-GT-005 | dispatch 表 9 ✗ セル網羅（受入基準 5）| 異常系 | APPROVED / REJECTED / CANCELLED の各 Gate × approve / reject / cancel = 9 経路 | 全 9 経路で `decision_already_decided` raise、MSG-GT-001 |
| TC-UT-GT-014 | state machine TABLE の `Final` / `MappingProxyType` 性質（§確定 B）| 異常系 | `state_machine.TABLE[(PENDING, 'approve')] = APPROVED` 試行 | runtime 例外（`MappingProxyType` の setitem 拒否）、pyright も `Final` 違反として typecheck で検出 |
| TC-UT-GT-015 | `approve` 失敗時の元 Gate 不変（§確定 E pre-validate）| 異常系 | APPROVED の Gate で再 approve 試行 | 失敗後、元 Gate の decision / audit_trail / その他全属性が完全に変化なし |

### 不変条件 5 種 + auto-mask + MSG（test_invariants.py、受入基準 7, 10, 11, 12）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-GT-007 | `_validate_decided_at_consistency`（受入基準 7）| 異常系 | (1) decision=PENDING, decided_at=非 None / (2) decision=APPROVED, decided_at=None | 各々 `ExternalReviewGateInvariantViolation(kind='decided_at_inconsistent')`、MSG-GT-002 |
| TC-UT-GT-010 | `_validate_feedback_text_range`（受入基準 10）| 境界値 | feedback_text=''（0 文字、OK）/ 10000 文字（OK）/ 10001 文字（NG）| 0/10000 は構築成功、10001 は MSG-GT-004（kind='feedback_text_range'）|
| TC-UT-GT-011 | T3: `ExternalReviewGateInvariantViolation` の webhook auto-mask（§確定 H、受入基準 11）| 異常系 | feedback_text に webhook URL を含む文字列 + 10001 文字超過で構築 | 例外の `str(exc)` および `exc.detail` の両方で webhook URL token 部分が `<REDACTED:DISCORD_WEBHOOK>` に伏字化（6 兄弟同パターン）|
| TC-UT-GT-018 | application 層責務 5 件が Aggregate 内で強制されない（§確定 J）| 正常系 | 存在しない task_id / stage_id / reviewer_id を渡して Gate 構築 | 構築成功（Aggregate は VO 型保持のみ）、5 件の責務すべてに「Aggregate 層で強制しない」物理確認 |
| TC-UT-GT-021 | MSG-GT-001 (decision_already_decided) Next: hint | 異常系 | APPROVED の Gate で再 approve | 1 行目: `[FAIL] Gate decision is already decided:` で始まる、2 行目: **`Next:`** + `"PENDING -> APPROVED" in str(exc)` |
| TC-UT-GT-022 | MSG-GT-002 (decided_at_inconsistent) Next: hint | 異常系 | decision=PENDING + decided_at 非 None | 1 行目: `[FAIL] Gate decided_at consistency violation:`、2 行目: **`Next:`** + `"Repository row integrity" in str(exc)` |
| TC-UT-GT-023 | MSG-GT-003 (snapshot_immutable) Next: hint | 異常系 | snapshot 改変試行 | 1 行目: `[FAIL] Gate deliverable_snapshot is immutable`、2 行目: **`Next:`** + `"frozen at Gate creation" in str(exc)` |
| TC-UT-GT-024 | MSG-GT-004 (feedback_text_range) Next: hint | 異常系 | feedback_text 10001 文字 | 1 行目: `[FAIL] Gate feedback_text must be 0-10000`、2 行目: **`Next:`** + `"NFC-normalized" in str(exc)` |
| TC-UT-GT-025 | MSG-GT-005 (audit_trail_append_only) Next: hint | 異常系 | audit_trail 既存 entry 改変 | 1 行目: `[FAIL] Gate audit_trail violates append-only contract`、2 行目: **`Next:`** + `"Only append" in str(exc)` |

### audit_trail append-only + snapshot 不変性 + record_view 冪等性なし（test_audit_snapshot.py、受入基準 8, 9、§確定 C / D / G）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-GT-008 | `_validate_snapshot_immutable`（§確定 D、受入基準 8）| 異常系 | コンストラクタ後の snapshot 改変試行（直接代入は frozen で拒否、`model_validate` 経由で別 snapshot を渡す）| `ExternalReviewGateInvariantViolation(kind='snapshot_immutable')` raise、または `pydantic.ValidationError`（frozen 経由）|
| TC-UT-GT-009 | `_validate_audit_trail_append_only`（§確定 C、受入基準 9）| 異常系 | (1) 既存 entry の comment 改変 / (2) 既存 entry の前に新 entry prepend / (3) 既存 entry 削除 / (4) 順序入れ替え | 各々 `ExternalReviewGateInvariantViolation(kind='audit_trail_append_only')`、MSG-GT-005 |
| TC-UT-GT-009-append-ok | append-only の正常経路 | 正常系 | 元 audit_trail に新 entry を末尾 append | 構築成功（既存 N 件 + 新規 1 件 = N+1 件、順序保持）|

### criteria 不変条件（test_audit_snapshot.py 内追加、受入基準 16、§確定 D'）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-GT-026 | `required_deliverable_criteria` 正常系（空・非空タプル）| 正常系 | (1) `required_deliverable_criteria=()` / (2) AcceptanceCriterion 1 件 / (3) AcceptanceCriterion 3 件（required=True / False 混在）| 各々構築成功、criteria がタプルとして保持される（AcceptanceCriterion は Issue #115 実体化済み VO を使用）|
| TC-UT-GT-027 | `_validate_criteria_immutable`（§確定 D'、受入基準 16）| 異常系 | コンストラクタ後に別の criteria タプルを渡して `model_validate` 経由で更新試行 | `ExternalReviewGateInvariantViolation(kind='criteria_immutable')` raise、MSG-GT-008（1 行目 `[FAIL] Gate required_deliverable_criteria is immutable`、2 行目 `Next:` 含む）|
| TC-UT-GT-028 | criteria が approve / reject 後も引き継がれる（`_rebuild_with_state` で渡さない契約）| 正常系 | criteria 3 件の PENDING Gate → `approve(...)` → 新 Gate / `reject(...)` → 新 Gate / `record_view(...)` → 新 Gate | 各遷移後の Gate の `required_deliverable_criteria` が元と完全同一（MSG-GT-008 が raise されない、フィールド値 / 順序 / required フラグが変化なし）|

## カバレッジ基準

- REQ-GT-001〜007 すべてに最低 1 件のテストケース
- **state machine 全 7 ✓ 遷移**が独立した正常系で網羅（TC-UT-GT-003 / 004 / 013 / 006 × 4 状態 = 7 経路）
- **dispatch 表 9 ✗ セル**が TC-UT-GT-005 で異常系網羅（PENDING 以外からの approve / reject / cancel = 9 経路）
- **6 不変条件 helper** 全種に独立 unit ケース（decided_at_consistency / feedback_text_range / snapshot_immutable / audit_trail_append_only / decision_immutable / criteria_immutable）
- **§確定 G record_view 冪等性なし**: TC-UT-GT-006 で同 owner / 同時刻でも複数エントリ追加を物理確認
- **§確定 D snapshot 不変性**: TC-UT-GT-008 で構造的に物理保証
- **§確定 D' criteria 不変性**: TC-UT-GT-026〜028 で `required_deliverable_criteria` 不変性を物理保証（受入基準 16）
- **auto-mask（§確定 H）**: TC-UT-GT-011 で物理確認
- **MSG 2 行構造 + Next: hint**: TC-UT-GT-021〜028 で全 MSG-GT で `assert "Next:" in str(exc)` を CI 強制（028 は MSG-GT-008 criteria_immutable）
- 親 spec 受入基準 1〜12, 16 すべてに unit/integration ケース（14/15 は system-test-design.md / repository/test-design.md で管理、frozen・CI 品質基準は内部品質基準）
- 確定 A〜K, D' すべてに証拠ケース
- C0 目標: `domain/external_review_gate/` で **95% 以上**

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全ジョブ緑
- ローカル: `cd backend && uv run pytest tests/domain/external_review_gate/test_external_review_gate/ -v` → 全テスト緑
- 不変条件違反の実観測: 不正入力で MSG-GT-001〜005 が出ることを目視
- record_view 冪等性なしの実観測: 同 owner / 同時刻で `record_view` を 2 回呼んで audit_trail が 2 件に増えることを目視
- snapshot 不変性の実観測: `gate.deliverable_snapshot = ...` 直接代入で `pydantic.ValidationError` が出る
- webhook auto-mask の実観測: `feedback_text='https://discord.com/api/webhooks/123/secret-token..' + 'a'*10000` で例外発生時に `<REDACTED:DISCORD_WEBHOOK>` が出る

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      external_review_gate.py                  # 新規: GateFactory / ApprovedGateFactory /
                                               # RejectedGateFactory / CancelledGateFactory /
                                               # AuditEntryFactory / DeliverableFactory（task PR #42 から再利用）
    domain/
      external_review_gate/
        __init__.py
        test_external_review_gate/             # 4 ファイル分割（最初から）
          __init__.py
          test_construction.py                 # TC-UT-GT-001/002/012/016/017/019/020
          test_state_machine.py                # TC-UT-GT-003/004/005/006/013/014/015
          test_invariants.py                   # TC-UT-GT-007/010/011/018/021〜025
          test_audit_snapshot.py               # TC-UT-GT-008/009 + TC-IT-GT-001〜003（往復シナリオ）
```

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| Gate 後続申し送り #1 | `feedback_text` / `audit_trail.comment` の `MaskedText` 配線 | `feature/external-review-gate-repository`（Issue #36）| agent-repository PR #43 の Schneier #3 実適用パターンを踏襲 |
| Gate 後続申し送り #2 | `deliverable_snapshot` の inline コピー実装 | `feature/external-review-gate-repository`（Issue #36）| `storage.md` §snapshot 凍結方式既凍結、本 PR では VO 構造の不変性凍結のみ |
| Gate 後続申し送り #3 | Gate decision → Task method dispatch の application 層実装 | `feature/external-review-gate-application`（後続）| task #42 §確定 A-2 連携先、APPROVED → `approve_review` / REJECTED → `reject_review` / CANCELLED → 場合により `cancel` |

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-GT-001〜006 すべてに 1 件以上のテストケース
- [ ] **state machine 全 7 ✓ 遷移**が独立した正常系で網羅（TC-UT-GT-003 / 004 / 013 / 006 × 4）
- [ ] **dispatch 表 9 ✗ セル**が TC-UT-GT-005 で異常系網羅
- [ ] **6 不変条件 helper** 全種に独立 unit ケース（criteria_immutable は TC-UT-GT-026〜028）
- [ ] **§確定 G record_view 冪等性なし**を TC-UT-GT-006 で物理確認
- [ ] **§確定 D snapshot 不変性**を TC-UT-GT-008 で物理確認
- [ ] **§確定 D' criteria 不変性**を TC-UT-GT-026〜028 で物理確認（受入基準 16）
- [ ] **auto-mask（§確定 H）**を TC-UT-GT-011 で物理確認（feedback_text に webhook URL 含む経路）
- [ ] **MSG 2 行構造 + Next: hint**: TC-UT-GT-021〜028 で全 MSG-GT で `assert "Next:" in str(exc)` を CI 強制（028 は MSG-GT-008 criteria_immutable）
- [ ] 確定 A〜K, D' すべてに証拠ケース
- [ ] frozen 不変性 + 構造的等価 + extra='forbid' が独立検証
- [ ] **テストファイル分割（4 ファイル）が basic-design.md §モジュール構成と整合**（Norman R-N1 教訓を最初から反映）
- [ ] task #42 §確定 A-2 連携先（Gate decision → Task method dispatch は application 層責務）の責務分離が明示
- [ ] 後続申し送り 3 件（Repository マスキング配線 / snapshot inline コピー / GateService dispatch）が PR 本文に明示
