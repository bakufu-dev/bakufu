# 詳細設計補章: SQLAlchemy event listener + SQLite トリガ

> 親: [`../detailed-design.md`](../detailed-design.md)。本書は永続化前マスキングの強制ゲートウェイ化（確定 B）と `audit_log` 不変性の物理保証（確定 C）を凍結する。

## 確定 B: SQLAlchemy event listener の登録方式

table モジュール内で `event.listens_for(TableClass, 'before_insert')` / `'before_update'` をデコレータとして登録する。listener 関数は table モジュールの module-level に定義し、外部から差し替え不可（テスト時は `event.remove()` で削除可）。

理由:

- table 定義と listener が同一ファイルにあり、属性追加時に listener 内のフィールドリストを更新する責務が明確
- SQLAlchemy の event API は import 時に listener が登録される（lazy import を避ける）
- pyright strict で listener の引数型（`Mapper`, `Connection`, `Target`）を明示

raw SQL 経路（`session.execute(insert(table).values(...))` 等）でも listener は走るため、ORM mapper を経由しない経路でも masking が適用される（多層防御）。これが TypeDecorator 方式に対する優位性で、属性追加時の漏れを物理排除する（[`../requirements-analysis.md`](../requirements-analysis.md) §確定 R1-D 参照）。

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
