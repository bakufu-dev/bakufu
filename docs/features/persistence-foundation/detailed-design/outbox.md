# 詳細設計補章: Outbox Dispatcher 空 handler レジストリ Fail Loud

> 親: [`../detailed-design.md`](../detailed-design.md)。本書は空 handler レジストリ稼働時の WARN 設計（確定 K、Schneier 中等 3 対応）を凍結する。Outbox Dispatcher の polling 構造契約は [`modules.md`](modules.md) §Module dispatcher.py を参照。

## 確定 K: Outbox Dispatcher 空 handler レジストリ稼働時の WARN（Schneier 中等 3 対応）

本 PR では Handler 実装を登録しない（空レジストリ）。後続 PR が register するまでの空レジストリ稼働中、Outbox 行が累積する経路に対して **早期検出の WARN ログ**を組み込む。

### 空レジストリ検出ロジック（凍結）

| タイミング | 動作 |
|----|----|
| Bootstrap stage 6 起動完了直後 | `len(handler_registry) == 0` なら WARN 出力: `[WARN] Bootstrap stage 6/8: No event handlers registered. Outbox events will accumulate without dispatch. Register handlers via feature/{event-kind}-handler PRs before processing real events.` |
| Dispatcher polling サイクルごと | `polling SQL で取得した行数 > 0` AND `handler_registry が空` なら WARN（**1 サイクルにつき 1 回**、ログ・スパム防止）: `[WARN] Outbox has {n} pending events but handler_registry is empty.` |
| Outbox 滞留閾値 | `domain_event_outbox` の `status='PENDING'` 行数が **100 件超** で WARN（5 分に 1 回、`feature/admin-cli` の monitoring に通知）: `[WARN] Outbox PENDING count={n} > 100. Inspect with bakufu admin list-pending.` |

### 「dispatcher を本 PR で起動しない」案を採用しなかった理由

Schneier 中等 3 (C) の「本 PR では dispatcher を起動しない」案は最もシンプルだが、**Bootstrap 起動シーケンス 8 段階の順序を本 PR で凍結する目的に反する**。後続 PR が「初回 handler 登録時に Bootstrap が一部やり直される」という分岐を入れると、起動順序の単一性が崩れ、TC-IT-PF-012 系の試験性も失われる。

代わりに「dispatcher は起動するが、空レジストリは WARN で運用者に通知される」という Fail Loud 設計を採用。CEO が起動ログを見れば即座に気付ける。

### test-design.md でのカバレッジ

| TC | 検証内容 |
|----|----|
| TC-IT-PF-008-A | 空レジストリで Bootstrap 起動 → WARN ログ 1 件出力 |
| TC-IT-PF-008-B | PENDING 行 1 件 INSERT + 空レジストリで polling 1 サイクル → WARN ログ 1 件、`status='PENDING'` のまま |
| TC-IT-PF-008-C | 同シナリオで polling 2 サイクル目 → WARN は 1 回のみ（重複抑止） |
| TC-IT-PF-008-D | PENDING 行 101 件 INSERT → 滞留閾値 WARN 出力 |
