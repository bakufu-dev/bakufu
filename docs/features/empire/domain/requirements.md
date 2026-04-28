# 要件定義書

> feature: `empire`
> 関連: [feature-spec.md](../feature-spec.md) / [`docs/design/domain-model/aggregates.md`](../../../design/domain-model/aggregates.md) §Empire

## 機能要件

### REQ-EM-001: Empire 構築

| 項目 | 内容 |
|------|------|
| 入力 | `id: EmpireId`（UUIDv4）、`name: str`（1〜80 文字） |
| 処理 | 入力（id / name）を業務ルール R1-1（[`feature-spec.md §7`](../feature-spec.md)）に照らして検査 → 通過時のみ Empire を新規構築（rooms / agents は空の状態で構築） |
| 出力 | `Empire` インスタンス（rooms / agents が空の状態） |
| エラー時 | 業務ルール R1-1 違反（name 範囲外）で `EmpireInvariantViolation` を raise（MSG-EM-001） |

### REQ-EM-002: Agent 採用

| 項目 | 内容 |
|------|------|
| 入力 | `agent_ref: AgentRef`（`agent_id`, `name`, `role` を含む VO） |
| 処理 | 既採用一覧と照らして `agent_id` の重複（業務ルール R1-2）および容量上限（業務ルール R1-6）を検査 → 通過時のみ採用（既採用一覧に追加した新 Empire を返す）。実装方針は [`basic-design.md §処理フロー`](basic-design.md) / [`detailed-design.md §確定 A`](detailed-design.md) |
| 出力 | `agent_ref.agent_id`（追加された Agent の ID） + 更新された Empire（呼び出し側が受け取る） |
| エラー時 | 業務ルール R1-2 違反（`agent_id` 重複）または R1-6 違反（容量超過）で `EmpireInvariantViolation`（MSG-EM-002 / MSG-EM-005）を raise。失敗時、元の Empire は変化しない（pre-validate 方式の保証） |

### REQ-EM-003: Room 設立

| 項目 | 内容 |
|------|------|
| 入力 | `room_ref: RoomRef`（`room_id`, `name`, `archived=False` で初期化済み） |
| 処理 | 既設立一覧と照らして `room_id` の重複(業務ルール R1-3)および容量上限(業務ルール R1-6)を検査 → 通過時のみ設立(既設立一覧に追加した新 Empire を返す) |
| 出力 | `room_ref.room_id` + 更新された Empire |
| エラー時 | 業務ルール R1-3 違反（`room_id` 重複）または R1-6 違反（容量超過）で `EmpireInvariantViolation`（MSG-EM-003 / MSG-EM-005）を raise。失敗時、元の Empire は変化しない |

### REQ-EM-004: Room アーカイブ

| 項目 | 内容 |
|------|------|
| 入力 | `room_id: RoomId` |
| 処理 | 既設立一覧から該当する Room を検索 → 見つかれば archived フラグを立てた状態に置換した新 Empire を返す（業務ルール R1-4 により物理削除はしない、履歴保持）。見つからなければ拒否 |
| 出力 | 更新された Empire |
| エラー時 | `room_id` が既設立一覧に存在しない場合 `EmpireInvariantViolation`（MSG-EM-004）を raise。失敗時、元の Empire は変化しない |

### REQ-EM-005: 不変条件検査

| 項目 | 内容 |
|------|------|
| 入力 | Empire インスタンス（コンストラクタ末尾 / 状態変更ふるまい末尾で自動呼び出し） |
| 処理 | 以下を検査: ① name 範囲（業務ルール R1-1）② `agent_id` の重複なし（R1-2）③ `room_id` の重複なし（R1-3）④ 採用済み一覧 / 設立済み一覧の容量上限（R1-6） |
| 出力 | None（検査通過） |
| エラー時 | いずれか違反で `EmpireInvariantViolation` を raise。違反種別は `kind` フィールドに格納（詳細は [`detailed-design.md §クラス設計（詳細）`](detailed-design.md)） |

## 画面・CLI 仕様

### CLI レシピ / コマンド

該当なし — 理由: 本 feature は domain 層のみ実装する。Admin CLI の `bakufu admin ...` コマンド群は `feature/admin-cli` で扱う。

### Web UI 画面

該当なし — 理由: HTTP API 経由の UI は `feature/http-api` および各 feature ごとの UI Issue で扱う。本 feature は HTTP API レイヤを持たない。

## API 仕様

該当なし — 理由: 本 feature は domain 層のみ実装する。HTTP API は `feature/http-api` で扱う。

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| 該当なし | — | — | — | — |

## データモデル

凍結済み設計（[`docs/design/domain-model/aggregates.md`](../../../design/domain-model/aggregates.md) §Empire）に従う。本 feature で確定する追加・変更は以下の通り。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| Empire（Aggregate Root） | `id` | `EmpireId`（UUID） | 不変 | — |
| Empire | `name` | `str` | 1〜80 文字 | — |
| Empire | `rooms` | `list[RoomRef]` | 同一 `room_id` の重複なし | RoomRef VO |
| Empire | `agents` | `list[AgentRef]` | 同一 `agent_id` の重複なし | AgentRef VO |
| RoomRef（VO、frozen） | `room_id` | `RoomId`（UUID） | 不変 | Room Aggregate（参照） |
| RoomRef | `name` | `str` | 1〜80 文字（Room の name と同一規格） | — |
| RoomRef | `archived` | `bool` | デフォルト False | — |
| AgentRef（VO、frozen） | `agent_id` | `AgentId`（UUID） | 不変 | Agent Aggregate（参照） |
| AgentRef | `name` | `str` | 1〜40 文字（Agent の name と同一規格） | — |
| AgentRef | `role` | `Role` | 列挙型 | — |

`EmpireId` / `RoomId` / `AgentId` / `Role` は `domain/value_objects.py` 既存定義（[`domain-model/value-objects.md`](../../../design/domain-model/value-objects.md)）を参照。

## ユーザー向けメッセージ一覧

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|----|------|----------------|---------|
| MSG-EM-001 | エラー（境界値） | Empire name は 1〜80 文字 | `name` が長さ違反 |
| MSG-EM-002 | エラー（重複） | Agent {name} はすでに採用済み | `hire_agent` で `agent_id` 重複 |
| MSG-EM-003 | エラー（重複） | Room {name} はすでに設立済み | `establish_room` で `room_id` 重複 |
| MSG-EM-004 | エラー（参照エラー） | Room {room_id} が Empire 内に存在しない | `archive_room` で未登録 ID |
| MSG-EM-005 | エラー（一般） | Empire 不変条件違反: {detail} | 上記以外の不変条件違反 |

各メッセージの確定文言は [`detailed-design.md`](detailed-design.md) §MSG 確定文言表 で凍結する。

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | `pydantic` v2 | `pyproject.toml` | uv | 既存（[`tech-stack.md`](../../../design/tech-stack.md)）|
| Python 依存 | `pyright` (strict) | `pyproject.toml` dev | uv tool | 既存 |
| Python 依存 | `ruff` | 同上 | uv tool | 既存 |
| Python 依存 | `pytest` / `pytest-cov` | `pyproject.toml` dev | uv | 既存 |
| Node 依存 | 該当なし | — | — | 本 feature はバックエンド単独 |
| 外部サービス | 該当なし | — | — | domain 層のため外部通信なし |
