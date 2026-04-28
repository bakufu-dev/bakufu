# 要件定義書

> feature: `directive-repository`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源** / [`docs/features/room-repository/`](../room-repository/) **直近テンプレート** / [`docs/features/directive/`](../directive/)

## 機能要件

### REQ-DRR-001: DirectiveRepository Protocol 定義

| 項目 | 内容 |
|------|------|
| 入力 | 該当なし（Protocol 定義） |
| 処理 | `application/ports/directive_repository.py` で `DirectiveRepository(Protocol)` を定義。**5 method**（empire-repo の 3 method + §確定 R1-D の `find_by_room` / `find_by_task_id`）: `find_by_id(directive_id: DirectiveId) -> Directive \| None` / `count() -> int` / `save(directive: Directive) -> None` / `find_by_room(room_id: RoomId) -> list[Directive]` / `find_by_task_id(task_id: TaskId) -> Directive \| None`。すべて `async def`、`@runtime_checkable` なし |
| 出力 | Protocol 定義。pyright strict で `SqliteDirectiveRepository` が満たすことを型レベル検証 |
| エラー時 | 該当なし |

### REQ-DRR-002: SqliteDirectiveRepository 実装

| 項目 | 内容 |
|------|------|
| 入力 | `AsyncSession`（コンストラクタ引数）、各 method の引数 |
| 処理 | `find_by_id`: `directives` SELECT → 不在なら None。存在すれば `_from_row()` で Directive 復元（子テーブルなし、flat な 1 行 SELECT）。`count`: `select(func.count()).select_from(DirectiveRow)` で SQL `COUNT(*)`。`save`: `directives` UPSERT のみ（子テーブルなし、1 テーブル 1 行の INSERT OR REPLACE / merge）。`find_by_room`: `SELECT * FROM directives WHERE target_room_id = :room_id ORDER BY created_at DESC` で DirectiveRow 一覧取得 → 各行を `_from_row()` で Directive に変換して返却。`find_by_task_id`: `SELECT id FROM directives WHERE task_id = :task_id LIMIT 1` で DirectiveId 取得 → `find_by_id` 委譲（§確定 R1-D 同パターン） |
| 出力 | `find_by_id` / `find_by_task_id`: `Directive \| None`、`count`: `int`、`save`: `None`、`find_by_room`: `list[Directive]`（空の場合 `[]`） |
| エラー時 | SQLAlchemy `IntegrityError`（FK RESTRICT 違反 / NOT NULL 違反等）/ `OperationalError` を上位伝播。Repository 内で明示的 `commit` / `rollback` はしない |

### REQ-DRR-003: Alembic 0006 revision

| 項目 | 内容 |
|------|------|
| 入力 | room-repo の 0005 revision（`down_revision="0005_room_aggregate"` で chain 一直線） |
| 処理 | `0006_directive_aggregate.py` で 1 テーブル追加: `directives`（id PK / **text MaskedText NOT NULL** / target_room_id UUIDStr FK → rooms.id ON DELETE CASCADE NOT NULL / created_at DateTime NOT NULL / task_id UUIDStr NULL）、INDEX(target_room_id, created_at) 非 UNIQUE を追加。**`directives.task_id` への FK は張らない**（tasks テーブル未存在 — §確定 R1-C BUG-EMR-001 パターン、§Known Issues に申し送り） |
| 出力 | 1 テーブル + INDEX + FK 1 件（directives.target_room_id → rooms.id CASCADE）が SQLite に存在。directives.task_id は nullable UUIDStr として存在（FK なし） |
| エラー時 | migration 失敗 → `BakufuMigrationError`、Bootstrap stage 3 で Fail Fast |

### REQ-DRR-004: CI 三層防衛の Directive 拡張（**正/負のチェック併用**、workflow-repo §確定 E パターン）

| 項目 | 内容 |
|------|------|
| 入力 | `scripts/ci/check_masking_columns.sh`（Layer 1）と `backend/tests/architecture/test_masking_columns.py`（Layer 2）|
| 処理 | (a) Layer 1 grep guard: `tables/directives.py` の `text` カラム宣言行に **`MaskedText` 必須**（正のチェック、directive §確定 G 実適用 grep 物理保証）。`tables/directives.py` の `text` 以外のカラムに `MaskedText` / `MaskedJSONEncoded` が登場しない（過剰マスキング防止、負のチェック）。(b) Layer 2 arch test: parametrize に Directive テーブル追加、`directives.text` の `column.type.__class__ is MaskedText` を assert |
| 出力 | CI が Directive テーブルで「`directives.text` は `MaskedText` 必須、その他は masking なし」を物理保証 |
| エラー時 | 後続 PR が誤って `directives.text` を `Text`（masking なし）に変更 → Layer 2 arch test で落下、PR ブロック |

### REQ-DRR-005: storage.md 逆引き表更新

| 項目 | 内容 |
|------|------|
| 入力 | `docs/architecture/domain-model/storage.md` §逆引き表（Room 行が最終行、Issue #33 で追加済み） |
| 処理 | §逆引き表に Directive 関連 2 行追加: (a) `directives.text: MaskedText`（directive §確定 G **実適用**、persistence-foundation #23 で hook 構造提供済みを本 PR で配線）、(b) `directives` 残カラム（`id` / `target_room_id` / `created_at` / `task_id`）は masking 対象なし |
| 出力 | storage.md §逆引き表が「Directive 関連の masking 対象は `directives.text` のみ、directive §確定 G 実適用済み」状態 |
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

本 Issue で導入する 1 テーブル + INDEX + FK 1 件（directives.target_room_id → rooms.id）。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `directives` | `id` | `UUIDStr` | PK, NOT NULL | DirectiveId |
| `directives` | `text` | **`MaskedText`** | NOT NULL | CEO directive 本文（directive §確定 G 実適用） |
| `directives` | `target_room_id` | `UUIDStr` | **FK → `rooms.id` ON DELETE CASCADE, NOT NULL** | 委譲先 Room（§確定 R1-B） |
| `directives` | `created_at` | `DateTime` | NOT NULL（タイムゾーン aware、UTC） | 発行時刻 |
| `directives` | `task_id` | `UUIDStr` | **NULL（FK は張らない — §確定 R1-C、BUG-EMR-001 パターン）** | 紐付け済み Task（task-repository PR で FK closure） |
| `directives` INDEX | `(target_room_id, created_at)` 非 UNIQUE | — | — | **§確定 R1-D**: `find_by_room` の Room スコープ検索 + created_at ソートに複合 INDEX |

**masking 対象カラム**: `directives.text` のみ（`MaskedText`、§確定 R1-E）。その他 4 カラムは masking 対象なし、CI 三層防衛で「対象なし」を明示登録。

##### `directives.task_id` に FK を張らない根拠

§確定 R1-C（BUG-EMR-001 パターン）: 0006 時点で `tasks` テーブルは未存在（task-repository は後続 PR）。empire_room_refs.room_id と同じ forward reference 問題であり、task-repository PR で `op.batch_alter_table('directives')` 経由で `task_id → tasks.id` FK を ON DELETE RESTRICT で追加することを申し送りとする。

## ユーザー向けメッセージ一覧

該当なし — 理由: Repository は内部 API、ユーザー向けメッセージは application 層 / HTTP API 層が定義する（directive feature §確定 / `DirectiveService` / MSG-DR-NNN 系で扱う）。

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|----|------|----------------|---------|
| 該当なし | — | — | — |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | SQLAlchemy 2.x / Alembic / aiosqlite | pyproject.toml | uv | 既存（M2 永続化基盤）|
| Python 依存 | typing.Protocol | 標準ライブラリ | — | Python 3.12 標準 |
| ドメイン | `Directive` / `DirectiveId` / `RoomId` / `TaskId` | `domain/directive/` / `domain/value_objects.py` | 内部 import | 既存（directive PR #24）|
| インフラ | `Base` / `UUIDStr` / `MaskedText` / `MaskingGateway` | `infrastructure/persistence/sqlite/base.py` / `infrastructure/security/masking.py` | 内部 import | 既存（M2 永続化基盤、persistence-foundation #23 で `MaskedText` の TypeDecorator + directive §確定 G hook 構造提供済み）|
| インフラ | `AsyncSession` / `async_sessionmaker` | `infrastructure/persistence/sqlite/session.py` | 内部 import | 既存 |
| 外部参照テーブル | `rooms` | Alembic 0005 で先行追加済み | — | 既存（room-repo PR #47 マージ済み）|
| 外部サービス | 該当なし | — | — | infrastructure 層、外部通信なし |
