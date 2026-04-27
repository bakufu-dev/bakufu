# Domain Event と補償設計（Outbox / Dispatcher）

> [`../domain-model.md`](../domain-model.md) の補章。Domain Event 一覧と「結果整合の前提で発生する後続処理失敗を補償する」Transactional Outbox 設計を凍結する。

## Domain Event 一覧

| イベント | 発火元 | 受け手 / 効果 |
|---------|------|------------|
| `DirectiveIssued` | Directive 作成時 | Task 生成（application 層） |
| `TaskAssigned` | Task.assign() | Agent 通知、UI 更新 |
| `DeliverableCommitted` | Task.commit_deliverable() | 次 Stage の自動開始判定 |
| `ExternalReviewRequested` | Task.request_external_review() | ExternalReviewGate 生成、reviewer 通知（Discord/Slack） |
| `ExternalReviewApproved` | Gate.approve() | Task.advance() |
| `ExternalReviewRejected` | Gate.reject() | Task.advance(transition_id=REJECTED で差し戻し) |
| `TaskBlocked` | Task.block() | UI 更新、Notifier で人間に通知 |
| `TaskCompleted` | Task が終端 Stage で APPROVED | Empire 全体への通知、CEO ダッシュボード更新 |
| `TaskCancelled` | Task.cancel() | 関連 Gate を CANCELLED 化（`Gate.cancel()` 呼び出し） |
| `OutboxDeadLettered` | Dispatcher が 5 回失敗で `DEAD_LETTER` 化 | Notifier で人間に通知（dead-letter 専用通知経路） |

イベントは **同期メソッド呼び出し**ではなく、application 層の Use Case が次の Aggregate を更新する形で実現する（複数 Aggregate にまたがる更新は結果整合）。

## Transactional Outbox（補償設計）

結果整合の前提では「Aggregate を保存したのにイベントの後続処理（Notifier 通知 / 次 Aggregate の更新 / WebSocket ブロードキャスト）が失敗する」可能性が必ず残る。これを補償する仕組みを **Transactional Outbox パターン** で MVP に組み込む。

### 設計方針

| 項目 | 採用 | 不採用候補 / 理由 |
|----|----|----|
| 永続化先 | SQLite の `domain_event_outbox` テーブル | Redis / RabbitMQ：MVP のローカルファースト要件で外部依存を増やさない（YAGNI） |
| イベントの書き込み | Aggregate 保存と**同一トランザクション**で Outbox に INSERT | 別 Tx：Aggregate は保存されたがイベントが失われる窓が生じる（at-most-once になり MVP 要件不適合） |
| 配送セマンティクス | at-least-once（同一 event を複数回 dispatch しうる） | exactly-once：分散トランザクションが必要で MVP 範囲外 |
| 受信側冪等性 | Handler は `event_id` を見て重複を no-op 化 | — |
| Dispatcher | Backend プロセス内の常駐 asyncio task（1 秒間隔で polling） | 別プロセス worker：シングルプロセス前提なので不要（YAGNI） |
| 排他制御 | **不要**（シングルプロセス前提）。`status` 列は単に「現在実行中マーカー」として使用 | 楽観排他 / version 列：マルチプロセス対応は Phase 2 で改めて設計（YAGNI） |
| Retry 戦略 | exponential backoff（10s → 1m → 5m → 30m → 30m）、最大 5 回 | — |
| Dead-letter | 5 回失敗時に `status=DEAD_LETTER` をスタンプ。CLI コマンドで手動再投入可能（UI は Phase 2） | — |
| Dead-letter 通知 | `OutboxDeadLettered` イベントを Notifier 経由で Discord に発信（dead-letter 専用ハンドラ） | sliding：通知漏れで放置されるリスク |

### `domain_event_outbox` 行スキーマ

| 列 | 型 | 意図 |
|----|----|----|
| `event_id` | UUID（PK） | イベント一意識別。Handler 側冪等性キー |
| `event_kind` | enum（`DirectiveIssued` / `TaskAssigned` / ...） | ディスパッチ先 Handler の決定 |
| `aggregate_id` | UUID | 発火元 Aggregate（debug / 順序付け用） |
| `payload_json` | JSON | イベント本体（VO のシリアライズ）。永続化前に [`storage.md`](storage.md) §シークレットマスキング規則 を適用。マスキング配線は SQLAlchemy `before_insert` / `before_update` event listener で**強制ゲートウェイ化**する（[`feature/persistence-foundation`](../../features/persistence-foundation/detailed-design.md) §確定 B / F）— 直 INSERT / raw SQL 経路でも listener が走るため呼び忘れ経路ゼロ |
| `created_at` | datetime（UTC） | 発火時刻 |
| `status` | `OutboxStatus` | `PENDING` / `DISPATCHING` / `DISPATCHED` / `DEAD_LETTER` |
| `attempt_count` | int | リトライ回数 |
| `next_attempt_at` | datetime（UTC） | 次回試行時刻（backoff 計算結果） |
| `last_error` | str（NULL 可） | 直近失敗の例外メッセージ。永続化前にマスキング適用（同上、event listener 強制ゲートウェイ） |
| `updated_at` | datetime（UTC） | 行更新時刻（再起動時のリカバリ判定に使用） |
| `dispatched_at` | datetime（UTC, NULL 可） | `DISPATCHED` 遷移時刻 |

### Dispatcher の動作（確定）

| 段階 | 動作 |
|----|----|
| 1. polling SQL | `(status='PENDING' AND next_attempt_at <= now()) OR (status='DISPATCHING' AND updated_at < now() - 5min)` の行を SELECT（最大 N 件） |
| 2. 状態マーキング | 行 `status=DISPATCHING`, `updated_at=now()` に更新（シングルプロセスのため排他不要） |
| 3. dispatch | `event_kind` から Handler を解決し `await handler(payload)` |
| 4. 成功 | `status=DISPATCHED`, `dispatched_at=now()` |
| 5. 失敗 | `attempt_count += 1`、`next_attempt_at = now() + backoff(attempt_count)`、`last_error` 記録（マスキング後）、`status=PENDING` に戻す。`attempt_count >= 5` なら `status=DEAD_LETTER` + `OutboxDeadLettered` イベントを別行として Outbox に追記 |
| 6. プロセス再起動時 | `DISPATCHING` のまま残った行は `updated_at < now() - 5min` 条件で **強制再取得**される。これにより再起動時の永久 stuck を回避（クラッシュ復旧条件） |

**`DISPATCHING` のまま再起動した場合のリカバリ条件**:

`updated_at` の存在意義は、Dispatcher 中の行を「実行中」マーキングしたまま Backend がクラッシュ・再起動しても、5 分経過後の polling で自動的に再取得されることを保証することにある。`next_attempt_at` だけでは「未来時刻に next_attempt_at が設定された後にプロセスが落ちる」ケースで stuck するため、`DISPATCHING` 行の `updated_at` ベースのリカバリ条件を必須とする。

### Handler 一覧（MVP）

| event_kind | Handler 役割 |
|----|----|
| `DirectiveIssued` | Task Aggregate を生成し保存（次 Tx） |
| `TaskAssigned` | WebSocket ブロードキャスト + Agent 呼び出し（LLM Adapter） |
| `DeliverableCommitted` | 次 Stage の自動開始判定 + WebSocket ブロードキャスト |
| `ExternalReviewRequested` | ExternalReviewGate 生成 + Discord Notifier 呼び出し + WebSocket |
| `ExternalReviewApproved` / `ExternalReviewRejected` | Task.advance() 呼び出し（次 Tx） + WebSocket |
| `TaskBlocked` | WebSocket ブロードキャスト + Discord Notifier に「人間介入要」通知 |
| `TaskCompleted` | git push / WebSocket / ダッシュボード更新通知 |
| `TaskCancelled` | 関連 Gate を `Gate.cancel()` で CANCELLED 化（`ReviewDecision.CANCELLED` に遷移） + WebSocket |
| `OutboxDeadLettered` | Discord Notifier に「dead-letter 発生（admin 対応要）」を通知。通知失敗時は本イベント自身の retry policy に従う（無限ループ防止のため最大 5 回後はログ出力のみで打ち切り） |

### `BLOCKED` Task に対する Outbox の扱い

Task が `BLOCKED` 状態のとき、その Task に紐づく `TaskAssigned` / `DeliverableCommitted` 等の後続イベントは **dispatch されない**。Dispatcher は Handler 内で「Task の現状態」を確認し、`BLOCKED` なら no-op で `DISPATCHED` にスタンプして次に進む（無限再試行防止）。

Owner が `bakufu admin retry-task` を実行すると Task が `IN_PROGRESS` に戻り、必要なイベントは application 層が再発行する（Outbox に新規 INSERT）。古い `DISPATCHED` イベントを再投入する経路は持たない（冪等性を保つため）。

### 受信側冪等性の責務

各 Handler は `event_id` を `event_id_consumed` テーブル（または handler 固有の冪等キー列）に記録し、再ディスパッチを no-op 化する。

特に：
- **Notifier**: Discord メッセージ送信は `event_id` を embed footer に埋め、二重送信を Discord 側で抑止できないため受信側で `event_id_consumed` をチェック
- **WebSocket**: 同一 `event_id` の再配信はクライアント側で Idempotent に処理（state を再代入するだけなので問題なし）
- **Aggregate 更新**: `Task.advance()` 等は同一 transition_id × event_id で実行済みなら no-op

### dead-letter の運用

`DEAD_LETTER` 行は CLI コマンド `bakufu admin retry-event <event_id>` で `status=PENDING`, `attempt_count=0` にリセットして再投入する。MVP では UI を作らない（YAGNI）。

dead-letter 発生時には `OutboxDeadLettered` イベントが Outbox に追記され、Discord Notifier 経由で Owner に通知される。これにより放置防止を実現する。

dead-letter の **発見手段** は admin CLI で提供する（[`../tech-stack.md`](../tech-stack.md) §Admin CLI 運用方針）：

| コマンド | 用途 |
|----|----|
| `bakufu admin list-dead-letters [--since <iso8601>] [--kind <event_kind>]` | dead-letter 一覧を JSON / table で出力 |
| `bakufu admin list-blocked [--since <iso8601>]` | `BLOCKED` Task 一覧を JSON / table で出力 |
| `bakufu admin retry-event <event_id>` | 単一 dead-letter を `PENDING` に戻して再投入 |
| `bakufu admin retry-task <task_id>` | `BLOCKED` Task を `IN_PROGRESS` に戻し、現 Stage を再実行 |
| `bakufu admin cancel-task <task_id> --reason <text>` | Task を `CANCELLED` に遷移、関連 Gate も連鎖 |
