# 業務仕様書（feature-spec）— admin-cli

> feature: `admin-cli`（業務概念単位）
> sub-features: `application` | `cli`
> 関連 Issue: [#165 feat(M5-C): admin-cli実装](https://github.com/bakufu-dev/bakufu/issues/165)
> 凍結済み設計: [`docs/design/architecture.md`](../../design/architecture.md) §interfaces レイヤー / [`docs/design/threat-model.md`](../../design/threat-model.md) §A09

## 本書の役割

本書は **admin-cli という業務概念全体の業務仕様** を凍結する。LLM 障害・Discord 障害発生時に BLOCKED 状態の Task や dead-letter 化した Domain Event Outbox を発見・救済する唯一の手動操作経路として、CEO（運用者）が実行する管理 CLI コマンドセットを定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない。

**書くこと**:
- ペルソナがこの業務概念で達成できるようになる行為（ユースケース UC-AC-NNN）
- 業務ルール（BLOCKED 状態の扱い・dead-letter の定義・audit_log 強制記録等、確定 R1-X として凍結）
- 観察可能な事象としての受入基準（システムテストの真実源）

**書かないこと**（後段の設計書・別ディレクトリへ追い出す）:
- 採用技術スタック → sub-feature の `basic-design.md` / [`docs/design/tech-stack.md`](../../design/tech-stack.md)
- 実装方式の比較・選定議論 → sub-feature の `detailed-design.md`
- 内部 API 形・メソッド名・属性名・型 → sub-feature の `basic-design.md` / `detailed-design.md`
- pyright strict / カバレッジ閾値 → §10 開発者品質基準（CI 担保、業務要求とは分離）

## 1. この feature の位置付け

admin-cli は **bakufu の運用管理インターフェース** として定義する。LLM 障害（OAuth 期限切れ等）や Discord 障害時に bakufu の処理が停止した際に、CEO が手動で状態を把握し、復旧操作を実行する唯一の経路。

業務的なライフサイクルは複数の実装レイヤーを跨ぐ:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| interfaces | `cli` | CEO が実行する 5 コマンド定義・出力フォーマット（テーブル / JSON）・lite DB 初期化 |
| application | `application` | AdminService（BLOCKED Task 管理・dead-letter Event 管理・audit_log 記録）|

## 2. 人間の要求

> Issue #165:
>
> M5-A（stage-executor）完了後に着手可能な管理 CLI。BLOCKED 状態の Task や dead-letter 化した Outbox event を発見・救済する唯一の経路。LLM 障害（OAuth 期限切れ等）や Discord 障害時に運用者（CEO）が手動で状況を把握し、処理を再開できるようにする。

## 3. 背景・痛点

### 現状の痛点

1. LLM 呼び出しが失敗して Task が BLOCKED になったとき、bakufu の状態を確認・回復する手段がない
2. Domain Event Outbox の dispatch が繰り返し失敗して dead-letter になったとき、再投入する手段がない
3. 障害発生時の運用操作の証跡がなく、事後の障害調査ができない

### 解決されれば変わること

- CEO が CLI から BLOCKED Task の一覧を確認し、原因解消後に retry または cancel できる
- dead-letter Domain Event を再投入して Discord 通知・処理フローを復旧できる
- 全操作が audit_log に記録され、事後の障害調査・不正検出ができる

### ビジネス価値

- bakufu の自律動作に障害が生じた場合でも人間が復旧介入できる（MVP の運用継続性確保）
- 操作証跡（OWASP A09）を担保し、誤操作・不正操作を後追い検出できる

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|---|---|---|---|
| CEO（堀川）| bakufu システムオーナー兼運用者 | 直接 | LLM 障害・Discord 障害発生時に手動で状態を確認・復旧する |

プロジェクト全体ペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|---|---|---|---|---|
| UC-AC-001 | CEO | BLOCKED Task の一覧を確認して障害の全体像を把握したい | 必須 | `application` + `cli` |
| UC-AC-002 | CEO | 原因解消後に BLOCKED Task を IN_PROGRESS に戻して自動再開させたい | 必須 | `application` + `cli` |
| UC-AC-003 | CEO | 不要になった Task を CANCELLED に遷移させて処理を止めたい | 必須 | `application` + `cli` |
| UC-AC-004 | CEO | dead-letter 化した Domain Event の一覧を確認したい | 必須 | `application` + `cli` |
| UC-AC-005 | CEO | dead-letter Domain Event を Outbox に再投入して処理を再開させたい | 必須 | `application` + `cli` |

## 6. スコープ

### In Scope

- 5 コマンド（`list-blocked` / `retry-task` / `cancel-task` / `list-dead-letters` / `retry-event`）
- `--json` フラグによる JSON 出力（CI / スクリプト連携用）
- 全操作の audit_log 記録（受入基準 #13）
- lite DB 初期化（全 8 Stage の Bootstrap を起動せず DB 接続のみ確立）

### Out of Scope（参照）

- Task の状態遷移の詳細ロジック → `feature/task`
- Outbox dispatch ロジック → `feature/persistence-foundation`
- Web UI からの管理操作 → Phase 2 以降
- `AWAITING_EXTERNAL_REVIEW` 状態の Task のキャンセル → Phase 2 以降（R1-3 で明示禁止）

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-1: `list-blocked` は `status=BLOCKED` の Task のみ表示する

BLOCKED 以外の status（PENDING / IN_PROGRESS / AWAITING_EXTERNAL_REVIEW / DONE / CANCELLED）は一覧に含めない。

**理由**: CEO は「今すぐ回収が必要な Task」のみを確認したい。全 Task を表示すると信号が埋もれる。

### 確定 R1-2: `retry-task` は `BLOCKED` Task のみ受け付ける（Fail Fast）

`task.status ≠ BLOCKED` の場合は即座にエラーを返す。IN_PROGRESS / DONE / CANCELLED / PENDING / AWAITING_EXTERNAL_REVIEW Task への retry は禁止。

**理由**: retry は「LLM 障害で止まった Task を再開する」操作。BLOCKED 以外への retry は業務的に意味がなく、誤操作を防ぐ（Fail Fast 原則）。

### 確定 R1-3: `cancel-task` は `BLOCKED / PENDING / IN_PROGRESS` Task のみ受け付ける

`task.status ∉ {BLOCKED, PENDING, IN_PROGRESS}` の場合は即座にエラーを返す。DONE / CANCELLED Task への cancel は冪等でなくなるため禁止。`AWAITING_EXTERNAL_REVIEW` 状態への cancel は MVP スコープ外（ExternalReviewGate との整合が必要なため Phase 2 以降）。

**理由**: 既に完了・キャンセル済みの Task への cancel は業務的に無意味。AWAITING_EXTERNAL_REVIEW の cancel は外部承認フローとの不整合を引き起こすリスクがある。

### 確定 R1-4: `list-dead-letters` は `status=DEAD_LETTER` の Outbox Event のみ表示する

PENDING / DISPATCHING / DONE 行は一覧に含めない。

**理由**: Outbox Dispatcher が最大試行回数（`DEFAULT_MAX_ATTEMPTS=5`）を超えて DEAD_LETTER に昇格した行のみが手動介入の対象。

### 確定 R1-5: `retry-event` は `DEAD_LETTER` Event のみ受け付け、`attempt_count` をリセットする

`status ≠ DEAD_LETTER` の場合は即座にエラーを返す。retry 時は `status = PENDING` / `attempt_count = 0` / `next_attempt_at = now(UTC)` にリセットする。Outbox Dispatcher の次回ポーリングサイクルで自動 dispatch される。

**理由**: Dispatcher の再試行ループに戻すには PENDING に戻すのみで十分。attempt_count をリセットしないと即座に DEAD_LETTER に戻る。

### 確定 R1-6: 全 Admin CLI 操作は `audit_log` に記録する（受入基準 #13）

`list-blocked` / `list-dead-letters` を含む全操作を `AuditLogRow` として audit_log に INSERT する。`result='OK'`（成功時）/ `result='FAIL'`（失敗時）で記録する。失敗時は `error_text=<マスキング済み例外メッセージ>` を追加する。`AuditLogRow.actor` には OS ユーザー名（`whoami` 相当）を使用する。

**理由**: 受入基準 #13（OWASP A09）。`audit_log` は DELETE が SQLite トリガで拒否される追記専用テーブルであり、操作証跡の改ざん不可性が保証される。

### 確定 R1-7: 出力形式は `--json` フラグで切り替える

デフォルト: 人間が読みやすいテーブル形式（stdout）。`--json` フラグ指定時: JSON 配列（stdout）。エラーメッセージは stdout / `--json` 両モードで stderr に出力する。

**理由**: CEO が目視確認するシナリオとスクリプトで処理するシナリオの両方を想定する。

### 確定 R1-8: `retry-task` は Task.status を `BLOCKED → IN_PROGRESS` に変更するのみ。CLI プロセス内での LLM 実行は行わない

bakufu サーバーの StageWorker が IN_PROGRESS Task を自動ピックアップして実行を再開する（ジェンセン決定）。

**理由**: CLI は短命プロセスであり、長時間の LLM 実行を担うべきではない。サーバーの StageWorker がステート管理の責任を持つ（関心の分離）。

## 8. 制約・前提

| 区分 | 内容 |
|---|---|
| 依存 feature | `feature/stage-executor`（M5-A 完了必須。`Task.unblock_retry()` domain メソッドが使用可能）|
| 依存 feature | `feature/persistence-foundation`（`audit_log` / `domain_event_outbox` テーブルスキーマ確定済み）|
| 依存 feature | `feature/task`（`Task.cancel()` / `Task.unblock_retry()` domain メソッド確定済み）|
| 前提 | `AuditLogRow` テーブルは既存スキーマに存在（`alembic/versions/0001_init_audit_pid_outbox.py`）|
| 前提 | `OutboxRow.status = 'DEAD_LETTER'` は Outbox Dispatcher が最大試行超過時に設定する |
| 運用前提 | bakufu サーバーが稼働中の状態で admin-cli を実行することを想定する |
| 実行環境 | bakufu パッケージと同一仮想環境で `python -m bakufu.cli.admin` または pyproject.toml スクリプトとして実行 |

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|---|---|---|
| 11 | `bakufu admin list-blocked` が BLOCKED Task の一覧を表示する（task_id / room_id / last_error / blocked_at を含む）| UC-AC-001 | TC-IT-AC-001 |
| 12 | `bakufu admin retry-task <task_id>` 実行後、Task.status が BLOCKED → IN_PROGRESS に更新されている | UC-AC-002 | TC-IT-AC-002 |
| 12b | `bakufu admin cancel-task <task_id>` 実行後、Task.status が CANCELLED に更新されている | UC-AC-003 | TC-IT-AC-003 |
| 13a | `bakufu admin list-dead-letters` が dead-letter Event の一覧を表示する（event_id / event_kind / attempt_count / last_error を含む）| UC-AC-004 | TC-IT-AC-004 |
| 13b | `bakufu admin retry-event <event_id>` 実行後、OutboxRow.status=PENDING / attempt_count=0 にリセットされている | UC-AC-005 | TC-IT-AC-005 |
| 14 | 全 Admin CLI 操作の後（list 系を含む）、audit_log テーブルに対応レコードが追記される | 全 UC | TC-IT-AC-006 |

## 10. 開発者品質基準（CI 担保、業務要求ではない）

| # | 基準 | 検証方法 |
|---|---|---|
| Q-1 | 型検査 / lint がエラーゼロ | CI lint / typecheck ジョブ（ruff / pyright strict）|
| Q-2 | 各コマンドの IT カバレッジ ≥ 85% | pytest --cov |

## 11. 開放論点 (Open Questions)

| # | 論点 | 起票先 |
|---|---|---|
| Q-OPEN-1 | `AWAITING_EXTERNAL_REVIEW` 状態の Task を cancel する場合、ExternalReviewGate を同時に無効化する必要があるか | Phase 2 検討 |
| Q-OPEN-2 | bakufu サーバーの StageWorker が IN_PROGRESS 孤立 Task を起動時リカバリスキャンでピックアップする機構が必要か | **解決済み（2026-05-02 ジェンセン決定）**: Option A（起動時リカバリスキャン）を M5-C スコープで採用。詳細設計は `docs/features/stage-executor/application/detailed-design.md §確定J` |

## 12. Sub-issue 分割計画

| Sub-issue 名 | 紐付く UC | スコープ | 依存関係 |
|---|---|---|---|
| **A**: `application` | UC-AC-001〜005 | AdminService 実装 + AuditLogWriterPort / OutboxEventRepositoryPort 新規定義 | なし |
| **B**: `cli` | UC-AC-001〜005 | CLI コマンド定義 + lite DB 初期化 + 出力フォーマット | A に依存 |

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|---|---|---|
| `task.last_error` | LLM 障害時のエラーメッセージ（`MaskedText` で永続化時マスキング済み）| 中 |
| `outbox.payload_json` | Domain Event ペイロード（webhook URL 等を含む可能性、`MaskedJSONEncoded` でマスキング済み）| 中 |
| `outbox.last_error` | Outbox dispatch エラーメッセージ（`MaskedText` でマスキング済み）| 中 |
| `audit_log.args_json` | 実行引数（task_id / event_id 等、UUID のみ）| 低 |
| `audit_log.error_text` | コマンド失敗時の例外メッセージ（`MaskedText` でマスキング済み）| 中 |

## 14. 非機能要求

| 区分 | 要求 |
|---|---|
| パフォーマンス | list 系コマンドは 1 秒以内にレスポンス（SQLite ローカル DB のため十分達成可能）|
| 可用性 | bakufu サーバーが停止中でも DB ファイルが存在すれば実行可能（lite Bootstrap）|
| 可搬性 | Python 3.12+ + bakufu パッケージ（同一仮想環境で実行）|
| セキュリティ | `audit_log` は追記専用（DELETE トリガで保護）。list 系も audit_log に記録（OWASP A09）|
