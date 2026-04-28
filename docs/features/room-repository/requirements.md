# 要件定義書

> feature: `room-repository`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源** / [`docs/features/agent-repository/`](../agent-repository/) **3 件目テンプレート** / [`docs/features/room/`](../room/)

## 機能要件

### REQ-RR-001: RoomRepository Protocol 定義

| 項目 | 内容 |
|------|------|
| 入力 | 該当なし（Protocol 定義） |
| 処理 | `application/ports/room_repository.py` で `RoomRepository(Protocol)` を定義。**4 method**（empire-repo の 3 method + agent-repo §R1-C の `find_by_name`、§確定 R1-F）: `find_by_id(room_id: RoomId) -> Room \| None` / `count() -> int` / `save(room: Room, empire_id: EmpireId) -> None` / `find_by_name(empire_id: EmpireId, name: str) -> Room \| None`。すべて `async def`、`@runtime_checkable` なし |
| 出力 | Protocol 定義。pyright strict で SqliteRoomRepository が満たすことを型レベル検証 |
| エラー時 | 該当なし |

### REQ-RR-002: SqliteRoomRepository 実装

| 項目 | 内容 |
|------|------|
| 入力 | `AsyncSession`（コンストラクタ引数）、各 method の引数 |
| 処理 | `find_by_id`: `rooms` SELECT → 不在なら None。存在すれば `room_members` を `ORDER BY agent_id, role` で SELECT（§BUG-EMR-001 規約） → `_from_row()` で Room 復元。`count`: `select(func.count()).select_from(RoomRow)` で SQL `COUNT(*)`。`save`: §確定 R1-A の delete-then-insert（3 段階手順、empire-repo と同パターンで子テーブル数のみ縮小: rooms UPSERT + room_members DELETE/INSERT）。`find_by_name`: `SELECT id FROM rooms WHERE empire_id=:empire_id AND name=:name LIMIT 1` で RoomId 取得 → `find_by_id` 委譲（agent §確定 F 同パターン） |
| 出力 | `find_by_id` / `find_by_name`: `Room \| None`、`count`: `int`、`save`: `None` |
| エラー時 | SQLAlchemy `IntegrityError`（FK RESTRICT 違反 / UNIQUE(room_id, agent_id, role) 違反等）/ `OperationalError` を上位伝播。Repository 内で明示的 `commit` / `rollback` はしない |

### REQ-RR-003: Alembic 0005 revision

| 項目 | 内容 |
|------|------|
| 入力 | agent-repo の 0004 revision（`down_revision="0004_agent_aggregate"` で chain 一直線）|
| 処理 | `0005_room_aggregate.py` で 2 テーブル追加 + 既存テーブルへの FK closure: (a) `rooms`（id PK / empire_id FK → empires.id ON DELETE CASCADE / **workflow_id FK → workflows.id ON DELETE RESTRICT** / name String(80) / description String(500) / **prompt_kit_prefix_markdown Text MaskedText** / archived Boolean、UNIQUE 制約は張らない — name 一意は application 層責務。**INDEX(empire_id, name) 非 UNIQUE** を追加）、(b) `room_members`（room_id FK → rooms.id ON DELETE CASCADE / agent_id UUIDStr / role String(32) / joined_at DateTime / **UNIQUE(room_id, agent_id, role)**）、(c) **`empire_room_refs.room_id → rooms.id` FK closure を `op.batch_alter_table` で追加**（ON DELETE CASCADE、BUG-EMR-001 close） |
| 出力 | 2 テーブル + INDEX + UNIQUE + FK 3 件（rooms.empire_id / rooms.workflow_id / room_members.room_id）+ empire_room_refs.room_id FK closure が SQLite に存在 |
| エラー時 | migration 失敗 → `BakufuMigrationError`、Bootstrap stage 3 で Fail Fast |

### REQ-RR-004: CI 三層防衛の Room 拡張（**正/負のチェック併用**、workflow-repo §確定 E パターン）

| 項目 | 内容 |
|------|------|
| 入力 | `scripts/ci/check_masking_columns.sh`（Layer 1）と `backend/tests/architecture/test_masking_columns.py`（Layer 2）|
| 処理 | (a) Layer 1 grep guard: `tables/rooms.py` の `prompt_kit_prefix_markdown` カラム宣言行に **`MaskedText` 必須**（正のチェック、room §確定 G 実適用 grep 物理保証）。`tables/rooms.py` の `prompt_kit_prefix_markdown` 以外のカラムに `MaskedText` / `MaskedJSONEncoded` が登場しない（過剰マスキング防止）。`tables/room_members.py` 全体に `MaskedText` / `MaskedJSONEncoded` が登場しない（負のチェック）。(b) Layer 2 arch test: parametrize に Room 2 テーブル追加、`rooms.prompt_kit_prefix_markdown` の `column.type.__class__ is MaskedText` を assert |
| 出力 | CI が Room 2 テーブルで「`rooms.prompt_kit_prefix_markdown` は `MaskedText` 必須、その他は masking なし」を物理保証 |
| エラー時 | 後続 PR が誤って `prompt_kit_prefix_markdown` を `Text`（masking なし）に変更 → Layer 2 arch test で落下、PR ブロック |

### REQ-RR-005: storage.md 逆引き表更新

| 項目 | 内容 |
|------|------|
| 入力 | `docs/architecture/domain-model/storage.md` §逆引き表（既存 `PromptKit.prefix_markdown` 行は persistence-foundation #23 で「`feature/room-repository`（後続）」と表記） |
| 処理 | §逆引き表に Room 関連 2 行追加: (a) `rooms.prompt_kit_prefix_markdown: MaskedText`（room §確定 G **実適用**、persistence-foundation #23 で hook 構造提供済みを本 PR で配線）、(b) `rooms` 残カラム + `room_members` 全カラムは masking 対象なし。既存の `PromptKit.prefix_markdown` 行は本 PR で**実適用済み**を明示するよう更新 |
| 出力 | storage.md §逆引き表が「Room 関連の masking 対象は `rooms.prompt_kit_prefix_markdown` のみ、room §確定 G 実適用済み」状態 |
| エラー時 | 該当なし |

### REQ-RR-006: empire-repository BUG-EMR-001 close 同期

| 項目 | 内容 |
|------|------|
| 入力 | `docs/features/empire-repository/detailed-design.md` §Known Issues §BUG-EMR-001（既存 RESOLVED マーク済みだが「Repository に `ORDER BY` を追加」のみ closure、**FK 追加 closure は未完了**）、§`empire_room_refs` テーブル §Room テーブルへの FK を張らない理由（既存「`feature/room-repository` PR で migration で FK を追加する責務分離」）|
| 処理 | (a) §Known Issues §BUG-EMR-001 直下に「**FK closure also resolved in `feature/33-room-repository` Alembic 0005**」追記、(b) §`empire_room_refs` テーブル §Room テーブルへの FK を張らない理由 を「**FK closure 完了済み（0005_room_aggregate）**」と更新（既存記述は歴史的経緯として残す） |
| 出力 | empire-repository 設計書が真実源として「Room FK closure 完了」を反映 |
| エラー時 | 該当なし |

## 画面・CLI 仕様

### CLI レシピ / コマンド

該当なし — 理由: 本 feature は infrastructure 層（Repository 実装）。

| コマンド | 概要 |
|---------|------|
| 該当なし | — |

### Web UI 画面

該当なし — 理由: UI を持たない。

| 画面ID | 画面名 | 主要操作 |
|-------|-------|---------|
| 該当なし | — | — |

## API 仕様

該当なし — 理由: HTTP API は `feature/http-api` で扱う。

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| 該当なし | — | — | — | — |

## データモデル

本 Issue で導入する 2 テーブル + UNIQUE + INDEX + FK 3 件 + empire_room_refs FK closure。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `rooms` | `id` | `UUIDStr` | PK, NOT NULL | RoomId |
| `rooms` | `empire_id` | `UUIDStr` | FK → `empires.id` ON DELETE CASCADE, NOT NULL | 所属 Empire |
| `rooms` | `workflow_id` | `UUIDStr` | **FK → `workflows.id` ON DELETE RESTRICT, NOT NULL** | 採用 Workflow（§確定 R1-B） |
| `rooms` | `name` | `String(80)` | NOT NULL（**DB UNIQUE は張らない、application 層責務**） | 部屋名（Empire 内一意） |
| `rooms` | `description` | `String(500)` | NOT NULL DEFAULT '' | 用途説明 |
| `rooms` | `prompt_kit_prefix_markdown` | **`MaskedText`** | NOT NULL DEFAULT '' | PromptKit.prefix_markdown（room §確定 G 実適用） |
| `rooms` | `archived` | `Boolean` | NOT NULL DEFAULT FALSE | アーカイブ状態 |
| `rooms` INDEX | `(empire_id, name)` 非 UNIQUE | — | — | **§確定 R1-F**: find_by_name の Empire スコープ検索（左端プリフィックス）|
| `room_members` | `room_id` | `UUIDStr` | FK → `rooms.id` ON DELETE CASCADE, NOT NULL | 所属 Room |
| `room_members` | `agent_id` | `UUIDStr` | NOT NULL（FK は **意図的に張らない** — Agent は別 Aggregate、application 層 `RoomService.add_member` が `AgentRepository.find_by_id` で参照整合性検査） | Agent への参照 |
| `room_members` | `role` | `String(32)` | NOT NULL（Role enum）| ペアリング Role |
| `room_members` | `joined_at` | `DateTime` | NOT NULL（タイムゾーン aware、UTC）| 参加時刻 |
| `room_members` UNIQUE | `(room_id, agent_id, role)` | — | — | **§確定 R1-D 二重防衛** |
| `empire_room_refs.room_id` FK closure | — | — | FK → `rooms.id` ON DELETE CASCADE（**0005 で `op.batch_alter_table` 経由追加**） | **§確定 R1-C**、BUG-EMR-001 close |

**masking 対象カラム**: `rooms.prompt_kit_prefix_markdown` のみ（`MaskedText`、§確定 R1-E）。その他 11 カラムは masking 対象なし、CI 三層防衛で「対象なし」を明示登録。

##### `room_members.agent_id` に FK を張らない根拠

room §確定（[aggregates.md §Room](../../architecture/domain-model/aggregates.md) L36 / [room/detailed-design.md L66](../room/detailed-design.md)）で「`members[*].agent_id` が指す Agent の存在は application 層 `RoomService.add_member` が `AgentRepository.find_by_id` で確認」と application 層責務として凍結済み。DB FK を張ると application 層の MSG-RR-NNN を出す前に IntegrityError が raise されてユーザー voice が崩れる（agent §R1-B / 本 §R1-F INDEX 設計と同論理）。

加えて、Agent Aggregate は archived=True 状態でも row が残る（room §確定）。FK CASCADE は危険（archived agent がいる Room の members が勝手に削除される）、RESTRICT も Room 編成時の柔軟性を損なう。**FK を張らず application 層検査のみに統一**が正解。

## ユーザー向けメッセージ一覧

該当なし — 理由: Repository は内部 API、ユーザー向けメッセージは application 層 / HTTP API 層が定義する（room feature §確定 / `RoomService` / `EmpireService` の MSG-RM-NNN 系で扱う）。

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|----|------|----------------|---------|
| 該当なし | — | — | — |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | SQLAlchemy 2.x / Alembic / aiosqlite | pyproject.toml | uv | 既存（M2 永続化基盤）|
| Python 依存 | typing.Protocol | 標準ライブラリ | — | Python 3.12 標準 |
| ドメイン | `Room` / `RoomId` / `EmpireId` / `WorkflowId` / `AgentId` / `Role` / `PromptKit` / `AgentMembership` / `RoomInvariantViolation` | `domain/room/` / `domain/value_objects.py` / `domain/exceptions.py` | 内部 import | 既存（room PR #22）|
| インフラ | `Base` / `UUIDStr` / `MaskedText` / `MaskingGateway` | `infrastructure/persistence/sqlite/base.py` / `infrastructure/security/masking.py` | 内部 import | 既存（M2 永続化基盤、persistence-foundation #23 で `MaskedText` の TypeDecorator + room §確定 G hook 構造提供済み）|
| インフラ | `AsyncSession` / `async_sessionmaker` | `infrastructure/persistence/sqlite/session.py` | 内部 import | 既存 |
| 外部参照テーブル | `empires` / `workflows` / `empire_room_refs` | Alembic 0002 / 0003 / 0002 で先行追加済み | — | 既存（empire-repo / workflow-repo マージ済み）|
| 外部サービス | 該当なし | — | — | infrastructure 層、外部通信なし |
