# 要求分析書

> feature: `persistence-foundation`
> Issue: [#19 feat(persistence-foundation): SQLite永続化基盤 (M2)](https://github.com/bakufu-dev/bakufu/issues/19)
> 凍結済み設計: [`tech-stack.md`](../../architecture/tech-stack.md) §ORM / §LLM Adapter 運用方針 / §Admin CLI 運用方針 / [`storage.md`](../../architecture/domain-model/storage.md) §シークレットマスキング規則 / [`events-and-outbox.md`](../../architecture/domain-model/events-and-outbox.md) §`domain_event_outbox`

## 人間の要求

> Issue #19:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の **横断基盤**を立ち上げる。M1 ドメイン骨格 3 兄弟（empire / workflow / agent）+ 後続 4 Aggregate（room / directive / task / external-review-gate）の Repository 実装が乗る共通基盤を本 Issue で凍結し、Aggregate 別 Repository は後続 PR（`feature/{aggregate}-repository`）で個別に積む。**Repository 実装本体は本 Issue のスコープ外**（巨大 PR 化を避ける）。

## 背景・目的

### 現状の痛点

1. M1 ドメイン骨格が完走（PR #15 / #16 / #17）したが、**永続化基盤が無いため Aggregate を保存・復元できない**。MVP の受入基準 #8「再起動後も Empire / Room / Agent / Task / Gate の状態が SQLite から復元される」を満たす経路が存在しない
2. 永続化を Aggregate 別 Issue で並行着手すると、**SQLAlchemy engine 設定 / Alembic head / マスキング配線 / Outbox スキーマ等の共通基盤が各 PR で並列に決まり、後で衝突する**。M1 で empire / workflow / agent の domain 設計を集約 PR（threat-model.md / mvp-scope.md）で先に凍結したのと同じ問題が永続化層でも起こる
3. Schneier 申し送り 6 項目（`BAKUFU_DATA_DIR` 絶対パス強制 / H10 TOCTOU / `Persona.prompt_body` Repository マスキング / `audit_log` DELETE 拒否トリガ / `bakufu_pid_registry` 0600 / Outbox `payload_json` / `last_error` 永続化前マスキング）が個別 Repository PR に分散すると**漏れが生じる経路が増える**。1 PR で凍結する基盤化が必須

### 解決されれば変わること

- 後続 `feature/{aggregate}-repository` PR が SQLAlchemy engine / session / マスキングゲートウェイ / マイグレーション head を共有資産として参照できる
- Schneier 申し送り 6 項目のうち本 Issue で配線できる 4 項目（#1 / #4 / #5 / #6）が **1 PR で凍結**され、他項目（#2 / #3）も hook 構造を提供する
- M3 HTTP API / M5 LLM Adapter / M6 ExternalReviewGate UI が「永続化が動いている前提」で開発を進められる
- domain → infrastructure の依存方向（domain は外側を知らない）が SQLAlchemy event listener / TypeDecorator パターンで物理保証される（後続 Repository が崩しにくい）

### ビジネス価値

- bakufu MVP の Vモデル E2E（M7）に至る最短経路の M2 を確保
- 「Aggregate 別 Repository は小粒 PR に分割可能」な構造を最初に定義することで、レビュー負荷を分散しつつ後続を高速に積める
- セキュリティ申し送りを単一 PR で凍結することで、後続レビュアー（Schneier / スティーブ / Norman）の確認帯域を節約する

## 議論結果

### 設計担当による採用前提

- ORM は **SQLAlchemy 2.x 非同期版**（[`tech-stack.md`](../../architecture/tech-stack.md) §ORM 確定）。`AsyncSession` ベースで `async with session.begin():` を Unit-of-Work 境界とする
- マイグレーションは **Alembic**（同上）。初回 revision は共通基盤テーブル 3 種（`audit_log` / `bakufu_pid_registry` / `domain_event_outbox`）のみ。Aggregate 別テーブルは後続 PR で別 revision を積む
- SQLite は **WAL モード + foreign_keys ON + busy_timeout 5000ms** を engine 生成時に PRAGMA で強制する（接続イベントで毎接続適用）
- `BAKUFU_DATA_DIR` は **起動時に絶対パスで解決**し以後保持する（Schneier 申し送り #1）。相対パスは Fail Fast
- マスキングは **永続化前の単一ゲートウェイ** `infrastructure/security/masking.py` に集約し、SQLAlchemy event listener（`before_insert` / `before_update`）で**強制ゲートウェイ化**する。「呼ぶのを忘れる」経路を物理的に塞ぐ
- `audit_log` は **追記のみ**。DELETE は SQLite トリガーで `RAISE(ABORT)`、UPDATE も `result` / `error_text` の null 埋めのみ許可（Schneier 申し送り #4）
- Outbox Dispatcher は **骨格のみ**実装（polling SQL / 状態マーキング / 5 分リカバリ条件 / 5 回 dead-letter）。Handler 実装は後続 PR で event 種別ごとに積む
- `bakufu_pid_registry` テーブルと起動時 GC スケルトン（`psutil.create_time()` で PID 衝突対策、`recursive=True` で子孫追跡）を本 Issue で確定（Schneier 申し送り #5）
- ディレクトリ層分離: `infrastructure/persistence/sqlite/` / `infrastructure/security/` / `infrastructure/config/` の 3 領域。empire / workflow / agent の domain 層に**侵入しない**ことを CI で保証

### 却下候補と根拠

| 候補 | 却下理由 |
|-----|---------|
| Repository 本体まで本 Issue で実装する | 巨大 PR 化（4 Aggregate × Repository でファイル数 50+、レビュー帯域を圧迫）。基盤と Repository を分離して後続 PR で積み増す方が安全 |
| Outbox Dispatcher の Handler 実装まで本 Issue に含める | Handler は event 種別ごとに副作用（Notifier / WebSocket / 次 Aggregate 更新）が異なり、配線が複雑。骨格のみで止め、Handler は `feature/outbox-handlers` 系の小粒 PR で積む |
| Synchronous SQLAlchemy（v1.4 sync 互換）を採用 | FastAPI + uvicorn の async runtime と相性が悪く、connection pool / session 管理が複雑化する。`tech-stack.md` の async 確定方針と矛盾 |
| マスキングを application 層 service の責務（メソッド呼び出し）にする | 「呼び忘れ」経路が生まれる（OWASP A02 / A09 リスク）。SQLAlchemy event listener で強制ゲートウェイ化することで「直接 INSERT する経路」も masking を経由する物理保証を得る |
| Alembic を後段で導入し本 Issue は SQLAlchemy `metadata.create_all()` で済ませる | Phase 2 でスキーマ変更が必要になった瞬間に migration が要るが、その時点でのデータ移行スクリプトを後付けで書くのは負債。最初から Alembic を入れる |
| WAL 以外（ROLLBACK ジャーナル）を採用 | 同時読み書き性能が劣る。WAL は SQLite の標準推奨で MVP 想定の単一プロセス + WebSocket リアルタイム配信に必須 |
| TypeDecorator ベースのマスキング配線（`MaskedString` 型） | 個別カラムごとに型を差し替える必要があり、属性追加時の漏れが生まれやすい。**`event.listens_for(target, 'before_insert/before_update')` の表テーブル横断で配線**する方が漏れにくい |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: Schneier 申し送り 6 項目の取り込み境界

| # | 申し送り項目 | 本 Issue での実装 | 理由 |
|---|----|----|----|
| 1 | `BAKUFU_DATA_DIR` 絶対パス強制 | ✓ 起動時解決ロジックを `infrastructure/config/data_dir.py` に集約 | 全永続化経路の前提となるため基盤に置く |
| 2 | H10 TOCTOU race condition（skill path I/O 直前再検証） | ✗ `feature/skill-loader` 責務として継承（本 Issue では設計書 §申し送り に明記） | I/O 経路は LLM Adapter / Skill loader に閉じる責務分離 |
| 3 | `Persona.prompt_body` Repository マスキング | △ hook 構造のみ確定（実適用は `feature/agent-repository`） | Aggregate 別 Repository が乗るため hook 提供で十分 |
| 4 | `audit_log` DELETE 拒否 SQLite トリガー | ✓ Alembic 初回 revision で `CREATE TRIGGER` | テーブル定義と物理保証を 1 PR で凍結 |
| 5 | `bakufu_pid_registry` OS file mode 0600 | ✓ テーブル + 起動時 GC スケルトン | 起動シーケンスに組み込む必要があるため基盤に置く |
| 6 | Outbox `payload_json` / `last_error` 永続化前マスキング | ✓ SQLAlchemy `before_insert` / `before_update` で強制ゲートウェイ化 | OWASP A02 / A09 の物理保証 |

#### 確定 R1-B: Repository 実装の境界

本 Issue では Aggregate 別 Repository を**実装しない**。後続 PR で `feature/empire-repository` / `feature/workflow-repository` / `feature/agent-repository` / `feature/room-repository` / `feature/task-repository` / `feature/directive-repository` / `feature/external-review-gate-repository` の独立 PR として積む。理由:

- 各 Repository は SQLAlchemy mapper（imperative または declarative）+ domain ↔ row 変換 + マスキング配線（before_insert / before_update）+ Aggregate 別の取得 / 検索クエリで合計 200〜400 行 + テスト 200 行になり、4〜7 個積むと 1500〜4000 行の PR になる
- 1 PR あたり Aggregate 1 個に絞れば、レビュアーが「この Aggregate の永続化責任は閉じている」と単独で確認できる
- 失敗した Repository 実装を別 PR で revert すれば他 Aggregate に影響しない

#### 確定 R1-C: Backend 起動シーケンス順序の凍結

`backend/src/bakufu/main.py` の起動順序を以下に凍結する。各段階失敗時は Fail Fast（プロセス終了）:

1. `BAKUFU_DATA_DIR` 解決（絶対パス検証） — Schneier #1
2. SQLite engine 初期化（PRAGMA 強制：WAL / foreign_keys / busy_timeout）
3. Alembic auto-migrate（最新 head へ）
4. `bakufu_pid_registry` 起動時 GC（前回プロセスの孤児 kill） — Schneier #5
5. アタッチメント FS ルート存在確認 + パーミッション検証（`0700` 強制）
6. Outbox Dispatcher 常駐タスク起動 — Schneier #6 の masking 配線済み
7. アタッチメント孤児 GC スケジューラ起動（24h 周期）
8. FastAPI / WebSocket リスナ開始（既定 `127.0.0.1:8000`）

**順序の根拠**:

- 1 → 2: engine が DATA_DIR 配下にファイルを置くため
- 2 → 3: Alembic は engine 経由で migrate する
- 3 → 4: pid_registry テーブルが存在してから GC を走らせる
- 4 → 6: 前回プロセスの孤児が現セッションの初回 Outbox を横取りしないため、pid_registry GC を Dispatcher 起動より前に置く
- 6 → 8: HTTP リスナを開く前に Outbox が動いていないと、初期化中の Aggregate 操作が dead-letter 化する経路ができる

#### 確定 R1-D: SQLAlchemy event listener vs TypeDecorator のマスキング配線方式

採用: **`event.listens_for(target, 'before_insert')` / `'before_update'` の表テーブル横断配線**。

理由:

| 検討事項 | event listener | TypeDecorator |
|----|----|----|
| 配線の一元性 | ✓ table 単位で listener を 1 つ登録すれば全カラムを横断検査できる | ✗ カラムごとに型を差し替える必要 |
| 属性追加時の漏れ | ✓ 新カラム追加時、masking 対象なら listener 内のフィールドリストに 1 行追加するだけ | ✗ カラム定義時に `MaskedString` 型を指定し忘れると検査が抜ける |
| パフォーマンス | ✓ INSERT / UPDATE 直前の 1 回のみ呼ばれる | △ Type レベルで bind_param に毎回介入する |
| テスト容易性 | ✓ listener を直接呼んでテストできる | △ 型を介すため mock しにくい |
| 「呼び忘れ」経路 | ✓ table に直接 INSERT する経路でも listener が走る | ✗ raw SQL 経路は型を経由しない |

`Persona.prompt_body` / `PromptKit.prefix_markdown` / `Conversation.body_markdown` / `Deliverable.body_markdown` / `domain_event_outbox.payload_json` / `domain_event_outbox.last_error` / `audit_log.args_json` / `audit_log.error_text` / `Task.last_error` の 9 経路すべてを listener 配線で物理保証する（後続 Repository PR で table 定義と同時に listener 登録）。

#### 確定 R1-E: 起動時 PRAGMA 強制方法（Schneier 重大 2 対応で 8 件に拡張）

SQLAlchemy の `event.listens_for(engine, 'connect')` で **毎接続時に PRAGMA を SET**する。

| # | PRAGMA | 値 | 根拠 |
|---|----|----|----|
| 1 | `journal_mode` | `WAL` | 同時読み書き性能、再起動時の WAL 自動チェックポイント |
| 2 | `foreign_keys` | `ON` | SQLite 既定 OFF。Aggregate 間の参照整合性を物理保証 |
| 3 | `busy_timeout` | `5000`（ms） | 同時アクセス時のロック待ち上限 |
| 4 | `synchronous` | `NORMAL`（WAL モードで安全） | 完全 fsync より高速、WAL の crash safety を維持 |
| 5 | `temp_store` | `MEMORY` | 一時テーブル / インデックスをメモリで保持 |
| 6 | `defensive` | `ON`（SQLite 3.31+） | runtime DDL（CREATE / DROP TRIGGER 等）を制限し、`audit_log` トリガを DROP できない経路に置く |
| 7 | `writable_schema` | `OFF` | runtime 中の `sqlite_master` 直接 UPDATE を阻止 |
| 8 | `trusted_schema` | `OFF` | スキーマ内の関数・VIEW などへの信頼を最小化 |

application 接続では上記 8 件すべてを SET。**Alembic migration 接続のみ別経路（`defensive=OFF`）で生成し、Bootstrap stage 3 終了時に `dispose()` で破棄**する（dual connection、詳細設計書 §確定 D-2）。これにより Backend ランタイム中は DDL 制限された接続しか存在せず、攻撃者が runtime DDL でトリガを DROP する経路を物理的に塞ぐ。

`defensive=ON` が技術的に困難な場合は **OS ユーザー隔離 + DB ファイル 0600 で DDL 経路を物理的に塞ぐ** フォールバックを採用（threat-model.md §A4 で信頼境界を明記）。

#### 確定 R1-F: DB ファイル権限の検出 + 警告（Schneier 重大 3 対応）

`os.chmod` のサイレント修正を**廃止**。Forensic 観点で異常状態の検出可能性を残す。詳細は requirements.md §REQ-PF-002-A。

#### 確定 R1-G: `BAKUFU_DB_PATH` 環境変数の廃止（Schneier 重大 4 対応）

DB ファイルパスは `<DATA_DIR>/bakufu.db` 固定。`BAKUFU_DATA_DIR` だけ守って `BAKUFU_DB_PATH` がノーガードで存在する状態は防衛として整合性がない。YAGNI で攻撃面を減らす。

#### 確定 R1-H: マスキング Fail-Secure 契約（Schneier 重大 1 対応）

`MaskingGateway` は **生データを書く経路ゼロ**を絶対不変条件とする。例外時は `<REDACTED:MASK_ERROR>` / `<REDACTED:LISTENER_ERROR>` / `<REDACTED:MASK_OVERFLOW>` で完全置換。環境変数辞書ロード失敗は Fail Fast。詳細は detailed-design.md §確定 F。

#### 確定 R1-I: Bootstrap 入口の `os.umask(0o077)`（Schneier 中等 1 対応）

WAL / SHM ファイルが SQLite 自動生成時に umask 0o022 で 0o644 に作られる経路を塞ぐ。`Bootstrap.run()` の最初の文で `os.umask(0o077)` を SET。POSIX 限定。詳細は detailed-design.md §確定 L。

#### 確定 R1-J: `BAKUFU_DB_KEY` の削除（Schneier 中等 2 対応、YAGNI）

MVP では SQLCipher 等の at-rest 暗号化を採用しない方針（[`mvp-scope.md`](../../architecture/mvp-scope.md) §含めない機能）。`BAKUFU_DB_KEY` を masking 対象 env から削除し、代わりに `BAKUFU_DISCORD_BOT_TOKEN`（threat-model.md §資産 で「高」機密性が明記）を追加。Phase 2 で SQLCipher 導入時に再度 masking 対象に追加。

#### 確定 R1-K: 空 handler レジストリ稼働時の WARN（Schneier 中等 3 対応）

dispatcher は本 PR で起動するが、handler レジストリが空の場合は WARN ログで運用者に Fail Loud で通知する。Outbox 滞留閾値（PENDING > 100 件）でも WARN 出力。詳細は detailed-design.md §確定 K。

#### 確定 R1-L: Bootstrap 起動失敗時の cleanup（Schneier 中等 4 対応）

Bootstrap は `try / finally` 構造で stage 6 / 7 で起動した task を **後に起動したものから先に cancel**（LIFO）し、engine `dispose()` を呼んでから exit する。Phase 2 のグレースフルシャットダウン拡張への伸び代を残す設計。詳細は detailed-design.md §確定 J。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 個人開発者 CEO | bakufu インスタンスのオーナー | GitHub / Docker / CLI 日常使用 | bakufu Backend を起動・停止し、再起動後もデータが復元される | 永続化を意識せずに UI から Empire / Room / Agent / Task を操作 |
| 後続 Issue 担当（バックエンド開発者） | Aggregate 別 Repository PR の実装者 | SQLAlchemy 経験あり | 本 Issue の基盤を import して Repository を 1 個積む | 共通基盤の API（Session / マスキング hook / マイグレーション）を素直に呼べる |

bakufu システム全体のペルソナは [`docs/architecture/context.md`](../../architecture/context.md) §4 を参照。

## 前提条件・制約

| 区分 | 内容 |
|-----|------|
| 既存技術スタック | Python 3.12+ / SQLAlchemy 2.x / Alembic / Pydantic v2 / pyright strict / pytest（[`tech-stack.md`](../../architecture/tech-stack.md)） |
| 既存 CI | lint / typecheck / test-backend / audit |
| 既存ブランチ戦略 | GitFlow（CONTRIBUTING.md §ブランチ戦略） |
| コミット規約 | Conventional Commits |
| ライセンス | MIT |
| ネットワーク | 該当なし — infrastructure 層（local SQLite + ローカル filesystem） |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+。POSIX 限定機能（file mode 0600 / 0700）は OS 検出して条件付き適用 |

## 機能一覧

| 機能ID | 機能名 | 概要 | 優先度 |
|--------|-------|------|--------|
| REQ-PF-001 | データルート解決 | `BAKUFU_DATA_DIR` を起動時に絶対パスで解決、未設定時は OS 別既定。相対パスは Fail Fast | 必須（Schneier #1） |
| REQ-PF-002 | SQLite engine 初期化 | async engine 生成 + 接続イベントで PRAGMA 強制（WAL / foreign_keys / busy_timeout / synchronous / temp_store） | 必須 |
| REQ-PF-003 | AsyncSession factory | `async with session.begin():` を UoW 境界として提供 | 必須 |
| REQ-PF-004 | Alembic 初回 migration | `audit_log` / `bakufu_pid_registry` / `domain_event_outbox` の 3 テーブル + `audit_log` DELETE 拒否トリガ | 必須（Schneier #4） |
| REQ-PF-005 | マスキング単一ゲートウェイ | 環境変数 + 9 種正規表現 + ホームパスの 3 段階適用順序、`infrastructure/security/masking.py` に集約 | 必須（Schneier #6） |
| REQ-PF-006 | SQLAlchemy event listener 配線（Outbox） | `domain_event_outbox` の `payload_json` / `last_error` を `before_insert` / `before_update` で強制マスキング | 必須（Schneier #6） |
| REQ-PF-007 | Outbox Dispatcher 骨格 | polling SQL（PENDING + DISPATCHING の 5 分リカバリ条件）、5 回 dead-letter、Handler レジストリ（空ハンドラ登録可） | 必須 |
| REQ-PF-008 | pid_registry 起動時 GC | テーブル + GC スケルトン（`psutil.Process.create_time()` で PID 衝突対策、`recursive=True` で子孫追跡） | 必須（Schneier #5） |
| REQ-PF-009 | アタッチメント FS ルート初期化 | `BAKUFU_DATA_DIR/attachments/` 作成 + パーミッション 0700 強制（POSIX のみ）+ 孤児 GC スケジューラ枠 | 必須 |
| REQ-PF-010 | 起動シーケンス凍結 | §確定 R1-C の 8 段階を `main.py` で実装、各段階失敗時 Fail Fast | 必須 |

## Sub-issue 分割計画

本 Issue は意図的に**基盤に絞った 1 PR**であり、Aggregate 別 Repository（4〜7 種）を別 PR に分離することで既に分割済み。本 Issue 自体をさらに分割すると Alembic 初回 revision が複数 PR に跨がり head 管理が壊れる。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 単一 PR | REQ-PF-001〜010 | 設計書 4 本 + infrastructure/persistence/sqlite/ + infrastructure/security/masking.py + infrastructure/config/data_dir.py + alembic/ + main.py 起動シーケンス + ユニット / 結合テスト | M1 ドメイン骨格 3 兄弟（PR #15 / #16 / #17）マージ済み |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | engine 起動 < 200ms（PRAGMA 適用込み）、Alembic migration（初回 revision 適用）< 500ms、masking 1KB 入力 < 1ms、Outbox polling 1 サイクル < 50ms |
| 可用性 | SQLite WAL mode による crash safety（`synchronous=NORMAL`）、Backend クラッシュ後の起動時 GC で孤児 subprocess を kill / 孤児 Outbox 行をリカバリ |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 90% 以上（基盤コードのため高カバレッジ目標） |
| 可搬性 | POSIX 限定機能（file mode）は OS 検出して条件付き適用。Windows では ACL / `oslib` を使わず、ファイルが OS ユーザーのホーム配下に置かれる前提で「`%LOCALAPPDATA%\bakufu` 配下は OS ユーザーのみアクセス可能」を信頼 |
| セキュリティ | OWASP A02（マスキング） / A04（pre-validate / Fail Fast） / A05（PRAGMA 強制 / file mode） / A08（追記 only audit_log + DELETE トリガ） / A09（マスキング適用ログ）。詳細は [`threat-model.md`](../../architecture/threat-model.md) |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | `BAKUFU_DATA_DIR` 未設定時に OS 別既定が絶対パスで解決される | TC-UT-PF-001 |
| 2 | `BAKUFU_DATA_DIR` 相対パス指定時に起動 Fail Fast（`ValueError`） | TC-UT-PF-002 |
| 3 | engine 接続時に WAL / foreign_keys ON / busy_timeout が適用される | TC-IT-PF-003（PRAGMA を `PRAGMA journal_mode` で確認） |
| 4 | Alembic 初回 revision で 3 テーブル + DELETE 拒否トリガが作成される | TC-IT-PF-004 |
| 5 | `audit_log` への DELETE が SQLite トリガで `RAISE(ABORT)` される | TC-IT-PF-005 |
| 6 | マスキング単体テスト（環境変数 / 9 種正規表現 / ホームパス、適用順序込み）すべて pass | TC-UT-PF-006 |
| 7 | `domain_event_outbox` への INSERT で `payload_json` / `last_error` が masking 後の値で永続化される | TC-IT-PF-007（`sk-ant-...` / `ghp_...` を含む payload を INSERT して SELECT で確認） |
| 8 | Outbox Dispatcher 骨格の polling SQL が `(PENDING AND next_attempt_at <= now)` または `(DISPATCHING AND updated_at < now - 5min)` の行を取得する | TC-IT-PF-008 |
| 9 | Outbox Dispatcher 骨格が 5 回失敗で `status=DEAD_LETTER` + `OutboxDeadLettered` event を別行として追記する | TC-IT-PF-009 |
| 10 | `bakufu_pid_registry` 起動時 GC が `psutil.create_time()` で PID 衝突を識別する | TC-UT-PF-010（mock psutil でケース網羅） |
| 11 | アタッチメント FS ルートが `0700` で作成される（POSIX） | TC-IT-PF-011 |
| 12 | 起動シーケンス 8 段階が順序通り実行され、各段階失敗時に後続が走らない | TC-IT-PF-012 |
| 13 | `domain` 層から `bakufu.infrastructure.*` への import がゼロ件（CI で検査） | CI script |
| 14 | `pyright --strict` および `ruff check` がエラーゼロ | CI lint / typecheck |
| 15 | カバレッジが `infrastructure/persistence/sqlite/` / `infrastructure/security/` で 90% 以上 | pytest --cov |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| `BAKUFU_DATA_DIR` 絶対パス | 起動時解決後の OS パス | 低（ログに出力する場合は `<HOME>` 置換適用） |
| `bakufu.db` / `bakufu.db-wal` / `bakufu.db-shm` | SQLite 物理ファイル | **高**（OS file mode 0600、漏洩時の対応は [`storage.md`](../../architecture/domain-model/storage.md) §漏洩したらどうするか） |
| `domain_event_outbox.payload_json` / `last_error` | Domain Event 本体 + 失敗時例外メッセージ | **中→低**（永続化前マスキング適用後は機密性除去） |
| `audit_log.args_json` / `error_text` | Admin CLI 引数 + 失敗時メッセージ | **中→低**（同上） |
| `bakufu_pid_registry.pid` / `parent_pid` / `cmd` | LLM subprocess の追跡情報 | 低（`cmd` 内に環境変数値が混入し得るため masking 対象） |
