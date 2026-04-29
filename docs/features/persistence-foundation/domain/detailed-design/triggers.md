# 詳細設計補章: TypeDecorator 配線 + SQLite トリガ

> 親: [`../detailed-design.md`](../detailed-design.md)。本書は永続化前マスキングの強制ゲートウェイ化（確定 B、TypeDecorator `process_bind_param`）と `audit_log` 不変性の物理保証（確定 C、SQLite トリガ）を凍結する。

## 確定 B: SQLAlchemy TypeDecorator の登録方式（[`../feature-spec.md`](../feature-spec.md) §確定 R1-D で event listener から反転却下）

`infrastructure/persistence/sqlite/base.py` に **`MaskedJSONEncoded`** / **`MaskedText`** の 2 TypeDecorator を定義し、各 table の masking 対象カラムで `mapped_column(MaskedJSONEncoded, ...)` / `mapped_column(MaskedText, ...)` として宣言する。SQLAlchemy が bind parameter 解決時に内部の `process_bind_param` フックを発火し、`MaskingGateway.mask_in()` / `mask()` を呼び出して masking 後の値を返す。

### 採用根拠（実装段階の技術検証で反転）

旧設計の `event.listens_for(TableClass, 'before_insert')` / `'before_update'` 方式は「raw SQL 経路でも listener が走る」想定だったが、PR #23 BUG-PF-001 で**SQLAlchemy 2.x の Core `insert(table).values({...})` の inline values は ORM mapper を経由しないため `before_insert` listener が発火しない**ことが判明（TC-IT-PF-020 旧 xfail strict=True）。raw SQL 経路で生 secret が永続化される脱出経路が残るため、TypeDecorator `process_bind_param` 方式に反転（リーナス commit `4b882bf`、TC-IT-PF-020 PASSED）。詳細経緯は [`../feature-spec.md`](../feature-spec.md) §確定 R1-D。

### `process_bind_param` の発火経路（Core / ORM 両対応）

| 永続化経路 | 発火 |
|----|----|
| ORM `session.add(row)` → flush | ✓ `process_bind_param` 発火 |
| ORM `session.execute(insert(model).values(model_obj))` | ✓ |
| Core `session.execute(insert(table).values({"col": value}))` | ✓ — 旧 listener 方式は不発火、本方式は捕捉 |
| Core `session.execute(text("INSERT ..."))` + bind params | ✓ |

raw SQL（plain `text()` クエリ）でも bind parameter 経由なら `process_bind_param` が発火する。bind を経由しない手書き SQL リテラル（`text("INSERT INTO ... VALUES ('secret')")` 等）は対象外だが、これは SQL injection 脆弱性そのものとして別途禁止される（[`../../../design/tech-stack.md`](../../../design/tech-stack.md) §ORM 確定方針: raw SQL 禁止、SQLAlchemy 経由のみ）。

### 「属性追加時の漏れ」物理保証（CI 三層防衛）

TypeDecorator 採用の唯一のリスク（カラム宣言時に `Masked*` 型指定忘れ）を以下 3 層で物理保証:

1. **CI grep guard** (`scripts/ci/check_masking_columns.sh`): [`../../../design/domain-model/storage.md`](../../../design/domain-model/storage.md) §逆引き表 のカラム名を grep し、宣言行に `MaskedJSONEncoded` か `MaskedText` が含まれることを strict 検証
2. **アーキテクチャテスト** (`backend/tests/architecture/test_masking_columns.py`): SQLAlchemy metadata から逆引き表のカラムを抽出し、`column.type.__class__` が `MaskedJSONEncoded` / `MaskedText` であることを assert
3. **コードレビュー観点**: 新規 Aggregate Repository PR は逆引き表に行を追加 + masking 対象カラムの `Masked*` 指定を必須とするレビュー観点（[`../../../design/domain-model/storage.md`](../../../design/domain-model/storage.md) §逆引き表 §運用ルール）

これにより event listener 方式と同等以上の漏れ防止を担保しつつ、Core SQL 経路の物理保証を獲得する。

### TypeDecorator 配置と pyright strict 整合

| 名前 | 配置 | base 型 | 適用先（本 PR） |
|----|----|----|----|
| `MaskedJSONEncoded` | `infrastructure/persistence/sqlite/base.py` | `JSONEncoded` を拡張 | `domain_event_outbox.payload_json` / `audit_log.args_json` |
| `MaskedText` | 同上 | `Text` を拡張 | `domain_event_outbox.last_error` / `audit_log.error_text` / `bakufu_pid_registry.cmd` |

`process_bind_param` の override は `# pyright: ignore[reportIncompatibleMethodOverride]` を付与（SQLAlchemy `TypeDecorator` の type stub が広めに型付けされているため、bakufu 側で str / dict 限定にする）。

### テスト容易性

`MaskedJSONEncoded.process_bind_param(value, dialect)` を単独テストできる（SQLAlchemy session を介さず、直接呼んで masking 適用結果を検証可能）。Core / ORM 両経路の発火検証は `TC-IT-PF-020`（実 SQLite）で物理証明される。

## 確定 C: SQLite トリガ（`audit_log` 不変性）

Alembic 初回 revision で**2 つのトリガ**を発行する。SQL 本体は実装 PR で記述（本書は構造契約のみ）。

### トリガ 1: DELETE 拒否（`audit_log_no_delete`）

| 項目 | 値 |
|----|----|
| トリガ名 | `audit_log_no_delete` |
| タイミング | `BEFORE DELETE` |
| 対象テーブル | `audit_log` |
| 行スコープ | `FOR EACH ROW` |
| アクション | `RAISE(ABORT, 'audit_log is append-only')` |

### トリガ 2: UPDATE 制限（`audit_log_update_restricted`）

| 項目 | 値 |
|----|----|
| トリガ名 | `audit_log_update_restricted` |
| タイミング | `BEFORE UPDATE` |
| 対象テーブル | `audit_log` |
| 行スコープ | `FOR EACH ROW` |
| 条件 | `OLD.result IS NOT NULL`（`result` が既に値を持つ行への UPDATE） |
| アクション | `RAISE(ABORT, 'audit_log result is immutable once set')` |

### UPDATE 許容範囲

UPDATE は **`result` / `error_text` を NULL → 値**（実行完了時の 1 回のみ）の遷移だけ許可。すでに値が入っている行への UPDATE はトリガ 2 で拒否。

### 実装責務分離

- Alembic migration（`backend/alembic/versions/0001_init_*.py`）が SQL 本体を `op.execute("CREATE TRIGGER ...")` で発行
- 本書はトリガの**構造契約**（名前 / タイミング / 条件 / アクション）のみ凍結
- 結合テスト TC-IT-PF-005 / TC-IT-PF-015 が両トリガの動作を実 SQLite で検証

### トリガ自身の保護

トリガ自身が `DROP TRIGGER` / `sqlite_master` 直接 UPDATE で削除される経路は [`pragma.md`](pragma.md) §確定 D-1 の `defensive=ON` / `writable_schema=OFF` / `trusted_schema=OFF` で物理的に塞ぐ（Schneier 重大 2 対応、Defense in Depth）。
