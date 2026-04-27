# 要求分析書

> feature: `room-repository`
> Issue: [#33 feat(room-repository): Room SQLite Repository (M2, 0005)](https://github.com/bakufu-dev/bakufu/issues/33)
> 関連: [`docs/features/empire-repository/`](../empire-repository/) **テンプレート真実源**（§確定 A〜F + §Known Issues §BUG-EMR-001 規約） / [`docs/features/workflow-repository/`](../workflow-repository/) **2 件目テンプレート**（masking 対象あり版で正のチェック CI 三層防衛） / [`docs/features/agent-repository/`](../agent-repository/) **3 件目テンプレート**（4 method `find_by_name` 拡張パターン）/ [`docs/features/room/`](../room/) （domain 設計済み、PR #22 マージ済み）

## 人間の要求

> Issue #33:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の後続 Repository PR（empire-repository #25 のテンプレート責務継承）。**Room Aggregate** の SQLite 永続化を実装する。Alembic revision **0005_room_aggregate** で `rooms` / `room_members` の 2 テーブルを追加。**`PromptKit.prefix_markdown` の Repository マスキング実適用**（room feature §確定 G 踏襲）。

## 背景・目的

### 現状の痛点

1. M2 永続化基盤 + empire-repo + workflow-repo + agent-repo（PR #45 マージ済み）の 4 件 chain が揃ったが、Room は domain 層（PR #22）が完了していても **`PromptKit.prefix_markdown` の永続化経路がない**。MVP 核心ユースケース「CEO directive → Room 編成 → Task 起票 → Agent 配送」のうち Room 側の Repository が塞がれている
2. **room §確定 G 申し送り**: `PromptKit.prefix_markdown` の永続化前マスキング適用は room domain 層では「Repository 経路で実適用」と申し送り済み（[room/detailed-design.md L81](../room/detailed-design.md) §Value Object: PromptKit）。本 PR で実適用に移行しないと「PromptKit に webhook URL / API key が混入したらマスキングされない」状態が継続する。Schneier 申し送り #3（`Persona.prompt_body`）と同パターンで、agent-repo §確定 R1-B の **2 件目の masking 配線** に相当
3. **empire-repository BUG-EMR-001 関連 FK closure**: empire-repo PR #29 で `empire_room_refs.room_id` が `rooms` テーブル不在ゆえ FK を張らず参照のみ宣言（[empire-repository/detailed-design.md §empire_room_refs テーブル](../empire-repository/detailed-design.md#empire_room_refs-%E3%83%86%E3%83%BC%E3%83%96%E3%83%AB) L370-373 で「`feature/room-repository` PR で migration で FK を追加する責務分離」と凍結）。本 PR の Alembic 0005 で `op.batch_alter_table` 経由 FK 追加することが**設計時点で予約された責務**
4. agent-repo §確定 R1-C で「Empire 内一意 Aggregate には Repository 第 4 method `find_by_name(empire_id, name)` を追加」テンプレを確立。Room の `name` は room §確定（[aggregates.md §Room](../../architecture/domain-model/aggregates.md) L23-31）で「Empire 内で一意」と凍結済みで、本 PR が **agent-repo §R1-C パターン適用 2 件目** として後続 directive / task / external-review-gate-repository の真似元になる
5. agent-repo §確定 R1-D で `is_default` partial unique index による「Aggregate 不変条件 + DB 制約の二重防衛」テンプレを確立。Room の `(agent_id, role)` 重複禁止は room §確定 F（[room/detailed-design.md L171-184](../room/detailed-design.md)）で Aggregate 内で凍結済みだが、**DB レベル UNIQUE(room_id, agent_id, role)** を張らないと Aggregate 復元時に valid 判定をすり抜ける経路が残る（agent-repo §R1-D と完全同パターン）

### 解決されれば変わること

- `feature/room-application` / `feature/empire-application`（後続）が Room を `RoomRepository.find_by_id` で復元 → PromptKit / AgentMembership を valid な状態で受け取れる
- application 層 `EmpireService.establish_room(empire_id, name, ...)` が `find_by_name(empire_id, name)` で重複検査 → Empire 内一意性を保証（room §確定で凍結された application 層責務の経路が成立）
- PromptKit.prefix_markdown に CEO が誤って Discord webhook URL / API key を貼り付けても DB には `<REDACTED:DISCORD_WEBHOOK>` / `<REDACTED:ANTHROPIC_KEY>` で永続化、ログ・監査経路への流出を防ぐ（**room §確定 G 実適用**、Schneier 申し送り #3 のパターン継承）
- empire-repository BUG-EMR-001 が close（`empire_room_refs.room_id → rooms.id` FK が物理張られて Empire の room 参照が dangling pointer にならない）
- agent-repo / workflow-repo に続く **4 件目のテンプレート** として、後続 3 件 Repository PR（directive / task / external-review-gate-repository）が `find_by_name` 系の追加 method パターン + 「外部参照テーブルへの FK closure」パターンを真似できる経路が確立

### ビジネス価値

- bakufu の核心思想「AI 協業」の編成空間である Room を**安全に永続化**する。CEO が PromptKit に貼り付けたシステムプロンプト前置きに secret が混入する経路を物理的に塞ぐ（Defense in Depth、persistence-foundation §シークレットマスキング規則の Repository 経路実適用 2 件目）
- BUG-EMR-001 の closure により Empire ↔ Room 参照整合性が DB レベルで物理保証され、後続 Repository PR が「forward reference テーブル → 後続 PR で FK 追加」パターンを安心して使える基盤が確立

## 議論結果

### 設計担当による採用前提

- empire-repository / workflow-repository / agent-repository の §確定 A〜F + §BUG-EMR-001 規約を **100% 継承**
- Aggregate Root: Room、2 テーブル: `rooms` / `room_members`
- Alembic revision: `0005_room_aggregate`、`down_revision="0004_agent_aggregate"`（chain 一直線）
- masking 対象カラム: **`rooms.prompt_kit_prefix_markdown` のみ**（`MaskedText`、room §確定 G 実適用）
- find_by_id 子テーブル SELECT は `ORDER BY agent_id, role`（§Known Issues §BUG-EMR-001 規約、複合 key で決定論的順序）
- save() は delete-then-insert で 2 テーブル（empire-repo §確定 B 踏襲、3 段階手順: rooms UPSERT + room_members DELETE/INSERT）
- count() は SQL `COUNT(*)`（empire-repo §確定 D 踏襲）
- **Protocol は 5 method**: `find_by_id` / `count` / `save` / `find_by_name(empire_id, name)` / **`count_by_empire(empire_id)`**（empire-repo の 3 method + agent-repo §R1-C の `find_by_name` + 本 PR で第 5 method `count_by_empire` を追加）
- `workflow_id` の DB FK は `workflows.id` への ON DELETE **RESTRICT**（Workflow は Room の参照先であって所有者ではない、CASCADE は Room を勝手に消す）
- `empire_room_refs.room_id → rooms.id` FK を `op.batch_alter_table` 経由で追加（SQLite ALTER TABLE ADD CONSTRAINT 制約への対応、empire-repo BUG-EMR-001 closure）

### 却下候補と根拠

| 候補 | 却下理由 |
|---|---|
| `rooms.prompt_kit_prefix_markdown` を `Text` で保存（masking なし）+ application 層でマスキング | application 層実装漏れで raw 永続化リスク、room §確定 G 違反。`MaskedText` 強制（agent-repo §R1-B と同論理） |
| `rooms.name` に DB レベル UNIQUE 制約 (`UNIQUE(empire_id, name)`) を張る | agent-repo §確定 R1-B と同方針: application 層 `EmpireService.establish_room` が MSG-RR-NNN を出す前に `IntegrityError` が raise され、ユーザー向けメッセージが汚れる。`find_by_name` で application 層検査の経路を残し、DB は **non-unique INDEX(empire_id, name)** で SELECT 性能のみ確保 |
| `room_members` の DB UNIQUE 制約を張らず application 層検査のみ | agent-repo §確定 R1-D と同パターン: Aggregate 内不変条件 + application 層検査のみだと、Repository が壊れた行を返した場合の最終防衛線が抜ける。**`UNIQUE(room_id, agent_id, role)`** で二重防衛 |
| `workflow_id` の FK を ON DELETE CASCADE | Workflow は Room の参照先であって**所有者ではない**。CASCADE は「Workflow 削除 → 当該 Workflow を採用している全 Room が DB から消える」副作用、データ消失リスク大。RESTRICT で Workflow 削除を物理的に拒否し、application 層が「先に全 Room を archive / 別 Workflow に移行」する経路を強制 |
| `workflow_id` の FK を張らない（参照のみ宣言、empire_room_refs パターン継承） | 0005 時点で `workflows` テーブルは 0003 で先行存在済み（workflow-repository PR #41 マージ済み）。FK を張れる前提条件が揃っているのに張らないのは BUG-EMR-001 と同じ dangling pointer リスクを温存する。**FK は張れる時に張る**が原則 |
| `empire_room_refs.room_id` の FK 追加を別 PR に先送り | BUG-EMR-001 の closure は本 PR の責務として empire-repo §確定で**凍結済み**（[empire-repository/detailed-design.md §empire_room_refs テーブル §Room テーブルへの FK を張らない理由](../empire-repository/detailed-design.md#room-%E3%83%86%E3%83%BC%E3%83%96%E3%83%AB%E3%81%B8%E3%81%AE-fk-%E3%82%92%E5%BC%B5%E3%82%89%E3%81%AA%E3%81%84%E7%90%86%E7%94%B1) L370-373）。先送りは規約違反 |
| `find_by_name` を Protocol に追加せず application 層が `find_by_id` を全件 SELECT して filter | agent-repo §R1-C 却下と同論理: N+1 / 全件ロードで MVP の数十 Room は耐えられるが、後続 PR が真似すると数千 Room でメモリ枯渇 |
| `count_by_empire` を Protocol に追加せず `count()` で全 Empire 合計のみ提供 | Empire admin CLI / UI で「Empire 内 Room 数」を表示する経路が後続 PR で必要（room domain 層 §設計判断補足「なぜ description を 500 文字までに制限するか」で UI Room カード一覧が議論済み）。SQL レベル `COUNT(*) WHERE empire_id=?` で済むため、第 5 method として先取り凍結（empire-repo §確定 D の SQL `COUNT(*)` テンプレを Empire スコープに拡張） |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: empire / workflow / agent テンプレート 100% 継承（再凍結）

| 継承項目 | 本 PR への適用 |
|---|---|
| empire §確定 A | `application/ports/room_repository.py` 新規、Protocol、`@runtime_checkable` なし |
| empire §確定 B | save() で rooms UPSERT + room_members DELETE/INSERT、Repository 内 commit/rollback なし |
| empire §確定 C | `_to_row` / `_from_row` を private method に閉じる |
| empire §確定 D | `count()` は SQL `COUNT(*)` 限定 |
| empire §確定 E | CI 三層防衛 Layer 1 + Layer 2 + Layer 3 全部に Room 2 テーブル明示登録 |
| empire §BUG-EMR-001 規約 | `find_by_id` 子テーブル SELECT は `ORDER BY agent_id, role` 必須（複合 key の左から右へ昇順、決定論的順序の物理保証） |
| workflow §確定 E（正のチェック）| `rooms.prompt_kit_prefix_markdown` の `MaskedText` 必須を grep + arch test で物理保証 |
| agent §R1-C テンプレ | `find_by_name(empire_id, name)` 第 4 method 追加、Empire スコープ検索 |
| agent §R1-D テンプレ | DB レベル制約による二重防衛（本 PR では `UNIQUE(room_id, agent_id, role)`、agent の `partial unique` とは別形式だが**同じ Defense-in-Depth 思想**） |

#### 確定 R1-B: `workflow_id` FK 方向と ON DELETE 挙動

`rooms.workflow_id` を `workflows.id` への FK 制約付きで宣言:

| 項目 | 値 | 根拠 |
|---|---|---|
| FK 参照先 | `workflows.id` | workflow-repository PR #41 マージ済み、0003_workflow_aggregate で `workflows` テーブル先行追加済み（chain 順序が物理保証） |
| ON DELETE | **`RESTRICT`** | Workflow は Room の参照先であって所有者ではない（[aggregates.md §Workflow](../../architecture/domain-model/aggregates.md) L46-72 で凍結）。`CASCADE` は Workflow 削除で Room が勝手に消える副作用、データ消失リスク大。`RESTRICT` で Workflow 削除を物理的に拒否し、application 層が「先に全 Room を archive 又は別 Workflow に移行」する経路を強制（Fail Fast） |
| ON UPDATE | 該当なし | UUID PK は不変、UPDATE 経路を持たない |
| FK 違反時 | `sqlalchemy.IntegrityError`（FK constraint failed） | application 層で catch、HTTP 409 Conflict にマッピング（別 feature） |

##### CASCADE / RESTRICT / SET NULL 比較

| 候補 | 採否 | 理由 |
|---|---|---|
| **`RESTRICT`** | ✓ **採用** | Workflow 削除で Room が勝手に消えない、application 層が明示的に Room を整理してから Workflow を消す経路を強制 |
| `CASCADE` | ✗ | Workflow 削除 → 全 Room 消失、Empire が persona 設計に費やしたエンジニアリング工数が消える、不可逆データ損失 |
| `SET NULL` | ✗ | `workflow_id` は NOT NULL（Room は必ず Workflow を採用、room §確定で凍結）。`SET NULL` は型違反 |
| FK を張らない | ✗ | 0005 時点で workflows テーブルは存在、empire_room_refs と違って forward reference 問題なし。**FK は張れる時に張る**が原則（参照整合性の物理保証） |

[SQLite — Foreign Key Actions](https://www.sqlite.org/foreignkeys.html#fk_actions) で `RESTRICT` の挙動を確認: 親行を削除しようとした時点で raise（DEFERRABLE 経路でない限り Tx 末尾チェックではない、即時 raise）。MVP では DEFERRABLE 不要。

#### 確定 R1-C: `empire_room_refs.room_id → rooms.id` FK closure（BUG-EMR-001 close）

empire-repository §確定で「`feature/room-repository` PR で migration で FK を追加する責務分離」と凍結された FK closure を本 PR の Alembic 0005 で実施する。

##### Alembic 0005 での FK 追加方法

SQLite は ALTER TABLE ADD CONSTRAINT を直接サポートしない（[SQLite — ALTER TABLE](https://www.sqlite.org/lang_altertable.html) 参照、3.35+ でも CONSTRAINT 系は未サポート）。Alembic は SQLite 向けに **`op.batch_alter_table()`** を提供しており、内部で table 再作成（`CREATE TABLE new_t → INSERT SELECT → DROP old → RENAME`）して FK を追加する。

| 段階 | 操作 |
|---|---|
| 1 | `op.create_table('rooms', ...)` で rooms テーブル作成（`workflow_id` の FK 込み） |
| 2 | `op.create_table('room_members', ...)` で room_members テーブル作成（`room_id` の FK 込み） |
| 3 | **`op.batch_alter_table('empire_room_refs') as batch_op:` で `batch_op.create_foreign_key('fk_empire_room_refs_room_id', 'rooms', ['room_id'], ['id'], ondelete='CASCADE')`** を実行（empire_room_refs.room_id → rooms.id） |
| 4 | downgrade では batch_alter_table で drop_constraint、その後 drop_table 逆順 |

##### `empire_room_refs` 側の FK ON DELETE 挙動

| 項目 | 値 | 根拠 |
|---|---|---|
| ON DELETE | **`CASCADE`** | empire_room_refs は **Empire Aggregate の内部状態**（Empire の `rooms: list[RoomRef]` の永続化）。Room 削除で対応する RoomRef も消えるべき（Empire の参照が dangling になる方が不整合）。MVP では Room は archived 化のみで物理削除しないため CASCADE 経路は実質的に発火しないが、将来 Room を物理削除する経路を実装した場合の参照整合性を保証 |

##### empire-repo BUG-EMR-001 の close 手順

本 PR の同一コミットで:
1. `docs/features/empire-repository/detailed-design.md` §Known Issues §BUG-EMR-001 の status を「**RESOLVED in `feature/33-room-repository` Alembic 0005**」に更新
2. `docs/features/empire-repository/detailed-design.md` §`empire_room_refs` テーブル §Room テーブルへの FK を張らない理由 を「FK closure 完了済み（0005_room_aggregate）」に更新
3. `docs/architecture/domain-model/storage.md` §逆引き表 を更新（後述 R1-G）

#### 確定 R1-D: `(room_id, agent_id, role)` UNIQUE による二重防衛

room §確定 F で「`(agent_id, role)` ペアの重複禁止、同一 `agent_id` の異なる Role は許容」を Aggregate 内不変条件として凍結済み。本 PR で **DB レベル UNIQUE 制約** を追加して二重防衛:

```sql
UNIQUE(room_id, agent_id, role)
```

| 防衛層 | 検査内容 | 違反時 |
|---|---|---|
| Aggregate 内（既存）| `_validate_member_unique` で `(agent_id, role)` ペアを集合化、`len(set) < len(members)` なら raise | `RoomInvariantViolation(kind='member_duplicate')`（MSG-RM-003）|
| **DB UNIQUE 制約（本 PR 新規）** | INSERT/UPDATE で `(room_id, agent_id, role)` の集合に違反する行が来たら IntegrityError | `sqlalchemy.IntegrityError`、application 層が catch して 500 にマッピング（データ破損として扱う） |

##### partial unique でなく通常 UNIQUE を選ぶ根拠

agent-repo §R1-D の `is_default` partial unique（`UNIQUE WHERE is_default = 1`）と異なり、本 PR の `(room_id, agent_id, role)` は**全行に対する UNIQUE**で正しい:

| 採用 | 不採用 | 理由 |
|---|---|---|
| **通常 UNIQUE(room_id, agent_id, role)** | partial unique（条件付き） | `(agent_id, role)` の重複は room §確定 F で**全 members に対する不変条件**（特定条件下のみではない）、よって全行に対する通常 UNIQUE が正解 |
| | アプリ層検査のみ | Aggregate 内検査が壊れた場合の最終防衛線が消える、Defense in Depth 違反（agent §R1-D と同論理） |

`role` は VARCHAR(32) の Role enum 文字列のため、3 カラム複合 UNIQUE のサイズはコンパクト。SQLite の自動 INDEX 生成で SELECT 性能も担保される。

#### 確定 R1-E: `MaskedText` for `prompt_kit_prefix_markdown`（room §確定 G 実適用）

`rooms.prompt_kit_prefix_markdown` カラムを **`MaskedText`** で宣言、`process_bind_param` で `MaskingGateway.mask()` 経由マスキング（agent §R1-B の `Persona.prompt_body` と完全同パターン）:

| 経路 | 動作 |
|---|---|
| `_to_row(room)` | `rooms_row['prompt_kit_prefix_markdown'] = room.prompt_kit.prefix_markdown`（raw 文字列、room §確定 B より NFC 正規化のみ適用済み、strip 未適用） |
| `MaskedText.process_bind_param` | INSERT/UPDATE 直前に `MaskingGateway.mask(prefix_markdown)` を呼ぶ → `<REDACTED:*>` 化された文字列を DB に保存 |
| `_from_row(room_row, member_rows)` | DB から masked 文字列を取得、`PromptKit(prefix_markdown=masked_string)` で復元（**masking 不可逆性**、agent §確定 H と同申し送り） |

##### マスキング対象 secret パターン（storage.md §マスキング対象パターンより）

PromptKit に CEO が貼り付け得る secret 例:

| 想定混入 | 検出パターン | 置換結果 |
|---|---|---|
| Discord webhook URL | `https://discord.com/api/webhooks/...` | `<REDACTED:DISCORD_WEBHOOK>` |
| Anthropic API key | `sk-ant-...` | `<REDACTED:ANTHROPIC_KEY>` |
| GitHub PAT | `ghp_...` / `github_pat_...` | `<REDACTED:GITHUB_PAT>` |
| 環境変数値 | 起動時に登録された secret 環境変数の値完全一致 | `<REDACTED:ENV:KEY_NAME>` |

room §確定 H の `RoomInvariantViolation` auto-mask（domain 層、例外経路）と本 PR の `MaskedText`（infrastructure 層、永続化経路）が**多層防御**で組み合わさる。

##### 復元不可逆性の申し送り

`find_by_id` で復元される Room の `PromptKit.prefix_markdown` には masked 文字列が入る。`Room` を LLM Adapter にこれを送ると `<REDACTED:*>` がそのまま prompt に流れ、LLM 出力品質が下がる経路が生じる。MVP では「CEO が PromptKit を再編集する運用」で吸収、後続 `feature/llm-adapter` で「prefix_markdown に `<REDACTED:*>` を含む Room はログ警告 + 配送停止」契約を凍結する申し送り（agent-repo §確定 H 申し送り #1 と同パターン）。

#### 確定 R1-F: `find_by_name(empire_id, name)` + `count_by_empire(empire_id)` 第 4・5 method 追加 + INDEX 設計

empire-repo の Protocol は 3 method（find_by_id / count / save）、agent-repo で第 4 method `find_by_name` を追加。本 PR では agent-repo パターンを継承しつつ **第 5 method `count_by_empire` を追加** する:

| メソッド | 引数 | 戻り値 | 用途 |
|---|---|---|---|
| `find_by_name(empire_id: EmpireId, name: str) -> Room \| None` | EmpireId + name 文字列 | 該当 Room or None | application 層 `EmpireService.establish_room()` の Empire 内一意検査（room §確定 application 層責務） |
| `count_by_empire(empire_id: EmpireId) -> int` | EmpireId | 該当 Empire 内の Room 数 | Empire admin CLI `list-rooms` / UI Empire ダッシュボード「Room 数」表示 |

##### `find_by_name` の Empire スコープ必須性（agent §R1-C 同論理）

Room の `name` 一意性は Empire 内（`(empire_id, name)` の複合一意）のため、`find_by_name(name)` だけでは不十分。`empire_id` も引数に取って `WHERE empire_id = :empire_id AND name = :name` で SELECT する。

##### INDEX 設計（**non-unique INDEX**、agent-repo §R1-B の哲学継承）

| 採用 | 不採用 | 理由 |
|---|---|---|
| **`INDEX(empire_id, name)` 非 UNIQUE** | UNIQUE INDEX(empire_id, name) | application 層 `EmpireService.establish_room()` が MSG-RR-NNN（`RoomNameAlreadyExistsError`）を出す前に `IntegrityError` が raise されるとユーザー向けメッセージの voice が崩れる（agent §R1-B 同論理）。SELECT 性能のため **非 UNIQUE INDEX** で済ませる |
| | INDEX なし | `find_by_name` の `WHERE empire_id=? AND name=?` がフルテーブルスキャンになり、Empire 内 Room 数が増えると O(N) で遅くなる。MVP の数十 Room なら問題ないが、後続 PR が `count_by_empire` を実装する際にも `(empire_id)` での WHERE に効くよう **左端 prefix** で empire_id を含む複合 INDEX が最適 |
| | 別々の INDEX(empire_id) と INDEX(name) | 複合 INDEX `(empire_id, name)` が `(empire_id)` プリフィックスで `count_by_empire` にも効く（[SQLite — Query Planner](https://www.sqlite.org/queryplanner.html) 左端プリフィックスの原則）、別々 INDEX より効率的 |

| INDEX | 効く SELECT | 効かない SELECT |
|---|---|---|
| `INDEX(empire_id, name)` 非 UNIQUE | `WHERE empire_id=? AND name=?`（find_by_name）/ `WHERE empire_id=?`（count_by_empire） | `WHERE name=?` のみ（本 PR では発行しない） |

##### 後続 Repository PR への申し送り（テンプレート責務）

本 §確定 R1-F は agent-repo §R1-C を発展させ、「Aggregate 不変条件のうち DB SELECT を要する集合知識（Empire 内一意 / Room 内一意 等）+ 集合カウント（count_by_*）を Repository 第 4・5 method として追加するテンプレート」を確立する。後続 PR が同パターンを採用する場合:

| 後続 PR 候補 | 想定される追加 method |
|---|---|
| `feature/directive-repository`（Issue #34）| `find_by_target_room_id(room_id, after: datetime)` 等の Room 別検索（business requirement 次第） |
| `feature/task-repository`（Issue #35）| `find_blocked() -> list[Task]`（admin CLI `list-blocked`）/ `count_by_room(room_id)` |
| `feature/external-review-gate-repository`（Issue #36）| `find_pending_by_reviewer(reviewer_id)` / `find_by_task_id(task_id)` / `count_by_decision(decision)` |

#### 確定 R1-G: storage.md 逆引き表更新

`docs/architecture/domain-model/storage.md` §逆引き表に Room 関連 2 行追加:

| 行 | 内容 |
|---|---|
| `rooms.prompt_kit_prefix_markdown` | `MaskedText`、room §確定 G **実適用**、persistence-foundation #23 で hook 構造提供 → 本 PR で配線完了（既存 `PromptKit.prefix_markdown` 行を実適用済み表記に更新）|
| `rooms` 残カラム + `room_members` 全カラム | masking 対象なし（`UUIDStr` / `String` / `Boolean` / `DateTime` のみ。CI Layer 2 で `MaskedText` でないことを arch test で保証）|

storage.md §逆引き表の既存 `PromptKit.prefix_markdown` 行（persistence-foundation #23 時点で「`feature/room-repository`（後続）」と表記）を **本 PR で配線済みに更新**する責務（agent-repo §R1-E と同パターン）。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 個人開発者 CEO（堀川さん想定） | Room を Web UI / CLI で 編成 | GitHub / Docker / CLI 日常使用 | UI で「V モデル開発室」Room を編成 → DB 永続化 → Empire ダッシュボードで Room 一覧表示 | Room 名 / description / PromptKit / メンバー / Workflow を一度設定すれば永続化される |
| 後続 Issue 担当（バックエンド開発者） | `feature/room-application` / `feature/dispatcher` 実装者 | DDD 経験あり、SQLAlchemy 2.x async / Pydantic v2 経験あり | 本 PR の設計書を真実源として読み、Room 編成経路を実装 | empire-repo / workflow-repo / agent-repo / 本 PR テンプレートを直接参照して同パターンで Repository を増やせる |
| セキュリティレビュワー（Schneier 想定） | room §確定 G を本 PR で完了確認 | secret マスキング Defense in Depth | `rooms.prompt_kit_prefix_markdown` カラムが `MaskedText` で宣言、SQL 直読みで raw webhook URL / API key が出ないことを物理確認、`empire_room_refs.room_id → rooms.id` FK が物理張られていることを `PRAGMA foreign_key_list` で確認 | 永続化前マスキングの単一ゲートウェイが Room 経路でも機能、参照整合性が DB レベルで保証 |

##### ペルソナ別ジャーニー（個人開発者 CEO）

1. **Room 編成**: UI で name / description / workflow_id / prompt_kit / members を入力 → `EmpireService.establish_room(empire_id, name, ...)` を呼ぶ
2. **Empire 内一意検査**: application 層 `EmpireService.establish_room()` が `RoomRepository.find_by_name(empire_id, name)` を呼び、None なら新規作成、既存なら `RoomNameAlreadyExistsError` で 409 Conflict
3. **Workflow 存在検証**: application 層が `WorkflowRepository.find_by_id(workflow_id)` で確認（不在なら `WorkflowNotFoundError`）。本 PR では DB FK が RESTRICT で物理保証する第 2 防衛線も提供
4. **永続化**: `RoomRepository.save(room)` → SQLite に書き込み（`prompt_kit_prefix_markdown` は `MaskedText` 経由で masking 適用、CEO が PromptKit に webhook URL を含めても `<REDACTED:DISCORD_WEBHOOK>` 化）
5. **Dispatcher 起動時**: `RoomRepository.find_by_id(room_id)` で復元 → `PromptKit.prefix_markdown` には masked 文字列、LLM Adapter 配送時に警告経路（後続 feature 責務、申し送り）
6. **Empire ダッシュボード**: `RoomRepository.count_by_empire(empire_id)` で Empire 内 Room 数を表示

##### ジャーニーから逆算した受入要件

- ジャーニー 2: `find_by_name(empire_id, name) -> Room | None` が Empire スコープで動作（§確定 R1-F）
- ジャーニー 3: `workflows.id` への FK RESTRICT が DB レベルで Workflow 削除を拒否（§確定 R1-B）
- ジャーニー 4: `prompt_kit_prefix_markdown` に raw webhook URL を渡しても DB には `<REDACTED:DISCORD_WEBHOOK>` で永続化（§確定 R1-E）
- ジャーニー 5: `find_by_id` で復元される Room は valid（Pydantic 構築通過）、ただし `PromptKit.prefix_markdown` は masked 文字列（不可逆性、後続 LLM Adapter 警告経路の申し送り）
- ジャーニー 6: `count_by_empire(empire_id)` が SQL `COUNT(*)` で発行（全行ロード+ Python `len()` 禁止、§確定 R1-F）

## 前提条件・制約

| 区分 | 内容 |
|-----|------|
| 既存技術スタック | Python 3.12+ / SQLAlchemy 2.x async / Alembic / aiosqlite / Pydantic v2 / pyright strict / pytest |
| 既存 CI | lint / typecheck / test-backend / audit |
| 既存ブランチ戦略 | GitFlow（CONTRIBUTING.md §ブランチ戦略） |
| コミット規約 | Conventional Commits |
| ライセンス | MIT |
| ネットワーク | 該当なし — infrastructure 層、外部通信なし |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |

## 機能一覧

| 機能ID | 機能名 | 概要 | 優先度 |
|--------|-------|------|--------|
| REQ-RR-001 | RoomRepository Protocol 定義 | `application/ports/room_repository.py` で **5 method**（find_by_id / count / save / find_by_name / count_by_empire）を `async def` で宣言 | 必須 |
| REQ-RR-002 | SqliteRoomRepository 実装 | `infrastructure/persistence/sqlite/repositories/room_repository.py` で SQLite 実装、§確定 R1-A〜F を満たす | 必須 |
| REQ-RR-003 | Alembic 0005 revision | `0005_room_aggregate.py` で 2 テーブル + UNIQUE(room_id, agent_id, role) + INDEX(empire_id, name) + workflow_id FK RESTRICT 追加、`down_revision="0004_agent_aggregate"`、**`empire_room_refs.room_id → rooms.id` FK closure を `op.batch_alter_table` で追加**（BUG-EMR-001 close） | 必須 |
| REQ-RR-004 | CI 三層防衛の Room 拡張 | Layer 1 grep guard（rooms.prompt_kit_prefix_markdown 行に `MaskedText` 必須、正のチェック）+ Layer 2 arch test + Layer 3 storage.md 更新 | 必須 |
| REQ-RR-005 | storage.md 逆引き表更新 | Room 関連 2 行追加（§確定 R1-G） | 必須 |
| REQ-RR-006 | empire-repo BUG-EMR-001 close 同期 | `docs/features/empire-repository/detailed-design.md` §Known Issues §BUG-EMR-001 の status を「**RESOLVED in `feature/33-room-repository` Alembic 0005**」に更新、§`empire_room_refs` テーブル §Room テーブルへの FK を張らない理由 を「FK closure 完了済み（0005_room_aggregate）」に更新 | 必須 |

## Sub-issue 分割計画

本 Issue は単一 Aggregate Repository に閉じる粒度のため Sub-issue 分割は不要。1 PR で 5 設計書 + 実装 + ユニットテスト + BUG-EMR-001 close 同期を完結させる（empire-repo / workflow-repo / agent-repo と同方針）。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 単一 PR | REQ-RR-001〜006 | Room SQLite Repository + ユニットテスト + storage.md 更新 + BUG-EMR-001 close | M1 room（PR #22）+ M2 永続化基盤（PR #23）+ empire-repo（PR #29/#30）+ workflow-repo（PR #41）+ agent-repo（PR #45）マージ済み |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | `count()` / `count_by_empire()` は O(1) SQL `COUNT(*)`。`find_by_id` は子テーブル含めて O(1) Tx で 2 SELECT。`find_by_name` は `INDEX(empire_id, name)` 経由で O(log N) |
| 可用性 | 該当なし — infrastructure 層 |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 95% 以上（empire-repo / workflow-repo / agent-repo 実績水準）/ 全ファイル 500 行未満 |
| 可搬性 | SQLite 単一前提、Postgres 移行時は migration-plan.md §TODO-MIG-NNN として追記。`op.batch_alter_table` の SQLite 特化挙動は Postgres ではネイティブ ALTER TABLE で代替可能（Alembic が両 DB で同 syntax を提供） |
| セキュリティ | `rooms.prompt_kit_prefix_markdown` の Discord webhook URL / API key を `MaskedText` で永続化前マスキング（room §確定 G 実適用）。CI 三層防衛で物理保証。`workflow_id` FK RESTRICT で Workflow 削除を物理拒否、参照整合性保証。詳細は [`threat-model.md`](../../architecture/threat-model.md) §A02 / §A04 / §A08 / §A09 |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | `RoomRepository` Protocol が **5 method**（find_by_id / count / save / find_by_name / count_by_empire）を `async def` で定義、`@runtime_checkable` なし | TC-UT-RR-001 |
| 2 | `SqliteRoomRepository` が Protocol を型レベルで満たす（pyright strict） | CI typecheck |
| 3 | `save(room)` が rooms UPSERT + room_members DELETE/INSERT を同一 Tx 内で実行 | TC-UT-RR-002 |
| 4 | `find_by_id` の子テーブル SELECT が `ORDER BY agent_id, role` を発行（§BUG-EMR-001 規約） | TC-UT-RR-003 |
| 5 | `count()` が SQL `COUNT(*)` を発行（全行ロード+ Python `len()` 禁止） | TC-UT-RR-004 |
| 6 | `find_by_name(empire_id, name)` が `WHERE empire_id=:empire_id AND name=:name` で SELECT、不在なら None | TC-UT-RR-005 |
| 7 | `count_by_empire(empire_id)` が SQL `COUNT(*) WHERE empire_id=:empire_id` を発行 | TC-UT-RR-006 |
| 8 | `rooms.prompt_kit_prefix_markdown` が `MaskedText` で宣言、raw webhook URL を保存しても DB には `<REDACTED:DISCORD_WEBHOOK>` で永続化（room §確定 G 実適用） | TC-IT-RR-007-masking |
| 9 | `room_members` の `UNIQUE(room_id, agent_id, role)` が DB レベルで一意性を保証（同 (agent_id, role) ペアが 2 件あったら IntegrityError） | TC-IT-RR-008 |
| 10 | `rooms.workflow_id` の FK が `workflows.id` への ON DELETE RESTRICT で宣言、Workflow 削除時に Room が残っていれば IntegrityError | TC-IT-RR-009 |
| 11 | `rooms.empire_id` の FK が `empires.id` への ON DELETE CASCADE で宣言、Empire 削除で Room も削除される | TC-IT-RR-010 |
| 12 | `empire_room_refs.room_id → rooms.id` の FK が Alembic 0005 で物理追加される（PRAGMA foreign_key_list で確認可能、BUG-EMR-001 close） | TC-IT-RR-011 |
| 13 | `INDEX(empire_id, name)` 非 UNIQUE が rooms に存在（PRAGMA index_list で確認可能） | TC-IT-RR-012 |
| 14 | Alembic 0005 revision で 2 テーブル + UNIQUE + INDEX + workflow_id FK + empire_room_refs FK closure が SQLite に作成される | TC-IT-RR-013 |
| 15 | CI 三層防衛 Layer 1（grep guard で rooms.prompt_kit_prefix_markdown の `MaskedText` 必須）+ Layer 2（arch test）+ Layer 3（storage.md 更新）が pass | CI ジョブ |
| 16 | empire-repository §Known Issues §BUG-EMR-001 の status が「RESOLVED in `feature/33-room-repository` Alembic 0005」に更新済み | コードレビュー |
| 17 | `pyright --strict` および `ruff check` がエラーゼロ | CI lint / typecheck |
| 18 | カバレッジが Room Repository 配下で 95% 以上 | pytest --cov |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| `rooms.prompt_kit_prefix_markdown` | PromptKit の自然言語、システムプロンプトに展開される | **高**（Discord webhook URL / API key / GitHub PAT が混入し得る、room §確定 G 実適用、`MaskedText` 配線必須） |
| `rooms.id` / `empire_id` / `workflow_id` / `name` / `description` / `archived` | 識別子・表示名・bool | 低（name / description は CEO 自由記述だが secret 6 種非該当の前提、room §確定 B の NFC 正規化のみ） |
| `room_members.*`（room_id / agent_id / role / joined_at） | メンバー関係 | 低（UUID + Role enum + UTC datetime） |
