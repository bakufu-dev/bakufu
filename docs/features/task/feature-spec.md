# 業務仕様書（feature-spec）— Task

> feature: `task`（業務概念単位）
> sub-features: [`domain/`](domain/) | [`repository/`](repository/) | http-api（将来）| ui（将来）
> 関連 Issue: [#37 feat(task): Task Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/37) / [#35 feat(task-repository): Task SQLite Repository (M2)](https://github.com/bakufu-dev/bakufu/issues/35)
> 凍結済み設計: [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Task / [`docs/design/domain-model/value-objects.md`](../../design/domain-model/value-objects.md) §列挙型一覧（TaskStatus / LLMErrorKind） / [`docs/design/domain-model/storage.md`](../../design/domain-model/storage.md) §Deliverable / §Attachment / §シークレットマスキング適用先

## 本書の役割

本書は **Task という業務概念全体の業務仕様** を凍結する。bakufu 全体の要求分析（[`docs/analysis/`](../../analysis/)）を Task という業務概念で具体化し、ペルソナ（個人開発者 CEO）から見て **観察可能な業務ふるまい** を実装レイヤー（domain / repository / http-api / ui）に依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / 将来の http-api / ui）は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない（本書の更新は別 PR で先行する）。

**書くこと**:
- ペルソナ（CEO）が Task という業務概念で達成できるようになる行為（ユースケース）
- 業務ルール（不変条件・state machine・BLOCKED 隔離・terminal 検査・永続性・masking 等、すべての sub-feature を貫く凍結）
- E2E で観察可能な事象としての受入基準（業務概念全体）
- sub-feature 間の責務分離マップ（実装レイヤー対応）

**書かないこと**（sub-feature の設計書へ追い出す）:
- 採用技術スタック（Pydantic / SQLAlchemy / FastAPI 等） → sub-feature の `basic-design.md`
- 実装方式の比較・選定議論（pre-validate / delete-then-insert / decision table / TypeDecorator 等） → sub-feature の `detailed-design.md`
- 内部 API 形・メソッド名・属性名・型 → sub-feature の `basic-design.md` / `detailed-design.md`
- sub-feature 内のテスト戦略（IT / UT） → sub-feature の `test-design.md`（E2E のみ親 [`system-test-design.md`](system-test-design.md) で扱う）
- pyright / ruff / カバレッジ等の CI 品質基準 → §10 開発者品質基準 / sub-feature の `test-design.md §カバレッジ基準`

## 1. この feature の位置付け

bakufu インスタンスで「CEO directive → Vモデル工程進行 → 完了」を駆動する実行単位「Task」を、ペルソナ（個人開発者 CEO）が Stage 進行・成果物確認・External Review 承認を通じて観察・操作できる業務概念として定義する。Task は CEO directive から生成され、Workflow の Stage を進行しながら Agent が deliverable を commit し、External Review Gate を経て DONE に至る。

Task の業務的なライフサイクルは複数の実装レイヤーを跨ぐ:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| domain | [`domain/`](domain/) | Task の状態遷移（TaskStatus 6 種 / 13 遷移の state machine）・不変条件・Deliverable / Attachment VO・BLOCKED 隔離経路を Aggregate 内で保証 |
| repository | [`repository/`](repository/) | Task の状態を再起動跨ぎで保持（永続化）、`last_error` / `body_markdown` の secret マスキングを担保 |
| http-api | (将来) | UI / 外部クライアントから Task を操作・取得する経路 |
| ui | (将来) | CEO が Task 進行状況を確認し、External Review Gate を操作する画面 |

本書はこれら全レイヤーを貫く **業務概念単位の凍結文書** であり、各 sub-feature は本書を引用して実装契約を凍結する。

## 2. 人間の要求

> Issue #37（M1 domain）:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の **6 番目の Aggregate**（M1 最大難所）として **Task Aggregate Root** を実装する。Task は CEO directive から生成され、Workflow の Stage を進行しながら Agent が deliverable を commit するワークフロー実行単位。**TaskStatus 6 種の state machine** + **BLOCKED 隔離経路** + **External Review Gate との連携**を持つ、MVP の核心ユースケース「CEO directive → Vモデル工程進行 → 完了」の駆動エンジン。

> Issue #35（M2 repository）:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の後続 Repository PR。**Task Aggregate** の SQLite 永続化を実装する。4 テーブル（tasks / task_assigned_agents / deliverables / deliverable_attachments）にまたがる複合永続化と、`tasks.last_error` / `deliverables.body_markdown` の MaskedText 実適用、`directives.task_id → tasks.id` FK（BUG-DRR-001）closure が核心。

## 3. 背景・痛点

### 現状の痛点

1. M1 ドメイン骨格 5 兄弟（empire / workflow / agent / room / directive）が完走したが、MVP 核心ユースケース「CEO directive → Vモデル工程進行 → DONE」を駆動する Task Aggregate がないため、M7「V モデル E2E」へ至る経路が Task で塞がれている
2. `feature/external-review-gate` は `task_id` を介して Task を参照する設計。Task がないと Gate 構築の参照整合性検査が成立しない
3. directive #28 は `link_task(task_id)` で Task を紐付けるが、紐付け先となる Task Aggregate Root が存在しない（`directives.task_id → tasks.id` FK も未追加の状態）
4. TaskStatus 6 種 + 13 遷移の state machine 方式が未確定。`advance` 単一 method による暗黙 dispatch は 3 PR 連鎖（task-repository / external-review-gate-aggregate / external-review-gate-repository）の前提に揺れを残すため、method × current_status → action の対応を 1:1 静的に凍結する必要がある
5. BLOCKED 隔離経路（LLM Adapter 復旧不能エラー → 人間介入待ち）の Aggregate 内表現も未確定
6. CEO が Task を設計しても再起動で状態が消えるなら業務として成立しない（Task 進行は持続的な工程概念）

### 解決されれば変わること

- `feature/external-review-gate` Aggregate Issue が Task 参照を前提に着手可能になる
- M2 後段の `feature/task-repository` が Aggregate VO 構造を真実源として SQLite 配線を始められる
- empire / workflow / agent / room / directive の確立済みパターンを **6 例目**として揃え、M1 完走の最後のピースが埋まる
- state machine の決定表方式を凍結することで、後続 `feature/external-review-gate` の 4 種 state machine でも同パターンが使える
- Task の状態がアプリ再起動を跨いで保持される（CEO は永続化を意識しない）
- `tasks.last_error` / `deliverables.body_markdown` に CEO / Agent が入力した secret が DB に raw 保存されない

### ビジネス価値

- bakufu の核心思想「CEO directive → Vモデル工程進行 → 外部レビューで人間が承認」のうち**最も中核となる工程駆動**を Aggregate 単位で表現する
- **BLOCKED の明示的隔離**により「LLM API 認証切れで無限再試行 → 課金事故」を構造で防ぐ
- AI 協業による品質向上を**人間チェックポイント（External Review Gate）でゲート**する設計を Task ↔ Gate の連携経路として固定する

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|-----------|------|---------|---------------|
| 個人開発者 CEO（堀川さん想定） | bakufu インスタンスのオーナー、Task の生成起点 | 直接（将来の UI 経由）/ 間接（domain・repository sub-feature では application 層経由） | 1 行の指令で Vモデル開発フローを起動して、各工程の進捗を見ながら最終的に成果物を受け取る。認証切れで Task が BLOCKED になったら admin CLI で復旧する |
| 運用担当（CEO 自身が兼務） | BLOCKED Task を `bakufu admin task retry-task <task_id>` で復旧 | CLI 操作 | LLM API 認証切れで Task が BLOCKED 化 → admin CLI で `retry-task` → IN_PROGRESS に復帰 → 再実行 |

bakufu システム全体ペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

##### ペルソナ別ジャーニー（個人開発者 CEO）

1. **directive 発行**: UI のチャット欄に `$ ブログ分析機能を作って` と入力 → Enter
2. **Task 生成**: directive 経由で Task が `status=PENDING, current_stage_id=workflow.entry_stage_id, deliverables={}` で起票される
3. **Agent 割当**: `TaskService.assign(task_id, agent_ids)` → `task.assign(agent_ids)` → `status=PENDING → IN_PROGRESS`
4. **成果物 commit**: 担当 Agent が Stage の deliverable を作成 → `task.commit_deliverable(stage_id, deliverable, by_agent_id)` → `deliverables` dict に追加
5. **External Review 要求**: Stage が EXTERNAL_REVIEW kind の場合 → `task.request_external_review()` → `status=IN_PROGRESS → AWAITING_EXTERNAL_REVIEW` + Gate Aggregate 生成
6. **承認 / 差し戻し**: CEO が Gate を `approve()` → `task.approve_review(transition_id, by_owner_id, next_stage_id)` → 次 Stage へ。CEO が Gate を `reject()` → `task.reject_review(transition_id, by_owner_id, next_stage_id)` → 差し戻し先 Stage へ（**専用 method 分離**）
7. **通常進行**: `task.advance_to_next(transition_id, by_owner_id, next_stage_id)` → IN_PROGRESS の自己遷移（EXTERNAL_REVIEW を経由しない Stage 間遷移）
8. **DONE**: 終端 Stage で `task.complete(transition_id, by_owner_id)` → `status=IN_PROGRESS → DONE`（terminal、以後変更不可）

##### ペルソナ別ジャーニー（運用担当）

1. **BLOCKED 検出**: `bakufu admin task list-blocked` で BLOCKED 状態の Task 一覧を表示
2. **エラー確認**: `bakufu admin task show <task_id>` で `last_error` を確認（マスキング済み）
3. **認証復旧**: 環境変数 `ANTHROPIC_API_KEY` を更新
4. **再試行**: `bakufu admin task retry-task <task_id>` → application 層が `task.unblock_retry()` → `status=BLOCKED → IN_PROGRESS`、`last_error=None`

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|-------|---------|-----------------|-------|------|
| UC-TS-001 | CEO | directive から Task を起票できる（status=PENDING で生成、assigned_agent_ids=[]） | 必須 | domain |
| UC-TS-002 | CEO | Task に Agent を割り当てて工程を開始できる（PENDING → IN_PROGRESS） | 必須 | domain |
| UC-TS-003 | CEO | Agent が Stage の成果物を commit できる（`deliverables[stage_id]` 更新） | 必須 | domain |
| UC-TS-004 | CEO | External Review Stage でレビュー承認 / 差し戻しができる（専用 method 分離） | 必須 | domain |
| UC-TS-005 | CEO | 終端 Stage で Task を完了できる（IN_PROGRESS → DONE、terminal） | 必須 | domain |
| UC-TS-006 | CEO / 運用担当 | BLOCKED Task を復旧できる（block / unblock_retry） | 必須 | domain |
| UC-TS-007 | CEO | 任意のタイミングで Task を中止できる（PENDING / IN_PROGRESS / AWAITING / BLOCKED → CANCELLED） | 必須 | domain |
| UC-TS-008 | CEO | 設計した Task の状態がアプリ再起動を跨いで保持される（永続化を意識しない） | 必須 | repository |

## 6. スコープ

### In Scope

- Task 業務概念全体で観察可能な業務ふるまい（UC-TS-001〜008）
- ふるまいの呼び出し失敗時に観察される拒否シグナル（業務ルール違反）
- 業務概念単位の E2E 検証戦略 → [`system-test-design.md`](system-test-design.md)

### Out of Scope（参照）

- Task の HTTP API → 将来の `task/http-api/` sub-feature
- Task の進行 UI → 将来の `task/ui/` sub-feature
- External Review Gate の業務ふるまい → `feature/external-review-gate`（別 Aggregate）
- Dispatcher の Stage 自動実行 → `feature/dispatcher`
- Admin CLI 実装 → `feature/admin-cli`
- 永続化基盤の汎用責務 → [`feature/persistence-foundation`](../persistence-foundation/)
- 実 LLM 送信 → `feature/llm-adapter`
- Attachment 物理ファイル管理 → `feature/attachment-storage`（未 Issue）

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-1: Task の状態は TaskStatus 6 種（PENDING / IN_PROGRESS / AWAITING_EXTERNAL_REVIEW / BLOCKED / DONE / CANCELLED）で表現する

**理由**: 業務上識別可能な 6 つの状態がある。DONE と CANCELLED は terminal（以後変更不可）。詳細な遷移ルールは確定 R1-2 で凍結。

### 確定 R1-2: state machine は 13 遷移の decision table で凍結（**method 名 = action 名で 1:1**）

`TaskStatus` 6 種 + Task ふるまい 10 種 = 60 経路のうち**実際に許可されるのは 13 遷移のみ**。`advance` 単一 method による暗黙 dispatch は不採用（**`approve_review` / `reject_review` / `advance_to_next` / `complete` の 4 method 専用分離**で凍結）:

| 起点状態 | 操作 | 遷移先状態 |
|---|---|---|
| PENDING | `assign` | IN_PROGRESS |
| PENDING | `cancel` | CANCELLED |
| IN_PROGRESS | `commit_deliverable` | IN_PROGRESS（自己遷移）|
| IN_PROGRESS | `request_external_review` | AWAITING_EXTERNAL_REVIEW |
| IN_PROGRESS | `advance_to_next` | IN_PROGRESS（自己遷移）|
| IN_PROGRESS | `complete` | DONE |
| IN_PROGRESS | `block` | BLOCKED |
| IN_PROGRESS | `cancel` | CANCELLED |
| AWAITING_EXTERNAL_REVIEW | `approve_review` | IN_PROGRESS |
| AWAITING_EXTERNAL_REVIEW | `reject_review` | IN_PROGRESS |
| AWAITING_EXTERNAL_REVIEW | `cancel` | CANCELLED |
| BLOCKED | `unblock_retry` | IN_PROGRESS |
| BLOCKED | `cancel` | CANCELLED |

DONE / CANCELLED を起点とする遷移は **table に存在しない** ことで明示禁止。

### 確定 R1-3: DONE / CANCELLED は terminal 状態（全ふるまい入口で先頭 Fail Fast）

全 10 ふるまい（assign / commit_deliverable / request_external_review / approve_review / reject_review / advance_to_next / complete / cancel / block / unblock_retry）の入口で terminal 状態を先頭検査し、`TaskInvariantViolation(kind='terminal_violation')` を raise する。

### 確定 R1-4: BLOCKED 状態の `last_error` 必須（空文字列禁止、1〜10000 文字 NFC 正規化）

`block(reason, last_error)` の `last_error` は非空文字列（1〜10000 文字、NFC 正規化のみ・strip しない）。空文字列は `TaskInvariantViolation(kind='blocked_requires_last_error')` で Fail Fast。`status == BLOCKED ⇔ last_error is not None and last_error != ''` を不変条件として Aggregate 全体で保証。

**理由**: BLOCKED 状態は「人間介入待ち」の隔離。なぜ blocked になったか（LLM Adapter のエラー本文）を保持しないと admin CLI / UI で復旧判断ができない。

### 確定 R1-5: `unblock_retry()` 後に `last_error` を None にリセット

復旧した時点で前回エラーは履歴情報。`audit_log` に履歴は残るので Aggregate 内属性としては不要。`status != BLOCKED ⇔ last_error is None` の不変条件を保持する。

### 確定 R1-6: `assigned_agent_ids` は順序保持 list + Aggregate 内で重複・容量検査

- 重複なし（`assigned_agents_unique`）、最大 5 件（`assigned_agents_capacity`）
- Set ではなく List で保持（empire の `agents: list[AgentRef]` 同様、割当順が UI 表示順を決める）
- 各 AgentId が Room.members 内に存在するかの参照整合性は **application 層責務**

### 確定 R1-7: `deliverables` は `dict[StageId, Deliverable]`（同 Stage への 2 回目 commit は上書き）

「Stage ごとに最新の成果物 1 件」を dict 型レベルで保証。`current_stage_id` / `stage_id` の Workflow 内存在検証は **application 層責務**（Aggregate 内では UUID 型として valid まで守る）。

### 確定 R1-8: `TaskInvariantViolation` は webhook auto-mask を適用（5 兄弟と同パターン）

`super().__init__` 前に `mask_discord_webhook(message)` と `mask_discord_webhook_in(detail)` を強制適用。`last_error` / `deliverables[*].body_markdown` に webhook URL が混入し得るため、例外経路での webhook token 漏洩を物理的に防ぐ（多層防御）。

### 確定 R1-9: エラーメッセージは 2 行構造（`[FAIL] failure` + `Next: action`）

MSG-TS-001〜010 はすべて「失敗事実（1 行目）+ 次に何をすべきか（2 行目）」の 2 行構造。`assert "Next:" in str(exc)` を CI で物理保証する（room §確定 I 踏襲）。

### 確定 R1-10: `current_stage_id` / `transition_id` / `next_stage_id` / `assigned_agent_ids` の参照整合性は application 層責務

Task Aggregate は UUID 型として保持するのみ。Workflow 内存在・Room.members 内存在の検証は `TaskService` が `WorkflowRepository` / `RoomRepository` / `AgentRepository` 経由で行う。Aggregate 間依存を生まないための設計決定。

### 確定 R1-11: Task の状態は再起動跨ぎで保持される

Task 進行は持続的な工程概念であり、アプリ再起動による状態消失は業務として許容できない。永続化は CEO から意識されない透明な責務（UC-TS-008）。

### 確定 R1-12: `tasks.last_error` / `deliverables.body_markdown` は DB に raw secret で保存しない

CEO directive 由来の `last_error` / Agent 成果物の `body_markdown` に webhook URL / API key が混入し得るため、Repository 層で永続化前に `MaskedText` TypeDecorator を適用する。domain 層は raw 保持し、Repository 層でマスキング（多層防御の各層が独立して secret 漏洩を防ぐ）。

## 8. 制約・前提

| 区分 | 内容 |
|-----|------|
| 既存運用規約 | GitFlow / Conventional Commits（[`CONTRIBUTING.md`](../../../CONTRIBUTING.md)） |
| ライセンス | MIT |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |
| ネットワーク | 該当なし — Task 業務概念は外部通信を持たない（実 LLM 送信は `feature/llm-adapter` 責務）|
| 依存 feature | M1 開始時点: 5 兄弟（empire / workflow / agent / room / directive）マージ済み / M2 開始時点: M1 Task Aggregate + [`feature/persistence-foundation`](../persistence-foundation/) + empire-repository マージ済み |

実装技術スタック（Python 3.12 / Pydantic v2 / SQLAlchemy 2.x async / Alembic / pyright strict / pytest）は各 sub-feature の `basic-design.md §依存関係` に集約する。

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|------|---------|---------|
| 1 | 担当エージェントなし・成果物なし・エラー情報なしの初期状態（PENDING）で有効な Task が作成でき、room / directive / 現在の Stage と関連付けられる（業務ルール R1-1） | UC-TS-001 | TC-UT-TS-001（[`domain/test-design.md`](domain/test-design.md)） |
| 2 | TaskStatus 6 種すべての状態で構築可能（永続化からの復元経路、ただし `status=BLOCKED` のときは `last_error` 必須） | UC-TS-001 | TC-UT-TS-002 |
| 3 | `assign(agent_ids)` で PENDING → IN_PROGRESS 遷移、`assigned_agent_ids` 更新 | UC-TS-002 | TC-UT-TS-003 |
| 4 | state machine に定義されない遷移（例: DONE 状態からの再割り当て）を要求した場合、拒否される（業務ルール R1-2） | UC-TS-002〜007 | TC-UT-TS-004 |
| 5 | DONE 状態の Task はすべての操作を拒否する（終端状態・業務ルール R1-3） | UC-TS-005 | TC-UT-TS-005 |
| 6 | CANCELLED 状態の Task はすべての操作を拒否する（終端状態・業務ルール R1-3） | UC-TS-007 | TC-UT-TS-006 |
| 7 | Task を BLOCKED にするにはエラー情報（last_error）が必須。空文字の場合は拒否される（業務ルール R1-5） | UC-TS-006 | TC-UT-TS-007 |
| 8 | BLOCKED 状態から再開を指示すると IN_PROGRESS に戻り、エラー情報がクリアされる（業務ルール R1-5） | UC-TS-006 | TC-UT-TS-008 |
| 9 | 同一エージェントを重複して割り当てることはできない（業務ルール R1-4） | UC-TS-002 | TC-UT-TS-009 |
| 10 | BLOCKED 以外の状態で Task にエラー情報が残存している場合、整合性エラーとして拒否される（業務ルール R1-5） | UC-TS-001〜007 | TC-UT-TS-010 |
| 11 | 業務ルール違反のエラーメッセージに Discord webhook URL が含まれていた場合、`<REDACTED:DISCORD_WEBHOOK>` として伏字化される（domain 層での多層防御、受入基準 17 の repository 層マスキングとは独立） | UC-TS-001〜007 | TC-UT-TS-011 |
| 12 | Agent が Stage の成果物（本文・添付ファイル・提出者・提出日時）を提出でき、有効な Deliverable として記録される（業務ルール R1-6） | UC-TS-003 | TC-UT-TS-012 |
| 13 | sha256 / filename / mime_type / size_bytes を指定して有効な Attachment が構築できる。ファイル名のパストラバーサル（../）・不正 MIME 型等のサニタイズ規則違反は拒否される（業務ルール R1-10） | UC-TS-003 | TC-UT-TS-013 |
| 14 | 業務ルール違反のエラーメッセージには次に取るべき行動の案内（Next: ...）が含まれる | UC-TS-001〜007 | TC-UT-TS-046〜052（[`domain/test-design.md`](domain/test-design.md)） |
| 16 | Task の状態がアプリ再起動跨ぎで永続化される（status / deliverables / assigned_agent_ids / last_error が再起動後に構造的等価で復元） | UC-TS-008 | TC-E2E-TS-001（[`system-test-design.md`](system-test-design.md)） |
| 17 | `tasks.last_error` / `deliverables.body_markdown` に Discord webhook token / GitHub PAT 等の secret を含む値を保存すると、DB には `<REDACTED:*>` でマスキングされた値が格納される（raw secret が DB に残らない） | UC-TS-008 | TC-IT-TR-020-masking-*（[`repository/test-design.md`](repository/test-design.md)） |

E2E（受入基準 16）は [`system-test-design.md`](system-test-design.md) で詳細凍結。受入基準 1〜14 は domain sub-feature の IT / UT で検証（[`domain/test-design.md`](domain/test-design.md)）。受入基準 17 は repository sub-feature の IT で検証。

## 10. 開発者品質基準（CI 担保、業務要求ではない）

各 sub-feature の `basic-design.md §モジュール契約` / `test-design.md §カバレッジ基準` で個別に管理する。本書では業務要求のみ凍結。

参考: domain は `domain/task/` カバレッジ 95% 以上、repository は実装ファイル群で 90% 以上を目標としているが、これは sub-feature 側の凍結事項。pyright strict pass / ruff 警告ゼロも sub-feature 側で保証する。

## 11. 開放論点 (Open Questions)

凍結時点で未確定の論点はなし — 設計レビューで全件凍結済み（§確定 R1-1〜12 として §7 に集約）。

## 12. sub-feature 一覧とマイルストーン整理

[`README.md`](README.md) を参照。

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Task.last_error | LLM Adapter の例外メッセージ（自然言語、長文） | **高**（API key / webhook URL / OAuth token が混入し得る、Repository 永続化前マスキング必須） |
| Deliverable.body_markdown | Agent 成果物本文（Markdown、長文） | **高**（同上、Repository 永続化前マスキング必須） |
| Task.deliverables（dict） | Stage ごとの成果物スナップショット | **高**（中身の body_markdown が高機密） |
| Task.id / room_id / directive_id / current_stage_id / assigned_agent_ids | UUID 識別子のみ | 低 |
| Task.status | enum（TaskStatus 6 種） | 低 |
| Task.created_at / updated_at | UTC datetime | 低 |
| 永続化テーブル群（tasks / task_assigned_agents / deliverables / deliverable_attachments） | 上記の永続化先 | 低〜高（`tasks.last_error` / `deliverables.body_markdown` のみ MaskedText、その他は masking 対象なし） |

## 14. 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 不変条件検査は state machine table lookup（O(1)）+ 属性数固定の検査（O(N) where N = `assigned_agent_ids` 件数、最大 5）。1ms 未満。永続化層 50ms 未満を目標 |
| 可用性 | 永続化層の WAL モード + crash safety（[`feature/persistence-foundation`](../persistence-foundation/) 担保）により、書き込み中のクラッシュでも Task 状態が破損しない |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ domain 95% 以上 / repository 90% 以上（各 sub-feature の `test-design.md §カバレッジ基準` で管理） |
| 可搬性 | 純 Python のみ（domain 層）。OS / ファイルシステム依存なし（SQLite はクロスプラットフォーム） |
| セキュリティ | `last_error` / `deliverables[*].body_markdown` に webhook URL / API key が混入し得る。Repository 永続化前マスキング必須（業務ルール R1-12）。`TaskInvariantViolation` の auto-mask で例外経路の多層防御（業務ルール R1-8）。詳細は [`docs/design/threat-model.md`](../../design/threat-model.md) |
