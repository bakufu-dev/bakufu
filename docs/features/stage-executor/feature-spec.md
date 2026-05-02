# 業務仕様書（feature-spec）— Stage 実行ループ

> feature: `stage-executor`
> sub-features: application
> 関連 Issue: #163
> 凍結済み設計: [`docs/design/domain-model.md`](../../design/domain-model.md) §Task / §Workflow / §Stage

## 本書の役割

本書は **Stage 実行ループという業務概念全体の業務仕様** を凍結する。Task が新しい Stage に遷移した際に、StageKind（WORK / INTERNAL_REVIEW / EXTERNAL_REVIEW）に応じて何が起きるかを業務観点で定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない。

**書くこと**:
- ペルソナがこの業務概念で達成できるようになる行為（ユースケース UC-ME-NNN）
- 業務ルール（StageKind 分岐・エラー分類・BLOCKED 回復経路、確定 R1-X として凍結）
- 観察可能な事象としての受入基準（システムテストの真実源）

**書かないこと**（後段の設計書・別ディレクトリへ追い出す）:
- 採用技術スタック → `application/basic-design.md` / [`docs/design/tech-stack.md`](../../design/tech-stack.md)
- 実装方式の比較・選定議論 → `application/detailed-design.md`
- 内部 API 形・メソッド名・属性名・型 → `application/basic-design.md` / `application/detailed-design.md`
- pyright strict / カバレッジ閾値 → §10 開発者品質基準（CI 担保、業務要求とは分離）

## 1. この feature の位置付け

Stage 実行ループは **Task の Stage 遷移をトリガーとして、各 Stage の実行を正しいアクターに委譲するオーケストレーション機構** として定義する。bakufu の「自立開発」能力の中枢を担い、DirectiveIssued イベントから Task DONE までの自動実行経路を閉じる。

業務的なライフサイクルは複数の実装レイヤーを跨ぐ:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| application | application（本 Issue）| Stage 実行の業務判断・LLM 呼び出し・エラー分類・BLOCKED 管理 |
| infrastructure | （bootstrap / worker）| asyncio バックグラウンドワーカー・pid_registry 管理 |
| interfaces | （admin-cli: M5-C #165）| BLOCKED 救済・retry 操作の人間接点 |

## 2. 人間の要求

> Issue #163:
>
> 「bakufu で bakufu 自立開発を指示できる状態」にするために、Task が各 Stage を自動実行する機構を実装する。LLMProviderPort の確定・Stage 実行ループ・非同期キュー設計を含む。

## 3. 背景・痛点

### 現状の痛点

1. M4（WebSocket broadcast）まで完了しており Task の状態遷移は domain 層で完全に定義されているが、Task を「動かす」オーケストレーターが存在しない。HTTP API から Directive を投入しても Stage が自動進行しない
2. `LLMProviderPort`（ClaudeCodeLLMClient）は実装済みだが、どの Stage で・誰が・どのシステムプロンプトで呼び出すかが未設計
3. エラー発生時の Task BLOCKED 化・回復経路が設計されておらず、異常系が処理されない

### 解決されれば変わること

- Directive を投入すると Task が Stage を順番に自動実行し、WORK Stage では Claude Code CLI が deliverable を生成する
- INTERNAL_REVIEW / EXTERNAL_REVIEW Stage で適切なゲート処理に委譲される
- エラー発生時は Task が BLOCKED になり、人間が admin CLI（M5-C）で救済できる
- 「bakufu で bakufu 自立開発を指示できる状態」（MVP ゴール）に直結する

### ビジネス価値

- bakufu が自立的に「設計 → 実装 → レビュー」の工程を実行できるようになる
- 人間の介入が ExternalReviewGate の承認操作のみに限定される

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|---|---|---|---|
| CEO（まこちゃん）| bakufu オーナー | 直接 | Directive を投入するだけで Task が自動進行し、ExternalReviewGate でのみ承認操作をすればよい |
| bakufu 自身 | Stage 実行の実行主体（Agent）| 間接 | 各 Stage の deliverable を生成して次 Stage へ進む |
| 管理者 | BLOCKED Task を発見・救済する人間 | 直接 | BLOCKED Task を admin CLI で復旧できる |

プロジェクト全体ペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|---|---|---|---|---|
| UC-ME-001 | bakufu 自身 | WORK Stage において Claude Code CLI が呼び出され、deliverable が生成されて次 Stage へ進む | 必須 | application |
| UC-ME-002 | bakufu 自身 | INTERNAL_REVIEW Stage において InternalReviewGate 実行が委譲され、全 APPROVED で次 Stage へ、1 件でも REJECTED で前段 Stage に差し戻しが発生する | 必須 | application（M5-B #164 接点）|
| UC-ME-003 | bakufu 自身 | EXTERNAL_REVIEW Stage において ExternalReviewGate が生成され、Task が AWAITING_EXTERNAL_REVIEW となる | 必須 | application |
| UC-ME-004 | bakufu 自身 | LLM 呼び出し中に復旧不能エラーが発生した際に Task が BLOCKED となり、エラー情報がマスキングされて保存される | 必須 | application |
| UC-ME-005 | 管理者 | BLOCKED Task に対して retry 操作を行うと Task が IN_PROGRESS に戻り、最後の Stage が再キューされる | 必須 | application（M5-C #165 接点）|

## 6. スコープ

### In Scope

- WORK Stage における LLM 呼び出し（Claude Code CLI）・deliverable 生成・次 Stage 進行（UC-ME-001）
- INTERNAL_REVIEW Stage の実行委譲インターフェースの凍結（実装本体は M5-B #164）（UC-ME-002）
- EXTERNAL_REVIEW Stage における ExternalReviewGate 生成委譲と Task.request_external_review() 呼び出し（UC-ME-003）
- LLMProviderError 5 分類 → Task.block() マッピング（UC-ME-004）
- BLOCKED Task の回復エントリポイント定義（M5-C #165 が使う接点の凍結）（UC-ME-005）
- 並行数制御（BAKUFU_MAX_CONCURRENT_STAGES）・asyncio Queue によるキューイング
- pid_registry への subprocess 登録・削除
- Bootstrap への StageWorker 登録（Stage 6.5）

### Out of Scope（参照）

- InternalReviewGate 実行ロジック本体 → `feature/internal-review-gate`（M5-B #164）
- ExternalReviewGate Domain 設計・永続化 → `feature/external-review-gate`（既存）
- admin CLI の実装（list-blocked / retry-task 等）→ M5-C #165
- Discord 通知実装 → M6-A #166
- 並列 Stage 実行（BAKUFU_MAX_CONCURRENT_STAGES > 1）→ Phase 2

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-1: WORK Stage は LLMProviderPort を通じて Claude Code CLI を呼び出す

Agent の `role_profile`（システムプロンプト）と Stage の `required_deliverables`（成果物定義）を組み合わせて LLM に送信する。session_id = Stage ID（Stage ごとに独立したセッション）。LLM の応答として得られる deliverable は masking gateway を通過してから永続化する。

**理由**: Stage ごとにコンテキストが独立しており、前 Stage の文脈の漏れ（cross-contamination）を防ぐ。CLI の `--session-id` オプションで会話継続が可能。

### 確定 R1-2: INTERNAL_REVIEW Stage 実行は M5-B（InternalReviewGate executor）に委譲する

Stage 実行ループは StageKind = INTERNAL_REVIEW を検知した時点で、InternalReviewGate executor の起動を委譲する。委譲インターフェース（Port）の凍結は本 Issue の `application/basic-design.md §REQ-ME-003` で行い、実装は M5-B #164 で行う。

**理由**: 内部レビュー（並列 Agent 審査）は独立した業務概念であり stage-executor の責務範囲外。責務分割を設計書で先行凍結することで M5-B が安全に接続できる。

### 確定 R1-3: EXTERNAL_REVIEW Stage は Task.request_external_review() を呼び出し、ExternalReviewGate 生成を ExternalReviewGateService に委譲する

Stage 実行ループは「外部レビューを要求する」というドメイン操作を Task に命令し、Gate 生成・Discord 通知は ExternalReviewGateService に委譲する。

**理由**: ExternalReviewGate は独立した Aggregate（feature/external-review-gate 設計済み）。Tell, Don't Ask 原則に従い、Stage 実行ループは Task に「何をするか」を命令し（Task.request_external_review()）、Gate 生成の詳細は知らない。

### 確定 R1-4: LLMProviderError 5 分類はすべて Task.block() に帰着する

分類ごとのリトライ戦略は [`docs/design/tech-stack.md §LLM Adapter 運用方針`](../../design/tech-stack.md) に従う:

| エラー種別 | リトライ戦略 | BLOCKED への帰着条件 |
|---|---|---|
| SessionLost | 新規 session_id で 1 回のみ再投入 | 再投入も失敗 → 即 BLOCKED |
| RateLimited | exponential backoff 最大 3 回（1m→5m→15m）| 3 回失敗 → BLOCKED |
| AuthExpired | リトライなし | 即 BLOCKED |
| Timeout | SIGTERM→5 秒 grace→SIGKILL → SessionLost 相当に合流 | SessionLost と同様 |
| Unknown | リトライなし | 即 BLOCKED |

BLOCKED 後、Outbox Dispatcher は当該 Task に対するイベントを再ディスパッチしない（無限再試行防止）。last_error には masking gateway 通過済みのエラー情報を保存する。

**理由**: tech-stack.md §LLM Adapter 運用方針で確定済みのリトライ戦略を業務ルールとして参照する。

### 確定 R1-5: BLOCKED Task の回復は Task.unblock_retry() を通じてのみ行う

回復を呼び出せる経路:
1. admin CLI `retry-task <task_id>`（M5-C #165）
2. UI 「再試行」ボタン（M6-B #167、Phase 2）

どちらの経路も `StageExecutorService` が提供するエントリポイントを経由して `Task.unblock_retry()` を呼び出し、最後の Stage を再キューする。interfaces 層が domain を直接操作することは禁止。

**理由**: 回復経路を単一サービスに集中させることで、BLOCKED→IN_PROGRESS の遷移が必ず audit_log に記録される。M5-C が本接点を安全に利用できるよう設計書で先行凍結する。

### 確定 R1-6: 並行数制御は BAKUFU_MAX_CONCURRENT_STAGES 環境変数で制御する（MVP デフォルト = 1）

上限超過時は asyncio Queue でキューイングし、先行 Stage 完了後に順番に実行する。MVP ではシリアル実行（デフォルト 1）。

**理由**: MVP の検証対象は「Vモデル工程と外部レビューゲートの正しさ」であり並列実行は非スコープ（requirements/functional-scope.md §非スコープに明記）。並列実行には git worktree 分離が前提となり Phase 2 以降で設計する。

### 確定 R1-7: StageWorker は Bootstrap Stage 6.5 で asyncio.create_task として登録する

Outbox Dispatcher（Bootstrap Stage 6）の直後、FastAPI listener（Bootstrap Stage 8）より前に配置する。Bootstrap が shutdown シグナルを受信した際は、実行中の Stage subprocess を SIGTERM して graceful drain する。

**理由**: Outbox Dispatcher が起動している状態で StageWorker が動作することで、Stage 実行が発火する Domain Event が正しく配送される順序が保証される。

### 確定 R1-8: 1 プロンプトごとに subprocess を spawn し、応答完了で正常終了する（プロセス常駐なし）

各 LLM 呼び出しは subprocess を新規生成し、応答完了後に正常終了する。spawn 時に `bakufu_pid_registry` テーブルに INSERT し、完了時に DELETE する。Backend クラッシュ時は Bootstrap Stage 4（pid_registry GC）が孤児を処理する。

**理由**: tech-stack.md §LLM Adapter 運用方針の確定事項。プロセス常駐を避けることで孤児プロセスリスクを最小化する。

## 8. 制約・前提

| 区分 | 内容 |
|---|---|
| 依存 feature（前提完了）| task / workflow / agent / llm-client / external-review-gate / persistence-foundation / websocket-broadcast |
| 依存 feature（本 Issue が接点提供）| internal-review-gate（M5-B #164）/ admin-cli（M5-C #165）|
| 環境変数 | `BAKUFU_MAX_CONCURRENT_STAGES`（デフォルト 1）|
| LLM CLI | `claude` コマンドが認証済みで PATH に存在すること |
| OS | POSIX 準拠（SIGTERM / SIGKILL / psutil が動作する環境）|

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|---|---|---|
| 1 | Task の current_stage が WORK Stage に遷移すると Claude Code CLI が呼び出され、deliverable が保存され、次 Stage へ進む | UC-ME-001 | TC-ST-ME-001 |
| 2 | INTERNAL_REVIEW Stage に遷移すると InternalReviewGate 実行が委譲される（M5-B 実装後に結合検証）| UC-ME-002 | TC-ST-ME-002 |
| 3 | EXTERNAL_REVIEW Stage に遷移すると ExternalReviewGate が生成され Task が AWAITING_EXTERNAL_REVIEW になる | UC-ME-003 | TC-ST-ME-003 |
| 4 | AuthExpired エラー発生時に Task が BLOCKED になり last_error にマスキング済みエラー情報が保存される | UC-ME-004 | TC-ST-ME-004 |
| 5 | BLOCKED Task に retry 操作を実行すると Task が IN_PROGRESS に戻り最後の Stage が再キューされる（M5-C 実装後）| UC-ME-005 | TC-ST-ME-005 |
| 6 | BAKUFU_MAX_CONCURRENT_STAGES=1 の環境で複数 Task が同時に WORK Stage に遷移した場合、1 件ずつ順番に実行される | UC-ME-001 | TC-ST-ME-006 |

## 10. 開発者品質基準（CI 担保、業務要求ではない）

| # | 基準 | 検証方法 |
|---|---|---|
| Q-1 | pyright strict エラーゼロ | CI typecheck |
| Q-2 | ruff lint / format エラーゼロ | CI lint |
| Q-3 | エラー 5 分類の mock-based characterization テストが全て pass | pytest |
| Q-4 | StageKind 3 分岐の各パスに IT カバレッジがある | pytest |

## 11. 開放論点 (Open Questions)

| # | 論点 | 起票先 |
|---|---|---|
| Q-OPEN-1 | InternalReviewGateExecutorPort の詳細シグネチャは M5-B 設計時に確定 | #164 |
| Q-OPEN-2 | SessionLost リトライ時の新規 session_id 生成戦略（UUID v4 vs. StageId+attempt ハッシュ）| `application/detailed-design.md` §確定 D で凍結 |
| Q-OPEN-3 | RateLimited backoff 設定値の環境変数化の要否（MVP は固定値採用予定）| `application/detailed-design.md` §確定 E で凍結 |

## 12. Sub-issue 分割計画

| Sub-issue 名 | 紐付く UC | スコープ | 依存関係 |
|---|---|---|---|
| **A**: application（本 Issue #163）| UC-ME-001〜005 全て | StageExecutorService + StageWorker + Bootstrap 登録 | M4 完了済み |
| **B**: InternalReviewGate executor（M5-B #164）| UC-ME-002 実装 | InternalReviewGate executor + 本 Issue の委譲接点に接続 | 本 Issue 完了後 |
| **C**: admin-cli（M5-C #165）| UC-ME-005 実装 | list-blocked / retry-task 等 | 本 Issue 完了後（M5-B と並列可）|

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|---|---|---|
| Stage 実行ログ（stderr）| Claude Code CLI の stderr 全文 | 中（masking gateway 通過必須）|
| last_error | Task.block() 時のエラー文字列 | 中（masking gateway 通過必須）|
| session_id | Stage ID（UUID v4）| 低 |
| pid | subprocess の PID（bakufu_pid_registry テーブル）| 低 |
| cmd | subprocess 起動コマンド | 中（masking gateway 通過必須）|
| deliverable 本体 | LLM が生成した成果物 | 中（masking gateway 通過必須）|

## 14. 非機能要求

| 区分 | 要求 |
|---|---|
| パフォーマンス | BAKUFU_MAX_CONCURRENT_STAGES=1 では 1 Stage の実行中に後続 Stage はキューイングされる。キューイング遅延は Stage 実行完了時間（LLM 応答待ち）に依存 |
| 可用性 | Backend クラッシュ後の再起動時に pid_registry GC（Bootstrap Stage 4）が孤児 subprocess を SIGKILL し、StageWorker が Queue 残存アイテムを再処理する |
| セキュリティ | subprocess の stdout/stderr・cmd・last_error は永続化前に masking gateway を通過する（`infrastructure/security/masking.py` 単一ゲートウェイ）|
| 可搬性 | POSIX 準拠環境（Linux / macOS）。Windows は対象外（SIGTERM / psutil の挙動差異）|
