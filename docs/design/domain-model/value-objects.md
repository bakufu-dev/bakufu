# Value Object / Entity 詳細

> [`../domain-model.md`](../domain-model.md) の補章。Aggregate に従属する Value Object と Entity の属性を凍結する。

## ID 型一覧（すべて UUIDv4）

| 名前 | 種別 | 用途 |
|----|----|----|
| `EmpireId` | UUID（VO） | Empire の一意識別 |
| `RoomId` | UUID（VO） | Room の一意識別 |
| `WorkflowId` | UUID（VO） | Workflow の一意識別 |
| `StageId` | UUID（VO） | Stage の一意識別 |
| `TransitionId` | UUID（VO） | Transition の一意識別 |
| `AgentId` | UUID（VO） | Agent の一意識別 |
| `TaskId` | UUID（VO） | Task の一意識別 |
| `DirectiveId` | UUID（VO） | Directive の一意識別 |
| `GateId` | UUID（VO） | ExternalReviewGate の一意識別 |
| `ConversationId` | UUID（VO） | Conversation の一意識別 |
| `MessageId` | UUID（VO） | Message の一意識別 |
| `OwnerId` | UUID（VO） | Owner / Reviewer の一意識別 |
| `EventId` | UUID（VO） | Domain Event の一意識別（Outbox 行 PK と一致） |
| `DeliverableTemplateId` | UUID（VO） | DeliverableTemplate の一意識別 |
| `RoleProfileId` | UUID（VO） | RoleProfile の一意識別 |

## 列挙型一覧

| 名前 | 値 | 意図 |
|----|----|----|
| `StageKind` | `WORK` / `INTERNAL_REVIEW` / `EXTERNAL_REVIEW` | Stage の種別 |
| `TransitionCondition` | `APPROVED` / `REJECTED` / `CONDITIONAL` / `TIMEOUT` | Transition の発火条件 |
| `Role` | `LEADER` / `DEVELOPER` / `TESTER` / `REVIEWER` / `UX` / `SECURITY` / `ASSISTANT` / `DISCUSSANT` / `WRITER` / `SITE_ADMIN` | Agent / Stage が要求する役割 |
| `TaskStatus` | `PENDING` / `IN_PROGRESS` / `AWAITING_EXTERNAL_REVIEW` / `BLOCKED` / `DONE` / `CANCELLED` | Task の全体状態 |
| `ReviewDecision` | `PENDING` / `APPROVED` / `REJECTED` / `CANCELLED` | ExternalReviewGate の判断結果 |
| `ProviderKind` | `CLAUDE_CODE` / `CODEX` / `GEMINI` / `OPENCODE` / `KIMI` / `COPILOT` | LLM プロバイダ種別 |
| `SpeakerKind` | `AGENT` / `OWNER` / `SYSTEM` | Conversation 発話者の種別 |
| `OutboxStatus` | `PENDING` / `DISPATCHING` / `DISPATCHED` / `DEAD_LETTER` | Outbox 行の配送状態 |
| `LLMErrorKind` | `SESSION_LOST` / `RATE_LIMITED` / `AUTH_EXPIRED` / `TIMEOUT` / `UNKNOWN` | LLM Adapter のエラー分類 |
| `AuditAction` | `VIEWED` / `RETRIED` / `CANCELLED` / `APPROVED` / `REJECTED` / `ADMIN_RETRY_TASK` / `ADMIN_CANCEL_TASK` / `ADMIN_RETRY_EVENT` / `ADMIN_LIST_BLOCKED` / `ADMIN_LIST_DEAD_LETTERS` | 監査ログのアクション種別 |
| `TemplateType` | `MARKDOWN` / `JSON_SCHEMA` / `OPENAPI` / `CODE_SKELETON` / `PROMPT` | DeliverableTemplate の種別 |

## Workflow 構成要素

### Stage（Entity within Workflow Aggregate）

| 属性 | 型 | 制約 |
|----|----|----|
| `id` | `StageId` | 不変 |
| `name` | `str` | 1〜80 文字（例: "要求分析"、"基本設計"、"実装"、"外部レビュー"） |
| `kind` | `StageKind` | `WORK` / `INTERNAL_REVIEW` / `EXTERNAL_REVIEW` |
| `required_role` | `frozenset[Role]` | この Stage を担当する Role の集合。**空集合は不可（最低 1 件）**。複数役割の協業を表現できる（例: `{LEADER, UX}`） |
| `required_deliverables` | `tuple[DeliverableRequirement, ...]` | この Stage で期待される成果物要件のリスト（空 tuple 許容）。`DeliverableRequirement.template_ref.template_id` は重複不可 |
| `completion_policy` | `CompletionPolicy`（VO） | 完了判定ロジック（例: "approved by reviewer" / "all checklist items checked"） |
| `notify_channels` | `List[NotifyChannel]` | `EXTERNAL_REVIEW` のときのみ必須。Discord / Slack / Email 等の通知先 |

**`required_role` を集合型にした理由**:
- 業務工程は単一役割で完結しないことが多い（例: 要件定義は LEADER + UX、基本設計は DEVELOPER + UX）
- 単一 `Role` から複数を表現するために合成 enum 値（`LEADER_AND_UX` 等）を増やすと組合せ爆発する
- `frozenset[Role]` は不変・順序非依存・集合演算（`is_subset_of` 等）が標準で使える
- Stage 担当割当時に「Agent の `role` が `required_role` に含まれるか」を `agent.role in stage.required_role` で素直に判定できる

### Transition（Entity within Workflow Aggregate）

| 属性 | 型 | 制約 |
|----|----|----|
| `id` | `TransitionId` | 不変 |
| `from_stage_id` | `StageId` | `stages` 内に存在 |
| `to_stage_id` | `StageId` | `stages` 内に存在 |
| `condition` | `TransitionCondition` | `APPROVED` / `REJECTED` / `CONDITIONAL` / `TIMEOUT` |
| `label` | `str` | UI 表示ラベル（例: "差し戻し"、"次工程へ"） |

## Agent 構成要素

### Persona（Value Object）

| 属性 | 型 |
|----|----|
| `display_name` | `str` |
| `archetype` | `str`（例: "イーロン・マスク風 CEO"） |
| `prompt_body` | `str`（Markdown、システムプロンプトに展開される自然言語） |

### ProviderConfig（Value Object）

| 属性 | 型 |
|----|----|
| `provider_kind` | `ProviderKind`（CLAUDE_CODE / CODEX / GEMINI / OPENCODE / KIMI / COPILOT 等） |
| `model` | `str`（例: "sonnet"、"opus"、"gpt-5-codex"） |
| `is_default` | `bool` |

### AgentMembership（Value Object、Room に従属）

| 属性 | 型 | 制約 |
|----|----|----|
| `agent_id` | `AgentId` | 既存 Agent を指す |
| `role` | `Role` | leader / developer / tester / reviewer / ux / security / discussant / writer 等 |
| `joined_at` | `datetime` | UTC |

## Room 構成要素

### PromptKit（Value Object、Room に従属）

| 属性 | 型 | 制約 |
|----|----|----|
| `prefix_markdown` | `str` | 0〜10000 文字（NFC 正規化のみ、strip しない — Markdown の前後改行を保持）。永続化前に [`storage.md`](storage.md) §シークレットマスキング規則 を適用（[`feature/room`](../../features/room/detailed-design.md) §確定 B / G で凍結） |

`Persona.prompt_body` と同じ規約（NFC のみ、strip しない）。Phase 2 で `variables: dict[str, str]` / `role_specific_prefix: dict[Role, str]` / `sections: list[Section]` の追加余地を残すため VO 化を維持する。詳細は [`feature/room/detailed-design.md`](../../features/room/detailed-design.md) §確定 G。

## Conversation 構成要素

### Message（Value Object）

| 属性 | 型 | 備考 |
|----|----|----|
| `id` | `MessageId` | 一意識別 |
| `speaker_kind` | `SpeakerKind` | AGENT / OWNER / SYSTEM |
| `speaker_id` | `AgentId | OwnerId | None` | speaker_kind に応じて型が決まる |
| `body_markdown` | `str` | 永続化前に [`storage.md`](storage.md) §シークレットマスキング規則 を適用 |
| `timestamp` | `datetime` | UTC |

## ExternalReviewGate 監査ログ

### AuditEntry（Value Object）

| 属性 | 型 |
|----|----|
| `id` | `UUID` |
| `actor_id` | `OwnerId` |
| `action` | `AuditAction`（VIEWED / APPROVED / REJECTED / CANCELLED 等） |
| `comment` | `str`（0〜2000 文字） |
| `occurred_at` | `datetime`（UTC） |

## Admin CLI 監査ログ（`audit_log` テーブル）

Admin CLI 経由のすべての操作を `audit_log` に永続化する。詳細は [`../tech-stack.md`](../tech-stack.md) §Admin CLI 運用方針 参照。

| 属性 | 型 | 備考 |
|----|----|----|
| `id` | `UUID`（PK） | — |
| `actor` | `str` | OS ユーザー名（`os.getlogin()`）+ ホスト名 |
| `command` | `str` | `retry-task` / `cancel-task` / `retry-event` / `list-blocked` / `list-dead-letters` |
| `args_json` | `JSON` | 引数（マスキング済み） |
| `result` | `enum` | `SUCCESS` / `FAILURE` |
| `error_text` | `str | None` | 失敗時の例外メッセージ（マスキング済み） |
| `executed_at` | `datetime`（UTC） | — |

`audit_log` は **追記のみ**。UPDATE / DELETE は禁止（Repository / SQL レベルで制約）。

## DeliverableTemplate 構成要素

### SemVer（Value Object）

| 属性 | 型 | 制約 |
|----|----|----|
| `major` | `int` | >= 0 |
| `minor` | `int` | >= 0 |
| `patch` | `int` | >= 0 |

- 文字列表現: `"{major}.{minor}.{patch}"`（例: `"1.2.3"`）
- `is_compatible_with(other: SemVer) -> bool`: `self.major == other.major` のとき `True`（major が一致すれば後方互換とみなす）
- 比較は `(major, minor, patch)` の辞書順（タプル比較）
- `SemVer.parse(s: str) -> SemVer`: `"major.minor.patch"` 形式の文字列をパース。不正な書式は `[FAIL]` + `Next:` の形式でドメイン例外を raise

### DeliverableTemplateRef（Value Object）

| 属性 | 型 | 制約 |
|----|----|----|
| `template_id` | `DeliverableTemplateId` | 参照先テンプレートの一意識別 |
| `minimum_version` | `SemVer` | 要求する最低互換バージョン（major が参照先の現行 major と一致すること） |

- `minimum_version.is_compatible_with(actual_version)` が `False` の場合、参照解決時にドメイン例外を raise

### AcceptanceCriterion（Value Object）

| 属性 | 型 | 制約 |
|----|----|----|
| `id` | `UUID` | 不変。テンプレート内で一意 |
| `description` | `str` | 1〜500 文字 |
| `required` | `bool` | デフォルト `True`（必須受入基準か任意受入基準かを区別） |

### DeliverableRequirement（Value Object）

| 属性 | 型 | 制約 |
|----|----|----|
| `template_ref` | `DeliverableTemplateRef` | 参照先成果物テンプレート（`template_id` + `minimum_version`） |
| `optional` | `bool` | `False` のとき必須成果物、`True` のとき任意成果物（デフォルト `False`） |

- Stage 内の `required_deliverables` は `template_ref.template_id` の重複を禁止する（Stage 自身の不変条件で検査、詳細は [`docs/features/workflow/domain/basic-design.md §REQ-WF-007`](../../features/workflow/domain/basic-design.md)）
- `optional=False` の成果物は Task 完了前に提出が期待される（application 層の責務）
- `DeliverableTemplateRef` の `minimum_version` によりバージョン互換性を保証する（`SemVer.is_compatible_with` 経由）
