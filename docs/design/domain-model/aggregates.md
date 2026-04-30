# Aggregate / Entity 詳細

> [`../domain-model.md`](../domain-model.md) の補章。各 Aggregate Root の属性・不変条件・ふるまいを凍結する。

## Empire（Aggregate Root、シングルトン）

| 属性 | 型 | 制約 | 意図 |
|----|----|----|----|
| `id` | `EmpireId`（UUID） | 不変 | bakufu インスタンスの一意識別 |
| `name` | `str` | 1〜80 文字 | 人間が認識する名前（例: "山田の幕府"） |
| `rooms` | `List[RoomRef]` | — | 編成された Room の参照（実体は別 Aggregate） |
| `agents` | `List[AgentRef]` | — | 採用された Agent の参照 |

**不変条件**:
- bakufu インスタンスにつき Empire は 1 つ（CEO = リポジトリオーナー）
- `rooms` / `agents` は参照のみ。実体は別 Aggregate なので Empire 経由での更新不可

**ふるまい**:
- `hire_agent(agent_data) -> AgentId`: Agent Aggregate を作成し、Empire の agents リストに追加
- `establish_room(room_data) -> RoomId`: Room Aggregate を作成し、Empire の rooms リストに追加
- `archive_room(room_id)`: Room を archived 状態に遷移。物理削除はしない（履歴保持）

## Room（Aggregate Root）

| 属性 | 型 | 制約 | 意図 |
|----|----|----|----|
| `id` | `RoomId`（UUID） | 不変 | Room の一意識別 |
| `name` | `str` | 1〜80 文字、Empire 内で一意 | 部屋名（例: "Vモデル開発室"、"アジャイル開発室"、"雑談部屋"） |
| `description` | `str` | 0〜500 文字 | 部屋の用途説明 |
| `workflow_id` | `WorkflowId` | 既存 Workflow を指す | 採用するワークフロー定義 |
| `members` | `List[AgentMembership]` | 同一 Agent の重複不可 | 採用された Agent と Role の対応 |
| `prompt_kit` | `PromptKit`（VO） | — | 部屋固有のシステムプロンプト（前置き） |
| `archived` | `bool` | デフォルト False | アーカイブ状態 |

**不変条件**:
- `workflow_id` は既存 Workflow を指す（参照整合性）
- `members` 内に同一 `agent_id` × 同一 `role` の重複なし
- `members` 内に少なくとも 1 名の `role == leader` の Agent が存在（Workflow が leader を要求する場合）

**ふるまい**:
- `add_member(agent_id, role)`: メンバー追加。`agent_id` の存在は application 層で検証
- `remove_member(agent_id, role)`: メンバー削除
- `update_prompt_kit(prompt_kit)`: プロンプト更新
- `archive()`: アーカイブ状態に遷移

## Workflow（Aggregate Root）

| 属性 | 型 | 制約 | 意図 |
|----|----|----|----|
| `id` | `WorkflowId`（UUID） | 不変 | Workflow の一意識別 |
| `name` | `str` | 1〜80 文字 | "V モデル開発フロー"、"アジャイル 1 週間スプリント" 等 |
| `stages` | `List[Stage]` | 1 件以上 | 工程ノード |
| `transitions` | `List[Transition]` | 0 件以上 | 工程間の遷移エッジ（DAG、差し戻しループ可） |
| `entry_stage_id` | `StageId` | `stages` 内に存在 | タスク開始時の初期 Stage |

`Stage` / `Transition` の属性詳細は [`value-objects.md`](value-objects.md) §Workflow 構成要素 参照。

**不変条件**:
- 全 Stage は `entry_stage_id` から到達可能（孤立 Stage 禁止）
- 全 Transition の `from_stage_id` / `to_stage_id` は `stages` 内に存在
- 終端 Stage（外向き Transition なし）が 1 件以上存在
- `EXTERNAL_REVIEW` Stage は `notify_channels` を持つ
- 同じ `from_stage_id` × `condition` の Transition は重複しない（決定論的）
- 各 Stage の `required_role` は空集合でない（最低 1 件の Role を持つ）— Stage 自身の不変条件だが、Workflow.validate() でも全 Stage を走査して集約検査する

**ふるまい**:
- `add_stage(stage_data) -> StageId`
- `add_transition(transition_data) -> TransitionId`
- `remove_stage(stage_id)`: 関連 Transition も削除。entry_stage_id を指す Stage は削除不可
- `validate() -> None`: 不変条件チェック。違反時は `WorkflowInvariantViolation` を raise（Fail Fast）

### `validate()` 呼びタイミングとロールバック方式（確定）

Aggregate Root は常に valid な状態を保つことを契約とする。`validate()` の呼びタイミングと「失敗時に Aggregate 状態が変更前に戻ること」の実現方式を以下に固定する。

**ロールバック実装方式: pre-validate 採用**

| 候補 | 採否 | 理由 |
|----|----|----|
| memento（変更前状態の deepcopy 退避 → 失敗時復元） | 不採用 | deepcopy のコスト、復元忘れリスク、Aggregate を途中で不正状態にする窓が開く |
| copy-on-write（毎操作で新 Aggregate を生成して置換） | 不採用 | Python frozen dataclass で表現可能だが Aggregate 全体を毎回再生成するオーバーヘッドが大きい |
| **pre-validate**（変更後の仮想状態を構築し validate 通過後に置換） | **採用** | Aggregate を不正状態にする窓が一瞬も開かない。失敗時は単に raise するだけで「ロールバック」が要らない |

**呼びタイミング**:

| タイミング | 実装場所 | 失敗時の挙動 |
|----------|---------|-------------|
| **構築完了時** | コンストラクタ末尾（`__post_init__` / Pydantic `model_validator`） | 不正な初期状態の Aggregate を生成させない（インスタンス化が失敗） |
| **状態変更ふるまい末尾** | `add_stage` / `add_transition` / `remove_stage` の最後 | pre-validate 方式: 内部で「変更後の stages / transitions を別オブジェクトとして仮構築」→ `validate()` 走行 → 通過時のみ自身に代入。失敗時は元の状態が変わっておらず、`WorkflowInvariantViolation` を raise |
| **bulk import ファクトリ** | `Workflow.from_dict(payload)` の末尾に 1 回のみ | 途中状態は valid でなくてよい。最終状態のみ検証 |

application 層の `Repository.save(workflow)` は **再 validate しない**。Aggregate Root が常に valid である契約を Repository が前提として受け取るため。Repository 側で再検証するのは契約違反を疑う設計（責務の二重化）であり、避ける。

**Fail Fast 原則との整合**:
- 不正な状態が一瞬でも Aggregate に存在すると、その間に Domain Event が発火した場合に伝播する
- pre-validate 方式は不正状態の窓をゼロにする
- 構築完了時 + 状態変更末尾の 2 点で常時 valid を保てば、Repository / interfaces / application 層は Aggregate の妥当性を疑う必要がない

## Agent（Aggregate Root）

| 属性 | 型 | 制約 | 意図 |
|----|----|----|----|
| `id` | `AgentId`（UUID） | 不変 | Agent の一意識別 |
| `name` | `str` | 1〜40 文字、Empire 内で一意 | 表示名 |
| `persona` | `Persona`（VO） | — | キャラクター設定（自然言語）、システムプロンプトに展開される |
| `role` | `Role` | — | 役割テンプレ（Room 採用時の既定値） |
| `providers` | `List[ProviderConfig]` | 1 件以上 | LLM プロバイダ設定（Claude Code / Codex / Gemini / OpenCode 等） |
| `skills` | `List[SkillRef]` | 0 件以上 | 添付スキル（Markdown プロンプト） |
| `archived` | `bool` | デフォルト False | アーカイブ状態 |

`Persona` / `ProviderConfig` の属性詳細は [`value-objects.md`](value-objects.md) §Agent 構成要素 参照。

**不変条件**:
- `providers` のうち `is_default == True` は 1 件のみ
- `name` は Empire 内で一意（人間がチャネルで識別する基準）

## Task（Aggregate Root）

| 属性 | 型 | 制約 | 意図 |
|----|----|----|----|
| `id` | `TaskId`（UUID） | 不変 | Task の一意識別 |
| `room_id` | `RoomId` | 既存 Room を指す | 所属する Room |
| `directive_id` | `DirectiveId` | 既存 Directive を指す | 起点となった指令 |
| `current_stage_id` | `StageId` | Room の Workflow 内の Stage | 現在進行中の工程 |
| `deliverables` | `Dict[StageId, Deliverable]` | — | Stage ごとの成果物スナップショット |
| `status` | `TaskStatus` | PENDING / IN_PROGRESS / AWAITING_EXTERNAL_REVIEW / BLOCKED / DONE / CANCELLED | 全体状態 |
| `assigned_agent_ids` | `List[AgentId]` | Room の members 内 | 現 Stage に割当中の Agent |
| `created_at` / `updated_at` | `datetime` | UTC | 監査用 |

`Deliverable` の属性詳細は [`storage.md`](storage.md) §Deliverable / Attachment 参照。

**TaskStatus 遷移**:

```
PENDING
   ↓ (assign agents)
IN_PROGRESS
   ↓ (Stage が EXTERNAL_REVIEW に到達)
AWAITING_EXTERNAL_REVIEW
   ↓ (Gate APPROVED)
IN_PROGRESS（次 Stage へ）
   ↓ (終端 Stage に到達 + APPROVED)
DONE

任意時点 → CANCELLED（CEO 判断）
AWAITING_EXTERNAL_REVIEW + REJECTED → IN_PROGRESS（差し戻し先 Stage へ）
IN_PROGRESS + LLM Adapter 復旧不能エラー → BLOCKED（人間介入待ち）
BLOCKED + 人間が retry → IN_PROGRESS（再試行）
BLOCKED + 人間が cancel → CANCELLED
```

**`BLOCKED` の意図**: LLM Adapter が `AuthExpired` などリトライで自動復旧不能なエラーを返したとき、Task は中断状態になる。`IN_PROGRESS` のまま放置すると Dispatcher が無限再試行するため、`BLOCKED` で明示的に隔離し、Owner が UI / CLI で復旧操作を行う。詳細は [`../tech-stack.md`](../tech-stack.md) §LLM Adapter 運用方針 参照。

**不変条件**:
- `current_stage_id` は Room の Workflow 内の Stage を指す
- `assigned_agent_ids` は Room の members に含まれる
- `status == DONE` の Task は更新不可

**ふるまい**:
- `assign(agent_ids)`: Agent を current_stage に割当
- `commit_deliverable(stage_id, deliverable, by_agent_id)`: 成果物登録
- `request_external_review() -> ExternalReviewGate`: 外部レビューゲートを生成（別 Aggregate）
- `advance(transition_id, by_owner_id)`: Stage を進める（Transition 経由）
- `cancel(by_owner_id, reason)`: 中止
- `block(reason, last_error)`: BLOCKED 状態に遷移（LLM Adapter 復旧不能エラー時、application 層が呼ぶ）
- `unblock_retry()`: BLOCKED → IN_PROGRESS、現 Stage を再実行（admin CLI 経由）

## Directive（Aggregate Root）

| 属性 | 型 | 制約 | 意図 |
|----|----|----|----|
| `id` | `DirectiveId`（UUID） | 不変 | 指令の一意識別 |
| `text` | `str` | 1〜10000 文字 | CEO directive 本文（`$` プレフィックスから始まる） |
| `target_room_id` | `RoomId` | 既存 Room | 委譲先の部屋 |
| `created_at` | `datetime` | UTC | 発行時刻 |
| `task_id` | `TaskId | None` | — | 生成された Task（未着手なら None） |

**ふるまい**:
- `spawn_task() -> Task`: 委譲先 Room の Workflow から Task を生成

## ExternalReviewGate（独立 Aggregate Root）

| 属性 | 型 | 制約 | 意図 |
|----|----|----|----|
| `id` | `GateId`（UUID） | 不変 | Gate の一意識別 |
| `task_id` | `TaskId` | 既存 Task | 対象タスク |
| `stage_id` | `StageId` | EXTERNAL_REVIEW Stage | 対象工程 |
| `deliverable_snapshot` | `Deliverable`（VO） | — | レビュー対象の成果物（凍結） |
| `reviewer_id` | `OwnerId` | — | 人間レビュワー（既定は CEO） |
| `decision` | `ReviewDecision` | PENDING / APPROVED / REJECTED / CANCELLED | 判断結果 |
| `feedback_text` | `str` | 0〜10000 文字 | 差し戻し理由・承認コメント |
| `audit_trail` | `List[AuditEntry]` | — | 誰がいつ何を見たかの監査ログ |
| `created_at` / `decided_at` | `datetime` | UTC | 監査用 |

**設計上の重要ポイント**: ExternalReviewGate は Stage の属性ではなく **独立した Aggregate**。理由:

- **エンティティ寿命が Stage と一致しない**: 差し戻し後も履歴を保持する必要がある（複数ラウンド可）
- **トランザクション境界が異なる**: Task の状態遷移と Gate の判断は別の人間（Agent vs CEO）が異なるタイミングで行う
- **AI 協業による品質向上を、人間チェックポイントで担保**するという bakufu の核心要件をモデル上で明示

**不変条件**:
- `decision` の遷移は `PENDING → APPROVED` / `PENDING → REJECTED` / `PENDING → CANCELLED` のいずれか 1 回のみ（不変）
- `decided_at` は `decision != PENDING` 時のみ非 None
- `deliverable_snapshot` は Gate 生成時に凍結、以後不変

**ふるまい**:
- `approve(by_owner_id, comment)`: PENDING → APPROVED、Task に `advance` を要求するイベント発火
- `reject(by_owner_id, comment)`: PENDING → REJECTED、Task に `advance(transition_id=REJECTED)` を要求するイベント発火
- `cancel(by_owner_id, reason)`: PENDING → CANCELLED（Task が CANCELLED になったときに連鎖）
- `record_view(by_owner_id, viewed_at)`: audit_trail に追加（閲覧記録）

## Conversation（Entity、Task に従属）

| 属性 | 型 | 制約 | 意図 |
|----|----|----|----|
| `id` | `ConversationId`（UUID） | 不変 | 一意識別 |
| `task_id` | `TaskId` | — | 所属タスク |
| `stage_id` | `StageId` | — | 所属工程 |
| `messages` | `List[Message]` | 時系列順 | Agent 間の対話ログ |

`Message` の属性は [`value-objects.md`](value-objects.md) §Conversation 参照。

ai-team の「チャネル」概念に相当。Web UI では Room の対話空間として表示される。

**重要**: `Message.body_markdown` および subprocess の stdout / stderr を message として保存する際は、永続化前に [`storage.md`](storage.md) §シークレットマスキング規則 を必ず適用する。

## DeliverableTemplate（Aggregate Root、Issue #115）

| 属性 | 型 | 制約 | 意図 |
|----|----|----|----|
| `id` | `DeliverableTemplateId`（UUID） | 不変 | テンプレートの一意識別 |
| `name` | `str` | 1〜80 文字 | 人間が認識するテンプレート名（例: "基本設計書テンプレ"） |
| `type` | `TemplateType` | `MARKDOWN` / `JSON_SCHEMA` / `OPENAPI` / `CODE_SKELETON` / `PROMPT` | テンプレートの種別 |
| `version` | `SemVer` | major >= 0、minor >= 0、patch >= 0 | セマンティックバージョン（例: 1.0.0） |
| `body` | `str` | 1〜100000 文字 | テンプレート本文（種別に応じた書式） |
| `acceptance_criteria` | `List[AcceptanceCriterion]` | 0 件以上 | このテンプレートが定義する受入基準の一覧 |
| `composed_of` | `List[DeliverableTemplateRef]` | 0 件以上、循環参照禁止 | 合成元テンプレートへの参照（合成テンプレートの場合） |
| `created_at` / `updated_at` | `datetime` | UTC | 監査用 |

構成要素 VO（`SemVer` / `DeliverableTemplateRef` / `AcceptanceCriterion`）の属性詳細は [`value-objects.md`](value-objects.md) §DeliverableTemplate 構成要素 参照。

**不変条件**:
- `type == JSON_SCHEMA` の場合、`body` は有効な JSON Schema である（構築時に検証）
- `composed_of` に自身の `id` を含む直接・間接の循環参照は禁止
- `composed_of` 内の各 `DeliverableTemplateRef.minimum_version` の `major` は参照先テンプレートの現行 `major` と一致しなければならない（互換性制約）
- `acceptance_criteria` 内の `AcceptanceCriterion.id` は重複しない

**ふるまい**:
- `create_new_version(bump: 'major' | 'minor' | 'patch') -> DeliverableTemplate`: 現バージョンから新バージョンのテンプレートを生成（別 Aggregate として永続化）
- `add_composition(ref: DeliverableTemplateRef) -> None`: 合成元テンプレートを追加。循環参照が生じる場合は `[FAIL]` + `Next:` の形式でドメイン例外を raise（pre-validate 方式）
- `remove_composition(template_id: DeliverableTemplateId) -> None`: 合成元テンプレートを削除
- `add_acceptance_criterion(criterion: AcceptanceCriterion) -> None`: 受入基準を追加
- `resolve_criteria() -> List[AcceptanceCriterion]`: `composed_of` を再帰的に展開し、全受入基準をフラット化して返す

## RoleProfile（Aggregate Root、Issue #115 / #116）

| 属性 | 型 | 制約 | 意図 |
|----|----|----|----|
| `id` | `RoleProfileId`（UUID） | 不変 | RoleProfile の一意識別 |
| `empire_id` | `EmpireId`（UUID） | 不変 | 所属 Empire（`(empire_id, role)` DB 一意制約の基盤、§確定D）|
| `role` | `Role`（StrEnum） | 不変 | この RoleProfile が対応する役割（例: `DEVELOPER`） |
| `deliverable_template_refs` | `tuple[DeliverableTemplateRef, ...]` | 空 tuple 許容 | この役割が担う成果物テンプレートへの参照一覧（immutable）|

**不変条件**:
- `deliverable_template_refs` 内の `DeliverableTemplateRef.template_id` は重複しない（`_validate_no_duplicate_refs`）
- 空 tuple は許容（0 件の状態も有効）

**ふるまい**:
- `add_template_ref(ref: DeliverableTemplateRef) -> RoleProfile`: テンプレート参照を追加した新インスタンスを返す。重複時は `RoleProfileInvariantViolation(kind='duplicate_template_ref')` を raise（MSG-DT-004）
- `remove_template_ref(template_id: DeliverableTemplateId) -> RoleProfile`: テンプレート参照を削除した新インスタンスを返す。指定 `template_id` が存在しない場合は `RoleProfileInvariantViolation(kind='template_ref_not_found')` を raise（MSG-DT-005）
- `get_all_acceptance_criteria(template_lookup: Mapping[DeliverableTemplateId, DeliverableTemplate]) -> list[AcceptanceCriterion]`: `deliverable_template_refs` を展開し、各テンプレートの `acceptance_criteria` を union する。`criterion.id` 重複は先頭出現を保持して除去。`required=True` を先頭、`required=False` を後続に安定ソートして返す（§確定E）

> **設計コントラクト**: 全ての書き換えふるまい（`add_template_ref` / `remove_template_ref`）は `model_dump → state 更新 → model_validate` の pre-validate 方式（§確定A）。元インスタンスは常に不変。`(empire_id, role)` の empire スコープ一意性は application / repository 層の責務（§確定D）。
