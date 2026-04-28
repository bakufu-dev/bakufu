# E2E テスト設計書

> feature: `task`（業務概念単位）
> 関連: [`feature-spec.md`](feature-spec.md) §9 受入基準 16（17 は repository IT）

## 本書の役割

本書は **Task 業務概念全体の E2E 検証戦略** を凍結する。各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / 将来の http-api / ui）の境界を跨いで観察される業務ふるまいを、ブラックボックスで検証する。

各 sub-feature の `test-design.md` は IT / UT のみを担当する。**E2E は本書だけが扱う**（sub-feature の test-design.md には E2E を書かない）。

## E2E スコープ

- domain sub-feature の Task 構築 / 状態遷移 → repository sub-feature の永続化 → 再起動 → repository の復元 → domain の Task 状態と構造的等価
- 将来 http-api / ui sub-feature が完成した時点で `curl` / Playwright 経由の E2E を本書に追記

## 観察主体

個人開発者 CEO（[`feature-spec.md §4 ペルソナ`](feature-spec.md)）。本 E2E では将来の `bakufu admin` CLI（`feature/admin-cli`）または直接 application 層を呼び出す test harness を用いて、CEO 観点での業務シナリオを観察する。

## E2E テストケース

| テストID | シナリオ | 観察主体の操作 | 期待結果（観察可能事象） | 紐付く受入基準 |
|---------|---------|--------------|---------------------|------------|
| TC-E2E-TS-001 | Task の再起動跨ぎ保持（業務ルール R1-16） | 1) Task を構築（status=PENDING、assigned_agent_ids=[]、deliverables={}）2) `TaskRepository.save(task)` 3) アプリ再起動相当（DB 接続再生成） 4) `TaskRepository.find_by_id(task.id)` | 復元された Task が元の Task と構造的等価（id / room_id / directive_id / current_stage_id / status / assigned_agent_ids / deliverables / last_error / created_at / updated_at が一致） | 16 |
| TC-E2E-TS-002 | BLOCKED 状態 Task の再起動跨ぎ保持（last_error 含む） | 1) IN_PROGRESS Task を構築 2) `task.block(reason, last_error='AuthExpired: ...')` で BLOCKED 化 3) `TaskRepository.save(blocked_task)` 4) 再起動 5) `TaskRepository.find_by_id(task.id)` | 復元された Task が status=BLOCKED、last_error が（マスキング適用後の）保持値と等価。アプリ再起動後も BLOCKED 状態と復旧用エラー情報が保持される | 16 |

将来追加予定:

- TC-E2E-TS-003: HTTP API 経由での Task lifecycle（`task/http-api/` 完成後）
- TC-E2E-TS-004: UI 経由での Task 進行 + External Review 承認（`task/ui/` 完成後、Playwright）

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | 実 SQLite（テスト用 in-memory または tempfile） |
| domain 層 | 実 Task / Deliverable / Attachment Aggregate |
| application 層 | 直接呼び出し（test harness） |
| 外部 LLM / Discord / GitHub | 本 E2E では未使用（task 業務概念に外部 I/O なし） |

## カバレッジ基準

- 受入基準 16 が **E2E で最低 1 件**（TC-E2E-TS-001）検証される
- 永続化跨ぎでの構造的等価を保証（`save → restart → find_by_id` ラウンドトリップ）
- BLOCKED 状態（last_error 含む）のラウンドトリップは TC-E2E-TS-002 でカバー（masking 不可逆性により last_error は `<REDACTED:*>` を含む形で復元される点に注意）
- E2E はテスト戦略ガイド §E2E対象の判断「sub-feature 跨ぎの統合シナリオに絞る」に従う

## テストディレクトリ構造

```
backend/tests/e2e/
└── test_task_lifecycle.py    # TC-E2E-TS-001, 002
```

## 未決課題

- TC-E2E-TS-003, 004 は将来の sub-feature 追加時に本書を更新する別 PR で起票
- External Review 経路（AWAITING_EXTERNAL_REVIEW → approve/reject → DONE）の E2E は `feature/external-review-gate` Aggregate が完成した時点で追加する
