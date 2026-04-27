# 要件定義書

> feature: `directive`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/architecture/domain-model/aggregates.md`](../../architecture/domain-model/aggregates.md) §Directive

## 機能要件

### REQ-DR-001: Directive 構築

| 項目 | 内容 |
|------|------|
| 入力 | `id: DirectiveId` / `text: str` / `target_room_id: RoomId` / `created_at: datetime`（UTC、tz-aware）/ `task_id: TaskId \| None`（既定 None） |
| 処理 | Pydantic 型バリデーション → `model_validator(mode='after')` で不変条件検査（`text` 1〜10000 文字、NFC 正規化のみ・strip しない / `task_id` UUIDv4 形式 or None / `created_at` tz-aware） |
| 出力 | valid な `Directive` インスタンス（frozen） |
| エラー時 | `DirectiveInvariantViolation` を raise。`message` は MSG-DR-001/002（2 行構造、§確定 R1-E）、`kind` は `text_range` / `task_already_linked` のいずれか。型違反は `pydantic.ValidationError`（MSG-DR-003） |

### REQ-DR-002: Task 紐付け

| 項目 | 内容 |
|------|------|
| 入力 | `task_id: TaskId`（生成済み Task の id） |
| 処理 | 現状の `task_id` を確認 → None なら新 `task_id` を設定して dict 化 → `Directive.model_validate(updated_dict)` で再構築 → `model_validator` 走行 → 不変条件通過時のみ新 Directive を返す。既に紐付け済みなら `_validate_task_link_immutable` で Fail Fast |
| 出力 | 新 `Directive` インスタンス（pre-validate 方式により元 Directive は変化しない） |
| エラー時 | `DirectiveInvariantViolation(kind='task_already_linked')`。元 Directive は変更されない |

### REQ-DR-003: 不変条件検査

| 項目 | 内容 |
|------|------|
| 入力 | Directive の現状属性 |
| 処理 | `_validate_text_range`（NFC 後の length が 1〜10000）/ `_validate_task_link_immutable`（task_id 一意遷移）を順次実行。命名対称性: empire / workflow / agent / room と並ぶ `_validate_*` helper |
| 出力 | 違反なしなら return（None）、違反時は `DirectiveInvariantViolation` を raise |
| エラー時 | `DirectiveInvariantViolation` 単一例外。`kind` で違反種別を識別 |

## 画面・CLI 仕様

### CLI レシピ / コマンド

該当なし — 理由: 本 feature は domain 層のみ。Admin CLI は `feature/admin-cli` で扱う。CEO directive 発行 UI は `feature/chat-ui` 相当（Phase 2）で扱う。

| コマンド | 概要 |
|---------|------|
| 該当なし | — |

### Web UI 画面

該当なし — 理由: UI は `feature/chat-ui`（Phase 2）で扱う。

| 画面ID | 画面名 | 主要操作 |
|-------|-------|---------|
| 該当なし | — | — |

## API 仕様

該当なし — 理由: API は `feature/http-api` で扱う。本 feature は domain 層のみ。

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| 該当なし | — | — | — | — |

## データモデル

`docs/architecture/domain-model/aggregates.md` §Directive の凍結済み定義に従う。本 feature では新規 VO は追加しない（`DirectiveId` は既存）。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| Directive | `id` | `DirectiveId` | 不変、UUIDv4 | Aggregate Root |
| Directive | `text` | `str` | 1〜10000 文字（NFC 正規化のみ、strip しない） | — |
| Directive | `target_room_id` | `RoomId` | UUIDv4。既存 Room を指す（参照整合性は application 層） | Room への参照 |
| Directive | `created_at` | `datetime` | UTC、tz-aware | — |
| Directive | `task_id` | `TaskId \| None` | UUIDv4 or None。一意遷移（None → 有効 TaskId のみ可、再リンク禁止） | Task への参照 |

## ユーザー向けメッセージ一覧

全 MSG は **2 行構造**を採用する（§確定 R1-E「フィードバック原則」、確定文言は detailed-design.md §MSG 確定文言表 で凍結）:

- 1 行目: `[FAIL] <failure summary>` — 何が失敗したか
- 2 行目: `Next: <action>` — 次に何をすべきか

「Next:」必須は test-design.md の TC-UT-DR-NNN で `assert "Next:" in str(exc)` により CI 物理保証する。

| ID | 種別 | 例外型 | kind | 表示条件 |
|----|------|------|------|---------|
| MSG-DR-001 | エラー | `DirectiveInvariantViolation` | `text_range` | text の NFC 後 length が 0 または 10001 以上 |
| MSG-DR-002 | エラー | `DirectiveInvariantViolation` | `task_already_linked` | 既に `task_id is not None` の Directive に `link_task` を実行 |
| MSG-DR-003 | エラー | `pydantic.ValidationError` | — | 型違反（None 渡し / tz-naive datetime / 不正 UUID 等） |
| MSG-DR-004 | エラー | `RoomNotFoundError` | — | application 層 `DirectiveService.issue()` で `target_room_id` の Room が存在しない |
| MSG-DR-005 | エラー | `WorkflowNotFoundError` | — | DirectiveService.issue() で Room の workflow_id を解決できない |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | Pydantic v2.x | pyproject.toml（既存） | uv | 既存 |
| Python 依存 | unicodedata（標準ライブラリ） | — | — | NFC 正規化 |
| ドメイン | `DirectiveId` / `RoomId` / `TaskId` | `domain/value_objects.py` | 内部 import | 既存 |
| ドメイン | `mask_discord_webhook` / `mask_discord_webhook_in` | `domain/exceptions.py`（agent / workflow / room と共有） | 内部 import | 既存 |
| 外部サービス | 該当なし | — | — | domain 層のため外部通信なし |
