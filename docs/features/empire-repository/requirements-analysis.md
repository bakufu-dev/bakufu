# 要求分析書

> feature: `empire-repository`
> Issue: [#25 feat(empire-repository): Empire SQLite Repository (M2)](https://github.com/bakufu-dev/bakufu/issues/25)
> 凍結済み設計: [`docs/architecture/domain-model/aggregates.md`](../../architecture/domain-model/aggregates.md) §Empire / [`docs/features/persistence-foundation/requirements-analysis.md`](../persistence-foundation/requirements-analysis.md) §確定 R1-D（TypeDecorator 採用 + CI 三層防衛）/ [`docs/features/empire/`](../empire/) （domain 設計済み）

## 人間の要求

> Issue #25:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の **最初の Aggregate Repository PR** として **Empire Repository** を実装する。M2 永続化基盤（PR #23、`persistence-foundation`）の上に乗る最初の Aggregate 別 Repository で、後続 6 件（workflow / agent / room / directive / task / external-review-gate）の **Repository 実装パターンを確立する**責務を持つ。Empire は最小 Aggregate（属性 4 件、参照型 RoomRef / AgentRef のみ、masking 対象カラムなし）のため、CI 三層防衛 + Repository ↔ domain 変換 + Alembic revision 拡張のテンプレートを最小コストで凍結できる。

## 背景・目的

### 現状の痛点

1. M2 永続化基盤（PR #23）が完了したが、**Aggregate 別 Repository が一切実装されていない**。`mvp-scope.md` 受入基準 #8「再起動後も Empire / Room / Agent / Task / Gate の状態が SQLite から復元される」を満たす経路が存在しない
2. 後続 Repository PR（workflow / agent / room / directive / task / external-review-gate）は **Repository 実装パターンの真実源**を必要としている。最初の PR が確立しないと 6 件の PR 並列着手で実装方針が分散する
3. M3 HTTP API は全 Aggregate の Repository を前提とする（`POST /empires` / `GET /empires/{id}` 等）。Repository が揃わないと M3 着手不可

### 解決されれば変わること

- Repository 実装パターンの真実源（Protocol 配置 / SQLite 実装配置 / domain ↔ row 変換 / `save()` 戦略 / Alembic revision 段階追加 / CI 三層防衛拡張）が確立、後続 6 件 PR が本 PR の確定 A〜F を直接参照して実装可能
- Empire の永続化が動作することで、Empire のシングルトン強制（application 層 `EmpireService.create()` が `count() == 0` を確認）が動作可能になる
- M3 HTTP API の Empire endpoint が着手可能になる

### ビジネス価値

- bakufu MVP の**永続化レイヤの起点**を確保。Empire は最上位 Aggregate のため、これが永続化されれば後続 Repository の参照整合性検査（`empire_id` FK）も成立する
- 「最小 Aggregate でテンプレートを確立する」アプローチにより、後続 Repository PR の実装コストを大幅に削減（同パターンをコピー&ペーストできる）

## 議論結果

### 設計担当による採用前提

- **Repository ポート配置**: `application/ports/{aggregate}_repository.py` で **Aggregate 別ファイル分離**（単一ファイル集約は肥大化、domain 配置は依存方向違反、§確定 R1-A）
- **`save()` 戦略**: **delete-then-insert**（同一 Tx 内で `DELETE FROM empire_room_refs WHERE empire_id=?` → 全件 `INSERT`、§確定 R1-B、イーロン承認済み）
- **domain ↔ row 変換**: `SqliteEmpireRepository` クラス内 private method `_to_row()` / `_from_row()`（§確定 R1-C）
- **シングルトン強制**: `EmpireService.create()` 責務（本 PR スコープ外）、Repository は `count()` メソッド提供のみ
- **CI 三層防衛の Empire 拡張**: Empire は **masking 対象カラムを持たない**ため、grep guard / arch test に Empire テーブル群を**明示登録**して「対象なし」を assertion（後続 Repository PR の漏れ防止テンプレート）

### 却下候補と根拠

| 候補 | 却下理由 |
|-----|---------|
| 全 Aggregate Repository を `application/ports/repositories.py` 単一ファイルに集約 | ファイル肥大化（7 Aggregate × 各 5〜10 メソッド = 50〜70 メソッドが 1 ファイル）、Aggregate 追加時の merge conflict が頻発 |
| Repository ポート（Protocol）を domain 層に配置（`domain/empire/repository.py`） | **依存方向違反**（domain は外側を知らない、Repository ポートは application 層、SQLite 実装は infrastructure 層）。clean architecture / DDD の依存方向（domain ← application ← infrastructure）と相容れない |
| `save()` 戦略を in-place 更新（差分計算 + INSERT/UPDATE/DELETE） | 差分計算が複雑、楽観排他なしでは race condition、シングルトン前提では不要な複雑性 |
| `save()` 戦略を event sourcing | MVP 範囲外（YAGNI）、永続化基盤 PR #23 が `domain_event_outbox` で結果整合を実現しており、Aggregate 内部状態は CRUD で十分 |
| domain ↔ row 変換を SQLAlchemy `composite()` / `class_mapper` の column_property 経由 | Aggregate Root の VO 構造（`RoomRef` / `AgentRef`）が複雑、SQLAlchemy 内部に閉じ込めると変換ロジックが見えにくい、テスト容易性が下がる |
| domain ↔ row 変換を別 module（`empire_mapper.py`）の free function で分離 | ファイル数増加、Repository に閉じる責務（外部から呼ばれない）のため private method で十分 |
| シングルトン強制ロジックを Repository に配置 | Aggregate 集合知識（同 bakufu インスタンスに Empire は 1 件）は Repository 単独では判定できない（Repository は CRUD のみ）。application 層 `EmpireService.create()` の責務（empire feature §確定 R1-B 既凍結） |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: Repository ポート配置 — Aggregate 別ファイル分離（イーロン承認済み）

`application/ports/{aggregate}_repository.py` で各 Aggregate に独立した Protocol ファイルを配置する。本 PR では `application/ports/empire_repository.py` のみ追加、後続 Repository PR が同パターンで `workflow_repository.py` / `agent_repository.py` 等を追加する。

ディレクトリ構造（テンプレートとして凍結）:

```
backend/src/bakufu/
└── application/
    ├── __init__.py            # 新規（最初の application 層ファイル）
    └── ports/
        ├── __init__.py        # 新規
        └── empire_repository.py  # 新規（本 PR）
```

`@runtime_checkable` は付与しない（Python 3.12 typing.Protocol の duck typing で十分、isinstance チェックは不要）。

#### 確定 R1-B: `save()` 戦略 — delete-then-insert（イーロン承認済み）

参照型カラム（`empire_room_refs` / `empire_agent_refs`）の更新は **同一 Tx 内で `DELETE WHERE empire_id=?` → 全件 `INSERT`** で実装する。

| 段階 | 動作 |
|---|---|
| 1 | `async with session.begin():` で UoW 境界（呼び出し側 service 層が管理） |
| 2 | `empires` 行を UPSERT（id 主キーで INSERT or UPDATE） |
| 3 | `DELETE FROM empire_room_refs WHERE empire_id = :empire_id` で全削除 |
| 4 | `empire.rooms` 全件を `INSERT INTO empire_room_refs ...` |
| 5 | `DELETE FROM empire_agent_refs WHERE empire_id = :empire_id` で全削除 |
| 6 | `empire.agents` 全件を `INSERT INTO empire_agent_refs ...` |

##### delete-then-insert 採用根拠

| 検討事項 | delete-then-insert | 差分計算 | event sourcing |
|---|---|---|---|
| 実装複雑性 | ✓ シンプル（DELETE + INSERT） | ✗ 差分計算ロジック | ✗ 別パラダイム |
| Tx 原子性 | ✓ 同一 Tx で完結 | △ 複雑な順序制御 | ✓ append-only |
| 楽観排他 | ✓ 不要（シングルトン前提） | ✗ version 列必要 | ✓ event_id |
| race condition | ✓ なし（シングルトン + 同一 Tx） | ✗ 並行更新でデッドロック可 | ✓ なし |
| パフォーマンス | △ 全件 DELETE/INSERT（Empire は MVP で N≤100 なので問題なし） | ✓ 差分のみ | △ event 圧縮必要 |
| 後続 Repository への適用性 | ✓ 同パターンで他 Aggregate にも転用可（room の members 等） | △ Aggregate ごとに差分計算ロジックを書く必要 | ✗ 別パラダイム |

MVP 範囲（N ≤ 100）でのパフォーマンス劣化は無視できる。後続 Repository PR（room の members、workflow の stages / transitions 等）が同パターンで実装可能なため、テンプレートとしての価値が最大。

#### 確定 R1-C: domain ↔ row 変換 — Repository クラス内 private method

`SqliteEmpireRepository` クラス内に `_to_row(empire: Empire) -> dict` / `_from_row(empire_row, room_refs, agent_refs) -> Empire` を private method として配置する。

理由:

- Repository に閉じる責務（外部から呼ばれない、テストは Repository を介して間接的に検証）
- Aggregate Root の VO 構造（`RoomRef` / `AgentRef`）を SQLAlchemy mapping から分離、domain 層が SQLAlchemy に依存しない
- pyright strict pass のため戻り値型を明示（`dict[str, Any]` / `Empire`）

#### 確定 R1-D: シングルトン強制の責務分離（empire feature §確定 R1-B 踏襲）

Empire の「bakufu インスタンスにつき Empire は 1 件」というシングルトン制約は**集合知識**であり Repository 単独では判定できない。`EmpireService.create()` の application 層が `EmpireRepository.count()` を呼び `count > 0` なら `EmpireAlreadyExistsError` を raise する責務（既に empire feature §確定 R1-B で凍結済み）。

本 PR では Repository に `count() -> int` メソッドを提供するのみ、シングルトン強制ロジックは別 PR `feature/empire-application` に分離。

#### 確定 R1-E: CI 三層防衛の Empire 拡張

Empire テーブル群（`empires` / `empire_room_refs` / `empire_agent_refs`）は **masking 対象カラムを持たない**。後続 Repository PR が「Empire の例があるから masking 対象漏れに気づかない」という事故を防ぐため、CI 三層防衛に**明示登録**する:

| Layer | 拡張内容 |
|---|---|
| Layer 1（grep guard） | `scripts/ci/check_masking_columns.sh` の対象テーブルリストに Empire 関連 3 テーブルを **明示登録**し、masking 対象カラムが存在しないことを検証（追加されたら違反）|
| Layer 2（arch test） | `backend/tests/architecture/test_masking_columns.py` の parametrize に 3 テーブル追加、各カラムが `MaskedJSONEncoded` / `MaskedText` **でない**（= 通常 String / Boolean / UUIDStr のみ）を assert |
| Layer 3（逆引き表） | `storage.md` §逆引き表に「Empire 関連カラム: masking 対象なし」行を追加（後続 Repository PR が誤って `MaskedText` を指定しないよう注記） |

#### 確定 R1-F: 後続 Repository PR のテンプレート責務

本 PR は最小 Aggregate（Empire は属性 4 件、masking 対象ゼロ、Domain Event なし）のため、Repository 実装パターンを最小コストで凍結できる**最適なテンプレート**。後続 Repository PR（workflow / agent / room / directive / task / external-review-gate）は本 PR の確定 A〜F を直接参照して実装する。

確立する設計判断:

- `application/ports/{aggregate}_repository.py` の Protocol 定義方式（§確定 R1-A）
- `infrastructure/persistence/sqlite/repositories/{aggregate}_repository.py` の SQLite 実装
- `_to_row` / `_from_row` の private method による domain ↔ row 変換（§確定 R1-C）
- delete-then-insert 戦略による参照型カラムの save 実装（§確定 R1-B）
- Alembic revision の段階的追加（initial revision に Aggregate を含めない、各 Aggregate Repository PR が個別 revision を積む）
- CI 三層防衛の parametrize 拡張義務（§確定 R1-E）

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 後続 Repository PR 担当（バックエンド開発者） | `feature/workflow-repository` / `feature/agent-repository` 等の実装者 | DDD 経験あり、SQLAlchemy 2.x async / Pydantic v2 経験あり | 本 PR の設計書を真実源として読み、Aggregate Repository を 1 件積む | 本 PR の確定 A〜F を素直に踏襲するだけで、後段レビューで責務散在を指摘されない |
| 個人開発者 CEO（堀川さん想定） | bakufu インスタンスのオーナー | GitHub / Docker / CLI 日常使用 | bakufu Backend を起動し、UI で Empire を作成、再起動後も Empire 状態が復元される | 永続化を意識せずに UI で Empire を扱える |

##### ペルソナ別ジャーニー（後続 Repository PR 担当）

1. **本 PR の設計書を読む**: `docs/features/empire-repository/` の 4 本を読み、確定 A〜F を理解する
2. **Aggregate Repository PR の起票**: `feat(workflow-repository): Workflow SQLite Repository (M2)` を起票
3. **設計書 4 本作成**: 本 PR の構造を踏襲、Aggregate 固有の差分（masking 対象カラム / 子 Entity 構造）のみ記述
4. **実装**: `application/ports/workflow_repository.py` Protocol 追加、`infrastructure/persistence/sqlite/repositories/workflow_repository.py` で SqliteWorkflowRepository 実装、`alembic/versions/0003_workflow_aggregate.py` 追加、CI 三層防衛の parametrize 拡張
5. **テスト**: 本 PR の `test_empire_repository.py` 構造を踏襲、Workflow 固有のテストケースを追加

##### ジャーニーから逆算した受入要件

- ジャーニー 1: 設計書が「テンプレートとして読める」構造（確定 A〜F が独立して凍結、Aggregate 固有部分が明確に分離）
- ジャーニー 4: ファイル配置・命名規則が機械的に follow できる
- ジャーニー 5: テスト構造が `test_empire_repository.py` を雛形にできる

bakufu システム全体のペルソナは [`docs/architecture/context.md`](../../architecture/context.md) §4 を参照。

## 前提条件・制約

| 区分 | 内容 |
|-----|------|
| 既存技術スタック | Python 3.12+ / SQLAlchemy 2.x async / Alembic / Pydantic v2 / pyright strict / pytest（M2 永続化基盤 #23 で確立） |
| 既存 CI | lint / typecheck / test-backend / audit / **CI 三層防衛 Layer 1 (check_masking_columns.sh) + Layer 2 (test_masking_columns.py)**（M2 で確立） |
| 既存ブランチ戦略 | GitFlow（CONTRIBUTING.md §ブランチ戦略） |
| コミット規約 | Conventional Commits |
| ライセンス | MIT |
| ネットワーク | 該当なし — infrastructure 層（local SQLite） |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |

## 機能一覧

| 機能ID | 機能名 | 概要 | 優先度 |
|--------|-------|------|--------|
| REQ-EMR-001 | EmpireRepository Protocol 定義 | `application/ports/empire_repository.py` で Protocol を定義（`find_by_id` / `count` / `save`） | 必須 |
| REQ-EMR-002 | SqliteEmpireRepository 実装 | `infrastructure/persistence/sqlite/repositories/empire_repository.py` で SQLite 実装 | 必須 |
| REQ-EMR-003 | Alembic 2nd revision | `0002_empire_aggregate.py` で 3 テーブル追加（`empires` / `empire_room_refs` / `empire_agent_refs`） | 必須 |
| REQ-EMR-004 | CI 三層防衛の Empire 拡張 | grep guard + arch test に Empire テーブル群を明示登録（masking 対象なし assertion） | 必須 |
| REQ-EMR-005 | storage.md 逆引き表更新 | Empire 関連カラムが masking 対象なしを明示する行を追加 | 必須 |

## Sub-issue 分割計画

本 Issue は意図的に**Repository 実装パターン確立に絞った 1 PR**であり、後続 Aggregate Repository（6 件）を別 PR に分離することで既に分割済み。本 Issue 自体をさらに分割すると Alembic revision が複数 PR に跨がり head 管理が壊れる。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 単一 PR | REQ-EMR-001〜005 | 設計書 4 本 + application/ports/ + infrastructure/persistence/sqlite/repositories/ + alembic/versions/0002_*.py + CI 三層防衛拡張 + storage.md 更新 + ユニット / 結合テスト | M2 永続化基盤（PR #23）+ M1 empire (#8) マージ済み |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | `find_by_id` < 10ms（Empire は MVP で N≤100、JOIN 込みでも問題なし）、`save()` < 50ms（delete-then-insert で 100 件 INSERT 含む） |
| 可用性 | M2 永続化基盤（WAL モード + crash safety + masking gateway）の上に乗る、追加要件なし |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 90% 以上（基盤に近いコードのため高カバレッジ目標、persistence-foundation 実績水準） |
| 可搬性 | M2 と同じ（POSIX 限定機能なし、純 SQLAlchemy） |
| セキュリティ | Empire には masking 対象カラムなし。CI 三層防衛で「対象なし」を明示登録（後続 Repository PR の漏れ防止）。詳細は [`threat-model.md`](../../architecture/threat-model.md) §A4 |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | `EmpireRepository` Protocol が `application/ports/empire_repository.py` で定義される（`find_by_id` / `count` / `save` の 3 メソッド） | TC-IT-EMR-001 |
| 2 | `SqliteEmpireRepository` が Protocol を満たす（pyright strict pass） | CI typecheck |
| 3 | `find_by_id(empire_id)` が新規 Empire を取得できる | TC-IT-EMR-002 |
| 4 | `find_by_id(unknown_id)` が `None` を返す | TC-IT-EMR-003 |
| 5 | `count()` が 0 件 / 1 件で正しい値を返す | TC-IT-EMR-004 |
| 6 | `save(empire)` が新規 Empire を挿入する（empires + empire_room_refs + empire_agent_refs の 3 テーブルに行が入る） | TC-IT-EMR-005 |
| 7 | `save(empire)` が既存 Empire の `rooms` / `agents` 変更を反映する（delete-then-insert 戦略、§確定 R1-B） | TC-IT-EMR-006 |
| 8 | domain ↔ row のラウンドトリップで構造的等価が保たれる（`save(empire)` → `find_by_id(empire.id)` → 復元 Empire == 元 Empire） | TC-IT-EMR-007 |
| 9 | Alembic 2nd revision で 3 テーブルが追加され、`alembic upgrade head` / `downgrade base` 双方が緑 | TC-IT-EMR-008 |
| 10 | CI 三層防衛 Layer 1（grep guard）が Empire 3 テーブルで「masking 対象なし」を pass | TC-CI-EMR-001 |
| 11 | CI 三層防衛 Layer 2（arch test）が Empire 3 テーブルで `column.type.__class__` が `MaskedJSONEncoded` / `MaskedText` でないことを assert | TC-IT-EMR-009 |
| 12 | `domain` 層から `application` / `infrastructure` への import がゼロ件（既存 CI 検査で確認） | CI script |
| 13 | `pyright --strict` および `ruff check` がエラーゼロ | CI lint / typecheck |
| 14 | カバレッジが `application/ports/empire_repository.py` / `infrastructure/persistence/sqlite/repositories/empire_repository.py` で 90% 以上 | pytest --cov |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| `empires.id` / `empires.name` | Empire の表示名（CEO 任意の文字列、例: "山田の幕府"） | 低 |
| `empire_room_refs.*` | Room 参照（id / name / archived） | 低 |
| `empire_agent_refs.*` | Agent 参照（id / name / role） | 低 |
| **masking 対象カラム** | **なし**（Empire 関連 3 テーブルすべて、storage.md §逆引き表で凍結） | — |
