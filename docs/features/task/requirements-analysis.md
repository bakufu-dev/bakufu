# 要求分析書

> feature: `task`
> Issue: [#37 feat(task): Task Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/37)
> 凍結済み設計: [`docs/architecture/domain-model/aggregates.md`](../../architecture/domain-model/aggregates.md) §Task / §Conversation / §ExternalReviewGate / [`value-objects.md`](../../architecture/domain-model/value-objects.md) §列挙型一覧（`TaskStatus` / `LLMErrorKind`） / §Conversation 構成要素 / [`storage.md`](../../architecture/domain-model/storage.md) §Deliverable / §Attachment / §シークレットマスキング適用先（`Task.last_error`）

## 人間の要求

> Issue #37:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の **6 番目の Aggregate**（M1 最大難所）として **Task Aggregate Root** を実装する。Task は CEO directive から生成され、Workflow の Stage を進行しながら Agent が deliverable を commit するワークフロー実行単位。**TaskStatus 6 種の state machine** + **BLOCKED 隔離経路** + **External Review Gate との連携**を持つ、MVP の核心ユースケース「CEO directive → Vモデル工程進行 → 完了」の駆動エンジン。

## 背景・目的

### 現状の痛点

1. M1 ドメイン骨格 5 兄弟（empire / workflow / agent / room / directive）が PR #15 / #16 / #17 / #22 / #28 で完走した。M2 永続化基盤（PR #23）+ empire-repository（PR #29 / #30）も完了。**しかし MVP 核心ユースケースの「CEO directive → Vモデル工程進行 → DONE」を駆動する Task Aggregate がないため、`mvp-scope.md` §M7「V モデル E2E」へ至る経路が Task で塞がれている**
2. 後続 `feature/external-review-gate` は `task_id` を介して Task を参照する設計（[`aggregates.md`](../../architecture/domain-model/aggregates.md) §ExternalReviewGate 属性表）。Task がないと Gate 構築の参照整合性検査が成立しない
3. directive #28 は `link_task(task_id)` で Task を紐付けるが、紐付け先となる Task Aggregate Root が存在しない（directive 設計書 §確定 R1-B が `feature/directive-application` で実体化される前提条件として Task が必要）
4. **TaskStatus 6 種 + 13 遷移**を Aggregate 内で正しく扱える state machine の表現方式が未確定。state machine が複雑なため「ふるまい毎に if 分岐を書く」実装になると遷移ルールが散逸し、後続 PR で「ある経路だけ遷移検査が抜けている」という退行が発生しやすい。さらに `advance` 単一 method による暗黙 dispatch（current_status と引数で内部分岐）は **3 PR 連鎖（task-repository / external-review-gate-aggregate / external-review-gate-repository）の前提に揺れを残す**ため、method × current_status → action の対応を**1:1 静的に凍結**する必要がある（Steve R2 指摘で本 PR スコープ完了の要件）
5. **`BLOCKED` 隔離経路**（LLM Adapter 復旧不能エラー → 人間介入待ち）の Aggregate 内表現も未確定。`last_error` の必須性 / auto-mask / unblock 経路の冪等性などの構造契約が要凍結

### 解決されれば変わること

- `feature/external-review-gate` Aggregate Issue が Task 参照を前提に着手可能になる（`task_id` 必須属性が確定する）
- M2 後段の `feature/task-repository`（Issue #35）が Aggregate VO 構造を真実源として SQLite 配線を始められる（`Task.last_error` の `MaskedText` 配線、`deliverables` の `body_markdown` の `MaskedText` 配線）
- empire / workflow / agent / room / directive の確立済みパターン（pre-validate / frozen Pydantic v2 / `_validate_*` helper / 例外 auto-mask / ディレクトリ層分離 / 例外型統一規約 / MSG 2 行構造）を **6 例目**として揃え、M1 完走の最後のピースが埋まる
- **state machine の決定表方式**を本 feature で凍結することで、後続 `feature/external-review-gate` の `decision: ReviewDecision`（PENDING/APPROVED/REJECTED/CANCELLED の 4 種 state machine）でも同パターンが使える

### ビジネス価値

- bakufu の核心思想「CEO directive → Vモデル工程進行 → 外部レビューで人間が承認」のうち**最も中核となる工程駆動**を Aggregate 単位で表現する。Task の遷移が安全に書けて初めて「Agent が成果物を作る → 人間がレビュー → DONE」が成立する
- **`BLOCKED` の明示的隔離**により「LLM API 認証切れで無限再試行 → 課金事故」を構造で防ぐ。これは ai-team から bakufu が学んだ運用知見の Aggregate 化
- AI 協業による品質向上を**人間チェックポイント（External Review Gate）でゲート**する設計を Task ↔ Gate の連携経路として固定する

## 議論結果

### 設計担当による採用前提

- Task Aggregate は **Pydantic v2 BaseModel + `model_config.frozen=True` + `model_validator(mode='after')`**（empire / workflow / agent / room / directive と同じ規約）
- `last_error` は **NFC 正規化のみ、strip しない**（`Persona.prompt_body` / `Directive.text` と同規約。LLM Adapter の改行を含む長文エラーを保持するため、`MaskedText` 配線で永続化前マスキング）
- `current_stage_id` の Workflow 内存在検証は **application 層責務**（`TaskService.advance()` で `WorkflowRepository.find_by_id` 経由）。Aggregate 内では UUID 型として valid までしか守らない
- `assigned_agent_ids` は **List**（順序保持、empire の `agents: list[AgentRef]` 同様）+ Aggregate 内不変条件で重複チェック（`_validate_assigned_agents_unique`）
- `deliverables: dict[StageId, Deliverable]` は dict キー一意性を Pydantic 型レベルで保証、Stage 集合内存在は application 層責務
- ディレクトリ層分離は room / directive と同パターン（`backend/src/bakufu/domain/task/` 配下に `task.py` / `aggregate_validators.py` / `state_machine.py` / `__init__.py`）
- 状態変更ふるまいは新インスタンス返却の pre-validate 方式（agent §確定 D / room §確定 D / directive §確定 A 踏襲）
- `TaskInvariantViolation` は workflow / agent / room / directive と同じく **`mask_discord_webhook` + `mask_discord_webhook_in` を `super().__init__` 前に強制適用**（`last_error` フィールド + `deliverables[*].body_markdown` に webhook URL / API key 混入経路の防衛線）

### 却下候補と根拠

| 候補 | 却下理由 |
|-----|---------|
| state machine を `if status == X and action == Y: ...` の if 分岐で書く | 6 種 × 8 遷移 = 48 経路のうち実際に許可されるのは 8 遷移のみ。if 分岐実装は「許可されない 40 経路を暗黙で禁止」する形になり、後続 PR で「assign を BLOCKED 状態でも呼べる」ような誤実装が紛れ込む退行リスクが高い。**enum-based decision table** で「(current_status, action) → next_status の表」として 8 遷移を **明示列挙**する方式を採用 |
| `current_stage_id` の Workflow 内存在を Aggregate 内で守る | Workflow Aggregate Root を import する必要があり、Aggregate 境界を跨ぐ責務散逸。directive §確定 G の `target_room_id` 検証を application 層に押し出した先例と同じ責務分離 |
| `assigned_agent_ids` を `Set[AgentId]` で保持 | empire の `agents: list[AgentRef]` で**順序保持**を凍結済み（割当順が UI 表示順を決める）。Set にすると pydantic の serialize で順序が非決定論になり、Repository 永続化時に diff ノイズが出る。List + 重複チェック helper で凍結 |
| `last_error` を Aggregate 内で `datetime.now(UTC)` 自動付加 | テスト容易性が下がる（freezegun が要る）。application 層 `TaskService.block(task, reason, error_text)` で生成して引数渡しする方が clean（directive §確定 G の `created_at` を引数で受け取る方針と対称） |
| `block(reason, last_error)` を Aggregate 内で auto-mask | `TaskInvariantViolation` の auto-mask とは異なり、`last_error` 属性そのものは VO 値として raw 保持し、永続化前マスキング（task-repository §`MaskedText` 配線）で適用する。Aggregate 内で値を改変するとログ表示・UI 表示・例外メッセージで「raw 必要」「mask 必要」の使い分けが application 層でできなくなる。directive §`Directive.text` と同方針（domain は raw、Repository が mask） |
| `deliverables` を `list[Deliverable]` にして StageId フィールドを Deliverable 内に持つ | `dict[StageId, Deliverable]` は「Stage ごとに最新の成果物 1 件」を Pydantic 型レベルで保証する（同 Stage への 2 回目 commit は dict 上書き）。list だと「同 Stage に複数 Deliverable が並ぶ」状態を Aggregate 内不変条件で別途チェックする必要があり、構造が複雑化する。MVP は「Stage ごとに最新成果物のみ」設計（`aggregates.md` §Task で `Dict[StageId, Deliverable]` 凍結済み）|
| `unblock_retry()` を冪等にして「IN_PROGRESS の Task に呼んでも no-op」にする | state machine の他の遷移（`assign` / `advance` / `cancel`）と一貫しない。「該当しない状態で呼ばれたら Fail Fast」を統一規則として全ふるまい共通で守る。BLOCKED 以外で `unblock_retry` を呼ぶのはバグなので素直に raise させる |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: state machine は **enum-based decision table** で凍結（**13 遷移、method 名 = action 名で 1:1**、Steve R2 指摘応答）

`TaskStatus` 6 種 + Task method 10 種 = 60 経路のうち**実際に許可されるのは 13 遷移のみ**を `state_machine.py` の dict / Mapping で**明示列挙**する。**action 名 = Task method 名で 1:1 対応**（detailed-design.md §確定 A-2 dispatch 表で凍結、揺れゼロ）:

| キー | 値 |
|---|---|
| `(PENDING, 'assign')` | `IN_PROGRESS` |
| `(PENDING, 'cancel')` | `CANCELLED`（terminal） |
| `(IN_PROGRESS, 'commit_deliverable')` | `IN_PROGRESS`（自己遷移、deliverables 更新のみ） |
| `(IN_PROGRESS, 'request_external_review')` | `AWAITING_EXTERNAL_REVIEW` |
| `(IN_PROGRESS, 'advance_to_next')` | `IN_PROGRESS`（自己遷移、current_stage_id 更新） |
| `(IN_PROGRESS, 'complete')` | `DONE`（terminal） |
| `(IN_PROGRESS, 'block')` | `BLOCKED` |
| `(IN_PROGRESS, 'cancel')` | `CANCELLED`（terminal） |
| `(AWAITING_EXTERNAL_REVIEW, 'approve_review')` | `IN_PROGRESS` |
| `(AWAITING_EXTERNAL_REVIEW, 'reject_review')` | `IN_PROGRESS` |
| `(AWAITING_EXTERNAL_REVIEW, 'cancel')` | `CANCELLED`（terminal） |
| `(BLOCKED, 'unblock_retry')` | `IN_PROGRESS` |
| `(BLOCKED, 'cancel')` | `CANCELLED`（terminal） |

DONE / CANCELLED を起点とする遷移は **table に存在しない** ことで明示禁止（lookup 失敗 → `TaskInvariantViolation(kind='terminal_violation')` または `'state_transition_invalid'`）。`advance` 単一 method による暗黙 dispatch は不採用（**`approve_review` / `reject_review` / `advance_to_next` / `complete` の 4 method 専用分離**で凍結、Steve R2 指摘応答、詳細は detailed-design.md §確定 A-2）。

理由:

- 13 遷移を表で読めるため設計書 / 実装 / テストの 3 箇所で同じ表を写経でき、退行検出が容易
- **action 名 = Task method 名 = audit_log の操作名**で 3 PR 連鎖（task-repository / external-review-gate-aggregate / external-review-gate-repository）に揺れを残さない
- 後続 `feature/external-review-gate` の 4 種 state machine（PENDING/APPROVED/REJECTED/CANCELLED）でも同パターンが流用できる
- room §確定 I の例外型統一規約（`*InvariantViolation` の `kind` で違反種別を識別）と相性が良い

#### 確定 R1-B: `status == DONE` / `CANCELLED` は terminal、**全ふるまいで先頭 Fail Fast**

`assign` / `commit_deliverable` / `request_external_review` / `approve_review` / `reject_review` / `advance_to_next` / `complete` / `cancel` / `block` / `unblock_retry` の **全 10 ふるまい入口**で:

1. `if self.status in {TaskStatus.DONE, TaskStatus.CANCELLED}: raise TaskInvariantViolation(kind='terminal_violation', detail={...})`
2. その後 state machine table lookup で許可遷移か検査

理由:

- terminal 状態の Task は「完了済 / 中止済」で、変更経路をすべて閉じる
- state machine table にも「DONE / CANCELLED 起点の遷移は表に存在しない」を凍結する（§確定 R1-A）が、ふるまい入口でも先に弾くことで多層防御
- 「DONE の Task に commit_deliverable を呼ぶ」「CANCELLED の Task に advance を呼ぶ」等、業務上発生し得る誤呼び出しに対して `pyright` や `mypy` だけでは検出できない実行時違反を Aggregate 内で確実に塞ぐ

#### 確定 R1-C: `block(reason, last_error)` の `last_error` 必須契約

`block` ふるまいは `last_error: str`（**1〜10000 文字、NFC 正規化のみ・strip しない**、空文字列禁止）を**必須引数**として受け取る。`_validate_blocked_has_last_error` で:

| 入力経路 | `last_error` | 判定 |
|---|---|---|
| `block(reason, last_error='AuthExpired: ...')` | 非空文字列 | OK（`Task.last_error` に値が入る） |
| `block(reason, last_error='')` | 空文字列 | NG → `TaskInvariantViolation(kind='blocked_requires_last_error')` |
| `block(reason, last_error=None)` | None | NG → `pydantic.ValidationError`（型違反、`str` を期待） |
| 永続化からの復元（コンストラクタ経路で `status=BLOCKED, last_error='...'`） | 非空文字列 | OK |
| 永続化からの復元（コンストラクタ経路で `status=BLOCKED, last_error=None`） | None | NG → `TaskInvariantViolation(kind='blocked_requires_last_error')`（データ破損として扱う、Repository が壊れた行を返した場合の最終防衛線） |

理由:

- BLOCKED 状態は「人間介入待ち」の隔離。なぜ blocked になったか（LLM Adapter のエラー本文）を保持しないと admin CLI / UI で復旧判断ができない
- `last_error` の auto-mask（永続化前マスキング）は `feature/task-repository` の `MaskedText` 配線で実施。Aggregate 内では raw 保持

#### 確定 R1-D: `unblock_retry()` 後の `last_error` クリアタイミング

| 候補 | 採否 | 理由 |
|---|---|---|
| **(a) `unblock_retry()` で `last_error = None` に戻す** | ✓ **採用** | BLOCKED から復旧した時点で前回エラーは履歴情報。次回 BLOCKED で新しい `last_error` がセットされるまで持ち続ける必要がない。`audit_log` に履歴は残るので Aggregate 内属性としては不要 |
| (b) `last_error` を保持し続ける | ✗ 不採用 | IN_PROGRESS 状態の Task が `last_error` 値を持つと「現在エラー中なのか？」が UI / CLI で判別不能になる。`last_error is None ⇔ status != BLOCKED` の不変条件を強くするほうが clean |
| (c) `last_error_history: list[str]` を別フィールドで持つ | ✗ 不採用（YAGNI） | MVP 範囲で「過去の BLOCKED エラー履歴」を Aggregate 内に持つ業務シナリオなし。必要になれば `audit_log` を Repository 経由で参照する |

`_validate_last_error_consistency` で:

```
if status == BLOCKED:
    last_error must be non-empty str
else:  # PENDING / IN_PROGRESS / AWAITING_EXTERNAL_REVIEW / DONE / CANCELLED
    last_error must be None
```

#### 確定 R1-E: `deliverables: dict[StageId, Deliverable]` の VO 凍結（**本 PR で `Deliverable` / `Attachment` VO も導入**）

現状 `Deliverable` / `Attachment` は `storage.md` §Deliverable / §Attachment で属性定義のみ凍結されている VO だが、Pydantic v2 BaseModel として実体化されていない。Task Aggregate が `deliverables: dict[StageId, Deliverable]` で参照するため、本 PR で **`Deliverable` / `Attachment` を VO として導入する**:

| VO | 配置 | 属性 |
|---|---|---|
| `Deliverable` | `domain/value_objects.py`（既存ファイル更新、empire の `RoomRef` / `AgentRef` と同階層） | `stage_id: StageId` / `body_markdown: str`（0〜1,000,000 文字） / `attachments: list[Attachment]` / `committed_by: AgentId` / `committed_at: datetime`（UTC） |
| `Attachment` | 同上 | `sha256: str`（64 hex 小文字） / `filename: str`（255 文字以内 + サニタイズ） / `mime_type: str`（ホワイトリスト） / `size_bytes: int`（0 〜 10MiB） |

理由:

- Task Aggregate が VO 型として参照する型は事前に凍結する必要がある（forward reference は Pydantic v2 で `model_rebuild` が必要になり、構造が複雑化する）
- `Deliverable.body_markdown` のマスキングは `feature/task-repository` で `MaskedText` 配線、Aggregate / VO レベルでは raw 保持
- `Attachment` の `filename` サニタイズ・MIME ホワイトリストは `storage.md` §Attachment で凍結済みルールを Pydantic `field_validator` で実装

#### 確定 R1-F: `TaskInvariantViolation` の auto-mask 経路

CEO directive 由来の `last_error` / `deliverables[*].body_markdown` に webhook URL や API key が混入し得るため、agent / workflow / room / directive と同パターンで:

1. `super().__init__` 前に `mask_discord_webhook(message)` を message に適用
2. `detail` に対し `mask_discord_webhook_in(detail)` を再帰的に適用
3. `kind` は enum 文字列のため mask 対象外
4. その後 `super().__init__(masked_message)` を呼ぶ

#### 確定 R1-G: 例外型統一規約と MSG 2 行構造（room §確定 I 踏襲）

| 違反種別 | 例外型 | 発生レイヤ | 凍結する `kind` 値 |
|---|---|---|---|
| 構造的不変条件違反 | `TaskInvariantViolation` | Aggregate `model_validator(mode='after')` または各ふるまい入口 | `terminal_violation` / `state_transition_invalid` / `blocked_requires_last_error` / `assigned_agents_unique` / `last_error_consistency` |
| 型違反 / 必須欠落 | `pydantic.ValidationError` | Pydantic 型バリデーション | — |
| application 層の参照整合性違反 | `TaskNotFoundError` / `RoomNotFoundError` / `WorkflowNotFoundError` / `AgentNotFoundError` | `TaskService` 系 | — |

MSG-TS-001〜010 は **2 行構造**（`[FAIL] failure` + `Next: action`）で凍結し、test-design.md の TC-UT-TS-NNN で `assert "Next:" in str(exc)` を CI 物理保証する規約（room §確定 I 踏襲）。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 個人開発者 CEO（堀川さん想定） | bakufu インスタンスのオーナー、Task の生成起点 | GitHub / Docker / CLI 日常使用 | UI のチャット欄に `$ ブログ分析機能を作って` と入力 → Directive 起票 → Task 生成 → 各 Stage 進行を Web UI で確認 → External Review で承認 → DONE | 1 行の指令で Vモデル開発フローを起動して、各工程の進捗を見ながら最終的に成果物を受け取る |
| 後続 Issue 担当（バックエンド開発者） | `feature/external-review-gate` / `feature/task-repository` PR の実装者 | DDD 経験あり、SQLAlchemy 2.x async / Pydantic v2 経験あり | 本 PR の設計書を真実源として読み、Gate と Task の連携 / Task 永続化を実装 | 設計書の確定 R1-A〜G を素直に実装するだけで、後段レビューで責務散在を指摘されない |
| 運用担当（CEO 自身が兼務） | BLOCKED Task を `bakufu admin task retry-task <task_id>` で復旧 | CLI 操作可能 | LLM API 認証切れで Task が BLOCKED 化 → admin CLI で `retry-task` → IN_PROGRESS に復帰 → 再実行 | 認証復旧後にワンコマンドで Task を再開する |

##### ペルソナ別ジャーニー（個人開発者 CEO）

1. **directive 発行**: UI のチャット欄に `$ ブログ分析機能を作って` と入力 → Enter
2. **Task 生成**: directive #28 経由で Task が `status=PENDING, current_stage_id=workflow.entry_stage_id, deliverables={}` で起票される
3. **Agent 割当**: `TaskService.assign(task_id, agent_ids)` が呼ばれて `task.assign(agent_ids)` → `status=PENDING → IN_PROGRESS`
4. **成果物 commit**: 担当 Agent が Stage の deliverable を作成 → `task.commit_deliverable(stage_id, deliverable, by_agent_id)` → `deliverables` dict に追加
5. **External Review 要求**: Stage が EXTERNAL_REVIEW kind の場合 → `task.request_external_review()` → `status=IN_PROGRESS → AWAITING_EXTERNAL_REVIEW` + Gate Aggregate 生成（application 層で Task ↔ Gate を紐付け）
6. **承認 / 差し戻し**: CEO が Gate を `approve()` → Gate APPROVED → application 層が `task.approve_review(transition_id, by_owner_id, next_stage_id)` → 次 Stage へ。CEO が Gate を `reject()` → Gate REJECTED → application 層が `task.reject_review(transition_id, by_owner_id, next_stage_id)` → 差し戻し先 Stage へ（**専用 method 分離**で `gate_decision` 引数なし、§確定 R1-A）
6.1. **通常進行**（EXTERNAL_REVIEW を経由しない Stage 間遷移）: `task.advance_to_next(transition_id, by_owner_id, next_stage_id)`
7. **DONE**: 終端 Stage で `task.complete(transition_id, by_owner_id)` → `status=IN_PROGRESS → DONE`（terminal、以後変更不可）

##### ジャーニーから逆算した受入要件

- ジャーニー 2: `Task(id, room_id, directive_id, current_stage_id, deliverables={}, status=PENDING, ...)` で valid な Task が構築できる必要がある
- ジャーニー 3: `assign` で PENDING → IN_PROGRESS、`assigned_agent_ids` が更新される
- ジャーニー 4: `commit_deliverable` で `deliverables[stage_id] = deliverable` が更新、`updated_at` も更新
- ジャーニー 5: `request_external_review` で IN_PROGRESS → AWAITING_EXTERNAL_REVIEW（current_stage が EXTERNAL_REVIEW kind の前提検査は application 層責務、Aggregate 内では state 遷移のみ）
- ジャーニー 6: Gate APPROVED → `approve_review(transition_id, by_owner_id, next_stage_id)` で AWAITING → IN_PROGRESS（次 Stage へ）/ Gate REJECTED → `reject_review(transition_id, by_owner_id, next_stage_id)` で AWAITING → IN_PROGRESS（差し戻し先 Stage へ）。**専用 method 分離**で `gate_decision` 引数による分岐なし（Steve R2 凍結、§確定 R1-A 根拠）
- ジャーニー 6.1: 通常進行は `advance_to_next(transition_id, by_owner_id, next_stage_id)`、IN_PROGRESS の自己遷移
- ジャーニー 7: 終端 Stage で `complete(transition_id, by_owner_id)` 呼び出し → DONE 遷移、以後の全 10 ふるまい（`assign` / `commit_deliverable` / `request_external_review` / `approve_review` / `reject_review` / `advance_to_next` / `complete` / `cancel` / `block` / `unblock_retry`）が Fail Fast（terminal）
- ジャーニー全般: `last_error` / `deliverables[*].body_markdown` に webhook URL が混入しても永続化前にマスキング、例外経路でも auto-mask（agent §確定 D 踏襲）

##### ペルソナ別ジャーニー（運用担当）

1. **BLOCKED 検出**: `bakufu admin task list-blocked` で BLOCKED 状態の Task 一覧を表示
2. **エラー確認**: `bakufu admin task show <task_id>` で `last_error` を確認（マスキング済み、UI 表示は raw 復元不可）
3. **認証復旧**: 環境変数 `ANTHROPIC_API_KEY` を更新
4. **再試行**: `bakufu admin task retry-task <task_id>` → application 層が `task.unblock_retry()` を呼ぶ → `status=BLOCKED → IN_PROGRESS`、`last_error=None`
5. **Dispatcher 再開**: 現 Stage を再実行

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
| REQ-TS-001 | Task 構築 | コンストラクタで全属性を受け取り、不変条件検査を経て valid な Task を返す（永続化からの復元と新規生成の両経路に対応） | 必須 |
| REQ-TS-002 | Agent 割当 | `assign(agent_ids)` で `assigned_agent_ids` 更新 + `status=PENDING → IN_PROGRESS` | 必須 |
| REQ-TS-003 | 成果物 commit | `commit_deliverable(stage_id, deliverable, by_agent_id)` で `deliverables[stage_id]` 更新 | 必須 |
| REQ-TS-004 | External Review 要求 | `request_external_review()` で IN_PROGRESS → AWAITING_EXTERNAL_REVIEW | 必須 |
| REQ-TS-005 | Stage 進行・レビュー反映系（**4 method 専用分離**、§確定 R1-A / detailed-design §確定 A-2） | `approve_review(transition_id, by_owner_id, next_stage_id)`（Gate APPROVED 経路）/ `reject_review(transition_id, by_owner_id, next_stage_id)`（Gate REJECTED 経路）/ `advance_to_next(transition_id, by_owner_id, next_stage_id)`（IN_PROGRESS 自己遷移）/ `complete(transition_id, by_owner_id)`（IN_PROGRESS → DONE）の 4 method | 必須 |
| REQ-TS-006 | 中止 | `cancel(by_owner_id, reason)` で任意時点 → CANCELLED（terminal） | 必須 |
| REQ-TS-007 | BLOCKED 化 | `block(reason, last_error)` で IN_PROGRESS → BLOCKED、`last_error` 必須 | 必須 |
| REQ-TS-008 | BLOCKED 復旧 | `unblock_retry()` で BLOCKED → IN_PROGRESS、`last_error=None` | 必須 |
| REQ-TS-009 | 不変条件検査 | コンストラクタ末尾と全ふるまい末尾で実行。state machine / DONE terminal / BLOCKED last_error / assigned_agents 一意 / last_error consistency | 必須 |
| REQ-TS-010 | `Deliverable` / `Attachment` VO 導入 | `domain/value_objects.py` に Pydantic v2 VO として実体化（storage.md §凍結に追従） | 必須 |
| REQ-TS-011 | `TaskStatus` / `LLMErrorKind` enum 追加 | `value-objects.md` §列挙型一覧 で凍結済みを Python 実体化 | 必須 |

## Sub-issue 分割計画

本 Issue は単一 Aggregate に閉じる粒度のため Sub-issue 分割は不要。1 PR で 5 設計書 + 実装 + ユニットテストを完結させる（empire / workflow / agent / room / directive と同方針）。state machine の複雑性は decision table 一覧化で吸収可能で、ファイル分割（task.py / aggregate_validators.py / state_machine.py）でも 500 行ルールを破らない見通し。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 単一 PR | REQ-TS-001〜011 | Task Aggregate + Deliverable / Attachment VO + TaskStatus / LLMErrorKind enum + ユニットテスト | M1 5 兄弟（PR #15/#16/#17/#22/#28）+ M2 永続化基盤（PR #23）+ empire-repository（PR #29/#30）マージ済み |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 不変条件検査は state machine table lookup（O(1)）+ 属性数固定の検査（O(N) where N = `assigned_agent_ids` 件数、最大 5）。1ms 未満 |
| 可用性 | 該当なし — domain 層 |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 95% 以上（5 兄弟実績水準） |
| 可搬性 | 純 Python のみ |
| セキュリティ | `last_error` / `deliverables[*].body_markdown` に webhook URL / API key が混入し得る。永続化前にマスキング規則の適用対象（[`storage.md`](../../architecture/domain-model/storage.md) §シークレットマスキング規則、`Task.last_error` / `Deliverable.body_markdown` 行が既に明示済み）。`TaskInvariantViolation` は webhook URL auto-mask（5 兄弟と同パターン）。詳細は [`threat-model.md`](../../architecture/threat-model.md) §A04 |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | `Task(id, room_id, directive_id, current_stage_id, deliverables={}, status=PENDING, assigned_agent_ids=[], created_at, updated_at, last_error=None)` で valid な Task が構築される | TC-UT-TS-001 |
| 2 | TaskStatus 6 種すべての状態で構築可能（永続化からの復元経路、ただし `status=BLOCKED` のときは `last_error` 必須） | TC-UT-TS-002 |
| 3 | `assign(agent_ids)` で PENDING → IN_PROGRESS 遷移、`assigned_agent_ids` 更新 | TC-UT-TS-003 |
| 4 | state machine table に存在しない遷移は `TaskInvariantViolation(kind='state_transition_invalid')` | TC-UT-TS-004 |
| 5 | `status == DONE` の Task に対する全 10 ふるまい呼び出しが `TaskInvariantViolation(kind='terminal_violation')` | TC-UT-TS-005 |
| 6 | `status == CANCELLED` の Task に対する全 10 ふるまい呼び出しが同上 | TC-UT-TS-006 |
| 7 | `block(reason, last_error='')` で `TaskInvariantViolation(kind='blocked_requires_last_error')` | TC-UT-TS-007 |
| 8 | `unblock_retry()` で BLOCKED → IN_PROGRESS、`last_error=None` に戻る | TC-UT-TS-008 |
| 9 | `assigned_agent_ids` の重複 → `TaskInvariantViolation(kind='assigned_agents_unique')` | TC-UT-TS-009 |
| 10 | IN_PROGRESS / DONE / 等の状態で `last_error != None` → `TaskInvariantViolation(kind='last_error_consistency')` | TC-UT-TS-010 |
| 11 | `TaskInvariantViolation` の `message` / `detail` 内 webhook URL が `<REDACTED:DISCORD_WEBHOOK>` に伏字化 | TC-UT-TS-011 |
| 12 | `Deliverable(stage_id, body_markdown, attachments, committed_by, committed_at)` で valid な VO が構築される | TC-UT-TS-012 |
| 13 | `Attachment(sha256, filename, mime_type, size_bytes)` で valid な VO が構築、サニタイズ規則違反は `pydantic.ValidationError` | TC-UT-TS-013 |
| 14 | エラーメッセージは 2 行構造（`[FAIL] ...` + `Next: ...`）、`assert "Next:" in str(exc)` で CI 物理保証 | TC-UT-TS-001〜011 全件 |
| 15 | Task は frozen で構造的等価判定 | TC-UT-TS-014 |
| 16 | `pyright --strict` および `ruff check` がエラーゼロ | CI lint / typecheck |
| 17 | カバレッジが `domain/task/` で 95% 以上 | pytest --cov |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Task.last_error | LLM Adapter の例外メッセージ（自然言語、長文の可能性） | **高**（API key / webhook URL / OAuth token が混入し得る、Repository 永続化前マスキング必須、storage.md §逆引き表に `Task.last_error: MaskedText` 行が既に登録済み） |
| Deliverable.body_markdown | Agent 成果物本文（Markdown、長文） | **高**（同上、storage.md §逆引き表に `Deliverable.body_markdown: MaskedText` 行が既に登録済み） |
| Task.deliverables（dict） | Stage ごとの成果物スナップショット | **高**（中身の body_markdown が高機密、container は dict 構造） |
| Task.id / room_id / directive_id / current_stage_id / assigned_agent_ids | UUID 識別子のみ | 低 |
| Task.status | enum（TaskStatus 6 種） | 低 |
| Task.created_at / updated_at | UTC datetime | 低 |
