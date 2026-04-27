# テスト設計書

<!-- feature: persistence-foundation -->
<!-- 配置先: docs/features/persistence-foundation/test-design.md -->
<!-- 対象範囲: REQ-PF-001〜010 / MSG-PF-001〜007 / 脅威 T1〜T5 / 受入基準 1〜15 / 詳細設計 確定 A〜I / Schneier 申し送り 4 項目 (#1 / #4 / #5 / #6) の結合テスト + masking listener が raw SQL 経路でも回避不能であることの物理保証 -->

本 feature は infrastructure 層の永続化基盤（DataDirResolver / SqliteEngine / SessionFactory / MaskingGateway / Outbox 系 / PidRegistryGC / AttachmentRoot / Bootstrap）に閉じる。Aggregate 別 Repository 本体は範囲外（後続 `feature/{aggregate}-repository` PR 群の責務）。HTTP API / CLI / UI の公開エントリポイントは持たないため、E2E は本 feature 範囲外（後続 `feature/admin-cli` / `feature/http-api` で起票）。

**本 feature のテストの主役は結合（integration）**である。理由は以下:

1. 永続化基盤の真価は **「呼び忘れ経路でもマスキングが効く」「DB 直 SQL でも `audit_log` DELETE が拒否される」「PRAGMA が毎接続適用される」「起動シーケンス 8 段階の順序が保証される」**といった**物理保証**にあり、unit でモックして検証すると本物の挙動を見失う
2. SQLite / Alembic / SQLAlchemy event listener / psutil / ファイルシステムは**本物を使えるなら本物を使う**（戦略ガイド §結合テスト方針: DB は実接続）
3. unit でモックするのは**単体ロジック**（regex 適用順序 / DataDirResolver の OS 別既定 / pid_gc の判定ロジック）に絞る

イーロン指示の **「Schneier 申し送り 4 項目（#1 / #4 / #5 / #6）の結合テスト + masking listener が raw SQL 経路でも回避不能であることのテスト」** は本 feature の中核として **integration（実 SQLite + 実ファイルシステム）** で網羅する。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-PF-001 | `data_dir.resolve()` 未設定時 OS 別既定 | TC-UT-PF-001 | ユニット | 正常系 | 1 |
| REQ-PF-001 | `data_dir.resolve()` 相対パス Fail Fast | TC-UT-PF-002 | ユニット | 異常系 | 2 |
| REQ-PF-001（Schneier #1） | `BAKUFU_DATA_DIR` 絶対パス強制（NUL バイト / `..` / 相対の網羅） | TC-UT-PF-002, TC-IT-PF-001 | ユニット / 結合 | 異常系 | 2 |
| REQ-PF-002 | engine 接続時 PRAGMA 5 件適用 | TC-IT-PF-003 | 結合 | 正常系 | 3 |
| REQ-PF-002（PRAGMA 順序、確定 D） | `journal_mode=WAL` を最初に SET | TC-IT-PF-013 | 結合 | 正常系 | 3 |
| REQ-PF-003 | AsyncSession factory + `async with session.begin()` | TC-IT-PF-014 | 結合 | 正常系 | （UoW 境界の動作確認） |
| REQ-PF-004 | Alembic 初回 revision で 3 テーブル + 2 トリガ | TC-IT-PF-004 | 結合 | 正常系 | 4 |
| REQ-PF-004（Schneier #4） | `audit_log` DELETE 拒否トリガ実発火 | TC-IT-PF-005 | 結合 | 異常系 | 5 |
| REQ-PF-004（Schneier #4） | `audit_log` UPDATE 制限トリガ（result NOT NULL 行への UPDATE 拒否） | TC-IT-PF-015 | 結合 | 異常系 | 5 |
| REQ-PF-005 | masking 9 種正規表現 + 環境変数 + ホームパス、適用順序込み | TC-UT-PF-006 | ユニット | 正常系 | 6 |
| REQ-PF-005（適用順序、確定 A） | OpenAI regex が `sk-ant-` を除く（Anthropic 先適用） | TC-UT-PF-016 | ユニット | 境界値 | 6 |
| REQ-PF-005（環境変数長さ） | 長さ 8 未満の env 値はパターン化しない | TC-UT-PF-017 | ユニット | 境界値 | 6 |
| REQ-PF-005（フォールバック、確定 F） | 想定外型・regex 例外時の `<REDACTED:UNKNOWN>` フォールバック | TC-UT-PF-018 | ユニット | 異常系 | 6 |
| REQ-PF-005（再帰走査） | dict / list の再帰 masking | TC-UT-PF-019 | ユニット | 正常系 | 6 |
| REQ-PF-006（Schneier #6） | `domain_event_outbox` への ORM 経由 INSERT で payload_json / last_error がマスキング後値に上書き | TC-IT-PF-007 | 結合 | 正常系 | 7 |
| REQ-PF-006（Schneier #6 / R1-D 中核） | **raw SQL 経路（`session.execute(insert(table).values(...))`）でも listener が走り masking 後値で永続化される** | TC-IT-PF-020 | 結合 | 正常系 | 7 |
| REQ-PF-006（Schneier #6） | `before_update` でも payload_json / last_error が再マスキングされる（dispatcher の dead-letter 化経路） | TC-IT-PF-021 | 結合 | 正常系 | 7 |
| REQ-PF-006（Schneier #6） | `audit_log.args_json` / `error_text` / `bakufu_pid_registry.cmd` のマスキング配線（hook 動作確認） | TC-IT-PF-022 | 結合 | 正常系 | 7 |
| REQ-PF-007 | Outbox Dispatcher polling SQL の取得条件 | TC-IT-PF-008 | 結合 | 正常系 | 8 |
| REQ-PF-007（DISPATCHING リカバリ） | `(DISPATCHING AND updated_at < now - 5min)` 行が再取得される | TC-IT-PF-023 | 結合 | 正常系 | 8 |
| REQ-PF-007（dead-letter 化） | 5 回失敗で `status=DEAD_LETTER` + `OutboxDeadLettered` event 別行追記 | TC-IT-PF-009 | 結合 | 異常系 | 9 |
| REQ-PF-007（backoff スケジュール） | attempt_count 1〜5 の next_attempt_at が表通り（10s / 1m / 5m / 30m / 30m） | TC-IT-PF-024 | 結合 | 正常系 | 9 |
| REQ-PF-007（Handler 未登録） | `HandlerNotRegisteredError` で行が再 PENDING に戻る | TC-IT-PF-025 | 結合 | 異常系 | 9 |
| REQ-PF-008（Schneier #5） | pid_registry GC: `psutil.create_time()` で PID 衝突識別（mock psutil でケース網羅） | TC-UT-PF-010 | ユニット | 正常系 | 10 |
| REQ-PF-008（Schneier #5） | pid_registry GC: `protected` 判定では DELETE のみで kill しない | TC-UT-PF-026 | ユニット | 正常系 | 10 |
| REQ-PF-008（Schneier #5） | pid_registry GC: `psutil.AccessDenied` で WARN ログ + 行残し（次回 GC 再試行） | TC-UT-PF-027 | ユニット | 異常系 | 10 |
| REQ-PF-008（Schneier #5） | pid_registry GC: 子孫追跡 `recursive=True` + SIGTERM → 5s grace → SIGKILL の順序 | TC-UT-PF-028 | ユニット | 正常系 | 10 |
| REQ-PF-009 | アタッチメント FS ルート 0700 で作成（POSIX） | TC-IT-PF-011 | 結合 | 正常系 | 11 |
| REQ-PF-009 | アタッチメント FS ルートの mkdir 失敗 → MSG-PF-003 | TC-IT-PF-029 | 結合 | 異常系 | （MSG-PF-003） |
| REQ-PF-009（Windows 互換） | Windows では chmod なしでも作成成功（POSIX 限定機能の条件分岐） | TC-UT-PF-030 | ユニット | 正常系 | （可搬性） |
| REQ-PF-010（確定 G） | 起動シーケンス 8 段階順序実行 | TC-IT-PF-012 | 結合 | 正常系 | 12 |
| REQ-PF-010（確定 G） | 各段階失敗時に後続が走らない（Fail Fast） | TC-IT-PF-031 | 結合 | 異常系 | 12 |
| REQ-PF-010（確定 G の例外） | 段階 4（pid_registry GC）失敗は非 fatal、後続が走る | TC-IT-PF-032 | 結合 | 正常系 | 12 |
| 確定 I（依存方向） | `domain` 層から `bakufu.infrastructure.*` への import ゼロ件 | TC-CI-PF-001 | CI script | — | 13 |
| AC-14（lint/typecheck） | `pyright --strict` / `ruff check` | （CI ジョブ） | — | — | 14 |
| AC-15（カバレッジ） | `pytest --cov=bakufu.infrastructure.persistence.sqlite --cov=bakufu.infrastructure.security` | （CI ジョブ） | — | — | 15 |
| MSG-PF-001 | `[FAIL] BAKUFU_DATA_DIR must be an absolute path (got: {value})` | TC-UT-PF-033 | ユニット | 異常系 | 2 |
| MSG-PF-002 | `[FAIL] SQLite engine initialization failed: {reason}` | TC-IT-PF-034 | 結合 | 異常系 | （文言照合） |
| MSG-PF-003 | `[FAIL] Attachment FS root initialization failed at {path}: {reason}` | TC-IT-PF-029 | 結合 | 異常系 | （文言照合） |
| MSG-PF-004 | `[FAIL] Alembic migration failed: {reason}` | TC-IT-PF-035 | 結合 | 異常系 | （文言照合） |
| MSG-PF-005 | SQLite トリガ raise message `audit_log is append-only` | TC-IT-PF-005 | 結合 | 異常系 | 5 |
| MSG-PF-005 | SQLite トリガ raise message `audit_log result is immutable once set` | TC-IT-PF-015 | 結合 | 異常系 | 5 |
| MSG-PF-006 | `[WARN] Masking gateway fallback applied: {kind}` | TC-UT-PF-018 | ユニット | 異常系 | 6 |
| MSG-PF-007 | `[WARN] pid_registry GC: psutil.AccessDenied for pid={pid}, retry next cycle` | TC-UT-PF-027 | ユニット | 異常系 | （文言照合） |
| 結合シナリオ 1 | Backend 起動 → Aggregate 永続化 → Outbox イベント生成 → Dispatcher 配送 → masking 適用済みで永続化されている | TC-IT-PF-036 | 結合 | 正常系 | 7, 8, 12 |
| 結合シナリオ 2 | クラッシュリカバリ: 起動時 GC で pid_registry 孤児削除 + Outbox DISPATCHING 行を 5 分経過後に再取得 | TC-IT-PF-037 | 結合 | 正常系 | 8 |

**マトリクス充足の証拠**:
- REQ-PF-001〜010 すべてに最低 1 件のテストケース
- **Schneier 申し送り 4 項目** すべてに **integration テスト**:
  - #1: `BAKUFU_DATA_DIR` 絶対パス強制 → TC-UT-PF-002 + TC-IT-PF-001
  - #4: `audit_log` DELETE 拒否トリガ + UPDATE 制限トリガ → TC-IT-PF-005 + TC-IT-PF-015
  - #5: `bakufu_pid_registry` GC + 0700 file mode → TC-UT-PF-010, 026, 027, 028 + TC-IT-PF-011
  - #6: Outbox masking listener → TC-IT-PF-007 + **TC-IT-PF-020（raw SQL 経路）** + TC-IT-PF-021 (before_update) + TC-IT-PF-022（audit_log / pid_registry 配線）
- **イーロン指示の中核「raw SQL 経路でも masking listener が回避不能」**を TC-IT-PF-020 で物理確認（確定 R1-D の根拠を test で凍結）
- **PRAGMA 強制（確定 D / E）**: 5 件全 PRAGMA + 順序（WAL 先頭）+ 毎接続適用を TC-IT-PF-003 + TC-IT-PF-013 で確認
- **起動シーケンス凍結（確定 G）**: 順序実行 + Fail Fast + 段階 4 のみ非 fatal を TC-IT-PF-012 / 031 / 032 で確認
- **masking 適用順序（確定 A）**: Anthropic 先 → OpenAI 後の順序維持を TC-UT-PF-016 で確認、長さ 8 未満は除外を TC-UT-PF-017 で確認
- **依存方向（確定 I）**: domain → infrastructure の参照ゼロを TC-CI-PF-001 (CI script) で物理確認
- MSG-PF-001〜007 すべてに静的文字列照合
- 受入基準 1〜13 すべてに unit/integration ケース（14/15 は CI ジョブ）
- T1〜T5（永続化前マスキング呼び忘れ / audit_log 改ざん / 相対 DATA_DIR / 孤児 kill 誤射 / SQLite 権限）すべてに有効性確認ケース
- 確定 A（masking 9 種 + env + home）/ B（listener 登録方式）/ C（SQLite トリガ）/ D（PRAGMA 順序）/ E（pid_gc 順序）/ F（masking フォールバック）/ G（起動シーケンス）/ H（Schneier 申し送りステータス）/ I（依存方向 CI 検査）すべてに証拠ケース
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

- 本 feature は infrastructure 層単独で、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない（[`requirements.md`](requirements.md) §画面・CLI 仕様 / §API 仕様 で「該当なし」と凍結）
- Bootstrap が起動する FastAPI / WebSocket リスナは段階 8 で「listening」に至るのみで、実 HTTP リクエストを処理する handler は本 PR の範囲外
- 戦略ガイド §E2E対象の判断「内部API・ライブラリなどエンドユーザー操作がない場合は結合テストで代替可」に従い、E2E は本 feature 範囲外
- 後続 `feature/admin-cli` / `feature/http-api` が公開 I/F を実装した時点で E2E（`bakufu admin retry-event` 等で実 SQLite に書き込み確認）を起票
- 受入基準 1〜13 はすべて unit/integration テストで検証可能（14/15 は CI ジョブ）

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
| TC-IT-PF-013 | SqliteEngine + PRAGMA 順序（確定 D） | tmp_path | engine 生成 + listener にログフックを差し込み | engine の `connect` event で発火された PRAGMA SET の順序を観測 | `journal_mode=WAL` が最初、続けて `foreign_keys=ON` / `busy_timeout=5000` / `synchronous=NORMAL` / `temp_store=MEMORY` の順 |
| TC-IT-PF-014 | SessionFactory + UoW 境界 | tmp_path bakufu.db | engine + session_factory 構築済み | `async with session_factory() as session, session.begin(): session.add(audit_log_row)` を実行 → ブロック退出で commit、ブロック内で例外 raise → ブロック退出で rollback | commit 経路で SELECT が値を返す、rollback 経路で SELECT が空 |
| TC-IT-PF-004 | Alembic 初回 revision | tmp_path bakufu.db + 本物の alembic | engine 構築済み | `alembic upgrade head` を実行 | `SELECT name FROM sqlite_master WHERE type='table'` で `audit_log` / `bakufu_pid_registry` / `domain_event_outbox` の 3 テーブルが存在、`type='trigger'` で `audit_log_no_delete` / `audit_log_update_restricted` の 2 トリガが存在（受入基準 4） |
| TC-IT-PF-035 | Alembic migration 失敗 | tmp_path + 故意に壊した revision script | upgrade head が例外を吐く設定 | `Bootstrap.run()` を呼ぶ | `BakufuMigrationError` が raise、`stderr` に `[FAIL] Alembic migration failed:` で始まるメッセージ（MSG-PF-004） |

### `audit_log` 改ざん拒否（Schneier #4、T2、受入基準 5）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-005 | SQLite トリガ + audit_log DELETE 拒否 | tmp_path + 初回 revision 適用済み | audit_log に 1 行 INSERT 済み | **raw SQL** で `DELETE FROM audit_log WHERE id=:id` を実行 | `sqlite3.IntegrityError`（または同等）が raise、`audit_log is append-only` 文言を含む（MSG-PF-005）。SELECT すると行は残ったまま（OWASP A08 / T2 物理保証） |
| TC-IT-PF-015 | SQLite トリガ + audit_log UPDATE 制限 | tmp_path + audit_log 1 行（result='SUCCESS' で確定済み） | result NOT NULL 行 | `UPDATE audit_log SET result='FAILURE' WHERE id=:id` を実行 | `sqlite3.IntegrityError` が raise、`audit_log result is immutable once set` 文言を含む。result NULL 行への UPDATE（result NULL → 'SUCCESS'）は通過することも併せて確認（実行完了時の唯一許可経路） |

### マスキング配線（Schneier #6、T1、受入基準 7）

**本 feature の中核。raw SQL 経路でも listener が走ることを物理保証する**（イーロン指示の核心）。

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-007 | Outbox listener + ORM 経路 | tmp_path + Alembic 適用済み | engine + session 構築済み | `MaskingPayloadFactory` で生成した `payload_json={'key': 'sk-ant-api03-' + 'A' * 50, 'github_pat': 'ghp_' + 'X' * 40, 'description': 'see /home/myuser/secret'}` を含む `domain_event_outbox` 行を `session.add()` で INSERT | `SELECT payload_json, last_error FROM domain_event_outbox` で取得した値で `sk-ant-api03-...` が `<REDACTED:ANTHROPIC_KEY>` に、`ghp_...` が `<REDACTED:GITHUB_PAT>` に、`/home/myuser/...` が `<HOME>/...` に置換されている（受入基準 7） |
| TC-IT-PF-020 | Outbox listener + **raw SQL 経路（R1-D 中核）** | tmp_path + Alembic 適用済み | engine + session 構築済み | **ORM mapper を経由しない経路** `session.execute(sqlalchemy.insert(outbox_table).values(payload_json='sk-ant-api03-' + 'A' * 50, last_error='ghp_' + 'X' * 40, ...))` で raw SQL 風に INSERT | listener が走り、SELECT で取得した値で `sk-ant-api03-...` が `<REDACTED:ANTHROPIC_KEY>` に、`ghp_...` が `<REDACTED:GITHUB_PAT>` に置換されている。**「呼び忘れ経路でもマスキングが効く」物理保証**（OWASP A02 / 確定 R1-D / event listener vs TypeDecorator の決定根拠を test で凍結） |
| TC-IT-PF-021 | Outbox listener + before_update | tmp_path + Outbox 行 1 件（PENDING） | dispatcher が dead-letter 化する経路をシミュレート | `UPDATE domain_event_outbox SET status='DEAD_LETTER', last_error='AKIA' + '1234567890ABCDEF1' WHERE event_id=:id` を実行 | `before_update` listener が走り、`last_error` が `<REDACTED:AWS_ACCESS_KEY>` で永続化される。`payload_json` も同じ行で再マスキング適用される（idempotent: 既マスキング済み値は再適用しても変化しない） |
| TC-IT-PF-022 | audit_log + pid_registry の masking 配線（hook 動作確認） | tmp_path + Alembic 適用済み | engine + session 構築済み | `audit_log.args_json={'token': 'xoxb-1234567890-...'}` / `error_text='Bearer eyJ...token...'` および `bakufu_pid_registry.cmd='claude --api-key=sk-ant-api03-...'` を INSERT | `SELECT` で取得した各値が `<REDACTED:SLACK_TOKEN>` / `<REDACTED:BEARER>` / `<REDACTED:ANTHROPIC_KEY>` に置換されている（Schneier #6 の hook 構造が 3 テーブル全てに動作することを物理確認） |

### Outbox Dispatcher（受入基準 8, 9）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-008 | Dispatcher polling SQL | tmp_path + Outbox 行（PENDING で `next_attempt_at <= now`、PENDING で `next_attempt_at > now`、DISPATCHED、DEAD_LETTER の 4 行） + freezegun 固定時刻 | dispatcher を 1 サイクル走らせる | polling SQL の取得結果を assert | PENDING で `next_attempt_at <= now` の 1 行のみ取得される。他 3 行は対象外 |
| TC-IT-PF-023 | Dispatcher DISPATCHING リカバリ | tmp_path + Outbox 行（DISPATCHING で `updated_at < now - 5min`、DISPATCHING で `updated_at < now - 4min`） + freezegun | dispatcher を 1 サイクル走らせる | 取得結果を assert | 5 分超過の 1 行のみ取得（4 分のものは未取得）、強制 PENDING 戻しは行わず DISPATCHING のまま再取得 → handler 再呼び出し |
| TC-IT-PF-009 | Dispatcher dead-letter 化 | tmp_path + 5 回失敗する Handler を register + Outbox 行（PENDING） + freezegun（backoff 経過させる） | dispatcher を 6 サイクル走らせる（attempt_count を 1 → 6 に進める） | DB 状態 + 別行の追記 | 元行が `status=DEAD_LETTER`、`attempt_count=5` で確定。さらに別行として `event_kind='OutboxDeadLettered'`、`payload_json` に元 event_id 参照、`status=PENDING` の dead-letter 専用 event が追記される（受入基準 9） |
| TC-IT-PF-024 | backoff スケジュール | tmp_path + 失敗 Handler + Outbox 行 + freezegun | attempt_count 1〜5 の各時点で polling 再走 | `next_attempt_at` の値を assert | attempt_count 1 で +10s、2 で +1m、3 で +5m、4 で +30m、5 で +30m（events-and-outbox.md §Retry 戦略 と同一） |
| TC-IT-PF-025 | Handler 未登録時の挙動 | tmp_path + Outbox 行（`event_kind='UnregisteredKind'`） | handler レジストリが空 | dispatcher を 1 サイクル走らせる | `HandlerNotRegisteredError` を catch、行は `status=PENDING` に戻る + WARN ログ。dispatcher 自身は終了しない |

### アタッチメント FS ルート（受入基準 11、Schneier #5 file mode 補完）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-011 | AttachmentRootInitializer + POSIX file mode | tmp_path（POSIX 環境） | DATA_DIR が tmp_path 配下 | `attachment_root.ensure_root()` を呼ぶ | `<DATA_DIR>/attachments/` が存在、`os.stat().st_mode & 0o777 == 0o700`（受入基準 11）。Linux/macOS で実 chmod 検証 |
| TC-IT-PF-029 | mkdir 失敗（権限不足） | tmp_path + 親ディレクトリを 0500 にして書き込み禁止 | `<DATA_DIR>` が書き込み禁止 | `attachment_root.ensure_root()` を呼ぶ | `BakufuConfigError` が raise、文言 `[FAIL] Attachment FS root initialization failed at {path}: {reason}`（MSG-PF-003） |

### 起動シーケンス順序保証（確定 G、受入基準 12）

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-PF-012 | Bootstrap 8 段階順序 | tmp_path + 全段階成功する設定 | 各段階に呼び出しログを差し込む | `Bootstrap.run()` を呼ぶ | ログから (1) DATA_DIR resolve → (2) engine init → (3) Alembic upgrade → (4) pid_gc → (5) attachments → (6) outbox dispatcher → (7) attachment GC scheduler → (8) FastAPI listener の順序通り実行が観測される（確定 G） |
| TC-IT-PF-031 | 段階失敗時の Fail Fast | tmp_path + 段階 2（engine init）で例外を仕込む | engine 生成が失敗する | `Bootstrap.run()` を呼ぶ | `BakufuConfigError(MSG-PF-002)` で raise、stderr へ出力、後続段階 3〜8 が**実行されないこと**をログ非出現で確認 |
| TC-IT-PF-032 | 段階 4（pid_gc）失敗の非 fatal | tmp_path + pid_gc で psutil.AccessDenied を全件返す mock | pid_gc が WARN 出力 | `Bootstrap.run()` を呼ぶ | WARN ログ出力 + 段階 5〜8 が継続実行される（確定 G の段階 4 のみ非 fatal 例外） |

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
| TC-UT-PF-018 | フォールバック（確定 F） | 異常系 | 想定外の型（`bytes` / `datetime`）を `mask_in()` に渡す + regex compile 失敗を mock | `<REDACTED:UNKNOWN>` でフォールバック、WARN ログに MSG-PF-006（`[WARN] Masking gateway fallback applied: {kind}`）出力。masking が**例外を投げない契約**を物理確認 |
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

### `extra='forbid'` / frozen など pydantic 規約は本 feature では適用外（infrastructure 層は domain と異なり Pydantic model を持たない、SQLAlchemy ORM が中心）

## CI スクリプト（受入基準 13）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-CI-PF-001 | 依存方向検査（確定 I） | CI script | `grep -rn 'from bakufu.infrastructure' backend/src/bakufu/domain/` を実行 | 空（マッチゼロ）。さらに `tests/architecture/test_dependency_direction.py` で `bakufu.domain.*` の全モジュールを import し、`bakufu.infrastructure.*` の名前が module 属性に含まれないことを検証 |

## カバレッジ基準

- REQ-PF-001 〜 010 の各要件が**最低 1 件**のテストケースで検証されている（マトリクス参照）
- **Schneier 申し送り 4 項目（#1 / #4 / #5 / #6）すべてに integration テスト**:
  - #1: TC-UT-PF-002 + TC-IT-PF-001 + TC-UT-PF-033 / 038 / 039 / 040
  - #4: TC-IT-PF-005（DELETE 拒否）+ TC-IT-PF-015（UPDATE 制限）
  - #5: TC-UT-PF-010, 026, 027, 028 + TC-IT-PF-011 (file mode)
  - #6: TC-IT-PF-007（ORM）+ **TC-IT-PF-020（raw SQL 経路、R1-D 中核）** + TC-IT-PF-021 (before_update) + TC-IT-PF-022（audit_log / pid_registry 配線）
- **イーロン指示の中核「raw SQL 経路でも masking listener が回避不能」を TC-IT-PF-020 で物理確認**（確定 R1-D の根拠を test で凍結し、将来 TypeDecorator 方式に変更しようとする退行を検出）
- **PRAGMA 強制（確定 D）**: 5 件 PRAGMA + 順序（WAL 先頭）+ 毎接続適用を TC-IT-PF-003 + TC-IT-PF-013 で確認
- **起動シーケンス凍結（確定 G）**: 順序実行 + Fail Fast + 段階 4 のみ非 fatal を TC-IT-PF-012 / 031 / 032 で確認
- **masking 適用順序（確定 A）**: Anthropic → OpenAI 順序を TC-UT-PF-016 で、長さ 8 未満除外を TC-UT-PF-017 で、フォールバック契約を TC-UT-PF-018 で確認（masking が例外を投げない物理保証）
- **依存方向（確定 I）**: domain → infrastructure 参照ゼロを TC-CI-PF-001 で確認
- MSG-PF-001 〜 007 の各文言が**静的文字列で照合**されている
- 受入基準 1 〜 13 の各々が**最低 1 件のユニット/結合ケース**で検証されている（E2E 不在のため戦略ガイドの「結合代替可」に従う）
- 受入基準 14（pyright/ruff）/ 15（カバレッジ 90%）は CI ジョブで担保
- T1〜T5 の各脅威に対する対策が**最低 1 件のテストケース**で有効性を確認されている
- 確定 A〜I すべてに証拠ケース
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
- masking 配線の実観測（手動試験）: 直接 `sqlite3` で `INSERT INTO domain_event_outbox(payload_json, ...) VALUES('sk-ant-api03-...')` を実行 → SELECT で `<REDACTED:ANTHROPIC_KEY>` に置換されていることを目視（**ただし `sqlite3` CLI は SQLAlchemy event listener を経由しないため masking が走らない**経路があり、これは ORM 経由の信頼境界外。bakufu アプリ経由の INSERT のみが masking ゲートウェイを保証する。本観測の意図は「DB 直挿しは listener を回避できる経路」を**運用者が認識する**ためで、防衛策としては OS file mode 0600 で他ユーザーからの DB アクセスを物理的に塞ぐ）

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
      persistence/
        sqlite/
          test_engine_pragma.py                # TC-IT-PF-003, 013
          test_session.py                      # TC-IT-PF-014
          test_alembic_init.py                 # TC-IT-PF-004, 035
          test_audit_log_trigger.py            # TC-IT-PF-005, 015 (Schneier #4)
          test_pid_gc.py                       # TC-UT-PF-010, 026, 027, 028 (Schneier #5)
          test_attachment_root.py              # TC-IT-PF-011, 029, TC-UT-PF-030 (Schneier #5)
          outbox/
            test_dispatcher.py                 # TC-IT-PF-008, 023, 009, 024, 025
            test_masking_listener.py           # TC-IT-PF-007, 020, 021, 022 (Schneier #6 / R1-D 中核)
      test_bootstrap_sequence.py               # TC-IT-PF-012, 031, 032, 034, TC-IT-PF-036, 037
```

**配置の根拠**:
- 戦略ガイド §テストディレクトリ構造 の Python 標準慣習に従う
- characterization は本流 CI から除外（`RUN_CHARACTERIZATION=1` 環境変数で明示有効化）
- factory は schema を参照して生成、raw fixture は integration test 専用（unit でも factory を介して同 schema から派生）
- architecture/test_dependency_direction.py は確定 I の物理保証（domain → infrastructure 参照ゼロ）
- masking_listener.py を**独立ファイル**にするのはイーロン指示の核心テスト群（raw SQL 経路含む）を 1 ファイルに集約し、レビュー時の確認帯域を最小化するため

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

- [ ] REQ-PF-001〜010 すべてに 1 件以上のテストケースがあり、特に integration が結合シナリオを単独でカバーしている
- [ ] **Schneier 申し送り 4 項目（#1 / #4 / #5 / #6）すべてに integration テスト**が起票され、unit のみで終わっていない
- [ ] **イーロン指示の核心「raw SQL 経路でも masking listener が回避不能」が TC-IT-PF-020 で実 SQLite に対し物理確認されている**（`session.execute(insert(table).values(...))` 経路で listener が走り masking 適用済み値で永続化されるか）
- [ ] `audit_log` DELETE 拒否 + UPDATE 制限の SQLite トリガが**実 raw SQL** で発火することが TC-IT-PF-005 / 015 で確認されている
- [ ] PRAGMA 5 件すべて + 順序（WAL 先頭、確定 D）が TC-IT-PF-003 / 013 で実 engine に対し確認されている
- [ ] pid_gc の `protected` 判定が「DELETE のみで kill しない」（TC-UT-PF-026）+ `AccessDenied` の WARN + 行残し（TC-UT-PF-027）+ 子孫追跡 `recursive=True`（TC-UT-PF-028）すべてが網羅されている
- [ ] 起動シーケンス 8 段階（確定 G）が順序実行（TC-IT-PF-012）+ Fail Fast（TC-IT-PF-031）+ 段階 4 のみ非 fatal（TC-IT-PF-032）で網羅されている
- [ ] masking 適用順序（Anthropic → OpenAI、TC-UT-PF-016）+ 環境変数長さ閾値 8（TC-UT-PF-017）+ フォールバック契約（TC-UT-PF-018）が独立して検証されている
- [ ] 依存方向（確定 I）が CI script（TC-CI-PF-001）+ test_dependency_direction.py の両方で物理保証されている
- [ ] **TBD-PF-1（psutil characterization）が本 PR 内で完了する計画**になっており、assumed mock 禁止規約に違反しない
- [ ] freezegun の clock factory（TBD-PF-2）が backoff / リカバリ判定テストの flaky 化を防ぐ設計になっている
- [ ] MSG-PF-001〜007 の文言が静的文字列で照合される設計になっている
- [ ] 確定 A〜I すべてに証拠ケースが含まれる
- [ ] T1〜T5 の各脅威への有効性確認ケースが含まれている
- [ ] 結合シナリオ（TC-IT-PF-036 / 037）が「Backend 起動 → 永続化 → Outbox → Dispatcher → masking 適用済み永続化 → クラッシュリカバリ」を一連で確認できる
- [ ] empire / workflow / agent / room の WeakValueDictionary レジストリ方式と整合した factory 設計になっている
