# テスト設計書 — directive / domain

<!-- feature: directive -->
<!-- sub-feature: domain -->
<!-- 配置先: docs/features/directive/domain/test-design.md -->
<!-- 対象範囲: REQ-DR-001〜003 / MSG-DR-001〜005 / 親 spec 受入基準 1〜7, 9 / 詳細設計 確定 A〜H / `link_task` 一意遷移 + auto-mask + 例外型統一 + 2 行構造 MSG -->

本 sub-feature は domain 層の Aggregate Root（Directive）と例外（DirectiveInvariantViolation）に閉じる M1 5 兄弟目（empire / workflow / agent / room の確立済みパターンを継承）。HTTP API / CLI / UI の公開エントリポイントは持たないため、E2E は本 sub-feature 範囲外（親 [`../system-test-design.md`](../system-test-design.md) で管理）。本 sub-feature のテストは **ユニット主体 + Aggregate 内 module 連携の往復シナリオ + 責務境界の物理確認** で構成する。

empire / workflow / agent / room の test-design.md と完全に同じ規約を踏襲（外部 I/O ゼロ・factory に `_meta.synthetic = True` の `WeakValueDictionary` レジストリ）。Directive は Aggregate 内 VO を新規追加しない（`DirectiveId` / `RoomId` / `TaskId` は既存）ため、factory 規模は最小。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-DR-001 | `Directive.__init__` / `model_validator(mode='after')` | TC-UT-DR-001 | ユニット | 正常系 | 1 |
| REQ-DR-001（text 境界） | `Directive.text` の長さバリデーション | TC-UT-DR-002 | ユニット | 境界値 | 2 |
| REQ-DR-001（NFC 正規化） | `Directive.text` の NFC 正規化（確定 B） | TC-UT-DR-003 | ユニット | 正常系 | 3 |
| REQ-DR-001（strip しない） | `Directive.text` の前後改行・空白保持（確定 B） | TC-UT-DR-004 | ユニット | 正常系 | 4 |
| REQ-DR-001（task_id 直接構築） | コンストラクタで `task_id=既存有効TaskId` を渡せる（永続化からの復元経路） | TC-UT-DR-014 | ユニット | 正常系 | （確定 C） |
| REQ-DR-001（created_at tz-aware） | naive datetime を渡すと `pydantic.ValidationError` | TC-UT-DR-015 | ユニット | 異常系 | （MSG-DR-003） |
| REQ-DR-002 | `Directive.link_task` 正常系 | TC-UT-DR-005 | ユニット | 正常系 | 5 |
| REQ-DR-002（再リンク禁止） | 既に紐付け済みの Directive で `link_task` 再呼び出し | TC-UT-DR-006 | ユニット | 異常系 | 6 |
| REQ-DR-002（同一 TaskId 再リンク） | `task_id == new_task_id` でも Fail Fast（確定 D の冪等性なし契約） | TC-UT-DR-016 | ユニット | 異常系 | （確定 D） |
| REQ-DR-003-① | text 1〜10000 文字 | TC-UT-DR-002 | ユニット | 境界値 | 2 |
| REQ-DR-003-② | task_id 一意遷移 | TC-UT-DR-006 | ユニット | 異常系 | 6 |
| 確定 A（pre-validate） | `link_task` 失敗時の元 Directive 不変 | TC-UT-DR-017 | ユニット | 異常系 | — |
| 確定 B（NFC + strip しない） | NFC 合成形 / 分解形が同一視される | TC-UT-DR-003 | ユニット | 正常系 | 3 |
| 確定 B（strip しない） | 前後改行・空白を保持 | TC-UT-DR-004 | ユニット | 正常系 | 4 |
| 確定 C（一意遷移検査） | `link_task` ふるまい入口で `self.task_id is None` を検査 | TC-UT-DR-006, TC-UT-DR-016 | ユニット | 異常系 | 6 |
| 確定 D（冪等性なし） | 同 TaskId 再リンクも Fail Fast | TC-UT-DR-016 | ユニット | 異常系 | （確定 D） |
| 確定 E（webhook auto-mask） | `DirectiveInvariantViolation` の auto-mask | TC-UT-DR-007 | ユニット | 異常系 | 7 |
| 確定 F（例外型統一） | text 違反は `DirectiveInvariantViolation`、型違反は `pydantic.ValidationError` | TC-UT-DR-002, TC-UT-DR-015 | ユニット | 異常系 | （確定 F） |
| 確定 G（target_room_id 検証） | Aggregate 内では `target_room_id` の Room 存在を検証しない（責務境界） | TC-UT-DR-018 | ユニット | 正常系 | （責務境界） |
| 確定 G（$ プレフィックス） | Aggregate 内では `$` プレフィックスを正規化しない（application 層責務） | TC-UT-DR-019 | ユニット | 正常系 | （責務境界） |
| 確定 H（責務分離マトリクス） | application 層責務 4 件すべてが Aggregate 内で強制されないことを物理確認 | TC-UT-DR-018, TC-UT-DR-019 | ユニット | 正常系 | （責務境界） |
| frozen 不変性 | `Directive.text = 'X'` 等の直接代入拒否 | TC-UT-DR-020 | ユニット | 異常系 | 内部品質基準 |
| frozen 構造的等価 | 同一属性の Directive 2 インスタンスが `==` True / `hash()` 一致 | TC-UT-DR-008 | ユニット | 正常系 | 内部品質基準 |
| `extra='forbid'` | 未知フィールド拒否 | TC-UT-DR-021 | ユニット | 異常系 | （T1 防御） |
| MSG-DR-001（2 行構造） | `[FAIL] Directive text must be 1-10000 characters (got {length})` + `Next:` hint | TC-UT-DR-022 | ユニット | 異常系 | 2, 9 |
| MSG-DR-002（2 行構造） | `[FAIL] Directive already has a linked Task: directive_id={...}, existing_task_id={...}` + `Next:` hint | TC-UT-DR-023 | ユニット | 異常系 | 6, 9 |
| MSG-DR-003 | 型違反は `pydantic.ValidationError` 経由（kind 概念なし） | TC-UT-DR-015 | ユニット | 異常系 | （確定 F） |
| **Next: hint 物理保証**（確定 F） | 全 MSG-DR-001/002 で `assert "Next:" in str(exc)` を CI 強制 | TC-UT-DR-022, TC-UT-DR-023 | ユニット | 異常系 | 9（room §確定 I 踏襲） |
| AC-lint/typecheck | `pyright --strict` / `ruff check` | （CI ジョブ） | — | — | 内部品質基準 |
| AC-カバレッジ | `pytest --cov=bakufu.domain.directive` | （CI ジョブ） | — | — | 内部品質基準 |
| 結合シナリオ 1 | `Directive` + `DirectiveInvariantViolation` 往復 | TC-IT-DR-001 | 結合 | 正常系/異常系 | 1, 5 |
| 結合シナリオ 2 | `link_task` 失敗 → 同一 Directive で再リンク不可（pre-validate 連続安全性） | TC-IT-DR-002 | 結合 | 異常系 | 5, 6 |

**マトリクス充足の証拠**:

- REQ-DR-001〜003 すべてに最低 1 件のテストケース
- **`task_id` 一意遷移検査（確定 C / D）**: None → 有効 TaskId は OK（TC-UT-DR-005）+ 有効 TaskId への上書きは raise（TC-UT-DR-006）+ 同一 TaskId 再リンクも raise（TC-UT-DR-016）の 3 経路で「冪等性なし、1 回のみ許可」契約を物理確認
- **責務境界 4 件**（`target_room_id` Room 存在 / `$` プレフィックス正規化 / Workflow 解決 / Task 生成と紐付けの 1 Tx）すべてに「Aggregate 層で強制しない」ことを物理確認する unit ケース（TC-UT-DR-018, TC-UT-DR-019）。room §確定 R1-A 系と同パターンで責務境界を test で凍結し将来の誤った Aggregate 内強制への退行を防ぐ
- **DirectiveInvariantViolation auto-mask（確定 E）**: webhook URL を含む 10001 文字超過の text で例外発生 → message と detail の両方が伏字化されていることを TC-UT-DR-007 で確認
- **MSG 2 行構造 + Next: hint 物理保証（確定 F、room §確定 I 踏襲）**: 全 MSG-DR-001/002 で `assert "Next:" in str(exc)` を CI 強制（TC-UT-DR-022, TC-UT-DR-023）。「hint が抜けたら CI で落ちる」を test 層で凍結
- MSG-DR-001〜005 すべてに静的文字列照合（MSG-DR-003〜005 は application 層 / `pydantic.ValidationError` 経由のため範囲外注意書きあり）
- 親 spec 受入基準 1〜7, 9 すべてに unit/integration ケース
- 確定 A（pre-validate）/ B（NFC + strip しない）/ C（一意遷移）/ D（冪等性なし）/ E（auto-mask）/ F（例外型統一 + 2 行 MSG）/ G（responsibility 分離）/ H（責務分離マトリクス）すべてに証拠ケース
- 孤児要件ゼロ

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **該当なし** | Directive は domain 層単独で外部 I/O を持たない（HTTP / DB / ファイル / 時刻 / LLM / Discord いずれも未依存）。`text` は文字列バリデーションのみで実 LLM 送信は `feature/llm-adapter` 責務。`target_room_id` / `task_id` も VO 型として保持のみで、参照先 Aggregate の存在検証は application 層責務（`DirectiveService.issue()`） | — | — | **不要（外部 I/O ゼロ）** |
| `unicodedata.normalize('NFC', ...)` | text 正規化 | — | — | 不要（CPython 標準ライブラリ仕様で固定、empire / workflow / agent / room と同方針） |
| `datetime.now(UTC)` | `Directive.created_at`（呼び出し側 application 層で生成して引数渡し、Aggregate 内では受け取るのみ） | — | — | 不要（Aggregate 内で時刻を取得しない、§確定設計判断「なぜ created_at を引数で受け取るか」） |

**根拠**:
- [`basic-design.md`](basic-design.md) §外部連携 で「該当なし — domain 層のみのため外部システムへの通信は発生しない」と凍結
- 本 sub-feature では assumed mock 問題は構造上発生しない（モック対象なし）

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `DirectiveFactory` | `Directive`（valid デフォルト = `task_id=None`、`created_at=datetime.now(UTC)`、短文 text） | `True` |
| `LinkedDirectiveFactory` | `Directive`（valid デフォルト + `task_id=既存有効TaskId`、永続化復元シナリオ用） | `True` |
| `LongTextDirectiveFactory` | `Directive`（text 10000 文字、上限境界） | `True` |

`_meta.synthetic = True` は empire / workflow / agent / room と同じく **`tests/factories/directive.py` モジュールスコープ `WeakValueDictionary[int, BaseModel]` レジストリ + `id(instance)` をキーに `is_synthetic()` で判定** 方式を踏襲する。frozen + `extra='forbid'` を尊重してインスタンスに属性追加は試みない。本番コード（`backend/src/bakufu/`）からは `tests/factories/directive.py` を import しない（CI で `tests/` から `src/` への向きのみ許可）。

## E2E テストケース

**該当なし** — 理由:

- 本 sub-feature は domain 層の純粋ライブラリで、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない
- E2E は親 [`../system-test-design.md`](../system-test-design.md) が管理する（TC-E2E-DR-001, 002）
- 受入基準 1〜7, 9 はすべて unit/integration テストで検証可能

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — domain 層のため公開 I/F なし | — | — |

## 結合テストケース

domain 層単独の本 sub-feature では「結合」を **Aggregate 内 module 連携（Directive + DirectiveInvariantViolation の往復シナリオ）+ pre-validate 連続シナリオ**と定義する。外部 LLM / Discord / GitHub / DB は本 sub-feature では使わないためモック不要。

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-DR-001 | `Directive` + `DirectiveInvariantViolation` 往復 | factory（`DirectiveFactory`） | task_id=None の最小 Directive | 1) `link_task(task_id_1)` で None → 有効 TaskId 遷移 → 新 Directive、元 Directive は task_id=None のまま → 2) 新 Directive で `link_task(task_id_2)` を試行 → MSG-DR-002 で raise → 3) 元 Directive と新 Directive の構造的等価判定（`==` False、task_id が異なる） | 受入基準 1, 5 を一連で確認、Pydantic frozen 不変性を経路全体で確認 |
| TC-IT-DR-002 | `Directive.link_task`（失敗）+ pre-validate 連続安全性 | factory | 既に紐付け済み Directive（task_id=既存有効TaskId） | 1) 同一 Directive で `link_task(new_task_id)` → MSG-DR-002 で raise → 2) 元 Directive の task_id が unchanged であることを確認（pre-validate 確定 A）→ 3) 別の新規 task_id_3 でも `link_task` → 同様に raise（再リンク禁止は永続的） | 失敗の独立性（pre-validate 確定 A）が連続操作で破綻しないこと、受入基準 5, 6 |

**注**: 本 sub-feature では結合テストも `tests/integration/test_directive.py` ではなく `tests/domain/directive/test_directive.py` 内の「往復シナリオ」セクションとして実装してよい（empire / workflow / agent / room と同方針）。

## ユニットテストケース

`tests/factories/directive.py` の factory 経由で入力を生成する。raw fixture は本 sub-feature では外部 I/O ゼロのため存在しない。

### Directive Aggregate Root（不変条件 2 種、親 spec 受入基準 1〜7）

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---------|-----|------|---------------|---------|
| TC-UT-DR-001 | `Directive(id, text, target_room_id, created_at)` task_id=None 既定 | 正常系 | factory デフォルト | 構築成功、`task_id=None`、`text` は NFC 正規化済み、`created_at` は tz-aware UTC |
| TC-UT-DR-002 | `Directive.text` 境界値（確定 B） | 境界値 | text 0 / 1 / 10000 / 10001 文字、NFC 分解形混入 | 0/10001 は拒否 + MSG-DR-001、1/10000 は成功 |
| TC-UT-DR-003 | NFC 正規化（確定 B） | 正常系 | 合成形 `'ダリオ要件'` / 分解形 `'ダリオ要件'`（カタカナ NFD） | 両 Directive の `text` が NFC 正規化済みで同一値、構造的等価が成立 |
| TC-UT-DR-004 | strip しない（確定 B） | 正常系 | `text='\n# Directive\n\nbody\n\n'`（前後改行を含む） | `Directive.text == '\n# Directive\n\nbody\n\n'`（改行が保持される）。CEO directive の段落構造を保持する設計判断の物理確認 |
| TC-UT-DR-005 | `Directive.link_task(task_id)` 正常系 | 正常系 | task_id=None の Directive + 有効 TaskId | 新 Directive の `task_id` が有効 TaskId に遷移、元 Directive は task_id=None のまま（frozen） |
| TC-UT-DR-006 | `link_task` 再リンク禁止（確定 C / D） | 異常系 | 既に紐付け済み Directive（task_id=既存有効TaskId） + 別の new_task_id | 拒否、detail に `directive_id` / `existing_task_id` / `attempted_task_id` を含む |
| TC-UT-DR-007 | T2: `DirectiveInvariantViolation` の webhook auto-mask（確定 E） | 異常系 | webhook URL を含む 10001 文字超過 text を構築試行 | 例外の `str(exc)` および `exc.detail` の両方で webhook URL の token 部分が `<REDACTED:DISCORD_WEBHOOK>` に伏字化されていること（agent / workflow / room と同パターン） |
| TC-UT-DR-008 | frozen 構造的等価 / hash（内部品質基準） | 正常系 | 全属性同値の Directive を 2 インスタンス | `==` True、`hash()` 一致。frozen + `model_config.frozen=True` 起因 |
| TC-UT-DR-014 | コンストラクタで task_id=既存有効TaskId（確定 C） | 正常系 | `Directive(task_id=既存TaskId)` での直接構築 | 構築成功（永続化からの復元経路、`_validate_task_link_immutable` は link_task 経路でのみ発動、コンストラクタ経路は許容） |
| TC-UT-DR-015 | created_at tz-aware 必須（MSG-DR-003） | 異常系 | `created_at=datetime.now()`（naive、tz 情報なし） | 型違反（kind 概念なし、確定 F の例外型統一規約）、message に tz / timezone / aware 等のキーワード含む |
| TC-UT-DR-016 | 同一 TaskId 再リンク（確定 D 冪等性なし） | 異常系 | 既存 task_id == new_task_id（同じ TaskId で 2 回 link_task） | 拒否、冪等にしない設計の物理確認（確定 D「1 回のみ許可、2 回目は常に Fail Fast」） |

### pre-validate 方式（確定 A）の元 Directive 不変性

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-DR-017 | `link_task` 失敗時の元 Directive 不変 | 異常系 | 既に紐付け済み Directive で `link_task` を試行（再リンク違反） | 失敗後、元 Directive の `task_id` が完全に変化なし（pre-validate 確定 A）。さらに別の new_task_id でも繰り返し失敗するため、状態破損が連続操作で進まないことを確認 |

### frozen / extra='forbid' / VO 構造的等価（内部品質基準、T1 防御）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-DR-020 | frozen 不変性 | 異常系 | `directive.text = 'X'` / `directive.task_id = ...` 等の直接代入 | 拒否（frozen instance への代入拒否）、Directive の全属性で確認 |
| TC-UT-DR-021 | `extra='forbid'` 未知フィールド拒否 | 異常系 | `Directive.model_validate({...,'unknown': 'x'})` | 型違反（`extra` 違反、T1 関連の入力境界防御） |

### application 層責務メタ（責務境界の物理確認、確定 G / H）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-DR-018 | Directive Aggregate は `target_room_id` の Room 存在を**検証しない**（確定 G） | 正常系 | 存在しない room_id（任意の UUIDv4 を生成）で Directive を構築 | 構築成功（Aggregate は target_room_id を VO 型として保持するのみ）。Room 存在検証は `DirectiveService.issue()` の `RoomRepository.find_by_id` 経由（room §確定 R1-A 系と同パターン） |
| TC-UT-DR-019 | Directive Aggregate は `text` の `$` プレフィックスを**正規化しない**（確定 G） | 正常系 | `text='ブログ分析機能を作って'`（`$` 無し）で Directive を構築 | 構築成功、`text` は `$` プレフィックス無しのまま保持される。`$` 正規化は `DirectiveService.issue()` 責務 |

これら 2 件は「将来の誤った Aggregate 内強制への退行を test で物理的に防ぐ」境界凍結ケース。

### MSG 文言照合 + Next: hint 物理保証（確定 F、受入基準 9）

**フィードバック原則の物理保証**（room §確定 I 踏襲、Norman R1 対応）: 全 MSG は **2 行構造**（1 行目 = 失敗事実 `[FAIL] ...`、2 行目 = 次の行動 `Next: ...`）。test 側で **`assert "Next:" in str(exc)`** を必須とし、hint 行が抜けたら CI で落ちる構造で凍結する。

| テストID | MSG ID | 例外型 | 入力 | 期待結果（1 行目: failure 完全一致 / 2 行目: hint 部分一致） |
|---------|--------|--------|------|---------|
| TC-UT-DR-022 | MSG-DR-001 | text 範囲違反 | text='a'*10001 | 1 行目: `[FAIL] Directive text must be 1-10000 characters (got 10001)` で始まる、2 行目: **`assert "Next:" in str(exc)`** + `assert "Trim" in str(exc)` または `"multiple directives" in str(exc)`（複数 directive 提案 hint） |
| TC-UT-DR-023 | MSG-DR-002 | task 再リンク違反 | 既に紐付け済み Directive で `link_task` 再呼び出し | 1 行目: `[FAIL] Directive already has a linked Task: directive_id=<id>, existing_task_id=<id>` 形式、2 行目: **`assert "Next:" in str(exc)`** + `assert "Issue a new Directive" in str(exc)`（新規 directive 発行 hint） + `assert "one Directive maps to one Task" in str(exc)`（1:1 設計言明） |

## カバレッジ基準

- REQ-DR-001 〜 003 の各要件が**最低 1 件**のテストケースで検証されている（マトリクス参照）
- 不変条件 2 種それぞれが独立した unit ケースで検証されている（`text` 範囲 / `task_id` 一意遷移）
- **`task_id` 一意遷移検査（確定 C / D）**: None → 有効 TaskId は OK（TC-UT-DR-005）+ 既存有効 TaskId への上書き禁止（TC-UT-DR-006）+ 同一 TaskId 再リンクも raise（TC-UT-DR-016）の 3 経路で「冪等性なし、1 回のみ許可」を物理確認
- **責務境界 2 件**（`target_room_id` Room 存在 / `$` プレフィックス正規化）すべてに「Aggregate 層で強制しない」ことを物理確認する unit ケース（TC-UT-DR-018, TC-UT-DR-019）。責務境界を test で凍結し将来の誤った Aggregate 内強制への退行を防ぐ
- **DirectiveInvariantViolation auto-mask（T2 防御、確定 E）**: webhook URL 含む入力で例外発生時に message と detail の両方が伏字化されていることを TC-UT-DR-007 で確認
- MSG-DR-001 / 002 の各文言が**静的文字列で照合**されており、加えて **`assert "Next:" in str(exc)` の hint 物理保証**を全 2 ケースで実施（TC-UT-DR-022, TC-UT-DR-023、確定 F / room §確定 I 踏襲）。「hint が抜けたら CI で落ちる」物理層でフィードバック原則を凍結
- MSG-DR-003 は型違反経路として TC-UT-DR-015 で確認（kind 概念なし、確定 F 例外型統一規約）
- MSG-DR-004 / 005 は application 層 `DirectiveService.issue()` の責務、本 sub-feature 範囲外（後続 `feature/directive-application` で起票）
- 親 spec 受入基準 1 〜 7, 9 の各々が**最低 1 件のユニット/結合ケース**で検証されている
- 受入基準 10（E2E: 永続化）は親 [`../system-test-design.md`](../system-test-design.md) で管理。受入基準 11（masking IT）は repository sub-feature の test-design.md で管理
- C0 目標: `domain/directive/` 配下で **95% 以上**（domain 層基準、要件分析書 §非機能要求準拠）

## 人間が動作確認できるタイミング

本 sub-feature は domain 層単独のため、人間が UI / CLI で触れるタイミングは無い。レビュワー / オーナーは以下で動作確認する。

- CI 統合後: `gh pr checks` で 7 ジョブ緑（lint / typecheck / test-backend / audit / fmt / commit-msg / no-ai-footer）
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/domain/directive/test_directive.py -v` → 全テスト緑
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.domain.directive --cov-report=term-missing tests/domain/directive/test_directive.py` → `domain/directive/` 95% 以上
- 不変条件違反の実観測: 不正入力で MSG-DR-001/002 が出ることを目視（実装担当が PR 説明欄に貼り付け）
- `link_task` 再リンク禁止の実観測: `uv run python -c "from tests.factories.directive import DirectiveFactory; from uuid import uuid4; d = DirectiveFactory(); d2 = d.link_task(uuid4()); d2.link_task(uuid4())"` で MSG-DR-002 が出ることを目視
- webhook auto-mask の実観測: `text='https://discord.com/api/webhooks/123/secret-token-..' + 'a'*10000` の形で webhook URL を含む長文を構築試行 → 例外 message / detail に `<REDACTED:DISCORD_WEBHOOK>` が出ることを目視

後段で `directive/http-api/` sub-feature（Directive 発行 API）/ `directive/ui/` sub-feature（CEO directive 発行チャット画面）が完成したら、本 sub-feature の Directive を経由して `curl` 経由の手動シナリオで E2E 観測可能になる。

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      __init__.py
      directive.py             # DirectiveFactory / LinkedDirectiveFactory /
                               # LongTextDirectiveFactory
                               # （empire / workflow / agent / room 流の
                               # WeakValueDictionary レジストリ + is_synthetic()）
    domain/
      directive/
        __init__.py
        test_directive.py      # TC-UT-DR-001〜023 + TC-IT-DR-001〜002（往復シナリオ section）
```

**配置の根拠**:
- empire / workflow / agent / room と同方針: domain 層単独・外部 I/O ゼロのため `tests/integration/` ディレクトリは作らない
- characterization / raw / schema は本 sub-feature では生成しない（外部 I/O ゼロ）
- factory のみは生成する（unit テストの入力バリエーション網羅のため）
- 本 sub-feature では agent / room と同じく helper module-level 独立化（`_validate_text_range` / `_validate_task_link_immutable`）を `aggregate_validators.py` に持つ。test 側は `Directive` を構築 / メソッド呼び出しすることで間接的に helper を経路網羅する

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| （N/A） | 該当なし — 外部 I/O ゼロのため characterization 不要 | — | 後続 `repository` sub-feature の Repository 実装（DB 永続化、`directives.text` を `MaskedText` 列で配線、`storage.md` §逆引き表に Directive 行追加対象）/ `directive/ui/` sub-feature（Web UI）が起票時に Directive 起点の characterization が発生する見込み |

**Schneier 申し送り（前 PR レビューより継承）**:

- **`Directive.text` の secret マスキング**: 本 sub-feature では文字列保持のみ。永続化前マスキング規則（[`storage.md`](../../../design/domain-model/storage.md) §シークレットマスキング規則）の適用は `repository` sub-feature 責務として明示申し送り（detailed-design §データ構造（永続化キー）に `MaskedText` 列指定済）。本 sub-feature では「domain VO は raw 保持、Repository 層で適用」という適用先指定を凍結
- **本 sub-feature 固有の申し送り**:
  - `target_room_id` 参照整合性 / Workflow 解決 / Task 生成と紐付けの 1 Tx は `DirectiveService.issue()` 責務（確定 G / H）。`feature/directive-application` 実装時に MSG-DR-004 / 005 + 1 Tx 内 Task 生成 + link_task の順序を漏れなく実装する申し送り
  - prompt injection 対策（敵対的 directive text 検出 / ユーザー入力境界 escape）は `feature/llm-adapter` および `directive/http-api/` 実装時の入力境界責務として残す。本 sub-feature は長さ制約（10000 文字）のみを Pydantic field validator + `_validate_text_range` で Fail Fast
  - `link_task` の冪等性なし契約（確定 D）: 業務シナリオで再リンクが必要な場合は新規 Directive 発行で対応する設計。将来で「Directive update」業務要求が出た場合のみ再検討

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-DR-001〜003 すべてに 1 件以上のテストケースがあり、不変条件 2 種が独立 unit で検証されている
- [ ] **`task_id` 一意遷移検査**が「None → 有効 TaskId（TC-UT-DR-005）+ 既存 → new で拒否（TC-UT-DR-006）+ 同一 TaskId でも拒否（TC-UT-DR-016）」の 3 経路で確定 C / D を物理確認している
- [ ] **責務境界 2 件**（`target_room_id` Room 存在 / `$` プレフィックス正規化）すべてが「Aggregate 内で強制しない」ことを TC-UT-DR-018 / 019 で物理確認している
- [ ] **DirectiveInvariantViolation auto-mask（確定 E）**が webhook URL 含む長文での例外発生時に message + detail 両方で伏字化されることを TC-UT-DR-007 で確認している
- [ ] **MSG 2 行構造 + Next: hint（確定 F、room §確定 I 踏襲）**: TC-UT-DR-022 / 023 で全 2 MSG-DR で `assert "Next:" in str(exc)` を CI 強制
- [ ] MSG-DR-003 が型違反経路として TC-UT-DR-015 で確認されている（例外型統一規約）
- [ ] MSG-DR-004 / 005 が application 層責務として明示され、本 sub-feature テスト範囲外であることが明確
- [ ] 確定 A〜H（pre-validate / NFC + strip しない / 一意遷移 / 冪等性なし / auto-mask / 例外型統一 + 2 行 MSG / responsibility 分離 / 責務分離マトリクス）すべてに証拠ケースが含まれる
- [ ] frozen 不変性（TC-UT-DR-020）+ 構造的等価（TC-UT-DR-008）+ extra='forbid'（TC-UT-DR-021）が独立して検証されている（内部品質基準として）
- [ ] empire / workflow / agent / room の WeakValueDictionary レジストリ方式と整合した factory 設計になっている
- [ ] 外部 I/O ゼロの主張が basic-design.md と整合している
- [ ] Schneier 申し送り（`Directive.text` の persistence-foundation 経由マスキング配線 / `DirectiveService.issue()` の Tx 境界 / prompt injection は別 feature 責務）が次レビュー時に確認可能な形で記録されている
