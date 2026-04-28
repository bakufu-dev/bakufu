# 要件定義書

> feature: `room`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Room

## 機能要件

### REQ-RM-001: Room 構築

| 項目 | 内容 |
|------|------|
| 入力 | `id: RoomId` / `name: str` / `description: str` / `workflow_id: WorkflowId` / `members: list[AgentMembership]` / `prompt_kit: PromptKit` / `archived: bool`（既定 False） |
| 処理 | Pydantic 型バリデーション → `model_validator(mode='after')` で不変条件検査（`name` 1〜80 文字 / `description` 0〜500 文字 / `(agent_id, role)` 重複なし / `len(members) <= 50`）。すべて NFC + strip 適用後の長さで判定 |
| 出力 | valid な `Room` インスタンス（frozen） |
| エラー時 | `RoomInvariantViolation` を raise。`message` は MSG-RM-001/002/003/004（2 行構造 — `[FAIL] ...` + `Next: ...`、§確定 I）、`kind` は `name_range` / `description_too_long` / `member_duplicate` / `capacity_exceeded` のいずれか。`prompt_kit` 引数の長さ違反は **VO 構築段階で `pydantic.ValidationError`**（MSG-RM-007）として Room 構築前に raise 済み |

### REQ-RM-002: メンバー追加

| 項目 | 内容 |
|------|------|
| 入力 | `agent_id: AgentId` / `role: Role` / `joined_at: datetime`（UTC） |
| 処理 | 現 `members` に新 `AgentMembership` を append した dict を構築 → `Room.model_validate(updated_dict)` で再構築 → `model_validator` 走行 → 不変条件通過時のみ新 Room を返す |
| 出力 | 新 `Room` インスタンス（pre-validate 方式により元 Room は変化しない） |
| エラー時 | `RoomInvariantViolation`。`kind`: `member_duplicate` / `capacity_exceeded` / `room_archived` のいずれか。元 Room は変更されない |

### REQ-RM-003: メンバー削除

| 項目 | 内容 |
|------|------|
| 入力 | `agent_id: AgentId` / `role: Role` |
| 処理 | 現 `members` から `(agent_id, role)` ペアに一致する 1 件を削除した dict を構築 → `model_validate` で再構築 |
| 出力 | 新 `Room` インスタンス |
| エラー時 | `RoomInvariantViolation`。`kind`: `member_not_found` / `room_archived` のいずれか |

### REQ-RM-004: PromptKit 更新

| 項目 | 内容 |
|------|------|
| 入力 | `prompt_kit: PromptKit` |
| 処理 | `prompt_kit` を新 PromptKit に差し替えた dict を構築 → `model_validate` で再構築 |
| 出力 | 新 `Room` インスタンス |
| エラー時 | `RoomInvariantViolation(kind='room_archived')` のみ。PromptKit 自体の検査は VO 構築時に完了済み（`prefix_markdown` 0〜10000 文字） |

### REQ-RM-005: アーカイブ

| 項目 | 内容 |
|------|------|
| 入力 | なし（self） |
| 処理 | `_rebuild_with_state` 経由で `archived = True` の dict を構築 → `model_validate` で再構築。状態に依らず実行（既に `archived == True` でも新インスタンス返却、エラーにしない） |
| 出力 | 新 `Room` インスタンス（`archived == True`） |
| エラー時 | 通常経路では発生しない（不変条件は archive 後も保持される） |

### REQ-RM-006: 不変条件検査

| 項目 | 内容 |
|------|------|
| 入力 | Room の現状属性 |
| 処理 | `_validate_name_range` / `_validate_description_length` / `_validate_member_unique` / `_validate_member_capacity` を順次実行（命名対称性: empire / workflow / agent と並ぶ `_validate_*` helper） |
| 出力 | 違反なしなら return（None）、違反時は `RoomInvariantViolation` を raise |
| エラー時 | `RoomInvariantViolation` 単一例外。`kind` で違反種別を識別 |

## 画面・CLI 仕様

### CLI レシピ / コマンド

該当なし — 理由: 本 feature は domain 層のみ。Admin CLI は `feature/admin-cli` で扱う。

| コマンド | 概要 |
|---------|------|
| 該当なし | — |

### Web UI 画面

該当なし — 理由: UI は `feature/room-ui` で扱う。

| 画面ID | 画面名 | 主要操作 |
|-------|-------|---------|
| 該当なし | — | — |

## API 仕様

該当なし — 理由: API は `feature/http-api` で扱う。本 feature は domain 層のみ。

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| 該当なし | — | — | — | — |

## データモデル

`docs/design/domain-model/aggregates.md` §Room の凍結済み定義に従う。本 feature では `PromptKit` VO の属性確定（[`value-objects.md`](../../design/domain-model/value-objects.md) に追記）を行う。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| Room | `id` | `RoomId` | 不変、UUIDv4 | Aggregate Root |
| Room | `name` | `str` | 1〜80 文字（NFC + strip 後）、Empire 内一意（application 層） | — |
| Room | `description` | `str` | 0〜500 文字（NFC + strip 後） | — |
| Room | `workflow_id` | `WorkflowId` | 既存 Workflow を指す（参照整合性は application 層） | Workflow への参照 |
| Room | `members` | `list[AgentMembership]` | `(agent_id, role)` 重複なし、`len <= 50` | — |
| Room | `prompt_kit` | `PromptKit` | VO | composition |
| Room | `archived` | `bool` | 既定 False、terminal | — |
| PromptKit | `prefix_markdown` | `str` | 0〜10000 文字（NFC のみ、strip しない） | Room への composition |
| AgentMembership | `agent_id` | `AgentId` | 既存 VO（再利用） | — |
| AgentMembership | `role` | `Role` | 既存 enum（再利用） | — |
| AgentMembership | `joined_at` | `datetime` | UTC | — |

## ユーザー向けメッセージ一覧

全 MSG は **2 行構造**を採用する（§確定 I「フィードバック原則」、確定文言は detailed-design.md §MSG 確定文言表 で凍結）:

- 1 行目: `[FAIL] <failure summary>` — 何が失敗したか
- 2 行目: `Next: <action>` — 次に何をすべきか

「Next:」必須は test-design.md の TC-UT-RM-NNN で `assert "Next:" in str(exc)` により CI 物理保証する。

| ID | 種別 | 例外型 | kind | 表示条件 |
|----|------|------|------|---------|
| MSG-RM-001 | エラー | `RoomInvariantViolation` | `name_range` | name の NFC + strip 後の length が 0 または 81 以上 |
| MSG-RM-002 | エラー | `RoomInvariantViolation` | `description_too_long` | description の NFC + strip 後の length が 501 以上 |
| MSG-RM-003 | エラー | `RoomInvariantViolation` | `member_duplicate` | members 内に同一 `(agent_id, role)` ペアが 2 件以上 |
| MSG-RM-004 | エラー | `RoomInvariantViolation` | `capacity_exceeded` | `len(members) > 50` |
| MSG-RM-005 | エラー | `RoomInvariantViolation` | `member_not_found` | `remove_member` で不在のペアを指定 |
| MSG-RM-006 | エラー | `RoomInvariantViolation` | `room_archived` | `archived == True` の Room に `add_member` / `remove_member` / `update_prompt_kit` を実行 |
| MSG-RM-007 | エラー | `pydantic.ValidationError`（`PromptKit` VO 経由） | — | NFC 後の length が 10001 以上（VO 構築時に raise、Room ふるまい呼び出し前） |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | Pydantic v2.x | pyproject.toml（既存） | uv | 既存 |
| Python 依存 | unicodedata（標準ライブラリ） | — | — | NFC 正規化 |
| ドメイン | `WorkflowId` | `domain/value_objects.py` | 内部 import | 既存 |
| ドメイン | `AgentId` / `Role` / `AgentMembership` | `domain/value_objects.py` | 内部 import | 既存 |
| ドメイン | `mask_discord_webhook` / `mask_discord_webhook_in` | `domain/exceptions.py`（agent / workflow と共有） | 内部 import | 既存 |
| 外部サービス | 該当なし | — | — | domain 層のため外部通信なし |
