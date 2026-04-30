# 業務仕様書（feature-spec）— Workflow

> feature: `workflow`（業務概念単位）
> sub-features: [`domain/`](domain/) | [`repository/`](repository/) | [`http-api/`](http-api/) | ui（将来）
> 関連 Issue: [#9 feat(workflow): Workflow + Stage + Transition Aggregate (M1)](https://github.com/bakufu-dev/bakufu/issues/9) / [#31 feat(workflow-repository): Workflow SQLite Repository (M2)](https://github.com/bakufu-dev/bakufu/issues/31) / [#58 feat(workflow-http-api): Workflow + Stage HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/58)
> 凍結済み設計: [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Workflow / [`docs/design/domain-model/value-objects.md`](../../design/domain-model/value-objects.md) §Workflow 構成要素

## 本書の役割

本書は **Workflow という業務概念全体の業務仕様** を凍結する。bakufu 全体の要求分析（[`docs/analysis/`](../../analysis/)）を Workflow という業務概念で具体化し、ペルソナ（個人開発者 CEO）から見て **観察可能な業務ふるまい** を実装レイヤー（domain / repository / http-api / ui）に依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / [`http-api/`](http-api/) / 将来の ui）は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない（本書の更新は別 PR で先行する）。

**書くこと**:
- ペルソナ（CEO）が Workflow という業務概念で達成できるようになる行為（ユースケース）
- 業務ルール（不変条件・DAG 整合性・容量上限・EXTERNAL_REVIEW 規約・永続性 等、すべての sub-feature を貫く凍結）
- E2E で観察可能な事象としての受入基準（業務概念全体）
- sub-feature 間の責務分離マップ（実装レイヤー対応）

**書かないこと**（sub-feature の設計書へ追い出す）:
- 採用技術スタック（Pydantic / SQLAlchemy / FastAPI 等） → sub-feature の `basic-design.md`
- 実装方式の比較・選定議論（pre-validate / delete-then-insert / BFS / TypeDecorator 等） → sub-feature の `detailed-design.md`
- 内部 API 形・メソッド名・属性名・型 → sub-feature の `basic-design.md` / `detailed-design.md`
- sub-feature 内のテスト戦略（IT / UT） → sub-feature の `test-design.md`（E2E のみ親 [`system-test-design.md`](system-test-design.md) で扱う）

## 1. この feature の位置付け

bakufu インスタンスの組織（Empire）で採用する AI 協業フローを表現する「Workflow」を、ペルソナ（個人開発者 CEO）が Stage と Transition を組み合わせて設計・運用できる業務概念として定義する。Workflow は Stage（工程）の有向非循環グラフ（DAG）であり、V モデル開発フロー / アジャイルスプリント等のプリセットを表現する核となる Aggregate。

Workflow の業務的なライフサイクルは複数の実装レイヤーを跨ぐ:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| domain | [`domain/`](domain/) | Workflow / Stage / Transition の構造的整合性（DAG 不変条件・容量・EXTERNAL_REVIEW 規約・required_role 非空）を Aggregate 内で保証 |
| repository | [`repository/`](repository/) | Workflow の状態を再起動跨ぎで保持（永続化）、Stage.notify_channels の Discord webhook token マスキングを担保 |
| http-api | [`http-api/`](http-api/) | UI / 外部クライアントから Workflow を操作・取得する経路 |
| ui | (将来) | CEO が Workflow の DAG を直感的に編集する画面（react-flow 統合予定） |

本書はこれら全レイヤーを貫く **業務概念単位の凍結文書** であり、各 sub-feature は本書を引用して実装契約を凍結する。

## 2. 人間の要求

> Issue #9（M1 domain）:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の一環として **Workflow Aggregate Root** を実装する。Workflow は Stage / Transition を内部に持つ DAG ワークフロー定義で、Vモデル / アジャイル等のプリセットを表現する核となる Aggregate。

> Issue #31（M2 repository）:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の後続 Repository PR（empire-repository #25 のテンプレート責務継承）。**Workflow Aggregate** の SQLite 永続化を実装する。`Stage.notify_channels` の Discord webhook token の Repository マスキング実適用が本 PR の核心。

> Issue #58（M3 http-api）:
>
> Workflow Aggregate および Stage 一覧エンドポイントを実装する。Workflow Designer（JSON 編集 + プリセット選択）の基盤 API。Room にカスタム Workflow を作成・割り当て、取得・更新・アーカイブを行う 7 エンドポイントを提供する。

## 3. 背景・痛点

### 現状の痛点

1. bakufu の差別化要因「Vモデル工程の Aggregate ロック」は Workflow Aggregate なしには実現できない。Aggregate なら工程逸脱が型システムレベルで不可能になるが、現状は文書のみ
2. M1 後段の `task` Issue は `current_stage_id` を Workflow Aggregate 内の Stage に解決する設計。Workflow がないと Task の遷移ロジックが書けない
3. プリセット（Vモデル開発室 / アジャイル開発室）は JSON 定義から構築する設計。ファクトリ実装も本 feature が含まれる
4. M2 後続 Repository 5 件（agent / room / directive / task / external-review-gate）は `rooms.workflow_id` FK を必要とする。workflow-repository を最初に積まないと後続 PR の Alembic revision で FK が張れない
5. CEO が Workflow を設計しても再起動で状態が消えるなら業務として成立しない（Workflow 設計は持続的な組織概念）

### 解決されれば変わること

- `task` Aggregate（M1 後段）が `current_stage_id` を valid な Stage に解決できる
- Vモデルプリセット読み込みが JSON → Aggregate の形で動き、`feature/workflow-presets` で V モデル / アジャイルが追加可能になる
- Workflow の状態がアプリ再起動を跨いで保持される（CEO は永続化を意識しない）
- `Stage.notify_channels` に CEO が Discord webhook URL を設定しても DB には `<REDACTED:DISCORD_WEBHOOK>` で永続化（webhook token マスキング実適用完了）

### ビジネス価値

- bakufu の核心思想「External Review Gate を含む工程ロック」が型レベルで実現する
- Workflow を JSON で受け取れる設計が確定すれば、UI で「Workflow 編集」を後段で実装する際の入出力契約も自動的に確定する

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|-----------|------|---------|---------------|
| 個人開発者 CEO | bakufu インスタンスのオーナー | 直接（将来の UI 経由）/ 間接（domain・repository sub-feature では application 層経由） | Workflow を設計し、Stage / Transition を構成して DAG を定義する。JSON プリセットを読み込んで V モデル開発室を即座に構築できる。再起動跨ぎで Workflow 状態が保持される |

bakufu システム全体ペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|-------|---------|-----------------|-------|------|
| UC-WF-001 | CEO | valid な Workflow を構築できる（Stage / Transition / entry_stage_id を設定して DAG 整合性を満たす）| 必須 | domain |
| UC-WF-002 | CEO | Workflow に Stage を追加できる | 必須 | domain |
| UC-WF-003 | CEO | Workflow に Transition を追加できる | 必須 | domain |
| UC-WF-004 | CEO | Workflow から Stage を削除できる（関連 Transition も連鎖削除） | 必須 | domain |
| UC-WF-005 | CEO | 業務ルール違反（DAG 不整合・容量超過・EXTERNAL_REVIEW 規約違反等）の操作が拒否され、Workflow 状態は変化しない | 必須 | domain |
| UC-WF-006 | CEO | JSON プリセット定義から Workflow を一括構築できる | 必須 | domain |
| UC-WF-007 | CEO | 設計した Workflow の状態がアプリ再起動を跨いで保持される（永続化を意識しない）| 必須 | repository |
| UC-WF-008 | CEO | HTTP API 経由で Room に新しい Workflow を作成し割り当てられる（JSON 定義またはプリセット名を指定）| 必須 | http-api |
| UC-WF-009 | CEO | HTTP API 経由で Room に現在割り当てられている Workflow を取得できる | 必須 | http-api |
| UC-WF-010 | CEO | HTTP API 経由で Workflow を ID で取得できる（Stage / Transition 一覧込み）| 必須 | http-api |
| UC-WF-011 | CEO | HTTP API 経由で Workflow の名前または Stage / Transition 構成を更新できる（DAG 整合性を維持しながら）| 必須 | http-api |
| UC-WF-012 | CEO | HTTP API 経由で Workflow をアーカイブできる（論理削除。アーカイブ後は更新不可）| 必須 | http-api |
| UC-WF-013 | CEO | HTTP API 経由で Workflow の Stage 一覧を取得できる（各 Stage に紐づく Transition 情報込み）| 必須 | http-api |
| UC-WF-014 | CEO | HTTP API 経由でプリセット Workflow 一覧を取得できる（V モデル / アジャイル等）| 必須 | http-api |

## 6. スコープ

### In Scope

- Workflow 業務概念全体で観察可能な業務ふるまい（UC-WF-001〜007）
- ふるまいの呼び出し失敗時に観察される拒否シグナル（業務ルール違反）
- 業務概念単位の E2E 検証戦略 → [`system-test-design.md`](system-test-design.md)

### Out of Scope（参照）

- Workflow の HTTP API → [`workflow/http-api/`](http-api/)（M3 で実装済み）
- Workflow の編集 UI → 将来の `workflow/ui/` sub-feature（react-flow 統合予定）
- Workflow プリセット JSON 定義の管理 → `feature/workflow-presets`
- Task の Workflow-Stage 解決 → `feature/task`
- 永続化基盤の汎用責務（WAL / マイグレーション / masking gateway） → [`feature/persistence-foundation`](../persistence-foundation/)
- 実 Discord webhook 送信 → `feature/discord-notifier`（本 feature では URL allow list 形式チェックのみ）

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-1: Workflow 名は 1〜80 文字、空白のみは無効

**理由**: CEO が認識可能な表示名であること。NFC 正規化 + strip 後の Unicode コードポイント数で判定。詳細は [`domain/detailed-design.md`](domain/detailed-design.md)。

### 確定 R1-2: Stage は 1〜30 件、`stage_id` 重複なし

**理由**: 有向グラフの最小要件として Stage が 1 件以上必要。MVP の実用範囲（V モデル開発室 13 Stage 程度）の 2 倍を上限に設定。Phase 2 で運用実績を見て調整。

### 確定 R1-3: Transition は 0〜60 件、`transition_id` 重複なし

**理由**: 最小 Workflow（1 Stage + 0 Transition、entry == 終端）を許容。上限は Stage 上限の 2 倍。

### 確定 R1-4: `entry_stage_id` は必ず `stages` 内の Stage を指す

**理由**: Task がどの Stage から開始するかを一意に決定する。DAG の起点として不可欠。

### 確定 R1-5: `entry_stage_id` から全 Stage に到達可能（孤立 Stage 禁止）

**理由**: 到達不能な Stage は Task がそこに遷移できない「ゾンビ Stage」であり、DAG の意味を壊す。BFS で検査。

### 確定 R1-6: 終端 Stage（外向き Transition なし）が 1 件以上存在

**理由**: 終端のない DAG は循環を持ち、Task が無限ループする。複数終端（並列終端）は許容。

### 確定 R1-7: 同一 `(from_stage_id, condition)` の Transition 重複は禁止（決定論性）

**理由**: 同じ条件で複数の Transition が存在すると、Task の遷移先が非決定的になる。

### 確定 R1-8: EXTERNAL_REVIEW Stage は `notify_channels` を 1 件以上持つ

**理由**: External Review Gate は外部に通知して承認を得る工程。通知先がなければ Gate が機能しない。

### 確定 R1-9: 全 Stage の `required_role` は空集合不可

**理由**: 担当役割のない Stage には Task を誰も担当できない。業務ルール違反として早期検出。

### 確定 R1-10: `Stage.notify_channels` の Discord webhook URL は業務ルールに定めた allow list を充足する

**理由**: webhook URL は実 HTTP POST の送信先となるため、SSRF 防御として URL の形式・スキーム・ホスト・パス構造を厳格に検査する必要がある。詳細ルール（G1〜G10）は [`domain/detailed-design.md §確定 G`](domain/detailed-design.md) に凍結。

### 確定 R1-11: Workflow の状態は再起動跨ぎで保持される

**理由**: Workflow 設計は持続的な組織概念であり、アプリ再起動による状態消失は業務として許容できない。永続化は CEO から意識されない透明な責務。

### 確定 R1-12: `Stage.notify_channels` の Discord webhook token は永続化前にマスキングを適用する

**理由**: CEO が Stage 設計時に webhook URL を含めた場合、DB 直読み / バックアップ / 監査ログ経路への token 流出を防ぐ。domain 層は raw URL を保持し、Repository 層で永続化前に token 部を `<REDACTED:DISCORD_WEBHOOK>` に置換する。

### 確定 R1-13: Stage に `required_gate_roles` を設定できる（Issue #65 で追加）

CEO は Workflow 設計時に、各 Stage に `required_gate_roles`（内部レビューを担当する GateRole 名のセット）を設定できる。空集合は「内部レビュー不要の Stage」を意味し合法。非空の場合、各要素は 1〜40 文字の小文字英数字ハイフン（slug 形式）でなければならない。

**理由**: InternalReviewGate feature（Issue #65）が、Workflow Stage ごとに内部審査観点（reviewer / ux / security 等）を定義できる要件（[`../internal-review-gate/feature-spec.md §9 AC#1`](../internal-review-gate/feature-spec.md)）を満たすために必要。Stage の `required_gate_roles` が空集合の場合は InternalReviewGate が生成されない（application 層の責務）。実装詳細は [`domain/basic-design.md §REQ-WF-008`](domain/basic-design.md) を参照。

### 確定 R1-14: Workflow はアーカイブ状態を持つ

CEO は Workflow をアーカイブ（論理削除）できる。アーカイブ済み Workflow は更新操作（PATCH）を受け付けない。ただし取得（GET）は可能。

**理由**: 運用中の Workflow を誤って削除・変更する事故を防ぐため、論理削除（アーカイブ）で保全しつつ参照可能な状態を維持する。物理削除は現在 Room.workflow_id FK が存在するため許容できない（FK 参照整合性の破壊）。

### 確定 R1-15: Room の Workflow 割り当て変更は既存 Room の workflow_id を上書きする

POST /api/rooms/{room_id}/workflows で新しい Workflow を作成・割り当てると、Room の workflow_id が新しい Workflow ID に更新される。古い Workflow は自動アーカイブされず、引き続き取得可能。

**理由**: Workflow の更新履歴を保全しつつ、Room が常に一つの「現役 Workflow」を参照する単純な構造を維持する。Room は 1 つの Workflow のみを参照する（1:1 参照）。

### 確定 R1-16: notify_channels が masked 状態の Workflow は更新操作（PATCH）を受け付けない

EXTERNAL_REVIEW Stage を含む Workflow を一度永続化すると、webhook token は `<REDACTED:DISCORD_WEBHOOK>` に置換される（業務ルール R1-12）。この状態では `WorkflowRepository.find_by_id` による Workflow 復元時に `NotifyChannel` の Pydantic バリデーションが失敗するため、PATCH による更新は技術的に不可能となる。application 層はこの `pydantic.ValidationError` を `WorkflowIrreversibleError` に変換し、HTTP 409 で拒否する。CEO が Workflow を更新したい場合は、新しい webhook URL を含む Workflow を再作成すること（POST /api/rooms/{room_id}/workflows）。

**理由**: webhook token の masking は不可逆（[`repository/detailed-design.md §確定H §不可逆性`](repository/detailed-design.md)）。masking 後に元の URL を復元する手段がないため、domain の `NotifyChannel` バリデーションが復元時に必ず失敗する。内部エラー（500）ではなく、業務的に理解可能な 409 として拒否することで Fail Fast 原則を満たし、CEO に明示的な操作ガイダンスを提供する。

### 確定 R1-17: Stage の `required_deliverables` は `template_ref.template_id` の重複を禁止する（Issue #117）

CEO は各 Stage に `required_deliverables`（`DeliverableRequirement` のリスト）を設定できる。各 `DeliverableRequirement` は `template_ref: DeliverableTemplateRef` と `optional: bool` を持つ。`required_deliverables` 内の `template_ref.template_id` は重複してはならない（同一テンプレートを必須・任意に二重設定する業務的に無意味な状態を防ぐ）。空リスト（成果物要件なし）は合法。

**理由**: 旧 `deliverable_template: str`（Markdown 自由記述）は機械的な整合性チェックが不可能だった。`DeliverableRequirement` VO（`template_ref: DeliverableTemplateRef, optional: bool`）への置き換えにより、DeliverableTemplate との参照整合性・SemVer バージョン互換性をドメイン層で保証できる。`optional` フラグで「提出が期待される（必須）/ 任意」を明示し、将来の Task 完了判定（application 層）に活用できる構造を提供する。

## 8. 制約・前提

| 区分 | 内容 |
|-----|------|
| 既存運用規約 | GitFlow / Conventional Commits（[`CONTRIBUTING.md`](../../../CONTRIBUTING.md)） |
| ライセンス | MIT |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |
| ネットワーク | 該当なし — Workflow 業務概念は外部通信を持たない（永続化はローカル SQLite。実 webhook 送信は `feature/discord-notifier` 責務）|
| 依存 feature | M1 開始時点: chore #7 マージ済み / M2 開始時点: M1 `workflow/domain` + [`feature/persistence-foundation`](../persistence-foundation/) + empire-repository マージ済み |

実装技術スタック（Python 3.12 / Pydantic v2 / SQLAlchemy 2.x async / Alembic / pyright strict / pytest）は各 sub-feature の `basic-design.md §依存関係` に集約する。

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|------|---------|---------|
| 1 | 1 Stage + 0 Transition の最小 Workflow が構築できる（entry_stage_id == 終端 Stage） | UC-WF-001 | TC-UT-WF-001（[`domain/test-design.md`](domain/test-design.md)） |
| 2 | `entry_stage_id` が stages に存在しない Workflow は構築できない（業務ルール R1-4） | UC-WF-005 | TC-UT-WF-002 |
| 3 | 孤立 Stage（entry から到達不能）がある Workflow は構築できない（業務ルール R1-5） | UC-WF-005 | TC-UT-WF-003 |
| 4 | 終端 Stage が 0 件（全 Stage に外向き Transition あり = 循環）の Workflow は構築できない（業務ルール R1-6） | UC-WF-005 | TC-UT-WF-004 |
| 5 | 同一 `(from_stage_id, condition)` の Transition 重複は拒否される（業務ルール R1-7） | UC-WF-005 | TC-UT-WF-005 |
| 6 | EXTERNAL_REVIEW Stage で `notify_channels` が空の Workflow は構築できない（業務ルール R1-8） | UC-WF-005 | TC-UT-WF-006a, 006b |
| 7 | `required_role` が空集合の Stage を含む Workflow は構築できない（業務ルール R1-9） | UC-WF-005 | TC-UT-WF-007 |
| 8 | `add_stage` 失敗時、Workflow 状態が変化していない（業務ルール R1-2） | UC-WF-002, 005 | TC-UT-WF-008 |
| 9 | `remove_stage(entry_stage_id)` は拒否され、Workflow 状態が変化しない（業務ルール R1-4） | UC-WF-004, 005 | TC-UT-WF-009 |
| 10 | V モデル開発室の JSON プリセット（13 Stage / 15 Transition）から Workflow を一括構築できる（業務ルール R1-2〜9 全充足）| UC-WF-006 | TC-IT-WF-001（[`domain/test-design.md`](domain/test-design.md)） |
| 11 | 設計した Workflow の状態がアプリ再起動跨ぎで保持される（業務ルール R1-11） | UC-WF-007 | TC-E2E-WF-001（[`system-test-design.md`](system-test-design.md)） |
| 12 | `Stage.notify_channels` に Discord webhook URL を設定して永続化すると、DB には token 部が伏字化されて保存される（業務ルール R1-12） | UC-WF-007 | TC-IT-WFR-013（[`repository/test-design.md`](repository/test-design.md)） |

| 13 | HTTP API 経由で Room に JSON 定義 Workflow を作成・割り当てられる（業務ルール R1-1〜9 充足、Room.workflow_id が更新される）| UC-WF-008 | TC-IT-WFH-001（[`http-api/test-design.md`](http-api/test-design.md)）|
| 14 | HTTP API 経由でプリセット名を指定して Workflow を作成・割り当てられる（preset_name="v-model"）| UC-WF-008, UC-WF-014 | TC-IT-WFH-002 |
| 15 | HTTP API 経由で Room の現在の Workflow を取得できる（Stage / Transition 込み）| UC-WF-009 | TC-IT-WFH-003 |
| 16 | HTTP API 経由で Workflow を ID で単件取得できる（Stage / Transition / entry_stage_id 含む）| UC-WF-010 | TC-IT-WFH-004 |
| 17 | HTTP API 経由で Workflow 名を更新できる（DAG 整合性は既存のまま維持）| UC-WF-011 | TC-IT-WFH-005 |
| 18 | HTTP API 経由で Workflow の Stage / Transition を全置換更新できる（DAG 検査が走り、違反時は 422）| UC-WF-011 | TC-IT-WFH-006 |
| 19 | HTTP API 経由で Workflow をアーカイブできる（204 No Content、以降の PATCH は 409）| UC-WF-012, R1-14 | TC-IT-WFH-007 |
| 20 | HTTP API 経由で Workflow の Stage 一覧を取得できる（各 Stage に紐づく Transition 情報込み）| UC-WF-013 | TC-IT-WFH-008 |
| 21 | HTTP API 経由でプリセット一覧を取得できる（少なくとも "v-model" が含まれる）| UC-WF-014 | TC-IT-WFH-009 |
| 22 | HTTP API 経由 Workflow CRUD が再起動跨ぎで保持される（E2E）| UC-WF-008〜010 | TC-E2E-WF-003（[`system-test-design.md`](system-test-design.md)）|
| 23 | EXTERNAL_REVIEW Stage を含む Workflow への PATCH は 409 で拒否される（業務ルール R1-16）| UC-WF-011, R1-16 | TC-IT-WFH-030（[`http-api/test-design.md`](http-api/test-design.md)）|
| 24 | `required_deliverables` 内に同一 `template_id` を持つ `DeliverableRequirement` 2 件を含む Stage は構築できない（業務ルール R1-17）| UC-WF-005 | TC-UT-WF-063（[`domain/test-design.md`](domain/test-design.md)）|

E2E（受入基準 11, 22）は [`system-test-design.md`](system-test-design.md) で詳細凍結。受入基準 1〜10, 24 は domain sub-feature の IT / UT で検証（[`domain/test-design.md`](domain/test-design.md)）。受入基準 12 は repository sub-feature の IT で検証。受入基準 13〜21 / 23 は http-api sub-feature の IT / UT で検証（[`http-api/test-design.md`](http-api/test-design.md)）。

## 10. 開発者品質基準（CI 担保、業務要求ではない）

各 sub-feature の `basic-design.md §モジュール契約` / `test-design.md §カバレッジ基準` で個別に管理する。本書では業務要求のみ凍結。

参考: domain は `domain/workflow.py` カバレッジ 95% 以上、repository は実装ファイル群で 90% 以上を目標としているが、これは sub-feature 側の凍結事項。

## 11. 開放論点 (Open Questions)

| # | 論点 | 起票先 |
|---|------|-------|
| Q-WF-001 | `Workflow.archived: bool = False` フィールドは domain sub-feature の設計変更が必要。http-api PR と同一 PR で domain/basic-design.md / detailed-design.md を更新する。旧 R1 レビューで凍結済みの不変条件（R1-1〜13）には影響なし | 本 PR（Issue #58）で対処 |
| Q-WF-002 | プリセット JSON 定義の管理方針（アプリ内 static データ or 別ファイル or DB bootstrap）は http-api/detailed-design.md §確定 D で凍結する | 本 PR（Issue #58）で対処 |

## 12. sub-feature 一覧とマイルストーン整理

[`README.md`](README.md) を参照。

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Workflow.name | "V モデル開発フロー" 等の定義名 | 低 |
| Stage.name / kind / required_role / required_deliverables | Stage のメタデータ | 低 |
| Stage.completion_policy | 完了判定ロジック設定（CEO 設計値） | 低 |
| Stage.notify_channels | Discord webhook URL（token を含む）| **中**（token を持つ第三者は当該 webhook 経由で任意送信可、Repository 永続化前マスキング必須） |
| 永続化テーブル群（workflows / workflow_stages / workflow_transitions） | 上記の永続化先 | 低〜中（`workflow_stages.notify_channels_json` のみ MaskedJSONEncoded、その他は masking 対象なし） |

## 14. 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 業務ふるまい呼び出しの応答が CEO 視点で「即時」と感じられること。DAG 検査は O(V+E)（V=stages, E=transitions）で MVP 想定規模（stages ≤ 30, transitions ≤ 60）で 1ms 未満を目標。永続化層 50ms 未満を目標 |
| 可用性 | 永続化層の WAL モード + crash safety（[`feature/persistence-foundation`](../persistence-foundation/) 担保）により、書き込み中のクラッシュでも Workflow 状態が破損しない |
| 可搬性 | 純 Python のみ。OS / ファイルシステム依存なし（SQLite はクロスプラットフォーム） |
| セキュリティ | 業務ルール違反は早期に拒否される（Fail Fast）。`Stage.notify_channels` の Discord webhook token は Repository 層 `MaskedJSONEncoded` で永続化前マスキング（業務ルール R1-12）。URL allow list G1〜G10（業務ルール R1-10）で SSRF 防御 |
