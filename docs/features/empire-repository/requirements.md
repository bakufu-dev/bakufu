# 要件定義書

> feature: `empire-repository`
> 関連: [requirements-analysis.md](requirements-analysis.md) / [`docs/features/persistence-foundation/`](../persistence-foundation/) / [`docs/features/empire/`](../empire/)

## 機能要件

### REQ-EMR-001: EmpireRepository Protocol 定義

| 項目 | 内容 |
|------|------|
| 入力 | 該当なし（Protocol 定義のため抽象） |
| 処理 | `application/ports/empire_repository.py` で `EmpireRepository(Protocol)` を定義。3 メソッド: `find_by_id(empire_id: EmpireId) -> Empire \| None` / `count() -> int` / `save(empire: Empire) -> None`。すべて `async def` |
| 出力 | Protocol 定義（`@runtime_checkable` なし）。pyright strict で SqliteEmpireRepository が Protocol を満たすことを型レベル検証 |
| エラー時 | 該当なし（Protocol は実行時例外を持たない） |

### REQ-EMR-002: SqliteEmpireRepository 実装

| 項目 | 内容 |
|------|------|
| 入力 | `AsyncSession`（コンストラクタ引数）、各メソッドに応じた引数（`empire_id` / `empire`） |
| 処理 | `find_by_id`: `empires` + `empire_room_refs` + `empire_agent_refs` を JOIN して取得 → `_from_row()` で Empire 復元。`count`: `SELECT COUNT(*) FROM empires`。`save`: §確定 R1-B の delete-then-insert 戦略（empires UPSERT → empire_room_refs DELETE+INSERT → empire_agent_refs DELETE+INSERT、すべて呼び出し側 service の同一 Tx 内で実行） |
| 出力 | `find_by_id`: `Empire \| None`、`count`: `int`、`save`: `None` |
| エラー時 | SQLAlchemy `IntegrityError`（FK 違反等）→ application 層に伝播。SQLite 接続切断 → `OperationalError` を上位伝播。`save` 中の Tx は呼び出し側 service が `async with session.begin():` で管理、Repository 内では明示的な commit / rollback はしない |

### REQ-EMR-003: Alembic 2nd revision

| 項目 | 内容 |
|------|------|
| 入力 | M2 永続化基盤（PR #23）の initial revision（`0001_init_audit_pid_outbox.py`）|
| 処理 | `0002_empire_aggregate.py` で 3 テーブル追加: (a) `empires`（id PK、name String(80) NOT NULL）、(b) `empire_room_refs`（empire_id FK → empires.id CASCADE、room_id UUIDStr、name String(80)、archived Boolean、UNIQUE(empire_id, room_id)）、(c) `empire_agent_refs`（empire_id FK → empires.id CASCADE、agent_id UUIDStr、name String(40)、role String(32)、UNIQUE(empire_id, agent_id)）|
| 出力 | 3 テーブル + 関連 INDEX が SQLite に存在する状態 |
| エラー時 | migration 失敗 → `BakufuMigrationError(MSG-PF-004)`、Bootstrap stage 3 で Fail Fast（M2 永続化基盤の規約） |

### REQ-EMR-004: CI 三層防衛の Empire 拡張

| 項目 | 内容 |
|------|------|
| 入力 | M2 永続化基盤の `scripts/ci/check_masking_columns.sh`（Layer 1）と `backend/tests/architecture/test_masking_columns.py`（Layer 2）|
| 処理 | (a) Layer 1 grep guard: 対象テーブルリストに `empires` / `empire_room_refs` / `empire_agent_refs` の 3 テーブルを **明示登録**し、masking 対象カラムが存在しないことを strict 検証。(b) Layer 2 arch test: parametrize に 3 テーブル追加、各カラムが `MaskedJSONEncoded` / `MaskedText` **でない**ことを assert |
| 出力 | CI が Empire 3 テーブルで「masking 対象なし」を物理保証する状態 |
| エラー時 | 後続 Repository PR が誤って `MaskedText` を Empire カラムに指定 → CI で Layer 2 arch test が落下、PR ブロック |

### REQ-EMR-005: storage.md 逆引き表更新

| 項目 | 内容 |
|------|------|
| 入力 | `docs/design/domain-model/storage.md` の §逆引き表（11 行、persistence-foundation で凍結済み）|
| 処理 | §逆引き表に「Empire 関連カラム: masking 対象なし」を明示する行を追加（後続 Repository PR が誤って `MaskedText` を指定しないテンプレート） |
| 出力 | storage.md §逆引き表に Empire 行が追加された状態（テキスト更新のみ）|
| エラー時 | 該当なし（ドキュメント更新） |

## 画面・CLI 仕様

### CLI レシピ / コマンド

該当なし — 理由: 本 feature は infrastructure 層（Repository 実装）。Admin CLI は `feature/admin-cli` で扱う。

| コマンド | 概要 |
|---------|------|
| 該当なし | — |

### Web UI 画面

該当なし — 理由: UI を持たない。

| 画面ID | 画面名 | 主要操作 |
|-------|-------|---------|
| 該当なし | — | — |

## API 仕様

該当なし — 理由: HTTP API は `feature/http-api` で扱う。本 PR は内部 API（Python module-level の Protocol / Class）のみ提供する。

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|-----|------|----------|----------|
| 該当なし | — | — | — | — |

## データモデル

本 Issue で導入する 3 テーブル + 関連 INDEX。

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `empires` | `id` | `UUIDStr` | PK, NOT NULL | EmpireId |
| `empires` | `name` | `String(80)` | NOT NULL | 表示名 |
| `empire_room_refs` | `empire_id` | `UUIDStr` | FK → `empires.id` ON DELETE CASCADE, NOT NULL | 所属 Empire |
| `empire_room_refs` | `room_id` | `UUIDStr` | NOT NULL | Room への参照 |
| `empire_room_refs` | `name` | `String(80)` | NOT NULL | RoomRef.name |
| `empire_room_refs` | `archived` | `Boolean` | NOT NULL DEFAULT FALSE | RoomRef.archived |
| `empire_room_refs` UNIQUE | `(empire_id, room_id)` | — | — | DB 制約で `RoomRef.room_id` 一意性を担保 |
| `empire_agent_refs` | `empire_id` | `UUIDStr` | FK → `empires.id` ON DELETE CASCADE, NOT NULL | 所属 Empire |
| `empire_agent_refs` | `agent_id` | `UUIDStr` | NOT NULL | Agent への参照 |
| `empire_agent_refs` | `name` | `String(40)` | NOT NULL | AgentRef.name |
| `empire_agent_refs` | `role` | `String(32)` | NOT NULL | AgentRef.role（enum string） |
| `empire_agent_refs` UNIQUE | `(empire_id, agent_id)` | — | — | DB 制約で `AgentRef.agent_id` 一意性を担保 |

**masking 対象カラム**: **なし**（storage.md §逆引き表で凍結、§確定 R1-E で CI 三層防衛が物理保証）。

## ユーザー向けメッセージ一覧

該当なし — 理由: Repository は内部 API のみ提供、ユーザー向けメッセージは application 層 / HTTP API 層が定義する。

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|----|------|----------------|---------|
| 該当なし | — | — | — |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| ランタイム | Python 3.12+ | pyproject.toml | uv | 既存 |
| Python 依存 | SQLAlchemy 2.x | pyproject.toml | uv | 既存（M2 永続化基盤で導入済み）|
| Python 依存 | Alembic | pyproject.toml | uv | 既存 |
| Python 依存 | typing.Protocol | 標準ライブラリ | — | Python 3.12 標準 |
| ドメイン | `Empire` / `EmpireId` / `RoomRef` / `AgentRef` | `domain/empire.py` / `domain/value_objects.py` | 内部 import | 既存（empire feature #8）|
| インフラ | `Base` / `UUIDStr` / `UTCDateTime` | `infrastructure/persistence/sqlite/base.py` | 内部 import | 既存（M2 永続化基盤）|
| インフラ | `AsyncSession` / `async_sessionmaker` | `infrastructure/persistence/sqlite/session.py` | 内部 import | 既存 |
| 外部サービス | 該当なし | — | — | infrastructure 層のため外部通信なし |
