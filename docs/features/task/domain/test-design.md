# テスト設計書 — task / domain

> feature: `task`（業務概念）/ sub-feature: `domain`
> 親業務仕様: [`../feature-spec.md`](../feature-spec.md)
> 対象範囲: REQ-TS-001〜011 / MSG-TS-001〜010 / §9 受入基準 1〜14 + #16（E2E、親 system-test-design.md）+ #17（IT、repository sub-feature）/ 詳細設計 確定 A〜K / state machine 13 遷移 + DONE/CANCELLED terminal + BLOCKED 契約 + last_error consistency + auto-mask + 例外型統一 + 2 行構造 MSG

本 feature は domain 層の Aggregate Root（Task）+ VO（Deliverable / Attachment）+ enum（TaskStatus / LLMErrorKind）+ 例外（TaskInvariantViolation）に閉じる **M1 6 兄弟目**（empire / workflow / agent / room / directive の確立済みパターンを継承）。HTTP API / CLI / UI の公開エントリポイントは持たないため、E2E は本 feature 範囲外（後続 `feature/admin-cli` / `feature/http-api` / `feature/chat-ui`（Phase 2）で起票）。本 feature のテストは **ユニット主体 + Aggregate 内 module 連携の往復シナリオ + state machine 全 13 遷移網羅 + 責務境界の物理確認** で構成する。

5 兄弟と完全に同じ規約を踏襲（外部 I/O ゼロ・factory に `_meta.synthetic = True` の `WeakValueDictionary` レジストリ）。Task は state machine の複雑性が増すため、test ファイルは**最初から 4 ファイル分割**（500 行ルール、empire-repo PR #29 Norman 教訓を最初から反映）。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-TS-001（構築） | `Task.__init__` / `model_validator(mode='after')` | TC-UT-TS-001 | ユニット | 正常系 | 1 |
| REQ-TS-001（永続化復元） | TaskStatus 6 種で構築可能 | TC-UT-TS-002 | ユニット | 正常系 / 境界 | 2 |
| REQ-TS-002（assign） | `Task.assign` 正常系 | TC-UT-TS-003 | ユニット | 正常系 | 3 |
| REQ-TS-002（state machine） | 不正遷移 | TC-UT-TS-004 | ユニット | 異常系 | 4 |
| REQ-TS-003（commit_deliverable） | `Task.commit_deliverable` 正常系 | TC-UT-TS-030 | ユニット | 正常系 | （IN_PROGRESS のみ許可） |
| REQ-TS-004（request_external_review） | `Task.request_external_review` 正常系 | TC-UT-TS-031 | ユニット | 正常系 | （IN_PROGRESS → AWAITING） |
| REQ-TS-005a（approve_review） | `Task.approve_review` 正常系（AWAITING → IN_PROGRESS、Gate APPROVED 経路） | TC-UT-TS-032 | ユニット | 正常系 | （§確定 A-2、Steve R2 凍結） |
| REQ-TS-005b（reject_review） | `Task.reject_review` 正常系（AWAITING → IN_PROGRESS、差し戻し先） | TC-UT-TS-032b | ユニット | 正常系 | （§確定 A-2、Gate REJECTED 経路） |
| REQ-TS-005c（advance_to_next） | `Task.advance_to_next` 正常系（IN_PROGRESS の自己遷移、通常進行） | TC-UT-TS-032c | ユニット | 正常系 | （§確定 A-2） |
| REQ-TS-005d（complete） | `Task.complete` 正常系（IN_PROGRESS → DONE） | TC-UT-TS-033 | ユニット | 正常系 | （§確定 A-2、終端到達） |
| REQ-TS-006（cancel） | `Task.cancel` 4 状態すべて | TC-UT-TS-034 | ユニット | 正常系 | （PENDING/IN_PROGRESS/AWAITING/BLOCKED → CANCELLED） |
| REQ-TS-007（block） | `Task.block` 正常系 | TC-UT-TS-035 | ユニット | 正常系 | （IN_PROGRESS → BLOCKED） |
| REQ-TS-007（block 必須） | `block(reason, last_error='')` Fail Fast | TC-UT-TS-007 | ユニット | 異常系 | 7 |
| REQ-TS-008（unblock_retry） | `Task.unblock_retry` 正常系 | TC-UT-TS-008 | ユニット | 正常系 | 8 |
| REQ-TS-009（不変条件 5 種） | `_validate_*` helper 経路 | TC-UT-TS-009, TC-UT-TS-010 | ユニット | 異常系 | 9, 10 |
| REQ-TS-009（terminal） | DONE / CANCELLED から全 10 ふるまい | TC-UT-TS-005, TC-UT-TS-006 | ユニット | 異常系 | 5, 6 |
| **§確定 A-2（dispatch 表）** | method × current_status → action 名の 1:1 対応 13 ✓ + 47 ✗ セルすべて検証 | TC-UT-TS-004 + TC-UT-TS-032〜033 + TC-UT-TS-005/006 | ユニット | 正常系 / 異常系 | （Steve R2 凍結） |
| REQ-TS-010（Deliverable VO） | `Deliverable` 構築 / 不変性 | TC-UT-TS-012 | ユニット | 正常系 | 12 |
| REQ-TS-010（Attachment VO） | `Attachment` 構築 / サニタイズ | TC-UT-TS-013 | ユニット | 正常系 / 異常系 | 13 |
| REQ-TS-011（TaskStatus enum） | StrEnum の 6 値 | TC-UT-TS-036 | ユニット | 正常系 | （列挙確認） |
| REQ-TS-011（LLMErrorKind enum） | StrEnum の 5 値 | TC-UT-TS-037 | ユニット | 正常系 | （列挙確認） |
| 確定 A（pre-validate） | `assign` 失敗時の元 Task 不変 | TC-UT-TS-038 | ユニット | 異常系 | — |
| 確定 B（state machine ロック） | `state_machine.TABLE` の `Final` / `MappingProxyType` 性質 | TC-UT-TS-039 | ユニット | 異常系 | — |
| 確定 C（NFC + strip しない） | `last_error` の合成形 / 分解形 / 前後改行保持 | TC-UT-TS-040 | ユニット | 正常系 | — |
| 確定 D（unblock で last_error クリア） | `unblock_retry` 後 `last_error is None` | TC-UT-TS-008 | ユニット | 正常系 | 8 |
| 確定 E（cancel 4 状態列挙） | 4 状態すべてから cancel 可能、DONE/CANCELLED から不可 | TC-UT-TS-034, TC-UT-TS-005, TC-UT-TS-006 | ユニット | 正常系 / 異常系 | 5, 6 |
| 確定 F（assigned_agents 重複） | 重複 → `assigned_agents_unique` | TC-UT-TS-009 | ユニット | 異常系 | 9 |
| 確定 F（assigned_agents 容量） | 6 件 → `assigned_agents_capacity` | TC-UT-TS-041 | ユニット | 異常系 | （MSG-TS-004） |
| 確定 G（by_agent_id 責務） | Aggregate 内では `by_agent_id` を `assigned_agent_ids` 内かチェックしない | TC-UT-TS-042 | ユニット | 正常系 | （責務境界） |
| 確定 H（pre-validate 連続） | `assign` 失敗 → 元 Task で再度 assign 可能 | TC-IT-TS-001 | 結合 | 異常系 | — |
| 確定 I（webhook auto-mask） | `TaskInvariantViolation` の auto-mask | TC-UT-TS-011 | ユニット | 異常系 | 11 |
| 確定 J（例外型統一） | terminal は `TaskInvariantViolation`、型違反は `pydantic.ValidationError` | TC-UT-TS-005, TC-UT-TS-008 | ユニット | 異常系 | （確定 J） |
| 確定 K（責務分離マトリクス） | application 層責務 5 件すべてが Aggregate 内で強制されないことを物理確認 | TC-UT-TS-043 | ユニット | 正常系 | （責務境界） |
| frozen 不変性 | `task.status = X` 直接代入拒否 | TC-UT-TS-044 | ユニット | 異常系 | 内部品質基準 |
| frozen 構造的等価 | 同一属性 Task 2 インスタンスが `==` True | TC-UT-TS-014 | ユニット | 正常系 | 内部品質基準 |
| `extra='forbid'` | 未知フィールド拒否 | TC-UT-TS-045 | ユニット | 異常系 | （T1 防御） |
| MSG-TS-001〜007（2 行構造） | 全 7 MSG で `assert "Next:" in str(exc)` | TC-UT-TS-046〜052 | ユニット | 異常系 | 14 |
| MSG-TS-008 | 型違反は `pydantic.ValidationError` 経由 | TC-UT-TS-053 | ユニット | 異常系 | （確定 J） |
| MSG-TS-009 | Attachment サニタイズ違反 | TC-UT-TS-013 | ユニット | 異常系 | 13 |
| **Next: hint 物理保証**（確定 J） | 全 MSG-TS-001〜007 で `assert "Next:" in str(exc)` を CI 強制 | TC-UT-TS-046〜052 | ユニット | 異常系 | 14（room §確定 I 踏襲） |
| AC-16（lint/typecheck） | `pyright --strict` / `ruff check` | （CI ジョブ） | — | — | 内部品質基準 |
| AC-17（カバレッジ） | `pytest --cov=bakufu.domain.task` | （CI ジョブ） | — | — | 内部品質基準 |
| 結合シナリオ 1 | Task lifecycle 完走（PENDING → DONE） | TC-IT-TS-002 | 結合 | 正常系 | 1, 3, 8（DONE 到達） |
| 結合シナリオ 2 | BLOCKED 経路と復旧（IN_PROGRESS → BLOCKED → IN_PROGRESS → DONE） | TC-IT-TS-003 | 結合 | 正常系 / 異常系 | 7, 8 |
| 結合シナリオ 3 | cancel 経路（4 状態すべてから CANCELLED） | TC-IT-TS-004 | 結合 | 正常系 | （確定 E） |

**マトリクス充足の証拠**:

- REQ-TS-001〜011 すべてに最低 1 件のテストケース
- **state machine 全 13 遷移網羅**: TC-UT-TS-003（assign）/ 030（commit）/ 031（request_review）/ 032（advance to next）/ 033（advance to DONE）/ 034（cancel from 4 states）/ 035（block）/ 008（unblock）の 8 ケース + cancel が 4 行 = 13 遷移すべてに正常系ケース。table 不在の遷移は TC-UT-TS-004 で `state_transition_invalid` 異常系を網羅
- **DONE / CANCELLED terminal 物理確認**: TC-UT-TS-005（DONE 起点で 10 ふるまい全部 raise）/ TC-UT-TS-006（CANCELLED 起点で同上）の 2 × 10 = 20 経路すべて
- **BLOCKED 契約**: `block(reason, last_error='')` で Fail Fast（TC-UT-TS-007）/ `unblock_retry` で `last_error=None` クリア（TC-UT-TS-008）/ `_validate_blocked_has_last_error`（TC-UT-TS-010）の 3 経路
- **責務境界 5 件**（current_stage_id 存在 / agent_ids ∈ Room.members / transition_id 存在 / Stage.kind 検査 / by_agent_id ∈ assigned）すべてに「Aggregate 層で強制しない」ことを物理確認する unit ケース（TC-UT-TS-042, TC-UT-TS-043）
- **TaskInvariantViolation auto-mask（確定 I）**: webhook URL を含む last_error で例外発生 → message と detail の両方が伏字化されていることを TC-UT-TS-011 で確認
- **MSG 2 行構造 + Next: hint 物理保証（確定 J、room §確定 I 踏襲）**: 全 MSG-TS-001〜007 で `assert "Next:" in str(exc)` を CI 強制（TC-UT-TS-046〜052）
- **§9 受入基準 1〜14 すべてに unit/integration ケース**（内部品質基準 lint/typecheck/coverage は CI ジョブ）。受入基準 #16（再起動跨ぎ保持）は親 [`../system-test-design.md`](../system-test-design.md) の TC-E2E-TS-001 で E2E カバー。受入基準 #17（DB masking）は repository sub-feature の TC-IT-TR-020-masking-* で IT カバー
- 確定 A（pre-validate）/ B（table ロック）/ C（NFC + strip しない）/ D（last_error クリア）/ E（cancel 4 状態）/ F（agents 重複/容量）/ G（by_agent_id 責務）/ H（連続安全性）/ I（auto-mask）/ J（例外型統一 + 2 行 MSG）/ K（責務分離マトリクス）すべてに証拠ケース
- 孤児要件ゼロ

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **該当なし** | Task / Deliverable / Attachment は domain 層単独で外部 I/O を持たない（HTTP / DB / ファイル / 時刻 / LLM / Discord いずれも未依存）。`last_error` / `body_markdown` は文字列バリデーションのみで実 LLM 送信は `feature/llm-adapter` 責務。`current_stage_id` / `room_id` / `directive_id` も VO 型として保持のみで、参照先 Aggregate の存在検証は application 層責務 | — | — | **不要（外部 I/O ゼロ）** |
| `unicodedata.normalize('NFC', ...)` | last_error 正規化 | — | — | 不要（CPython 標準ライブラリ仕様で固定、5 兄弟と同方針） |
| `datetime.now(UTC)` | `Task.created_at` / `updated_at`（呼び出し側 application 層で生成して引数渡し、Aggregate 内では受け取るのみ） | — | — | 不要（Aggregate 内で時刻を取得しない、§設計判断「なぜ created_at/updated_at を引数で受け取るか」） |
| `os.path.basename()` | Attachment.filename サニタイズ（path traversal 二重防護） | — | — | 不要（Python 標準ライブラリ仕様で固定） |

**根拠**:
- [`basic-design.md`](basic-design.md) §外部連携 で「該当なし — domain 層のみのため外部システムへの通信は発生しない」と凍結
- [`../feature-spec.md`](../feature-spec.md) §8 制約・前提 で「ネットワーク: 該当なし」と凍結
- 本 feature では assumed mock 問題は構造上発生しない（モック対象なし）

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `TaskFactory` | `Task`（valid デフォルト = `status=PENDING`、`assigned_agent_ids=[]`、`deliverables={}`、`last_error=None`） | `True` |
| `InProgressTaskFactory` | `Task`（status=IN_PROGRESS、assigned_agent_ids 1 件） | `True` |
| `AwaitingReviewTaskFactory` | `Task`（status=AWAITING_EXTERNAL_REVIEW） | `True` |
| `BlockedTaskFactory` | `Task`（status=BLOCKED、last_error 非空） | `True` |
| `DoneTaskFactory` | `Task`（status=DONE、deliverables 1 件） | `True` |
| `CancelledTaskFactory` | `Task`（status=CANCELLED） | `True` |
| `DeliverableFactory` | `Deliverable`（valid デフォルト + 添付なし） | `True` |
| `AttachmentFactory` | `Attachment`（valid デフォルト = sha256 既知 hex / filename ASCII / mime image/png / size 1024） | `True` |

`_meta.synthetic = True` は 5 兄弟と同じく **`tests/factories/task.py` モジュールスコープ `WeakValueDictionary[int, BaseModel]` レジストリ + `id(instance)` をキーに `is_synthetic()` で判定** 方式を踏襲する。frozen + `extra='forbid'` を尊重してインスタンスに属性追加は試みない。本番コード（`backend/src/bakufu/`）からは `tests/factories/task.py` を import しない（CI で `tests/` から `src/` への向きのみ許可）。

## E2E テストケース

**該当なし** — 理由:

- 本 feature は domain 層の純粋ライブラリで、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない（[`../feature-spec.md`](../feature-spec.md) §6 スコープ で「該当なし」と凍結）
- 戦略ガイド §E2E対象の判断「内部API・ライブラリなどエンドユーザー操作がない場合は結合テストで代替可」に従い、E2E は本 feature 範囲外
- 後続 `feature/admin-cli` / `feature/http-api`（Task lifecycle API） / `feature/chat-ui`（Phase 2 Web UI）が公開 I/F を実装した時点で E2E を起票
- §9 受入基準 1〜14 はすべて unit/integration テストで検証可能。#16（再起動跨ぎ保持）は親 [`../system-test-design.md`](../system-test-design.md) の TC-E2E-TS-001 が担当。#17（DB masking）は repository sub-feature の IT が担当

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — domain 層のため公開 I/F なし | — | — |

## 結合テストケース

domain 層単独の本 feature では「結合」を **Aggregate 内 module 連携（Task + state_machine + TaskInvariantViolation の往復シナリオ）+ Task lifecycle 完走シナリオ**と定義する。外部 LLM / Discord / GitHub / DB は本 feature では使わないためモック不要。

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-TS-001 | `Task.assign`（失敗）+ pre-validate 連続安全性（確定 H） | factory（`TaskFactory`） | 既に IN_PROGRESS の Task | 1) 再度 `assign(...)` を試行 → MSG-TS-002（state_transition_invalid）→ 2) 元 Task が status=IN_PROGRESS のまま不変であることを確認（確定 A）→ 3) 別経路の `commit_deliverable` を呼んで成功することで状態破損なし確認 | 失敗の独立性が連続操作で破綻しないこと、元 Task 不変、別ふるまいでの再試行成功 |
| TC-IT-TS-002 | Task lifecycle 完走（PENDING → IN_PROGRESS → AWAITING_EXTERNAL_REVIEW → IN_PROGRESS → DONE、§確定 A-2 の 4 method 専用分離経路） | factory + `DeliverableFactory` | task_id=t_1, status=PENDING の Task | 1) `assign([agent_a])` → IN_PROGRESS → 2) `commit_deliverable(stage_a, deliverable, agent_a)` → 3) `request_external_review()` → AWAITING → 4) **`approve_review(transition_id, owner_id, next_stage_id)`** → IN_PROGRESS（次 Stage） → 5) `commit_deliverable` → 6) **`complete(transition_id, owner_id)`** → DONE → 7) DONE 状態で全 10 ふるまい呼び出しが MSG-TS-001 で raise | 5 段階の lifecycle が完走、最終 status=DONE、deliverables 2 件、DONE が terminal で全変更不可、`approve_review` / `complete` の専用 method 分離が一連の呼び出しで成立 |
| TC-IT-TS-003 | BLOCKED 経路と復旧（IN_PROGRESS → BLOCKED → IN_PROGRESS → DONE） | factory + webhook URL を含む last_error 文字列 | task_id=t_1, status=IN_PROGRESS の Task | 1) `block(reason, last_error='AuthExpired: https://discord.com/api/webhooks/123/secret')` → BLOCKED → 2) Task の `last_error` が NFC 正規化済みで保持されることを確認（auto-mask は永続化前のため Aggregate 内では raw 保持）→ 3) `unblock_retry()` → IN_PROGRESS → 4) `last_error=None` であることを確認（確定 D）→ 5) `commit_deliverable` → 6) **`complete(transition_id, owner_id)`** → DONE | BLOCKED 隔離 → 復旧 → DONE 完走、確定 D の last_error クリア物理確認 |
| TC-IT-TS-005 | **REJECTED 差し戻し経路**（§確定 A-2、Gate REJECTED → reject_review） | factory + DeliverableFactory | task_id=t_1, status=AWAITING_EXTERNAL_REVIEW の Task | 1) `reject_review(transition_id, owner_id, next_stage_id=差し戻し先)` → IN_PROGRESS（current_stage_id が差し戻し先）→ 2) `commit_deliverable(差し戻し先 stage_id, ...)` → 3) `request_external_review()` → AWAITING（再レビュー）→ 4) `approve_review(...)` → IN_PROGRESS → 5) `complete(...)` → DONE | reject → 再 commit → 再 review → approve → complete の差し戻し再ループが成立、差し戻し前後で別の current_stage_id を持てる物理確認 |
| TC-IT-TS-004 | cancel 経路（PENDING / IN_PROGRESS / AWAITING / BLOCKED の 4 状態すべてから CANCELLED）| factory 6 種 | 各状態の Task 4 件 | 各 Task に対して `cancel(owner_id, reason='manual abort')` → status=CANCELLED に遷移、cancel 後の `last_error` は None（status=CANCELLED は last_error_consistency により None 必須）| 4 状態すべてから CANCELLED への遷移が成功、確定 E（4 状態列挙）の物理確認 |

**注**: 本 feature では結合テストも `tests/integration/test_task.py` ではなく `tests/domain/task/test_task/` ディレクトリ内の test_state_machine.py / test_construction.py 等に「往復シナリオ」セクションとして実装してよい（5 兄弟と同方針）。

## ユニットテストケース

`tests/factories/task.py` の factory 経由で入力を生成する。raw fixture は本 feature では外部 I/O ゼロのため存在しない。

### Task 構築（test_construction.py、受入基準 1, 2, 14）

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---------|-----|------|---------------|---------|
| TC-UT-TS-001 | `Task(...)` 既定値で構築 | 正常系 | factory デフォルト | 構築成功、`status=PENDING`、`deliverables={}`、`assigned_agent_ids=[]`、`last_error=None`、`created_at <= updated_at` |
| TC-UT-TS-002 | TaskStatus 6 種で構築可能（永続化復元、§確定 R1-A） | 正常系 / 境界 | 各 TaskStatus + 整合する last_error | 6 件すべて構築成功（status=BLOCKED は last_error 非空必須、他は None 必須） |
| TC-UT-TS-014 | frozen 構造的等価 / hash | 正常系 | 全属性同値の Task 2 インスタンス | `==` True、`hash()` 一致 |
| TC-UT-TS-040 | last_error の NFC + strip しない（確定 C） | 正常系 | last_error='AuthExpired:\n  at line 1\n  at line 2'（前後改行保持） | 構築成功、`last_error` の改行・前後空白が保持される、NFC 合成形 / 分解形が同一視 |
| TC-UT-TS-044 | frozen 不変性 | 異常系 | `task.status = TaskStatus.IN_PROGRESS` 等の直接代入 | `pydantic.ValidationError`（frozen instance への代入拒否）、Task の全属性で確認 |
| TC-UT-TS-045 | `extra='forbid'` 未知フィールド拒否 | 異常系 | `Task.model_validate({...,'unknown': 'x'})` | `pydantic.ValidationError`、`extra` 違反（T1 関連の入力境界防御） |
| TC-UT-TS-053 | 型違反は `pydantic.ValidationError`（MSG-TS-008） | 異常系 | `created_at=datetime.now()`（naive）/ `status='UNKNOWN_STATUS'`（enum 外）/ `id='not-uuid'` | 各々で `pydantic.ValidationError`（kind 概念なし、確定 J 例外型統一規約） |

### state machine 全 13 遷移 + 不正遷移網羅（test_state_machine.py、受入基準 3〜8）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-TS-003 | `assign` 正常系（PENDING → IN_PROGRESS） | 正常系 | PENDING の Task + agent_ids=[agent_a] | 新 Task の status=IN_PROGRESS、assigned_agent_ids=[agent_a]、元 Task は不変 |
| TC-UT-TS-004 | state machine 不正遷移（一覧網羅） | 異常系 | 6 status × 10 method = 60 経路のうち 13 許可遷移を除く 47 経路（dispatch 表 ✗ セル全件、§確定 A-2） | 各々で `TaskInvariantViolation(kind='state_transition_invalid')`、MSG-TS-002 |
| TC-UT-TS-005 | DONE terminal 全 10 ふるまい raise（受入基準 5） | 異常系 | DoneTaskFactory + 全 10 ふるまい呼び出し（assign / commit_deliverable / request_external_review / approve_review / reject_review / advance_to_next / complete / cancel / block / unblock_retry） | 全 10 ふるまいが `TaskInvariantViolation(kind='terminal_violation')`、MSG-TS-001 |
| TC-UT-TS-006 | CANCELLED terminal 全 10 ふるまい raise（受入基準 6） | 異常系 | CancelledTaskFactory + 全 10 ふるまい呼び出し | 同上 |
| TC-UT-TS-007 | `block(reason, last_error='')` Fail Fast（受入基準 7） | 異常系 | IN_PROGRESS の Task + last_error='' | `TaskInvariantViolation(kind='blocked_requires_last_error')`、MSG-TS-006 |
| TC-UT-TS-008 | `unblock_retry()` 正常系 + last_error クリア（受入基準 8、確定 D） | 正常系 | BlockedTaskFactory（last_error 非空） | 新 Task の status=IN_PROGRESS、`last_error is None` |
| TC-UT-TS-030 | `commit_deliverable` 正常系（IN_PROGRESS の自己遷移） | 正常系 | IN_PROGRESS の Task + DeliverableFactory | 新 Task の deliverables[stage_id] = deliverable、status=IN_PROGRESS のまま、updated_at 更新 |
| TC-UT-TS-031 | `request_external_review` 正常系（IN_PROGRESS → AWAITING） | 正常系 | IN_PROGRESS の Task | 新 Task の status=AWAITING_EXTERNAL_REVIEW |
| TC-UT-TS-032 | `approve_review` 正常系（AWAITING_EXTERNAL_REVIEW → IN_PROGRESS、Gate APPROVED 経路、§確定 A-2）| 正常系 | AwaitingReviewTaskFactory + transition_id + next_stage_id（次 Stage） | 新 Task の status=IN_PROGRESS、current_stage_id=next_stage_id |
| TC-UT-TS-032b | `reject_review` 正常系（AWAITING_EXTERNAL_REVIEW → IN_PROGRESS、Gate REJECTED 経路、§確定 A-2）| 正常系 | AwaitingReviewTaskFactory + transition_id + next_stage_id（差し戻し先） | 新 Task の status=IN_PROGRESS、current_stage_id=差し戻し先 |
| TC-UT-TS-032c | `advance_to_next` 正常系（IN_PROGRESS の自己遷移、通常進行、§確定 A-2）| 正常系 | InProgressTaskFactory + transition_id + next_stage_id | 新 Task の status=IN_PROGRESS、current_stage_id 更新 |
| TC-UT-TS-033 | `complete` 正常系（IN_PROGRESS → DONE、終端到達、§確定 A-2）| 正常系 | InProgressTaskFactory + transition_id（next_stage_id 引数なし） | 新 Task の status=DONE（terminal）、current_stage_id 不変 |
| TC-UT-TS-034 | `cancel` 4 状態すべてから（確定 E）| 正常系 | PENDING / IN_PROGRESS / AWAITING / BLOCKED の 4 Task | 各々 status=CANCELLED に遷移、`last_error=None`（cancel は last_error をクリア） |
| TC-UT-TS-035 | `block` 正常系（IN_PROGRESS → BLOCKED） | 正常系 | IN_PROGRESS の Task + last_error='AuthExpired: ...' | 新 Task の status=BLOCKED、last_error 非空 |
| TC-UT-TS-038 | `assign` 失敗時の元 Task 不変（確定 A） | 異常系 | IN_PROGRESS の Task で再度 `assign` | 失敗後、元 Task の `assigned_agent_ids` / `status` / その他全属性が完全に変化なし（pre-validate） |
| TC-UT-TS-039 | state machine TABLE の `Final` / `MappingProxyType` 性質（確定 B） | 異常系 | `state_machine.TABLE[(PENDING, 'assign')] = TaskStatus.DONE` 試行 | runtime 例外（`MappingProxyType` の setitem 拒否）、pyright も `Final` 違反として typecheck で検出 |

### 不変条件 helper 5 種（test_invariants.py、受入基準 9〜11）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-TS-009 | `_validate_assigned_agents_unique`（受入基準 9）| 異常系 | assigned_agent_ids=[agent_a, agent_b, agent_a] | `TaskInvariantViolation(kind='assigned_agents_unique')`、MSG-TS-003、detail に重複 ID |
| TC-UT-TS-010 | `_validate_last_error_consistency`（受入基準 10）| 異常系 | status=IN_PROGRESS, last_error='something' / status=BLOCKED, last_error=None | 各々 `TaskInvariantViolation(kind='last_error_consistency')`、MSG-TS-005 |
| TC-UT-TS-011 | T3: `TaskInvariantViolation` の webhook auto-mask（確定 I、受入基準 11）| 異常系 | last_error に webhook URL を含む文字列で構築 → 不変条件違反を発生させる | 例外の `str(exc)` および `exc.detail` の両方で webhook URL の token 部分が `<REDACTED:DISCORD_WEBHOOK>` に伏字化されていること（5 兄弟と同パターン） |
| TC-UT-TS-041 | `_validate_assigned_agents_capacity` | 異常系 | assigned_agent_ids=6 件 | `TaskInvariantViolation(kind='assigned_agents_capacity')`、MSG-TS-004 |
| TC-UT-TS-042 | Aggregate 内では `by_agent_id` が `assigned_agent_ids` 内かを**検査しない**（確定 G）| 正常系 | IN_PROGRESS の Task + assigned_agent_ids=[agent_a] + `commit_deliverable(stage, d, by_agent_id=agent_z)`（agent_z は Task に未割当）| 構築成功（Aggregate 内では `by_agent_id` を検査しない）。検査は `TaskService.commit_deliverable()` 責務（責務境界の物理確認） |
| TC-UT-TS-043 | application 層責務 5 件すべてが Aggregate 内で強制されないこと（確定 K） | 正常系 | 存在しない room_id / current_stage_id / agent_id を渡して Task 構築 | 構築成功（Aggregate は VO 型保持のみ）。5 件の責務すべてに「Aggregate 層で強制しない」ことを物理確認する境界凍結ケース |

### Deliverable / Attachment VO（test_vo.py、受入基準 12, 13）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-TS-012 | `Deliverable(...)` 構築 + frozen | 正常系 / 異常系 | factory デフォルト + 直接代入試行 + 1,000,000 文字超過 body_markdown | 構築成功、frozen で代入不可、1,000,001 文字は `pydantic.ValidationError` |
| TC-UT-TS-013 | `Attachment(...)` 構築 + サニタイズ + ホワイトリスト | 正常系 / 異常系 | sha256 64 hex（成功）/ 63 文字（失敗）/ 大文字混入（失敗）/ filename `'../etc/passwd'`（失敗）/ filename `'CON.txt'`（失敗）/ mime_type `'text/html'`（失敗）/ size_bytes 10485761（失敗、10MiB+1） | 各々 `pydantic.ValidationError`、MSG-TS-009、message に違反内容のキーワード |
| TC-UT-TS-036 | TaskStatus enum 値網羅 | 正常系 | 6 値すべての StrEnum 比較 | `TaskStatus.PENDING == 'PENDING'` 等、StrEnum 仕様 |
| TC-UT-TS-037 | LLMErrorKind enum 値網羅 | 正常系 | 5 値すべて | 同上 |

### MSG 文言照合 + Next: hint 物理保証（test_invariants.py 後半、確定 J、受入基準 14）

**フィードバック原則の物理保証**（room §確定 I 踏襲、Norman R1 対応）: 全 MSG は **2 行構造**（1 行目 = 失敗事実 `[FAIL] ...`、2 行目 = 次の行動 `Next: ...`）。test 側で **`assert "Next:" in str(exc)`** を必須とし、hint 行が抜けたら CI で落ちる構造で凍結する。

| テストID | MSG ID | 例外型 | 入力 | 期待結果（1 行目: failure 完全一致 / 2 行目: hint 部分一致） |
|---------|--------|--------|------|---------|
| TC-UT-TS-046 | MSG-TS-001 | `TaskInvariantViolation(kind='terminal_violation')` | DONE の Task で `assign` 試行 | 1 行目: `[FAIL] Task is in terminal state DONE and cannot be modified: task_id=...` で始まる、2 行目: **`assert "Next:" in str(exc)`** + `"DONE/CANCELLED Tasks are immutable" in str(exc)` |
| TC-UT-TS-047 | MSG-TS-002 | `TaskInvariantViolation(kind='state_transition_invalid')` | PENDING の Task で `commit_deliverable` 試行 | 1 行目: `[FAIL] Invalid state transition: PENDING cannot perform 'commit_deliverable'` で始まる、2 行目: **`assert "Next:" in str(exc)`** + `"state_machine.py" in str(exc)` |
| TC-UT-TS-048 | MSG-TS-003 | `TaskInvariantViolation(kind='assigned_agents_unique')` | duplicates=[agent_a] | 1 行目: `[FAIL] Task assigned_agent_ids must not contain duplicates:` で始まる、2 行目: **`Next:`** + `"Deduplicate" in str(exc)` |
| TC-UT-TS-049 | MSG-TS-004 | `TaskInvariantViolation(kind='assigned_agents_capacity')` | 6 件の agent_ids | 1 行目: `[FAIL] Task assigned_agent_ids exceeds capacity: got 6, max 5`、2 行目: **`Next:`** + `"split work" in str(exc)` |
| TC-UT-TS-050 | MSG-TS-005 | `TaskInvariantViolation(kind='last_error_consistency')` | status=IN_PROGRESS, last_error='oops' | 1 行目: `[FAIL] Task last_error consistency violation:`、2 行目: **`Next:`** + `"Repository row integrity" in str(exc)` |
| TC-UT-TS-051 | MSG-TS-006 | `TaskInvariantViolation(kind='blocked_requires_last_error')` | block(reason, last_error='') | 1 行目: `[FAIL] Task block() requires non-empty last_error`、2 行目: **`Next:`** + `"1-10000 chars" in str(exc)` |
| TC-UT-TS-052 | MSG-TS-007 | `TaskInvariantViolation(kind='timestamp_order')` | created_at > updated_at | 1 行目: `[FAIL] Task timestamp order violation:`、2 行目: **`Next:`** + `"updated_at must be >= created_at" in str(exc)` |

## カバレッジ基準

- REQ-TS-001 〜 011 の各要件が**最低 1 件**のテストケースで検証されている（マトリクス参照）
- **state machine 全 13 遷移**が独立した正常系ケースで網羅されている（TC-UT-TS-003 / 008 / 030〜035 + cancel 4 状態 = 13 遷移）。table 不在の 29 経路は TC-UT-TS-004 で異常系網羅
- **DONE / CANCELLED terminal 物理確認**: TC-UT-TS-005（DONE × 10 ふるまい）/ TC-UT-TS-006（CANCELLED × 10 ふるまい）の 20 経路すべて
- **BLOCKED 契約 3 経路**（block 必須 / unblock クリア / 不変条件 last_error consistency）が独立した unit ケースで検証
- **責務境界 5 件**（current_stage_id / agent_ids / transition_id / Stage.kind / by_agent_id）すべてに「Aggregate 層で強制しない」ことを物理確認する unit ケース（TC-UT-TS-042, TC-UT-TS-043）
- **TaskInvariantViolation auto-mask（T3 防御、確定 I）**: webhook URL 含む last_error で例外発生時に message と detail の両方が伏字化されていることを TC-UT-TS-011 で確認
- MSG-TS-001 〜 007 の各文言が**静的文字列で照合**されており、加えて **`assert "Next:" in str(exc)` の hint 物理保証**を全 7 ケースで実施（TC-UT-TS-046〜052、確定 J / room §確定 I 踏襲）。「hint が抜けたら CI で落ちる」物理層でフィードバック原則を凍結
- MSG-TS-008 / 009 は `pydantic.ValidationError` 経路として TC-UT-TS-053 / TC-UT-TS-013 で確認（kind 概念なし、確定 J 例外型統一規約）
- MSG-TS-010 は application 層 `TaskService` 責務、本 feature 範囲外（後続 `feature/task-application` で起票）
- 受入基準 1 〜 14 の各々が**最低 1 件のユニット/結合ケース**で検証されている（E2E 不在のため戦略ガイドの「結合代替可」に従う）
- 受入基準 #16（再起動跨ぎ保持）は親 [`../system-test-design.md`](../system-test-design.md) の TC-E2E-TS-001 で E2E カバー。#17（DB masking）は repository sub-feature の TC-IT-TR-020-masking-* で IT カバー（lint/typecheck/coverage は §10 開発者品質基準）
- 確定 A〜K すべてに証拠ケース
- C0 目標: `domain/task/` 配下で **95% 以上**（domain 層基準、要件分析書 §非機能要求準拠）

## 人間が動作確認できるタイミング

本 feature は domain 層単独のため、人間が UI / CLI で触れるタイミングは無い。レビュワー / オーナーは以下で動作確認する。

- CI 統合後: `gh pr checks` で 7 ジョブ緑（lint / typecheck / test-backend / audit / fmt / commit-msg / no-ai-footer）
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/domain/task/test_task/ -v` → 全テスト緑
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.domain.task --cov-report=term-missing tests/domain/task/test_task/` → `domain/task/` 95% 以上
- 不変条件違反の実観測: 不正入力で MSG-TS-001〜007 が出ることを目視（実装担当が PR 説明欄に貼り付け）
- state machine 不正遷移の実観測: `uv run python -c "from tests.factories.task import DoneTaskFactory; t = DoneTaskFactory(); t.assign([])"` で MSG-TS-001 が出ることを目視
- BLOCKED 復旧の実観測: `uv run python -c "from tests.factories.task import BlockedTaskFactory; t = BlockedTaskFactory(); t2 = t.unblock_retry(); print(t2.last_error)"` で `None` が出ることを目視
- webhook auto-mask の実観測: `last_error='https://discord.com/api/webhooks/123/secret-token-..'` を含む状態で不変条件違反を発生させ、例外 message / detail に `<REDACTED:DISCORD_WEBHOOK>` が出ることを目視

後段で `feature/admin-cli`（`bakufu admin task list-blocked` / `retry-task` / `cancel-task`）/ `feature/http-api`（Task lifecycle API）/ `feature/chat-ui`（Phase 2）が完成したら、本 feature の Task を経由して `curl` / CLI で E2E 観測可能になる。

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      __init__.py
      task.py                              # TaskFactory / InProgressTaskFactory /
                                           # AwaitingReviewTaskFactory / BlockedTaskFactory /
                                           # DoneTaskFactory / CancelledTaskFactory /
                                           # DeliverableFactory / AttachmentFactory
                                           # （5 兄弟流 WeakValueDictionary レジストリ + is_synthetic()）
    domain/
      task/
        __init__.py
        test_task/                         # 4 ファイル分割（500 行ルール、empire-repo PR #29 教訓を最初から反映）
          __init__.py
          test_construction.py             # TC-UT-TS-001/002/014/040/044/045/053
          test_state_machine.py            # TC-UT-TS-003〜008/030〜035/038/039 + TC-IT-TS-001〜004
          test_invariants.py               # TC-UT-TS-009〜011/041〜043/046〜052
          test_vo.py                       # TC-UT-TS-012/013/036/037
```

**配置の根拠**:
- 5 兄弟と同方針: domain 層単独・外部 I/O ゼロのため `tests/integration/` ディレクトリは作らない
- characterization / raw / schema は本 feature では生成しない（外部 I/O ゼロ）
- factory のみは生成する（unit テストの入力バリエーション網羅のため）
- 本 feature では state machine の複雑性により **最初から 4 ファイル分割**（empire-repo PR #29 で test 単一ファイル 506 行 → 500 行ルール違反 → ディレクトリ分割の Norman 教訓を反映）。各ファイルを 200 行を目安、500 行ルール厳守
- `aggregate_validators.py` の helper 5 種は `Task` を構築 / メソッド呼び出しすることで間接的に経路網羅（5 兄弟と同方針）

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| （N/A） | 該当なし — 外部 I/O ゼロのため characterization 不要 | — | 後続 `feature/task-repository`（Issue #35）の Repository 実装（DB 永続化、`tasks.last_error` を `MaskedText` 列で配線、`task_deliverables.body_markdown` を `MaskedText` 列で配線、`storage.md` §逆引き表は既に登録済み）/ `feature/task-application` の application 層 service / `feature/external-review-gate` Aggregate / `feature/admin-cli`（retry-task / cancel-task）/ `feature/chat-ui`（Phase 2 Web UI）が起票時に Task 起点の characterization が発生する見込み |

**Schneier 申し送り（前 PR レビューより継承 + 本 PR 固有）**:

- **`Task.last_error` の secret マスキング**: 本 feature では文字列保持のみ。永続化前マスキング規則（[`storage.md`](../../design/domain-model/storage.md) §シークレットマスキング規則 / §逆引き表 既登録）の適用は `feature/task-repository` 責務として明示申し送り（detailed-design §データ構造（永続化キー）に `MaskedText` 列指定済）
- **`Deliverable.body_markdown` の secret マスキング**: 同上、Task aggregate 経由で持つ Deliverable VO の body_markdown は永続化前マスキング対象（既存 storage.md §逆引き表登録）
- **本 feature 固有の申し送り**:
  - `current_stage_id` / `transition_id` / `next_stage_id` の Workflow 内存在検証 / `agent_ids` の Room.members 内検証 / Stage.kind=EXTERNAL_REVIEW 検証 / `by_agent_id` ∈ assigned_agent_ids 検証 — すべて `TaskService` 系 application 層責務（確定 K の責務分離マトリクス 5 件）。`feature/task-application` 実装時に MSG-TS-010 + 5 件の参照整合性検査を漏れなく実装する申し送り
  - state machine table の追加・削除（`state_machine.py` の修正）は本 PR の凍結を破る変更となるため、後続 PR が遷移追加を試みる場合は本 detailed-design.md §確定 R1-A の遷移表を**同 PR で更新**することが必須。table のみの変更は実装と設計書の片肺になり退行リスクが高い
  - 並行性（同一 Task に複数 application 層が同時にふるまい呼び出し）は Repository 層の楽観排他 / Tx 境界で守る責務（`feature/task-repository` の Issue #35）。Aggregate 層では並行性に対する保護はせず、frozen + pre-validate で「単一 Tx 内の状態整合性」だけを保証する申し送り
  - `BLOCKED` 状態の Task に対する自動再試行禁止: Dispatcher は BLOCKED Task をスキップする責務（`feature/dispatcher` で起票）。本 PR では state machine table で「BLOCKED から自動的に IN_PROGRESS に戻る経路は存在しない」（`unblock_retry` は admin CLI 経由の人間介入のみ）を凍結
  - prompt injection 対策（敵対的 deliverable.body_markdown 検出 / ユーザー入力境界 escape）は `feature/llm-adapter` および `feature/http-api` の入力境界責務として残す。本 feature は長さ制約（last_error 1〜10000 / body_markdown 0〜1,000,000）のみを Pydantic field validator + `_validate_*` で Fail Fast

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-TS-001〜011 すべてに 1 件以上のテストケースがあり、不変条件 5 種が独立 unit で検証されている
- [ ] **state machine 全 13 遷移**が独立した正常系ケースで網羅されている（TC-UT-TS-003 / 008 / 030〜035 + cancel 4 状態）。table 不在の 29 経路は TC-UT-TS-004 で異常系網羅
- [ ] **DONE / CANCELLED terminal 物理確認**: TC-UT-TS-005, TC-UT-TS-006 で 14 経路すべて
- [ ] **BLOCKED 契約 3 経路**（block 必須 TC-UT-TS-007 / unblock クリア TC-UT-TS-008 / consistency TC-UT-TS-010）すべて
- [ ] **責務境界 5 件**（current_stage_id / agent_ids / transition_id / Stage.kind / by_agent_id）すべてが「Aggregate 内で強制しない」ことを TC-UT-TS-042 / 043 で物理確認
- [ ] **TaskInvariantViolation auto-mask（確定 I）**が webhook URL 含む last_error で例外発生時に message + detail 両方で伏字化されることを TC-UT-TS-011 で確認
- [ ] **MSG 2 行構造 + Next: hint（確定 J、room §確定 I 踏襲）**: TC-UT-TS-046〜052 で全 7 MSG-TS で `assert "Next:" in str(exc)` を CI 強制
- [ ] MSG-TS-008 / 009 が `pydantic.ValidationError` 経路として TC-UT-TS-053 / TC-UT-TS-013 で確認されている（例外型統一規約）
- [ ] MSG-TS-010 が application 層責務として明示され、本 feature テスト範囲外であることが明確
- [ ] 確定 A〜K（pre-validate / table ロック / NFC + strip しない / unblock クリア / cancel 4 状態 / agents 重複・容量 / by_agent_id 責務 / 連続安全性 / auto-mask / 例外型統一 + 2 行 MSG / 責務分離マトリクス）すべてに証拠ケースが含まれる
- [ ] frozen 不変性（TC-UT-TS-044）+ 構造的等価（TC-UT-TS-014）+ extra='forbid'（TC-UT-TS-045）が独立して検証されている
- [ ] 5 兄弟の WeakValueDictionary レジストリ方式と整合した factory 設計になっている
- [ ] 外部 I/O ゼロの主張が basic-design.md / ../feature-spec.md §8 制約・前提 と整合している
- [ ] **テストファイル分割（4 ファイル）が basic-design.md §モジュール構成 / detailed-design.md §設計判断補足と整合**（empire-repo PR #29 の 500 行ルール教訓を最初から反映）
- [ ] Schneier 申し送り（`Task.last_error` / `Deliverable.body_markdown` の persistence-foundation 経由マスキング配線 / state machine table の修正同期 / 並行性は Repository 責務 / BLOCKED 自動再試行禁止 / prompt injection は別 feature 責務）が次レビュー時に確認可能な形で test-design および設計書に記録されている
