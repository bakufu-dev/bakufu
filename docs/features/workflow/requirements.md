# 要件定義書

> feature: `workflow`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Workflow

## 機能要件

### REQ-WF-001: Workflow 構築

| 項目 | 内容 |
|------|------|
| 入力 | `id: WorkflowId`、`name: str`（1〜80）、`stages: list[Stage]`（1 件以上）、`transitions: list[Transition]`（0 件以上）、`entry_stage_id: StageId` |
| 処理 | Pydantic 型バリデーション → `model_validator(mode='after')` で DAG 不変条件 7 種を集約検査（①entry 存在 ②Transition 参照整合 ③決定論性 ④BFS 到達可能性 ⑤終端 Stage ⑥EXTERNAL_REVIEW notify_channels 集約 ⑦required_role 非空 集約） → 通過時のみ Workflow を返す |
| 出力 | `Workflow` インスタンス（frozen） |
| エラー時 | `WorkflowInvariantViolation` を raise。MSG-WF-001〜007 のいずれかを格納 |

### REQ-WF-002: Stage 追加

| 項目 | 内容 |
|------|------|
| 入力 | 現 Workflow + `stage: Stage` |
| 処理 | 1) 現 `stages` に `stage` を追加した新リスト 2) 仮 Workflow を `model_validate(updated_dict)` で再構築（不変条件検査が走る） 3) 通過時のみ仮 Workflow を返す |
| 出力 | 更新された Workflow（新インスタンス） |
| エラー時 | 同一 `stage_id` 重複、Stage 自身の不変条件違反等で `WorkflowInvariantViolation`（MSG-WF-008） |

### REQ-WF-003: Transition 追加

| 項目 | 内容 |
|------|------|
| 入力 | 現 Workflow + `transition: Transition` |
| 処理 | 1) 現 `transitions` に追加した新リスト 2) 仮 Workflow を再構築し DAG 整合性を検査 |
| 出力 | 更新された Workflow |
| エラー時 | `from_stage_id` / `to_stage_id` が `stages` 内に存在しない、同一 `from × condition` の Transition 重複で `WorkflowInvariantViolation`（MSG-WF-009 / MSG-WF-005）|

### REQ-WF-004: Stage 削除

| 項目 | 内容 |
|------|------|
| 入力 | 現 Workflow + `stage_id: StageId` |
| 処理 | 1) 削除対象 `stage_id` が `entry_stage_id` を指すなら即 raise（MSG-WF-010） 2) `stages` から該当 Stage を除外し、`transitions` から `from_stage_id` または `to_stage_id` が一致するものを除外 3) 仮 Workflow を再構築・検査 |
| 出力 | 更新された Workflow |
| エラー時 | `stage_id` が存在しない、entry stage を削除しようとした、削除後に到達不能 Stage が生じた等で `WorkflowInvariantViolation` |

### REQ-WF-005: DAG 不変条件検査

| 項目 | 内容 |
|------|------|
| 入力 | Workflow インスタンス（コンストラクタ末尾 / 状態変更ふるまい末尾で自動呼び出し） |
| 処理 | 以下の検査を順次実行（最初の違反で停止）: ①`entry_stage_id` が `stages` に存在 ②全 Transition の `from_stage_id` / `to_stage_id` が `stages` に存在 ③同一 `from_stage_id × condition` の Transition 重複なし（決定論性） ④`entry_stage_id` から BFS で全 Stage に到達可能（孤立 Stage 禁止） ⑤終端 Stage（外向き Transition なし）が 1 件以上存在 ⑥`EXTERNAL_REVIEW` Stage は `notify_channels` を持つ ⑦各 Stage の `required_role` が空集合でない |
| 出力 | None（検査通過） |
| エラー時 | いずれか違反で `WorkflowInvariantViolation`（kind に違反種別を格納） |

### REQ-WF-006: bulk-import ファクトリ

| 項目 | 内容 |
|------|------|
| 入力 | `payload: dict`（`{id, name, stages, transitions, entry_stage_id}`） |
| 処理 | 1) Pydantic で全 Stage / Transition を構築（個別に Stage 自身の不変条件はここで検査） 2) Workflow を `model_validate(payload)` で再構築（最終状態のみ validate） 3) 通過時のみ返す |
| 出力 | `Workflow` インスタンス |
| エラー時 | Pydantic `ValidationError` または `WorkflowInvariantViolation` を raise（MSG-WF-011） |

### REQ-WF-007: Stage 自身の不変条件

| 項目 | 内容 |
|------|------|
| 入力 | Stage インスタンス |
| 処理 | `model_validator(mode='after')` で: ①`required_role` が空集合でない ②`EXTERNAL_REVIEW` の場合 `notify_channels` を持つ |
| 出力 | None |
| エラー時 | `StageInvariantViolation`（`WorkflowInvariantViolation` のサブクラス） |

## 画面・CLI 仕様

### CLI レシピ / コマンド

該当なし — 理由: 本 feature は domain 層のみ実装する。Workflow プリセットの JSON 定義 / 読み込み CLI は `feature/workflow-presets` で扱う。

### Web UI 画面

該当なし — 理由: UI は `feature/workflow-ui`（Phase 2 で react-flow 統合予定）で扱う。

## API 仕様

該当なし — 理由: 本 feature は domain 層のみ。HTTP API は `feature/http-api` で扱う。

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| 該当なし | — | — | — | — |

## データモデル

凍結済み設計（[`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Workflow / [`value-objects.md`](../../design/domain-model/value-objects.md) §Workflow 構成要素）に従う。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| Workflow（Aggregate Root） | `id` | `WorkflowId`（UUID） | 不変 | — |
| Workflow | `name` | `str` | 1〜80 文字 | — |
| Workflow | `stages` | `list[Stage]` | 1 件以上、`stage_id` 重複なし | Stage Entity |
| Workflow | `transitions` | `list[Transition]` | 0 件以上 | Transition Entity |
| Workflow | `entry_stage_id` | `StageId` | `stages` 内に存在 | Stage Entity（参照） |
| Stage（Entity） | `id` | `StageId` | 不変 | — |
| Stage | `name` | `str` | 1〜80 文字 | — |
| Stage | `kind` | `StageKind` | enum | — |
| Stage | `required_role` | `frozenset[Role]` | 空集合不可 | Role enum |
| Stage | `deliverable_template` | `str` | Markdown | — |
| Stage | `completion_policy` | `CompletionPolicy`（VO） | — | — |
| Stage | `notify_channels` | `list[NotifyChannel]` | `EXTERNAL_REVIEW` で必須 | NotifyChannel VO |
| Transition（Entity） | `id` | `TransitionId` | 不変 | — |
| Transition | `from_stage_id` | `StageId` | `stages` 内に存在 | Stage |
| Transition | `to_stage_id` | `StageId` | `stages` 内に存在 | Stage |
| Transition | `condition` | `TransitionCondition` | enum | — |
| Transition | `label` | `str` | 0〜80 文字 | — |
| NotifyChannel（VO） | `kind` | `Literal['discord']` | **MVP は discord のみ**。slack/email は `pydantic.ValidationError` 拒否 | — |
| NotifyChannel | `target` | `str` | 1〜500 文字、Discord webhook URL allow list G1〜G10（[detailed-design.md](detailed-design.md) §確定 G）を完全充足。token 部はシリアライズ時 `<REDACTED:DISCORD_WEBHOOK>` でマスキング | — |

`StageKind` / `Role` / `TransitionCondition` の値域は [`value-objects.md`](../../design/domain-model/value-objects.md) §列挙型一覧 を参照。

## ユーザー向けメッセージ一覧

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|----|------|----------------|---------|
| MSG-WF-001 | エラー（境界値） | Workflow name は 1〜80 文字 | name 長違反 |
| MSG-WF-002 | エラー（参照不整合） | entry_stage_id が stages に存在しない | 構築時 |
| MSG-WF-003 | エラー（DAG） | 孤立 Stage が存在（到達不能） | 構築時 / 状態変更後 |
| MSG-WF-004 | エラー（DAG） | 終端 Stage が 0 件（循環） | 同上 |
| MSG-WF-005 | エラー（決定論） | 同一 from_stage × condition の Transition が重複 | 同上 |
| MSG-WF-006 | エラー（通知設定） | EXTERNAL_REVIEW Stage は notify_channels を持つ必要がある | Stage 自身の不変条件違反 |
| MSG-WF-007 | エラー（必須役割） | Stage の required_role は空集合不可 | 同上 |
| MSG-WF-008 | エラー（重複） | Stage id 重複 | `add_stage` |
| MSG-WF-009 | エラー（参照不整合） | Transition の from / to が stages に存在しない | `add_transition` |
| MSG-WF-010 | エラー（削除拒否） | entry_stage_id を指す Stage は削除不可 | `remove_stage` |
| MSG-WF-011 | エラー（bulk import） | from_dict ペイロードの形式違反: {detail} | `from_dict` |
| MSG-WF-012 | エラー（参照不整合） | Stage not found in workflow: stage_id={stage_id} | `remove_stage` で未登録 stage_id |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | `pydantic` v2 | `pyproject.toml` | uv | 既存 |
| Python 依存 | `pyright` (strict) | `pyproject.toml` dev | uv tool | 既存 |
| Python 依存 | `ruff` | 同上 | uv tool | 既存 |
| Python 依存 | `pytest` / `pytest-cov` | 同上 | uv | 既存 |
| Node 依存 | 該当なし | — | — | バックエンド単独 |
| 外部サービス | 該当なし | — | — | domain 層 |
