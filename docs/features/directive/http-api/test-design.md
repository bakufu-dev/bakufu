# テスト設計書

> feature: `directive` / sub-feature: `http-api`
> 関連 Issue: [#60 feat(task-http-api): Directive + Task lifecycle HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/60)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../system-test-design.md`](../system-test-design.md)

## 本書の役割

本書は `basic-design.md §モジュール契約` の REQ-DR-HTTP-001 と、`detailed-design.md` の確定事項 A〜G を、PR #111 の検証範囲にだけ紐付ける。将来追加する IT / UT 予定ケースは、その PR で追記する。

**書くこと**:
- PR #111 で実装済みの Directive HTTP API 結合テスト
- 親 E2E テストで観測済みの Directive 発行・拒否・masking の対応関係
- factory / raw fixture の現状
- カバレッジ基準

**書かないこと**:
- 将来拡張用の IT / UT 予定ケース
- DB 直接確認を前提にした受入検証。ただし atomic UoW の結合テストだけはロールバック物理証明として repository 経由の事後確認を許容する

## テストケース ID 採番規則

| 番号帯 | 用途 |
|---|---|
| TC-IT-DRH-017 | 結合テスト（Directive + Task atomic UoW ロールバック）|
| TC-E2E-DR-003 | 親 system-test-design 管轄の E2E（Directive 発行 + Task 起票 + Room 拒否）|

## テストマトリクス

| 要件 ID | 実装アーティファクト | テストケース ID | テストレベル | 種別 | 実装済みテスト |
|---|---|---|---|---|---|
| REQ-DR-HTTP-001（正常系）| `directive_router` POST + `DirectiveService.issue` + `WorkflowRepository.find_by_id(room.workflow_id)` + Task 起票 | TC-E2E-DR-003 | E2E | 正常系 | `TestDirectiveTaskHttpE2E.test_directive_issue_creates_task_and_task_lifecycle_is_observable` |
| REQ-DR-HTTP-001（masking: text）| `DirectiveResponse.text` field_serializer | TC-E2E-DR-003 | E2E | セキュリティ | `TestDirectiveTaskHttpE2E.test_directive_issue_creates_task_and_task_lifecycle_is_observable` |
| REQ-DR-HTTP-001（Room 不在 / archived）| `RoomNotFoundError` / `RoomArchivedError` handlers | TC-E2E-DR-003 | E2E | 異常系 | `TestDirectiveTaskHttpE2E.test_directive_issue_rejects_missing_and_archived_room` |
| 確定B atomic UoW | `DirectiveService.issue` の単一 `session.begin()` | TC-IT-DRH-017 | 結合 | 異常系 | `test_issue_rolls_back_directive_when_task_save_fails` |

**マトリクス充足の証拠**:
- `Workflow.entry_stage_id` は Room から直接参照せず、`WorkflowRepository.find_by_id(room.workflow_id)` で取得する
- Directive 発行時に Task が同時起票され、`directive.task_id == task.id` を E2E で観測する
- raw token を含む Directive text が HTTP レスポンスで露出しないことを E2E で観測する
- Room 不在 404 / archived 409 を E2E で観測する
- Task 保存失敗時に孤立 Directive が残らないことを結合テストで確認する

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 |
|---|---|---|---|---|
| SQLite（テスト用 DB）| atomic UoW 結合テスト / E2E 前提データ | `tmp_path` 配下 DB | `tests/factories/db.py` / `tests/factories/directive.py` / `tests/factories/task.py` | 実 DB を使用。受入相当の観測は HTTP レスポンス優先 |
| FastAPI ASGI | HTTP リクエスト送信 | — | — | `httpx.AsyncClient` + `ASGITransport` |

**factory ステータス**: `tests/factories/directive.py` は実装済み。`make_directive()` / `make_linked_directive()` / `make_long_text_directive()` を提供する。

## 結合テストケース

| テストID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|---|
| TC-IT-DRH-017 | `DirectiveService.issue` → `DirectiveRepository.save` → `TaskRepository.save` | 実 SQLite tempdb | Empire・Workflow・Room 存在。DI で `TaskRepository.save` が `IntegrityError` を送出するスタブに差し替え | `POST /api/rooms/{room_id}/directives` 正常 payload | HTTP 500。repository 経由の確認で対象 Room に Directive が残らない |

## E2E 対応

| テストID | 対象 | 操作 | 期待結果 |
|---|---|---|---|
| TC-E2E-DR-003 | Directive 発行 + Task 起票 | `POST /api/rooms/{room_id}/directives` | HTTP 201。`directive.task_id == task.id`、Task status は `PENDING`、secret は masked |
| TC-E2E-DR-003 | Room 不在 / archived 拒否 | missing Room / archived Room に POST | missing は 404、archived は 409 |

## カバレッジ基準

- REQ-DR-HTTP-001 の正常系は E2E で 1 件以上検証する
- Room 不在 / archived の異常系は E2E で検証する
- HTTP レスポンス masking は E2E で検証する
- atomic UoW は結合テストで Task 保存失敗時のロールバックを検証する
- 本 PR の検証範囲外の IT / UT 予定ケースを本書に残さない

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全 7 ジョブ緑であること
- ローカル:
  ```sh
  uv run pytest backend/tests/e2e/test_directive_task_http_api.py backend/tests/integration/test_directive_http_api/test_atomic_uow.py
  ```

## テストディレクトリ構造

```
backend/tests/
├── e2e/
│   └── test_directive_task_http_api.py          # TC-E2E-DR-003 / TC-E2E-TS-003 / TC-E2E-TS-004
├── factories/
│   ├── directive.py                             # 実装済み: make_directive ほか
│   └── task.py                                  # 実装済み: make_task ほか
└── integration/
    └── test_directive_http_api/
        └── test_atomic_uow.py                   # TC-IT-DRH-017
```

## 未決課題・characterization task

| # | 内容 | 起票先 |
|---|---|---|
| 該当なし | PR #111 の Directive HTTP API 検証範囲では未決課題なし。将来 API 拡張時は、その PR でテスト設計を追加する | — |

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — 機能要件（REQ ID）
- [`detailed-design.md`](detailed-design.md) — MSG 確定文言 / スキーマ仕様 / 確定A〜G / アトミック UoW 実装契約
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様
- [`../system-test-design.md`](../system-test-design.md) — E2E テスト
- [`../../task/http-api/test-design.md`](../../task/http-api/test-design.md) — Task HTTP API テスト設計
