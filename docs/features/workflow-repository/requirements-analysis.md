# 要求分析書

> feature: `workflow-repository`
> Issue: [#31 feat(workflow-repository): Workflow SQLite Repository (M2, 0003)](https://github.com/bakufu-dev/bakufu/issues/31)
> 凍結済み設計: [`docs/features/empire-repository/`](../empire-repository/) **§確定 A〜F + §Known Issues §BUG-EMR-001 規約**（テンプレート真実源、必読）/ [`docs/architecture/domain-model/aggregates.md`](../../architecture/domain-model/aggregates.md) §Workflow / [`docs/features/workflow/`](../workflow/) （domain 設計済み、PR #16 マージ済み）

## 人間の要求

> Issue #31:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の後続 Repository PR（empire-repository #25 のテンプレート責務継承）。Workflow Aggregate の SQLite 永続化を実装する。Alembic revision 0003_workflow_aggregate で `workflows` / `workflow_stages` / `workflow_transitions` の 3 テーブル + 関連 INDEX を追加。

## 背景・目的

### 現状の痛点

1. **M2 永続化基盤（PR #23）+ empire-repository（PR #29 / #30）が完了したが、Workflow Aggregate の永続化がない**。`mvp-scope.md` 受入基準 #8「再起動後も Empire / Room / Agent / Task / Gate の状態が SQLite から復元される」のうち Workflow 永続化が宙に浮いている
2. M2 後続 Repository 5 件（agent / room / directive / task / external-review-gate）は Workflow テーブルへの参照（`rooms.workflow_id` FK）を必要とする。**workflow-repository を最初に積まないと後続 Repository PR の Alembic revision で FK が張れない**
3. M3 HTTP API は Workflow CRUD endpoint を必要とする（CEO が Workflow プリセットを選択して Room を編成する MVP 受入基準 #2）。Repository が揃わないと M3 着手不可

### 解決されれば変わること

- room-repository (#33) が `rooms.workflow_id` を `workflows.id` への FK で宣言できる
- M2 Repository 6 件のテンプレート責務（empire-repository #25 の確定 A〜F + §Known Issues §BUG-EMR-001 規約）を継承する **2 例目** が揃い、後続 PR（agent / room / directive / task / gate）の参照源が増える
- Workflow 固有の永続化論点（`Stage.required_role: frozenset[Role]` のシリアライズ / `Stage.notify_channels: list[NotifyChannel]` の masking / `entry_stage_id` 参照整合性）を凍結し、後続 Repository PR が同様の VO 永続化問題に直面したとき本 PR を参照できる

### ビジネス価値

- bakufu MVP の **「V モデル開発フロー」「アジャイル 1 週間スプリント」等のプリセット Workflow** を永続化し、再起動後も維持できるようになる
- Workflow を中核とする Vモデル E2E（M7）への最短経路の中継地点を確保

## 議論結果

### 設計担当による採用前提

- **テンプレート責務 100% 継承**: empire-repository #25 の §確定 A〜F + §Known Issues §BUG-EMR-001 規約を**そのまま踏襲**。本 feature 固有の論点は確定 G〜J で追加凍結する
- `workflow_stages` / `workflow_transitions` の子テーブル更新は **delete-then-insert**（同一 Tx、§確定 B）
- `find_by_id` の子テーブル SELECT に **`ORDER BY stage_id` / `ORDER BY transition_id` 必須**（§Known Issues §BUG-EMR-001 規約）
- `count()` は **`select(func.count()).select_from(WorkflowRow)`** で SQL レベル COUNT(*)（§確定 D 補強）
- `Stage.notify_channels` の Discord webhook token は **`MaskedJSONEncoded`** で `process_bind_param` 経由マスキング（Schneier 申し送り #6 + workflow feature §確定 G の実適用）
- ディレクトリ構造は empire-repository と完全対称（`application/ports/workflow_repository.py` + `infrastructure/persistence/sqlite/repositories/workflow_repository.py` + `tables/{workflows,workflow_stages,workflow_transitions}.py`）

### 却下候補と根拠

| 候補 | 却下理由 |
|-----|---------|
| `Stage.required_role: frozenset[Role]` を子テーブル `workflow_stage_required_roles(stage_id, role)` で正規化 | テーブル数増加、Stage の VO 構造に対して過剰正規化。enum の文字列 set 程度なら CSV シリアライズで十分（§確定 G） |
| `Stage.notify_channels: list[NotifyChannel]` を子テーブル `workflow_stage_notify_channels(stage_id, idx, channel_kind, target)` で正規化 | Stage は固定数の Channel しか持たない見込み（MVP で 1〜3 件）、正規化のメリット少ない。子テーブル増加でクエリ複雑化（§確定 H） |
| `Stage.required_role` の persistence を `roles_json: JSONEncoded` の JSON 配列で保持 | enum の文字列リスト程度なら CSV で十分、JSON 化は YAGNI（§確定 G） |
| `Workflow.entry_stage_id` を `workflow_stages.stage_id` への DB レベル FK で宣言 | **循環参照**（Workflow → Stage → Workflow）、SQLAlchemy + SQLite で自然に表現できない。Aggregate 内不変条件で守る（§確定 J、workflow #16 で凍結済み） |
| empire-repository と異なる Repository ポート配置（単一ファイル集約 / domain 層配置 等） | empire-repository §確定 A で凍結済み、本 PR は同パターンを踏襲する責務 |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: empire-repository テンプレート 100% 継承（再凍結）

empire-repository #25 の以下の確定をすべて本 PR に継承する:

| 確定 | 規約 | 本 PR への適用 |
|---|---|---|
| §確定 A | Repository ポート Aggregate 別ファイル | `application/ports/workflow_repository.py` |
| §確定 B | `save()` は delete-then-insert（同一 Tx、Repository は commit / rollback しない） | `save(workflow)` で workflows UPSERT + workflow_stages DELETE+INSERT + workflow_transitions DELETE+INSERT |
| §確定 C | domain ↔ row 変換は `_to_row()` / `_from_row()` private method | 同パターン、Stage / Transition の VO 構造を SQLAlchemy mapping から分離 |
| §確定 D | `count()` は `select(func.count()).select_from(WorkflowRow)` で SQL レベル COUNT(*) | 同パターン（empire-repo PR #29 で凍結） |
| §確定 E | CI 三層防衛 grep guard + arch test + storage.md §逆引き表 | 本 PR で Workflow 3 テーブルを Layer 1+2+3 に登録、`notify_channels_json` の `MaskedJSONEncoded` を物理保証 |
| §確定 F | 11 項目チェックリスト遵守 | 本 PR の受入基準で全件 ✓ |
| §Known Issues §BUG-EMR-001 規約 | `find_by_id` の子テーブル SELECT に必ず `ORDER BY` 発行、test は `sorted(...)` で list 順序比較 | `ORDER BY stage_id` / `ORDER BY transition_id` |

本 PR は確定 A〜F を再議論しない（empire-repo PR #29 / #30 で確定済み）。

#### 確定 R1-B: Workflow 固有の確定 G〜J（本 PR で新規凍結）

| 確定 | 内容 |
|---|---|
| 確定 G | `Stage.required_role: frozenset[Role]` の **`roles_csv: String` カンマ区切りシリアライズ**（順序決定論的、テスト容易性のため `sorted(role.value for role in stage.required_role)` でソートしてから `","` で結合） |
| 確定 H | `Stage.notify_channels: list[NotifyChannel]` の **`notify_channels_json: MaskedJSONEncoded` で inline JSON**（`process_bind_param` で webhook token を `<REDACTED:DISCORD_WEBHOOK>` 化、Schneier 申し送り #6 + workflow feature §確定 G 実適用） |
| 確定 I | `Stage.completion_policy: CompletionPolicy` の **`completion_policy_json: JSONEncoded` で inline JSON**（masking 対象外、公開可能な設定値） |
| 確定 J | `Workflow.entry_stage_id` の参照整合性は **Aggregate 内不変条件で守る**（DB レベル FK は循環参照のため宣言しない、workflow #16 で凍結済み） |

#### 確定 R1-C: Alembic revision chain 一直線

`0003_workflow_aggregate.py` の `down_revision = "0002_empire_aggregate"` で chain を一直線化（empire-repo PR #29 で確立した規約）。本 PR で head が分岐しないことを CI で検査（既存の `test_alembic_chain.py` の parametrize に `0003` を追加）。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 後続 Repository PR 担当（バックエンド開発者） | `feature/27-agent-repository` 等の実装者 | DDD 経験あり、SQLAlchemy 2.x async 経験あり | 本 PR の設計書を真実源として読み、Aggregate Repository を 1 件積む | 本 PR の確定 A〜J を素直に踏襲して実装 |
| 個人開発者 CEO（堀川さん想定） | bakufu インスタンスのオーナー | UI で Workflow プリセットを選択して Room を編成 | 永続化を意識せずに Workflow を扱える |

##### ペルソナ別ジャーニー（後続 Repository PR 担当）

1. **本 PR の設計書を読む**: empire-repository (#25) の真実源 + 本 PR の Workflow 固有確定 G〜J を理解
2. **agent-repository PR の起票**: `feat(agent-repository): Agent SQLite Repository (M2, 0004, Schneier #3 実適用)` を起票
3. **設計書 4 本作成**: 本 PR と empire-repo の構造を踏襲、Agent 固有の差分（`Persona.prompt_body` の `MaskedText`、Schneier #3 実適用）のみ記述
4. **実装**: ファイル配置・命名規則は本 PR を雛形にできる
5. **テスト**: 本 PR の test 構造（`test_protocol_crud.py` / `test_save_semantics.py` / `test_constraints_arch.py`）を踏襲

bakufu システム全体のペルソナは [`docs/architecture/context.md`](../../architecture/context.md) §4 を参照。

## 前提条件・制約

| 区分 | 内容 |
|-----|------|
| 既存技術スタック | Python 3.12+ / SQLAlchemy 2.x async / Alembic / Pydantic v2 / pyright strict / pytest（M2 永続化基盤 #23 で確立） |
| 既存 CI | lint / typecheck / test-backend / audit / **CI 三層防衛 Layer 1 + Layer 2**（M2 で確立） |
| 既存ブランチ戦略 | GitFlow |
| コミット規約 | Conventional Commits |
| ライセンス | MIT |
| ネットワーク | 該当なし — infrastructure 層 |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |

## 機能一覧

| 機能ID | 機能名 | 概要 | 優先度 |
|--------|-------|------|--------|
| REQ-WFR-001 | WorkflowRepository Protocol 定義 | `application/ports/workflow_repository.py` で Protocol を定義（`find_by_id` / `count` / `save`） | 必須 |
| REQ-WFR-002 | SqliteWorkflowRepository 実装 | `infrastructure/persistence/sqlite/repositories/workflow_repository.py` で SQLite 実装 | 必須 |
| REQ-WFR-003 | Alembic 0003 revision | `0003_workflow_aggregate.py` で 3 テーブル追加（`workflows` / `workflow_stages` / `workflow_transitions`） | 必須 |
| REQ-WFR-004 | CI 三層防衛の Workflow 拡張 | grep guard + arch test に Workflow 3 テーブルを明示登録（`notify_channels_json` の `MaskedJSONEncoded` 必須を物理保証、その他は対象なし） | 必須 |
| REQ-WFR-005 | storage.md 逆引き表更新 | Workflow 関連カラムを追加（`workflow_stages.notify_channels_json` を `MaskedJSONEncoded` で明示、その他は masking 対象なし） | 必須 |

## Sub-issue 分割計画

本 Issue は単一 Repository PR に閉じる粒度（empire-repository と同規模）。Sub-issue 分割不要。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 単一 PR | REQ-WFR-001〜005 | 設計書 4 本 + Repository ポート + SQLite 実装 + Alembic 0003 + CI 三層防衛拡張 + storage.md 更新 + ユニット / 結合テスト | M2 永続化基盤（PR #23）+ M1 workflow（PR #16）+ empire-repository（PR #29 / #30）マージ済み |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | `find_by_id` < 50ms（Workflow stages 10 件 + transitions 20 件想定の JOIN）、`save()` < 100ms（delete-then-insert で 30 件 INSERT 含む） |
| 可用性 | M2 永続化基盤の上に乗る、追加要件なし |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 90% 以上（empire-repo 実績水準） |
| 可搬性 | M2 と同じ |
| セキュリティ | `notify_channels_json` の Discord webhook token を `MaskedJSONEncoded` で永続化前マスキング。Schneier 申し送り #6 の実適用、Workflow 経路でも masking 強制ゲートウェイが機能することを CI 三層防衛で物理保証。詳細は [`threat-model.md`](../../architecture/threat-model.md) §A2 / §T1 |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | `WorkflowRepository` Protocol が `application/ports/workflow_repository.py` で定義（3 メソッド、empire-repo と同 signature） | TC-IT-WFR-001 |
| 2 | `SqliteWorkflowRepository` が Protocol を満たす（pyright strict pass） | CI typecheck |
| 3 | `find_by_id(workflow_id)` が Workflow を取得できる（不在時 None） | TC-IT-WFR-002 |
| 4 | `find_by_id` の `workflow_stages` SELECT に `ORDER BY stage_id` 発行（§Known Issues §BUG-EMR-001 規約） | TC-IT-WFR-003 |
| 5 | `find_by_id` の `workflow_transitions` SELECT に `ORDER BY transition_id` 発行（同上） | TC-IT-WFR-004 |
| 6 | `count()` が SQL レベル `COUNT(*)` 発行（§確定 D 補強、全行ロード+ Python `len()` 禁止） | TC-IT-WFR-005 |
| 7 | `save(workflow)` が新規 Workflow を挿入（workflows + workflow_stages + workflow_transitions の 3 テーブル更新、delete-then-insert 戦略） | TC-IT-WFR-006 |
| 8 | `save(workflow)` で `Stage.required_role: frozenset[Role]` が `roles_csv` カンマ区切りで永続化、`_from_row` で frozenset に復元 | TC-IT-WFR-007 |
| 9 | `save(workflow)` で `Stage.notify_channels` の Discord webhook URL が `<REDACTED:DISCORD_WEBHOOK>` でマスキング後永続化（実 SQLite 経由で TC-IT-WFR-XXX で物理確認） | TC-IT-WFR-008 |
| 10 | domain ↔ row のラウンドトリップで構造的等価が保たれる（`save(workflow) → find_by_id(workflow.id) → 復元 Workflow` が `sorted(...)` 比較で等価） | TC-IT-WFR-009 |
| 11 | Alembic 0003 revision で 3 テーブルが追加され、`alembic upgrade head` / `downgrade base` 双方緑、chain 一直線 | TC-IT-WFR-010 |
| 12 | CI 三層防衛 Layer 1（grep guard）が `workflow_stages.notify_channels_json` の `MaskedJSONEncoded` 必須を assert + その他カラムは masking なしを assert | TC-CI-WFR-001 |
| 13 | CI 三層防衛 Layer 2（arch test）が `Base.metadata.tables['workflow_stages']` の `notify_channels_json` カラム型が `MaskedJSONEncoded` であることを assert | TC-IT-WFR-011 |
| 14 | `domain` 層から `application` / `infrastructure` への import がゼロ件（既存 CI 検査で確認） | CI script |
| 15 | `pyright --strict` および `ruff check` がエラーゼロ、カバレッジ 90% 以上 | CI lint / typecheck / coverage |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| `workflows.id` / `workflows.name` | Workflow の表示名（CEO 任意の文字列、例: "V モデル開発フロー"） | 低 |
| `workflow_stages.stage_id` / `name` / `kind` / `roles_csv` / `deliverable_template` / `completion_policy_json` | Stage の構造化メタデータ | 低 |
| `workflow_stages.notify_channels_json` | NotifyChannel のリスト（Discord webhook URL token を含む） | **中**（webhook token を持つ第三者は当該 webhook 経由で任意送信可、`MaskedJSONEncoded` で永続化前マスキング必須） |
| `workflow_transitions.*` | Transition の enum / FK のみ | 低 |
