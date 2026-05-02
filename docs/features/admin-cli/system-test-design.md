# システムテスト設計書

> feature: `admin-cli`
> 関連: [`feature-spec.md`](feature-spec.md) §9 受入基準

## 本書の役割

本書は **admin-cli 業務概念全体のシステムテスト戦略** を凍結する。sub-feature（application / cli）の境界を跨いで観察される業務ふるまいを、ブラックボックスで検証する。

各 sub-feature の `test-design.md` は IT / UT のみを担当する。**システムテストは本書だけが扱う**（`application/test-design.md` にシステムテストを書かない）。

## システムテスト スコープ

- `list-blocked` コマンド → BLOCKED Task 一覧取得 の End-to-End
- `retry-task <task_id>` コマンド → Task.status BLOCKED → IN_PROGRESS 変更 の End-to-End
- `cancel-task <task_id>` コマンド → Task.status → CANCELLED 変更 の End-to-End
- `list-dead-letters` コマンド → DEAD_LETTER Outbox Event 一覧取得 の End-to-End
- `retry-event <event_id>` コマンド → OutboxRow.status = PENDING リセット の End-to-End
- 全コマンド実行後の audit_log 追記 の End-to-End（受入基準 #14）

## 観察主体

bakufu Backend DB（SQLite）。本テストでは pytest + asyncio + SQLite インメモリ DB（または一時 DB ファイル）を用いて、AdminService の業務操作が DB に正しく反映されることを観察する。CLI レイヤー（Typer コマンド）は直接 AdminService を呼び出す形でシステムテストを実施し、プロセス起動は IT 対象外とする（IT では AdminService のメソッドを直接テストする）。

## システムテストケース

| テストID | シナリオ | セットアップ | 期待結果（観察可能事象）| 紐付く受入基準 |
|---|---|---|---|---|
| TC-ST-AC-001 | `list-blocked` — BLOCKED Task が存在する場合 | DB に status=BLOCKED の Task を 3 件、status=IN_PROGRESS の Task を 1 件作成 | AdminService.list_blocked_tasks() が 3 件の BlockedTaskSummary を返す（IN_PROGRESS は含まない）| feature-spec.md §9 #11 |
| TC-ST-AC-002 | `retry-task` — 正常系 | DB に status=BLOCKED の Task を作成 | Task.status が IN_PROGRESS に更新され、audit_log に `command=retry-task`, `result=OK` レコードが追記される | feature-spec.md §9 #12 |
| TC-ST-AC-003 | `retry-task` — Task not BLOCKED（エラー）| DB に status=IN_PROGRESS の Task を作成 | IllegalTaskStateError が送出され、audit_log に `command=retry-task`, `result=FAIL` レコードが追記される | feature-spec.md §9 #12 |
| TC-ST-AC-004 | `cancel-task` — 正常系（BLOCKED Task）| DB に status=BLOCKED の Task を作成 | Task.status が CANCELLED に更新され、audit_log に `command=cancel-task`, `result=OK` が追記される | feature-spec.md §9 #12b |
| TC-ST-AC-005 | `cancel-task` — AWAITING_EXTERNAL_REVIEW Task（エラー）| DB に status=AWAITING_EXTERNAL_REVIEW の Task を作成 | IllegalTaskStateError が送出され、audit_log に `result=FAIL` が追記される | feature-spec.md R1-3 |
| TC-ST-AC-006 | `list-dead-letters` — DEAD_LETTER Event が存在する場合 | DB に status=DEAD_LETTER の OutboxRow を 2 件、status=PENDING を 1 件作成 | AdminService.list_dead_letters() が 2 件の DeadLetterSummary を返す（PENDING は含まない）| feature-spec.md §9 #13a |
| TC-ST-AC-007 | `retry-event` — 正常系 | DB に status=DEAD_LETTER / attempt_count=5 の OutboxRow を作成 | OutboxRow.status=PENDING / attempt_count=0 にリセットされ、audit_log に `command=retry-event`, `result=OK` が追記される | feature-spec.md §9 #13b |
| TC-ST-AC-008 | `retry-event` — Event not DEAD_LETTER（エラー）| DB に status=PENDING の OutboxRow を作成 | エラーが送出され、audit_log に `result=FAIL` が追記される | feature-spec.md R1-5 |
| TC-ST-AC-009 | audit_log — `list-blocked` 実行後の記録 | DB が空の状態 | AdminService.list_blocked_tasks() 呼び出し後、audit_log に `command=list-blocked`, `result=OK` が追記される | feature-spec.md §9 #14 |
| TC-ST-AC-010 | `list-blocked` — BLOCKED Task が 0 件 | DB に BLOCKED Task が存在しない | 空リストを返し（エラーではない）、audit_log に記録される | feature-spec.md R1-1 |

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | SQLite インメモリ DB（pytest fixture で起動・破棄）|
| domain 層 | 実 Aggregate（モックなし）|
| application 層 | AdminService を直接呼び出し（CLI プロセス起動は IT 対象外）|
| audit_log | 操作後に `SELECT * FROM audit_log` で追記内容を直接検証 |
| OutboxRow | `SELECT * FROM domain_event_outbox WHERE event_id = ?` で status / attempt_count を直接検証 |
| Task | `SELECT * FROM tasks WHERE id = ?` で status を直接検証 |

## カバレッジ基準

- 受入基準（[`feature-spec.md §9`](feature-spec.md)）が **システムテストで最低 1 件** 検証される（TC-ST-AC-NNN との対応表参照）
- 全 5 コマンドに正常系・異常系の TC が存在する
- audit_log 追記は全コマンドで独立して検証される（TC-ST-AC-009 参照）
