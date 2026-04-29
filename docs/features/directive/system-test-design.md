# E2E テスト設計書

> feature: `directive`（業務概念単位）
> 関連: [`feature-spec.md`](feature-spec.md) §9 受入基準 10（11 は repository IT）/ 12〜15（http-api sub-feature）

## 本書の役割

本書は **Directive 業務概念全体の E2E 検証戦略** を凍結する。各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / 将来の http-api / ui）の境界を跨いで観察される業務ふるまいを、ブラックボックスで検証する。

各 sub-feature の `test-design.md` は IT / UT と、親 E2E への参照だけを担当する。**E2E シナリオ定義の真実源は本書**とする。

## E2E スコープ

- domain sub-feature の Directive 構築 / link_task → repository sub-feature の永続化 → 再起動 → repository の復元 → domain の Directive 状態と構造的等価
- http-api sub-feature の HTTP API 経由 Directive 発行 + Task 同時起票 → 永続化 → 再起動 → GET による `text` masked 確認（Issue #60、受入基準 12〜15）
- 将来 ui sub-feature が完成した時点で Playwright 経由の E2E を本書に追記

## 観察主体

個人開発者 CEO（[`feature-spec.md §4 ペルソナ`](feature-spec.md)）。本 E2E では将来の `bakufu admin` CLI（`feature/admin-cli`）または直接 application 層を呼び出す test harness を用いて、CEO 観点での業務シナリオを観察する。

## E2E テストケース

| テストID | シナリオ | 観察主体の操作 | 期待結果（観察可能事象） | 紐付く受入基準 |
|---------|---------|--------------|---------------------|------------|
| TC-E2E-DR-001 | Directive の再起動跨ぎ保持（業務ルール R1-G） | 1) Directive を構築（task_id=None、有効なテキスト・委譲先 Room・発行日時） 2) `DirectiveRepository.save(directive)` 3) アプリ再起動相当（DB 接続再生成） 4) `DirectiveRepository.find_by_id(directive.id)` | 復元された Directive が元の Directive と構造的等価（id / text / target_room_id / created_at / task_id が一致）。アプリ再起動後も Directive の状態（text・Room 紐付け・発行日時）が保持される | 10 |
| TC-E2E-DR-002 | task_id 紐付け済み Directive の再起動跨ぎ保持 | 1) task_id=None で Directive を構築 2) `DirectiveRepository.save(directive)` 3) `directive.link_task(task_id)` で Task を紐付けた新 Directive を取得 4) `DirectiveRepository.save(updated_directive)` 5) 再起動 6) `DirectiveRepository.find_by_id(directive.id)` | 復元された Directive の task_id が更新済み TaskId と等価。Task 紐付けがアプリ再起動後も保持される | 10 |

| TC-E2E-DR-003 | HTTP API 経由 Directive 発行 + Task 起票（受入基準 12〜15 複合） | 1) POST /api/rooms/{room_id}/directives — secret を含む text → 201 DirectiveWithTaskResponse（directive.text masked / task.status=PENDING）2) GET /api/tasks/{task_id} → status=PENDING 3) POST /api/tasks/{task_id}/assign — agent_ids=[agent_id] → 200 TaskResponse（status=IN_PROGRESS）4) POST /api/rooms/{not_exist_room_id}/directives → 404 5) POST /api/rooms/{archived_room_id}/directives → 409 | POST 201 + directive.text masked / task.status=PENDING / assign 後 IN_PROGRESS / Room 不在 404 / Room archived 409 | 12, 13, 14, 15 |

将来追加予定:

- TC-E2E-DR-004: UI チャット欄経由での Directive 発行 + Task 生成（`directive/ui/` 完成後、Playwright）

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | 実 SQLite（テスト用 in-memory または tempfile） |
| domain 層 | 実 Directive Aggregate |
| application 層 | 直接呼び出し（test harness） |
| 外部 LLM / Discord / GitHub | 本 E2E では未使用（Directive 業務概念に外部 I/O なし） |

## カバレッジ基準

- 受入基準 10 が **E2E で最低 1 件**（TC-E2E-DR-001）検証される
- 永続化跨ぎでの構造的等価を保証（`save → restart → find_by_id` ラウンドトリップ）
- task_id 紐付け済み Directive のラウンドトリップは TC-E2E-DR-002 でカバー（UPSERT による task_id 更新の永続性確認）
- 受入基準 11（masking IT）は repository sub-feature の TC-IT-DRR-010-masking-* で検証する（本書の E2E 範囲外）
- 受入基準 12〜15 が TC-E2E-DR-003 として **E2E で最低 1 件** ずつ検証される（http-api sub-feature 完成後）
- TC-E2E-DR-003 の masking 検証は POST レスポンスの `directive.text` フィールドが masked 値であることを確認
- E2E はテスト戦略ガイド §E2E対象の判断「sub-feature 跨ぎの統合シナリオに絞る」に従う

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | 実 SQLite（テスト用 in-memory または tempfile） |
| domain 層 | 実 Directive / Task Aggregate |
| application 層 | 直接呼び出し（test harness）または HTTP API 経由（TC-E2E-DR-003）|
| HTTP API 層（TC-E2E-DR-003）| FastAPI TestClient（`httpx.AsyncClient` + `ASGITransport`）— 実 DB 使用 |
| 外部 LLM / Discord / GitHub | 本 E2E では未使用（Directive 業務概念に外部 I/O なし）|

## テストディレクトリ構造

```
backend/tests/e2e/
├── test_directive_lifecycle.py    # TC-E2E-DR-001, 002
└── test_directive_task_http_api.py # TC-E2E-DR-003（Issue #60 実装済み）
```

## 未決課題

- TC-E2E-DR-003 は http-api sub-feature（Issue #60）で実装済み
- TC-E2E-DR-004（UI Playwright）は将来の `directive/ui/` sub-feature 追加時に本書を更新する別 PR で起票
- masking 不可逆性の E2E 確認（text に secret を含む Directive を永続化して再起動後に `<REDACTED:*>` が保持されること）は TC-E2E-DR-001/002 の派生として将来追加可能
