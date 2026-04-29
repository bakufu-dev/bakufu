# E2E テスト設計書

> feature: `task`（業務概念単位）
> 関連: [`feature-spec.md`](feature-spec.md) §9 受入基準 16（17 は repository IT）/ 18〜23（http-api sub-feature）

## 本書の役割

本書は **Task 業務概念全体の E2E 検証戦略** を凍結する。各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / 将来の http-api / ui）の境界を跨いで観察される業務ふるまいを、ブラックボックスで検証する。

各 sub-feature の `test-design.md` は IT / UT のみを担当する。**E2E は本書だけが扱う**（sub-feature の test-design.md には E2E を書かない）。

## E2E スコープ

- domain sub-feature の Task 構築 / 状態遷移 → repository sub-feature の永続化 → 再起動 → repository の復元 → domain の Task 状態と構造的等価
- http-api sub-feature の HTTP API 経由 Task lifecycle（取得 / assign / cancel / unblock / commit_deliverable）→ 永続化 → 再起動 → GET による `last_error` / `body_markdown` masked 確認（Issue #60、受入基準 18〜23）
- 将来 ui sub-feature が完成した時点で Playwright 経由の E2E を本書に追記

## 観察主体

個人開発者 CEO（[`feature-spec.md §4 ペルソナ`](feature-spec.md)）。本 E2E では将来の `bakufu admin` CLI（`feature/admin-cli`）または直接 application 層を呼び出す test harness を用いて、CEO 観点での業務シナリオを観察する。

## E2E テストケース

| テストID | シナリオ | 観察主体の操作 | 期待結果（観察可能事象） | 紐付く受入基準 |
|---------|---------|--------------|---------------------|------------|
| TC-E2E-TS-001 | Task の再起動跨ぎ保持（業務ルール R1-16） | 1) Task を構築（status=PENDING、assigned_agent_ids=[]、deliverables={}）2) `TaskRepository.save(task)` 3) アプリ再起動相当（DB 接続再生成） 4) `TaskRepository.find_by_id(task.id)` | 復元された Task が元の Task と構造的等価（id / room_id / directive_id / current_stage_id / status / assigned_agent_ids / deliverables / last_error / created_at / updated_at が一致） | 16 |
| TC-E2E-TS-002 | BLOCKED 状態 Task の再起動跨ぎ保持（last_error 含む） | 1) IN_PROGRESS Task を構築 2) `task.block(reason, last_error='AuthExpired: ...')` で BLOCKED 化 3) `TaskRepository.save(blocked_task)` 4) 再起動 5) `TaskRepository.find_by_id(task.id)` | 復元された Task が status=BLOCKED、last_error が（マスキング適用後の）保持値と等価。アプリ再起動後も BLOCKED 状態と復旧用エラー情報が保持される | 16 |

| TC-E2E-TS-003 | HTTP API 経由 Task lifecycle + 再起動跨ぎ一貫性（受入基準 18〜23 複合） | 1) GET /api/tasks/{task_id}（Directive 経由で起票済み Task）→ 200 TaskResponse（last_error=null / status=PENDING）2) POST /api/tasks/{task_id}/assign — agent_ids=[agent_id] → 200（status=IN_PROGRESS）3) POST /api/tasks/{task_id}/deliverables/{stage_id} — body_markdown="ANTHROPIC_API_KEY=sk-ant-xxxx..." → 200 TaskResponse（body_markdown masked）4) アプリ再起動相当（DB 接続再生成）5) GET /api/tasks/{task_id} → status=IN_PROGRESS 保持、deliverables[stage_id].body_markdown masked 6) PATCH /api/tasks/{task_id}/cancel → 200（status=CANCELLED）7) PATCH /api/tasks/{task_id}/cancel（再試行）→ 409（terminal_violation）8) GET /api/tasks/{not_exist_id} → 404 | GET 200 + last_error masked / assign 後 IN_PROGRESS / deliverable commit 後 body_markdown masked / 再起動後状態保持 / cancel 200 + CANCELLED / 再 cancel 409 / 不在 404 | 18, 19, 20, 22, 23 |
| TC-E2E-TS-004 | HTTP API 経由 BLOCKED Task 復旧（受入基準 21） | 1) Task を BLOCKED 状態にする（domain 層直接操作 + save）2) PATCH /api/tasks/{task_id}/unblock → 200 TaskResponse（status=IN_PROGRESS, last_error=null）3) PATCH /api/tasks/{task_id}/unblock（再試行）→ 409（IN_PROGRESS からの unblock_retry は state machine で禁止）| unblock 200 + IN_PROGRESS + last_error=null / 再 unblock 409 | 21 |

将来追加予定:

- TC-E2E-TS-005: UI 経由での Task 進行 + External Review 承認（`task/ui/` 完成後、Playwright）

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | 実 SQLite（テスト用 in-memory または tempfile） |
| domain 層 | 実 Task / Deliverable / Attachment Aggregate |
| application 層 | 直接呼び出し（test harness） |
| 外部 LLM / Discord / GitHub | 本 E2E では未使用（task 業務概念に外部 I/O なし） |

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | 実 SQLite（テスト用 in-memory または tempfile） |
| domain 層 | 実 Task / Deliverable / Attachment Aggregate |
| application 層 | 直接呼び出し（test harness）または HTTP API 経由（TC-E2E-TS-003, 004）|
| HTTP API 層（TC-E2E-TS-003, 004）| FastAPI TestClient（`httpx.AsyncClient` + `ASGITransport`）— 実 DB 使用 |
| 外部 LLM / Discord / GitHub | 本 E2E では未使用（task 業務概念に外部 I/O なし）|

## カバレッジ基準

- 受入基準 16 が **E2E で最低 1 件**（TC-E2E-TS-001）検証される
- 永続化跨ぎでの構造的等価を保証（`save → restart → find_by_id` ラウンドトリップ）
- BLOCKED 状態（last_error 含む）のラウンドトリップは TC-E2E-TS-002 でカバー（masking 不可逆性により last_error は `<REDACTED:*>` を含む形で復元される点に注意）
- 受入基準 18〜23 が TC-E2E-TS-003 / TC-E2E-TS-004 として **E2E で最低 1 件** ずつ検証される（http-api sub-feature 完成後）
- TC-E2E-TS-003 の masking 検証は GET レスポンスの `deliverables[*].body_markdown` フィールドが `<REDACTED:*>` であることを確認
- E2E はテスト戦略ガイド §E2E対象の判断「sub-feature 跨ぎの統合シナリオに絞る」に従う

## テストディレクトリ構造

```
backend/tests/e2e/
├── test_task_lifecycle.py     # TC-E2E-TS-001, 002
├── test_task_http_api.py      # TC-E2E-TS-003（http-api sub-feature 完成後）
└── test_task_unblock_api.py   # TC-E2E-TS-004（http-api sub-feature 完成後）
```

## 未決課題

- TC-E2E-TS-003, 004 は http-api sub-feature（Issue #60）の実装完了後に実行可能。本書は検証シナリオを凍結済み
- TC-E2E-TS-005（UI Playwright）は将来の `task/ui/` sub-feature 追加時に本書を更新する別 PR で起票
- External Review 経路（AWAITING_EXTERNAL_REVIEW → approve/reject → DONE）の E2E は `feature/external-review-gate` Aggregate が完成した時点で追加する
