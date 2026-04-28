# 業務仕様書（feature-spec）— Directive

> feature: `directive`（業務概念単位）
> sub-features: [`domain/`](domain/) | [`repository/`](repository/) | http-api（将来）| ui（将来）
> 関連 Issue: [#24 feat(directive): Directive Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/24) / [#34 feat(directive-repository): Directive SQLite Repository (M2)](https://github.com/bakufu-dev/bakufu/issues/34)
> 凍結済み設計: [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Directive / [`docs/design/domain-model/value-objects.md`](../../design/domain-model/value-objects.md) §ID 型一覧（DirectiveId は既存）/ [`docs/design/domain-model/storage.md`](../../design/domain-model/storage.md) §シークレットマスキング規則

## 本書の役割

本書は **Directive という業務概念全体の業務仕様** を凍結する。bakufu 全体の要求分析（[`docs/analysis/`](../../analysis/)）を Directive という業務概念で具体化し、ペルソナ（個人開発者 CEO）から見て **観察可能な業務ふるまい** を実装レイヤー（domain / repository / http-api / ui）に依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / 将来の http-api / ui）は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない（本書の更新は別 PR で先行する）。

**書くこと**:
- ペルソナ（CEO）が Directive という業務概念で達成できるようになる行為（ユースケース）
- 業務ルール（不変条件・テキスト制約・Task 紐付け・webhook マスキング・永続性等、すべての sub-feature を貫く凍結）
- E2E で観察可能な事象としての受入基準（業務概念全体）
- sub-feature 間の責務分離マップ（実装レイヤー対応）

**書かないこと**（sub-feature の設計書へ追い出す）:
- 採用技術スタック（Pydantic / SQLAlchemy 等） → sub-feature の `basic-design.md`
- 実装方式の比較・選定議論（pre-validate / TypeDecorator 等） → sub-feature の `detailed-design.md`
- 内部 API 形・メソッド名・属性名・型 → sub-feature の `basic-design.md` / `detailed-design.md`
- sub-feature 内のテスト戦略（IT / UT） → sub-feature の `test-design.md`（E2E のみ親 [`system-test-design.md`](system-test-design.md) で扱う）
- pyright / ruff / カバレッジ等の CI 品質基準 → §10 開発者品質基準 / sub-feature の `test-design.md §カバレッジ基準`

## 1. この feature の位置付け

bakufu インスタンスで CEO が発行する指令「Directive」は、MVP 核心ユースケース「CEO directive → Task 起票 → Vモデル工程進行 → 外部レビューで人間が承認 → DONE」の**起点**を担う。Directive は `$` プレフィックスから始まるテキストと委譲先 Room を持ち、Directive から Task が生成される。

Directive の業務的なライフサイクルは複数の実装レイヤーを跨ぐ:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| domain | [`domain/`](domain/) | Directive のテキスト制約（1〜10000文字）・Task 紐付けの一意遷移・webhook auto-mask を Aggregate 内で保証 |
| repository | [`repository/`](repository/) | Directive の状態を再起動跨ぎで保持（永続化）、`directives.text` の secret マスキングを担保 |
| http-api | (将来) | UI / 外部クライアントから Directive を発行・取得する経路 |
| ui | (将来) | CEO が Directive を発行するチャット画面 |

本書はこれら全レイヤーを貫く **業務概念単位の凍結文書** であり、各 sub-feature は本書を引用して実装契約を凍結する。

## 2. 人間の要求

> Issue #24（M1 domain）:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の **5 番目の Aggregate** として **Directive Aggregate Root** を実装する。Directive は CEO（リポジトリオーナー）が発行する指令で、`$` プレフィックスから始まるテキストと委譲先 Room を持つ。Directive から Task が生成され、MVP の核心ユースケース「CEO directive → Task 起票 → 各 Stage を Agent が処理 → 外部レビューで人間が承認/差し戻し → DONE」の**起点**を担う。

> Issue #34（M2 repository）:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の後続 Repository PR。**Directive Aggregate** の SQLite 永続化を実装する。`directives.text` の `MaskedText` 実適用、および `find_by_room` メソッド（4-method Protocol）が核心。

## 3. 背景・痛点

### 現状の痛点

1. M1 ドメイン骨格 4 兄弟（empire / workflow / agent / room）が完走したが、**CEO directive の起点 Aggregate がないため Task 起票経路が宙に浮いている**
2. M1 後段の `task` Issue は `directive_id` を介して Directive を参照する設計。Directive がないと Task 構築の参照整合性検査が成立しない
3. UI の MVP は「Room チャネルで `$` プレフィックスのメッセージを送信 → directive 起票 → Task 生成」を中核ユースケースに据える。Directive の attribute / 不変条件が決まっていないと UI 側の実装が着手できない

### 解決されれば変わること

- `task` Issue が Directive 参照を前提に実装可能になる（`directive_id` 必須属性が確定する）
- empire / workflow / agent / room の確立済みパターンを **5 例目**として揃え、後続 task の実装パターンを完全固定する
- Directive の状態がアプリ再起動を跨いで保持される（CEO は永続化を意識しない）
- `directives.text` に CEO が入力した secret が DB に raw 保存されない

### ビジネス価値

- bakufu の核心思想「CEO directive → Vモデル工程進行 → 外部レビューで人間が承認」のうち最初の **CEO directive 起点** を Aggregate 単位で表現する
- 「`$` プレフィックスで CEO 入力を識別する」ai-team 由来の運用慣習を Aggregate 内で正規化し、UI / API レイヤと application 層の責務を明確に分離する

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|-----------|------|---------|---------------|
| 個人開発者 CEO（堀川さん想定） | bakufu インスタンスのオーナー、Directive の発行者 | 直接（将来の UI 経由）/ 間接（domain・repository sub-feature では application 層経由） | 1 行の指令で Vモデル開発フローを起動する。Room チャネルで `$ ブログ分析機能を作って` と入力すれば Directive が起票され Task が生成される |

bakufu システム全体ペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

##### ペルソナ別ジャーニー（個人開発者 CEO）

1. **directive 発行**: UI のチャット欄に `$ ブログのアクセス分析機能を作って` と入力 → Enter
2. **正規化**: application 層が `$` 付きを保証（既に `$` で始まれば変更なし、なければ自動付加）
3. **Directive 構築**: 委譲先 Room・発行日時と関連付けられた Directive が作成される
4. **永続化**: `DirectiveRepository.save(directive)` で SQLite に書き込み（text に混入した secret は DB には伏字化）
5. **Task 生成**: 同一トランザクション内で Task を作り Directive に紐付け
6. **Vモデル工程開始**: Room の Workflow から Task が起票され工程が進む

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|-------|---------|-----------------|-------|------|
| UC-DR-001 | CEO | Directive を発行できる（テキストと委譲先 Room を指定、Task 紐付けなし初期状態） | 必須 | domain |
| UC-DR-002 | CEO | 発行した Directive に Task を紐付けられる（link_task、1 回のみ） | 必須 | domain |
| UC-DR-003 | CEO | 業務ルール違反（テキスト超過・再リンク等）を拒否できる | 必須 | domain |
| UC-DR-004 | CEO | 発行した Directive の状態がアプリ再起動を跨いで保持される（永続化を意識しない） | 必須 | repository |

## 6. スコープ

### In Scope

- Directive 業務概念全体で観察可能な業務ふるまい（UC-DR-001〜004）
- ふるまいの呼び出し失敗時に観察される拒否シグナル（業務ルール違反）
- 業務概念単位の E2E 検証戦略 → [`system-test-design.md`](system-test-design.md)

### Out of Scope（参照）

- Directive の HTTP API → 将来の `directive/http-api/` sub-feature
- Directive 発行チャット UI → 将来の `directive/ui/` sub-feature
- Task Aggregate の業務ふるまい → `feature/task`（別 Aggregate）
- application 層 `DirectiveService.issue()` の実装 → `feature/directive-application`（未起票）
- `target_room_id` の参照整合性検証 → `DirectiveService.issue()` 責務（application 層）
- 永続化基盤の汎用責務 → [`feature/persistence-foundation`](../persistence-foundation/)

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-A: `$` プレフィックス正規化は application 層責務

`aggregates.md` §Directive で「`$` プレフィックスから始まる」と概念定義されているが、Aggregate 内不変条件として強制しない。`DirectiveService.issue(raw_text, target_room_id)` の application 層が `text = raw_text if raw_text.startswith('$') else '$' + raw_text` で正規化する。

**理由**: CEO が `$` を打ち忘れた場合の自動付加が運用上自然。Aggregate は valid な text しか受け取らない契約で清潔に保つ。

### 確定 R1-B: `spawn_task` ではなく `link_task` に変更

`aggregates.md` §Directive で「`spawn_task() -> Task`」と記述されているが、Aggregate 境界違反のため変更する。`link_task(task_id) -> Directive` で生成済み Task の id を関連付ける（pre-validate 方式で新インスタンス返却）。Task 生成は `DirectiveService.issue()` の application 層責務。

### 確定 R1-C: `task_id` 一意遷移（None → 有効 TaskId のみ可、再リンク禁止）

`task_id is None` から有効 TaskId への遷移は 1 回のみ許可。既に `task_id is not None` の Directive への再リンクは拒否（業務的に「1 Directive → 1 Task」の関係を保証）。

### 確定 R1-D: `DirectiveInvariantViolation` は webhook auto-mask を適用

CEO が directive `text` に webhook URL を貼り付け得るため、agent / workflow / room と同パターンで `super().__init__` 前に `message` / `detail` の webhook URL を伏字化する（多層防御）。

### 確定 R1-E: エラーメッセージは 2 行構造（`[FAIL] failure` + `Next: action`）

MSG-DR-001〜005 はすべて「失敗事実（1 行目）+ 次に何をすべきか（2 行目）」の 2 行構造。`assert "Next:" in str(exc)` を CI で物理保証する（room §確定 I 踏襲）。

### 確定 R1-F: `directives.text` は DB に raw secret で保存しない

CEO directive 由来の `text` に webhook URL / API key が混入し得るため、Repository 層で永続化前に `MaskedText` TypeDecorator を適用する。domain 層は raw 保持し、Repository 層でマスキング（多層防御の各層が独立して secret 漏洩を防ぐ）。

### 確定 R1-G: Directive の状態は再起動跨ぎで保持される

Directive 発行は永続的な業務記録であり、アプリ再起動による状態消失は業務として許容できない。永続化は CEO から意識されない透明な責務（UC-DR-004）。

## 8. 制約・前提

| 区分 | 内容 |
|-----|------|
| 既存運用規約 | GitFlow / Conventional Commits（[`CONTRIBUTING.md`](../../../CONTRIBUTING.md)） |
| ライセンス | MIT |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |
| ネットワーク | 該当なし — Directive 業務概念は外部通信を持たない（実 LLM 送信は `feature/llm-adapter` 責務）|
| 依存 feature | M1 開始時点: 4 兄弟（empire / workflow / agent / room）マージ済み / M2 開始時点: M1 Directive Aggregate + [`feature/persistence-foundation`](../persistence-foundation/) マージ済み |

実装技術スタック（Python 3.12 / Pydantic v2 / SQLAlchemy 2.x async / Alembic / pyright strict / pytest）は各 sub-feature の `basic-design.md §依存関係` に集約する。

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|------|---------|---------|
| 1 | CEO が有効な Directive を作成でき、委譲先 Room・発行日時と関連付けられる。Task 未紐付けの初期状態で生成される（業務ルール R1-C） | UC-DR-001 | TC-UT-DR-001（[`domain/test-design.md`](domain/test-design.md)） |
| 2 | Directive のテキストが業務ルール（1〜10000 文字）を超えると発行を拒否される | UC-DR-001 | TC-UT-DR-002 |
| 3 | テキストの NFC 正規化が適用される（合成形・分解形が同一として扱われる） | UC-DR-001 | TC-UT-DR-003 |
| 4 | テキストの前後改行・空白が保持される（strip されない。CEO の複数段落 directive を損なわない） | UC-DR-001 | TC-UT-DR-004 |
| 5 | Directive に Task を紐付けられる（初回のみ、紐付け後は Task 参照が確立される） | UC-DR-002 | TC-UT-DR-005 |
| 6 | 既に Task が紐付け済みの Directive への再リンクは拒否される（業務ルール R1-C「1 Directive → 1 Task」） | UC-DR-002 | TC-UT-DR-006 |
| 7 | 業務ルール違反のエラーメッセージに Discord webhook URL が含まれていた場合、`<REDACTED:DISCORD_WEBHOOK>` として伏字化される（domain 層での多層防御、業務ルール R1-D） | UC-DR-001〜003 | TC-UT-DR-007 |
| 9 | 業務ルール違反のエラーメッセージには次に取るべき行動の案内（Next: ...）が含まれる（業務ルール R1-E） | UC-DR-001〜003 | TC-UT-DR-022, TC-UT-DR-023 |
| 10 | Directive の状態がアプリ再起動跨ぎで永続化される（テキスト・委譲先 Room・発行日時・Task 参照が再起動後に構造的等価で復元、業務ルール R1-G） | UC-DR-004 | TC-E2E-DR-001（[`system-test-design.md`](system-test-design.md)） |
| 11 | `directives.text` に Discord webhook token / GitHub PAT 等の secret を含む値を保存すると、DB には `<REDACTED:*>` でマスキングされた値が格納される（raw secret が DB に残らない、業務ルール R1-F） | UC-DR-004 | TC-IT-DRR-010-masking-*（[`repository/test-design.md`](repository/test-design.md)） |

E2E（受入基準 10）は [`system-test-design.md`](system-test-design.md) で詳細凍結。受入基準 1〜7, 9 は domain sub-feature の IT / UT で検証（[`domain/test-design.md`](domain/test-design.md)）。受入基準 11 は repository sub-feature の IT で検証。

**注**: 受入基準 #8 は本 feature では設定しない（frozen による構造的等価判定は domain 内部品質基準として sub-feature の `test-design.md §内部品質基準` で管理）。

## 10. 開発者品質基準（CI 担保、業務要求ではない）

各 sub-feature の `basic-design.md §モジュール契約` / `test-design.md §カバレッジ基準` で個別に管理する。本書では業務要求のみ凍結。

参考: domain は `domain/directive/` カバレッジ 95% 以上、repository は実装ファイル群で 90% 以上を目標としているが、これは sub-feature 側の凍結事項。pyright strict pass / ruff 警告ゼロも sub-feature 側で保証する。

## 11. 開放論点 (Open Questions)

凍結時点で未確定の論点はなし — 設計レビューで全件凍結済み（§確定 R1-A〜G として §7 に集約）。

## 12. sub-feature 一覧とマイルストーン整理

[`README.md`](README.md) を参照。

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Directive.text | CEO directive 本文（自然言語、`$` プレフィックス付き、長文可） | **高**（webhook URL / API key 等が誤って混入し得る、Repository 永続化前マスキング必須） |
| Directive.target_room_id | 委譲先 Room の参照 | 低 |
| Directive.created_at | UTC 発行時刻 | 低 |
| Directive.task_id | 生成された Task の参照（None or 有効 TaskId） | 低 |
| 永続化テーブル（directives） | 上記の永続化先 | 低〜高（`directives.text` のみ MaskedText、その他は masking 対象なし） |

## 14. 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 不変条件検査は O(1)（属性数固定）。1ms 未満。永続化層 50ms 未満を目標 |
| 可用性 | 永続化層の WAL モード + crash safety（[`feature/persistence-foundation`](../persistence-foundation/) 担保）により、書き込み中のクラッシュでも Directive 状態が破損しない |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ domain 95% 以上 / repository 90% 以上（各 sub-feature の `test-design.md §カバレッジ基準` で管理） |
| 可搬性 | 純 Python のみ（domain 層）。OS / ファイルシステム依存なし（SQLite はクロスプラットフォーム） |
| セキュリティ | `text` に webhook URL / API key が混入し得る。Repository 永続化前マスキング必須（業務ルール R1-F）。`DirectiveInvariantViolation` の auto-mask で例外経路の多層防御（業務ルール R1-D）。詳細は [`docs/design/threat-model.md`](../../design/threat-model.md) |
