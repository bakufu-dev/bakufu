# DB マイグレーション方針（凍結中、TODO 集約）

> **Status**: TODO（M5+ で着手予定）。本ファイルは **後続 PR で受ける TODO の単一の真実源**。
> 本ファイルが存在することで「設計書中の申し送りが行き場を失わず、必ずここに集約される」契約が物理的に成立する。

## 位置づけ

- bakufu MVP（v0.1.0）は **SQLite 単一**を前提に M2 永続化基盤（PR #23）が凍結された
- M5 以降の Phase 2 で **PostgreSQL 移行**を検討する（MVP の単一プロセス前提を破る並列実行 / マルチテナント / WAL より上の DB 監視等が必要になった時点で起票）
- 本ファイルは **PR でも空ファイルとしてコミットしておき**、各設計書の「申し送り」セクションが本ファイルへ向けて TODO を集約する受け皿となる

## TODO 集約

各 TODO は **「どの設計書のどの §確定 から流れてきたか」** を必ず明示し、後続 PR が逆引きできる構造とする。本ファイルへの追記は対応する設計書の §確定 / §申し送り を更新する PR と**同一 PR**で行う（片肺禁止）。

### TODO-MIG-001: workflow-repository §確定 J — `Workflow.entry_stage_id` の DB FK 対応

| 項目 | 内容 |
|---|---|
| 流入元 | [`docs/features/workflow-repository/detailed-design.md`](../features/workflow-repository/detailed-design.md) §確定 J |
| 凍結内容 | MVP（SQLite）では `workflows.entry_stage_id` に DB レベル FK を**張らない**。Aggregate 不変条件（`Workflow` 構築時の `dag_validators._validate_entry_stage_in_stages`、workflow #16 凍結）で守る |
| Postgres 移行時の選択肢 | **(i) FK + `DEFERRABLE INITIALLY DEFERRED` で Tx 末端で FK 検査**（Postgres standard、最も安全） / **(ii) MVP と同じく FK 宣言なし、Aggregate 不変条件のみで担保**（M2 SQLite 段階の凍結を継続） |
| 起票時に確定すべき事項 | (a) (i) / (ii) のどちらを採用するか / (b) `workflow_transitions.from_stage_id` / `to_stage_id` も同方針か（同様に循環参照回避で MVP は FK なし、移行時に再議論） / (c) Alembic chain で SQLite → Postgres の portability をどう担保するか（dialect 依存の DDL 分岐） |
| 担当 PR（予定） | M5+ 起票予定。本ファイルが受け皿として存在することで、ユーザーが「設計書のどこに書かれていたか」を逆引きする経路を保証する |

### TODO-MIG-002〜（後続 PR で追記）

各 Repository feature / domain feature で「Postgres / 他 DB 移行時に再議論する」内容が出た場合、本リストに追記する責務を持つ。フォーマットは TODO-MIG-001 を写経する。

## 受け皿としての位置づけ（本ファイルが空ファイル + TODO 集約である意味）

| パターン | 本ファイル不在 | **本ファイル存在（採用）** |
|---|---|---|
| 設計書の申し送りが「将来 PR で対応」と書いてある | 「将来 PR」がどこを指すか不明、追跡不能 | 本ファイルに集約、起票時に逆引き可能 |
| Postgres 移行時に「設計書のどこに方針が書かれていたか」を探す | 全 feature の設計書を grep して探す | 本ファイルの TODO リストから流入元 §確定 を 1 hop で逆引き |
| 移行 PR が複数回に分かれる | 各 PR の整合性チェックが個別判断になる | 本ファイルが SoT なので各 PR は本ファイル + 該当設計書を同時更新 |

## 着手ガイド（M5+ 起票時の手順）

1. 本ファイルの TODO リストを総ざらいし、影響範囲を見積もる
2. `docs/architecture/migration-plan.md` を本ファイルとして拡張（PoC / 段階的移行手順 / dual-write 期間 / cutover）
3. 各 TODO に対し、流入元の設計書（`docs/features/{feature-name}/detailed-design.md` §確定 X）を**同一 PR で更新**して RESOLVED 化
4. Alembic revision を SQLite / Postgres dialect 分岐 or Postgres-only branch で発行
5. CI で SQLite + Postgres 両方の test suite を走らせる経路を追加（本 ファイル + tech-stack.md と同期）

## 出典・参考

- [PostgreSQL — `DEFERRABLE` constraint](https://www.postgresql.org/docs/current/sql-set-constraints.html) — TODO-MIG-001 (i) の根拠
- [Alembic — Multiple Database Support](https://alembic.sqlalchemy.org/en/latest/branches.html) — dialect 分岐の根拠
- [`docs/features/workflow-repository/detailed-design.md`](../features/workflow-repository/detailed-design.md) §確定 J — TODO-MIG-001 の流入元
- [`docs/features/persistence-foundation/`](../features/persistence-foundation/) — M2 永続化基盤（SQLite 凍結）
- [`docs/architecture/tech-stack.md`](tech-stack.md) — DB 採用根拠（Phase 1 SQLite）
