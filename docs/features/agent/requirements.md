# 要件定義書

> feature: `agent`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/architecture/domain-model/aggregates.md`](../../architecture/domain-model/aggregates.md) §Agent

## 機能要件

### REQ-AG-001: Agent 構築

| 項目 | 内容 |
|------|------|
| 入力 | `id: AgentId`、`name: str`（1〜40）、`persona: Persona`、`role: Role`、`providers: list[ProviderConfig]`（1 件以上）、`skills: list[SkillRef]`（0 件以上、デフォルト []）|
| 処理 | Pydantic 型バリデーション → `model_validator(mode='after')` で不変条件検査 → 通過時のみ Agent を返す |
| 出力 | `Agent` インスタンス（frozen、`archived=False`）|
| エラー時 | `AgentInvariantViolation` を raise。MSG-AG-001〜005 |

### REQ-AG-002: Provider 切替

| 項目 | 内容 |
|------|------|
| 入力 | 現 Agent + `provider_kind: ProviderKind` |
| 処理 | 1) providers 内で `provider_kind` が一致するエントリを探す 2) 見つからなければ raise（MSG-AG-006） 3) 全 providers の `is_default` を再計算（対象を True、他を False） 4) 仮 Agent を `model_validate(updated_dict)` で再構築（不変条件検査） 5) 通過時のみ仮 Agent を返す |
| 出力 | 更新された Agent（新インスタンス） |
| エラー時 | provider_kind 未登録なら `AgentInvariantViolation`（MSG-AG-006）|

### REQ-AG-003: Skill 追加

| 項目 | 内容 |
|------|------|
| 入力 | 現 Agent + `skill_ref: SkillRef` |
| 処理 | 現 `skills` に追加した新リストを構築 → 仮 Agent を再構築 → 不変条件検査 |
| 出力 | 更新された Agent |
| エラー時 | 同一 `skill_id` 重複で `AgentInvariantViolation`（MSG-AG-007）|

### REQ-AG-004: Skill 削除

| 項目 | 内容 |
|------|------|
| 入力 | 現 Agent + `skill_id: SkillId` |
| 処理 | 1) `skills` から該当 SkillRef を除外した新リストを構築 2) 該当が存在しなければ raise（MSG-AG-008） 3) 仮 Agent を再構築・検査 |
| 出力 | 更新された Agent |
| エラー時 | `skill_id` 未登録で `AgentInvariantViolation` |

### REQ-AG-005: アーカイブ

| 項目 | 内容 |
|------|------|
| 入力 | 現 Agent |
| 処理 | `archived=True` に更新した仮 Agent を再構築 |
| 出力 | 更新された Agent |
| エラー時 | 既に `archived=True` の Agent に `archive()` を呼ぶと冪等で同じ状態を返す（エラーにしない） |

### REQ-AG-006: 不変条件検査

| 項目 | 内容 |
|------|------|
| 入力 | Agent インスタンス（コンストラクタ末尾 / 状態変更ふるまい末尾で自動呼び出し） |
| 処理 | `model_validator(mode='after')` で: ①`name` 1〜40 文字 ②`providers` 内 `is_default == True` が 1 件のみ ③`providers` 内 `provider_kind` の重複なし ④`skills` 内 `skill_id` の重複なし |
| 出力 | None |
| エラー時 | いずれか違反で `AgentInvariantViolation`（kind に違反種別） |

## 画面・CLI 仕様

### CLI レシピ / コマンド

該当なし — 理由: 本 feature は domain 層のみ。Admin CLI は `feature/admin-cli` で扱う。

### Web UI 画面

該当なし — 理由: UI は `feature/agent-ui` で扱う。

## API 仕様

該当なし — 理由: 本 feature は domain 層のみ。HTTP API は `feature/http-api` で扱う。

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| 該当なし | — | — | — | — |

## データモデル

凍結済み設計（[`docs/architecture/domain-model/aggregates.md`](../../architecture/domain-model/aggregates.md) §Agent / [`value-objects.md`](../../architecture/domain-model/value-objects.md) §Agent 構成要素）に従う。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| Agent（Aggregate Root） | `id` | `AgentId`（UUID） | 不変 | — |
| Agent | `name` | `str` | 1〜40 文字、Empire 内一意（application 層責務） | — |
| Agent | `persona` | `Persona`（VO） | — | Persona VO |
| Agent | `role` | `Role`（enum） | — | — |
| Agent | `providers` | `list[ProviderConfig]` | 1 件以上、`provider_kind` 重複なし、`is_default == True` は 1 件のみ | ProviderConfig VO |
| Agent | `skills` | `list[SkillRef]` | 0 件以上、`skill_id` 重複なし、上限 20 件 | SkillRef VO |
| Agent | `archived` | `bool` | デフォルト False | — |
| Persona（VO、frozen） | `display_name` | `str` | 1〜40 文字 | — |
| Persona | `archetype` | `str` | 0〜80 文字（例: "イーロン・マスク風 CEO"）| — |
| Persona | `prompt_body` | `str` | 0〜10000 文字、Markdown | — |
| ProviderConfig（VO、frozen） | `provider_kind` | `ProviderKind`（enum） | — | — |
| ProviderConfig | `model` | `str` | 1〜80 文字（例: "sonnet" / "gpt-5-codex"） | — |
| ProviderConfig | `is_default` | `bool` | — | — |
| SkillRef（VO、frozen） | `skill_id` | `SkillId`（UUID） | 不変 | — |
| SkillRef | `name` | `str` | 1〜80 文字 | — |
| SkillRef | `path` | `str` | 1〜500 文字、相対パス | — |

## ユーザー向けメッセージ一覧

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|----|------|----------------|---------|
| MSG-AG-001 | エラー（境界値） | Agent name は 1〜40 文字 | name 長違反 |
| MSG-AG-002 | エラー（必須） | Agent は providers を 1 件以上持つ必要がある | providers 空 |
| MSG-AG-003 | エラー（不変） | providers の is_default は 1 件のみ可能 | 0 件または 2 件以上 |
| MSG-AG-004 | エラー（重複） | provider_kind が重複している | 同一 ProviderKind 複数登録 |
| MSG-AG-005 | エラー（境界値） | Persona.prompt_body は 10000 文字以内 | prompt_body 長違反 |
| MSG-AG-006 | エラー（参照不整合） | provider_kind {kind} は登録されていない | `set_default_provider` |
| MSG-AG-007 | エラー（重複） | skill_id {id} はすでに追加済み | `add_skill` |
| MSG-AG-008 | エラー（参照不整合） | skill_id {id} は Agent に登録されていない | `remove_skill` |
| MSG-AG-009 | エラー（path traversal） | SkillRef.path 検証失敗（H1〜H10 のいずれか） | `SkillRef` 構築時、§確定 H |
| MSG-AG-010 | エラー（境界値） | Persona.archetype は 0〜80 文字 | archetype 長違反 |
| MSG-AG-011 | エラー（境界値） | Persona.display_name は 1〜40 文字 | display_name 長違反 |
| MSG-AG-012 | エラー（未実装プロバイダ） | provider_kind が MVP で未実装 | `AgentService.hire()` で `BAKUFU_IMPLEMENTED_PROVIDERS` に含まれない provider_kind、§確定 I |

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
