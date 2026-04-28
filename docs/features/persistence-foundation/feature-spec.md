# 業務仕様書（feature-spec）— persistence-foundation

> feature: `persistence-foundation`（業務概念単位）
> sub-features: [`domain/`](domain/)
> 関連 Issue: [#19 feat(persistence-foundation): SQLite永続化基盤 (M2)](https://github.com/bakufu-dev/bakufu/issues/19)
> 凍結済み設計: [`docs/design/tech-stack.md`](../../design/tech-stack.md) §ORM / §LLM Adapter 運用方針 / §Admin CLI 運用方針 / [`docs/design/domain-model/storage.md`](../../design/domain-model/storage.md) §シークレットマスキング規則 / [`docs/design/domain-model/events-and-outbox.md`](../../design/domain-model/events-and-outbox.md) §`domain_event_outbox`

## 本書の役割

本書は **persistence-foundation という業務概念全体の業務仕様** を凍結する。プロジェクト全体の要求分析（[`docs/analysis/`](../../analysis/)）を SQLite 永続化基盤という観点で具体化し、ペルソナから見て **観察可能な業務ふるまい** を実装レイヤーに依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない。

**書くこと**:
- ペルソナが persistence-foundation で達成できるようになる行為（ユースケース）
- 業務ルール（Schneier 申し送り / TypeDecorator 配線 / PRAGMA 強制 / 起動シーケンス等、すべての sub-feature を貫く凍結）
- 観察可能な事象としての受入基準（システムテストの真実源）

**書かないこと**（後段の設計書・別ディレクトリへ追い出す）:
- 採用技術スタック → `domain/basic-design.md` / [`docs/design/tech-stack.md`](../../design/tech-stack.md)
- 実装方式の比較・選定議論 → `domain/detailed-design.md`
- 内部 API 形・メソッド名・属性名・型 → `domain/basic-design.md` / `domain/detailed-design.md`
- pyright strict / カバレッジ閾値 → §10 開発者品質基準（CI 担保）

## 1. この feature の位置付け

persistence-foundation は **bakufu MVP M2 の横断基盤** として定義する。M1 ドメイン骨格 3 兄弟（empire / workflow / agent）+ 後続 4 Aggregate（room / directive / task / external-review-gate）の Repository 実装が乗る共通基盤を本 feature で凍結し、Aggregate 別 Repository は後続 PR として積む。

業務的なライフサイクルは単一の実装レイヤーに閉じる:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| infrastructure domain | [`domain/`](domain/) | SQLite 永続化基盤（engine / session / masking / outbox / pid_registry / bootstrap）の初期化と保証 |
| repository（各 Aggregate） | 後続 feature | 本 feature の基盤を共通資産として参照し、Aggregate 別永続化を実装 |
| http-api | (将来) | HTTP 経由の永続化操作 |
| ui | (将来) | CEO が永続化状態を観察する画面 |

## 2. 人間の要求

> Issue #19:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の **横断基盤**を立ち上げる。M1 ドメイン骨格 3 兄弟（empire / workflow / agent）+ 後続 4 Aggregate（room / directive / task / external-review-gate）の Repository 実装が乗る共通基盤を本 Issue で凍結し、Aggregate 別 Repository は後続 PR（`feature/{aggregate}-repository`）で個別に積む。**Repository 実装本体は本 Issue のスコープ外**（巨大 PR 化を避ける）。

## 3. 背景・痛点

### 現状の痛点

1. M1 ドメイン骨格が完走（PR #15 / #16 / #17）したが、**永続化基盤が無いため Aggregate を保存・復元できない**。MVP の受入基準「再起動後も Empire / Room / Agent / Task / Gate の状態が SQLite から復元される」を満たす経路が存在しない
2. 永続化を Aggregate 別 Issue で並行着手すると、**SQLAlchemy engine 設定 / Alembic head / マスキング配線 / Outbox スキーマ等の共通基盤が各 PR で並列に決まり、後で衝突する**
3. Schneier 申し送り 6 項目が個別 Repository PR に分散すると**漏れが生じる経路が増える**。1 PR で凍結する基盤化が必須

### 解決されれば変わること

- 後続 `feature/{aggregate}-repository` PR が SQLAlchemy engine / session / マスキングゲートウェイ / マイグレーション head を共有資産として参照できる
- Schneier 申し送り 6 項目のうち本 feature で配線できる 4 項目（#1 / #4 / #5 / #6）が **1 PR で凍結**される
- M3 HTTP API / M5 LLM Adapter / M6 ExternalReviewGate UI が「永続化が動いている前提」で開発を進められる

### ビジネス価値

- bakufu MVP の Vモデル E2E（M7）に至る最短経路の M2 を確保
- 「Aggregate 別 Repository は小粒 PR に分割可能」な構造を最初に定義
- セキュリティ申し送りを単一 PR で凍結することで、後続レビュアーの確認帯域を節約

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|---|---|---|---|
| 個人開発者 CEO | bakufu インスタンスのオーナー | 直接（Backend 起動・停止） | 永続化を意識せずに UI から Empire / Room / Agent / Task を操作 |
| 後続 Issue 担当（バックエンド開発者） | Aggregate 別 Repository PR の実装者 | 間接（本 feature の API を利用） | 共通基盤の API（Session / マスキング hook / マイグレーション）を素直に呼べる |

bakufu システム全体のペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|---|---|---|---|---|
| UC-PF-001 | CEO | bakufu Backend を起動し、8 段階のシーケンスが成功して HTTP リスナが開始される | 必須 | `domain/` |
| UC-PF-002 | 後続開発者 | Aggregate を永続化する際、masking が自動適用され生 secret が DB に到達しない | 必須 | `domain/` |
| UC-PF-003 | CEO | Backend クラッシュ後に再起動し、孤児プロセスが自動 GC されて正常起動する | 必須 | `domain/` |
| UC-PF-004 | CEO | Outbox イベントが Dispatcher で非同期に配送される（骨格） | 必須 | `domain/` |
| UC-PF-005 | CEO | `BAKUFU_DATA_DIR` 不正指定時に即座に Fail Fast でエラーメッセージが表示される | 必須 | `domain/` |

## 6. スコープ

### In Scope

- Backend 起動シーケンス 8 段階（DATA_DIR 解決 / engine / migration / pid_gc / attachments / outbox / scheduler / HTTP）
- SQLAlchemy 2.x 非同期 engine + PRAGMA 8 件強制（WAL / foreign_keys / defensive 等）
- Alembic 初回 revision（3 テーブル + 2 トリガ）
- マスキング単一ゲートウェイ（9 種正規表現 + 環境変数 + ホームパス）
- SQLAlchemy TypeDecorator 配線（Core / ORM 両経路 masking 強制）
- Outbox Dispatcher 骨格（polling / dead-letter / handler レジストリ）
- pid_registry 起動時 GC（`psutil.create_time()` PID 衝突対策）

### Out of Scope（参照）

- Aggregate 別 Repository 本体 → `feature/{aggregate}-repository` 系の後続 PR
- Outbox Handler 実装（event_kind 別副作用） → `feature/{event-kind}-handler` 系の後続 PR
- HTTP API エンドポイント → `feature/http-api`
- Admin CLI → `feature/admin-cli`
- H10 TOCTOU race condition → `feature/skill-loader`

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-A: Schneier 申し送り 6 項目の取り込み境界

| # | 申し送り項目 | 本 feature | 理由 |
|---|---|---|---|
| 1 | `BAKUFU_DATA_DIR` 絶対パス強制 | ✓ | 全永続化経路の前提となるため基盤に置く |
| 2 | H10 TOCTOU race condition | ✗ | `feature/skill-loader` 責務（本 feature §申し送り に明記） |
| 3 | `Persona.prompt_body` Repository マスキング | △ hook 構造のみ | Aggregate 別 Repository が乗るため hook 提供で十分 |
| 4 | `audit_log` DELETE 拒否 SQLite トリガー | ✓ | テーブル定義と物理保証を 1 PR で凍結 |
| 5 | `bakufu_pid_registry` OS file mode 0600 | ✓ | 起動シーケンスに組み込む必要があるため基盤に置く |
| 6 | Outbox `payload_json` / `last_error` 永続化前マスキング | ✓ | SQLAlchemy TypeDecorator `process_bind_param` で強制ゲートウェイ化 |

### 確定 R1-B: Repository 実装の境界

本 feature では Aggregate 別 Repository を**実装しない**。後続 PR で独立して積む。理由: 各 Repository は合計 200〜400 行 + テスト 200 行になり、4〜7 個積むと 1500〜4000 行の PR になる。1 PR あたり Aggregate 1 個に絞ることでレビュー負荷を分散する。

### 確定 R1-C: Backend 起動シーケンス順序の凍結

以下の 8 段階を `main.py` で凍結。各段階失敗時は Fail Fast（プロセス終了）:

1. `BAKUFU_DATA_DIR` 解決（絶対パス検証）— Schneier #1
2. SQLite engine 初期化（PRAGMA 強制）
3. Alembic auto-migrate（最新 head へ）
4. `bakufu_pid_registry` 起動時 GC — Schneier #5（失敗は非 fatal / WARN）
5. アタッチメント FS ルート存在確認 + パーミッション検証
6. Outbox Dispatcher 常駐タスク起動 — Schneier #6
7. アタッチメント孤児 GC スケジューラ起動（24h 周期）
8. FastAPI / WebSocket リスナ開始（既定 `127.0.0.1:8000`）

### 確定 R1-D: マスキング配線方式（TypeDecorator 採用、event listener 反転却下）

採用: **SQLAlchemy TypeDecorator (`MaskedJSONEncoded` / `MaskedText`) の `process_bind_param` フック**。

旧設計の `event.listens_for(TableClass, 'before_insert')` は PR #23 BUG-PF-001 の技術検証で **SQLAlchemy 2.x Core `insert(table).values({...})` の inline values は ORM mapper を経由しないため `before_insert` listener が発火しない**ことが判明し反転却下（TC-IT-PF-020 旧 xfail strict=True）。raw SQL 経路で生 secret が永続化される脱出経路が残るため Schneier 申し送り #6 の契約が破綻。TypeDecorator `process_bind_param` は Core / ORM 両経路で確実に発火する（TC-IT-PF-020 PASSED で物理保証、commit `4b882bf`）。

「属性追加時の漏れ」リスクは CI 三層防衛（grep guard + アーキテクチャテスト + `storage.md` 逆引き表運用ルール）で物理保証する。

### 確定 R1-E: 起動時 PRAGMA 強制方法

`event.listens_for(engine, 'connect')` で毎接続時に以下 8 件の PRAGMA を SET:

| # | PRAGMA | 値 | 根拠 |
|---|---|---|---|
| 1 | `journal_mode` | `WAL` | 同時読み書き性能 |
| 2 | `foreign_keys` | `ON` | SQLite 既定 OFF。参照整合性の物理保証 |
| 3 | `busy_timeout` | `5000`（ms） | 同時アクセス時のロック待ち上限 |
| 4 | `synchronous` | `NORMAL` | WAL モードで安全かつ高速 |
| 5 | `temp_store` | `MEMORY` | 一時テーブル / インデックスをメモリで保持 |
| 6 | `defensive` | `ON`（SQLite 3.31+） | runtime DDL を制限し `audit_log` トリガを DROP できない経路に置く |
| 7 | `writable_schema` | `OFF` | runtime 中の `sqlite_master` 直接 UPDATE を阻止 |
| 8 | `trusted_schema` | `OFF` | スキーマ内の関数・VIEW などへの信頼を最小化 |

Alembic migration 接続のみ `defensive=OFF` の別経路（dual connection）で生成し、Bootstrap stage 3 終了時に `dispose()` で破棄する。

### 確定 R1-F: DB ファイル権限の検出 + 警告（Forensic 観点）

`os.chmod` のサイレント修正を**廃止**。異常状態の検出可能性を残す。WARN + 修復 + 続行が運用バランスとして妥当（Forensic 観点）。

### 確定 R1-G: `BAKUFU_DB_PATH` 環境変数の廃止

DB ファイルパスは `<DATA_DIR>/bakufu.db` 固定。YAGNI で攻撃面を減らす。

### 確定 R1-H: マスキング Fail-Secure 契約

`MaskingGateway` は **生データを書く経路ゼロ**を絶対不変条件とする。例外時は `<REDACTED:MASK_ERROR>` / `<REDACTED:LISTENER_ERROR>` / `<REDACTED:MASK_OVERFLOW>` で完全置換。環境変数辞書ロード失敗は Fail Fast。

### 確定 R1-I: Bootstrap 入口の `os.umask(0o077)`

WAL / SHM ファイルが SQLite 自動生成時に umask 0o022 で 0o644 に作られる経路を塞ぐ。`Bootstrap.run()` の最初の文で `os.umask(0o077)` を SET。POSIX 限定。

### 確定 R1-J: `BAKUFU_DB_KEY` の削除（YAGNI）

MVP では SQLCipher 等の at-rest 暗号化を採用しない方針。`BAKUFU_DB_KEY` を masking 対象 env から削除し、代わりに `BAKUFU_DISCORD_BOT_TOKEN`（高機密性）を追加。

### 確定 R1-K: 空 handler レジストリ稼働時の WARN

dispatcher は本 PR で起動するが、handler レジストリが空の場合は WARN ログで Fail Loud に通知する。Outbox 滞留閾値（PENDING > 100 件）でも WARN 出力。

### 確定 R1-L: Bootstrap 起動失敗時の cleanup

Bootstrap は `try / finally` 構造で stage 6 / 7 で起動した task を **後に起動したものから先に cancel**（LIFO）し、engine `dispose()` を呼んでから exit する。

## 8. 制約・前提

| 区分 | 内容 |
|---|---|
| 既存技術スタック | Python 3.12+ / SQLAlchemy 2.x / Alembic / Pydantic v2 / pyright strict / pytest |
| 既存 CI | lint / typecheck / test-backend / audit |
| 既存ブランチ戦略 | GitFlow（CONTRIBUTING.md §ブランチ戦略） |
| コミット規約 | Conventional Commits |
| ライセンス | MIT |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+。POSIX 限定機能（file mode 0600 / 0700）は OS 検出して条件付き適用 |
| 依存 feature | M1 ドメイン骨格 3 兄弟（PR #15 / #16 / #17）マージ済み |

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|---|---|---|
| 1 | `BAKUFU_DATA_DIR` 未設定時に OS 別既定が絶対パスで解決される | UC-PF-005 | TC-UT-PF-001 |
| 2 | `BAKUFU_DATA_DIR` 相対パス指定時に起動が即座に失敗し、パスが相対パスである旨のエラーが表示される | UC-PF-005 | TC-UT-PF-002 |
| 3 | engine 接続時に WAL / foreign_keys ON / busy_timeout が適用される | UC-PF-001 | TC-IT-PF-003 |
| 4 | Alembic 初回 revision で 3 テーブル + DELETE 拒否トリガが作成される | UC-PF-001 | TC-IT-PF-004 |
| 5 | `audit_log` への DELETE 操作が拒否され、エラーが返される | UC-PF-002 | TC-IT-PF-005 |
| 6 | マスキング単体テスト（環境変数 / 9 種正規表現 / ホームパス）すべて pass | UC-PF-002 | TC-UT-PF-006 |
| 7 | `domain_event_outbox` への INSERT で `payload_json` / `last_error` が masking 後値で永続化される | UC-PF-002 | TC-IT-PF-007, TC-IT-PF-020（raw SQL 経路、§確定 R1-D 中核） |
| 8 | Outbox Dispatcher 骨格の polling SQL が PENDING / DISPATCHING リカバリ条件で行を取得する | UC-PF-004 | TC-IT-PF-008 |
| 9 | Outbox Dispatcher 骨格が 5 回失敗で `status=DEAD_LETTER` + `OutboxDeadLettered` event を別行として追記する | UC-PF-004 | TC-IT-PF-009 |
| 10 | `bakufu_pid_registry` 起動時 GC が `psutil.create_time()` で PID 衝突を識別する | UC-PF-003 | TC-UT-PF-010 |
| 11 | アタッチメント FS ルートが `0700` で作成される（POSIX） | UC-PF-001 | TC-IT-PF-011 |
| 12 | 起動シーケンス 8 段階が順序通り実行され、各段階失敗時に後続が走らない | UC-PF-001 | TC-IT-PF-012 |
| ~~13~~ | （欠番 — 依存方向 CI 検査は §10 Q-3 に移動） | — | — |

## 10. 開発者品質基準（CI 担保、業務要求ではない）

| # | 基準 | 検証方法 |
|---|---|---|
| Q-1 | `pyright --strict` および `ruff check` がエラーゼロ | CI lint / typecheck ジョブ |
| Q-2 | カバレッジが `infrastructure/persistence/sqlite/` / `infrastructure/security/` で 90% 以上 | pytest --cov |
| Q-3 | `domain` 層から `bakufu.infrastructure.*` への import がゼロ件（CI スクリプト検査） | TC-CI-PF-001 |

## 11. 開放論点 (Open Questions)

| # | 論点 | 起票先 |
|---|---|---|
| TBD-PF-1 | psutil の characterization fixture（raw + schema 生成） | 本 PR 内で完了 |
| TBD-PF-2 | freezegun ベースの clock factory | 本 PR 内で完了 |

## 12. Sub-issue 分割計画

| Sub-issue 名 | 紐付く UC | スコープ | 依存関係 |
|---|---|---|---|
| 単一 PR（#19） | UC-PF-001〜005 | 設計書 + infrastructure/persistence/sqlite/ + infrastructure/security/masking.py + infrastructure/config/data_dir.py + alembic/ + main.py | M1 ドメイン骨格 3 兄弟マージ済み |

本 Issue は意図的に**基盤に絞った 1 PR**であり、Aggregate 別 Repository（4〜7 種）を別 PR に分離することで既に分割済み。本 Issue 自体をさらに分割すると Alembic 初回 revision が複数 PR に跨がり head 管理が壊れる。

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|---|---|---|
| `BAKUFU_DATA_DIR` 絶対パス | 起動時解決後の OS パス | 低（ログに出力する場合は `<HOME>` 置換適用） |
| `bakufu.db` / `bakufu.db-wal` / `bakufu.db-shm` | SQLite 物理ファイル | **高**（OS file mode 0600、漏洩対応は [`storage.md`](../../design/domain-model/storage.md) §漏洩したらどうするか） |
| `domain_event_outbox.payload_json` / `last_error` | Domain Event 本体 + 失敗時例外メッセージ | **中→低**（永続化前マスキング適用後は機密性除去） |
| `audit_log.args_json` / `error_text` | Admin CLI 引数 + 失敗時メッセージ | **中→低**（同上） |
| `bakufu_pid_registry.pid` / `parent_pid` / `cmd` | LLM subprocess の追跡情報 | 低（`cmd` 内に環境変数値が混入し得るため masking 対象） |

## 14. 非機能要求

| 区分 | 要求 |
|---|---|
| パフォーマンス | engine 起動 < 200ms（PRAGMA 適用込み）、Alembic migration（初回 revision 適用）< 500ms、masking 1KB 入力 < 1ms、Outbox polling 1 サイクル < 50ms |
| 可用性 | SQLite WAL mode による crash safety（`synchronous=NORMAL`）、Backend クラッシュ後の起動時 GC で孤児 subprocess を kill / 孤児 Outbox 行をリカバリ |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 90% 以上 |
| 可搬性 | POSIX 限定機能（file mode）は OS 検出して条件付き適用。Windows では `%LOCALAPPDATA%` 配下のホームを信頼 |
| セキュリティ | OWASP A02（マスキング）/ A04（pre-validate / Fail Fast）/ A05（PRAGMA 強制 / file mode）/ A08（追記 only audit_log + DELETE トリガ）/ A09（マスキング適用ログ） |
