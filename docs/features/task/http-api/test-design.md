# テスト設計書

> feature: `task` / sub-feature: `http-api`
> 関連 Issue: [#60 feat(task-http-api): Directive + Task lifecycle HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/60)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../system-test-design.md`](../system-test-design.md)

## 本書の役割

本書は `basic-design.md §モジュール契約` の REQ-TS-HTTP-001〜006 と、`detailed-design.md` の確定事項 A〜G を、PR #111 の検証範囲にだけ紐付ける。将来追加する IT / UT 予定ケースは、その PR で追記する。

**書くこと**:
- PR #111 で実装済みの Task HTTP API E2E 検証
- Room.members 認可、担当 Agent 検証、masking、Task lifecycle の観測点
- factory / raw fixture の現状
- カバレッジ基準

**書かないこと**:
- 将来拡張用の IT / UT 予定ケース
- DB 直接確認を前提にした受入検証

## テストケース ID 採番規則

| 番号帯 | 用途 |
|---|---|
| TC-E2E-TS-003 | 親 system-test-design 管轄の E2E（Directive 起点の Task lifecycle）|
| TC-E2E-TS-004 | 親 system-test-design 管轄の E2E（BLOCKED Task unblock）|
| TC-E2E-TS-005 | 認可境界 E2E（Room.members 外 assign 拒否）|
| TC-E2E-TS-006 | 認可境界 E2E（未担当 submitter 拒否）|

## テストマトリクス

| 要件 ID | 実装アーティファクト | テストケース ID | テストレベル | 種別 | 実装済みテスト |
|---|---|---|---|---|---|
| REQ-TS-HTTP-001（Task 取得）| `task_router` GET + `TaskService.find_by_id` | TC-E2E-TS-003 / TC-E2E-TS-004 | E2E | 正常系 / 異常系 | `test_directive_issue_creates_task_and_task_lifecycle_is_observable` / `test_blocked_task_can_be_unblocked_through_public_api` |
| REQ-TS-HTTP-002（Room 内 Task 一覧）| `task_router` GET list + `TaskService.find_all_by_room` | TC-E2E-TS-003 | E2E | 正常系 | `test_directive_issue_creates_task_and_task_lifecycle_is_observable` |
| REQ-TS-HTTP-003（assign）| `TaskService.assign` + Room.members 認可 | TC-E2E-TS-003 / TC-E2E-TS-005 | E2E | 正常系 / 認可 | `test_directive_issue_creates_task_and_task_lifecycle_is_observable` / `test_task_assignment_rejects_agent_outside_room` |
| REQ-TS-HTTP-004（cancel）| `TaskService.cancel` | TC-E2E-TS-003 | E2E | 正常系 / conflict | `test_directive_issue_creates_task_and_task_lifecycle_is_observable` |
| REQ-TS-HTTP-005（unblock）| `TaskService.unblock_retry` | TC-E2E-TS-004 | E2E | 正常系 / conflict | `test_blocked_task_can_be_unblocked_through_public_api` |
| REQ-TS-HTTP-006（deliverable）| `TaskService.commit_deliverable` + 担当 Agent 検証 | TC-E2E-TS-003 / TC-E2E-TS-006 | E2E | 正常系 / 認可 | `test_directive_issue_creates_task_and_task_lifecycle_is_observable` / `test_deliverable_rejects_unassigned_submitter` |
| 確定A masking | `TaskResponse.last_error` / `DeliverableResponse.body_markdown` field_serializer | TC-E2E-TS-003 / TC-E2E-TS-004 | E2E | セキュリティ | `test_directive_issue_creates_task_and_task_lifecycle_is_observable` / `test_blocked_task_can_be_unblocked_through_public_api` |
| 確定E 認可境界 | `TaskAuthorizationError` | TC-E2E-TS-005 / TC-E2E-TS-006 | E2E | セキュリティ | `test_task_assignment_rejects_agent_outside_room` / `test_deliverable_rejects_unassigned_submitter` |

**マトリクス充足の証拠**:
- Task 取得・一覧・assign・cancel・unblock・deliverable は公開 HTTP API のレスポンスだけで観測する
- Room.members 外の Agent は assign で 403 になる
- Room member でも Task 未担当の Agent は deliverable commit で 403 になる
- `last_error` と `body_markdown` に raw token が HTTP レスポンスで露出しない
- terminal / invalid retry は 409 として観測する

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 |
|---|---|---|---|---|
| SQLite（テスト用 DB）| E2E 前提データ | `tmp_path` 配下 DB | `tests/factories/db.py` / `tests/factories/directive.py` / `tests/factories/task.py` | Workflow / Agent / BLOCKED Task の前提だけ実 repository で seed。検証は HTTP レスポンスで行う |
| FastAPI ASGI | HTTP リクエスト送信 | — | — | `httpx.AsyncClient` + `ASGITransport` |

**factory ステータス**: `tests/factories/task.py` は実装済み。`make_task()` / `make_deliverable()` / `make_attachment()` / status 別 factory を提供する。

## E2E テストケース

| テストID | 対象 | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|
| TC-E2E-TS-003 | Directive 起点の Task lifecycle | Empire・Workflow・Room・Room member Agent 存在 | Directive 発行 → Task GET → Room Task list → assign → deliverable commit → Task GET → cancel → cancel 再試行 → missing Task GET | Task は `PENDING` で作成され、assign 後 `IN_PROGRESS`、deliverable body は masked、cancel 後 `CANCELLED`、再 cancel は 409、missing Task は 404 |
| TC-E2E-TS-004 | BLOCKED Task unblock | BLOCKED Task と担当 Agent 存在 | Task GET → unblock → unblock 再試行 | `last_error` は masked、unblock 後 `IN_PROGRESS` かつ `last_error=null`、再 unblock は 409 |
| TC-E2E-TS-005 | Room.members 外 assign 拒否 | Task の Room に所属しない Agent 存在 | `POST /api/tasks/{task_id}/assign` | HTTP 403 |
| TC-E2E-TS-006 | 未担当 submitter 拒否 | Room member だが Task 未担当の Agent 存在 | `POST /api/tasks/{task_id}/deliverables/{stage_id}` | HTTP 403 |

## カバレッジ基準

- REQ-TS-HTTP-001〜006 の主要正常系を E2E で 1 件以上検証する
- Room.members 認可と担当 Agent 検証を E2E で検証する
- `last_error` / `body_markdown` の HTTP レスポンス masking を E2E で検証する
- terminal / invalid retry の 409 を E2E で検証する
- 本 PR の検証範囲外の IT / UT 予定ケースを本書に残さない

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全 7 ジョブ緑であること
- ローカル:
  ```sh
  uv run pytest backend/tests/e2e/test_directive_task_http_api.py
  ```

## テストディレクトリ構造

```
backend/tests/
├── e2e/
│   └── test_directive_task_http_api.py          # TC-E2E-TS-003〜006
└── factories/
    ├── directive.py                             # 実装済み: make_directive ほか
    └── task.py                                  # 実装済み: make_task ほか
```

## 未決課題・characterization task

| # | 内容 | 起票先 |
|---|---|---|
| 該当なし | PR #111 の Task HTTP API 検証範囲では未決課題なし。将来 API 拡張時は、その PR でテスト設計を追加する | — |

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — 機能要件（REQ ID）
- [`detailed-design.md`](detailed-design.md) — MSG 確定文言 / スキーマ仕様 / 確定A〜G
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様
- [`../system-test-design.md`](../system-test-design.md) — E2E テスト
- [`../../directive/http-api/test-design.md`](../../directive/http-api/test-design.md) — Directive HTTP API テスト設計
