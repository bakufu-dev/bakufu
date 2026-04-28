# 要求分析書

> feature: `directive-repository`
> Issue: [#34 feat(directive-repository): Directive SQLite Repository (M2, 0006)](https://github.com/bakufu-dev/bakufu/issues/34)
> 関連: [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源**（§確定 A〜F + §Known Issues §BUG-EMR-001 規約） / [`docs/features/room-repository/`](../room-repository/) **直近テンプレート**（masking 対象あり版 + find_by_name 系拡張パターン） / [`docs/features/directive/`](../directive/) （domain 設計済み、PR #24 マージ済み） / [`docs/design/domain-model/storage.md`](../../design/domain-model/storage.md) §逆引き表（`Directive.text: MaskedText` 行追加対象）

## 人間の要求

> Issue #34:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の後続 Repository PR（room-repository #33 の次）。**Directive Aggregate** の SQLite 永続化を実装する。Alembic revision **0006_directive_aggregate** で `directives` テーブルを追加。**`Directive.text` の Repository マスキング実適用**（directive feature §確定 G 踏襲）。

## 背景・目的

### 現状の痛点

1. M2 永続化基盤 + empire-repo + workflow-repo + agent-repo + room-repo（PR #47 マージ済み）の 5 件 chain が揃ったが、Directive は domain 層（PR #24）が完了していても **`Directive.text` の永続化経路がない**。MVP 核心ユースケース「CEO directive → Room 編成 → Task 起票 → Agent 配送」の**起点**が塞がれている
2. **directive feature §確定 G 申し送り**: `Directive.text` の永続化前マスキング適用は directive domain 層では「Repository 経路で実適用」と申し送り済み（[directive/detailed-design.md](../directive/detailed-design.md) §データ構造 §永続化）。本 PR で実適用に移行しないと「Directive.text に webhook URL / API key が混入したらマスキングされない」状態が継続する。Schneier 申し送り #3 / room §確定 G のパターンを継承する **3 件目の masking 配線**
3. Directive は CEO が発行した指令テキストであり、PromptKit.prefix_markdown 同様に「CEO がチャット欄で Discord webhook URL や API key を含む長文を送信する」経路が現実に存在する。DB に平文で保存されると audit_log / ログ経由の secret 漏洩リスクが継続する
4. room-repository §確定 R1-F で「後続 Repository は `find_by_room` / `find_by_task_id` の追加 method パターンを必要に応じて採用」と申し送りされた。Directive の 主要クエリパターン（Room 内 directive 一覧 / Task 紐付け directive 検索）に対応する Repository method が確定していない

### 解決されれば変わること

- `feature/directive-application`（後続）が `DirectiveRepository.find_by_id` / `find_by_room` で Directive を復元 → `Directive.text` が valid な状態（masking 済み DB から復元時は raw text として返却）で受け取れる
- `Directive.text` に CEO が誤って Discord webhook URL / API key を貼り付けても DB には `<REDACTED:DISCORD_WEBHOOK>` / `<REDACTED:ANTHROPIC_KEY>` で永続化、ログ・監査経路への流出を防ぐ（**directive §確定 G 実適用**）
- `find_by_room(room_id)` ORDER BY `created_at DESC` で Room チャネルの directive 一覧を取得できる（後続 UI 実装の経路確立）
- `find_by_task_id(task_id)` で Task から発行元 Directive を逆引きできる（後続 task-application の経路確立）
- empire-repo / workflow-repo / agent-repo / room-repo に続く **5 件目のテンプレート** として、後続 task / external-review-gate-repository が同パターンを真似できる経路が確立

### ビジネス価値

- bakufu の核心思想「CEO directive → V モデル工程進行 → 外部レビューで人間が承認」の**起点 Aggregate の永続化経路が確立**する。CEO が Room チャネルに入力した指令が安全に永続化・復元できる
- Directive.text の MaskedText 配線で「CEO が入力した生テキストが DB / ログ / 監査経路に raw で流れる」脅威経路を物理閉鎖（Defense in Depth 第 3 弾、persistence-foundation §シークレットマスキング規則の Repository 経路実適用 3 件目）

## 議論結果

### 設計担当による採用前提

- empire-repository / workflow-repository / agent-repository / room-repository の §確定 A〜F + §BUG-EMR-001 規約を **100% 継承**
- Aggregate Root: Directive、**単一テーブル**: `directives`（子テーブルなし — Directive は flat な 5 属性 Aggregate）
- Alembic revision: `0006_directive_aggregate`、`down_revision="0005_room_aggregate"`（chain 一直線）
- masking 対象カラム: **`directives.text` のみ**（`MaskedText`、directive §確定 G 実適用）
- save() は `directives` UPSERT のみ（子テーブルなし、empire §確定 B の delete-then-insert パターンを 1 テーブルに縮小適用）
- count() は SQL `COUNT(*)`（empire §確定 D 踏襲）
- **Protocol は 4 method**: `find_by_id` / `count` / `save(directive)` / `find_by_room(room_id)`（`find_by_task_id` は task-repository PR で method + INDEX + FK closure を**同時**追加 — §確定 R1-D 参照）
- `save(directive)` は **標準 1 引数パターン**（Directive は `target_room_id` 属性を自身で持つため — [storage.md §Repository save() インターフェース設計パターン](../../design/domain-model/storage.md#repository-save-インターフェース設計パターン確定-h-補足) 標準パターン適用）
- `target_room_id` の DB FK は `rooms.id` への ON DELETE **CASCADE**（Directive は Room が削除されると意味を失う — 委譲先 Room なき Directive は orphan）
- `task_id` は nullable UUIDStr、**FK は張らない**（0006 時点で `tasks` テーブル未存在 — BUG-EMR-001 パターン、task-repository PR で `op.batch_alter_table` 経由 FK 追加を申し送り）
- INDEX: `(target_room_id, created_at)` 非 UNIQUE（`find_by_room` の Room スコープ検索 + created_at ソートに複合 INDEX）

### 却下候補と根拠

| 候補 | 却下理由 |
|---|---|
| `directives.text` を `Text` で保存（masking なし）+ application 層でマスキング | application 層実装漏れで raw 永続化リスク、directive §確定 G 違反。`MaskedText` 強制（room §確定 R1-E と同論理） |
| `target_room_id` FK を ON DELETE RESTRICT | Directive は Room に対して「子」の関係（Room が消えると Directive は意味を失う）。RESTRICT だと「Room を削除したい時に先に全 Directive を消す」手順が必要になり application 層が複雑化。CASCADE が自然な意味論 |
| `target_room_id` FK を ON DELETE SET NULL | `target_room_id` は NOT NULL（Directive は必ず委譲先 Room を持つ）。SET NULL は型違反 |
| `target_room_id` FK を張らない（参照のみ宣言）| 0006 時点で `rooms` テーブルは 0005 で先行存在済み。FK を張れる前提条件が揃っているのに張らないのは dangling pointer リスク温存。**FK は張れる時に張る** が原則 |
| `task_id` FK を 0006 で `tasks.id` に張る | 0006 時点で `tasks` テーブル未存在（task-repository は後続 PR）。empire_room_refs と同じ forward reference 問題。task-repository PR で `op.batch_alter_table` 経由 FK 追加（BUG-EMR-001 規約） |
| `find_by_room` を Protocol に追加せず application 層が全件 SELECT + filter | N+1 / 全件ロードで MVP の数十 Directive は耐えられるが、Room あたり数百 Directive になった場合にメモリ枯渇。INDEX(target_room_id, created_at) で効率的に検索する経路を最初から設計 |
| `find_by_task_id` を本 PR の Protocol に追加する | **YAGNI 違反**。task-application も task-repository も未存在（後続 PR）で呼び出し側ゼロ。INDEX も「追加しない（YAGNI）」と同 PR 内で矛盾認定している（「method は今、INDEX は将来」は不整合）。task-repository PR で method + INDEX + FK closure を**同時**追加するのが正しい設計 — §確定 R1-D で凍結 |
| `save(directive, room_id)` の非対称パターン | Directive は `target_room_id` を自身の属性として持つ（[directive/detailed-design.md §Aggregate Root: Directive](../directive/detailed-design.md) 属性表）。DB 永続化に必要な `target_room_id` を Directive 自身から取れるため非対称パターン不要。[storage.md §確定 H](../../design/domain-model/storage.md) 判断ルール参照 |
| `find_by_room` の ORDER BY を `created_at DESC` 単独 | BUG-EMR-001 規約「複合 key で決定論的順序」に違反。同時刻 Directive で順序非決定的。`created_at DESC, id DESC` とすることで id（PK、一意）を tiebreaker として決定論的順序を保証 |
| `find_by_room` の ORDER BY を created_at ASC | Room チャネルで「最新 directive を先頭表示」するのが UI / CLI の自然な表示順（最も新しい CEO 指令が先頭、時系列降順）。ASC だと古い directive を先頭に表示する逆順になりユーザー体験が悪い |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: empire / workflow / agent / room テンプレート 100% 継承（再凍結）

| 継承項目 | 本 PR への適用 |
|---|---|
| empire §確定 A | `application/ports/directive_repository.py` 新規、Protocol、`@runtime_checkable` なし |
| empire §確定 B | save() で `directives` UPSERT（子テーブルなし、1 テーブルの UPSERT のみ） |
| empire §確定 C | `_to_row` / `_from_row` を private method に閉じる |
| empire §確定 D | `count()` は SQL `COUNT(*)` 限定 |
| empire §確定 E | CI 三層防衛 Layer 1 + Layer 2 + Layer 3 全部に Directive テーブル明示登録 |
| workflow §確定 E（正のチェック）| `directives.text` の `MaskedText` 必須を grep + arch test で物理保証 |
| room §確定 R1-A（save パターン） | `save(directive: Directive)` 標準 1 引数（[storage.md §確定 H](../../design/domain-model/storage.md) 判断ルール適用） |

#### 確定 R1-B: `target_room_id` FK 方向と ON DELETE 挙動

`directives.target_room_id` を `rooms.id` への FK 制約付きで宣言:

| 項目 | 値 | 根拠 |
|---|---|---|
| FK 参照先 | `rooms.id` | room-repository PR #47 マージ済み、0005_room_aggregate で `rooms` テーブル先行追加済み（chain 順序が物理保証） |
| ON DELETE | **`CASCADE`** | Directive は委譲先 Room に従属する（Room が消えると Directive は orphan）。RESTRICT だと Room 削除前に全 Directive を消す手順が必要で application 層が複雑化。CASCADE で Room 削除時に関連 Directive を自動削除するのが意味論的に自然 |
| ON UPDATE | 該当なし | UUID PK は不変、UPDATE 経路を持たない |
| FK 違反時 | `sqlalchemy.IntegrityError`（FK constraint failed） | application 層で catch、HTTP 404 / 409 にマッピング（別 feature） |

##### CASCADE / RESTRICT / SET NULL 比較

| 候補 | 採否 | 理由 |
|---|---|---|
| **`CASCADE`** | ✓ **採用** | Room 削除で当該 Room の Directive が自動削除。orphan directive を残さない |
| `RESTRICT` | ✗ | Room を削除するには先に全 Directive を消す手順が必要。application 層が複雑化し、Room archive 時の UX が悪化 |
| `SET NULL` | ✗ | `target_room_id` は NOT NULL（Directive は必ず委譲先 Room を持つ、directive §確定で凍結）。SET NULL は型違反 |
| FK を張らない | ✗ | 0006 時点で rooms テーブルは存在、forward reference 問題なし。**FK は張れる時に張る** が原則 |

#### 確定 R1-C: `task_id` FK closure 申し送り（BUG-EMR-001 パターン）

`directives.task_id` は nullable UUIDStr として 0006 で宣言するが、**`tasks.id` への FK は張らない**:

| 段階 | 内容 |
|---|---|
| 0006（本 PR） | `directives.task_id` を nullable UUIDStr として追加。FK なし（forward reference 問題） |
| task-repository（後続） | `tasks` テーブル追加 + `op.batch_alter_table('directives')` で `directives.task_id → tasks.id` FK を ON DELETE **RESTRICT** で追加（Directive が参照している Task は削除できない） |

`task_id` FK の ON DELETE は **RESTRICT**:
- Task が削除されると「発行元 Directive がある Task が消えた」状態になる。Directive は Task 発行の証跡であり、Task が消えたら Directive の task_id を NULL に戻すのではなく、Task 削除を物理的に拒否する方が audit trail として健全
- application 層が「Task を削除したい場合は先に Directive の task_id を None に遷移させる」手順を踏む（Fail Fast）

#### 確定 R1-D: `find_by_room` 追加 method と `find_by_task_id` 申し送り

**本 PR（0006）スコープ**: `find_by_room` のみ追加（4-method Protocol）。

| method | シグネチャ | 意図 |
|---|---|---|
| `find_by_room` | `async def find_by_room(room_id: RoomId) -> list[Directive]` | Room 内 directive 一覧を `created_at DESC, id DESC` で返却（BUG-EMR-001 規約: 決定論的順序） |

`find_by_room` の ORDER BY:
- **`created_at DESC, id DESC`** を採用（BUG-EMR-001 規約「複合 key で決定論的順序」適用）
- `created_at` が同一値の場合、`id`（PK、UUIDv4、一意）を tiebreaker として使用し順序を完全決定論化
- INDEX `(target_room_id, created_at)` が複合 INDEX の左端プリフィックスで `WHERE target_room_id = :room_id` → `ORDER BY created_at DESC` をカバー。`id` 追加は SQLite が PK lookup で補完

**task-repository PR への申し送り（`find_by_task_id`）**:
- task-repository PR で `find_by_task_id(task_id: TaskId) -> Directive | None` を Protocol に追加、同時に `directives.task_id` への INDEX + FK closure（§確定 R1-C）を一括追加する
- 「呼び出し側（task-application）が存在しない状態で method + INDEX なし」の矛盾を task-repository PR 時点で解消する（YAGNI 原則 — PR #47 §count_by_empire YAGNI 却下と同論理）

#### 確定 R1-E: CI 三層防衛の Directive 拡張

| Layer | 内容 |
|---|---|
| Layer 1（grep guard） | `scripts/ci/check_masking_columns.sh` に `tables/directives.py` の `text` カラム宣言行に `MaskedText` 必須（正のチェック）+ `text` 以外のカラムに `MaskedText` / `MaskedJSONEncoded` が登場しない（過剰マスキング防止、負のチェック）を追加 |
| Layer 2（arch test） | `backend/tests/architecture/test_masking_columns.py` の parametrize に `directives` テーブル追加、`directives.text` の `column.type.__class__ is MaskedText` を assert |
| Layer 3（storage.md） | `docs/design/domain-model/storage.md` §逆引き表に `directives.text: MaskedText`（feature/directive-repository 実適用）行を追加 |

#### 確定 R1-F: storage.md §逆引き表更新

§逆引き表に Directive 関連 2 行追加:

| 行 | 内容 |
|---|---|
| 追加行 (a) | `directives.text: MaskedText`（directive §確定 G **実適用**、persistence-foundation #23 で hook 構造提供済みを本 PR で配線） |
| 追加行 (b) | `directives` 残カラム（`id` / `target_room_id` / `created_at` / `task_id`）は masking 対象なし（UUIDStr / DateTime、CI 三層防衛で「対象なし」を明示登録） |

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| CEO（リポジトリオーナー） | bakufu システムの directive 発行者 | 非技術者〜中級 | Room チャネルで `$` プレフィックスのメッセージを送信し directive を起票 | 発行した指令が安全に永続化され、後続 Task が生成されること |
| 実装者（bakufu contributor） | directive-application / task-application 実装担当 | 上級 | DirectiveRepository を使って application 層を実装 | 型安全な 4 method Protocol で Directive を永続化・復元できること |

<!-- bakufu システム全体ペルソナは docs/analysis/personas.md を参照。-->

## 前提条件・制約

| 区分 | 内容 |
|-----|------|
| 既存技術スタック | Python 3.12 / SQLAlchemy 2.x async / Alembic / aiosqlite（M2 永続化基盤済み） |
| 既存 CI | GitHub Actions + pytest + pyright strict（既存） |
| 既存ブランチ戦略 | GitFlow（CONTRIBUTING.md §ブランチ戦略） |
| コミット規約 | Conventional Commits |
| ライセンス | MIT |
| ネットワーク | 外部通信なし（infrastructure 層、SQLite ローカル） |
| 対象 OS | Linux / macOS（SQLite aiosqlite 共通） |
| Alembic chain 前提 | 0005_room_aggregate（PR #47）マージ済みが必須 |

## 機能一覧

| 機能ID | 機能名 | 概要 | 優先度 |
|--------|-------|------|--------|
| REQ-DRR-001 | DirectiveRepository Protocol 定義 | `application/ports/directive_repository.py` で `DirectiveRepository(Protocol)` を定義（4 method） | 必須 |
| REQ-DRR-002 | SqliteDirectiveRepository 実装 | `infrastructure/persistence/sqlite/repositories/directive_repository.py` で SQLAlchemy 2.x async を使用して 4 method を実装 | 必須 |
| REQ-DRR-003 | Alembic 0006 revision | `0006_directive_aggregate.py` で `directives` テーブル追加 + INDEX + FK | 必須 |
| REQ-DRR-004 | CI 三層防衛の Directive 拡張 | grep guard / arch test / storage.md を Directive テーブルで拡張（正/負のチェック併用） | 必須 |
| REQ-DRR-005 | storage.md 逆引き表更新 | `directives.text: MaskedText` 行追加 + `directives` 残カラム masking 対象なし明示 | 必須 |

## Sub-issue 分割計画

該当なし — 理由: 単一テーブル、4 method Protocol、CI 拡張のみで Sub-issue 分割不要。1 PR で完結する規模。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 該当なし | — | — | — |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | `find_by_room` は INDEX(target_room_id, created_at) で O(log N) 以下。MVP 数百 Directive でフルスキャン発生なし |
| 可用性 | SQLite ローカル、外部依存なし |
| 保守性 | pyright strict で `SqliteDirectiveRepository` が `DirectiveRepository(Protocol)` を満たすことを型レベル検証 |
| 可搬性 | aiosqlite / SQLAlchemy 2.x async のみ、OS 非依存 |
| セキュリティ | `directives.text` は `MaskedText` TypeDecorator で `process_bind_param` 経由マスキング。CI 三層防衛で実装漏れを物理保証 |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | `DirectiveRepository(Protocol)` が 4 method（`find_by_id` / `count` / `save` / `find_by_room`）を定義している | pyright strict 型チェック |
| 2 | `SqliteDirectiveRepository` が `DirectiveRepository(Protocol)` を満たす | pyright strict 型チェック |
| 3 | `find_by_id(directive_id)` が存在する Directive を返し、存在しない場合 None を返す | TC-UT-DRR-001, TC-UT-DRR-002 |
| 4 | `save(directive)` が `directives` テーブルに正しく永続化し、`find_by_id` で復元できる | TC-UT-DRR-003 |
| 5 | `directives.text` が DB に保存される際 `MaskedText` によりマスキングされる | TC-IT-DRR-010 |
| 6 | `find_by_room(room_id)` が当該 Room の Directive 一覧を `created_at DESC, id DESC` で返す（BUG-EMR-001 規約: 同時刻の場合 id で決定論的順序） | TC-UT-DRR-004 |
| 7 | `count()` が `directives` テーブルの行数を返す | TC-UT-DRR-005 |
| 8 | Alembic 0006 が `alembic upgrade head` / `alembic downgrade -1` でエラーなく動作する | TC-IT-DRR-001 |
| 9 | `rooms.id` FK（ON DELETE CASCADE）が動作し、Room 削除時に Directive が自動削除される | TC-IT-DRR-005 |
| 10 | `directives.task_id` は nullable で FK なし（0006 時点で tasks テーブル未存在） | Alembic revision 確認 |
| 11 | CI grep guard が `directives.text` 以外のカラムへの `MaskedText` 追加を検出して失敗する | CI grep guard 実行 |
| 12 | storage.md §逆引き表に `directives.text: MaskedText` 行が追加されている | ドキュメント確認 |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| `Directive.text` | CEO が発行した指令テキスト（`$` プレフィックス + 本文）。Discord webhook URL / API key が混入し得る | **高**（`MaskedText` で永続化前マスキング必須） |
| `DirectiveId` / `target_room_id` / `task_id` | UUID 参照値 | 低 |
| `created_at` | 指令発行 UTC 時刻 | 低 |
