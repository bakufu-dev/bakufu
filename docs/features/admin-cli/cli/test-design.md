# テスト設計書 — admin-cli / cli

> feature: `admin-cli` / sub-feature: `cli`
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md)
> 担当 Issue: [#165 feat(M5-C): admin-cli実装](https://github.com/bakufu-dev/bakufu/issues/165)

## 本書の役割

本書は **admin-cli / cli sub-feature の IT（結合テスト）と UT（単体テスト）** を凍結する。システムテスト（TC-ST-AC-001〜010）は [`../system-test-design.md`](../system-test-design.md) が担当する。本書が担う IT テストは Typer CLI レイヤーに特化し、コマンド引数解析・出力フォーマット・exit code・エラー stderr 出力を検証する。

## テスト方針

| レベル | 対象 | 手段 |
|-------|------|------|
| IT（結合）| Typer コマンド → mock AdminService | `typer.testing.CliRunner` + AsyncMock で AdminService をスタブ化 |
| UT（単体）| `OutputFormatter` 各関数 / MSG 文言定数 | pytest（同期） |

**AdminService を mock する理由**: CLI sub-feature の IT テストの関心は「CLI 層の契約」（引数解析・出力形式・exit code・エラーメッセージ）であり、AdminService の業務ロジックは `application/test-design.md` で既に検証する。AdminService を mock することで CLI 層を独立して検証でき、テストの責務が明確になる。

**プロセス起動テストは対象外**: システムテストの観察方法に記載の通り「プロセス起動は IT 対象外」。`CliRunner` は Typer の機能を同プロセス内で呼び出す（`mix_stderr=False` でstdout/stderr を分離して確認する）。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-AC-CLI-001 | `AdminApp.list_blocked()` | TC-IT-AC-CLI-001, TC-IT-AC-CLI-002, TC-IT-AC-CLI-003 | IT | 正常系 / 境界値 | feature-spec.md §9 #11 |
| REQ-AC-CLI-002 | `AdminApp.retry_task()` | TC-IT-AC-CLI-004, TC-IT-AC-CLI-005, TC-IT-AC-CLI-006 | IT | 正常系 / 異常系 | feature-spec.md §9 #12 |
| REQ-AC-CLI-003 | `AdminApp.cancel_task()` | TC-IT-AC-CLI-007 | IT | 正常系 | feature-spec.md §9 #12b |
| REQ-AC-CLI-004 | `AdminApp.list_dead_letters()` | TC-IT-AC-CLI-008, TC-IT-AC-CLI-009 | IT | 正常系 | feature-spec.md §9 #13a |
| REQ-AC-CLI-005 | `AdminApp.retry_event()` | TC-IT-AC-CLI-010, TC-IT-AC-CLI-011 | IT | 正常系 / 異常系 | feature-spec.md §9 #13b |
| REQ-AC-CLI-006 | `LiteBootstrap.setup_db()` | TC-IT-AC-CLI-012 | IT | 異常系 | — |
| §確定 A (lite Bootstrap) | `LiteBootstrap.setup_db()` Stage 1+4 のみ | TC-IT-AC-CLI-012 | IT | 正常系 | — |
| §確定 B (UUID Fail Fast) | `AdminApp.retry_task()` / `retry_event()` UUID 検証 | TC-IT-AC-CLI-005, TC-IT-AC-CLI-011 | IT | 異常系 | — |
| §確定 C (exit code) | 各コマンドの exit code | TC-IT-AC-CLI-001〜012 全て | IT | 正常系 / 異常系 | — |
| §確定 D (出力フォーマット) | `OutputFormatter` 各関数 | TC-UT-AC-CLI-001〜012 | UT | 正常系 / 境界値 | — |
| MSG-AC-CLI-001 | LiteBootstrap DB 接続失敗メッセージ | TC-IT-AC-CLI-012 | IT | 文言照合 | — |
| MSG-AC-CLI-002 | UUID パースエラーメッセージ | TC-IT-AC-CLI-005, TC-IT-AC-CLI-011 | IT | 文言照合 | — |
| 変更コマンド成功文言 | OutputFormatter / AdminApp stdout | TC-UT-AC-CLI-010, TC-UT-AC-CLI-011, TC-UT-AC-CLI-012 | UT | 文言照合 | — |
| T2: CLI 引数インジェクション | Typer 型アノテーション + UUID パース | TC-IT-AC-CLI-005, TC-IT-AC-CLI-011 | IT | セキュリティ | — |

**マトリクス充足の証拠**:
- REQ-AC-CLI-001 〜 REQ-AC-CLI-006 全てに IT テストケース（最低 1 件）
- §確定 A〜D 全てに IT または UT テストケース（最低 1 件）
- MSG-AC-CLI-001 / MSG-AC-CLI-002 に文言照合テスト
- 変更コマンド成功 stdout 文言 3 件（retry-task / cancel-task / retry-event）を UT で照合
- T2 脅威に有効性確認テスト

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 |
|---|---|---|---|---|
| `AdminService` | CLI コマンドからの業務処理委譲 | — | `AsyncMock()` | IT は mock で応答を制御（`list_blocked_tasks` の戻り値 / `retry_task` の例外等）|
| SQLite DB（LiteBootstrap 経由）| lite Bootstrap の DB 接続確立 | — | `make_test_engine` / `create_all_tables`（DB 接続テストのみ TC-IT-AC-CLI-012 で使用）| TC-IT-AC-CLI-012 のみ実 DB。他は AdminService mock で DB 接続不要 |
| `BAKUFU_DATA_DIR` 環境変数 | LiteBootstrap の DB ファイルパス解決 | — | `monkeypatch.setenv` / `tmp_path` fixture | TC-IT-AC-CLI-012 で not-exist ディレクトリを設定してエラーを誘発 |

**外部 API 依存なし**。Characterization fixture 不要。

**CLI CliRunner の設定**:
- `CliRunner(mix_stderr=False)` を使用して stdout / stderr を個別に取得
- `result.exit_code` で exit code を確認
- `result.output`（stdout）と `result.stderr` で出力を確認

## 結合テストケース（IT）

テストファイル: `backend/tests/integration/test_admin_cli.py`

### TC-IT-AC-CLI-001: list-blocked — テーブル形式デフォルト出力（§確定 D / §確定 C）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-CLI-001 / §確定 D / §確定 C |
| 前提 | mock AdminService の `list_blocked_tasks()` が `BlockedTaskSummary` 2 件を返す |
| 操作 | `runner.invoke(app, ["list-blocked"])` |
| 期待結果 | `result.exit_code == 0`。stdout に `TASK ID` 列ヘッダが含まれる（tabulate テーブル形式）。各 task の UUID 文字列が stdout に含まれる |

### TC-IT-AC-CLI-002: list-blocked --json — JSON 配列出力（§確定 D）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-CLI-001 / §確定 D / feature-spec.md R1-7 |
| 前提 | mock AdminService の `list_blocked_tasks()` が `BlockedTaskSummary` 1 件を返す |
| 操作 | `runner.invoke(app, ["list-blocked", "--json"])` |
| 期待結果 | `result.exit_code == 0`。stdout が有効な JSON 配列としてパース可能。`task_id` / `room_id` / `blocked_at` / `last_error` フィールドが含まれる |

### TC-IT-AC-CLI-003: list-blocked — 0 件時の人間向けメッセージ（§確定 D 境界値）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-CLI-001 / §確定 D / feature-spec.md R1-1 |
| 前提 | mock AdminService の `list_blocked_tasks()` が空リスト `[]` を返す |
| 操作 | `runner.invoke(app, ["list-blocked"])` |
| 期待結果 | `result.exit_code == 0`。stdout に "（BLOCKED Task はありません）" が含まれる（エラーではない）|

### TC-IT-AC-CLI-004: retry-task — 正常系 + 成功メッセージ stdout + exit code 0（§確定 C）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-CLI-002 / §確定 C |
| 前提 | mock AdminService の `retry_task()` が正常終了（None を返す）|
| 操作 | `runner.invoke(app, ["retry-task", str(task_id)])` |
| 期待結果 | `result.exit_code == 0`。stdout に `[OK]` および `IN_PROGRESS` が含まれる（MSG 確定文言）|

### TC-IT-AC-CLI-005: retry-task — 無効 UUID → MSG-AC-CLI-002 + exit code 1（§確定 B / T2）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-CLI-002 / §確定 B / T2 |
| 前提 | なし（AdminService は呼ばれない）|
| 操作 | `runner.invoke(app, ["retry-task", "not-a-uuid"])` |
| 期待結果 | `result.exit_code == 1`。stderr に `[FAIL]` および `UUID` が含まれる（MSG-AC-CLI-002）。AdminService は 1 回も呼ばれない |

### TC-IT-AC-CLI-006: retry-task — TaskNotFoundError → MSG-AC-001 + exit code 1（§確定 C）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-CLI-002 / §確定 C |
| 前提 | mock AdminService の `retry_task()` が `TaskNotFoundError` を raise |
| 操作 | `runner.invoke(app, ["retry-task", str(uuid4())])` |
| 期待結果 | `result.exit_code == 1`。stderr に `[FAIL]` が含まれる（MSG-AC-001 転送）|

### TC-IT-AC-CLI-007: cancel-task — 正常系 + 成功メッセージ + exit code 0（§確定 C）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-CLI-003 / §確定 C |
| 前提 | mock AdminService の `cancel_task()` が正常終了（None を返す）|
| 操作 | `runner.invoke(app, ["cancel-task", str(task_id)])` |
| 期待結果 | `result.exit_code == 0`。stdout に `[OK]` および `CANCELLED` が含まれる（MSG 確定文言）|

### TC-IT-AC-CLI-008: list-dead-letters — テーブル形式出力（§確定 D）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-CLI-004 / §確定 D |
| 前提 | mock AdminService の `list_dead_letters()` が `DeadLetterSummary` 1 件を返す |
| 操作 | `runner.invoke(app, ["list-dead-letters"])` |
| 期待結果 | `result.exit_code == 0`。stdout に `EVENT ID` / `KIND` 列ヘッダが含まれる（tabulate テーブル形式）|

### TC-IT-AC-CLI-009: list-dead-letters --json — JSON 配列出力 + 0 件境界値（§確定 D）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-CLI-004 / §確定 D / feature-spec.md R1-7 |
| 前提（a）| mock AdminService の `list_dead_letters()` が `DeadLetterSummary` 1 件を返す |
| 前提（b）| mock AdminService の `list_dead_letters()` が空リスト `[]` を返す（0 件サブケース）|
| 操作 | `runner.invoke(app, ["list-dead-letters", "--json"])` |
| 期待結果 a | stdout が有効な JSON 配列。`event_id` / `event_kind` / `attempt_count` フィールドが含まれる |
| 期待結果 b | exit code 0。stdout に `[]` が含まれる（JSON モードの 0 件）|

### TC-IT-AC-CLI-010: retry-event — 正常系 + 成功メッセージ + exit code 0（§確定 C）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-CLI-005 / §確定 C |
| 前提 | mock AdminService の `retry_event()` が正常終了（None を返す）|
| 操作 | `runner.invoke(app, ["retry-event", str(event_id)])` |
| 期待結果 | `result.exit_code == 0`。stdout に `[OK]` および `PENDING` が含まれる（MSG 確定文言）|

### TC-IT-AC-CLI-011: retry-event — 無効 UUID → MSG-AC-CLI-002 + exit code 1（§確定 B / T2）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-CLI-005 / §確定 B / T2 |
| 前提 | なし（AdminService は呼ばれない）|
| 操作 | `runner.invoke(app, ["retry-event", "invalid-uuid"])` |
| 期待結果 | `result.exit_code == 1`。stderr に `[FAIL]` が含まれる（MSG-AC-CLI-002）。AdminService は呼ばれない |

### TC-IT-AC-CLI-012: lite Bootstrap — DB ファイル不在 → MSG-AC-CLI-001 + exit code 1（§確定 A）

| 項目 | 内容 |
|-----|------|
| 対象 | REQ-AC-CLI-006 / §確定 A |
| 前提 | `BAKUFU_DATA_DIR` 環境変数を存在しないパスに設定 |
| 操作 | `runner.invoke(app, ["list-blocked"])` |
| 期待結果 | `result.exit_code == 1`。stderr に `[FAIL]` および DB パスが含まれる（MSG-AC-CLI-001）|
| 注記 | AdminService の mock は設定しない。LiteBootstrap が Fail Fast する経路を直接テスト |

## ユニットテストケース（UT）

テストファイル: `backend/tests/unit/test_admin_cli_formatter.py`

UT は `OutputFormatter` の関数を直接呼び出し、出力文字列の正確性を確認する（非同期不要、同期テスト）。

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---|---|---|---|---|
| TC-UT-AC-CLI-001 | `format_blocked_tasks()` — テーブル形式 | 正常系 | `BlockedTaskSummary` 1 件（uuid / room_id / last_error / blocked_at）| stdout 文字列に `TASK ID` カラムヘッダが含まれる（tabulate `"simple"` フォーマット）|
| TC-UT-AC-CLI-002 | `format_blocked_tasks()` — JSON 形式 | 正常系 | `BlockedTaskSummary` 1 件 | 返却文字列が JSON 配列として valid。`task_id` / `room_id` / `blocked_at` / `last_error` の 4 フィールドが存在する |
| TC-UT-AC-CLI-003 | `format_blocked_tasks()` — 0 件テーブル | 境界値 | 空リスト | 返却文字列に "（BLOCKED Task はありません）" が含まれる |
| TC-UT-AC-CLI-004 | `format_dead_letters()` — テーブル形式 | 正常系 | `DeadLetterSummary` 1 件 | 返却文字列に `EVENT ID` / `KIND` カラムヘッダが含まれる |
| TC-UT-AC-CLI-005 | `format_dead_letters()` — JSON 形式 | 正常系 | `DeadLetterSummary` 1 件 | 返却文字列が JSON 配列として valid。`event_id` / `event_kind` / `aggregate_id` / `attempt_count` / `last_error` / `updated_at` の 6 フィールドが存在する |
| TC-UT-AC-CLI-006 | `format_dead_letters()` — 0 件 JSON | 境界値 | 空リスト、`json_output=True` | 返却文字列が `"[]"` に等しい（§確定 D JSON 0 件）|
| TC-UT-AC-CLI-007 | `format_success()` — JSON 形式 | 正常系 | `message="OK", json_output=True` | 返却 JSON に `"result": "ok"` が含まれる |
| TC-UT-AC-CLI-008 | `format_error()` — `[FAIL]` プレフィックス | 正常系 | `message="エラー"` | 返却文字列が `"[FAIL] エラー"` で始まる |
| TC-UT-AC-CLI-009 | `format_blocked_tasks()` — last_error 80 文字トランケート（§確定 D） | 境界値 | last_error が 100 文字の `BlockedTaskSummary`（テーブル形式） | 返却文字列に 81 文字目以降が含まれない。81 文字目以降の代わりに `...` が含まれる |
| TC-UT-AC-CLI-010 | retry-task 成功 stdout 確定文言 | 文言照合 | `format_success("retry-task", task_id)` 相当 | `[OK]` / `BLOCKED → IN_PROGRESS` / `StageWorker` が含まれる（detailed-design.md §確定 D 成功文言）|
| TC-UT-AC-CLI-011 | cancel-task 成功 stdout 確定文言 | 文言照合 | `format_success("cancel-task", task_id)` 相当 | `[OK]` / `CANCELLED` が含まれる（detailed-design.md §確定 D 成功文言）|
| TC-UT-AC-CLI-012 | retry-event 成功 stdout 確定文言 | 文言照合 | `format_success("retry-event", event_id)` 相当 | `[OK]` / `DEAD_LETTER → PENDING` / `Outbox Dispatcher` が含まれる（detailed-design.md §確定 D 成功文言）|

## カバレッジ基準

| 対象 | カバレッジ目標 |
|-----|------------|
| REQ-AC-CLI-001 〜 REQ-AC-CLI-006 の各要件 | IT テストで最低 1 件検証 |
| §確定 B（UUID Fail Fast）| TC-IT-AC-CLI-005 / TC-IT-AC-CLI-011 で無効 UUID を確認 |
| §確定 C（exit code 0/1）| 全 IT テストで exit code を検証 |
| §確定 D（出力フォーマット詳細仕様）| UT で tabulate テーブル列・JSON フィールド・0件文言・トランケート・確定文言を全て照合 |
| MSG-AC-CLI-001 / MSG-AC-CLI-002 | IT で stderr 出力の `[FAIL]` キーワードを確認 |
| 変更コマンド成功文言（3 コマンド分）| UT で確定文言をそのまま照合 |
| T2（CLI 引数インジェクション）| TC-IT-AC-CLI-005 / TC-IT-AC-CLI-011 で特殊文字列を含む UUID 不正入力を確認 |

## テストディレクトリ構造

```
backend/tests/
├── unit/
│   └── test_admin_cli_formatter.py     ← TC-UT-AC-CLI-001〜012（OutputFormatter / 確定文言 UT）
└── integration/
    └── test_admin_cli.py               ← TC-IT-AC-CLI-001〜012（CliRunner + mock AdminService）
```

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全ジョブ緑であること
- ローカル:
  ```
  cd backend
  python -m pytest tests/unit/test_admin_cli_formatter.py tests/integration/test_admin_cli.py -v
  ```
- 実コマンド確認（bakufu 仮想環境 + BAKUFU_DATA_DIR 設定済み環境で）:
  ```
  bakufu admin list-blocked
  bakufu admin retry-task <uuid>
  bakufu admin list-dead-letters --json
  ```

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — REQ-AC-CLI-001〜006
- [`detailed-design.md §確定事項`](detailed-design.md) — §確定 A〜D / MSG-AC-CLI-001〜002 / 変更コマンド確定文言
- [`../feature-spec.md §7`](../feature-spec.md) — 業務ルール R1-7（出力形式）
- [`../application/test-design.md`](../application/test-design.md) — AdminService の IT / UT テスト
- [`../system-test-design.md`](../system-test-design.md) — システムテスト TC-ST-AC-001〜010
