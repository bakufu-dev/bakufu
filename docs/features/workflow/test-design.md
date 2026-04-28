# テスト設計書

<!-- feature: workflow -->
<!-- 配置先: docs/features/workflow/test-design.md -->
<!-- 対象範囲: REQ-WF-001〜007 / MSG-WF-001〜012 / 脅威 T1, T2, T3 / 受入基準 1〜12 / 詳細設計 確定 A〜G / DAG 不変条件 7 種 / SSRF G1〜G10 / シークレットマスキング -->

本 feature は domain 層の Aggregate Root（Workflow）と内部 Entity（Stage / Transition）と VO（CompletionPolicy / NotifyChannel）と例外（WorkflowInvariantViolation / StageInvariantViolation）に閉じる。HTTP API / CLI / UI の公開エントリポイントは持たないため、E2E は本 feature 範囲外（後続 feature/http-api / feature/workflow-presets / feature/workflow-ui で起票）。本 feature のテストは **ユニット主体 + 結合は Aggregate 内 module 連携の往復シナリオ + V モデル開発室レンダリング例の from_dict 構築**で構成する。

empire の test-design.md（`docs/features/empire/test-design.md`）と同じ規約を踏襲（外部 I/O ゼロ・factory に `_meta.synthetic = True` の `WeakValueDictionary` レジストリ）。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-WF-001 | `Workflow.__init__` / `model_validator(mode='after')` | TC-UT-WF-001 | ユニット | 正常系 | 1 |
| REQ-WF-001（name 境界） | `Workflow.name` バリデーション | TC-UT-WF-011 | ユニット | 境界値 | （MSG-WF-001） |
| REQ-WF-001（NFC 正規化） | `Workflow.name` の NFC + strip | TC-UT-WF-012 | ユニット | 正常系 | （確定 B / empire 流用） |
| REQ-WF-002 | `Workflow.add_stage` | TC-UT-WF-013, TC-UT-WF-014 | ユニット | 正常系/異常系 | 8 |
| REQ-WF-002（容量） | `add_stage` 31 件目 | TC-UT-WF-015 | ユニット | 境界値 | （確定 E） |
| REQ-WF-003 | `Workflow.add_transition` | TC-UT-WF-016, TC-UT-WF-017 | ユニット | 正常系/異常系 | 5 |
| REQ-WF-003（容量） | `add_transition` 61 本目 | TC-UT-WF-018 | ユニット | 境界値 | （確定 E） |
| REQ-WF-004 | `Workflow.remove_stage` | TC-UT-WF-009, TC-UT-WF-019 | ユニット | 正常系/異常系 | 9 |
| REQ-WF-004（連鎖削除） | `remove_stage` 関連 Transition の連鎖削除 | TC-UT-WF-020 | ユニット | 正常系 | — |
| REQ-WF-004（孤立化検知） | `remove_stage` 後に到達不能化する Stage を生む削除 | TC-UT-WF-021 | ユニット | 異常系 | — |
| REQ-WF-005-① | DAG 検査: entry_stage_id 存在 | TC-UT-WF-002 | ユニット | 異常系 | 2 |
| REQ-WF-005-② | DAG 検査: Transition 参照整合 | TC-UT-WF-022 | ユニット | 異常系 | （MSG-WF-009） |
| REQ-WF-005-③ | DAG 検査: 同一 (from, condition) Transition 重複 | TC-UT-WF-005 | ユニット | 異常系 | 5 |
| REQ-WF-005-④ | DAG 検査: BFS 到達可能性（孤立 Stage 禁止） | TC-UT-WF-003 | ユニット | 異常系 | 3 |
| REQ-WF-005-⑤ | DAG 検査: 終端 Stage 1 件以上（循環検出） | TC-UT-WF-004 | ユニット | 異常系 | 4 |
| REQ-WF-005-⑥ | DAG 検査: 全 Stage の `required_role` 非空（集約再確認） | TC-UT-WF-007 | ユニット | 異常系 | 7 |
| REQ-WF-005-⑦ | DAG 検査: 全 EXTERNAL_REVIEW Stage の `notify_channels` 非空（集約再確認） | TC-UT-WF-006a, TC-UT-WF-006b | ユニット | 異常系 | 6 |
| REQ-WF-005（BFS 安全性） | 循環 Workflow に対して BFS が無限ループしない（停止性） | TC-UT-WF-023 | ユニット | 異常系 | （確定 B） |
| REQ-WF-006 | `Workflow.from_dict` 正常系（V モデル開発室） | TC-IT-WF-001 | 結合 | 正常系 | 10 |
| REQ-WF-006（型違反） | `from_dict` で `Role` 名が enum 外 | TC-UT-WF-024 | ユニット | 異常系 | （MSG-WF-011 / T1） |
| REQ-WF-006（UUID 違反） | `from_dict` で `id` が UUID 形式違反 | TC-UT-WF-025 | ユニット | 異常系 | （T1） |
| REQ-WF-006（必須欠落） | `from_dict` で `entry_stage_id` 欠落 | TC-UT-WF-026 | ユニット | 異常系 | （T1） |
| REQ-WF-006（Stage index 識別） | `from_dict` 失敗時に問題の Stage index が detail に含まれる | TC-UT-WF-027 | ユニット | 異常系 | （確定: from_dict のデバッグ容易性） |
| REQ-WF-007-① | Stage 自身: `required_role` 空集合検査 | TC-UT-WF-028 | ユニット | 異常系 | 7 |
| REQ-WF-007-② | Stage 自身: `EXTERNAL_REVIEW` の `notify_channels` 必須検査 | TC-UT-WF-029 | ユニット | 異常系 | 6 |
| 確定 A（pre-validate） | `add_stage` 失敗時の元 Workflow 不変 | TC-UT-WF-008 | ユニット | 異常系 | 8 |
| 確定 A（pre-validate） | `add_transition` 失敗時の元 Workflow 不変 | TC-UT-WF-030 | ユニット | 異常系 | — |
| 確定 A（pre-validate） | `remove_stage` 失敗時の元 Workflow 不変 | TC-UT-WF-031 | ユニット | 異常系 | — |
| frozen 不変性 | `Workflow` / `Stage` / `Transition` への属性代入拒否 | TC-UT-WF-032 | ユニット | 異常系 | — |
| `extra='forbid'` | 未知フィールド拒否 | TC-UT-WF-033 | ユニット | 異常系 | （T1） |
| T3 / 確定 G3 | `http://discord.com/...`（HTTPS 強制違反）を拒否 | TC-UT-WF-034 | ユニット | 異常系 | — |
| T3 / 確定 G4 | `NotifyChannel.target` の host 偽装（`https://discord.com.evil.example/`）を拒否 | TC-UT-WF-035 | ユニット | 異常系 | — |
| T3 / 確定 G7 | `target='https://discord.com/'`（パス不足）を拒否 | TC-UT-WF-036 | ユニット | 異常系 | — |
| T3 / 確定 G1 | `target` 文字数 501 超過（DoS / メモリ攻撃防御） | TC-UT-WF-048 | ユニット | 境界値 | — |
| T3 / 確定 G5 | port 違反（`:80` / `:8443` / `:8080`）を拒否 | TC-UT-WF-049 | ユニット | 異常系 | — |
| T3 / 確定 G6 | userinfo 拒否（`https://attacker@discord.com/...` / `https://u:p@discord.com/...`） | TC-UT-WF-050 | ユニット | 異常系 | — |
| T3 / 確定 G7 | パス形式違反（id 非数字 / token 不正文字 / id 31 桁 / token 101 文字） | TC-UT-WF-051 | ユニット | 異常系 | — |
| T3 / 確定 G8 | query 付き（`?override=x`）を拒否 | TC-UT-WF-052 | ユニット | 異常系 | — |
| T3 / 確定 G9 | fragment 付き（`#frag`）を拒否 | TC-UT-WF-053 | ユニット | 異常系 | — |
| T3 / 確定 G10 | 大文字パス（`/API/WEBHOOKS/...`）を拒否 | TC-UT-WF-054 | ユニット | 異常系 | — |
| MVP kind 制約 | `kind='slack'` をコンストラクタで拒否 | TC-UT-WF-055 | ユニット | 異常系 | — |
| MVP kind 制約 | `kind='email'` をコンストラクタで拒否 | TC-UT-WF-056 | ユニット | 異常系 | — |
| シークレットマスキング | `NotifyChannel.model_dump(mode='json')` で token 部が `<REDACTED:DISCORD_WEBHOOK>` 化 | TC-UT-WF-057 | ユニット | 正常系 | — |
| シークレットマスキング | `Workflow.model_dump_json()` で全 NotifyChannel.target がマスキング済み | TC-UT-WF-058 | ユニット | 正常系 | — |
| シークレットマスキング | 例外 `message` / `detail` に webhook token が漏出しない | TC-UT-WF-059 | ユニット | 異常系 | — |
| 確定 F（helper 独立性） | `_validate_dag_reachability` / `_validate_dag_sink_exists` / `_validate_transition_determinism` / `_validate_transition_refs` / `_validate_required_role_non_empty` / `_validate_capacity` を直接 import して呼び出す | TC-UT-WF-060 | ユニット | 正常系/異常系 | — |
| T2（容量 DoS） | stages = 30 成功 / 31 件目で raise | TC-UT-WF-015 | ユニット | 境界値 | — |
| T2（容量 DoS） | transitions = 60 成功 / 61 本目で raise | TC-UT-WF-018 | ユニット | 境界値 | — |
| MSG-WF-001 | `[FAIL] Workflow name must be 1-80 characters (got {length})` | TC-UT-WF-037 | ユニット | 異常系 | （文言照合） |
| MSG-WF-002 | `[FAIL] entry_stage_id {id} not found in stages` | TC-UT-WF-038 | ユニット | 異常系 | 2 |
| MSG-WF-003 | `[FAIL] Unreachable stages from entry: {stage_ids}` | TC-UT-WF-039 | ユニット | 異常系 | 3 |
| MSG-WF-004 | `[FAIL] No sink stage; workflow has cycles only ...` | TC-UT-WF-040 | ユニット | 異常系 | 4 |
| MSG-WF-005 | `[FAIL] Duplicate transition: from_stage={from_id}, condition={condition}` | TC-UT-WF-041 | ユニット | 異常系 | 5 |
| MSG-WF-006 | `[FAIL] EXTERNAL_REVIEW stage {stage_id} must have at least one notify_channel` | TC-UT-WF-042 | ユニット | 異常系 | 6 |
| MSG-WF-007 | `[FAIL] Stage {stage_id} required_role must not be empty` | TC-UT-WF-043 | ユニット | 異常系 | 7 |
| MSG-WF-008 | `[FAIL] Stage id duplicate: {stage_id}` | TC-UT-WF-044 | ユニット | 異常系 | 8 |
| MSG-WF-009 | `[FAIL] Transition references unknown stage: from={from_id}, to={to_id}` | TC-UT-WF-045 | ユニット | 異常系 | （MSG 単独照合） |
| MSG-WF-010 | `[FAIL] Cannot remove entry stage: {stage_id}` | TC-UT-WF-046 | ユニット | 異常系 | 9 |
| MSG-WF-011 | `[FAIL] from_dict payload invalid: {detail}` | TC-UT-WF-047 | ユニット | 異常系 | （MSG 単独照合） |
| MSG-WF-012 | `[FAIL] Stage not found in workflow: stage_id={stage_id}` | TC-UT-WF-019 | ユニット | 異常系 | 9 |
| AC-11（lint/typecheck） | `pyright --strict` / `ruff check` | （CI ジョブ） | — | — | 11 |
| AC-12（カバレッジ） | `pytest --cov=bakufu.domain.workflow` | （CI ジョブ） | — | — | 12 |
| 結合シナリオ 1 | V モデル開発室 13 Stage / 15 Transition の `from_dict` 構築 | TC-IT-WF-001 | 結合 | 正常系 | 10 |
| 結合シナリオ 2 | `Workflow` + `Stage` + `Transition` + `WorkflowInvariantViolation` 往復 | TC-IT-WF-002 | 結合 | 正常系 | 1, 8, 5, 9 |

**マトリクス充足の証拠**:
- REQ-WF-001〜007 すべてに最低 1 件のテストケース
- DAG 不変条件 7 種すべてに独立した検証ケース（REQ-WF-005-①〜⑦）
- MSG-WF-001〜012 すべてに静的文字列照合（MSG-WF-012 は TC-UT-WF-019 で文言完全一致照合）
- 受入基準 1〜10 すべてに unit/integration ケース（11/12 は CI ジョブ）
- T1（不正 JSON）/ T2（DoS 容量）/ T3（SSRF/A10）すべてに有効性確認ケース
- 確定 A（pre-validate）/ B（BFS）/ C（終端検出）/ D（from_dict ペイロード）/ E（容量上限）/ F（helper 独立性）/ G1〜G10（NotifyChannel URL allow list 全規則）すべてに証拠ケース
- TC-UT-WF-006 を 006a（Stage 自身経路）/ 006b（集約検査経路）に分割し、二重防護の独立性を物理層で検証
- シークレットマスキング規則（webhook token の `<REDACTED:DISCORD_WEBHOOK>` 化）を 3 経路（`model_dump(mode='json')` / `model_dump_json()` / 例外 message/detail）でカバー
- MVP kind 制約（`'slack'` / `'email'` 拒否）をコンストラクタレベルで検証
- 孤児要件ゼロ

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **該当なし** | Workflow は domain 層単独で外部 I/O を持たない（HTTP / DB / ファイル / 時刻 / LLM / Discord いずれも未依存）。`NotifyChannel.target` の URL 文字列は **VO 内に保持される文字列**であって本 feature では通信しない（実際の Discord webhook 送信は `feature/discord-notifier` 責務） | — | — | **不要（外部 I/O ゼロ）** |
| `unicodedata.normalize('NFC', ...)` | name 正規化 | — | — | 不要（CPython 標準ライブラリ仕様で固定、empire と同方針） |
| `collections.deque` | BFS 到達可能性検査の作業キュー | — | — | 不要（標準ライブラリ） |

**根拠**:
- [`basic-design.md`](basic-design.md) §外部連携 で「該当なし — domain 層のみのため外部システムへの通信は発生しない」と凍結
- [`requirements-analysis.md`](requirements-analysis.md) §前提条件・制約 で「ネットワーク: 該当なし」と凍結
- T3（SSRF/A10）対策の URL allow list は **文字列バリデーション** であって通信ではない。実 webhook 送信時の URL 解釈・SSRF 防御は後続 `feature/discord-notifier` の責務として残し、本 feature では VO レベルの allow list 形式照合のみテストする

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `WorkflowFactory` | `Workflow`（valid デフォルト = 単一 Stage Workflow） | `True` |
| `VModelWorkflowFactory` | V モデル開発室レンダリング例の正規 13 Stage / 15 Transition 構成 | `True` |
| `StageFactory` | `Stage`（valid デフォルト = `kind=WORK` / `required_role={DEVELOPER}` / `notify_channels=[]`） | `True` |
| `ExternalReviewStageFactory` | `Stage`（`kind=EXTERNAL_REVIEW` + valid `notify_channels`） | `True` |
| `TransitionFactory` | `Transition`（valid デフォルト = `condition=APPROVED`） | `True` |
| `NotifyChannelFactory` | `NotifyChannel`（`kind='discord'` + valid Discord webhook URL） | `True` |
| `CompletionPolicyFactory` | `CompletionPolicy` | `True` |

`_meta.synthetic = True` は empire 流の **`tests/factories/workflow.py` モジュールスコープ `WeakValueDictionary[int, BaseModel]` レジストリ + `id(instance)` をキーに `is_synthetic()` で判定** 方式を踏襲する。frozen + `extra='forbid'` を尊重してインスタンスに属性追加は試みない。本番コード（`backend/src/bakufu/`）からは `tests/factories/workflow.py` を import しない（CI で `tests/` から `src/` への向きのみ許可）。

**V モデル開発室の正規ペイロード**:
詳細設計 §確定 D の payload 形式に従い、[`docs/design/domain-model/transactions.md`](../../design/domain-model/transactions.md) の V モデル開発室レンダリング例（13 Stage / 15 Transition）を **JSON ファイル**として `tests/fixtures/v_model_workflow.json` に固定する。これは外部 I/O fixture ではなく **設計書のレンダリング例の凍結** であり、characterization の対象外（実観測が不要、仕様書がソース）。

## E2E テストケース

**該当なし** — 理由:

- 本 feature は domain 層の純粋ライブラリで、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない
- 戦略ガイド §E2E対象の判断「バッチ処理・内部API・ライブラリなどエンドユーザー操作がない場合は結合テストで代替可」に従い、E2E は本 feature 範囲外
- 受入基準 10「V モデル開発室を `from_dict` で構築できる」は要件分析書で「TC-UT-WF-010（E2E 相当）」と但書付きで列挙されているが、本 feature ではこれは **結合テスト** の TC-IT-WF-001 として整理する（公開 I/F 経由ではないため）
- 後続 feature/workflow-presets（プリセット読み込み CLI）/ feature/workflow-ui（react-flow UI）/ feature/http-api（Workflow CRUD）が公開 I/F を実装した時点で E2E を起票する

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — domain 層のため公開 I/F なし | — | — |

## 結合テストケース

domain 層単独の本 feature では「結合」を **Aggregate 内 module 連携（Workflow + Stage + Transition + NotifyChannel + CompletionPolicy + 例外の往復シナリオ）+ V モデル開発室レンダリング例の bulk-import** と定義する。外部 LLM / Discord / GitHub / DB は本 feature では使わないためモック不要。

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-WF-001 | `Workflow.from_dict` + 全 Stage / Transition / NotifyChannel / CompletionPolicy | `tests/fixtures/v_model_workflow.json`（設計書 transactions.md レンダリング例の凍結、外部 I/O ではなく仕様書ソース） | factory 不要、JSON ファイル | 1) JSON 読み込み → `Workflow.from_dict(payload)` → 2) 13 Stage / 15 Transition / 全 EXTERNAL_REVIEW Stage の notify_channels 充足を確認 → 3) entry → 各 Stage の到達可能性確認 → 4) 終端 Stage 件数を確認 | DAG 7 種すべて通過、受入基準 10 達成、`Workflow` インスタンスが返る |
| TC-IT-WF-002 | `Workflow` + `Stage` + `Transition` + `WorkflowInvariantViolation` 往復 | factory（`WorkflowFactory` / `StageFactory` / `TransitionFactory`） | 単一 Stage の最小 Workflow | 1) `add_stage(new)` で 2 Stage に増やす → 2) `add_transition(new→entry)` で循環を作る試み → MSG-WF-004 で raise → 3) 元 Workflow が unchanged であることを確認（pre-validate）→ 4) 別の `add_transition(entry→new)` で正常追加 → 5) `remove_stage(new)` で 1 Stage に戻す → Transition も連鎖削除されることを確認 | 受入基準 1, 5, 8, 9 を一連で確認、Pydantic frozen 不変性を経路全体で確認 |
| TC-IT-WF-003 | `Workflow.from_dict` + 不正 payload バリエーション（T1 防御の集約検証） | factory + 改変版 v_model JSON | V モデル JSON を base に Role 名 enum 外 / UUID 形式違反 / entry 欠落 / 重複 stage_id を埋め込み | 各バリエーションに対して `from_dict` が `WorkflowInvariantViolation` または `pydantic.ValidationError` を raise、detail に問題箇所（Stage index 等）を含む | T1 攻撃面を多角的にカバー |

**注**: 本 feature では結合テストも `tests/integration/test_workflow.py` ではなく `tests/domain/test_workflow.py` 内の「往復シナリオ」「from_dict 結合」セクションとして実装してよい（empire と同方針）。

## ユニットテストケース

`tests/factories/workflow.py` の factory 経由で入力を生成する。raw fixture は本 feature では外部 I/O ゼロのため存在しない。設計書凍結例（V モデル）は JSON 固定。

### Workflow Aggregate Root（DAG 不変条件含む）

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---------|-----|------|---------------|---------|
| TC-UT-WF-001 | `Workflow(stages=[1件], transitions=[], entry_stage_id=...)` | 正常系 | 単一 Stage で entry == 終端 | 構築成功、`stages` 1 件、`transitions` 0 件 |
| TC-UT-WF-002 | `Workflow(entry_stage_id=未登録)` | 異常系 | entry_stage_id が `stages` に存在しない | `WorkflowInvariantViolation(kind='entry_not_in_stages')`、MSG-WF-002 |
| TC-UT-WF-003 | 孤立 Stage が存在 | 異常系 | 3 Stage、entry → S1 のみ Transition、S2 が孤立 | `WorkflowInvariantViolation(kind='unreachable_stage')`、MSG-WF-003、detail に S2.id を含む |
| TC-UT-WF-004 | 終端 Stage 0 件（循環） | 異常系 | 3 Stage 全てに外向き Transition があり閉路を構成 | `WorkflowInvariantViolation(kind='no_sink_stage')`、MSG-WF-004 |
| TC-UT-WF-005 | 同一 (from, condition) 重複 | 異常系 | 同一 from_stage_id × condition=APPROVED の Transition を 2 本 | `WorkflowInvariantViolation(kind='transition_duplicate')`、MSG-WF-005 |
| TC-UT-WF-006a | EXTERNAL_REVIEW で notify_channels 空（**Stage 自身の検査経路**） | 異常系 | `Stage(kind=EXTERNAL_REVIEW, notify_channels=[])` を**単独で**構築 | Stage コンストラクタの `model_validator(mode='after')` が `StageInvariantViolation(kind='missing_notify')` を raise、`message` が MSG-WF-006 と完全一致。Workflow を経由する前に raise されることを確認 |
| TC-UT-WF-006b | EXTERNAL_REVIEW で notify_channels 空（**Workflow 集約検査経路**、二重防護の独立検証） | 異常系 | Workflow 内部の集約検査関数 `_validate_external_review_notify(stages)` を直接呼ぶ。`stages=[Stage(kind=EXTERNAL_REVIEW, notify_channels=[])]` を擬似的に渡す（Stage 自身の検査をバイパスして集約検査が独立に動くことを確認）。実装は `notify_channels=[]` の Stage を構築できないため、テストでは monkeypatch で Stage の `model_validator` を一時的に no-op 化し、それ以外を経由させる | 集約検査関数が `WorkflowInvariantViolation(kind='missing_notify_aggregate')` を raise、`message` が MSG-WF-006 と完全一致。Stage 自身の検査が機能しなくても Workflow 集約検査が二重防護として動くことを担保 |
| TC-UT-WF-007 | required_role 空集合 | 異常系 | Stage の required_role = frozenset() | `StageInvariantViolation(kind='empty_required_role')`、MSG-WF-007 |
| TC-UT-WF-011 | name 境界値 | 境界値 | name 0 / 1 / 80 / 81 文字、空白のみ、NFC 分解形混入 | 0/81/空白のみは MSG-WF-001 で raise、1/80 は成功、NFC 正規化 + strip 後に判定（empire 流） |
| TC-UT-WF-012 | name NFC + strip 正規化 | 正常系 | 合成形「テスト」/分解形「テスト」/前後空白あり | `Workflow.name` が NFC + strip 後の文字列で保持される |
| TC-UT-WF-022 | Transition 参照が Stage 不在 | 異常系 | Transition の to_stage_id が stages に存在しない | `WorkflowInvariantViolation(kind='transition_ref_invalid')`、MSG-WF-009 |
| TC-UT-WF-023 | 循環 Workflow に対する BFS 停止性 | 異常系 | A → B → C → A の循環 + entry=A を構築試行 | BFS が無限ループせず O(V+E) 内に終端検出失敗を返す（確定 B、`collections.deque` 安全性） |

### Stage Entity 自身の不変条件（二重防護）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-WF-028 | `Stage(required_role=frozenset())` | 異常系 | required_role 空集合 | `StageInvariantViolation(kind='empty_required_role')`、Workflow 構築前に検出 |
| TC-UT-WF-029 | `Stage(kind=EXTERNAL_REVIEW, notify_channels=[])` | 異常系 | EXTERNAL_REVIEW で notify_channels 空 | `StageInvariantViolation(kind='missing_notify')` |

### add_stage / add_transition / remove_stage（pre-validate 方式 確定 A）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-WF-013 | `add_stage(new_stage)` | 正常系 | 既存 Workflow に新 Stage 追加（必要な Transition も別途追加） | 新 Workflow の `stages` に追加、元 Workflow は変化なし |
| TC-UT-WF-014 | `add_stage` で stage_id 重複 | 異常系 | 既存 stage_id の Stage を追加 | `WorkflowInvariantViolation(kind='stage_duplicate' or similar)`、MSG-WF-008 |
| TC-UT-WF-015 | `add_stage` 容量上限 | 境界値 | 30 件成功、31 件目で raise | 30 まで成功、31 で `WorkflowInvariantViolation(kind='capacity_exceeded')` |
| TC-UT-WF-016 | `add_transition(new_transition)` | 正常系 | 既存 Workflow に新 Transition 追加 | 新 Workflow の `transitions` に追加 |
| TC-UT-WF-017 | `add_transition` 参照不正 | 異常系 | from / to が stages 不在 | MSG-WF-009 |
| TC-UT-WF-018 | `add_transition` 容量上限 | 境界値 | 60 本成功、61 本目で raise | 60 まで成功、61 で raise |
| TC-UT-WF-009 | `remove_stage(entry_stage_id)` | 異常系 | entry を削除しようとする | `WorkflowInvariantViolation(kind='cannot_remove_entry')`、MSG-WF-010 |
| TC-UT-WF-019 | `remove_stage(unknown_id)` | 異常系 | stages に存在しない id を指定 | `WorkflowInvariantViolation(kind='stage_not_found')` を raise、`message` が `[FAIL] Stage not found in workflow: stage_id={stage_id}`（MSG-WF-012）と完全一致、元 Workflow は変化なし |
| TC-UT-WF-020 | `remove_stage` 連鎖削除 | 正常系 | 削除対象 Stage を from / to に持つ Transition も連鎖削除されることを確認 | 新 Workflow の `transitions` 件数が減る、関連のないものは残る |
| TC-UT-WF-021 | `remove_stage` 後に到達不能化 | 異常系 | 削除すると途中の Stage が孤立する構成 | `WorkflowInvariantViolation(kind='unreachable_stage')`、元 Workflow 不変 |
| TC-UT-WF-008 | `add_stage` 失敗時の元 Workflow 不変 | 異常系 | 重複 stage_id で失敗 | 失敗後、元 Workflow の `stages` 件数・内容完全一致（pre-validate） |
| TC-UT-WF-030 | `add_transition` 失敗時の元 Workflow 不変 | 異常系 | 参照不正で失敗 | 元 Workflow の `transitions` 件数・内容完全一致 |
| TC-UT-WF-031 | `remove_stage` 失敗時の元 Workflow 不変 | 異常系 | 到達不能化させる削除で失敗 | 元 Workflow が完全に変化なし |

### from_dict bulk-import（T1 防御の境界線）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-WF-024 | `from_dict` で Role 名 enum 外 | 異常系 | `required_role: ["UNKNOWN_ROLE"]` | `pydantic.ValidationError` または MSG-WF-011、detail に問題の Stage index と field 名 |
| TC-UT-WF-025 | `from_dict` で UUID 形式違反 | 異常系 | `id: "not-a-uuid"` | `pydantic.ValidationError`、detail に id 形式違反 |
| TC-UT-WF-026 | `from_dict` で entry_stage_id 欠落 | 異常系 | payload に entry_stage_id キーなし | `pydantic.ValidationError`、必須欠落 |
| TC-UT-WF-027 | `from_dict` 失敗時の Stage index 識別 | 異常系 | 3 件目の Stage に required_role 空集合を仕込む | 例外 detail に `stage_index=2` を含む（確定: from_dict のデバッグ容易性、設計書 §設計判断の補足） |

### frozen / extra='forbid' / SSRF allow list（防御の物理層）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-WF-032 | frozen 不変性 | 異常系 | `workflow.name = 'X'` / `stage.kind = ...` / `transition.from_stage_id = ...` 直接代入 | `pydantic.ValidationError`（frozen instance への代入拒否）、Workflow / Stage / Transition / NotifyChannel / CompletionPolicy 全てで確認 |
| TC-UT-WF-033 | `extra='forbid'` 未知フィールド拒否 | 異常系 | `Workflow.model_validate({...,'unknown': 'x'})` | `pydantic.ValidationError`、`extra` 違反（T1 防御） |
| TC-UT-WF-034 | NotifyChannel allow list G3（スキーム強制）| 異常系 | `target='http://discord.com/api/webhooks/123456/abc-DEF_xyz'`（HTTP） | `pydantic.ValidationError`、HTTPS 強制（T3 / A10）、detail に G3 違反 |
| TC-UT-WF-035 | NotifyChannel allow list G4（host 偽装拒否） | 異常系 | `target='https://discord.com.evil.example/api/webhooks/123/abc'` / `target='https://evil-discord.com/api/webhooks/...'` / `target='https://api.discord.com/api/webhooks/...'`（部分一致） | `pydantic.ValidationError`、`hostname == 'discord.com'` 完全一致照合（T3 / A10）、detail に G4 違反 |
| TC-UT-WF-036 | NotifyChannel allow list G7（パス不足） | 異常系 | `target='https://discord.com/'`（パス空）/ `target='https://discord.com/api/webhooks/'`（id/token 欠落） | `pydantic.ValidationError`、`/api/webhooks/{id}/{token}` 形式照合 |

### NotifyChannel URL allow list G1〜G10 拡張（SSRF 防衛線の完全網羅）

`detailed-design.md` §確定 G の G1〜G10 を**全て独立 unit ケース**で検証する。1 つでも抜けると Schneier が指摘した SSRF/A10 の防衛線に穴が空く。

| テストID | 規則 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-WF-048 | G1（文字数上限） | 境界値 | `target=` 空文字列 / 500 文字（valid 形式に paddings は不可、ただし長すぎる token 部で 500 文字構成）/ 501 文字 | 0 文字 / 501 文字は `pydantic.ValidationError`、500 文字（valid 形式の最大）は成功、detail に G1 違反 |
| TC-UT-WF-049 | G5（ポート制約） | 異常系 | `target='https://discord.com:80/api/webhooks/123/abc'` / `:8443` / `:8080` / `:443` | `:80` / `:8443` / `:8080` は `pydantic.ValidationError`、`:443`（明示）と省略は成功、detail に G5 違反 |
| TC-UT-WF-050 | G6（userinfo 拒否） | 異常系 | `target='https://attacker@discord.com/api/webhooks/123/abc'`（username のみ）/ `target='https://user:pass@discord.com/api/webhooks/123/abc'`（user:password）/ `target='https://%40discord.com@discord.com/api/webhooks/...'`（URL エンコード偽装） | 全て `pydantic.ValidationError`、`parsed.username is None and parsed.password is None` 検査、detail に G6 違反。**RFC 3986 userinfo 経由の host 偽装攻撃**を物理層で塞ぐ |
| TC-UT-WF-051 | G7（パス正規表現完全一致） | 異常系 | `target='https://discord.com/api/webhooks/abc/def'`（id 非数字）/ `'.../webhooks/123/!@#'`（token 不正文字）/ `'.../webhooks/' + '0'*31 + '/abc'`（id 31 桁、上限超過）/ `'.../webhooks/123/' + 'a'*101`（token 101 文字、上限超過）/ `'.../api/webhooks/123/abc/'`（末尾スラッシュ）/ `'.../api/webhooks/123/abc/extra'`（余剰 segment） | 全て `pydantic.ValidationError`、`^/api/webhooks/(?P<id>[0-9]{1,30})/(?P<token>[A-Za-z0-9_\-]{1,100})$` 正規表現 fullmatch、detail に G7 違反 |
| TC-UT-WF-052 | G8（query 禁止） | 異常系 | `target='https://discord.com/api/webhooks/123/abc?override=x'` / `'?'`（空 query） | `pydantic.ValidationError`、`parsed.query == ''` 検査、`?override` 等での挙動変更経路を塞ぐ、detail に G8 違反 |
| TC-UT-WF-053 | G9（fragment 禁止） | 異常系 | `target='https://discord.com/api/webhooks/123/abc#frag'` / `'#'`（空 fragment） | `pydantic.ValidationError`、`parsed.fragment == ''` 検査、ログ・監査での扱いを単純化、detail に G9 違反 |
| TC-UT-WF-054 | G10（パス大文字小文字） | 異常系 | `target='https://discord.com/API/WEBHOOKS/123/abc'`（大文字 API）/ `'.../Api/Webhooks/123/abc'`（混合）/ `'https://DISCORD.COM/api/webhooks/123/abc'`（host 大文字、urlparse 正規化で小文字化されるため**成功**） | パス大文字は `pydantic.ValidationError`、host 大文字は urlparse の hostname 小文字化で**成功**することを別途確認、G10 の挙動仕様を凍結 |

### NotifyChannel kind 制約（MVP は discord のみ）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-WF-055 | `NotifyChannel(kind='slack', target=...)` | 異常系 | `kind='slack'`、target は任意 | `pydantic.ValidationError`、`kind` Literal['discord'] 違反、detail に kind 制約違反、Phase 2 申し送り（slack 解禁時に同等の確定 G が必要）|
| TC-UT-WF-056 | `NotifyChannel(kind='email', target=...)` | 異常系 | `kind='email'` | 同上、`pydantic.ValidationError` |

### NotifyChannel シークレットマスキング（webhook token 漏出防止）

`detailed-design.md` §確定 G `target のシークレット扱い` で凍結された 6 永続化先のうち、本 feature 範囲（VO シリアライズ + 例外文言）を unit でカバー。残り（Outbox / audit_log / Conversation / 構造化ログ）は `feature/persistence` / `feature/discord-notifier` 責務として申し送る。

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-WF-057 | `NotifyChannel.model_dump(mode='json')` の field_serializer | 正常系 | `target='https://discord.com/api/webhooks/123456789/SuperSecretToken_-abc'` | 出力 dict の `target` が `'https://discord.com/api/webhooks/123456789/<REDACTED:DISCORD_WEBHOOK>'`（id 部は識別性のため残す、token 部のみ伏字）、`mode='python'`（デフォルト）では raw target を返すことも別途確認 |
| TC-UT-WF-058 | `Workflow.model_dump_json()` 経由の全 NotifyChannel マスキング | 正常系 | V モデル開発室レンダリング例の Workflow（複数 EXTERNAL_REVIEW Stage に webhook URL 設定済み） | JSON 出力中に `SuperSecretToken_-abc` 等の token 部が**1 件も含まれず**、すべて `<REDACTED:DISCORD_WEBHOOK>` で置換されている（正規表現 `https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_\-]{20,}` で出力をスキャンしてヒットゼロ確認）|
| TC-UT-WF-059 | 例外 `message` / `detail` のマスキング | 異常系 | 何らかの不正状態で `WorkflowInvariantViolation` を raise する際、`detail` に webhook URL を含む文脈情報を持つケース（例: NotifyChannel の target を含む Stage 情報を detail に格納） | 例外 `message` および `repr(detail)` に webhook token 部が**含まれない**（マスキング済み）、id 部は残ってよい。Schneier 指摘 §確定 G `target のシークレット扱い` 6 行目（例外 message / detail 永続化先）に直接対応 |

### 集約検査 helper の独立性（確定 F、二重防護のテスタビリティ）

`detailed-design.md` §確定 F で凍結された 7 helper（`_validate_dag_reachability` / `_validate_dag_sink_exists` / `_validate_transition_determinism` / `_validate_transition_refs` / `_validate_external_review_notify` / `_validate_required_role_non_empty` / `_validate_capacity`）はモジュールレベル private 関数として実装される。本ケースで **Workflow 本体を構築せず** helper を直接 import して呼び出すことで、Stage 自身の `model_validator` とコード非共有である物理保証を担保する。

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-WF-060 | 7 helper 関数の独立呼び出し | 正常系/異常系 | `from bakufu.domain.workflow import _validate_dag_reachability, _validate_dag_sink_exists, _validate_transition_determinism, _validate_transition_refs, _validate_external_review_notify, _validate_required_role_non_empty, _validate_capacity` で直接 import、各々に valid / invalid な stages / transitions / entry_stage_id を渡す | 正常入力では None 返却（または例外なし）、不正入力では各 helper が**それぞれ対応する `WorkflowInvariantViolation(kind=...)` を raise**（kind は §確定 F 表に従う）。Workflow 本体を構築しないため Stage 自身の `model_validator` を経由せず、helper のロジックを単独で検査可能。TC-UT-WF-006b の前提も成立する |

### MSG 文言照合

| テストID | MSG ID | 入力 | 期待結果 |
|---------|--------|------|---------|
| TC-UT-WF-037 | MSG-WF-001 | name='a'*81 | `[FAIL] Workflow name must be 1-80 characters (got 81)` 完全一致 |
| TC-UT-WF-038 | MSG-WF-002 | entry_stage_id 未登録 | `[FAIL] entry_stage_id <id> not found in stages` 形式 |
| TC-UT-WF-039 | MSG-WF-003 | 孤立 Stage 1 件 | `[FAIL] Unreachable stages from entry: [<id>]` 形式 |
| TC-UT-WF-040 | MSG-WF-004 | 循環のみ | `[FAIL] No sink stage; workflow has cycles only (entry=<id>)` 形式 |
| TC-UT-WF-041 | MSG-WF-005 | (from, APPROVED) 重複 | `[FAIL] Duplicate transition: from_stage=<id>, condition=APPROVED` 形式 |
| TC-UT-WF-042 | MSG-WF-006 | EXTERNAL_REVIEW で notify 空 | `[FAIL] EXTERNAL_REVIEW stage <id> must have at least one notify_channel` 形式 |
| TC-UT-WF-043 | MSG-WF-007 | required_role 空集合 | `[FAIL] Stage <id> required_role must not be empty` 形式 |
| TC-UT-WF-044 | MSG-WF-008 | add_stage で重複 | `[FAIL] Stage id duplicate: <id>` 形式 |
| TC-UT-WF-045 | MSG-WF-009 | Transition 参照不正 | `[FAIL] Transition references unknown stage: from=<id>, to=<id>` 形式 |
| TC-UT-WF-046 | MSG-WF-010 | entry 削除試行 | `[FAIL] Cannot remove entry stage: <id>` 形式 |
| TC-UT-WF-047 | MSG-WF-011 | from_dict で invalid payload | `[FAIL] from_dict payload invalid: <detail>` プレフィックス |

### Value Object 単独テスト（参考）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-VO-WF-001 | `CompletionPolicy(kind, description)` | 正常系 | 全 Literal 値 | 成功 |
| TC-UT-VO-WF-002 | `CompletionPolicy` 不正 kind | 異常系 | `kind='unknown'` | `pydantic.ValidationError` |
| TC-UT-VO-WF-003 | `NotifyChannel(kind='discord', target=valid)` | 正常系 | valid Discord webhook URL | 成功 |
| TC-UT-VO-WF-004 | `Transition` 構造的等価 | 正常系 | 全属性同値の 2 インスタンス | `==` True、`hash()` 一致 |

## カバレッジ基準

- REQ-WF-001 〜 007 の各要件が**最低 1 件**のテストケースで検証されている（マトリクス参照）
- DAG 不変条件 7 種それぞれが独立した unit ケースで検証されている（REQ-WF-005-①〜⑦）
- MSG-WF-001 〜 012 の各文言が**静的文字列で照合**されている（TC-UT-WF-019, 037 〜 047）
- 受入基準 1 〜 10 の各々が**最低 1 件のユニット/結合ケース**で検証されている（E2E 不在のため戦略ガイドの「結合代替可」に従う）
- 受入基準 11（pyright/ruff）/ 12（カバレッジ）は CI ジョブで担保
- T1（不正 JSON）/ T2（DoS 容量）/ T3（SSRF/A10）の各脅威に対する対策が**最低 1 件のテストケース**で有効性を確認されている
- 確定 A（pre-validate）/ B（BFS）/ C（終端検出）/ D（from_dict ペイロード）/ E（容量上限）/ F（helper 独立性）/ G（NotifyChannel URL allow list G1〜G10 + シークレットマスキング + kind 制約）に対する証拠ケースが各々最低 1 件
- 二重防護の独立性（Stage 自身経路 / Workflow 集約経路）が TC-UT-WF-006a / 006b で**コード非共有**を物理層で検証
- シークレットマスキング規則が **3 シリアライズ経路**（`model_dump(mode='json')` / `model_dump_json()` / 例外 message・detail）で検証
- C0 目標: `domain/workflow.py` で **95% 以上**（domain 層基準、要件分析書 §非機能要求準拠）

## 人間が動作確認できるタイミング

本 feature は domain 層単独のため、人間が UI / CLI で触れるタイミングは無い。レビュワー / オーナーは以下で動作確認する。

- CI 統合後: `gh pr checks` で 7 ジョブ緑（lint / typecheck / test-backend / audit / fmt / commit-msg / no-ai-footer）
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/domain/test_workflow.py -v` → 全テスト緑
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.domain.workflow --cov-report=term-missing tests/domain/test_workflow.py` → `domain/workflow.py` 95% 以上
- V モデル開発室レンダリング例の構築実観測: `uv run python -c "import json; from bakufu.domain.workflow import Workflow; wf = Workflow.from_dict(json.load(open('backend/tests/fixtures/v_model_workflow.json'))); print(len(wf.stages), len(wf.transitions))"` で `13 15` が出力されることを目視（実装担当が PR 説明欄に貼り付け）
- DAG 不変条件違反の実観測: 不正 payload で from_dict を呼んで MSG-WF-001〜012 が出ることを目視
- シークレットマスキング実観測: `uv run python -c "from bakufu.domain.workflow import NotifyChannel; nc = NotifyChannel(kind='discord', target='https://discord.com/api/webhooks/123/SuperSecretToken_-abc'); import json; print(nc.model_dump_json())"` で出力 JSON に `SuperSecretToken_-abc` が含まれず `<REDACTED:DISCORD_WEBHOOK>` に置換されていることを目視

後段で feature/workflow-presets（プリセット読み込み CLI）/ feature/http-api（Workflow CRUD）が完成したら、本 feature の Workflow を経由して `bakufu admin workflow load` や `curl` 経由の手動シナリオで E2E 観測可能になる。

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      __init__.py
      workflow.py              # WorkflowFactory / VModelWorkflowFactory / StageFactory / 
                               # ExternalReviewStageFactory / TransitionFactory / 
                               # NotifyChannelFactory / CompletionPolicyFactory
                               # （empire 流の WeakValueDictionary レジストリ + is_synthetic()）
    fixtures/
      v_model_workflow.json    # 設計書 transactions.md レンダリング例の凍結（外部 I/O ではなく仕様書ソース）
    domain/
      __init__.py
      test_workflow.py         # TC-UT-WF-001〜060 + TC-IT-WF-001〜003（往復シナリオ section + from_dict integration section + SSRF G1〜G10 section + マスキング section + helper 独立性 section）
```

**配置の根拠**:
- empire と同方針: domain 層単独・外部 I/O ゼロのため `tests/integration/` は作らない
- `v_model_workflow.json` は characterization fixture ではなく **設計書のレンダリング例の凍結 JSON**。`tests/fixtures/characterization/` 配下ではなく `tests/fixtures/` 直下に置く（実観測ではないため）
- characterization / raw / schema は本 feature では生成しない（外部 I/O ゼロ）

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| （N/A） | 該当なし — 外部 I/O ゼロのため characterization 不要 | — | 後続 feature/persistence（DB 永続化）/ feature/http-api（HTTP 境界の payload schema）/ feature/discord-notifier（実 webhook 送信）/ feature/workflow-presets（プリセット JSON 読み込み）が起票時に Workflow 起点の characterization が発生する見込み |

**Schneier から前回申し送りされた件への対応状況**（empire レビューより）:

- TOCTOU race: 本 PR では対象外（`feature/persistence` 責務）。Workflow には Empire のシングルトン制約に相当するものはないため、本 feature では発生しない
- Unicode 不可視文字 / 同形異字符: 本 PR では対象外（`feature/http-api` の入力境界責務）。`name` の機密レベルは低のため認可バイパス経路ではないが、後段で抜けないこと
- **本 feature 固有の申し送り**: NotifyChannel.target の URL allow list（G1〜G10）は **形式バリデーション** のみ。実 webhook 送信時の SSRF 防御（DNS rebinding / IPv4 mapped IPv6 / URL リダイレクト追跡時の再検査）は `feature/discord-notifier` 責務として残す（detailed-design.md §確定 G `Phase 2 で再検証が必要な項目`）
- **シークレットマスキング 6 経路の責務分離**: detailed-design.md §確定 G `target のシークレット扱い` で凍結された 6 永続化先のうち、本 feature でカバーするのは **(1) `Workflow` / `Stage` / `NotifyChannel` の `model_dump(mode='json')` および `model_dump_json()` 出力** と **(2) 例外 `message` / `detail`** の 2 経路（TC-UT-WF-057〜059）。残り 4 経路（Outbox `payload_json` / `audit_log.args_json` / Conversation system message / 構造化ログ stdout・file）は `feature/persistence` / `feature/discord-notifier` / `feature/audit-log` の責務として申し送り、`storage.md` §シークレットマスキング規則 への正規表現追補 PR を起こすことが detailed-design.md で凍結されている

## レビュー観点（テスト設計レビュー時）

- [ ] DAG 不変条件 7 種すべてが REQ-WF-005-①〜⑦ として独立した unit ケースで検証されている
- [ ] MSG-WF-001〜012 の文言が静的文字列で照合される設計になっている（MSG-WF-012 = stage_not_found 含む）
- [ ] 確定 A〜G（pre-validate / BFS / 終端検出 / from_dict ペイロード / 容量 30/60 / helper 独立性 / NotifyChannel URL allow list）すべてに証拠ケースが含まれる
- [ ] 脅威 T1（不正 JSON）/ T2（容量 DoS）/ T3（SSRF/A10）への有効性確認ケースが含まれる
- [ ] 外部 I/O ゼロの主張が basic-design.md / requirements-analysis.md と整合している
- [ ] BFS の循環下停止性（TC-UT-WF-023）が独立したケースで検証されている
- [ ] Stage 自身の不変条件（required_role 非空 / EXTERNAL_REVIEW notify_channels）と Workflow 集約検査の両方でテストが用意されている（二重防護、TC-UT-WF-006a / 006b）
- [ ] 確定 F の 7 helper を直接 import する独立性検証（TC-UT-WF-060）が含まれ、Stage 自身経路と集約検査経路のコード非共有を物理層で担保している
- [ ] **NotifyChannel URL allow list G1〜G10 全項目**が独立した unit ケース（TC-UT-WF-034〜036, 048〜054）で検証されている。特に G6（userinfo `https://attacker@discord.com/...` 拒否）/ G8（query 拒否）/ G9（fragment 拒否）/ G10（パス大文字区別）に抜けがない
- [ ] **シークレットマスキング**が 3 経路（`model_dump(mode='json')` / `model_dump_json()` / 例外 message・detail）で検証され、token 部が `<REDACTED:DISCORD_WEBHOOK>` に置換され id 部のみ残る規則が固定されている
- [ ] **MVP kind 制約**（`'slack'` / `'email'` のコンストラクタ拒否）が TC-UT-WF-055 / 056 で検証されている
- [ ] `from_dict` のデバッグ容易性（Stage index を detail に含める）が TC-UT-WF-027 で検証されている
- [ ] V モデル開発室レンダリング例（13 Stage / 15 Transition）が結合テストで構築できることを TC-IT-WF-001 で検証している
- [ ] empire の WeakValueDictionary レジストリ方式と整合した factory 設計になっている
