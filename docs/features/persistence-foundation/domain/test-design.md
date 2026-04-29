# テスト設計書

<!-- feature: persistence-foundation / sub-feature: domain -->
<!-- 配置先: docs/features/persistence-foundation/domain/test-design.md -->
<!-- 対象範囲: REQ-PF-001〜010 + REQ-PF-002-A / MSG-PF-001〜008 / 脅威 T1〜T9 / 受入基準 1〜12 / 開発者品質基準 Q-1 / Q-2 / Q-3 / 詳細設計 確定 A〜L (D-1〜D-4 / F の Fail-Secure 3 種 / J の LIFO cleanup / K の空ハンドラ Fail Loud / L の umask) / Schneier 申し送り 4 項目 (#1 / #4 / #5 / #6) + Schneier 重大 4 + 中等 4 のすべてに対する検出力テスト -->

本 feature は infrastructure 層の永続化基盤（DataDirResolver / SqliteEngine / SessionFactory / MaskingGateway / Outbox 系 / PidRegistryGC / AttachmentRoot / Bootstrap）に閉じる。Aggregate 別 Repository 本体は範囲外（後続 `feature/{aggregate}-repository` PR 群の責務）。HTTP API / CLI / UI の公開エントリポイントは持たないため、E2E は本 feature 範囲外（後続 `feature/admin-cli` / `feature/http-api` で起票）。

**本 feature のテストの主役は結合（integration）**である。理由は以下:

1. 永続化基盤の真価は **「呼び忘れ経路でもマスキングが効く」「DB 直 SQL でも `audit_log` DELETE が拒否される」「PRAGMA が毎接続適用される」「起動シーケンス 8 段階の順序が保証される」**といった**物理保証**にあり、unit でモックして検証すると本物の挙動を見失う
2. SQLite / Alembic / SQLAlchemy TypeDecorator (`MaskedJSONEncoded` / `MaskedText`、§確定 R1-D で旧 event listener 案から反転) / psutil / ファイルシステムは**本物を使えるなら本物を使う**（戦略ガイド §結合テスト方針: DB は実接続）
3. unit でモックするのは**単体ロジック**（regex 適用順序 / DataDirResolver の OS 別既定 / pid_gc の判定ロジック）に絞る

イーロン指示の **「Schneier 申し送り 4 項目（#1 / #4 / #5 / #6）の結合テスト + TypeDecorator `process_bind_param` が raw SQL 経路でも回避不能であることのテスト」**（旧表現「masking listener」は §確定 R1-D の反転で「TypeDecorator」に書き換え、内容は同一）は本 feature の中核として **integration（実 SQLite + 実ファイルシステム）** で網羅する。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-PF-001 | `data_dir.resolve()` 未設定時 OS 別既定 | TC-UT-PF-001 | ユニット | 正常系 | #1 |
| REQ-PF-001 | `data_dir.resolve()` 相対パス Fail Fast | TC-UT-PF-002 | ユニット | 異常系 | #2 |
| REQ-PF-001（Schneier #1） | `BAKUFU_DATA_DIR` 絶対パス強制（NUL バイト / `..` / 相対の網羅） | TC-UT-PF-002, TC-IT-PF-001 | ユニット / 結合 | 異常系 | #2 |
| REQ-PF-002 | engine 接続時 PRAGMA **8 件**適用（確定 D-1） | TC-IT-PF-003 | 結合 | 正常系 | #3 |
| REQ-PF-002（PRAGMA 順序、確定 D-1） | `journal_mode=WAL` を最初に SET、`defensive=ON` / `writable_schema=OFF` / `trusted_schema=OFF` を含む 8 件全網羅 | TC-IT-PF-013 | 結合 | 正常系 | #3 |
| REQ-PF-002（確定 D-1、Schneier 重大 2） | application engine で `defensive=ON` / `writable_schema=OFF` / `trusted_schema=OFF` が SET されている | TC-IT-PF-003-A | 結合 | 正常系 | 内部品質基準 |
| REQ-PF-002（確定 D-1、Schneier 重大 2） | **`DROP TRIGGER audit_log_no_delete`** が application engine 経由で拒否される（runtime DDL 制限） | TC-IT-PF-003-B | 結合 | 異常系 | 内部品質基準 |
| REQ-PF-002（確定 D-1、Schneier 重大 2） | **`UPDATE sqlite_master SET sql=...`** が application engine 経由で拒否される（trusted_schema=OFF + writable_schema=OFF） | TC-IT-PF-003-C | 結合 | 異常系 | 内部品質基準 |
| REQ-PF-002（確定 D-2 / D-3、dual connection） | `create_migration_engine()` は `defensive=OFF` / `writable_schema=ON` で生成、stage 3 終了時点で `dispose()` 済み（runtime に migration engine が生存しない） | TC-IT-PF-003-D | 結合 | 正常系 | 内部品質基準 |
| REQ-PF-002-A（DB 権限検出、Schneier 重大 3） | 新規 DB ファイル作成時 0o600 で作成される（POSIX）+ INFO ログ「Created new DB file at {path} (mode=0o600)」 | TC-IT-PF-002-A | 結合 | 正常系 | 内部品質基準 |
| REQ-PF-002-A（DB 権限検出、Schneier 重大 3） | 既存 DB が 0o644 で起動 → WARN ログ + `os.chmod(0o600)` で修復 + 起動続行（**Forensic 痕跡を消さない**：WARN ログに `prior unauthorized access` の hint が含まれる） | TC-IT-PF-002-B | 結合 | 異常系 | 内部品質基準 |
| REQ-PF-002-A（DB 権限検出、Schneier 重大 3） | WAL / SHM ファイル（`bakufu.db-wal` / `bakufu.db-shm`）にも同じ検出ロジックが適用される | TC-IT-PF-002-C | 結合 | 正常系 | 内部品質基準 |
| REQ-PF-003 | AsyncSession factory + `async with session.begin()` | TC-IT-PF-014 | 結合 | 正常系 | 内部品質基準 |
| REQ-PF-004 | Alembic 初回 revision で 3 テーブル + 2 トリガ | TC-IT-PF-004 | 結合 | 正常系 | #4 |
| REQ-PF-004（Schneier #4） | `audit_log` DELETE 拒否トリガ実発火 | TC-IT-PF-005 | 結合 | 異常系 | #5 |
| REQ-PF-004（Schneier #4） | `audit_log` UPDATE 制限トリガ（result NOT NULL 行への UPDATE 拒否） | TC-IT-PF-015 | 結合 | 異常系 | #5 |
| REQ-PF-005 | masking 9 種正規表現 + 環境変数 + ホームパス、適用順序込み | TC-UT-PF-006 | ユニット | 正常系 | #6 |
| REQ-PF-005（適用順序、確定 A） | OpenAI regex が `sk-ant-` を除く（Anthropic 先適用） | TC-UT-PF-016 | ユニット | 境界値 | #6 |
| REQ-PF-005（環境変数長さ） | 長さ 8 未満の env 値はパターン化しない | TC-UT-PF-017 | ユニット | 境界値 | #6 |
| REQ-PF-005（**Fail-Secure 契約、確定 F**、Schneier 重大 1） | mask が予期せぬ例外 raise 時、入力 str 全体が `<REDACTED:MASK_ERROR>` で完全置換される（生データは絶対に永続化されない） | TC-UT-PF-006-A | ユニット | 異常系 | #6 |
| REQ-PF-005（**Fail-Secure 契約、確定 F**、Schneier 重大 1） | mask_in が異常 dict（10MB 超）を受信時、当該 dict / list 全体が `<REDACTED:MASK_OVERFLOW>` で置換される | TC-UT-PF-006-B | ユニット | 異常系 | #6 |
| REQ-PF-006（**Fail-Secure 契約、確定 F**、Schneier 重大 1 中核） | TypeDecorator `process_bind_param` 自体が予期せぬ例外を raise 時、当該 masking 対象フィールドが `<REDACTED:LISTENER_ERROR>` で完全置換される（生データを書く経路ゼロ、トークン名 `LISTENER_ERROR` は履歴的命名で BUG-PF-001 修正前の listener 方式から継承） | TC-UT-PF-006-C | ユニット | 異常系 | #7 |
| REQ-PF-005（環境変数辞書ロード Fail Fast、確定 F） | 起動時に `os.environ` から既知 env キーの取得が失敗した場合、`BakufuConfigError(MSG-PF-008)` で Bootstrap exit 1（**部分マスキングで起動しない**） | TC-IT-PF-007-D | 結合 | 異常系 | 内部品質基準 |
| REQ-PF-005（再帰走査） | dict / list の再帰 masking | TC-UT-PF-019 | ユニット | 正常系 | #6 |
| REQ-PF-006（Schneier #6） | `domain_event_outbox` への ORM 経由 INSERT で payload_json / last_error がマスキング後値に上書き | TC-IT-PF-007 | 結合 | 正常系 | #7 |
| REQ-PF-006（Schneier #6 / R1-D 中核） | **raw SQL 経路（`session.execute(insert(table).values(...))`）でも TypeDecorator `process_bind_param` が走り masking 後値で永続化される**（旧 event listener 方式が破綻したことを物理証明する回帰テスト） | TC-IT-PF-020 | 結合 | 正常系 | #7 |
| REQ-PF-006（Schneier #6） | UPDATE 経路（`update(table).values(last_error=...)`）でも payload_json / last_error が `process_bind_param` で再マスキングされる（dispatcher の dead-letter 化経路） | TC-IT-PF-021 | 結合 | 正常系 | #7 |
| REQ-PF-006（Schneier #6） | `audit_log.args_json` / `error_text` / `bakufu_pid_registry.cmd` の TypeDecorator 配線動作確認 | TC-IT-PF-022 | 結合 | 正常系 | #7 |
| REQ-PF-007 | Outbox Dispatcher polling SQL の取得条件 | TC-IT-PF-008 | 結合 | 正常系 | #8 |
| REQ-PF-007（DISPATCHING リカバリ） | `(DISPATCHING AND updated_at < now - 5min)` 行が再取得される | TC-IT-PF-023 | 結合 | 正常系 | #8 |
| REQ-PF-007（dead-letter 化） | 5 回失敗で `status=DEAD_LETTER` + `OutboxDeadLettered` event 別行追記 | TC-IT-PF-009 | 結合 | 異常系 | #9 |
| REQ-PF-007（backoff スケジュール） | attempt_count 1〜5 の next_attempt_at が表通り（10s / 1m / 5m / 30m / 30m） | TC-IT-PF-024 | 結合 | 正常系 | #9 |
| REQ-PF-007（Handler 未登録） | `HandlerNotRegisteredError` で行が再 PENDING に戻る | TC-IT-PF-025 | 結合 | 異常系 | #9 |
| REQ-PF-007（**空 handler レジストリ Fail Loud**、確定 K、Schneier 中等 3） | 空レジストリで Bootstrap 起動完了直後に WARN ログ 1 件（`No event handlers registered. Outbox events will accumulate ...`） | TC-IT-PF-008-A | 結合 | 異常系 | 内部品質基準 |
| REQ-PF-007（**空 handler レジストリ Fail Loud**、確定 K） | PENDING 行 1 件 INSERT + 空レジストリで polling 1 サイクル → WARN ログ 1 件（`Outbox has {n} pending events but handler_registry is empty.`）、行は `status='PENDING'` のまま | TC-IT-PF-008-B | 結合 | 異常系 | 内部品質基準 |
| REQ-PF-007（**空 handler ログ・スパム防止**、確定 K） | 同シナリオで polling 2 サイクル目 → WARN ログは**追加されない**（1 サイクルにつき 1 回のみ重複抑止） | TC-IT-PF-008-C | 結合 | 異常系 | 内部品質基準 |
| REQ-PF-007（**Outbox 滞留閾値 WARN**、確定 K） | PENDING 行 101 件 INSERT → 滞留閾値 WARN（`Outbox PENDING count={n} > 100. Inspect with bakufu admin list-pending.`）が 5 分に 1 回出力 | TC-IT-PF-008-D | 結合 | 異常系 | 内部品質基準 |
| REQ-PF-008（Schneier #5） | pid_registry GC: `psutil.create_time()` で PID 衝突識別（mock psutil でケース網羅） | TC-UT-PF-010 | ユニット | 正常系 | #10 |
| REQ-PF-008（Schneier #5） | pid_registry GC: `protected` 判定では DELETE のみで kill しない | TC-UT-PF-026 | ユニット | 正常系 | #10 |
| REQ-PF-008（Schneier #5） | pid_registry GC: `psutil.AccessDenied` で WARN ログ + 行残し（次回 GC 再試行） | TC-UT-PF-027 | ユニット | 異常系 | #10 |
| REQ-PF-008（Schneier #5） | pid_registry GC: 子孫追跡 `recursive=True` + SIGTERM → 5s grace → SIGKILL の順序 | TC-UT-PF-028 | ユニット | 正常系 | #10 |
| REQ-PF-009 | アタッチメント FS ルート 0700 で作成（POSIX） | TC-IT-PF-011 | 結合 | 正常系 | #11 |
| REQ-PF-009 | アタッチメント FS ルートの mkdir 失敗 → MSG-PF-003 | TC-IT-PF-029 | 結合 | 異常系 | 内部品質基準 |
| REQ-PF-009（Windows 互換） | Windows では chmod なしでも作成成功（POSIX 限定機能の条件分岐） | TC-UT-PF-030 | ユニット | 正常系 | 内部品質基準 |
| REQ-PF-010（確定 G） | 起動シーケンス 8 段階順序実行 + 各段階の INFO 構造化ログ（開始/完了/失敗） | TC-IT-PF-012 | 結合 | 正常系 | #12 |
| REQ-PF-010（確定 G） | 各段階失敗時に後続が走らない（Fail Fast） | TC-IT-PF-031 | 結合 | 異常系 | #12 |
| REQ-PF-010（確定 G の例外） | 段階 4（pid_registry GC）失敗は非 fatal、後続が走る | TC-IT-PF-032 | 結合 | 正常系 | #12 |
| REQ-PF-010（**Bootstrap cleanup LIFO**、確定 J、Schneier 中等 4） | 段階 7 で例外発生時、段階 6 の dispatcher_task が `cancel()` 済みになる（`task.cancelled() == True`） | TC-IT-PF-012-A | 結合 | 異常系 | 内部品質基準 |
| REQ-PF-010（**Bootstrap cleanup LIFO**、確定 J） | 段階 8（FastAPI バインド失敗）で例外発生時、段階 6（dispatcher）と段階 7（attachment GC scheduler）の**両 task が cancel される + LIFO 順**（7 → 6 の順で cancel） | TC-IT-PF-012-B | 結合 | 異常系 | 内部品質基準 |
| REQ-PF-010（**engine.dispose() 保証**、確定 J） | cleanup 中に `engine.dispose()` が必ず呼ばれる（接続 pool / WAL flush の保証）+ 構造化ログが flush される | TC-IT-PF-012-C | 結合 | 異常系 | 内部品質基準 |
| REQ-PF-010（**umask 0o077 SET**、確定 L、Schneier 中等 1） | Bootstrap 起動後、`bakufu.db-wal` / `bakufu.db-shm` ファイルのモードが 0o600 で作成されている（POSIX、umask 0o077 が WAL/SHM 自動生成時に効く物理保証） | TC-IT-PF-001-A | 結合 | 正常系 | 内部品質基準 |
| REQ-PF-010（**umask 0o077 SET**、確定 L） | `Bootstrap.run()` の**最初の文**（stage 1 より前）で `os.umask(0o077)` が呼ばれる（mock で `os.umask` の call_args[0][0] == 0o077 を assert） | TC-UT-PF-001-A | ユニット | 正常系 | 内部品質基準 |
| 確定 I（依存方向） | `domain` 層から `bakufu.infrastructure.*` への import ゼロ件 | TC-CI-PF-001 | CI script | — | 内部品質基準 |
| Q-1（lint/typecheck） | `pyright --strict` / `ruff check` | （CI ジョブ） | — | — | 内部品質基準 |
| Q-2（カバレッジ） | `pytest --cov=bakufu.infrastructure.persistence.sqlite --cov=bakufu.infrastructure.security` | （CI ジョブ） | — | — | 内部品質基準 |
| MSG-PF-001 | `[FAIL] BAKUFU_DATA_DIR must be an absolute path (got: {value})` | TC-UT-PF-033 | ユニット | 異常系 | #2 |
| MSG-PF-002 | `[FAIL] SQLite engine initialization failed: {reason}` | TC-IT-PF-034 | 結合 | 異常系 | 内部品質基準 |
| MSG-PF-003 | `[FAIL] Attachment FS root initialization failed at {path}: {reason}` | TC-IT-PF-029 | 結合 | 異常系 | 内部品質基準 |
| MSG-PF-004 | `[FAIL] Alembic migration failed: {reason}` | TC-IT-PF-035 | 結合 | 異常系 | 内部品質基準 |
| MSG-PF-005 | SQLite トリガ raise message `audit_log is append-only` | TC-IT-PF-005 | 結合 | 異常系 | #5 |
| MSG-PF-005 | SQLite トリガ raise message `audit_log result is immutable once set` | TC-IT-PF-015 | 結合 | 異常系 | #5 |
| MSG-PF-006 | `[WARN] Masking gateway fallback applied: {kind}` — `{kind}` は `mask_error` / `listener_error` / `mask_overflow` / `mask_oversize_dict` のいずれか（確定 F の 3 種に同期） | TC-UT-PF-006-A, TC-UT-PF-006-B, TC-UT-PF-006-C | ユニット | 異常系 | #6 |
| MSG-PF-007 | `[WARN] pid_registry GC: psutil.AccessDenied for pid={pid}, retry next cycle` | TC-UT-PF-027 | ユニット | 異常系 | 内部品質基準 |
| MSG-PF-008（新規、確定 F） | `[FAIL] Masking environment dictionary load failed: {reason}. Cannot start with partial masking layer. Investigate env access permissions.` | TC-IT-PF-007-D | 結合 | 異常系 | 内部品質基準 |
| 結合シナリオ 1 | Backend 起動 → Aggregate 永続化 → Outbox イベント生成 → Dispatcher 配送 → masking 適用済みで永続化されている | TC-IT-PF-036 | 結合 | 正常系 | #7, #8, #12 |
| 結合シナリオ 2 | クラッシュリカバリ: 起動時 GC で pid_registry 孤児削除 + Outbox DISPATCHING 行を 5 分経過後に再取得 | TC-IT-PF-037 | 結合 | 正常系 | #8 |

**マトリクス充足の証拠**:
- REQ-PF-001〜010 + REQ-PF-002-A すべてに最低 1 件のテストケース
- **Schneier 申し送り 4 項目** すべてに **integration テスト**:
  - #1: `BAKUFU_DATA_DIR` 絶対パス強制 → TC-UT-PF-002 + TC-IT-PF-001
  - #4: `audit_log` DELETE 拒否トリガ + UPDATE 制限トリガ → TC-IT-PF-005 + TC-IT-PF-015
  - #5: `bakufu_pid_registry` GC + 0700 file mode → TC-UT-PF-010, 026, 027, 028 + TC-IT-PF-011
  - #6: Outbox masking via TypeDecorator `process_bind_param` → TC-IT-PF-007 + **TC-IT-PF-020（raw SQL 経路、§確定 R1-D 中核）** + TC-IT-PF-021 (UPDATE 経路) + TC-IT-PF-022（audit_log / pid_registry 配線）
- **Schneier 重大 4 件**すべてに検出力テスト（Schneier 再レビュー指摘 13 件超 = 計 20 件追加）:
  - 重大 1（Fail-Secure 契約、確定 F）: TC-UT-PF-006-A（mask 例外 → MASK_ERROR）/ TC-UT-PF-006-B（10MB 超 → MASK_OVERFLOW）/ **TC-UT-PF-006-C（`process_bind_param` 例外 → フィールド LISTENER_ERROR、本契約の中核、トークン名 `LISTENER_ERROR` は履歴的命名）** / TC-IT-PF-007-D（env 辞書ロード Fail Fast、MSG-PF-008）
  - 重大 2（PRAGMA defensive、確定 D-1〜D-4）: TC-IT-PF-003-A（defensive=ON / writable_schema=OFF / trusted_schema=OFF SET）/ **TC-IT-PF-003-B（DROP TRIGGER 拒否、トリガ DDL 改ざん防御の物理保証）** / TC-IT-PF-003-C（sqlite_master UPDATE 拒否）/ TC-IT-PF-003-D（dual connection、migration engine の dispose 確認）
  - 重大 3（DB 権限検出 Forensic、REQ-PF-002-A）: TC-IT-PF-002-A（新規 0o600）/ TC-IT-PF-002-B（既存 0o644 → WARN + 修復）/ TC-IT-PF-002-C（WAL/SHM）
  - 重大 4（`BAKUFU_DB_PATH` 廃止）: 環境変数自体を撤去したため攻撃面の物理排除（追加 TC 不要、TC-UT-PF-001 系で「`BAKUFU_DATA_DIR` のみ受け付けて `BAKUFU_DB_PATH` は無視される」契約を担保）
- **Schneier 中等 4 件**すべてに検出力テスト:
  - 中等 1（umask、確定 L）: **TC-IT-PF-001-A（WAL/SHM 0o600）** / TC-UT-PF-001-A（umask call_args 確認）
  - 中等 2（`BAKUFU_DB_KEY` 削除）: REQ-PF-005 の env キーリストに登場しないことを TC-UT-PF-006 のパラメタライズで確認（masking 対象は `BAKUFU_DISCORD_BOT_TOKEN` に置換、攻撃面の物理排除）
  - 中等 3（空 handler Fail Loud、確定 K）: TC-IT-PF-008-A（起動完了直後 WARN）/ TC-IT-PF-008-B（polling サイクル WARN）/ **TC-IT-PF-008-C（重複抑止）** / TC-IT-PF-008-D（滞留 100 件超 WARN）
  - 中等 4（Bootstrap cleanup LIFO、確定 J）: TC-IT-PF-012-A（dispatcher_task cancel 単独）/ **TC-IT-PF-012-B（dispatcher + scheduler の LIFO cancel）** / TC-IT-PF-012-C（engine.dispose() 保証）
- **イーロン指示の中核「raw SQL 経路でも masking が回避不能」**を TC-IT-PF-020 で物理確認（TypeDecorator `process_bind_param` の Core / ORM 両経路発火 = 確定 R1-D の根拠を test で凍結。旧 listener 案を反転却下した PR #23 BUG-PF-001 の回帰テスト）
- **PRAGMA 強制（確定 D-1）**: **8 件全 PRAGMA**（WAL / foreign_keys / busy_timeout / synchronous / temp_store / **defensive=ON** / **writable_schema=OFF** / **trusted_schema=OFF**）+ 順序（WAL 先頭）+ 毎接続適用を TC-IT-PF-003 + TC-IT-PF-013 + TC-IT-PF-003-A で確認
- **起動シーケンス凍結（確定 G）**: 順序実行（INFO 構造化ログ込み）+ Fail Fast + 段階 4 のみ非 fatal + LIFO cleanup（確定 J）を TC-IT-PF-012 / 012-A / 012-B / 012-C / 031 / 032 で確認
- **masking 適用順序（確定 A）**: Anthropic 先 → OpenAI 後の順序維持を TC-UT-PF-016 で確認、長さ 8 未満は除外を TC-UT-PF-017 で確認
- **依存方向（確定 I）**: domain → infrastructure の参照ゼロを TC-CI-PF-001 (CI script) で物理確認
- **MSG-PF-001〜008 すべて**に静的文字列照合（MSG-PF-008 は Schneier 重大 1 対応で新規追加、TC-IT-PF-007-D で照合）
- 受入基準 1〜12 すべてに unit/integration ケース（Q-1/Q-2/Q-3 は CI ジョブ担保）
- **T1〜T9** すべてに有効性確認ケース（T1〜T5 既存 + T6 マスキング fail-open / T7 トリガ DDL 改ざん / T8 DB 権限異常 / T9 空 handler 起動の 4 件は threat-model.md §A4 への昇格に同期）
- 確定 A（masking 9 種 + env + home）/ B（**TypeDecorator `process_bind_param` 配線**、§確定 R1-D で event listener 案から反転）/ C（SQLite トリガ）/ **D-1〜D-4（PRAGMA 8 件 + dual connection）** / E（pid_gc 順序）/ **F（Fail-Secure 3 種）** / G（起動シーケンス + INFO ログ）/ H（Schneier 申し送りステータス）/ I（依存方向 CI 検査）/ **J（Bootstrap cleanup LIFO）** / **K（空 handler Fail Loud）** / **L（umask 0o077）**すべてに証拠ケース
- 孤児要件ゼロ

## 外部 I/O 依存マップ

本 feature は infrastructure 層の中核であり、本物のSQLite + 本物のファイルシステム + 本物の Alembic を使う。psutil のみ unit ではモック化、integration では避ける（OS 依存性が高く、テスト環境で実 process を spawn することは安定性を損なう）。

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **SQLite (sqlite+aiosqlite)** | engine / session / 全テーブル / トリガ / Alembic migration | 不要（実 DB を `tmp_path` 配下の bakufu.db で起動、テストごとに使い捨て） | 不要（DB は本物） | **済（本物使用）** |
| **ファイルシステム** | `BAKUFU_DATA_DIR` / `attachments/` / file mode 0600/0700 / DB ファイル | 不要（`pytest.tmp_path`） | 不要（FS は本物） | **済（本物使用）** |
| **Alembic** | 初回 revision の `upgrade head` / `downgrade base` | 不要（本物の `alembic upgrade` を実 SQLite に対し実行） | 不要 | **済（本物使用）** |
| **環境変数** | `BAKUFU_DATA_DIR` / `BAKUFU_DB_PATH` / `BAKUFU_DEBUG` / 各 API キー（masking 対象） | 不要 | 不要 | **済（`monkeypatch.setenv` 使用）** |
| **psutil（プロセス操作）** | `pid_registry` 起動時 GC（`Process.create_time()` / `children(recursive=True)` / SIGTERM / SIGKILL） | `tests/fixtures/characterization/raw/psutil_process_states.json`（マスク済み実観測：CPython の `Process.create_time()` 出力 / `children()` 出力 / `NoSuchProcess` / `AccessDenied` の各例外形状） | `tests/factories/psutil_process.py`（schema 由来、`_meta.synthetic=True`、`PsutilProcessFactory` / `OrphanProcessFactory` / `ProtectedProcessFactory` / `AccessDeniedProcessFactory`） | **要起票 (Issue TBD-PF-1)** — 本 PR の unit / integration 実装着手前に必須 |
| **OS time（`datetime.now(UTC)` / `time.time()`）** | Outbox `created_at` / `next_attempt_at` / `updated_at` / DISPATCHING 5 分リカバリ判定 | 不要 | `tests/factories/freezegun_clock.py`（`freezegun` 経由の固定時刻、`_meta.synthetic=True`） | **要起票 (Issue TBD-PF-2)** — Outbox dispatcher の backoff / リカバリ判定をテストするため |
| **OS platform（`platform.system()`）** | `data_dir._default_for_os()` の OS 分岐 / `attachment_root.ensure_root()` の chmod 条件分岐 | 不要 | 不要（`monkeypatch.setattr('platform.system', ...)` で直接差し替え、Linux/macOS/Windows 各値） | **済（標準ライブラリの mock で十分）** |
| **asyncio loop** | Outbox Dispatcher の polling task / attachment GC スケジューラ / Bootstrap.run() | 不要 | 不要（`pytest-asyncio` の `event_loop` fixture を使用） | **済（pytest-asyncio）** |

**空欄（要起票）の扱い**: TBD-PF-1（psutil characterization）/ TBD-PF-2（freezegun clock factory）の Issue が完了するまで、該当項目に関わる unit/integration は「assumed mock」を禁じる。特に **TBD-PF-1 が未完で `psutil.Process.create_time()` の戻り値型・精度・例外形状を仮定で書くと、PID 衝突対策の検出力ゼロのテストになる**。本 PR は **TBD-PF-1 と TBD-PF-2 を本 PR の冒頭で完了させてから unit / integration 実装に着手する**（起動順序: characterization → factory → unit/integration）。

**raw fixture の鮮度**: TBD-PF-1 完了時に `_meta.captured_at` / `psutil_version` を埋め、CI で 30 日超過 fail を有効化する。psutil は Python マイナーバージョン更新で挙動が変わる可能性があるため、依存更新時は raw を再取得する。

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `PsutilProcessFactory` | psutil.Process の mock（`pid` / `create_time()` / `children(recursive=True)` / `terminate()` / `kill()` / `wait()` メソッドを持つ） | `True` |
| `OrphanProcessFactory` | `create_time()` が pid_registry の `started_at` と一致する mock（孤児 kill 対象） | `True` |
| `ProtectedProcessFactory` | `create_time()` が `started_at` と不一致の mock（PID 再利用、protected 判定） | `True` |
| `AccessDeniedProcessFactory` | `create_time()` 呼び出し時に `psutil.AccessDenied` を raise する mock | `True` |
| `NoSuchProcessFactory` | `psutil.Process(pid)` 呼び出し時点で `psutil.NoSuchProcess` を raise する mock | `True` |
| `FrozenClockFactory` | `freezegun.freeze_time()` のラッパー。`_meta.synthetic=True` のメタを付与 | `True` |
| `OutboxRowFactory` | `domain_event_outbox` 行（PENDING / DISPATCHING / DEAD_LETTER の各 status） | `True` |
| `AuditLogRowFactory` | `audit_log` 行（result NULL / SUCCESS / FAILURE の各状態） | `True` |
| `PidRegistryRowFactory` | `bakufu_pid_registry` 行 | `True` |
| `MaskingPayloadFactory` | masking 入力サンプル（API キー / GitHub PAT / Discord token / Bearer 各形式を埋め込んだ dict / list / str） | `True` |

`_meta.synthetic = True` は empire / workflow / agent / room と同じく **`tests/factories/<name>.py` モジュールスコープ `WeakValueDictionary[int, BaseModel]` レジストリ + `id(instance)` をキーに `is_synthetic()` で判定** 方式を踏襲する。本番コード（`backend/src/bakufu/`）からは `tests/factories/` を import しない（CI で `tests/` から `src/` への向きのみ許可）。

## E2E テストケース

**該当なし** — 理由:

- 本 feature は infrastructure 層単独で、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない（[`../feature-spec.md`](../feature-spec.md) §画面・CLI 仕様 / §API 仕様 で「該当なし」と凍結）
- Bootstrap が起動する FastAPI / WebSocket リスナは段階 8 で「listening」に至るのみで、実 HTTP リクエストを処理する handler は本 PR の範囲外
- 戦略ガイド §E2E対象の判断「内部API・ライブラリなどエンドユーザー操作がない場合は結合テストで代替可」に従い、E2E は本 feature 範囲外
- 後続 `feature/admin-cli` / `feature/http-api` が公開 I/F を実装した時点で E2E（`bakufu admin retry-event` 等で実 SQLite に書き込み確認）を起票
- 受入基準 1〜12 はすべて unit/integration テストで検証可能（Q-1/Q-2/Q-3 は CI ジョブ担保）

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — infrastructure 層のため公開 I/F なし | — | — |

## 結合テストケース

**「複数モジュール連携 + 実 SQLite + 実ファイルシステム + 実 Alembic」を contract testing する**層。外部 LLM / Discord / GitHub は本 feature では使わない（後続 feature の責務）。

### 起動シーケンス + DataDir + Engine + Migration（受入基準 1, 3, 4, 12）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-001 | DataDirResolver + 環境変数 | `monkeypatch.setenv('BAKUFU_DATA_DIR', '/abs/path')` | 任意の絶対パス値 | `data_dir.resolve()` を呼ぶ | 戻り値が `Path('/abs/path')` の絶対パスで Path.resolve() 済み |
| TC-IT-PF-003 | SqliteEngine + 接続 PRAGMA | tmp_path 配下の bakufu.db | engine 生成後、`async with engine.begin()` で接続 | `SELECT * FROM pragma_journal_mode / pragma_foreign_keys / pragma_busy_timeout / pragma_synchronous / pragma_temp_store` を実行 | 各 PRAGMA が `WAL` / `1`（ON）/ `5000` / `1`（NORMAL）/ `2`（MEMORY）であること（受入基準 3） |
| TC-IT-PF-013 | SqliteEngine + PRAGMA **8 件** 順序（確定 D-1） | tmp_path | engine 生成 + listener にログフックを差し込み | engine の `connect` event で発火された PRAGMA SET の順序を観測 | `journal_mode=WAL` が最初、続けて `foreign_keys=ON` / `busy_timeout=5000` / `synchronous=NORMAL` / `temp_store=MEMORY` / **`defensive=ON`** / **`writable_schema=OFF`** / **`trusted_schema=OFF`** の **8 件全網羅** |
| TC-IT-PF-003-A | application engine の defensive PRAGMA SET（確定 D-1、Schneier 重大 2） | tmp_path | application engine 構築済み | engine 接続後に `PRAGMA defensive` / `PRAGMA writable_schema` / `PRAGMA trusted_schema` を SELECT | 各値が `1` (ON) / `0` (OFF) / `0` (OFF)。SQLite version が `defensive=ON` 未対応の場合は確定 D-4 のフォールバック経路（`query_only` 切替方式）が動作することを検証 |
| TC-IT-PF-003-B | **DROP TRIGGER 拒否**（確定 D-1、Schneier 重大 2、T7 防御） | tmp_path + Alembic 適用済み（audit_log_no_delete トリガ存在） | application engine | application engine 経由で `DROP TRIGGER audit_log_no_delete` を**raw SQL** で実行 | `sqlite3.OperationalError`（または同等）が raise、トリガは削除されない（`SELECT name FROM sqlite_master WHERE type='trigger'` で `audit_log_no_delete` が依然存在）。**runtime DDL 制限の物理保証**（攻撃者が DROP TRIGGER で audit_log 防衛を外せない） |
| TC-IT-PF-003-C | **sqlite_master UPDATE 拒否**（確定 D-1、Schneier 重大 2、T7 防御） | tmp_path | application engine | application engine 経由で `UPDATE sqlite_master SET sql='...' WHERE name='audit_log_no_delete'` を**raw SQL** で実行 | `sqlite3.OperationalError`（writable_schema=OFF + trusted_schema=OFF の組合せで拒否）、トリガ定義は変更されない |
| TC-IT-PF-003-D | **dual connection の生存期間**（確定 D-2 / D-3、Schneier 重大 2） | tmp_path | `Bootstrap.run()` 経由 | (1) Bootstrap stage 3 開始時点で `create_migration_engine()` 経由の engine が `defensive=OFF` / `writable_schema=ON` で生成されることを listener フックで観測 (2) stage 3 終了時点で当該 engine の `engine.dispose()` が呼ばれていることを mock の call_count == 1 で確認 (3) stage 4 以降は application engine（defensive=ON）のみが生存することを `engine_registry` の inspection で確認 | runtime には migration engine が**存在しない**ことが物理保証される。攻撃者が runtime DDL でトリガを DROP する経路が論理的に閉じる |
| TC-IT-PF-014 | SessionFactory + UoW 境界 | tmp_path bakufu.db | engine + session_factory 構築済み | `async with session_factory() as session, session.begin(): session.add(audit_log_row)` を実行 → ブロック退出で commit、ブロック内で例外 raise → ブロック退出で rollback | commit 経路で SELECT が値を返す、rollback 経路で SELECT が空 |
| TC-IT-PF-004 | Alembic 初回 revision | tmp_path bakufu.db + 本物の alembic | engine 構築済み | `alembic upgrade head` を実行 | `SELECT name FROM sqlite_master WHERE type='table'` で `audit_log` / `bakufu_pid_registry` / `domain_event_outbox` の 3 テーブルが存在、`type='trigger'` で `audit_log_no_delete` / `audit_log_update_restricted` の 2 トリガが存在（受入基準 4） |
| TC-IT-PF-035 | Alembic migration 失敗 | tmp_path + 故意に壊した revision script | upgrade head が例外を吐く設定 | `Bootstrap.run()` を呼ぶ | `BakufuMigrationError` が raise、`stderr` に `[FAIL] Alembic migration failed:` で始まるメッセージ（MSG-PF-004） |

### `audit_log` 改ざん拒否（Schneier #4、T2、受入基準 5）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-005 | SQLite トリガ + audit_log DELETE 拒否 | tmp_path + 初回 revision 適用済み | audit_log に 1 行 INSERT 済み | **raw SQL** で `DELETE FROM audit_log WHERE id=:id` を実行 | `sqlite3.IntegrityError`（または同等）が raise、`audit_log is append-only` 文言を含む（MSG-PF-005）。SELECT すると行は残ったまま（OWASP A08 / T2 物理保証） |
| TC-IT-PF-015 | SQLite トリガ + audit_log UPDATE 制限 | tmp_path + audit_log 1 行（result='SUCCESS' で確定済み） | result NOT NULL 行 | `UPDATE audit_log SET result='FAILURE' WHERE id=:id` を実行 | `sqlite3.IntegrityError` が raise、`audit_log result is immutable once set` 文言を含む。result NULL 行への UPDATE（result NULL → 'SUCCESS'）は通過することも併せて確認（実行完了時の唯一許可経路） |

### マスキング配線（Schneier #6、T1、受入基準 7）

**本 feature の中核。raw SQL 経路でも TypeDecorator `process_bind_param` が走ることを物理保証する**（イーロン指示の核心、§確定 R1-D 反転後の表現）。

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-007 | Outbox masking（TypeDecorator）+ ORM 経路 | tmp_path + Alembic 適用済み | engine + session 構築済み | `MaskingPayloadFactory` で生成した `payload_json={'key': 'sk-ant-api03-' + 'A' * 50, 'github_pat': 'ghp_' + 'X' * 40, 'description': 'see /home/myuser/secret'}` を含む `domain_event_outbox` 行を `session.add()` で INSERT | `SELECT payload_json, last_error FROM domain_event_outbox` で取得した値で `sk-ant-api03-...` が `<REDACTED:ANTHROPIC_KEY>` に、`ghp_...` が `<REDACTED:GITHUB_PAT>` に、`/home/myuser/...` が `<HOME>/...` に置換されている（受入基準 7） |
| TC-IT-PF-020 | Outbox masking（TypeDecorator）+ **raw SQL 経路（R1-D 中核）** | tmp_path + Alembic 適用済み | engine + session 構築済み | **ORM mapper を経由しない経路** `session.execute(sqlalchemy.insert(outbox_table).values(payload_json='sk-ant-api03-' + 'A' * 50, last_error='ghp_' + 'X' * 40, ...))` で raw SQL 風に INSERT | TypeDecorator `process_bind_param` が走り、SELECT で取得した値で `sk-ant-api03-...` が `<REDACTED:ANTHROPIC_KEY>` に、`ghp_...` が `<REDACTED:GITHUB_PAT>` に置換されている。**「呼び忘れ経路でもマスキングが効く」物理保証**（OWASP A02 / 確定 R1-D / 旧 event listener 案が反転却下された決定根拠を test で凍結。退行検出: 将来誰かが TypeDecorator → listener 方式に戻そうとすると本テストが赤くなる） |
| TC-IT-PF-021 | Outbox masking（TypeDecorator）+ UPDATE 経路 | tmp_path + Outbox 行 1 件（PENDING） | dispatcher が dead-letter 化する経路をシミュレート | `UPDATE domain_event_outbox SET status='DEAD_LETTER', last_error='AKIA' + '1234567890ABCDEF1' WHERE event_id=:id` を実行 | `MaskedText.process_bind_param` が UPDATE bind でも発火し、`last_error` が `<REDACTED:AWS_ACCESS_KEY>` で永続化される。`payload_json` も同じ行で再マスキング適用される（idempotent: 既マスキング済み値は再適用しても変化しない） |
| TC-IT-PF-022 | audit_log + pid_registry の masking 配線（hook 動作確認） | tmp_path + Alembic 適用済み | engine + session 構築済み | `audit_log.args_json={'token': 'xoxb-1234567890-...'}` / `error_text='Bearer eyJ...token...'` および `bakufu_pid_registry.cmd='claude --api-key=sk-ant-api03-...'` を INSERT | `SELECT` で取得した各値が `<REDACTED:SLACK_TOKEN>` / `<REDACTED:BEARER>` / `<REDACTED:ANTHROPIC_KEY>` に置換されている（Schneier #6 の hook 構造が 3 テーブル全てに動作することを物理確認） |
| TC-IT-PF-007-D | **環境変数辞書ロード Fail Fast**（確定 F、Schneier 重大 1） | tmp_path + 故意に `os.environ.get` を例外 raise させる mock | Bootstrap 起動時 | `Bootstrap.run()` を呼ぶ | (1) Bootstrap が exit 1 でプロセス終了（`SystemExit.code == 1`）、(2) stderr に MSG-PF-008 完全一致: `[FAIL] Masking environment dictionary load failed: {reason}. Cannot start with partial masking layer. Investigate env access permissions.`、(3) stage 2 以降に進まない（Fail Fast）、(4) 部分マスキングで起動しないことを物理確認（**部分マスキング起動経路の根絶**） |

### Outbox Dispatcher（受入基準 8, 9）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-008 | Dispatcher polling SQL | tmp_path + Outbox 行（PENDING で `next_attempt_at <= now`、PENDING で `next_attempt_at > now`、DISPATCHED、DEAD_LETTER の 4 行） + freezegun 固定時刻 | dispatcher を 1 サイクル走らせる | polling SQL の取得結果を assert | PENDING で `next_attempt_at <= now` の 1 行のみ取得される。他 3 行は対象外 |
| TC-IT-PF-023 | Dispatcher DISPATCHING リカバリ | tmp_path + Outbox 行（DISPATCHING で `updated_at < now - 5min`、DISPATCHING で `updated_at < now - 4min`） + freezegun | dispatcher を 1 サイクル走らせる | 取得結果を assert | 5 分超過の 1 行のみ取得（4 分のものは未取得）、強制 PENDING 戻しは行わず DISPATCHING のまま再取得 → handler 再呼び出し |
| TC-IT-PF-009 | Dispatcher dead-letter 化 | tmp_path + 5 回失敗する Handler を register + Outbox 行（PENDING） + freezegun（backoff 経過させる） | dispatcher を 6 サイクル走らせる（attempt_count を 1 → 6 に進める） | DB 状態 + 別行の追記 | 元行が `status=DEAD_LETTER`、`attempt_count=5` で確定。さらに別行として `event_kind='OutboxDeadLettered'`、`payload_json` に元 event_id 参照、`status=PENDING` の dead-letter 専用 event が追記される（受入基準 9） |
| TC-IT-PF-024 | backoff スケジュール | tmp_path + 失敗 Handler + Outbox 行 + freezegun | attempt_count 1〜5 の各時点で polling 再走 | `next_attempt_at` の値を assert | attempt_count 1 で +10s、2 で +1m、3 で +5m、4 で +30m、5 で +30m（events-and-outbox.md §Retry 戦略 と同一） |
| TC-IT-PF-025 | Handler 未登録時の挙動 | tmp_path + Outbox 行（`event_kind='UnregisteredKind'`） | handler レジストリが空 | dispatcher を 1 サイクル走らせる | `HandlerNotRegisteredError` を catch、行は `status=PENDING` に戻る + WARN ログ。dispatcher 自身は終了しない |

### Outbox Dispatcher 空 handler レジストリ Fail Loud（確定 K、Schneier 中等 3）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-008-A | Bootstrap stage 6 起動完了直後の WARN | tmp_path + handler_registry が空 | Bootstrap.run() 実行中 | stage 6 完了タイミングのログを観測 | WARN ログ 1 件出力: `[WARN] Bootstrap stage 6/8: No event handlers registered. Outbox events will accumulate without dispatch. Register handlers via feature/{event-kind}-handler PRs before processing real events.` 完全一致を含む |
| TC-IT-PF-008-B | polling サイクルでの空レジストリ WARN | tmp_path + Outbox に PENDING 行 1 件 + handler_registry 空 + freezegun（`next_attempt_at <= now`） | dispatcher を 1 サイクル走らせる | ログ + DB 状態を観測 | (1) WARN ログ 1 件: `[WARN] Outbox has {n} pending events but handler_registry is empty.` の `{n}` が `1` に展開されている、(2) 行は `status='PENDING'` のまま（DISPATCHED にも DEAD_LETTER にもならない） |
| TC-IT-PF-008-C | **重複抑止**（ログ・スパム防止、確定 K） | tmp_path + Outbox PENDING 1 件 + handler_registry 空 + freezegun | dispatcher を 2 サイクル連続で走らせる | 全 WARN ログを集計 | `Outbox has ... pending events but handler_registry is empty.` の WARN は **2 サイクル合計で 1 回のみ出力**（重複抑止フラグが効く）。同じレベルの spam 化を防ぐ |
| TC-IT-PF-008-D | **Outbox 滞留閾値 WARN**（100 件超） | tmp_path + Outbox に PENDING 101 件 INSERT + handler_registry 空 + freezegun（5 分経過させる） | dispatcher を 1 サイクル走らせる | ログを観測 | WARN ログ 1 件: `[WARN] Outbox PENDING count={n} > 100. Inspect with bakufu admin list-pending.` の `{n}` が `101` に展開されている。5 分経過後の次回も 1 回出力（5 分に 1 回ペース） |

### アタッチメント FS ルート（受入基準 11、Schneier #5 file mode 補完）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-011 | AttachmentRootInitializer + POSIX file mode | tmp_path（POSIX 環境） | DATA_DIR が tmp_path 配下 | `attachment_root.ensure_root()` を呼ぶ | `<DATA_DIR>/attachments/` が存在、`os.stat().st_mode & 0o777 == 0o700`（受入基準 11）。Linux/macOS で実 chmod 検証 |
| TC-IT-PF-029 | mkdir 失敗（権限不足） | tmp_path + 親ディレクトリを 0500 にして書き込み禁止 | `<DATA_DIR>` が書き込み禁止 | `attachment_root.ensure_root()` を呼ぶ | `BakufuConfigError` が raise、文言 `[FAIL] Attachment FS root initialization failed at {path}: {reason}`（MSG-PF-003） |

### DB ファイル権限検出（REQ-PF-002-A、Schneier 重大 3、Forensic 観点）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-002-A | 新規 DB ファイル作成時の 0o600（POSIX） | tmp_path + 新規 DATA_DIR（DB ファイル未作成） | engine 初回接続 | `Bootstrap.run()` 経由で stage 2 完了まで実行 | (1) `<DATA_DIR>/bakufu.db` が作成され `os.stat().st_mode & 0o777 == 0o600`、(2) INFO ログ: `[INFO] Created new DB file at {path} (mode=0o600)` が出力 |
| TC-IT-PF-002-B | 既存 DB の権限異常 → WARN + 修復 + 続行（Forensic） | tmp_path + 既存 `bakufu.db` を `os.chmod(path, 0o644)` で改ざんして配置 | DB ファイル mode が 0o644 | `Bootstrap.run()` 経由 stage 2 | (1) WARN ログ完全一致: `[WARN] DB file at {path} has unexpected permission 0o644, expected 0o600. This may indicate prior unauthorized access. Manual investigation recommended (compare with audit_log of last access). Auto-fixing to 0o600 to prevent further exposure.`、(2) ERROR ログにも同内容が複製される（Forensic 痕跡を消さない）、(3) `os.chmod(path, 0o600)` が呼ばれて修復、(4) Bootstrap は stage 3 以降を続行（Fail Fast にしない）、(5) `prior unauthorized access` の hint 文字列が WARN ログに含まれることを assert |
| TC-IT-PF-002-C | WAL / SHM ファイルにも検出ロジック適用 | tmp_path + 既存 `bakufu.db-wal` / `bakufu.db-shm` を 0o644 で配置 | WAL / SHM が 0o644 | `Bootstrap.run()` 経由 stage 2 | WAL / SHM 両ファイルで TC-IT-PF-002-B と同等の WARN + 修復 + 続行が動作。各ファイルに対し独立の WARN ログが出力される |

### 起動シーケンス順序保証（確定 G、受入基準 12）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-012 | Bootstrap 8 段階順序 | tmp_path + 全段階成功する設定 | 各段階に呼び出しログを差し込む | `Bootstrap.run()` を呼ぶ | ログから (1) DATA_DIR resolve → (2) engine init → (3) Alembic upgrade → (4) pid_gc → (5) attachments → (6) outbox dispatcher → (7) attachment GC scheduler → (8) FastAPI listener の順序通り実行が観測される（確定 G） |
| TC-IT-PF-031 | 段階失敗時の Fail Fast | tmp_path + 段階 2（engine init）で例外を仕込む | engine 生成が失敗する | `Bootstrap.run()` を呼ぶ | `BakufuConfigError(MSG-PF-002)` で raise、stderr へ出力、後続段階 3〜8 が**実行されないこと**をログ非出現で確認 |
| TC-IT-PF-032 | 段階 4（pid_gc）失敗の非 fatal | tmp_path + pid_gc で psutil.AccessDenied を全件返す mock | pid_gc が WARN 出力 | `Bootstrap.run()` を呼ぶ | WARN ログ出力 + 段階 5〜8 が継続実行される（確定 G の段階 4 のみ非 fatal 例外） |

### Bootstrap cleanup LIFO（確定 J、Schneier 中等 4）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-012-A | 段階 7 失敗時の段階 6 task cancel | tmp_path + 段階 7（attachment GC scheduler 起動）で例外を仕込む | 段階 6 まで成功、段階 7 で失敗 | `Bootstrap.run()` を呼ぶ | (1) `BakufuConfigError` 等で raise、(2) `dispatcher_task.cancelled() == True`（段階 6 で起動された task が finally で cancel された）、(3) `await asyncio.gather(dispatcher_task, return_exceptions=True)` の戻り値に `CancelledError` が含まれる |
| TC-IT-PF-012-B | **段階 8 失敗時の LIFO cancel**（確定 J 中核） | tmp_path + 段階 8（FastAPI バインド失敗、port 衝突など）で例外を仕込む | 段階 7 まで成功、段階 8 で失敗 | `Bootstrap.run()` を呼ぶ | (1) `gc_task.cancelled() == True` かつ `dispatcher_task.cancelled() == True`（**両 task が cancel される**）、(2) cancel 順序を mock の call_args_list で観測すると **`gc_task.cancel()` → `dispatcher_task.cancel()`** の順（**後に起動したものから先に cancel する LIFO**）、(3) `engine.dispose()` が cleanup 末尾で呼ばれる |
| TC-IT-PF-012-C | engine.dispose() / 構造化ログ flush の保証 | tmp_path + 任意の段階で例外を仕込む（段階 6 / 7 / 8） | 起動失敗 | `Bootstrap.run()` を呼ぶ | (1) `engine.dispose()` の mock の call_count == 1（接続 pool / WAL flush の保証）、(2) 構造化ログハンドラの `flush()` が呼ばれる、(3) プロセスが exit_code == 1 で終了 |

### umask 0o077 SET（確定 L、Schneier 中等 1）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-001-A | WAL / SHM が 0o600 で作成（POSIX 物理保証） | tmp_path（POSIX）+ 起動前にプロセスの umask が `0o022` であることを `os.umask(0o022)` で確認 | DATA_DIR が tmp_path 配下、新規 DB | `Bootstrap.run()` 経由で stage 2〜3 完了まで実行（SQLite が WAL / SHM を自動生成） | (1) `<DATA_DIR>/bakufu.db-wal` の `os.stat().st_mode & 0o777 == 0o600`、(2) `<DATA_DIR>/bakufu.db-shm` の `os.stat().st_mode & 0o777 == 0o600`。**umask 0o077 が SET されていない場合は両ファイルが 0o644 で作成される**ため、umask が効いていることが物理層で保証される |

### 結合シナリオ（受入基準 7, 8, 12 を一連で確認）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-036 | Backend 起動 → Aggregate 永続化 → Outbox event → Dispatcher 配送（masking 適用済みで永続化） | tmp_path + Echo Handler を register（payload を捨てるだけの no-op） + freezegun | 全構成要素が初期化済み | 1) `Bootstrap.run()` で 8 段階完了 → 2) 直接 `domain_event_outbox` に webhook URL を含む payload で 1 行 INSERT → 3) freezegun を `next_attempt_at` 直後に進める → 4) dispatcher を 1 サイクル走らせる → 5) Echo Handler が呼ばれて成功 | (a) DB 上の payload_json で webhook URL が `<REDACTED:DISCORD_WEBHOOK>` 化、(b) status が PENDING → DISPATCHING → DISPATCHED に遷移、(c) `dispatched_at` が freezegun の現在時刻と一致、(d) audit_log は INSERT されない（本シナリオは Admin CLI 経由ではないため）|
| TC-IT-PF-037 | クラッシュリカバリ（pid_registry 孤児削除 + Outbox DISPATCHING リカバリ） | tmp_path + 事前に bakufu_pid_registry に `started_at != psutil.create_time()` の行を仕込む（protected シナリオ）+ Outbox に `DISPATCHING` で `updated_at < now - 6min` の行を仕込む + freezegun | 前回プロセスがクラッシュした状態を再現 | `Bootstrap.run()` で起動シーケンス段階 4（pid_gc）と段階 6（dispatcher）を実行 | (a) pid_registry の protected 行が DELETE される（kill しない）、(b) Outbox DISPATCHING 行が dispatcher の polling で再取得され handler 呼び出しが再発火する |

## ユニットテストケース

`tests/factories/<name>.py` の factory 経由で入力を生成する。psutil / asyncio clock は本物を使えない / 使うべきでないため factory（mock）経由必須。raw fixture は本 feature では integration test 専用（unit でも `tests/factories/psutil_process.py` を介して同一 schema から派生させる）。

### DataDirResolver（受入基準 1, 2、Schneier #1）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-PF-001 | `data_dir.resolve()` 未設定時 OS 別既定 | 正常系 | `monkeypatch.delenv('BAKUFU_DATA_DIR')` + `monkeypatch.setattr('platform.system', lambda: 'Linux'/'Darwin'/'Windows')` の各値 | Linux: `${XDG_DATA_HOME:-$HOME/.local/share}/bakufu` の絶対パス、macOS: 同左、Windows: `%LOCALAPPDATA%\bakufu` の絶対パス（受入基準 1） |
| TC-UT-PF-002 | `data_dir.resolve()` 相対パス Fail Fast | 異常系 | `monkeypatch.setenv('BAKUFU_DATA_DIR', './relative/path')` | `BakufuConfigError(MSG-PF-001)` が raise（受入基準 2、Schneier #1） |
| TC-UT-PF-033 | MSG-PF-001 文言照合 | 異常系 | `BAKUFU_DATA_DIR='./relative'` | 例外 message が `[FAIL] BAKUFU_DATA_DIR must be an absolute path (got: ./relative)` 完全一致 |
| TC-UT-PF-038 | NUL バイト含む値 | 異常系 | `BAKUFU_DATA_DIR='/abs/with\x00null'` | `BakufuConfigError(MSG-PF-001)` |
| TC-UT-PF-039 | `..` 含む値 | 異常系 | `BAKUFU_DATA_DIR='/abs/../escape'` | `BakufuConfigError(MSG-PF-001)`（resolve 後でも `..` が parts に含まれる場合 Fail Fast） |
| TC-UT-PF-040 | singleton キャッシュ | 正常系 | `resolve()` を 2 回呼ぶ | 2 回目は os.environ を再読み込みせず初回値を返す（module-level `_resolved` キャッシュ） |

### MaskingGateway（受入基準 6、確定 A / F）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-PF-006 | masking 9 種正規表現 + 環境変数 + ホームパスの統合 | 正常系 | 各種秘密情報を埋め込んだ str | 9 種すべての置換が適用される。`MaskingPayloadFactory` で生成 |
| TC-UT-PF-016 | 適用順序: Anthropic 先 → OpenAI 後（確定 A） | 境界値 | `'sk-ant-api03-' + 'A' * 50`（Anthropic）+ `'sk-' + 'A' * 30`（OpenAI、`sk-ant-` を除く） | Anthropic は `<REDACTED:ANTHROPIC_KEY>`、OpenAI は `<REDACTED:OPENAI_KEY>` に独立して置換。**OpenAI regex が Anthropic を誤マッチしない**ことを assert |
| TC-UT-PF-017 | 環境変数値の長さ閾値 | 境界値 | `monkeypatch.setenv('ANTHROPIC_API_KEY', 'short')` (5 文字) / `'12345678'` (8 文字) / `'123456789'` (9 文字) | 5 文字: パターン化されない（誤マッチ防止）、8/9 文字: パターン化される。長さ 8 が境界（確定 A） |
| TC-UT-PF-018 | フォールバック（確定 F、互換性維持） | 異常系 | 想定外の型（`bytes` / `datetime`）を `mask_in()` に渡す | str に変換してから `mask()` 適用。`<REDACTED:UNKNOWN>` 経路は採用しない（確定 F で 3 種に統一） |
| TC-UT-PF-006-A | **mask 例外時の MASK_ERROR 完全置換**（確定 F、Schneier 重大 1） | 異常系 | regex マッチ中に例外を発生させる mock（理論上発生しないが防衛のため） | (1) `mask(input_str)` の戻り値が `<REDACTED:MASK_ERROR>` 完全一致（**入力 str 全体を完全置換、生データ部分残しなし**）、(2) WARN ログに MSG-PF-006 形式で `kind=mask_error` を含む |
| TC-UT-PF-006-B | **mask_in 異常 dict での MASK_OVERFLOW 置換**（確定 F、Schneier 重大 1） | 異常系 | 10MB 超の dict（再帰深度 100 超 or サイズ閾値超過）を `mask_in()` に渡す | (1) 当該 dict / list 全体が `<REDACTED:MASK_OVERFLOW>` で置換される、(2) 部分的な mask 適用は行わず**全体を捨てる**（Fail-Secure）、(3) WARN ログ MSG-PF-006 で `kind=mask_overflow`（または `mask_oversize_dict`）を含む |
| TC-UT-PF-006-C | **`process_bind_param` 例外時の LISTENER_ERROR 置換**（確定 F 中核、Schneier 重大 1） | 異常系 | TypeDecorator の outer catch を発火させる mock（masking gateway 内部で予期せぬ例外を strategically raise） | (1) 当該 masking 対象フィールド（`payload_json` / `last_error` / `args_json` / `error_text` / `cmd` / `prompt_body` 等）が `<REDACTED:LISTENER_ERROR>` で置換される（トークン名は履歴的命名、BUG-PF-001 修正前の listener 方式から継承）、(2) 生データが残る経路がないことを assert（**生データを書く経路ゼロの物理保証**）、(3) ERROR ログ出力（WARN ではなく ERROR）、(4) INSERT / UPDATE は continued（永続化を止めない） |
| TC-UT-PF-019 | 再帰走査 | 正常系 | `mask_in({'key': 'sk-ant-...', 'nested': {'pat': 'ghp_...', 'list': ['Bearer eyJ...', 'AKIA...']}, 'normal': 'no secret'})` | dict / list を再帰走査、全 str に masking 適用、非 str は素通り（int / None / bool） |
| TC-UT-PF-041 | ホームパス置換 | 正常系 | `mask('error at /home/myuser/.local/share/bakufu/db.sqlite')` (HOME=/home/myuser) | `/home/myuser` が `<HOME>` に置換 |
| TC-UT-PF-042 | 9 種 regex 各単独テスト | 正常系 | Anthropic / OpenAI / GitHub PAT / GitHub fine-grained / AWS Access / AWS Secret / Slack / Discord bot / Bearer の各形式 1 件ずつ | 各 regex に対応する `<REDACTED:{KIND}>` に置換（パラメタライズドテスト、9 ケース） |

### pid_registry GC（受入基準 10、Schneier #5、確定 E）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-PF-010 | `_classify_row()` PID 衝突識別（確定 E） | 正常系 | `OrphanProcessFactory` / `ProtectedProcessFactory` / `NoSuchProcessFactory` / `AccessDeniedProcessFactory` の 4 ケース | 順に `'orphan_kill'` / `'protected'` / `'absent'` / WARN ログ判定（受入基準 10） |
| TC-UT-PF-026 | protected 判定では DELETE のみ kill しない | 正常系 | `ProtectedProcessFactory`（PID 再利用された別プロセス） | `_kill_descendants` が**呼ばれない**ことを assert（mock の call_count == 0）、テーブルから DELETE のみ実行（OWASP T4 / 他プロジェクト誤射防止） |
| TC-UT-PF-027 | AccessDenied で WARN + 行残し | 異常系 | `AccessDeniedProcessFactory` | WARN ログに MSG-PF-007（`[WARN] pid_registry GC: psutil.AccessDenied for pid={pid}, retry next cycle`）出力、テーブルから DELETE しない（次回 GC で再試行） |
| TC-UT-PF-028 | 子孫追跡 + SIGTERM/grace/SIGKILL 順序 | 正常系 | `OrphanProcessFactory`（`children(recursive=True)` で 3 子孫を返す mock）+ `freezegun` | 各子孫 + 親に対し `terminate()` 呼び出し → 5 秒進める → `is_running()` で残存確認 → 残っていれば `kill()` 呼び出し の順序が観測される（確定 E）。**`recursive=True` が抜けないこと**を物理確認 |

### Bootstrap / 起動シーケンス（受入基準 12、確定 G）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-PF-030 | Windows での chmod スキップ | 正常系 | `monkeypatch.setattr('platform.system', lambda: 'Windows')` | `os.chmod` が呼ばれずに `attachment_root.ensure_root()` が成功（POSIX 限定機能の条件分岐が動作） |
| TC-UT-PF-034 | engine 初期化失敗の文言（MSG-PF-002 文言照合） | 異常系 | engine create で例外を仕込む（disk full simulator 等） | `BakufuConfigError`、message が `[FAIL] SQLite engine initialization failed: {reason}` 完全一致 |
| TC-UT-PF-001-A | **`os.umask(0o077)` が最初に SET される**（確定 L、Schneier 中等 1） | 正常系 | `monkeypatch.setattr('os.umask', mock_umask)` で `os.umask` を mock | (1) `Bootstrap.run()` を呼ぶ、(2) `mock_umask.call_args_list[0]` が `call(0o077)` 完全一致（**最初の文で呼ばれる**ことを物理確認）、(3) stage 1（DATA_DIR resolve）の処理開始より前に umask SET が発火、(4) Windows 環境では `os.umask` が no-op として動作することを `monkeypatch.setattr('platform.system', lambda: 'Windows')` 経路で確認（条件分岐は不要、`os.umask` が常に呼ばれる設計だが Windows で意味を持たない） |

### `extra='forbid'` / frozen など pydantic 規約は本 feature では適用外（infrastructure 層は domain と異なり Pydantic model を持たない、SQLAlchemy ORM が中心）

## CI スクリプト（開発者品質基準 Q-3）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-CI-PF-001 | 依存方向検査（確定 I） | CI script | `grep -rn 'from bakufu.infrastructure' backend/src/bakufu/domain/` を実行 | 空（マッチゼロ）。さらに `tests/architecture/test_dependency_direction.py` で `bakufu.domain.*` の全モジュールを import し、`bakufu.infrastructure.*` の名前が module 属性に含まれないことを検証 |

## カバレッジ基準

- REQ-PF-001 〜 010 + REQ-PF-002-A の各要件が**最低 1 件**のテストケースで検証されている（マトリクス参照）
- **Schneier 申し送り 4 項目（#1 / #4 / #5 / #6）すべてに integration テスト**:
  - #1: TC-UT-PF-002 + TC-IT-PF-001 + TC-UT-PF-033 / 038 / 039 / 040
  - #4: TC-IT-PF-005（DELETE 拒否）+ TC-IT-PF-015（UPDATE 制限）
  - #5: TC-UT-PF-010, 026, 027, 028 + TC-IT-PF-011 (file mode) + **TC-IT-PF-001-A**（umask 経由 WAL/SHM 0o600 の物理保証）
  - #6: TC-IT-PF-007（ORM）+ **TC-IT-PF-020（raw SQL 経路、R1-D 中核）** + TC-IT-PF-021 (UPDATE 経路) + TC-IT-PF-022（audit_log / pid_registry 配線）+ **TC-UT-PF-006-A / B / C**（Fail-Secure 3 種）+ **TC-IT-PF-007-D**（env 辞書ロード Fail Fast）
- **Schneier 再レビュー指摘の検出力テスト 20 件**（重大 4 + 中等 4 + Forensic 観点）:
  - 重大 1（Fail-Secure 契約、確定 F）: TC-UT-PF-006-A / B / C + TC-IT-PF-007-D（**生データを書く経路ゼロの物理保証**、本 PR の中核セキュリティ契約）
  - 重大 2（PRAGMA defensive、確定 D-1〜D-4）: TC-IT-PF-003-A / B / C / D（**DROP TRIGGER / sqlite_master UPDATE が application engine 経由で拒否される、dual connection で migration engine が runtime に生存しない**）
  - 重大 3（DB 権限検出 Forensic、REQ-PF-002-A）: TC-IT-PF-002-A / B / C（**WARN + 修復 + 続行で Forensic 痕跡を消さない**）
  - 重大 4（`BAKUFU_DB_PATH` 廃止）: 攻撃面の物理排除（環境変数自体を撤去）
  - 中等 1（umask、確定 L）: TC-IT-PF-001-A + TC-UT-PF-001-A（**Bootstrap.run() の最初の文で os.umask(0o077)**）
  - 中等 2（`BAKUFU_DB_KEY` 削除）: 攻撃面の物理排除（masking 対象 env キーから除外）
  - 中等 3（空 handler Fail Loud、確定 K）: TC-IT-PF-008-A / B / C / D
  - 中等 4（Bootstrap cleanup LIFO、確定 J）: TC-IT-PF-012-A / B / C
- **イーロン指示の中核「raw SQL 経路でも masking が回避不能」を TC-IT-PF-020 で物理確認**（TypeDecorator `process_bind_param` の Core / ORM 両経路発火 = §確定 R1-D の根拠を test で凍結。将来誰かが TypeDecorator → event listener 方式に戻そうとすると本テストが赤くなる退行検出）
- **PRAGMA 強制（確定 D-1）**: **8 件 PRAGMA**（WAL / foreign_keys / busy_timeout / synchronous / temp_store / **defensive=ON** / **writable_schema=OFF** / **trusted_schema=OFF**）+ 順序（WAL 先頭）+ 毎接続適用を TC-IT-PF-003 + TC-IT-PF-013 + TC-IT-PF-003-A で確認
- **起動シーケンス凍結（確定 G + J + L）**: 順序実行 + INFO 構造化ログ + Fail Fast + 段階 4 のみ非 fatal + LIFO cleanup + umask SET を TC-IT-PF-012 / 012-A / 012-B / 012-C / 031 / 032 / 001-A / TC-UT-PF-001-A で確認
- **masking 適用順序（確定 A）**: Anthropic → OpenAI 順序を TC-UT-PF-016 で、長さ 8 未満除外を TC-UT-PF-017 で、Fail-Secure フォールバック（確定 F の 3 種）を TC-UT-PF-006-A / B / C で確認（masking が**生データを永続化させない**物理保証）
- **依存方向（確定 I）**: domain → infrastructure 参照ゼロを TC-CI-PF-001 で確認
- **MSG-PF-001 〜 008** の各文言が**静的文字列で照合**されている（MSG-PF-008 は Schneier 重大 1 対応で新規追加、TC-IT-PF-007-D で照合）
- 受入基準 1 〜 12 の各々が**最低 1 件のユニット/結合ケース**で検証されている（E2E 不在のため戦略ガイドの「結合代替可」に従う）
- 開発者品質基準 Q-1（pyright/ruff）/ Q-2（カバレッジ 90%）/ Q-3（依存方向 CI 検査）は CI ジョブで担保
- **T1〜T9** の各脅威に対する対策が**最低 1 件のテストケース**で有効性を確認されている（T6〜T9 は threat-model.md §A4 への昇格に同期）
- 確定 A〜L すべてに証拠ケース（確定 D-1〜D-4 / F / J / K / L は Schneier 再レビューで新規凍結）
- C0 目標: `infrastructure/persistence/sqlite/` / `infrastructure/security/` で **90% 以上**（infrastructure 層基準、要件分析書 §非機能要求準拠）

## 人間が動作確認できるタイミング

本 feature は infrastructure 層単独だが、**Backend プロセスを実起動して動作確認できる**。

- CI 統合後: `gh pr checks` で 7 ジョブ緑（lint / typecheck / test-backend / audit / fmt / commit-msg / no-ai-footer）
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/infrastructure/ -v` → 全テスト緑
- Backend 実起動: `cd backend && uv run python -m bakufu`（環境変数 `BAKUFU_DATA_DIR=/tmp/bakufu-test` を設定）
  - 起動時に DATA_DIR / engine / Alembic / pid_gc / attachments / dispatcher の各段階ログを目視
  - `<DATA_DIR>/bakufu.db` が 0600 で作成されていることを `ls -l` で確認
  - `<DATA_DIR>/attachments/` が 0700 で作成されていることを `ls -ld` で確認
  - `sqlite3 <DATA_DIR>/bakufu.db ".tables"` で 3 テーブル + 2 トリガが見えることを目視
  - `sqlite3 <DATA_DIR>/bakufu.db "DELETE FROM audit_log;"` が `Runtime error: audit_log is append-only` で拒否されることを目視（Schneier #4 物理確認）
  - `BAKUFU_DATA_DIR=./relative` で起動 → 即時 exit 1 + stderr に MSG-PF-001（Schneier #1 物理確認）
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.infrastructure --cov-report=term-missing` → 90% 以上
- masking 配線の実観測（手動試験）: 直接 `sqlite3` で `INSERT INTO domain_event_outbox(payload_json, ...) VALUES('sk-ant-api03-...')` を実行 → SELECT で生データのまま（**`sqlite3` CLI は SQLAlchemy TypeDecorator `process_bind_param` を経由しないため masking が走らない**）。これは bakufu アプリの信頼境界外で、**bakufu アプリ経由の INSERT のみが masking ゲートウェイを保証する**。本観測の意図は「DB 直挿しは TypeDecorator 配線を回避できる経路」を**運用者が認識する**ためで、防衛策としては OS file mode 0600 で他ユーザーからの DB アクセスを物理的に塞ぐ（threat-model.md §A4 / §T7）

後段で `feature/admin-cli`（`bakufu admin retry-event` 等）/ `feature/http-api`（Aggregate CRUD）が完成したら、本 feature の永続化基盤を経由して `curl` 経由の手動シナリオで E2E 観測可能になる。

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      __init__.py
      psutil_process.py        # PsutilProcessFactory / OrphanProcessFactory /
                               # ProtectedProcessFactory / AccessDeniedProcessFactory /
                               # NoSuchProcessFactory（schema 由来、_meta.synthetic=True）
      freezegun_clock.py       # FrozenClockFactory（freezegun ラッパー、_meta.synthetic=True）
      outbox_row.py            # OutboxRowFactory（PENDING / DISPATCHING / DEAD_LETTER）
      audit_log_row.py         # AuditLogRowFactory（result NULL / SUCCESS / FAILURE）
      pid_registry_row.py      # PidRegistryRowFactory
      masking_payload.py       # MaskingPayloadFactory（9 種秘密情報埋め込み）
    fixtures/
      characterization/
        raw/
          psutil_process_states.json   # マスク済み実観測（Process.create_time / children / exception 形状）
        schema/
          psutil_process_schema.json   # 型 + 統計（factory のソース）
    characterization/
      conftest.py              # RUN_CHARACTERIZATION=1 でのみ実行する fixture 制御
      capture_psutil_states.py # raw + schema を生成する characterization スクリプト
    architecture/
      test_dependency_direction.py     # domain → infrastructure 参照ゼロを検証（確定 I）
    infrastructure/
      __init__.py
      config/
        test_data_dir.py                       # TC-UT-PF-001, 002, 033, 038, 039, 040
      security/
        test_masking.py                        # TC-UT-PF-006, 016, 017, 018, 019, 041, 042
        test_masking_fail_secure.py            # TC-UT-PF-006-A, 006-B, 006-C (Schneier 重大 1, 確定 F の中核)
      persistence/
        sqlite/
          test_engine_pragma.py                # TC-IT-PF-003, 013
          test_engine_defensive.py             # TC-IT-PF-003-A, 003-B, 003-C, 003-D (Schneier 重大 2, 確定 D-1〜D-4)
          test_db_permission.py                # TC-IT-PF-002-A, 002-B, 002-C (Schneier 重大 3, REQ-PF-002-A)
          test_session.py                      # TC-IT-PF-014
          test_alembic_init.py                 # TC-IT-PF-004, 035
          test_audit_log_trigger.py            # TC-IT-PF-005, 015 (Schneier #4)
          test_pid_gc.py                       # TC-UT-PF-010, 026, 027, 028 (Schneier #5)
          test_attachment_root.py              # TC-IT-PF-011, 029, TC-UT-PF-030 (Schneier #5)
          outbox/
            test_dispatcher.py                 # TC-IT-PF-008, 023, 009, 024, 025
            test_dispatcher_fail_loud.py       # TC-IT-PF-008-A, 008-B, 008-C, 008-D (Schneier 中等 3, 確定 K)
            test_masking_typedecorator.py      # TC-IT-PF-007, 020, 021, 022 (Schneier #6 / R1-D 中核、TypeDecorator process_bind_param 配線、旧 listener 方式は BUG-PF-001 で反転却下)
            test_masking_env_fail_fast.py      # TC-IT-PF-007-D (Schneier 重大 1, MSG-PF-008)
      test_bootstrap_sequence.py               # TC-IT-PF-012, 031, 032, 034, TC-IT-PF-036, 037
      test_bootstrap_cleanup.py                # TC-IT-PF-012-A, 012-B, 012-C (Schneier 中等 4, 確定 J)
      test_bootstrap_umask.py                  # TC-IT-PF-001-A, TC-UT-PF-001-A (Schneier 中等 1, 確定 L)
```

**配置の根拠**:
- 戦略ガイド §テストディレクトリ構造 の Python 標準慣習に従う
- characterization は本流 CI から除外（`RUN_CHARACTERIZATION=1` 環境変数で明示有効化）
- factory は schema を参照して生成、raw fixture は integration test 専用（unit でも factory を介して同 schema から派生）
- architecture/test_dependency_direction.py は確定 I の物理保証（domain → infrastructure 参照ゼロ）
- `test_masking_typedecorator.py` を**独立ファイル**にするのはイーロン指示の核心テスト群（raw SQL 経路含む）を 1 ファイルに集約し、レビュー時の確認帯域を最小化するため。TypeDecorator 配線採用は §確定 R1-D（旧 listener 案を BUG-PF-001 で反転却下）

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| TBD-PF-1 | psutil の characterization fixture（raw + schema 生成） | Issue: 本 PR 着手と同時に作成、PR #21 内で完了させる | `psutil.Process.create_time()` の戻り値型・精度、`children(recursive=True)` の戻り値構造、`NoSuchProcess` / `AccessDenied` の例外形状を実観測。CPython + psutil 既定値で取得し `_meta.captured_at` / `psutil_version` を埋める。CI で 30 日鮮度検証 |
| TBD-PF-2 | freezegun ベースの clock factory（`OutboxRowFactory.next_attempt_at` / `updated_at` を確定的に進める） | Issue: 本 PR 着手と同時に作成、PR #21 内で完了させる | `_meta.synthetic=True` を付与、本流 CI 通常実行で常時利用 |
| TBD-PF-3（後続 PR） | Aggregate 別 Repository の characterization（`Persona.prompt_body` / `PromptKit.prefix_markdown` の Repository 永続化前マスキング） | `feature/agent-repository` / `feature/room-repository` 起票時 | hook 構造のみ本 PR で確定、実適用は後続 PR で characterization と同時実装 |

**Schneier 申し送り 6 項目の本 PR / 後続 PR ステータス（確定 H 再掲）**:

| # | 項目 | 本 PR | 後続 PR | テスト責務 |
|---|---|---|---|---|
| 1 | `BAKUFU_DATA_DIR` 絶対パス | ✓ | — | TC-UT-PF-002, TC-IT-PF-001, TC-UT-PF-033 / 038 / 039 / 040 |
| 2 | H10 TOCTOU | ✗ | `feature/skill-loader` | 後続 feature の test-design.md で TOCTOU race 対策の検出力テストを起票（本 PR の対象外） |
| 3 | `Persona.prompt_body` Repository マスキング | △ hook 構造のみ | `feature/agent-repository` | TC-IT-PF-022 で `audit_log` / `pid_registry` の hook 動作を確認（`agents` テーブルへの listener 登録は後続 PR で起票） |
| 4 | `audit_log` DELETE 拒否 | ✓ | — | TC-IT-PF-005, TC-IT-PF-015 |
| 5 | `bakufu_pid_registry` 0600 + GC | ✓ + LLM Adapter は後続 | `feature/llm-adapter` | TC-UT-PF-010, 026, 027, 028 + TC-IT-PF-011 |
| 6 | Outbox `payload_json` / `last_error` マスキング | ✓ | — | TC-IT-PF-007, **TC-IT-PF-020 (raw SQL 経路、イーロン指示の核心)**, TC-IT-PF-021, TC-IT-PF-022 |

**本 feature 固有の申し送り**:

- **TBD-PF-1（psutil characterization）が unit / integration 実装の前提**: assumed mock の `psutil.Process` は OS 依存の戻り値型・精度を仮定で書くと PID 衝突対策の検出力ゼロのテストになる。本 PR の冒頭で characterization を完了させてから unit に着手する（順序: characterization → factory → unit / integration）
- **freezegun の固定時刻**: Outbox dispatcher の backoff スケジュール（10s / 1m / 5m / 30m / 30m）と DISPATCHING リカバリ（5 分超過判定）は実時刻依存テストにすると flaky になる。`FrozenClockFactory` で確定的に進める
- **POSIX 限定機能の条件分岐**: file mode 0600 / 0700 は POSIX のみ。Windows では `os.chmod` をスキップする（TC-UT-PF-030）。Windows CI を持たない場合は手動確認の申し送り
- **`sqlite3` CLI 経由の DB 直挿し経路は SQLAlchemy listener を経由しない**: これは「OS file mode 0600 で他ユーザーからの DB アクセスを物理的に塞ぐ」防衛で対処する範囲。本 feature の責務外だが、運用者が認識すべき信頼境界の境界線（threat-model.md §T5 と整合）

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-PF-001〜010 + REQ-PF-002-A すべてに 1 件以上のテストケースがあり、特に integration が結合シナリオを単独でカバーしている
- [ ] **Schneier 申し送り 4 項目（#1 / #4 / #5 / #6）すべてに integration テスト**が起票され、unit のみで終わっていない
- [ ] **イーロン指示の核心「raw SQL 経路でも masking listener が回避不能」が TC-IT-PF-020 で実 SQLite に対し物理確認されている**（`session.execute(insert(table).values(...))` 経路で listener が走り masking 適用済み値で永続化されるか）
- [ ] **Schneier 重大 1（Fail-Secure 契約、確定 F）の検出力**: TC-UT-PF-006-A / B / C で **`<REDACTED:MASK_ERROR>` / `<REDACTED:MASK_OVERFLOW>` / `<REDACTED:LISTENER_ERROR>` の 3 種完全置換**が物理確認、TC-IT-PF-007-D で env 辞書ロード失敗時の Fail Fast（MSG-PF-008、Bootstrap exit 1）が確認
- [ ] **Schneier 重大 2（PRAGMA defensive、確定 D-1〜D-4）の検出力**: TC-IT-PF-003-A（defensive=ON SET）/ **TC-IT-PF-003-B（DROP TRIGGER 拒否）** / TC-IT-PF-003-C（sqlite_master UPDATE 拒否）/ TC-IT-PF-003-D（dual connection の dispose）すべてが実 SQLite に対し物理確認
- [ ] **Schneier 重大 3（DB 権限検出 Forensic、REQ-PF-002-A）の検出力**: TC-IT-PF-002-A / B / C で WARN + 修復 + 続行 + WAL/SHM 適用が確認、`prior unauthorized access` の hint 文字列が WARN ログに含まれる
- [ ] **Schneier 中等 1（umask、確定 L）の検出力**: TC-IT-PF-001-A（WAL/SHM 0o600 物理保証）+ TC-UT-PF-001-A（`Bootstrap.run()` の最初の文で `os.umask(0o077)` の call_args 確認）
- [ ] **Schneier 中等 3（空 handler Fail Loud、確定 K）の検出力**: TC-IT-PF-008-A / B / C / D で起動完了直後 WARN + polling サイクル WARN + 重複抑止 + 滞留閾値 100 件超 WARN すべてが確認
- [ ] **Schneier 中等 4（Bootstrap cleanup LIFO、確定 J）の検出力**: TC-IT-PF-012-A（dispatcher cancel 単独）+ **TC-IT-PF-012-B（dispatcher + scheduler の LIFO cancel）** + TC-IT-PF-012-C（engine.dispose() 保証）
- [ ] `audit_log` DELETE 拒否 + UPDATE 制限の SQLite トリガが**実 raw SQL** で発火することが TC-IT-PF-005 / 015 で確認されている
- [ ] **PRAGMA 8 件**すべて + 順序（WAL 先頭、確定 D-1）が TC-IT-PF-003 / 013 / 003-A で実 engine に対し確認されている（旧 5 件から **`defensive=ON` / `writable_schema=OFF` / `trusted_schema=OFF` の 3 件追加**）
- [ ] pid_gc の `protected` 判定が「DELETE のみで kill しない」（TC-UT-PF-026）+ `AccessDenied` の WARN + 行残し（TC-UT-PF-027）+ 子孫追跡 `recursive=True`（TC-UT-PF-028）すべてが網羅されている
- [ ] 起動シーケンス 8 段階（確定 G）が順序実行（TC-IT-PF-012）+ Fail Fast（TC-IT-PF-031）+ 段階 4 のみ非 fatal（TC-IT-PF-032）+ INFO 構造化ログで網羅されている
- [ ] masking 適用順序（Anthropic → OpenAI、TC-UT-PF-016）+ 環境変数長さ閾値 8（TC-UT-PF-017）+ Fail-Secure 3 種（TC-UT-PF-006-A / B / C）が独立して検証されている
- [ ] 依存方向（確定 I）が CI script（TC-CI-PF-001）+ test_dependency_direction.py の両方で物理保証されている
- [ ] **TBD-PF-1（psutil characterization）が本 PR 内で完了する計画**になっており、assumed mock 禁止規約に違反しない
- [ ] freezegun の clock factory（TBD-PF-2）が backoff / リカバリ判定テストの flaky 化を防ぐ設計になっている
- [ ] **MSG-PF-001〜008** の文言が静的文字列で照合される設計になっている（MSG-PF-008 は新規）
- [ ] 確定 A〜L すべてに証拠ケースが含まれる
- [ ] **T1〜T9** の各脅威への有効性確認ケースが含まれている（T6〜T9 は threat-model.md §A4 の昇格に同期）
- [ ] 結合シナリオ（TC-IT-PF-036 / 037）が「Backend 起動 → 永続化 → Outbox → Dispatcher → masking 適用済み永続化 → クラッシュリカバリ」を一連で確認できる
- [ ] empire / workflow / agent / room の WeakValueDictionary レジストリ方式と整合した factory 設計になっている
