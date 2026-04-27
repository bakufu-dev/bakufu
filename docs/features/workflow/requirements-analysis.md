# 要求分析書

> feature: `workflow`
> Issue: [#9 feat(workflow): Workflow + Stage + Transition Aggregate (M1)](https://github.com/bakufu-dev/bakufu/issues/9)
> 凍結済み設計: [`docs/architecture/domain-model/aggregates.md`](../../architecture/domain-model/aggregates.md) §Workflow / [`value-objects.md`](../../architecture/domain-model/value-objects.md) §Workflow 構成要素

## 人間の要求

> Issue #9:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の一環として **Workflow Aggregate Root** を実装する。Workflow は Stage / Transition を内部に持つ DAG ワークフロー定義で、Vモデル / アジャイル等のプリセットを表現する核となる Aggregate。

## 背景・目的

### 現状の痛点

1. bakufu の差別化要因「Vモデル工程の Aggregate ロック」は Workflow Aggregate なしには実現できない。Aggregate なら工程逸脱が型システムレベルで不可能になるが、現状は文書のみ
2. M1 後段の `task` Issue は `current_stage_id` を Workflow Aggregate 内の Stage に解決する設計。Workflow が無いと Task の遷移ロジックが書けない
3. プリセット（Vモデル開発室 / アジャイル開発室）は JSON 定義から `Workflow.from_dict()` で構築する設計。ファクトリ実装も本 feature が含まれる
4. PR #6 / #11 で凍結した「pre-validate ロールバック方式」「`required_role: frozenset[Role]`」「`EXTERNAL_REVIEW` Stage は `notify_channels` 必須」などの実装お手本が必要

### 解決されれば変わること

- `task` Aggregate（M1 後段）が `current_stage_id` を valid な Stage に解決できる
- Vモデルプリセット読み込みが JSON → Aggregate の形で動き、`feature/workflow-presets` で V モデル / アジャイルが追加可能になる
- pre-validate 方式のお手本が 2 件目（Empire に続く）として出揃い、後続 Aggregate は同パターンを踏襲できる

### ビジネス価値

- bakufu の核心思想「External Review Gate を含む工程ロック」が型レベルで実現する
- Workflow を JSON で受け取れる設計が確定すれば、UI で「Workflow 編集」を後段で実装する際の入出力契約も自動的に確定する

## 議論結果

### 設計担当による採用前提

- Workflow Aggregate は **Pydantic v2 BaseModel + frozen + model_validator(mode='after')** で表現（Empire と同じ規約）
- Stage / Transition は **Workflow Aggregate 内部の Entity**。外部から個別に取得・更新できない（Aggregate 境界）。`Stage.id` / `Transition.id` を持つが Repository は Workflow 全体に対して読み書きする
- pre-validate 方式は **Empire と同じく `model_validate` 経由の再構築**で実装する（`add_stage` / `add_transition` / `remove_stage` の各ふるまい）
- DAG 不変条件検査は到達可能性 BFS / 終端 Stage 検出 / Transition 重複チェック / `EXTERNAL_REVIEW` の `notify_channels` 充足の 4 種を `model_validator` 内で順次実行
- `Workflow.from_dict(payload)` は **bulk-import ファクトリ**。JSON / dict から Stage / Transition を全量構築 → 最後に 1 回 validate（途中状態の valid を要求しない）

### 却下候補と根拠

| 候補 | 却下理由 |
|-----|---------|
| Stage / Transition を独立 Aggregate にする | Stage 単独で意味を持たず、Workflow 文脈でのみ valid。独立 Aggregate にすると Repository が散らばり、DAG 整合性がトランザクション境界をまたぐ |
| memento パターン（変更前状態を保存して失敗時復元） | pre-validate 方式で Aggregate を不正状態にする窓を一瞬も開かない方が原理的に堅牢。memento は復元忘れバグを生み得る |
| DAG 検査を Repository.save() で行う | Aggregate Root は常に valid な契約に反する。Repository は契約として valid な Aggregate しか受け取らない |
| 到達可能性検査を DFS で実装 | DFS / BFS どちらでも O(V+E)。BFS の方がスタック深さに依存せず、循環グラフでも実装が単純なため BFS を採用 |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: pre-validate 方式の Workflow への適用

`add_stage` / `add_transition` / `remove_stage` は Empire と同じ手順:

1. 引数の Pydantic 型バリデーション
2. 変更後の `stages` / `transitions` を新リストとして仮構築
3. `model_validate({...updated_dict})` で仮 Workflow を再構築（model_validator が走る）
4. 通過時のみ仮 Workflow を返す。違反時は raise（元 Workflow は変化しない）

#### 確定 R1-B: from_dict() ファクトリの責務範囲

`Workflow.from_dict(payload: dict) -> Workflow` は以下:

1. payload から Stage / Transition の dict 配列を取り出す
2. 全 Stage / Transition を一度に Pydantic 構築
3. Workflow を `model_validate(...)` で構築（最終状態のみ validate）
4. 失敗時は `WorkflowInvariantViolation` または Pydantic `ValidationError` を raise

JSON Schema での事前検証は実施しない（Pydantic 型強制で十分）。

#### 確定 R1-C: required_role の集合型と空集合検査

PR #11 で確定した `Stage.required_role: frozenset[Role]`、空集合不可は **Stage 自身の `model_validator`** および **Workflow.validate() の集約検査の両方で**チェックする（二重防護）。Stage の単体テストと Workflow 全体テストの双方で空集合違反を検知できる。

#### 確定 R1-D: 終端 Stage の定義

「終端 Stage = 外向き Transition を持たない Stage」と定義する。複数あってよい（並列終端を許容）。終端 Stage が 0 件なら必ず循環が存在し、Task が無限ループするため `WorkflowInvariantViolation`。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 個人開発者 CEO | bakufu インスタンスのオーナー | GitHub / Docker / CLI 日常使用 | プリセットから Workflow を選択して Room に紐づける、または JSON で独自 Workflow を編集する | 数クリックで V モデル / アジャイル開発室を構築、必要なら Stage / Transition を JSON で微調整 |

bakufu システム全体のペルソナは [`docs/architecture/context.md`](../../architecture/context.md) §4 を参照。

## 前提条件・制約

| 区分 | 内容 |
|-----|------|
| 既存技術スタック | Python 3.12+ / Pydantic v2 / pyright strict / pytest |
| 既存 CI | lint / typecheck / test-backend / audit |
| 既存ブランチ戦略 | GitFlow |
| コミット規約 | Conventional Commits |
| ライセンス | MIT |
| ネットワーク | 該当なし — domain 層 |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |

## 機能一覧

| 機能ID | 機能名 | 概要 | 優先度 |
|--------|-------|------|--------|
| REQ-WF-001 | Workflow 構築 | コンストラクタで Stage / Transition / entry_stage_id を受け取り、不変条件を検査して valid な Workflow を返す | 必須 |
| REQ-WF-002 | Stage 追加 | `add_stage(stage)` で Stage を追加、pre-validate で DAG 整合性を確認 | 必須 |
| REQ-WF-003 | Transition 追加 | `add_transition(transition)` で Transition を追加、from / to の存在と決定論性を検査 | 必須 |
| REQ-WF-004 | Stage 削除 | `remove_stage(stage_id)` で関連 Transition も削除。entry_stage_id を指す Stage は削除不可 | 必須 |
| REQ-WF-005 | DAG 不変条件検査 | 全 Stage が entry_stage_id から到達可能 / 終端 Stage 1 件以上 / Transition 参照整合 / EXTERNAL_REVIEW の notify_channels / Stage の required_role 非空 を集約検査 | 必須 |
| REQ-WF-006 | bulk-import ファクトリ | `Workflow.from_dict(payload)` で JSON / dict から Workflow を構築（最終状態のみ validate） | 必須 |
| REQ-WF-007 | Stage 自身の不変条件 | `required_role` が空集合でないこと、`EXTERNAL_REVIEW` Stage は `notify_channels` を持つこと | 必須 |

## Sub-issue 分割計画

本 Issue は単一 Aggregate に閉じる粒度のため Sub-issue 分割は不要。1 PR で 4 設計書 + 実装 + ユニットテストを完結させる。Workflow プリセット（V モデル / アジャイル）の JSON 定義は別 Issue（`feature/workflow-presets`）。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 単一 PR | REQ-WF-001〜007 | Workflow / Stage / Transition + pre-validate + from_dict + ユニットテスト | chore #7 マージ済み（前提充足） |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | DAG 検査は O(V+E)（V=stages, E=transitions）。MVP の想定規模 V ≤ 30, E ≤ 60 で 1ms 未満を目標 |
| 可用性 | 該当なし — domain 層 |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 80% 以上 |
| 可搬性 | 純 Python のみ |
| セキュリティ | `from_dict` 経路で外部 JSON を受け取るが、Pydantic 型強制で `Role` 名や UUID 形式の不正値を Fail Fast で拒否。詳細は [`threat-model.md`](../../architecture/threat-model.md) §A04 |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | 1 Stage + 0 Transition の最小 Workflow が構築できる（終端 Stage = entry Stage） | TC-UT-WF-001 |
| 2 | entry_stage_id が stages に存在しない場合 `WorkflowInvariantViolation` | TC-UT-WF-002 |
| 3 | 孤立 Stage（entry から到達不能）があれば `WorkflowInvariantViolation` | TC-UT-WF-003 |
| 4 | 終端 Stage が 0 件（全 Stage に外向き Transition あり = 循環）なら `WorkflowInvariantViolation` | TC-UT-WF-004 |
| 5 | 同一 `from_stage_id × condition` の Transition 重複は `WorkflowInvariantViolation` | TC-UT-WF-005 |
| 6 | `EXTERNAL_REVIEW` Stage で `notify_channels` 空なら `WorkflowInvariantViolation` | TC-UT-WF-006 |
| 7 | `required_role` 空集合の Stage を含む Workflow 構築は `WorkflowInvariantViolation` | TC-UT-WF-007 |
| 8 | `add_stage` 失敗時、Workflow 状態が変化していない（pre-validate 確認） | TC-UT-WF-008 |
| 9 | `remove_stage(entry_stage_id)` は `WorkflowInvariantViolation` | TC-UT-WF-009 |
| 10 | V モデル開発室レンダリング例（[`transactions.md`](../../architecture/domain-model/transactions.md)）を `from_dict` で構築できる | TC-UT-WF-010（E2E 相当） |
| 11 | `pyright --strict` および `ruff check` がエラーゼロ | CI lint / typecheck ジョブ |
| 12 | カバレッジが `domain/workflow.py` で 80% 以上 | pytest --cov |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Workflow.name | "V モデル開発フロー" 等の定義名 | 低 |
| Stage.deliverable_template | Stage の成果物 Markdown テンプレ | 低 |
| Stage.notify_channels | Discord webhook URL 等 | **中**（URL 自体は秘匿性中、配信時にマスキング対象。詳細は [`storage.md`](../../architecture/domain-model/storage.md)）|
