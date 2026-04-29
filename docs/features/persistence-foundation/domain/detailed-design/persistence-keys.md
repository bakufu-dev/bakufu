# 詳細設計補章: データ構造（永続化キー）

> 親: [`../detailed-design.md`](../detailed-design.md)。本書は本 PR で永続化される 3 テーブル + 1 INDEX + 2 トリガと Alembic 初回 revision のキー構造を凍結する。

## `audit_log` テーブル

[`../feature-spec.md`](../feature-spec.md) §データモデル + [`triggers.md`](triggers.md) §確定 C のトリガを参照。

## `bakufu_pid_registry` テーブル

[`../feature-spec.md`](../feature-spec.md) §データモデル を参照。詳細手順は [`bootstrap.md`](bootstrap.md) §確定 E。

## `domain_event_outbox` テーブル

[`../feature-spec.md`](../feature-spec.md) §データモデル + [`masking.md`](masking.md) §確定 A のマスキング適用先 を参照。

## Alembic 初回 revision キー構造

revision id: `0001`（自動生成 hash でも可、固定 ID `0001_init_audit_pid_outbox` を推奨）

| 操作 | 対象 |
|----|----|
| `op.create_table('audit_log', ...)` | 7 カラム |
| `op.create_table('bakufu_pid_registry', ...)` | 6 カラム |
| `op.create_table('domain_event_outbox', ...)` | 11 カラム |
| `op.create_index('ix_outbox_status_next_attempt', 'domain_event_outbox', ['status', 'next_attempt_at'])` | INDEX |
| `op.execute("CREATE TRIGGER audit_log_no_delete ...")` | DELETE 拒否トリガ（[`triggers.md`](triggers.md) §トリガ 1） |
| `op.execute("CREATE TRIGGER audit_log_update_restricted ...")` | UPDATE 制限トリガ（[`triggers.md`](triggers.md) §トリガ 2） |

`downgrade()` は `op.drop_table` / `op.execute("DROP TRIGGER ...")` で逆順に実行（Phase 2 のロールバック耐性）。
