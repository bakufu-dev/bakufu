# E2E テスト設計書

> feature: `workflow`（業務概念単位）
> 関連: [`feature-spec.md`](feature-spec.md) §9 受入基準 11（12 は repository IT）/ 受入基準 22（http-api E2E）

## 本書の役割

本書は **Workflow 業務概念全体の E2E 検証戦略** を凍結する。各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / 将来の http-api / ui）の境界を跨いで観察される業務ふるまいを、ブラックボックスで検証する。

各 sub-feature の `test-design.md` は IT / UT のみを担当する。**E2E は本書だけが扱う**（sub-feature の test-design.md には E2E を書かない）。

## E2E スコープ

- domain sub-feature の Workflow 構築 → repository sub-feature の永続化 → 再起動 → repository の復元 → domain の Workflow 状態と構造的等価
- http-api sub-feature の HTTP エンドポイント経由での Workflow CRUD → 永続化 → 再起動 → 取得の一貫性確認
- 将来 ui sub-feature が完成した時点で Playwright 経由の E2E を本書に追記

## 観察主体

個人開発者 CEO（[`feature-spec.md §4 ペルソナ`](feature-spec.md)）。TC-E2E-WF-001 / 002 では直接 application 層を呼び出す test harness を用いる。TC-E2E-WF-003 では httpx TestClient 経由で HTTP API を呼び出す（FastAPI TestClient + 実 SQLite）。

## E2E テストケース

| テストID | シナリオ | 観察主体の操作 | 期待結果（観察可能事象） | 紐付く受入基準 |
|---------|---------|--------------|---------------------|------------|
| TC-E2E-WF-001 | Workflow の再起動跨ぎ保持（業務ルール R1-11） | 1) Workflow 構築（name="V モデル開発フロー"、3 Stage + 2 Transition、WORK Stage のみ）2) `WorkflowRepository.save(workflow)` 3) アプリ再起動相当（DB 接続再生成） 4) `WorkflowRepository.find_by_id(workflow.id)` | 復元された Workflow が元の Workflow と構造的等価（id / name / stages / transitions / entry_stage_id が一致。Stage の required_role frozenset も等価） | 11 |
| TC-E2E-WF-002 | Workflow JSON プリセットからの構築と永続化（V モデル開発室） | 1) V モデル開発室プリセット JSON（13 Stage / 15 Transition）を `from_dict` で構築 2) `WorkflowRepository.save(workflow)` 3) 再起動 4) `WorkflowRepository.find_by_id(workflow.id)` | 13 Stage / 15 Transition / 正確な entry_stage_id が保持されている（notify_channels なし Workflow のため、ラウンドトリップで構造的等価が成立）| 10, 11 |

| TC-E2E-WF-003 | HTTP API 経由 Workflow CRUD の再起動跨ぎ一貫性（業務ルール R1-11, R1-14, R1-15）| 1) `POST /api/rooms/{room_id}/workflows`（JSON 定義）→ 2) `GET /api/workflows/{id}` で確認 → 3) `PATCH /api/workflows/{id}` で name 更新 → 4) アプリ再起動相当（DB 接続再生成）→ 5) `GET /api/workflows/{id}` で再取得 | 取得 Workflow の name が更新後の値と一致。stages / transitions / entry_stage_id が永続化後も等価。`GET /api/rooms/{room_id}/workflows` が同一 Workflow を返す | 22 |

将来追加予定:

- TC-E2E-WF-004: UI 経由での Workflow 編集（`workflow/ui/` 完成後、Playwright）

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | 実 SQLite（テスト用 in-memory または tempfile） |
| domain 層 | 実 Workflow / Stage / Transition / NotifyChannel / CompletionPolicy Aggregate |
| application 層 | 直接呼び出し（test harness） |
| 外部 LLM / Discord / GitHub | 本 E2E では未使用（business 概念に外部 I/O なし） |

## カバレッジ基準

- 受入基準 11 が **E2E で最低 1 件**（TC-E2E-WF-001）検証される
- 受入基準 22 が **E2E で最低 1 件**（TC-E2E-WF-003）検証される
- 永続化跨ぎでの構造的等価を保証（`save → restart → find_by_id` ラウンドトリップ）
- notify_channels 不在 Workflow でのラウンドトリップは TC-E2E-WF-001 / 002 / 003 でカバー（§確定 H §不可逆性による制約のため、EXTERNAL_REVIEW Stage を含む E2E ラウンドトリップは不可）
- E2E はテスト戦略ガイド §E2E対象の判断「sub-feature 跨ぎの統合シナリオに絞る」に従う

## テストディレクトリ構造

```
backend/tests/e2e/
├── test_workflow_lifecycle.py          # TC-E2E-WF-001, 002
└── test_workflow_http_api.py           # TC-E2E-WF-003
```

## 未決課題

- TC-E2E-WF-004 は将来の `workflow/ui/` sub-feature 追加時に本書を更新する別 PR で起票
- EXTERNAL_REVIEW Stage を含む Workflow の「再起動後に通知設定が保持される」E2E は §確定 H §不可逆性（masking 後 find_by_id で ValidationError）の制約があるため、`feature/notify-router` で「masked target の通知再登録フロー」が確定するまで保留
- TC-E2E-WF-003 は HTTP API 検証のため httpx TestClient を使用。外部 LLM / Discord は不使用（notify_channels なし Workflow のみを E2E 対象とする）
