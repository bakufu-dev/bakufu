# テスト設計書

<!-- feature: agent -->
<!-- 配置先: docs/features/agent/test-design.md -->
<!-- 対象範囲: REQ-AG-001〜006 / MSG-AG-001〜008 / 脅威 T1, T2 / 受入基準 1〜13 / 詳細設計 確定 A〜E + SkillRef.path 防御規則 / `is_default` ちょうど 1 件強制 / archive 冪等性 / name 一意の application 層責務 / SkillRef.path traversal 防御 7 規則 -->

本 feature は domain 層の Aggregate Root（Agent）と内部 VO（Persona / ProviderConfig / SkillRef）と例外（AgentInvariantViolation）に閉じる。HTTP API / CLI / UI の公開エントリポイントは持たないため、E2E は本 feature 範囲外（後続 feature/agent-ui / feature/http-api / feature/admin-cli で起票）。本 feature のテストは **ユニット主体 + 結合は Aggregate 内 module 連携の往復シナリオ + name 一意 application 層責務の境界線確認**で構成する。

empire / workflow の test-design.md と同じ規約を踏襲（外部 I/O ゼロ・factory に `_meta.synthetic = True` の `WeakValueDictionary` レジストリ）。Workflow のような helper module-level 独立化（確定 F）は本 feature では不要（不変条件検査が単純なため Agent.model_validator 内に直接記述で十分）。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-AG-001 | `Agent.__init__` / `model_validator(mode='after')` | TC-UT-AG-001 | ユニット | 正常系 | 1 |
| REQ-AG-001（name 境界） | `Agent.name` バリデーション | TC-UT-AG-002 | ユニット | 境界値 | 2 |
| REQ-AG-001（NFC 正規化） | `Agent.name` の NFC + strip（確定 E） | TC-UT-AG-012 | ユニット | 正常系 | （確定 E） |
| REQ-AG-001（providers 0 件） | `Agent(providers=[])` 拒否 | TC-UT-AG-013 | ユニット | 異常系 | （MSG-AG-002） |
| REQ-AG-001（providers 容量） | `len(providers) <= 10` | TC-UT-AG-014 | ユニット | 境界値 | （確定 C） |
| REQ-AG-001（provider_kind 重複） | `provider_kind` 重複拒否 | TC-UT-AG-015 | ユニット | 異常系 | （MSG-AG-004） |
| REQ-AG-001（Persona prompt_body 長） | 10000 / 10001 文字境界 | TC-UT-AG-016 | ユニット | 境界値 | （MSG-AG-005 / 確定 R1-D / T1 関連） |
| REQ-AG-002 | `Agent.set_default_provider` 正常系 | TC-UT-AG-005 | ユニット | 正常系 | 5 |
| REQ-AG-002（未登録） | `Agent.set_default_provider(unknown)` | TC-UT-AG-006 | ユニット | 異常系 | 6 |
| REQ-AG-002（既定切替の他フラグ更新） | 切替後に他 provider が is_default=False になる | TC-UT-AG-017 | ユニット | 正常系 | 5 |
| REQ-AG-003 | `Agent.add_skill` 正常系 | TC-UT-AG-007 | ユニット | 正常系 | 7 |
| REQ-AG-003（重複） | `add_skill` で skill_id 重複 | TC-UT-AG-008 | ユニット | 異常系 | 8 |
| REQ-AG-003（容量） | `len(skills) <= 20` | TC-UT-AG-018 | ユニット | 境界値 | （確定 C） |
| REQ-AG-004 | `Agent.remove_skill` 正常系 | TC-UT-AG-009 | ユニット | 正常系 | 9 |
| REQ-AG-004（未登録） | `remove_skill` で skill_id 未登録 | TC-UT-AG-019 | ユニット | 異常系 | （MSG-AG-008） |
| REQ-AG-005 | `Agent.archive()` 正常系 | TC-UT-AG-010 | ユニット | 正常系 | 10 |
| REQ-AG-005（冪等性） | 既 `archived=True` の Agent に `archive()` 再呼び出し | TC-UT-AG-020 | ユニット | 正常系 | （確定 D） |
| REQ-AG-006-① | name 1〜40 文字 | TC-UT-AG-002 | ユニット | 境界値 | 2 |
| REQ-AG-006-② | providers 1〜10 件 | TC-UT-AG-013, TC-UT-AG-014 | ユニット | 異常系/境界値 | — |
| REQ-AG-006-③ | provider_kind 重複なし | TC-UT-AG-015 | ユニット | 異常系 | — |
| REQ-AG-006-④ | `is_default == True` ちょうど 1 件（**0 件拒否**） | TC-UT-AG-003 | ユニット | 異常系 | 3 |
| REQ-AG-006-④ | `is_default == True` ちょうど 1 件（**2 件以上拒否**） | TC-UT-AG-004 | ユニット | 異常系 | 4 |
| REQ-AG-006-④ | `is_default == True` ちょうど 1 件（境界 0 / 1 / 2 / 3 件 全網羅、確定 B） | TC-UT-AG-021 | ユニット | 境界値 | 3, 4 |
| REQ-AG-006-⑤ | `skill_id` 重複なし、skills ≤ 20 件 | TC-UT-AG-008, TC-UT-AG-018 | ユニット | 異常系/境界値 | 8 |
| 確定 A（pre-validate） | `set_default_provider` 失敗時の元 Agent 不変 | TC-UT-AG-022 | ユニット | 異常系 | — |
| 確定 A（pre-validate） | `add_skill` 失敗時の元 Agent 不変 | TC-UT-AG-023 | ユニット | 異常系 | — |
| 確定 A（pre-validate） | `remove_skill` 失敗時の元 Agent 不変 | TC-UT-AG-024 | ユニット | 異常系 | — |
| 確定 D（archive 冪等性） | 連続 archive() 呼び出し | TC-UT-AG-020, TC-UT-AG-025 | ユニット | 正常系 | （確定 D / UX 担保） |
| 確定 E（NFC + strip） | name / Persona.display_name の NFC 正規化 | TC-UT-AG-012 | ユニット | 正常系 | — |
| frozen 不変性 | `Agent` / `Persona` / `ProviderConfig` / `SkillRef` 属性代入拒否 | TC-UT-AG-026 | ユニット | 異常系 | 11 |
| frozen 構造的等価 | VO の `__eq__` / `__hash__` | TC-UT-AG-011 | ユニット | 正常系 | 11 |
| `extra='forbid'` | 未知フィールド拒否 | TC-UT-AG-027 | ユニット | 異常系 | （T1 防御） |
| T1（prompt 長さ制約） | `Persona.prompt_body` 10001 文字拒否（サニタイズ・マスキングは別 feature 責務） | TC-UT-AG-016 | ユニット | 境界値/異常系 | （MSG-AG-005） |
| T2（不正 ProviderConfig） | `provider_kind` enum 外を Pydantic で Fail Fast 拒否 | TC-UT-AG-028 | ユニット | 異常系 | — |
| application 層責務メタ | Agent Aggregate は `name` の Empire 内一意を**強制しない** | TC-UT-AG-029 | ユニット | 正常系 | （確定 R1-B / 責務境界の物理確認） |
| Persona.archetype 境界 | `Persona.archetype` 0 / 80 / 81 文字 | TC-UT-VO-AG-007 | ユニット | 境界値 | （Schneier 申し送り Boy Scout: display_name と prompt_body にあり archetype に欠落していた片手落ちを補完） |
| SkillRef.path 防御 ① | NFC 正規化（empire / workflow と同方針）合成形 / 分解形が同一値として保持 | TC-UT-AG-038 | ユニット | 正常系 | （Schneier 凍結 1 / threat-model.md §A1 path 版） |
| SkillRef.path 防御 ② | 拒否文字: `\` / `\0` / ASCII 制御文字 (0x00〜0x1F、0x7F) / 先頭 `/` / Windows 絶対パス (`C:\...` / `D:/...`) | TC-UT-AG-039 | ユニット | 異常系 | （Schneier 凍結 2） |
| SkillRef.path 防御 ③ | `..` 連続を含むパスを拒否（`bakufu-data/skills/../../../etc/passwd` / `bakufu-data/skills/sub/../escape` 等） | TC-UT-AG-040 | ユニット | 異常系 | （Schneier 凍結 2 / path traversal 中核） |
| SkillRef.path 防御 ④ | PurePosixPath prefix 強制（`parts[0] == 'bakufu-data'` かつ `parts[1] == 'skills'`） | TC-UT-AG-041 | ユニット | 異常系 | （Schneier 凍結 3） |
| SkillRef.path 防御 ⑤ | `is_relative_to()` 物理保証（正規化後 base directory 外に出るパス拒否） | TC-UT-AG-042 | ユニット | 異常系 | （Schneier 凍結 4） |
| SkillRef.path 防御 ⑥ | Windows 予約名拒否（`CON` / `PRN` / `AUX` / `NUL` / `COM1〜9` / `LPT1〜9`、大文字小文字無視 + `.md` 等の拡張子付きも） | TC-UT-AG-043 | ユニット | 異常系 | （Schneier 凍結 6） |
| SkillRef.path 防御 ⑦ | 先頭 / 末尾の空白・`.` を拒否 | TC-UT-AG-044 | ユニット | 異常系 | （Schneier 凍結 2 補足） |
| SkillRef.path 防御 ⑧ | 長さ境界（0 / 500 / 501 文字、Schneier 凍結 5、既存 TC-UT-VO-AG-006 を維持） | TC-UT-VO-AG-006 | ユニット | 境界値 | （Schneier 凍結 5） |
| MSG 新設 | `[FAIL] SkillRef.path invalid: {detail}` 系の文言（ダリオが detailed-design 修正で確定する `kind='skill_path_invalid'` の MSG を追加予定）| TC-UT-AG-045 | ユニット | 異常系 | （MSG 文言照合、ダリオ修正後に MSG ID 確定） |
| MSG-AG-001 | `[FAIL] Agent name must be 1-40 characters (got {length})` | TC-UT-AG-030 | ユニット | 異常系 | 2 |
| MSG-AG-002 | `[FAIL] Agent must have at least one provider` | TC-UT-AG-031 | ユニット | 異常系 | （文言照合） |
| MSG-AG-003 | `[FAIL] Exactly one provider must have is_default=True (got {count})` | TC-UT-AG-032 | ユニット | 異常系 | 3, 4 |
| MSG-AG-004 | `[FAIL] Duplicate provider_kind: {kind}` | TC-UT-AG-033 | ユニット | 異常系 | （文言照合） |
| MSG-AG-005 | `[FAIL] Persona.prompt_body must be 0-10000 characters (got {length})` | TC-UT-AG-034 | ユニット | 異常系 | （文言照合） |
| MSG-AG-006 | `[FAIL] provider_kind not registered: {kind}` | TC-UT-AG-035 | ユニット | 異常系 | 6 |
| MSG-AG-007 | `[FAIL] Skill already added: skill_id={skill_id}` | TC-UT-AG-036 | ユニット | 異常系 | 8 |
| MSG-AG-008 | `[FAIL] Skill not found in agent: skill_id={skill_id}` | TC-UT-AG-037 | ユニット | 異常系 | （文言照合） |
| AC-12（lint/typecheck） | `pyright --strict` / `ruff check` | （CI ジョブ） | — | — | 12 |
| AC-13（カバレッジ） | `pytest --cov=bakufu.domain.agent` | （CI ジョブ） | — | — | 13 |
| 結合シナリオ 1 | `Agent` + `Persona` + `ProviderConfig` + `SkillRef` + `AgentInvariantViolation` 往復 | TC-IT-AG-001 | 結合 | 正常系/異常系 | 1, 5, 7, 9, 10 |
| 結合シナリオ 2 | Provider 切替（失敗→成功）の連続（pre-validate 連続安全性） | TC-IT-AG-002 | 結合 | 異常系/正常系 | 5, 6 |

**マトリクス充足の証拠**:
- REQ-AG-001〜006 すべてに最低 1 件のテストケース
- REQ-AG-006 不変条件 5 種すべてに独立した検証ケース（①〜⑤）
- **`is_default == True` ちょうど 1 件**: 0 / 1 / 2 / 3 件の境界値全網羅（TC-UT-AG-003, 004, 021）
- **`name` Empire 内一意は application 層責務**: TC-UT-AG-029 で「Aggregate 内では同 name の 2 件構築が成功する」ことを物理層で確認し、責務境界を test で凍結
- **`archive()` 冪等性**: 既 `archived=True` への呼び出し（TC-UT-AG-020）+ 連続呼び出し（TC-UT-AG-025）の 2 経路。返り値は `model_validate` 経由のため**新インスタンス**（同状態）を返す（ダリオ修正後の確定 D に整合）
- **SkillRef.path traversal 防御 7 規則**: NFC 正規化 / 拒否文字 / `..` 連続 / `bakufu-data/skills/` prefix 強制 / `is_relative_to()` 物理保証 / Windows 予約名拒否 / 先頭末尾空白の各々を独立 unit ケース化（TC-UT-AG-038〜044）+ 長さ境界（TC-UT-VO-AG-006）+ MSG 文言照合（TC-UT-AG-045）
- **Persona.archetype 境界**: 0 / 80 / 81 文字を TC-UT-VO-AG-007 で網羅（display_name / prompt_body と同水準に揃える）
- MSG-AG-001〜008（+ ダリオ追加予定の path_invalid MSG）すべてに静的文字列照合
- 受入基準 1〜11 すべてに unit/integration ケース（12/13 は CI ジョブ）
- T1（prompt_body 長さ）/ T2（不正 ProviderConfig）すべてに有効性確認ケース
- 確定 A（pre-validate）/ B（is_default count）/ C（容量 10/20）/ D（archive 冪等性 + 新インスタンス）/ E（NFC + strip、`Agent.name` + `Persona.display_name` 両方）すべてに証拠ケース
- 孤児要件ゼロ

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **該当なし** | Agent は domain 層単独で外部 I/O を持たない（HTTP / DB / ファイル / 時刻 / LLM / Discord いずれも未依存）。`Persona.prompt_body` は文字列バリデーションのみで、実際に LLM へ送信する経路は本 feature には存在しない（`feature/llm-adapter` 責務）。`SkillRef.path` も文字列バリデーションのみで実ファイル読み込みは行わない（`feature/skill-loader` 責務） | — | — | **不要（外部 I/O ゼロ）** |
| `unicodedata.normalize('NFC', ...)` | name / Persona.display_name 正規化 | — | — | 不要（CPython 標準ライブラリ仕様で固定、empire / workflow と同方針） |

**根拠**:
- [`basic-design.md`](basic-design.md) §外部連携 で「該当なし — domain 層のみのため外部システムへの通信は発生しない」と凍結
- [`requirements-analysis.md`](requirements-analysis.md) §前提条件・制約 で「ネットワーク: 該当なし」と凍結
- 本 feature では assumed mock 問題は構造上発生しない（モック対象なし）

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `AgentFactory` | `Agent`（valid デフォルト = 1 Provider with is_default=True、skills 空、archived=False） | `True` |
| `ArchivedAgentFactory` | `Agent`（valid デフォルト + `archived=True`） | `True` |
| `PersonaFactory` | `Persona`（valid デフォルト = display_name 1 件 + archetype 任意 + prompt_body 短文） | `True` |
| `LongPromptPersonaFactory` | `Persona`（prompt_body 10000 文字、上限境界） | `True` |
| `ProviderConfigFactory` | `ProviderConfig`（`provider_kind=CLAUDE_CODE` / `model='sonnet'` / `is_default=True` を default） | `True` |
| `NonDefaultProviderConfigFactory` | `ProviderConfig`（`is_default=False`） | `True` |
| `SkillRefFactory` | `SkillRef`（valid デフォルト） | `True` |

`_meta.synthetic = True` は empire / workflow と同じく **`tests/factories/agent.py` モジュールスコープ `WeakValueDictionary[int, BaseModel]` レジストリ + `id(instance)` をキーに `is_synthetic()` で判定** 方式を踏襲する。frozen + `extra='forbid'` を尊重してインスタンスに属性追加は試みない。本番コード（`backend/src/bakufu/`）からは `tests/factories/agent.py` を import しない（CI で `tests/` から `src/` への向きのみ許可）。

## E2E テストケース

**該当なし** — 理由:

- 本 feature は domain 層の純粋ライブラリで、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない（[`requirements.md`](requirements.md) §画面・CLI 仕様 / §API 仕様 で「該当なし」と凍結）
- 戦略ガイド §E2E対象の判断「バッチ処理・内部API・ライブラリなどエンドユーザー操作がない場合は結合テストで代替可」に従い、E2E は本 feature 範囲外
- 後続 feature/admin-cli（`bakufu admin agent hire` 等）/ feature/http-api（Agent CRUD）/ feature/agent-ui（Web UI）が公開 I/F を実装した時点で E2E を起票
- 受入基準 1〜11 はすべて unit/integration テストで検証可能（12/13 は CI ジョブ）

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — domain 層のため公開 I/F なし | — | — |

## 結合テストケース

domain 層単独の本 feature では「結合」を **Aggregate 内 module 連携（Agent + Persona + ProviderConfig + SkillRef + AgentInvariantViolation の往復シナリオ）+ pre-validate 連続シナリオ**と定義する。外部 LLM / Discord / GitHub / DB は本 feature では使わないためモック不要。

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-AG-001 | `Agent` + `Persona` + `ProviderConfig` + `SkillRef` + `AgentInvariantViolation` 往復 | factory（`AgentFactory` / `PersonaFactory` / `ProviderConfigFactory` / `SkillRefFactory`） | 1 Provider（is_default=True）の最小 Agent | 1) `add_skill` で skill 1 件追加 → 2) 2 番目の Provider（is_default=False）を含む factory で構築 → 3) `set_default_provider(2 番目)` で切替 → 4) 1 番目が is_default=False、2 番目が True に → 5) `remove_skill` で削除 → 6) `archive()` で archived=True に → 7) 各段階で frozen 不変性により元 Agent が変化しないことを確認 | 受入基準 1, 5, 7, 9, 10 を一連で確認、Pydantic frozen 不変性を経路全体で確認 |
| TC-IT-AG-002 | `Agent.set_default_provider`（失敗）+（成功）の連続 | factory | 2 Provider の Agent（CLAUDE_CODE デフォルト + CODEX 非デフォルト） | 1) 未登録 `provider_kind=GEMINI` を `set_default_provider` → MSG-AG-006 で raise → 2) 元 Agent が unchanged であることを確認（pre-validate）→ 3) 続けて登録済み `CODEX` を `set_default_provider` → 成功 → 4) CLAUDE_CODE が is_default=False、CODEX が True に切り替わったことを確認 | 失敗の独立性（pre-validate 確定 A）が連続操作で破綻しないこと、受入基準 5, 6 |

**注**: 本 feature では結合テストも `tests/integration/test_agent.py` ではなく `tests/domain/test_agent.py` 内の「往復シナリオ」セクションとして実装してよい（empire / workflow と同方針）。

## ユニットテストケース

`tests/factories/agent.py` の factory 経由で入力を生成する。raw fixture は本 feature では外部 I/O ゼロのため存在しない。

### Agent Aggregate Root（不変条件 5 種）

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---------|-----|------|---------------|---------|
| TC-UT-AG-001 | `Agent(id, name, persona, role, providers=[1 件 is_default=True], skills=[])` | 正常系 | factory デフォルト | 構築成功、`archived=False`、`providers` 1 件、`skills` 0 件 |
| TC-UT-AG-002 | `Agent.name` 境界値 | 境界値 | name 0 / 1 / 40 / 41 文字、空白のみ、NFC 分解形混入 | 0/41/空白のみは `AgentInvariantViolation(kind='name_range')` + MSG-AG-001、1/40 は成功 |
| TC-UT-AG-003 | `is_default == True` 0 件 | 異常系 | 全 provider が `is_default=False` | `AgentInvariantViolation(kind='default_not_unique')`、MSG-AG-003、`(got 0)` を含む |
| TC-UT-AG-004 | `is_default == True` 2 件以上 | 異常系 | 2 provider が両方 `is_default=True` | `AgentInvariantViolation(kind='default_not_unique')`、MSG-AG-003、`(got 2)` を含む |
| TC-UT-AG-012 | name / Persona.display_name の NFC + strip 正規化 | 正常系 | 合成形「ダリオ」/分解形「ダリオ」/前後空白あり `name='  ダリオ  '` | `Agent.name` および `persona.display_name` が NFC + strip 後の文字列で保持される |
| TC-UT-AG-013 | `providers=[]`（空配列） | 異常系 | providers リストが空 | `AgentInvariantViolation(kind='no_provider')`、MSG-AG-002 |
| TC-UT-AG-014 | providers 容量上限 | 境界値 | 10 件成功、11 件目で raise | 10 まで成功、11 で `AgentInvariantViolation`（確定 C） |
| TC-UT-AG-015 | provider_kind 重複 | 異常系 | 同一 provider_kind=CLAUDE_CODE で 2 エントリ | `AgentInvariantViolation(kind='provider_duplicate')`、MSG-AG-004 |
| TC-UT-AG-016 | Persona.prompt_body 境界値（T1 関連） | 境界値 | 0 / 10000 / 10001 文字 | 0/10000 は成功、10001 で `AgentInvariantViolation(kind='persona_too_long')`、MSG-AG-005、`(got 10001)` を含む |
| TC-UT-AG-021 | `is_default == True` count 全網羅（確定 B） | 境界値 | 3 provider で is_default=True が 0 / 1 / 2 / 3 件のパラメタライズ | 0 / 2 / 3 件は raise、1 件のみ成功 — `sum(1 for p in providers if p.is_default)` 検査の境界全網羅 |

### set_default_provider / add_skill / remove_skill / archive（pre-validate 方式 確定 A）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-AG-005 | `set_default_provider(provider_kind)` | 正常系 | 2 Provider Agent（CLAUDE_CODE デフォルト + CODEX 非デフォルト）に対し `set_default_provider(CODEX)` | 新 Agent の providers で CODEX が is_default=True、CLAUDE_CODE が False、元 Agent は変化なし |
| TC-UT-AG-006 | `set_default_provider` 未登録 | 異常系 | 登録されていない provider_kind=GEMINI | `AgentInvariantViolation(kind='provider_not_found')`、MSG-AG-006 |
| TC-UT-AG-017 | 切替後の他 provider フラグ更新 | 正常系 | 3 Provider Agent | `set_default_provider(CODEX)` 後、CODEX 以外の全 provider が is_default=False になることを assert |
| TC-UT-AG-007 | `add_skill(skill_ref)` | 正常系 | 空 skills + SkillRef 1 件 | 新 Agent の `skills` に 1 件追加、元 Agent は空のまま |
| TC-UT-AG-008 | `add_skill` 重複 | 異常系 | 既存 skill_id の SkillRef を追加 | `AgentInvariantViolation(kind='skill_duplicate')`、MSG-AG-007 |
| TC-UT-AG-018 | skills 容量上限 | 境界値 | 20 件成功、21 件目で raise | 20 まで成功、21 で raise（確定 C） |
| TC-UT-AG-009 | `remove_skill(skill_id)` | 正常系 | skills 1 件 + その skill_id を remove | 新 Agent の `skills` 0 件、元 Agent は 1 件のまま |
| TC-UT-AG-019 | `remove_skill` 未登録 | 異常系 | 存在しない skill_id を指定 | `AgentInvariantViolation(kind='skill_not_found')`、MSG-AG-008 |
| TC-UT-AG-010 | `archive()` 正常系 | 正常系 | archived=False の Agent | 新 Agent の `archived=True`、元 Agent は False のまま |
| TC-UT-AG-020 | `archive()` 冪等性（確定 D） | 正常系 | 既 `archived=True` の Agent に `archive()` 再呼び出し | 例外を raise**せず**、`archived=True` の Agent を返す（同状態の新インスタンス）。エラーにしない理由は UX 担保（確定 D） |
| TC-UT-AG-025 | `archive()` 連続呼び出し（冪等性の連続安全性） | 正常系 | archived=False の Agent → `archive()` → `archive()` → `archive()` を 3 連続 | 全呼び出しで `archived=True` の Agent を返す、エラーなし、最終状態が `archived=True` |
| TC-UT-AG-022 | `set_default_provider` 失敗時の元 Agent 不変 | 異常系 | 未登録 provider_kind で失敗 | 失敗後、元 Agent の providers の各 is_default フラグが完全に変化なし（pre-validate 確定 A） |
| TC-UT-AG-023 | `add_skill` 失敗時の元 Agent 不変 | 異常系 | 重複 skill_id で失敗 | 元 Agent の skills 件数・内容完全一致 |
| TC-UT-AG-024 | `remove_skill` 失敗時の元 Agent 不変 | 異常系 | 未登録 skill_id で失敗 | 元 Agent の skills 件数・内容完全一致 |

### frozen / extra='forbid' / VO 構造的等価（受入基準 11）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-AG-011 | VO 構造的等価 / hash | 正常系 | 全属性同値の Persona / ProviderConfig / SkillRef を 2 インスタンス | `==` True、`hash()` 一致（受入基準 11） |
| TC-UT-AG-026 | frozen 不変性 | 異常系 | `agent.name = 'X'` / `persona.archetype = ...` / `provider.is_default = ...` / `skill_ref.path = ...` 直接代入 | `pydantic.ValidationError`（frozen instance への代入拒否）、Agent / Persona / ProviderConfig / SkillRef すべてで確認 |
| TC-UT-AG-027 | `extra='forbid'` 未知フィールド拒否 | 異常系 | `Agent.model_validate({...,'unknown': 'x'})` | `pydantic.ValidationError`、`extra` 違反（T1 関連の入力境界防御） |

### 脅威対策（T1 / T2）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-AG-028 | T2: `provider_kind` enum 外を Pydantic で Fail Fast 拒否 | 異常系 | `provider_kind='UNKNOWN_PROVIDER'`（enum 外文字列） | `pydantic.ValidationError`（enum 不一致）、Agent 構築前に検出 |

**T1 申し送り**: `Persona.prompt_body` の prompt injection 対策は本 feature では **長さ上限のみ**を検証する（TC-UT-AG-016 で 10001 文字拒否）。実際のサニタイズ（敵対的プロンプト検出 / ユーザー入力境界での escape）は `feature/llm-adapter` および `feature/http-api` の入力境界責務として残す。LLM 出力を直接 shell 実行する経路は提供しないことが [`threat-model.md`](../../design/threat-model.md) §A2 で凍結されており、本 feature 範囲では prompt_body の長さ制約と永続化前マスキング規則の適用先指定（domain 層では文字列保持のみ、Repository 層で適用）に閉じる。

### application 層責務メタ（責務境界の物理確認）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-AG-029 | Agent Aggregate は `name` の Empire 内一意を**強制しない**（確定 R1-B） | 正常系 | 同 `name='ダリオ'` で異なる id の Agent 2 件を独立して構築 | 両方とも構築成功、`AgentInvariantViolation` を raise**しない**ことを assert。これは「name 一意は application 層 `AgentService.hire()` の `AgentRepository.find_by_name()` 経由で判定する」という責務境界を test で凍結し、将来の誤った Aggregate 内強制への退行を防ぐ |

### MSG 文言照合

| テストID | MSG ID | 入力 | 期待結果 |
|---------|--------|------|---------|
| TC-UT-AG-030 | MSG-AG-001 | name='a'*41 | `[FAIL] Agent name must be 1-40 characters (got 41)` 完全一致 |
| TC-UT-AG-031 | MSG-AG-002 | providers=[] | `[FAIL] Agent must have at least one provider` 完全一致 |
| TC-UT-AG-032 | MSG-AG-003 | is_default=True が 0 件 / 2 件 | `[FAIL] Exactly one provider must have is_default=True (got 0)` および `(got 2)` の各形式完全一致 |
| TC-UT-AG-033 | MSG-AG-004 | provider_kind 重複 | `[FAIL] Duplicate provider_kind: CLAUDE_CODE` 形式 |
| TC-UT-AG-034 | MSG-AG-005 | prompt_body 10001 文字 | `[FAIL] Persona.prompt_body must be 0-10000 characters (got 10001)` 完全一致 |
| TC-UT-AG-035 | MSG-AG-006 | set_default_provider 未登録 | `[FAIL] provider_kind not registered: GEMINI` 形式 |
| TC-UT-AG-036 | MSG-AG-007 | add_skill 重複 | `[FAIL] Skill already added: skill_id=<id>` 形式 |
| TC-UT-AG-037 | MSG-AG-008 | remove_skill 未登録 | `[FAIL] Skill not found in agent: skill_id=<id>` 形式 |

### Value Object 単独テスト

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-VO-AG-001 | `Persona(display_name, archetype, prompt_body)` | 正常系 | display_name 1〜40 / archetype 0〜80 / prompt_body 0〜10000 各境界 | 成功 |
| TC-UT-VO-AG-002 | `Persona.display_name` 境界違反 | 異常系 | display_name 0 / 41 文字 | `pydantic.ValidationError` |
| TC-UT-VO-AG-003 | `ProviderConfig(provider_kind, model, is_default)` | 正常系 | 全 ProviderKind enum 値（CLAUDE_CODE / CODEX / GEMINI / OPENCODE / KIMI / COPILOT）+ model 1〜80 文字 | 成功 |
| TC-UT-VO-AG-004 | `ProviderConfig.model` 境界違反 | 異常系 | model 0 / 81 文字 | `pydantic.ValidationError` |
| TC-UT-VO-AG-005 | `SkillRef(skill_id, name, path)` | 正常系 | UUID + name 1〜80 + path 1〜500 文字（valid 形式 `bakufu-data/skills/xxx.md`） | 成功 |
| TC-UT-VO-AG-006 | `SkillRef.path` 境界違反 | 異常系 | path 0 / 501 文字（Schneier 凍結 5） | `pydantic.ValidationError` |
| TC-UT-VO-AG-007 | `Persona.archetype` 境界値（**Boy Scout 補完**） | 境界値 | archetype 0 / 80 / 81 文字 | 0 / 80 文字は成功、81 文字で `pydantic.ValidationError`、`(got 81)` 形式の文言 |

### SkillRef.path traversal 防御規則（threat-model.md §A1 path 版、Schneier 凍結 1〜6）

ダリオが `detailed-design.md §SkillRef` に追加凍結した 6 規則 + 補足規則を、**全 7 規則を独立 unit ケース化**する。これは Empire / Workflow と同じ「VO レベルでの最初の防衛線」原則に揃える。`feature/skill-loader` での realpath 解決はあくまで Defense in Depth の 2 層目で、本 feature が 1 層目（VO Fail Fast）を担う。

| テストID | 規則 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-AG-038 | ① NFC 正規化 | 正常系 | 合成形 / 分解形両方の `bakufu-data/skills/テスト.md`（カタカナの NFC vs NFD） | `SkillRef.path` が NFC 正規化済みで保持され、構造的等価が成立。empire / workflow と同方針 |
| TC-UT-AG-039 | ② 拒否文字 | 異常系 | `path='bakufu-data/skills/foo\\bar.md'`（バックスラッシュ）/ `'...\x00malicious'`（NUL）/ `'...\x01ctrl'`（制御文字 0x01）/ `'/etc/passwd'`（先頭スラッシュ）/ `'C:\\Windows\\system32'`（Windows 絶対パス）/ `'D:/foo'` | 全て `pydantic.ValidationError`（or `AgentInvariantViolation(kind='skill_path_invalid')`）、Schneier 凍結 2 で挙げられた**全攻撃パターン**を Fail Fast 拒否、detail に違反種別を含む |
| TC-UT-AG-040 | ③ `..` 連続拒否（path traversal 中核） | 異常系 | `path='bakufu-data/skills/../../../etc/passwd'` / `'bakufu-data/skills/sub/../escape'` / `'bakufu-data/skills/./../config'` / `'bakufu-data/skills/legitimate/../../escape'` | 全て `pydantic.ValidationError`、PurePosixPath 正規化後に `..` が parts に残る場合**および**正規化後にコンポーネント数が減って base directory を脱出するケースの両方を拒否 |
| TC-UT-AG-041 | ④ prefix 強制（`bakufu-data/skills/`） | 異常系 | `path='other/path/file.md'`（先頭違反）/ `'bakufu-data/other/file.md'`（2 階層目違反）/ `'skills/file.md'`（先頭 `bakufu-data` 欠落）/ `'bakufu-data/'`（skills 欠落）| 全て `pydantic.ValidationError`、`PurePosixPath(path).parts[0] == 'bakufu-data' and parts[1] == 'skills'` を完全一致照合（Schneier 凍結 3） |
| TC-UT-AG-042 | ⑤ `is_relative_to()` 物理保証 | 異常系 | `path='bakufu-data/skills/legitimate/../../sneaky/escape.md'`（normalize すると `bakufu-data/sneaky/escape.md` で skills 外）/ `'bakufu-data/skills/.'`（resolve で skills 自身）/ シンボリックリンク的な記述で逃げるパターン | `(BAKUFU_DATA_DIR / path).resolve().is_relative_to((BAKUFU_DATA_DIR / 'skills').resolve())` が False の場合 raise（Schneier 凍結 4）。realpath 比較を VO レベルで強制することで base directory escape を物理層で塞ぐ |
| TC-UT-AG-043 | ⑥ Windows 予約名拒否 | 異常系 | `path='bakufu-data/skills/CON.md'` / `'.../prn.txt'`（小文字）/ `'.../AUX'` / `'.../NUL.markdown'` / `'.../COM1.md'` / `'.../LPT9.md'` / `'.../con'`（拡張子なし） | 全て `pydantic.ValidationError`、stem が予約名（大文字小文字無視）と一致する場合 raise（Schneier 凍結 6、attachment filename と同方針）。拡張子付きでも stem が予約名なら拒否 |
| TC-UT-AG-044 | ⑦ 先頭/末尾の空白・`.` 拒否（Schneier 凍結 2 補足） | 異常系 | `path=' bakufu-data/skills/file.md'`（先頭空白）/ `'bakufu-data/skills/file.md '`（末尾空白）/ `'.bakufu-data/skills/file.md'`（先頭 `.`）/ `'bakufu-data/skills/file.md.'`（末尾 `.`、Windows hidden 攻撃） | 全て `pydantic.ValidationError`、構築前 strip しない（強制拒否）方針で Fail Fast |
| TC-UT-AG-045 | MSG 文言照合 | 異常系 | TC-UT-AG-040 の `..` 含むパスで構築失敗 | 例外 `message` がダリオ修正後に確定する **`[FAIL] SkillRef.path invalid: {detail}`**（仮）プレフィックスで始まり、`detail` に違反規則番号（①〜⑦）を含む。実装時に MSG ID 確定（ダリオ修正のレビュー結果に従う） |

## カバレッジ基準

- REQ-AG-001 〜 006 の各要件が**最低 1 件**のテストケースで検証されている（マトリクス参照）
- 不変条件 5 種それぞれが独立した unit ケースで検証されている（REQ-AG-006 ①〜⑤）
- **`is_default == True` ちょうど 1 件**: 0 / 1 / 2 / 3 件の境界値全網羅（TC-UT-AG-003, 004, 021）
- **`archive()` 冪等性**: 既 `archived=True` への呼び出し（TC-UT-AG-020）+ 連続呼び出し（TC-UT-AG-025）で確認
- **`name` Empire 内一意は application 層責務**: TC-UT-AG-029 で Aggregate 層で強制しないことを物理確認、責務境界を test で凍結
- MSG-AG-001 〜 008 の各文言が**静的文字列で照合**されている（TC-UT-AG-030 〜 037）
- 受入基準 1 〜 11 の各々が**最低 1 件のユニット/結合ケース**で検証されている（E2E 不在のため戦略ガイドの「結合代替可」に従う）
- 受入基準 12（pyright/ruff）/ 13（カバレッジ）は CI ジョブで担保
- T1（prompt_body 長さ）/ T2（不正 ProviderConfig）の各脅威に対する対策が**最低 1 件のテストケース**で有効性を確認されている
- 確定 A（pre-validate）/ B（is_default count）/ C（容量 10/20）/ D（archive 冪等性 + 新インスタンス）/ E（NFC + strip、Agent.name + Persona.display_name 両方）すべてに証拠ケース
- **SkillRef.path traversal 防御 7 規則**（NFC / 拒否文字 / `..` / prefix / `is_relative_to` / Windows 予約名 / 先頭末尾）すべてに独立 unit ケース（TC-UT-AG-038〜044）+ 長さ境界（TC-UT-VO-AG-006）+ MSG 文言照合（TC-UT-AG-045）
- **Persona.archetype 境界**: 0 / 80 / 81 文字を TC-UT-VO-AG-007 で網羅
- C0 目標: `domain/agent.py` で **95% 以上**（domain 層基準、要件分析書 §非機能要求準拠）

## 人間が動作確認できるタイミング

本 feature は domain 層単独のため、人間が UI / CLI で触れるタイミングは無い。レビュワー / オーナーは以下で動作確認する。

- CI 統合後: `gh pr checks` で 7 ジョブ緑（lint / typecheck / test-backend / audit / fmt / commit-msg / no-ai-footer）
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/domain/test_agent.py -v` → 全テスト緑
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.domain.agent --cov-report=term-missing tests/domain/test_agent.py` → `domain/agent.py` 95% 以上
- 不変条件違反の実観測: 不正入力で MSG-AG-001〜008 が出ることを目視（実装担当が PR 説明欄に貼り付け）
- archive 冪等性の実観測: `uv run python -c "agent = AgentFactory(); a1 = agent.archive(); a2 = a1.archive(); print(a1.archived, a2.archived)"` で `True True` が出ることを目視
- is_default ちょうど 1 件の実観測: 0 件 / 2 件の providers で構築試行 → MSG-AG-003 の `(got 0)` / `(got 2)` を目視

後段で feature/admin-cli（`bakufu admin agent hire`）/ feature/http-api（Agent CRUD）が完成したら、本 feature の Agent を経由して `curl` 経由の手動シナリオで E2E 観測可能になる。

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      __init__.py
      agent.py                 # AgentFactory / ArchivedAgentFactory / PersonaFactory / 
                               # LongPromptPersonaFactory / ProviderConfigFactory / 
                               # NonDefaultProviderConfigFactory / SkillRefFactory
                               # （empire / workflow 流の WeakValueDictionary レジストリ + is_synthetic()）
    domain/
      __init__.py
      test_agent.py            # TC-UT-AG-001〜045 + TC-UT-VO-AG-001〜007 + TC-IT-AG-001〜002（往復シナリオ section + SkillRef.path traversal 防御 section）
```

**配置の根拠**:
- empire / workflow と同方針: domain 層単独・外部 I/O ゼロのため `tests/integration/` ディレクトリは作らない
- characterization / raw / schema は本 feature では生成しない（外部 I/O ゼロ）
- factory のみは生成する（unit テストの入力バリエーション網羅のため）
- 本 feature では `feature/workflow` の確定 F（集約検査 helper の module-level 独立化）相当の検査関数群を持たない（不変条件検査が単純なため `Agent.model_validator` 内に直接記述で十分）。Workflow のような DAG BFS や URL allow list G1〜G10 のような複雑検査は無い

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| （N/A） | 該当なし — 外部 I/O ゼロのため characterization 不要 | — | 後続 feature/persistence（DB 永続化、`agents.UNIQUE(empire_id, name)` 制約 + agent_providers の `is_default=TRUE` 1 件 partial unique index）/ feature/llm-adapter（実 LLM API 通信）/ feature/agent-ui（Web UI）が起票時に Agent 起点の characterization が発生する見込み |

**Schneier から前回申し送りされた件への対応状況**（empire / workflow レビューより）:

- **TOCTOU race（empire シングルトン）の系**: 本 PR では対象外。Agent には Empire 相当のシングルトン制約はないが、代わりに **`name` の Empire 内一意**を application 層 + DB UNIQUE で二重防御する設計が detailed-design.md §データ構造（永続化キー）に凍結されている（`agents.UNIQUE(empire_id, name)` + `agent_providers` の partial unique index で `is_default=TRUE` が 1 Agent あたり 1 件）。`feature/persistence` レビュー時にこの DB 制約が `basic-design.md` に書かれていることを必ず確認する申し送り
- **Unicode 不可視文字 / 同形異字符**: 本 PR では対象外（`feature/http-api` の入力境界責務）。Empire / Workflow / Agent 共通で `name` の機密レベルは低のため認可バイパス経路ではないが、後段で抜けないこと
- **Persona.prompt_body の secret マスキング**: 本 feature では文字列保持のみ。永続化前マスキング規則（[`storage.md`](../../design/domain-model/storage.md) §シークレットマスキング規則）の適用は `feature/persistence` 責務として明示申し送り。本 feature では「domain VO は raw 保持、Repository 層で適用」という適用先指定を凍結
- **本 feature 固有の申し送り**: prompt injection 対策（敵対的プロンプト検出 / ユーザー入力境界 escape）は `feature/llm-adapter` および `feature/http-api` の入力境界責務として残す。本 feature は長さ制約のみを Pydantic field validator で Fail Fast。LLM 出力を直接 shell 実行する経路がないことは [`threat-model.md`](../../design/threat-model.md) §A2 で凍結済み

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-AG-001〜006 すべてに 1 件以上のテストケースがあり、不変条件 5 種が独立 unit で検証されている
- [ ] **`is_default == True` ちょうど 1 件**強制が 0 / 1 / 2 / 3 件の境界値全網羅で検証されている（TC-UT-AG-003, 004, 021）
- [ ] **`name` Empire 内一意は application 層責務**であることが TC-UT-AG-029 で「同 name の 2 件構築が成功する」テストとして物理確認されている
- [ ] **`archive()` 冪等性**が既 `archived=True` への呼び出し（TC-UT-AG-020）+ 連続呼び出し（TC-UT-AG-025）の 2 経路で検証され、返り値が `model_validate` 経由の**新インスタンス**であることが明示されている（ダリオ修正後の確定 D に整合）
- [ ] **SkillRef.path traversal 防御 7 規則**すべてが独立 unit ケース（TC-UT-AG-038〜044）で検証されている。特に ③ `..` 連続拒否 / ④ `bakufu-data/skills/` prefix 強制 / ⑤ `is_relative_to()` 物理保証 に抜けがない（threat-model.md §A1 path 版）
- [ ] **`Persona.archetype` 境界値**（0 / 80 / 81 文字）が TC-UT-VO-AG-007 で検証され、display_name / prompt_body と同水準に揃っている
- [ ] MSG-AG-001〜008（+ ダリオ追加予定の `path_invalid` MSG）の文言が静的文字列で照合される設計になっている
- [ ] 確定 A〜E（pre-validate / is_default count / 容量 10/20 / archive 冪等性 + 新インスタンス / NFC + strip 両 VO）すべてに証拠ケースが含まれる
- [ ] 脅威 T1（prompt_body 長さ）/ T2（不正 ProviderConfig）への有効性確認ケースが含まれ、サニタイズ・マスキングは別 feature 責務として明示申し送りされている
- [ ] 外部 I/O ゼロの主張が basic-design.md / requirements-analysis.md と整合している（`is_relative_to()` 検査は文字列上の構造照合であり、本 feature では実 ファイルシステム I/O は発生させない方針が確定 — base directory は Path 定数として扱う）
- [ ] frozen 不変性（TC-UT-AG-026）+ 構造的等価（TC-UT-AG-011）+ extra='forbid'（TC-UT-AG-027）が独立して検証されている
- [ ] empire / workflow の WeakValueDictionary レジストリ方式と整合した factory 設計になっている
- [ ] Schneier 申し送り（DB UNIQUE 二重防御 / `feature/persistence` でのマスキング規則適用 / `Persona.prompt_body` を threat-model.md §主要資産表に「機密性：中」追加 / `provider_kind` の MVP 実装範囲を AgentService 責務として明記）が次レビュー時に確認可能な形で test-design および設計書に記録されている
