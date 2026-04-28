# 要求分析書

> feature: `agent`
> Issue: [#10 feat(agent): Agent Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/10)
> 凍結済み設計: [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Agent / [`value-objects.md`](../../design/domain-model/value-objects.md) §Agent 構成要素

## 人間の要求

> Issue #10:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の一環として **Agent Aggregate Root** を実装する。Agent は Persona / Role / LLM プロバイダ設定を持つ採用済み AI エージェントで、Room の `members` に紐づく中核 Aggregate。

## 背景・目的

### 現状の痛点

1. bakufu の核心思想「複数 AI エージェントの役割分担」は Agent Aggregate なしには実現できない。Persona / Role / Provider 設定を 1 つの整合性ある単位として扱う Aggregate が必要
2. M1 後段の `room` Issue は `AgentMembership` を介して Agent を参照する設計。Agent が無いと Room の `members` を構築できない
3. M1 後段の `task` Issue は `assigned_agent_ids` で Agent を参照し、LLM Adapter が `ProviderConfig` を読んで CLI / API を選択する。Agent が無いと LLM Adapter の Strategy 選択ができない

### 解決されれば変わること

- `room` / `task` Issue が Agent 参照を前提に実装可能になる
- LLM Adapter（`feature/llm-adapter`）が `ProviderConfig.is_default` を見てプロバイダを決定できる
- Persona / ProviderConfig / SkillRef の VO お手本が揃い、後続 Aggregate（Workflow と並んで）が Persona-like な VO を引用できる

### ビジネス価値

- bakufu の差別化「Persona 注入による Agent の個性化」が Aggregate 単位で扱えるようになる
- マルチプロバイダ対応（Claude Code / Codex / Gemini）の切替経路が `is_default` フラグ + Strategy パターンで実装可能になる

## 議論結果

### 設計担当による採用前提

- Agent Aggregate は **Pydantic v2 BaseModel + frozen + model_validator(mode='after')**（Empire / Workflow と同じ規約）
- `Persona` / `ProviderConfig` / `SkillRef` は frozen VO として本 feature で凍結
- Empire 内の `name` 一意制約は **application 層責務**（同 Empire 内の他 Agent との衝突は Repository が SELECT して判定）。Aggregate 内では「name は非空かつ 1〜40 文字」だけ守る
- `providers` の `is_default == True` は **Aggregate 内不変条件**として 1 件のみを強制
- `archive()` ふるまいは Empire と同様、`archived = True` への遷移のみ。物理削除なし

### 却下候補と根拠

| 候補 | 却下理由 |
|-----|---------|
| Persona を文字列単一フィールドにする | `display_name` / `archetype` / `prompt_body` は意味が異なる。VO 化することで UI の表示・編集境界が明確になり、prompt_body のサニタイズや archetype の i18n キー化が後段で容易 |
| `providers` を Dict[ProviderKind, ProviderConfig] にする | 同一プロバイダで複数モデル設定を持つケースを排除してしまう（例: Claude Code Sonnet + Opus）。List で持ち、`is_default` で 1 つを選ぶ設計が柔軟 |
| Agent.name の Empire 内一意を Aggregate 内で強制 | Aggregate 集合知識を要するため Aggregate Root の責務外。Repository SELECT でのみ判定可能 |
| Skill を独立 Aggregate にする | MVP では Skill は Markdown プロンプトの参照のみ（Phase 2 で実体化）。MVP では `SkillRef`（id + name + path）の VO のみ持つ |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: providers の `is_default` 一意制約の Aggregate 内検査

`model_validator(mode='after')` で:

1. `providers` 内で `is_default == True` の件数をカウント
2. 0 件または 2 件以上なら `AgentInvariantViolation(kind='default_provider_not_unique')` を raise

これは Aggregate 内不変条件として明確に定義される（外部知識を要しない）。

#### 確定 R1-B: name の Empire 内一意は application 層責務

application 層 `AgentService.hire()`（別 Issue で実装）の責務:

1. `AgentRepository.find_by_name(empire_id, name)` を呼ぶ
2. ヒットしたら `AgentNameAlreadyExistsError` を raise（Fail Fast）
3. 0 件なら新規 Agent を構築・保存

ドメイン層の Agent はこの呼び出し前提で「自身では名前一意を強制しない」契約。

#### 確定 R1-C: archive ふるまいの返り値型

`archive() -> Agent`（新インスタンス）。Empire / Workflow と同じく frozen の制約上、状態変更は新インスタンス返却。

#### 確定 R1-D: Persona.prompt_body のサイズ上限

`prompt_body` は LLM のシステムプロンプトに展開される自然言語。MVP では 0〜10000 文字。Phase 2 でプロバイダごとのトークン上限に応じて調整。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 個人開発者 CEO | bakufu インスタンスのオーナー | GitHub / Docker / CLI 日常使用 | UI から Agent を採用し、Persona / Role / Provider を編集する | 数クリックで Agent を採用、複数 LLM プロバイダから 1 つを既定として選択 |

bakufu システム全体のペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

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
| REQ-AG-001 | Agent 構築 | コンストラクタで `id` / `name` / `persona` / `role` / `providers` を受け取り、不変条件を検査して valid な Agent を返す | 必須 |
| REQ-AG-002 | Provider 切替 | `set_default_provider(provider_kind)` で既存プロバイダの `is_default` を更新 | 必須 |
| REQ-AG-003 | Skill 追加 | `add_skill(skill_ref)` で `skills` リストに追加。重複は不変条件違反 | 必須 |
| REQ-AG-004 | Skill 削除 | `remove_skill(skill_id)` で skills から削除 | 必須 |
| REQ-AG-005 | アーカイブ | `archive()` で `archived = True` への遷移 | 必須 |
| REQ-AG-006 | 不変条件検査 | `providers` の `is_default == True` が 1 件のみ、`name` 1〜40 文字、`skills` の `skill_id` 重複なし | 必須 |

## Sub-issue 分割計画

本 Issue は単一 Aggregate に閉じる粒度のため Sub-issue 分割は不要。1 PR で 4 設計書 + 実装 + ユニットテストを完結させる。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 単一 PR | REQ-AG-001〜006 | Agent + Persona / ProviderConfig / SkillRef VO + ユニットテスト | chore #7 マージ済み |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 不変条件検査は O(P+S)（P=providers 件数、S=skills 件数）。MVP の想定規模 P ≤ 10, S ≤ 20 で 1ms 未満 |
| 可用性 | 該当なし — domain 層 |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 80% 以上 |
| 可搬性 | 純 Python のみ |
| セキュリティ | `Persona.prompt_body` は LLM システムプロンプトに展開される。永続化前にマスキング規則の適用対象（[`storage.md`](../../design/domain-model/storage.md) §シークレットマスキング規則）。詳細は [`threat-model.md`](../../design/threat-model.md) §A04 |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | 1 Provider（is_default=True）の最小 Agent が構築できる | TC-UT-AG-001 |
| 2 | name が 0 文字 / 41 文字以上で `AgentInvariantViolation` | TC-UT-AG-002 |
| 3 | providers の `is_default == True` が 0 件で `AgentInvariantViolation` | TC-UT-AG-003 |
| 4 | providers の `is_default == True` が 2 件以上で `AgentInvariantViolation` | TC-UT-AG-004 |
| 5 | `set_default_provider(kind)` で既定プロバイダが切り替わり、他は False になる | TC-UT-AG-005 |
| 6 | 存在しない `provider_kind` で `set_default_provider` は `AgentInvariantViolation` | TC-UT-AG-006 |
| 7 | `add_skill(skill_ref)` で skills に追加 | TC-UT-AG-007 |
| 8 | 同一 `skill_id` の `add_skill` は `AgentInvariantViolation` | TC-UT-AG-008 |
| 9 | `remove_skill(skill_id)` で skills から削除 | TC-UT-AG-009 |
| 10 | `archive()` で `archived = True` の新 Agent を返す | TC-UT-AG-010 |
| 11 | Persona / ProviderConfig / SkillRef は frozen で構造的等価判定 | TC-UT-AG-011 |
| 12 | `pyright --strict` および `ruff check` がエラーゼロ | CI lint / typecheck |
| 13 | カバレッジが `domain/agent.py` で 80% 以上 | pytest --cov |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Agent.name | "イーロン" / "ダリオ" 等の表示名 | 低 |
| Persona.prompt_body | LLM システムプロンプト | 中（個人攻撃や違法行為を促す内容を含む可能性、UI 入力時に長さ上限・基本サニタイズ。詳細は別 feature） |
| ProviderConfig.model | "sonnet" / "gpt-5-codex" 等 | 低 |
| SkillRef.path | スキル markdown ファイルパス | 低 |
