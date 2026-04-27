# 要求分析書

> feature: `external-review-gate`
> Issue: [#38 feat(external-review-gate): ExternalReviewGate Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/38)
> 凍結済み設計: [`docs/architecture/domain-model/aggregates.md`](../../architecture/domain-model/aggregates.md) §ExternalReviewGate / [`value-objects.md`](../../architecture/domain-model/value-objects.md) §AuditEntry / §列挙型一覧（ReviewDecision / AuditAction）/ [`storage.md`](../../architecture/domain-model/storage.md) §snapshot 凍結方式

## 人間の要求

> Issue #38:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の **7 番目（最後）の Aggregate** として **ExternalReviewGate Aggregate Root** を実装する。Stage の `EXTERNAL_REVIEW` kind 到達時に application 層が生成する **独立 Aggregate Root**（Task の子ではない）。**MVP の核心要件「AI 協業による品質向上を、人間チェックポイントで担保する」**を Aggregate モデル上で実現する。

## 背景・目的

### 現状の痛点

1. M1 ドメイン骨格 6 兄弟（empire / workflow / agent / room / directive / task）が PR #15〜#42 で完走したが、**MVP 核心要件「人間チェックポイント」を表現する Aggregate がない**。task #37 PR #42 §確定 A-2 で `task.approve_review()` / `task.reject_review()` の dispatch 表は凍結したが、それを呼ぶ起点（Gate APPROVED / REJECTED）の Aggregate が存在しないと、`mvp-scope.md` §M7「V モデル E2E」で「CEO が承認/差戻」経路が成立しない
2. `aggregates.md` §ExternalReviewGate で属性 / ふるまい / 不変条件が凍結済みだが、Pydantic v2 BaseModel として実体化されていない。後続 `feature/external-review-gate-repository`（Issue #36）が VO 構造を真実源として SQLite 配線を始められない
3. **独立 Aggregate である理由（Task の子ではない）**が概念的には凍結されているが、本 PR で実装パターンとして固定しないと、後続 PR で「Task の子にしたほうが楽だった」という退行誘惑が起きやすい
4. **`decision` PENDING → 1 回のみ遷移**を Aggregate 内不変条件として凍結し、**`audit_trail` append-only** + **`deliverable_snapshot` 不変**の 3 つの不変条件を物理的に守る構造が要凍結

### 解決されれば変わること

- `feature/external-review-gate-repository`（Issue #36）が Aggregate VO 構造を真実源として SQLite 配線可能
- application 層 `GateService.approve()` / `reject()` が完了したら、`task.approve_review()` / `task.reject_review()` を**静的 dispatch**で呼ぶ経路（task #42 §確定 A-2 の連携先）が成立
- empire / workflow / agent / room / directive / task の確立済みパターンを **7 例目（最後）**として揃え、**M1 ドメイン骨格の完走**を達成
- task #42 で凍結した state machine + dispatch 表 + Aggregate 境界保護パターンを Gate でも踏襲（4 値 state machine、4 method 専用分離、`decision` 引数による暗黙 dispatch なし）

### ビジネス価値

- bakufu の核心思想「AI 協業による品質向上を、人間チェックポイントで担保する」を Aggregate 単位で表現する。CEO が UI で「approve / reject」を押す経路が Domain 層で安全にモデル化される
- Task と Gate の Aggregate 境界が明確化されることで、application 層 `GateService` が dispatch 担当として責務を持つ設計が固定（task #42 §確定 A-2 連携先）
- **複数ラウンド対応**（同 Task の同 Stage で REJECTED → 再 directive → 別 Gate 生成）の Aggregate 履歴保持が成立、`audit_trail` で「誰がいつ何を見たか / 判断したか」を全件凍結

## 議論結果

### 設計担当による採用前提

- ExternalReviewGate Aggregate は **Pydantic v2 BaseModel + `model_config.frozen=True` + `model_validator(mode='after')`**（6 兄弟と同じ規約）
- `feedback_text` は **NFC 正規化のみ、strip しない**（`Persona.prompt_body` / `PromptKit.prefix_markdown` / `Directive.text` / `Task.last_error` と同規約）
- `task_id` / `stage_id` / `reviewer_id` の存在検証は **application 層責務**（`GateService.create()` / `approve()` 系で `TaskRepository` / `WorkflowRepository` / `OwnerRepository` 経由）。Aggregate 内では UUID 型として valid までしか守らない
- `decision` PENDING → 1 回のみ遷移（task #42 §確定 R1-A の state machine 採用）
- ディレクトリ層分離は task と同パターン（`backend/src/bakufu/domain/external_review_gate/` 配下に `external_review_gate.py` / `aggregate_validators.py` / `state_machine.py` / `__init__.py`）
- 状態変更ふるまい 4 method（approve / reject / cancel / record_view）は **すべて新インスタンス返却**（pre-validate 方式、6 兄弟踏襲）
- `ExternalReviewGateInvariantViolation` は 6 兄弟と同じく **`mask_discord_webhook` + `mask_discord_webhook_in` を `super().__init__` 前に強制適用**（`feedback_text` / `audit_trail[*].comment` に webhook URL 混入経路の防衛線）

### 却下候補と根拠

| 候補 | 却下理由 |
|-----|---------|
| ExternalReviewGate を Task Aggregate Root の子（Entity）にする | Aggregate 境界違反。寿命が異なる（Stage 終了後も Gate は履歴として残る、複数ラウンドでは 1 Stage に複数 Gate）/ Tx 境界が異なる（CEO の承認は Agent 作業と非同期）/ DDD 原則違反。`aggregates.md` §ExternalReviewGate で **独立 Aggregate Root** と凍結済み、本 PR で再凍結 |
| `decision: ReviewDecision` を引数にとる単一 method `decide(decision, ...)` | task #42 §確定 A-2 の議論と同じ：暗黙 dispatch、Tell Don't Ask 違反。**4 method 専用分離**で凍結（approve / reject / cancel / record_view） |
| `record_view` を冪等にして「同 owner が 2 回閲覧したら no-op」にする | audit_trail は履歴であり、複数閲覧は事実として記録されるべき（誰が / いつ / 何度見たかが監査対象）。冪等にすると CEO の閲覧パターンが追跡できなくなり、監査要件と矛盾 |
| `audit_trail` を `set[AuditEntry]` で保持 | 順序保持必要（時系列で誰が何をしたか追える必要）+ 同 owner / 同時刻でも複数エントリ可。list 必須、append-only 不変条件で守る |
| `deliverable_snapshot` を Repository が `task.deliverables[stage_id]` を参照する形（snapshot inline コピーをやめる） | `storage.md` §snapshot 凍結方式で「inline コピー」と凍結済み。Deliverable 側で添付差し替えがあっても Gate snapshot は不変、という監査要件を満たすため inline コピー必須 |
| `feedback_text` を Aggregate 構築時に必須化（空文字列を禁止） | approve 時は comment が短い or 空でも valid（CEO の判断時に「OK」のみで approve できる UX を残す）。0〜10000 文字の幅広 range で柔軟性確保 |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: 独立 Aggregate である理由の凍結（concept→implementation の固定）

`aggregates.md` §ExternalReviewGate で「独立 Aggregate Root」と凍結済みだが、本 PR で実装パターンとして以下の 3 点を再凍結する:

| 凍結項目 | 内容 |
|---|---|
| **(1) エンティティ寿命が Stage と一致しない** | 差し戻し後も Gate は履歴として保持される（複数ラウンド可、同 Task の同 Stage で REJECTED → 再 directive → 別 Gate 生成）。Stage が完了しても Gate.audit_trail に「誰が承認/差戻したか」を残す監査要件 |
| **(2) トランザクション境界が異なる** | Task の状態遷移と Gate の判断は別の人間（Agent vs CEO）が異なるタイミングで行う。Gate.approve は CEO の UI 操作 → application 層 `GateService.approve()` → 同一 Tx 内で Gate 永続化 + Task.approve_review() 呼び出し（**ただし Task / Gate Aggregate は別 Tx で永続化、application 層が UoW で連結**）|
| **(3) 複数 Aggregate にまたがる更新を application 層で管理** | task #42 §確定 A-2 の dispatch 表で「Gate APPROVED → `task.approve_review()`」の連鎖を `GateService` が application 層で実行。Task / Gate どちらも frozen、各 Aggregate の不変条件は自身で守る |

##### Task / Gate の責務境界（task #42 §確定 K と直交独立）

| 責務 | 担当 |
|---|---|
| Gate の `decision` 遷移（PENDING → APPROVED/REJECTED/CANCELLED） | **本 PR ExternalReviewGate Aggregate** |
| Task の state 遷移（AWAITING_EXTERNAL_REVIEW → IN_PROGRESS） | task #37 Task Aggregate |
| Gate decision → Task method dispatch（APPROVED → `approve_review`、REJECTED → `reject_review`） | application 層 `GateService.approve()` / `reject()`（後続 PR） |

本 PR の Aggregate は **Task method を一切 import しない**（task #42 §確定 A-2 の Aggregate 境界保護を本 PR でも遵守）。

#### 確定 R1-B: state machine（4 値、4 method 専用分離、task #42 §確定 A-2 パターン継承）

`ReviewDecision` 4 値 + ふるまい 4 method の dispatch 表:

| method | PENDING | APPROVED | REJECTED | CANCELLED |
|---|---|---|---|---|
| `approve` | → APPROVED | ✗ | ✗ | ✗ |
| `reject` | → REJECTED | ✗ | ✗ | ✗ |
| `cancel` | → CANCELLED | ✗ | ✗ | ✗ |
| `record_view` | → PENDING（自己遷移、audit_trail 追加のみ）| → APPROVED（自己遷移、同上）| → REJECTED（自己遷移）| → CANCELLED（自己遷移）|

合計 **7 ✓ 遷移**（PENDING からの 3 遷移 + record_view 4 自己遷移）+ 9 ✗ セル（terminal 違反）。**task #42 §確定 A-2 と同パターン**で:

- method 名 = state machine action 名で 1:1 対応（`decision: ReviewDecision` 引数による暗黙 dispatch なし）
- `decided_at` は approve / reject / cancel で `decision != PENDING` に遷移する瞬間に設定、record_view では更新しない
- DONE / CANCELLED に相当する terminal は本 Aggregate にはないが、**「PENDING 以外からの decision 遷移は禁止（`record_view` 以外）」**を terminal 同等に扱う

#### 確定 R1-C: `audit_trail` append-only 不変条件

`audit_trail: list[AuditEntry]` は **既存エントリの編集禁止 + 新エントリ追加のみ**。`_validate_audit_trail_append_only` で:

| 検査内容 | 動作 |
|---|---|
| 既存 entry の改変（list 内オブジェクトの構造的等価性が崩れる）| `ExternalReviewGateInvariantViolation(kind='audit_trail_append_only')` で Fail Fast |
| 新規 entry の prepend（先頭挿入で順序破壊）| 同上 |
| 新規 entry の append のみ | OK |

##### `record_view` の冪等性なし契約

同 owner_id が複数回 `record_view` を呼び出すと audit_trail に複数エントリが積まれる:

| 入力 | 期待 |
|---|---|
| `gate.record_view(owner_a, t_1)` | audit_trail に 1 件 |
| `gate.record_view(owner_a, t_2)` | audit_trail に 2 件（同 owner、異なる時刻）|
| `gate.record_view(owner_a, t_1)` （同時刻）| audit_trail に 2 件（重複でも履歴として記録）|

監査要件として「誰がいつ何度見たか」を完全保持。

#### 確定 R1-D: `deliverable_snapshot` 不変条件凍結

`deliverable_snapshot: Deliverable`（task #37 で実体化済みの VO）は Gate 生成時に inline コピー、**以後不変**:

| 検査内容 | 動作 |
|---|---|
| 構築時の `deliverable_snapshot` が `Deliverable` 型として valid | OK（型レベル検証 + Deliverable 自体の VO 不変条件）|
| 状態変更ふるまい（approve / reject / cancel / record_view）で `deliverable_snapshot` を変更 | `_validate_snapshot_immutable` で Fail Fast |
| ただし record_view 等で `audit_trail` を追加するのは snapshot 不変性に違反しない | snapshot と audit_trail は独立属性 |

`storage.md` §snapshot 凍結方式の inline コピー方式を Aggregate 内 VO 構造で凍結。実際の inline コピー実装（Repository が Task の Deliverable を Gate row にコピー）は **`feature/external-review-gate-repository`（Issue #36）の責務**として申し送る（本 PR スコープ外）。

#### 確定 R1-E: `decided_at` consistency 不変条件

`decided_at: datetime | None` は `decision != PENDING` 時のみ非 None:

| `decision` | `decided_at` | 判定 |
|---|---|---|
| PENDING | None | OK |
| PENDING | 非 None | NG → `decided_at_inconsistent` |
| APPROVED / REJECTED / CANCELLED | 非 None | OK |
| APPROVED / REJECTED / CANCELLED | None | NG → `decided_at_inconsistent` |

#### 確定 R1-F: `ExternalReviewGateInvariantViolation` の auto-mask（task PR #42 §確定 R1-F 踏襲）

`feedback_text` / `audit_trail[*].comment` に CEO が webhook URL を貼り付ける経路があり得るため、6 兄弟と同パターン:

1. `super().__init__` 前に `mask_discord_webhook(message)` を message に適用
2. `detail` に対し `mask_discord_webhook_in(detail)` を再帰的に適用
3. `kind` は enum 文字列のため mask 対象外
4. その後 `super().__init__(masked_message)` を呼ぶ

#### 確定 R1-G: 例外型統一規約と MSG 2 行構造（room §確定 I 踏襲）

| 違反種別 | 例外型 | 発生レイヤ | 凍結する `kind` 値 |
|---|---|---|---|
| 構造的不変条件違反 | `ExternalReviewGateInvariantViolation` | Aggregate `model_validator(mode='after')` または各ふるまい入口 | `decision_already_decided` / `decided_at_inconsistent` / `snapshot_immutable` / `feedback_text_range` / `audit_trail_append_only` |
| 型違反 / 必須欠落 | `pydantic.ValidationError` | Pydantic 型バリデーション | — |
| application 層の参照整合性違反 | `TaskNotFoundError` / `OwnerNotFoundError` / `GateNotFoundError` | `GateService` 系 | — |

MSG-GT-001〜007 は **2 行構造**（`[FAIL] failure` + `Next: action`）で凍結し、test-design.md の TC-UT-GT-NNN で `assert "Next:" in str(exc)` を CI 物理保証する規約。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 個人開発者 CEO（堀川さん想定） | Gate を Web UI で approve / reject | GitHub / Docker / CLI 日常使用 | UI で deliverable_snapshot を確認 → approve コメント書き込み → Task が次 Stage に進む | 1 クリックで判断 → Task に連鎖 |
| 後続 Issue 担当（バックエンド開発者） | `feature/external-review-gate-repository`（Issue #36）/ `feature/external-review-gate-application` 実装者 | DDD 経験あり | 本 PR の VO 構造を真実源として読み、Repository / Service を実装 | 設計書を素直に実装するだけ、Aggregate 境界違反を犯さない |
| 監査担当（CEO 自身が兼務） | 後日 audit_trail を確認 | CLI / SQL 操作可能 | `bakufu admin gate show <gate_id>` で audit_trail を時系列表示 → 「誰がいつ何を見たか / 判断したか」を確認 | 監査ログから判断履歴を追跡 |

##### ペルソナ別ジャーニー（個人開発者 CEO）

1. **Stage が EXTERNAL_REVIEW kind に到達**: Agent が成果物 commit → application 層 `TaskService.request_external_review(task_id)` → `task.request_external_review()` が AWAITING_EXTERNAL_REVIEW に遷移（task #37）
2. **Gate 生成**: application 層 `GateService.create(task_id, stage_id, deliverable, reviewer_id)` が Deliverable を inline コピーして Gate を構築 → `ExternalReviewGate(id=uuid4(), task_id=..., stage_id=..., deliverable_snapshot=deliverable, reviewer_id=..., decision=PENDING, feedback_text='', audit_trail=[], created_at=now, decided_at=None)` → GateRepository.save
3. **CEO の閲覧**: UI で Gate を開く → `gate.record_view(owner_id, viewed_at)` で audit_trail 追加（複数閲覧可、§確定 R1-C）
4. **承認 or 差戻**: CEO が UI で approve ボタン → `gate.approve(by_owner_id, comment)` → PENDING → APPROVED、`decided_at` 設定、audit_trail に APPROVED エントリ追加 → application 層 `GateService.approve()` が **同一 application Tx 内で `task.approve_review(transition_id, by_owner_id, next_stage_id)`** を呼ぶ（Task / Gate の Aggregate 境界は別 Tx だが、application 層 UoW で連結）
5. **Task 進行**: Task が AWAITING_EXTERNAL_REVIEW → IN_PROGRESS（次 Stage）に遷移、Gate は履歴として保持される

##### ジャーニーから逆算した受入要件

- ジャーニー 2: `ExternalReviewGate(id, task_id, stage_id, deliverable_snapshot, reviewer_id, decision=PENDING, feedback_text='', audit_trail=[], created_at, decided_at=None)` で valid な Gate が構築できる
- ジャーニー 3: `record_view(owner_id, viewed_at)` で audit_trail に閲覧エントリが追加、複数回呼び出しで複数エントリ
- ジャーニー 4: `approve(by_owner_id, comment)` / `reject(by_owner_id, comment)` で PENDING → APPROVED/REJECTED、`decided_at` が設定される
- ジャーニー全般: `feedback_text` / `audit_trail[*].comment` に webhook URL 混入しても永続化前マスキング、例外経路でも auto-mask（§確定 R1-F）

bakufu システム全体のペルソナは [`docs/architecture/context.md`](../../architecture/context.md) §4 を参照。

## 前提条件・制約

| 区分 | 内容 |
|-----|------|
| 既存技術スタック | Python 3.12+ / Pydantic v2 / pyright strict / pytest |
| 既存 CI | lint / typecheck / test-backend / audit |
| 既存ブランチ戦略 | GitFlow（CONTRIBUTING.md §ブランチ戦略） |
| コミット規約 | Conventional Commits |
| ライセンス | MIT |
| ネットワーク | 該当なし — domain 層 |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |

## 機能一覧

| 機能ID | 機能名 | 概要 | 優先度 |
|--------|-------|------|--------|
| REQ-GT-001 | ExternalReviewGate 構築 | コンストラクタで全属性を受け取り、不変条件検査を経て valid な Gate を返す（永続化からの復元と新規生成の両経路に対応） | 必須 |
| REQ-GT-002 | approve | `approve(by_owner_id, comment)` で PENDING → APPROVED、`decided_at` 設定、audit_trail に APPROVED エントリ追加 | 必須 |
| REQ-GT-003 | reject | `reject(by_owner_id, comment)` で PENDING → REJECTED、同上 | 必須 |
| REQ-GT-004 | cancel | `cancel(by_owner_id, reason)` で PENDING → CANCELLED、同上 | 必須 |
| REQ-GT-005 | record_view | `record_view(by_owner_id, viewed_at)` で audit_trail に VIEWED エントリ追加（decision 自己遷移、4 状態すべてで許可、§確定 R1-C 冪等性なし） | 必須 |
| REQ-GT-006 | 不変条件検査 | コンストラクタ末尾と全ふるまい末尾で実行（5 種: decision_already_decided / decided_at_inconsistent / snapshot_immutable / feedback_text_range / audit_trail_append_only） | 必須 |

## Sub-issue 分割計画

本 Issue は単一 Aggregate に閉じる粒度のため Sub-issue 分割は不要。1 PR で 5 設計書 + 実装 + ユニットテストを完結させる（6 兄弟と同方針）。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 単一 PR | REQ-GT-001〜006 | ExternalReviewGate Aggregate + AuditEntry VO + ユニットテスト | M1 6 兄弟（empire / workflow / agent / room / directive / task）マージ済み + Deliverable VO（task PR #42 で実体化済み） |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 不変条件検査は O(N) where N = `audit_trail` 件数（最大想定 100 程度）。1ms 未満 |
| 可用性 | 該当なし — domain 層 |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 95% 以上 |
| 可搬性 | 純 Python のみ |
| セキュリティ | `feedback_text` / `audit_trail[*].comment` に webhook URL / API key 混入し得る。永続化前にマスキング規則の適用対象（後続 Repository PR で `MaskedText` 配線責務）。`ExternalReviewGateInvariantViolation` は webhook URL auto-mask（6 兄弟と同パターン）|

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | `ExternalReviewGate(id, task_id, stage_id, deliverable_snapshot, reviewer_id, decision=PENDING, feedback_text='', audit_trail=[], created_at, decided_at=None)` で valid な Gate 構築 | TC-UT-GT-001 |
| 2 | ReviewDecision 4 種すべてで構築可能（永続化復元、ただし `decided_at` consistency が成立）| TC-UT-GT-002 |
| 3 | `approve(by_owner_id, comment)` で PENDING → APPROVED、`decided_at` 設定、audit_trail に APPROVED エントリ追加 | TC-UT-GT-003 |
| 4 | `reject` / `cancel` も同上、対応する decision 値に遷移 | TC-UT-GT-004 |
| 5 | PENDING 以外からの `approve` / `reject` / `cancel` で `decision_already_decided` raise | TC-UT-GT-005 |
| 6 | `record_view` で audit_trail に VIEWED エントリ追加、4 状態すべてで許可、複数回呼び出しで複数エントリ（§確定 R1-C 冪等性なし）| TC-UT-GT-006 |
| 7 | `decided_at` consistency: PENDING 時は None、他は非 None | TC-UT-GT-007 |
| 8 | `deliverable_snapshot` を変更しようとすると `snapshot_immutable` raise（frozen 経由でも検査）| TC-UT-GT-008 |
| 9 | `audit_trail` の既存エントリ改変が `audit_trail_append_only` で raise | TC-UT-GT-009 |
| 10 | `feedback_text` 0 / 10000 は valid、10001 は `feedback_text_range` raise | TC-UT-GT-010 |
| 11 | `ExternalReviewGateInvariantViolation` の `message` / `detail` 内 webhook URL が `<REDACTED:DISCORD_WEBHOOK>` に伏字化（auto-mask）| TC-UT-GT-011 |
| 12 | エラーメッセージ 2 行構造（`[FAIL] ...` + `Next: ...`）、`assert "Next:" in str(exc)` で CI 物理保証 | TC-UT-GT-001〜011 全件 |
| 13 | Gate は frozen で構造的等価判定 | TC-UT-GT-012 |
| 14 | `pyright --strict` および `ruff check` がエラーゼロ | CI lint / typecheck |
| 15 | カバレッジが `domain/external_review_gate/` で 95% 以上 | pytest --cov |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Gate.feedback_text | CEO の判断コメント（自然言語、長文の可能性） | **高**（webhook URL / API key が混入し得る、Repository 永続化前マスキング必須）|
| Gate.audit_trail[*].comment | audit エントリのコメント | **高**（同上） |
| Gate.deliverable_snapshot | Deliverable VO の inline copy | **高**（body_markdown が高機密、Deliverable 自体の masking で守る）|
| Gate.id / task_id / stage_id / reviewer_id | UUID 識別子 | 低 |
| Gate.decision | enum（ReviewDecision 4 値） | 低 |
| Gate.created_at / decided_at | UTC datetime | 低 |
