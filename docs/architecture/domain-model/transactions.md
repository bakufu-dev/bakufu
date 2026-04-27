# トランザクション境界とレンダリング例

> [`../domain-model.md`](../domain-model.md) の補章。Aggregate 境界をまたぐ操作の Tx 分割例と、V モデル開発室の Workflow 構成例を凍結する。

## トランザクション境界の原則

- 1 トランザクションで 1 Aggregate のみを更新する
- 複数 Aggregate にまたがる整合性は Domain Event（Outbox 経由）で結果整合
- Outbox 行の INSERT は Aggregate 更新と **同一トランザクション**内（書き漏れを物理的に防ぐ）
- 添付ファイルの物理書き込みは Aggregate Tx の**外**（content-addressable + GC で整合性を回復）

## トランザクション境界の実例

### CEO directive 受付 → Task 生成

| 順 | Tx | 操作 |
|---|----|----|
| 1 | Tx-1 | Directive Aggregate を保存 + Outbox に `DirectiveIssued` 行を INSERT |
| 2 | — | Dispatcher が `DirectiveIssued` を pickup |
| 3 | Tx-2 | Workflow を読み、Task Aggregate を生成して保存 + Outbox に `TaskAssigned` 行を INSERT |
| 4 | — | Dispatcher が `TaskAssigned` を pickup |
| 5 | Tx-3 | Notifier 経由で Agent 通知（Discord / Slack）— 失敗してもリトライ可、結果整合 |

### Stage 完了 → 外部レビュー要求

| 順 | Tx | 操作 |
|---|----|----|
| 1 | Tx-1 | Task.commit_deliverable() で Deliverable 登録 + Outbox に `DeliverableCommitted` を INSERT |
| 2 | Tx-2 | Stage が EXTERNAL_REVIEW なら Task.request_external_review() で ExternalReviewGate 生成保存（status を AWAITING_EXTERNAL_REVIEW に更新）+ Outbox に `ExternalReviewRequested` を INSERT |
| 3 | — | Dispatcher が `ExternalReviewRequested` を pickup |
| 4 | Tx-3 | Notifier 経由で reviewer 通知 — 失敗してもリトライ可、5 回失敗で dead-letter 化 |

### 外部レビュー承認 → 次 Stage へ

| 順 | Tx | 操作 |
|---|----|----|
| 1 | Tx-1 | Gate.approve() で decision を APPROVED に更新 + Outbox に `ExternalReviewApproved` を INSERT |
| 2 | — | Dispatcher が `ExternalReviewApproved` を pickup |
| 3 | Tx-2 | Task.advance() で current_stage_id を遷移先に更新 + 必要なら次 Stage 用の `TaskAssigned` を Outbox に INSERT |

### LLM Adapter 復旧不能エラー → BLOCKED

| 順 | Tx | 操作 |
|---|----|----|
| 1 | — | Backend の LLM Adapter Handler が CLI subprocess の `AuthExpired` を検知 |
| 2 | Tx-1 | Task.block(reason, last_error) で status=BLOCKED 化（`last_error` はマスキング適用済み）+ Outbox に `TaskBlocked` を INSERT |
| 3 | — | Dispatcher が `TaskBlocked` を pickup |
| 4 | Tx-2 | Notifier 経由で Owner に「人間介入要」通知（Discord） |

### Admin CLI による Task 復旧

| 順 | Tx | 操作 |
|---|----|----|
| 1 | Tx-1 | `audit_log` に `command=retry-task` を INSERT（actor / args / executed_at） |
| 2 | Tx-2 | Task.unblock_retry() で status=IN_PROGRESS に戻し、Outbox に `TaskAssigned`（再実行用）を INSERT |
| 3 | — | Dispatcher が pickup し、LLM Adapter が再実行 |

各 Tx は単一 Aggregate の更新に閉じる。**複数 Aggregate を 1 Tx で更新しない**。

## レンダリング例（V モデル開発室）

```
Workflow: V モデル開発フロー
├── Stage: 要求分析 (WORK, REQUIRED_ROLE=LEADER)
├── Stage: 要求分析レビュー (EXTERNAL_REVIEW, notify=[Discord])
├── Stage: 要件定義 (WORK, REQUIRED_ROLE=LEADER+UX)
├── Stage: 要件定義レビュー (EXTERNAL_REVIEW, notify=[Discord])
├── Stage: 基本設計 (WORK, REQUIRED_ROLE=DEVELOPER+UX)
├── Stage: 基本設計レビュー (EXTERNAL_REVIEW, notify=[Discord])
├── Stage: 詳細設計 (WORK, REQUIRED_ROLE=DEVELOPER)
├── Stage: 詳細設計レビュー (EXTERNAL_REVIEW)
├── Stage: 実装 (WORK, REQUIRED_ROLE=DEVELOPER)
├── Stage: ユニットテスト (WORK, REQUIRED_ROLE=TESTER)
├── Stage: 結合テスト (WORK, REQUIRED_ROLE=TESTER)
├── Stage: E2E テスト (WORK, REQUIRED_ROLE=TESTER)
└── Stage: 完了レビュー (EXTERNAL_REVIEW, notify=[Discord])

Transitions:
- 要求分析 ─APPROVED→ 要件定義
- 要求分析 ─REJECTED→ 要求分析（自己ループで再作成）
- 要件定義 ─APPROVED→ 基本設計
- 要件定義 ─REJECTED→ 要求分析（差し戻し 1 段）
- 基本設計 ─REJECTED→ 要件定義（差し戻し 1 段）
- ...
- 完了レビュー ─APPROVED→ （終端、Task DONE）
- 完了レビュー ─REJECTED→ 該当工程（差し戻し）
```

DAG なので任意の差し戻し経路を定義可能。UI 側は `react-flow` 等でビジュアル編集できる想定（MVP では JSON 編集 / プリセットから選択で OK）。
