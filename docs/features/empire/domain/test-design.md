# テスト設計書

<!-- feature: empire -->
<!-- 配置先: docs/features/empire/test-design.md -->
<!-- 対象範囲: REQ-EM-001〜005 / MSG-EM-001〜005 / 脅威 T1, T2 / 受入基準 1〜9（観察可能な事象） / 開発者品質 Q-1, Q-2（CI 担保） / 詳細設計 確定 A〜D -->

本 feature は domain 層の単一 Aggregate（Empire）と参照 VO（RoomRef / AgentRef）と例外（EmpireInvariantViolation）に閉じる。HTTP API / CLI / UI のいずれの公開エントリポイントも持たないため、E2E は本 feature 範囲外（後続 feature/http-api / feature/admin-cli で起票）。本 feature のテストは **ユニット主体 + 結合は Aggregate 内 module 連携の往復シナリオ**で構成する。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-EM-001 | `Empire.__init__` / `model_validator(mode='after')` | TC-UT-EM-001, TC-UT-EM-002 | ユニット | 正常系 / 境界値 | 1, 2 |
| REQ-EM-001（NFC） | `Empire.name` の `unicodedata.normalize('NFC', ...)` + `strip()` | TC-UT-EM-003 | ユニット | 正常系 | 1（確定 B） |
| REQ-EM-002 | `Empire.hire_agent` | TC-UT-EM-004, TC-UT-EM-005 | ユニット | 正常系 | 3 |
| REQ-EM-002（重複） | `Empire.hire_agent` + `model_validator` | TC-UT-EM-006 | ユニット | 異常系 | 4 |
| REQ-EM-002（容量） | `Empire.hire_agent` + `model_validator` | TC-UT-EM-007 | ユニット | 境界値 | 9 |
| REQ-EM-003 | `Empire.establish_room` | TC-UT-EM-008 | ユニット | 正常系 | 5 |
| REQ-EM-003（重複） | `Empire.establish_room` + `model_validator` | TC-UT-EM-009 | ユニット | 異常系 | 6 |
| REQ-EM-003（容量） | `Empire.establish_room` + `model_validator` | TC-UT-EM-010 | ユニット | 境界値 | 9 |
| REQ-EM-004 | `Empire.archive_room` | TC-UT-EM-011 | ユニット | 正常系 | 7 |
| REQ-EM-004（未登録） | `Empire.archive_room` | TC-UT-EM-012 | ユニット | 異常系 | 8 |
| REQ-EM-004（線形探索 / 物理削除しない） | `Empire.archive_room` | TC-UT-EM-013 | ユニット | 正常系 | 7（確定 D） |
| REQ-EM-005（pre-validate） | `Empire.hire_agent` 失敗時の元 Empire 不変 | TC-UT-EM-014 | ユニット | 異常系 | 4（確定 A） |
| REQ-EM-005（pre-validate） | `Empire.establish_room` 失敗時の元 Empire 不変 | TC-UT-EM-015 | ユニット | 異常系 | 6（確定 A） |
| REQ-EM-005（pre-validate） | `Empire.archive_room` 失敗時の元 Empire 不変 | TC-UT-EM-016 | ユニット | 異常系 | 8（確定 A） |
| REQ-EM-005（frozen） | `Empire` / `RoomRef` / `AgentRef` の属性代入拒否 | TC-UT-EM-017 | ユニット | 異常系 | Q-3 |
| REQ-EM-005（extra='forbid'） | `Empire.model_validate` 未知フィールド拒否 | TC-UT-EM-018 | ユニット | 異常系 | Q-3 |
| MSG-EM-001 | 例外 message（name 範囲外） | TC-UT-EM-019 | ユニット | 異常系 | 2 |
| MSG-EM-002 | 例外 message（agent 重複） | TC-UT-EM-020 | ユニット | 異常系 | 4 |
| MSG-EM-003 | 例外 message（room 重複） | TC-UT-EM-021 | ユニット | 異常系 | 6 |
| MSG-EM-004 | 例外 message（room 未登録） | TC-UT-EM-022 | ユニット | 異常系 | 8 |
| MSG-EM-005 | 例外 message（汎用 invariant） | TC-UT-EM-023 | ユニット | 異常系 | Q-3 |
| T1 | 不正値での Aggregate 構築拒否 | TC-UT-EM-002, TC-UT-EM-006, TC-UT-EM-009, TC-UT-EM-018 | ユニット | 異常系 | Q-3 |
| T2 | 重複参照による DoS / メモリ肥大の即時拒否 | TC-UT-EM-006, TC-UT-EM-007, TC-UT-EM-009, TC-UT-EM-010 | ユニット | 異常系 | Q-3 |
| Q-1（lint/typecheck） | `pyright --strict` / `ruff check` | （CI ジョブ） | — | — | Q-1 |
| Q-2（カバレッジ） | `pytest --cov=bakufu.domain.empire` | （CI ジョブ） | — | — | Q-2 |
| 結合シナリオ 1 | `Empire` + `RoomRef` + `AgentRef` + `EmpireInvariantViolation` 往復 | TC-IT-EM-001 | 結合 | 正常系 | 1, 3, 5, 7 |
| 結合シナリオ 2 | hire 失敗 → establish 成功 → archive 成功（独立性） | TC-IT-EM-002 | 結合 | 異常系/正常系 | 4, 5, 7 |

**マトリクス充足の証拠**:
- REQ-EM-001〜005 すべてに最低 1 件のテストケース
- MSG-EM-001〜005 すべてに静的文字列照合
- 受入基準 1〜9 すべてにユニットケースまたは結合ケース（開発者品質 Q-1 / Q-2 は CI ジョブで担保）
- T1 / T2 すべてに有効性確認ケース
- 確定 A〜D（pre-validate / NFC / 容量 100 / 線形探索）すべてに証拠ケース
- 孤児要件（マトリクス外要件）なし

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **該当なし** | Empire は domain 層で外部 I/O を持たない（HTTP / DB / ファイル / 時刻 / LLM / Discord いずれも未依存）。`unicodedata.normalize('NFC', ...)` は CPython 標準ライブラリ仕様で固定、外部観測不要 | — | — | **不要（外部 I/O ゼロ）** |

**根拠**:
- [`basic-design.md`](basic-design.md) §外部連携 で「該当なし — domain 層のみのため外部システムへの通信は発生しない」と凍結
- [`feature-spec.md`](../feature-spec.md) §前提条件・制約 で「ネットワーク: 該当なし — Empire は domain 層のため外部通信なし」と凍結
- 本 feature では assumed mock 問題は構造上発生しない（モック対象なし）

**factory（合成データ）の扱い**:
unit テストの入力バリエーション網羅のため、`tests/factories/empire.py` に以下の factory を起票する。これらは外部観測の代替ではなく、純粋に Pydantic VO のパラメータ化生成器（faker + factory_boy）として機能する。

| factory | 出力 | synthetic 判定 |
|--------|-----|------------------|
| `EmpireFactory` | `Empire`（valid デフォルト + override 可） | `is_synthetic(instance) is True` |
| `RoomRefFactory` | `RoomRef`（valid デフォルト + override 可） | 同上 |
| `AgentRefFactory` | `AgentRef`（valid デフォルト + role=DEVELOPER） | 同上 |
| `RoleFactory` | `Role` enum 全列挙からランダム | （enum 値、判定対象外）|

**synthetic 識別の実装方針: WeakValueDictionary レジストリ（確定）**

Empire / RoomRef / AgentRef は `frozen=True` + `extra='forbid'` のため、インスタンス側に `_meta.synthetic` 等の属性を**追加することは物理的に不可能**。代わりに factory モジュール側のレジストリで識別する。

| 設計要素 | 確定内容 |
|---|---|
| レジストリ実体 | `tests/factories/empire.py` の **モジュールスコープ**に `_synthetic_registry: weakref.WeakValueDictionary[int, BaseModel]` を配置 |
| 登録キー | `id(instance)`（Python の組み込み id、int で hashable） |
| 登録値 | factory が生成した Pydantic インスタンス本体（weak reference として保持） |
| 登録タイミング | factory の `_create()` メソッド末尾で `_synthetic_registry[id(instance)] = instance` |
| 判定関数 | 同モジュールに `is_synthetic(instance: BaseModel) -> bool` を公開、`id(instance) in _synthetic_registry` で判定 |
| GC 時の挙動 | テスト終了でインスタンスが GC されると weak ref が消え、レジストリのエントリも自動消滅（メモリリークなし）|
| id 再利用衝突 | WeakValueDictionary は value GC 時にエントリを削除するため、同じ id が別インスタンスに再利用される瞬間にはレジストリに当該 id は存在しない（実害ゼロ）|

**WeakValueDictionary を選んだ理由**:

| 候補 | 採否 | 理由 |
|---|---|---|
| `WeakKeyDictionary[BaseModel, dict]` | 不採用 | Empire は `list[RoomRef]` / `list[AgentRef]` を持つため、`frozen=True` でも `__hash__` が定義できない。WeakKeyDictionary は key の hashable を要求 |
| `WeakSet[BaseModel]` | 不採用 | 同上の理由（set ベースで要素 hashable 必須）|
| `dict[int, BaseModel]`（強参照）| 不採用 | テスト終了後もレジストリが参照を保持し続け、GC を阻害（メモリリーク）|
| `list[weakref.ref]` を線形検索 | 不採用 | O(N) で重い、エントリ削除も自前実装が必要 |
| **`WeakValueDictionary[int, BaseModel]`** | **採用** | key が int（hashable）で制約回避、value は weakref で GC 連動、O(1) 判定 |

**利用方針**:

- 通常のテストでは `is_synthetic` を呼ぶ必要はない（factory 経由で生成した時点で synthetic と分かっているため）
- `is_synthetic` は「テスト境界を越えて本番コードに synthetic データが流れていないか」をアサーションで確認したい場面（Repository レイヤテスト等の後段 feature）で利用する想定
- 本番コード（`backend/src/bakufu/`）からは `tests/factories/empire.py` を import しない（責務分離、CI で `tests/` から `src/` へのみ依存する向きを強制）

## E2E テストケース

**該当なし** — 理由:

- 本 feature は domain 層の純粋ライブラリで、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない（[`basic-design.md §モジュール契約`](basic-design.md) §画面・CLI 仕様 / §API 仕様 で「該当なし」と凍結）
- テスト戦略ガイド §E2E対象の判断「バッチ処理・内部API・ライブラリなどエンドユーザー操作がない場合は結合テストで代替可」に従い、E2E は本 feature 範囲外
- 後続 feature/http-api（Empire CRUD エンドポイント）/ feature/admin-cli（`bakufu admin empire create` 等）が公開 I/F を実装した時点で E2E を起票する

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — domain 層のため公開 I/F なし | — | — |

## 結合テストケース

domain 層単独の本 feature では「結合」を **Aggregate 内 module 連携（Empire + RoomRef + AgentRef + EmpireInvariantViolation の往復シナリオ）** と定義する。外部 LLM / Discord / GitHub / DB は本 feature では使わないためモック不要。

| テストID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|----------------|---------|------|---------|
| TC-IT-EM-001 | `Empire` + `RoomRef` + `AgentRef` + `EmpireInvariantViolation` | 不要（外部 I/O ゼロ） | factory で valid な空 Empire 1 件 | 1) Empire 構築 → 2) AgentRef 1 件 hire_agent → 3) RoomRef 1 件 establish_room → 4) archive_room（同 room_id）→ 5) 各段階で新 Empire を返すこと、frozen により元 Empire は不変であること、最終状態で `agents` 1 件、`rooms` 1 件（archived=True）であることを確認 | 受入基準 1, 3, 5, 7 を一連で確認、Pydantic frozen 不変性を経路全体で確認 |
| TC-IT-EM-002 | `Empire.hire_agent`（失敗）+ `Empire.establish_room`（成功）+ `Empire.archive_room`（成功） | 不要 | factory で AgentRef 1 件・RoomRef 1 件を持つ Empire | 1) 既登録の agent_id を再 hire_agent → `EmpireInvariantViolation(kind='agent_duplicate')` 発生 → 2) 元 Empire が変化していないこと（agents 1 件のまま）を確認 → 3) 続けて新 RoomRef を establish_room → 成功 → 4) 続けて archive_room → 成功 | 失敗の独立性（pre-validate 方式 確定 A）が連続操作で破綻しないこと、受入基準 4, 5, 7 |

**注**: 本 feature では結合テストも `tests/integration/test_empire_aggregate.py` ではなく `tests/domain/test_empire.py` 内で「往復シナリオ」セクションとして実装してよい（domain 層単独で integration ディレクトリを作る必要は薄い）。実装担当の判断で配置を決める。

## ユニットテストケース

`tests/factories/empire.py` の factory 経由で入力を生成する。raw fixture は本 feature では存在しない（外部 I/O ゼロ）ため raw 直読禁止ルールは構造的に適用不能。

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---------|-----|------|---------------|---------|
| TC-UT-EM-001 | `Empire(id, name)` | 正常系 | `EmpireFactory(name='山田の幕府')` 相当の valid 入力 | `rooms=[]` / `agents=[]` の Empire が返る、`id` / `name` が入力通り |
| TC-UT-EM-002 | `Empire(id, name)` | 境界値/異常系 | `name=''`、`name='a'`（1 文字）、`name='a'*80`（80 文字）、`name='a'*81`（81 文字）、`name='   '`（空白のみ） | 0 文字 / 81 文字 / 空白のみは `EmpireInvariantViolation(kind='name_range')`、1 文字 / 80 文字は成功 |
| TC-UT-EM-003 | `Empire(id, name)` NFC 正規化 | 正常系 | `name` に合成形カタカナ「テスト」（U+30C6 U+30B9 U+30C8 等を分解形・合成形両方で）、前後空白あり `name='  山田の幕府  '` | `Empire.name` が NFC 正規化済み・strip 済みで保持される（確定 B） |
| TC-UT-EM-004 | `Empire.hire_agent(agent_ref)` | 正常系 | 空 Empire + `AgentRefFactory()` 1 件 | 新 Empire の `agents` に 1 件追加、元 Empire の `agents` は空のまま（frozen 不変性） |
| TC-UT-EM-005 | `Empire.hire_agent(agent_ref)` 連続 | 正常系 | 空 Empire + `AgentRefFactory()` を異なる agent_id で 3 件 | 最終 Empire の `agents` 件数が 3、agent_id が全て異なる |
| TC-UT-EM-006 | `Empire.hire_agent(agent_ref)` 重複 | 異常系 | factory で `agent_id` 重複の 2 件目を hire_agent | `EmpireInvariantViolation(kind='agent_duplicate')` raise、元 Empire は agents 1 件のまま |
| TC-UT-EM-007 | `Empire.hire_agent(agent_ref)` 容量上限 | 境界値 | `AgentRefFactory()` を 100 件まで成功、101 件目で失敗 | 100 件目までは成功、101 件目で `EmpireInvariantViolation(kind='capacity_exceeded')`、元 Empire は agents 100 件のまま（確定 C） |
| TC-UT-EM-008 | `Empire.establish_room(room_ref)` | 正常系 | 空 Empire + `RoomRefFactory()` 1 件 | 新 Empire の `rooms` に 1 件追加、元 Empire は空のまま |
| TC-UT-EM-009 | `Empire.establish_room(room_ref)` 重複 | 異常系 | factory で `room_id` 重複の 2 件目を establish_room | `EmpireInvariantViolation(kind='room_duplicate')` raise、元 Empire は rooms 1 件のまま |
| TC-UT-EM-010 | `Empire.establish_room(room_ref)` 容量上限 | 境界値 | `RoomRefFactory()` を 100 件まで成功、101 件目で失敗 | 100 件目までは成功、101 件目で `EmpireInvariantViolation(kind='capacity_exceeded')` |
| TC-UT-EM-011 | `Empire.archive_room(room_id)` | 正常系 | rooms 3 件（うち 2 件目を archive） | 新 Empire の `rooms` は 3 件のまま、対象 room_id の RoomRef のみ `archived=True`、他 2 件は `archived=False` |
| TC-UT-EM-012 | `Empire.archive_room(room_id)` 未登録 | 異常系 | rooms 1 件、別の `room_id` を指定 | `EmpireInvariantViolation(kind='room_not_found')` raise、元 Empire は変化なし |
| TC-UT-EM-013 | `Empire.archive_room(room_id)` 物理削除しない | 正常系 | rooms 1 件、その room_id を archive | 新 Empire の `rooms` 件数が 1 のまま、`archived=True` のみ変化（確定 D / 監査可視性） |
| TC-UT-EM-014 | `Empire.hire_agent` 失敗時の元 Empire 不変 | 異常系 | agents 1 件、同 agent_id を hire_agent して失敗 | 失敗後、元 Empire の `agents` 件数 1、内容も完全一致（pre-validate 方式 確定 A） |
| TC-UT-EM-015 | `Empire.establish_room` 失敗時の元 Empire 不変 | 異常系 | rooms 1 件、同 room_id を establish_room して失敗 | 失敗後、元 Empire の `rooms` 件数 1、内容も完全一致 |
| TC-UT-EM-016 | `Empire.archive_room` 失敗時の元 Empire 不変 | 異常系 | rooms 1 件、未登録 room_id を archive_room して失敗 | 失敗後、元 Empire の `rooms` の `archived` フラグも変化なし |
| TC-UT-EM-017 | frozen 不変性 | 異常系 | `empire.name = 'X'` / `room_ref.archived = True` / `agent_ref.role = ...` 直接代入 | `pydantic.ValidationError`（frozen instance への代入拒否）、Empire / RoomRef / AgentRef すべてで確認 |
| TC-UT-EM-018 | `extra='forbid'` 未知フィールド拒否 | 異常系 | `Empire.model_validate({'id': ..., 'name': ..., 'unknown_field': 'x'})` | `pydantic.ValidationError`、`extra` 違反を検出（T1 防御） |
| TC-UT-EM-019 | MSG-EM-001 文言照合 | 異常系 | (a) `name='a'*81` (b) `name='   '`（半角空白 3）(c) `name='　　a'`（全角空白 + a を 81 文字相当に拡張、strip + NFC 後 81 文字）| (a) `[FAIL] Empire name must be 1-80 characters (got 81)` と完全一致、(b) `(got 0)` と完全一致（strip 後 0 文字）、(c) NFC + strip 後の length と完全一致。詳細設計 §確定 B の正規化パイプライン適用後の `len()` であることを 3 ケースで担保 |
| TC-UT-EM-020 | MSG-EM-002 文言照合 | 異常系 | agent_id 重複で hire_agent 失敗 | 例外 `message` が `[FAIL] Agent already hired: agent_id={agent_id}` 形式で当該 agent_id を含む |
| TC-UT-EM-021 | MSG-EM-003 文言照合 | 異常系 | room_id 重複で establish_room 失敗 | 例外 `message` が `[FAIL] Room already established: room_id={room_id}` 形式で当該 room_id を含む |
| TC-UT-EM-022 | MSG-EM-004 文言照合 | 異常系 | 未登録 room_id で archive_room 失敗 | 例外 `message` が `[FAIL] Room not found in Empire: room_id={room_id}` 形式 |
| TC-UT-EM-023 | MSG-EM-005 文言照合 | 異常系 | 上記 4 種以外の不変条件違反（例: 容量超過） | 例外 `message` が `[FAIL] Empire invariant violation: {detail}` プレフィックスで始まる |

### Value Object 単独テスト（参考）

`RoomRef` / `AgentRef` は frozen VO として独立してテストする（Empire を経由しない契約検証）。

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-VO-001 | `RoomRef(room_id, name, archived=False)` | 正常系 | UUID + name 1 文字 / 80 文字 | 成功 |
| TC-UT-VO-002 | `RoomRef` name 境界値 | 異常系 | name 0 / 81 文字 | `pydantic.ValidationError` または `EmpireInvariantViolation`（実装担当判断、契約のみ凍結） |
| TC-UT-VO-003 | `AgentRef(agent_id, name, role)` | 正常系 | UUID + name 40 文字 + 各 Role enum 値 | 成功 |
| TC-UT-VO-004 | `AgentRef` name 境界値 | 異常系 | name 0 / 41 文字 | バリデーションエラー |
| TC-UT-VO-005 | `AgentRef` 不正 Role | 異常系 | `role='UNKNOWN'`（enum 外） | `pydantic.ValidationError` |
| TC-UT-VO-006 | `RoomRef` / `AgentRef` 構造的等価 | 正常系 | 全属性が同値の 2 インスタンス | `==` が True、`hash()` が一致 |

## カバレッジ基準

- REQ-EM-001 〜 005 の各要件が**最低 1 件**のテストケースで検証されている（マトリクス参照）
- MSG-EM-001 〜 005 の各文言が**静的文字列で照合**されている（TC-UT-EM-019 〜 023）
- 受入基準 1 〜 9 の各々が**最低 1 件のユニットテストケースまたは結合テストケース**で検証されている（E2E 不在のため受入基準は unit/integration で代替、戦略ガイド準拠）
- 開発者品質 Q-1（pyright/ruff）/ Q-2（カバレッジ 95%）は CI ジョブ（lint / typecheck / test-backend）で担保
- T1 / T2 の各脅威に対する対策が**最低 1 件のテストケース**で有効性を確認されている（マトリクス末尾参照）
- 確定 A（pre-validate）/ B（NFC）/ C（容量 100）/ D（線形探索）に対する証拠ケースが各々最低 1 件
- C0（行カバレッジ）目標: `domain/empire.py` で **95% 以上**（domain 層は 95% 基準、要件分析書 §非機能要求準拠）、`value_objects.py`（追加分のみ）で 90% 以上

## 人間が動作確認できるタイミング

本 feature は domain 層単独のため、人間が UI / CLI で触れるタイミングは無い。レビュワー / オーナーは以下で動作確認する。

- CI 統合後: `gh pr checks` で 7 ジョブ緑（lint / typecheck / test-backend / audit / fmt / commit-msg / no-ai-footer）
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/domain/test_empire.py -v` → 全テスト緑
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.domain.empire --cov-report=term-missing tests/domain/test_empire.py` → `domain/empire.py` 95% 以上
- 例外文言の実観測: `uv run python -c "from bakufu.domain.empire import Empire; Empire(id=..., name='a'*81)"` で MSG-EM-001 が出ることを目視（実装担当が PR 説明欄に貼り付け）

後段で feature/http-api（Empire CRUD エンドポイント）が完成したら、本 feature の Empire を経由して `curl` 経由の手動シナリオで E2E 観測可能になる。それまでは「単体ライブラリの契約テスト」で十分。

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      __init__.py
      empire.py                # EmpireFactory / RoomRefFactory / AgentRefFactory / RoleFactory
    domain/
      __init__.py
      test_empire.py           # TC-UT-EM-001〜023 + TC-IT-EM-001〜002（往復シナリオ section）
      test_value_objects.py    # TC-UT-VO-001〜006（既存ファイルに追記）
```

**配置の根拠**:
- 本 feature は domain 層単独・外部 I/O ゼロのため `tests/integration/` ディレクトリは作らない（戦略ガイドの「言語の慣習を尊重」に準拠、Python では tests/ 階層を切るが integration ディレクトリは外部依存を持つ場合に用意するのが慣習）
- 結合テスト（TC-IT-EM-001, 002）は `test_empire.py` 内に「Aggregate-内往復シナリオ」セクションとして同居させる。`integration/` を空ディレクトリで作るより読み手の負担が小さい
- characterization fixture / raw / schema は本 feature では生成しない（外部 I/O ゼロのため）
- factory のみは生成する（unit テストの入力バリエーション網羅のため）

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| （N/A） | 該当なし — 外部 I/O ゼロのため characterization 不要 | — | 後続 feature/persistence（DB I/O）/ feature/http-api（HTTP 境界）/ feature/discord-notifier（Discord webhook）が起票時に Empire 起点の characterization が発生する見込み |

## レビュー観点（テスト設計レビュー時）

- [ ] 受入基準 1〜8 が unit/integration ケースに 1:N で対応している（マトリクス確認）
- [ ] MSG-EM-001〜005 の文言が静的文字列で照合される設計になっている
- [ ] 確定 A〜D（pre-validate / NFC / 容量 100 / 線形探索）に対する証拠ケースが含まれる
- [ ] 脅威 T1 / T2 への有効性確認ケースが含まれる
- [ ] 外部 I/O ゼロの主張が basic-design.md / feature-spec.md と整合している
- [ ] E2E 不在の根拠（公開 I/F なし）が戦略ガイド §E2E対象の判断と整合している
- [ ] frozen 不変性 / extra='forbid' / Unicode NFC が独立してテストされている
- [ ] factory モジュールの `_synthetic_registry`（`WeakValueDictionary[int, BaseModel]`）に factory 生成インスタンスが登録され、`is_synthetic(instance)` で判定可能になっている（Pydantic frozen + extra='forbid' を尊重）
- [ ] テスト配置が言語慣習（Python `tests/` 階層 + factory 経由）に従っている
