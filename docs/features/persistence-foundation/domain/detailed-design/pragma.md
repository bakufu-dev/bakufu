# 詳細設計補章: PRAGMA + dual connection

> 親: [`../detailed-design.md`](../detailed-design.md)。本書は engine 接続時の PRAGMA SET 順序と application / migration の dual connection 設計を凍結する。Schneier 重大 2 対応。

## 確定 D: PRAGMA SET の順序と引き金（Schneier 重大 2 対応）

`audit_log` の DELETE / UPDATE 拒否トリガ（[`triggers.md`](triggers.md) §確定 C）は、**そのトリガ自身が DROP TRIGGER で削除可能**であれば防衛にならない。SQLite では `sqlite_master` を直接 UPDATE してトリガ定義を消す経路もある。これに対する Defense in Depth として PRAGMA リストに `defensive=ON` / `writable_schema=OFF` を追加し、**application 接続と migration 接続を分離**する。

### 確定 D-1: application 接続の PRAGMA リスト（毎接続 SET）

接続ごとに `event.listens_for(engine.sync_engine, 'connect')` で発火。順序固定:

| # | PRAGMA | 値 | 意図 |
|---|----|----|----|
| 1 | `journal_mode` | `WAL` | 同時読み書き性能、再起動時の WAL 自動チェックポイント。**他 PRAGMA より先**（他は WAL モード前提） |
| 2 | `foreign_keys` | `ON` | SQLite 既定 OFF。Aggregate 間の参照整合性を物理保証 |
| 3 | `busy_timeout` | `5000`（ms） | 同時アクセス時のロック待ち上限 |
| 4 | `synchronous` | `NORMAL` | WAL モードで安全。完全 fsync より高速 |
| 5 | `temp_store` | `MEMORY` | 一時テーブル / インデックスをメモリ保持 |
| 6 | `defensive` | `ON` | SQLite 3.31+。**runtime DDL（CREATE / DROP TRIGGER 等）を制限**し、`audit_log` トリガを DROP できない経路に置く |
| 7 | `writable_schema` | `OFF` | 既定 OFF だが**明示 SET**。runtime 中の `sqlite_master` 直接 UPDATE を阻止 |
| 8 | `trusted_schema` | `OFF` | SQLite 3.31+。スキーマ内の関数・VIEW などへの信頼を最小化 |

WAL モードはデータベースレベル永続化される（DB ファイルメタデータ）が、他は接続レベル。`foreign_keys` は SQLite 既定 OFF のため毎接続 SET 必須。

### 確定 D-2: Alembic migration 接続は別経路（dual connection）

`defensive=ON` 下では `CREATE TABLE` / `CREATE TRIGGER` 等の DDL も制限される（具体的な制限内容は SQLite version に依存）。Alembic は migration 適用時に DDL を発行する必要があるため、**migration 専用の engine** を分離する。

| 接続種別 | engine 生成関数 | PRAGMA defensive | PRAGMA writable_schema | 用途 |
|----|----|----|----|----|
| application 接続 | `create_engine()`（既定） | `ON` | `OFF` | Backend ランタイム中の全 SELECT / INSERT / UPDATE |
| migration 接続 | `create_migration_engine()`（限定使用） | `OFF` | `ON`（DDL 発行時のみ） | Alembic `upgrade` / `downgrade` のみ。Bootstrap stage 3 のみで使用 |

### 確定 D-3: migration engine の生存期間

`create_migration_engine()` は **Bootstrap stage 3 の `with` ブロック内のみ**で生存させる:

| 段階 | 操作 |
|----|----|
| stage 3 開始 | `create_migration_engine()` で migration 専用 engine を生成（`defensive=OFF`） |
| stage 3 中 | Alembic `upgrade head` を migration engine 経由で実行 |
| stage 3 終了 | migration engine を `dispose()` で破棄（接続 pool もクローズ） |
| stage 3 以降 | application engine（`defensive=ON`）のみが使われる |

これにより、Backend ランタイム中は `defensive=ON` の接続しか存在せず、攻撃者が runtime DDL でトリガを DROP する経路を物理的に塞ぐ。

### 確定 D-4: `defensive=ON` で技術的に migration ができない場合の代替

SQLAlchemy 2.x / aiosqlite の現行版で上記が技術的に困難な場合（PRAGMA `defensive` のサポート状況に依存）、以下のフォールバックを採用:

1. application engine も `defensive=OFF` で起動するが、PRAGMA `query_only=ON`（書き込み禁止モード）を**書き込み Tx 開始時のみ OFF にして再 ON**にする ─ 実装コスト高
2. または **threat-model.md §T2 に「DDL 経由のトリガ削除は Backend を別 OS ユーザーで動かし、DB ファイル 0600 で他ユーザーから DDL 経路を物理的に塞ぐ」と信頼境界を明記**（OS レベルの隔離に頼る）

実装 PR で SQLite version + aiosqlite 実機検証を行い、`defensive=ON` がサポートされていれば確定 D-1〜D-3 を採用、サポート不能なら (2) のフォールバック + threat-model 明記に切り替える。**いずれの場合も決定を threat-model.md §T2 に記録する**（信頼境界の透明性）。

### test-design.md でのカバレッジ

| TC | 検証内容 |
|----|----|
| TC-IT-PF-003 | PRAGMA 8 件すべてが application 接続で SET されていることを `PRAGMA <name>;` 取得で確認 |
| TC-IT-PF-003-A | application 接続から `DROP TRIGGER audit_log_no_delete` を試行 → SQLite が拒否 |
| TC-IT-PF-003-B | application 接続から `UPDATE sqlite_master SET ...` を試行 → 拒否 |
| TC-IT-PF-003-C | migration engine（stage 3）では DDL が成功する |
| TC-IT-PF-003-D | migration engine が stage 3 終了時に `dispose()` され、以降の DDL 発行経路が消えている |
