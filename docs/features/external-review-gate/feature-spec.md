# 業務仕様書（feature-spec）— ExternalReviewGate

> feature: `external-review-gate`（業務概念単位）
> sub-features: [`domain/`](domain/) | [`repository/`](repository/) | [`http-api/`](http-api/) | ui（将来）
> 関連 Issue: [#38 feat(external-review-gate): ExternalReviewGate Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/38) / [#36 feat(external-review-gate-repository): ExternalReviewGate SQLite Repository (M2)](https://github.com/bakufu-dev/bakufu/issues/36)
> 凍結済み設計: [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §ExternalReviewGate / [`docs/design/domain-model/value-objects.md`](../../design/domain-model/value-objects.md) §AuditEntry / §列挙型一覧（ReviewDecision / AuditAction）/ [`docs/design/domain-model/storage.md`](../../design/domain-model/storage.md) §snapshot 凍結方式

## 本書の役割

本書は **ExternalReviewGate という業務概念全体の業務仕様** を凍結する。bakufu 全体の要求分析（[`docs/analysis/`](../../analysis/)）を ExternalReviewGate という業務概念で具体化し、ペルソナ（個人開発者 CEO）から見て **観察可能な業務ふるまい** を実装レイヤー（domain / repository / http-api / ui）に依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / [`http-api/`](http-api/) / 将来の ui）は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない（本書の更新は別 PR で先行する）。

**書くこと**:
- ペルソナ（CEO）が ExternalReviewGate という業務概念で達成できるようになる行為（ユースケース）
- 業務ルール（不変条件・判断遷移・audit_trail・snapshot・webhook マスキング・永続性等、すべての sub-feature を貫く凍結）
- E2E で観察可能な事象としての受入基準（業務概念全体）
- sub-feature 間の責務分離マップ（実装レイヤー対応）

**書かないこと**（sub-feature の設計書へ追い出す）:
- 採用技術スタック（Pydantic / SQLAlchemy 等） → sub-feature の `basic-design.md`
- 実装方式の比較・選定議論（pre-validate / TypeDecorator 等） → sub-feature の `detailed-design.md`
- 内部 API 形・メソッド名・属性名・型 → sub-feature の `basic-design.md` / `detailed-design.md`
- sub-feature 内のテスト戦略（IT / UT） → sub-feature の `test-design.md`（E2E のみ親 [`system-test-design.md`](system-test-design.md) で扱う）
- pyright / ruff / カバレッジ等の CI 品質基準 → §10 開発者品質基準 / sub-feature の `test-design.md §カバレッジ基準`

## 1. この feature の位置付け

bakufu MVP 核心要件「AI 協業による品質向上を、人間チェックポイントで担保する」を Aggregate モデルで実現する。Stage の `EXTERNAL_REVIEW` kind 到達時に application 層が生成する **独立 Aggregate Root**（Task の子ではない）。

ExternalReviewGate の業務的なライフサイクルは複数の実装レイヤーを跨ぐ:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| domain | [`domain/`](domain/) | 判断状態の遷移（PENDING → APPROVED/REJECTED/CANCELLED）・audit_trail の監査記録・snapshot 不変性・webhook auto-mask を Aggregate 内で保証 |
| repository | [`repository/`](repository/) | Gate の状態を再起動跨ぎで保持（永続化）、3 masking カラムの secret 保護を担保 |
| http-api | [`http-api/`](http-api/) | CEO が approve / reject / cancel を実行する HTTP エンドポイント |
| ui | (将来) | CEO が Deliverable を確認してレビュー操作するチャット画面 |

本書はこれら全レイヤーを貫く **業務概念単位の凍結文書** であり、各 sub-feature は本書を引用して実装契約を凍結する。

## 2. 人間の要求

> Issue #38（M1 domain）:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の **7 番目（最後）の Aggregate** として **ExternalReviewGate Aggregate Root** を実装する。Stage の `EXTERNAL_REVIEW` kind 到達時に application 層が生成する **独立 Aggregate Root**（Task の子ではない）。**MVP の核心要件「AI 協業による品質向上を、人間チェックポイントで担保する」**を Aggregate モデル上で実現する。

> Issue #36（M2 repository）:
>
> ExternalReviewGate Aggregate（M1、PR #46）に対する SQLite 永続化基盤（M2 層）を実装する。3 テーブル構造（gate 本体 + snapshot / attachments / audit_entries）と 3 masking カラムが核心。**M2 マイルストーンの最後の PR**。

## 3. 背景・痛点

### 現状の痛点

1. M1 ドメイン骨格 6 兄弟（empire / workflow / agent / room / directive / task）が完走したが、**MVP 核心要件「人間チェックポイント」を表現する Aggregate がない**。`task.approve_review()` / `task.reject_review()` の dispatch 表は凍結済みだが、それを呼ぶ起点（Gate APPROVED / REJECTED）の Aggregate が存在しないと E2E 経路が成立しない
2. `aggregates.md` §ExternalReviewGate で属性 / ふるまい / 不変条件が凍結済みだが、実体化されていないため後続 Repository PR が着手できない
3. **独立 Aggregate である理由**（Task の子ではない）が固定されないと、後続 PR で「Task の子にしたほうが楽だった」という退行が起きやすい
4. CEO が approve / reject した根拠（誰がいつ何度確認して判断したか）を audit_trail で保持しないと監査要件が成立しない

### 解決されれば変わること

- `feature/external-review-gate-repository`（Issue #36）が Aggregate VO 構造を真実源として SQLite 配線可能
- application 層 `GateService.approve()` / `reject()` が完了したら、`task.approve_review()` / `task.reject_review()` を静的 dispatch で呼ぶ経路が成立
- empire / workflow / agent / room / directive / task の確立済みパターンを **7 例目（最後）**として揃え、M1 ドメイン骨格の完走を達成

### ビジネス価値

- bakufu の核心思想「AI 協業による品質向上を、人間チェックポイントで担保する」を Aggregate 単位で表現する。CEO が UI で「approve / reject」を押す経路が Domain 層で安全にモデル化される
- **複数ラウンド対応**（同 Task の同 Stage で REJECTED → 再 directive → 別 Gate 生成）の Aggregate 履歴保持が成立、audit_trail で「誰がいつ何を見たか / 判断したか」を全件凍結

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|-----------|------|---------|---------------|
| 個人開発者 CEO（堀川さん想定） | Gate を Web UI で approve / reject | GitHub / Docker / CLI 日常使用 | UI で Deliverable を確認 → approve コメント書き込み → Task が次 Stage に進む |
| 後続 Issue 担当（バックエンド開発者） | `feature/external-review-gate-repository`（Issue #36）/ `feature/external-review-gate-application` 実装者 | DDD 経験あり | 設計書を素直に実装するだけ、Aggregate 境界違反を犯さない |
| 監査担当（CEO 自身が兼務） | 後日 audit_trail を確認 | CLI / SQL 操作可能 | 誰がいつ何度確認して判断したかを追跡 |

bakufu システム全体のペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

##### ペルソナ別ジャーニー（個人開発者 CEO）

1. **Stage が EXTERNAL_REVIEW kind に到達**: Agent が成果物 commit → application 層が Gate を生成（PENDING 初期状態）
2. **CEO の閲覧**: UI で Gate（Deliverable スナップショット）を開く → 閲覧記録が audit_trail に追加
3. **承認 or 差戻**: CEO が approve → PENDING → APPROVED、記録追加 → Task が次 Stage に進む。または reject → REJECTED → Task が差し戻し
4. **複数ラウンド対応**: REJECTED 後、Agent が再 directive → 別 Gate 生成（旧 Gate は履歴として保持）

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|-------|---------|-----------------|-------|------|
| UC-ERG-001 | CEO | ExternalReviewGate を生成できる（Task・Stage・Deliverable・承認者と関連付け、PENDING 初期状態） | 必須 | domain |
| UC-ERG-002 | CEO | Gate を承認できる（approve → APPROVED、承認記録追加） | 必須 | domain |
| UC-ERG-003 | CEO | Gate を差し戻せる（reject → REJECTED）/ 中止できる（cancel → CANCELLED） | 必須 | domain |
| UC-ERG-004 | CEO | Gate を閲覧するたびに記録が残る（audit_trail 追加、複数閲覧も全件記録） | 必須 | domain |
| UC-ERG-005 | CEO | Gate の状態がアプリ再起動を跨いで保持される（永続化を意識しない） | 必須 | repository |

## 6. スコープ

### In Scope

- ExternalReviewGate 業務概念全体で観察可能な業務ふるまい（UC-ERG-001〜005）
- ふるまいの呼び出し失敗時に観察される拒否シグナル（業務ルール違反）
- 業務概念単位の E2E 検証戦略 → [`system-test-design.md`](system-test-design.md)

### Out of Scope（参照）

- CEO レビュー UI → 将来の `external-review-gate/ui/` sub-feature
- application 層 `GateService` の実装 → `feature/external-review-gate-application`（未起票）
- Task Aggregate の業務ふるまい → `feature/task`（別 Aggregate）
- `task_id` / `stage_id` / `reviewer_id` の参照整合性検証 → `GateService.create()` 責務（application 層）

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-A: 独立 Aggregate である理由の凍結（3 点）

Gate は Task の子 Entity ではなく独立 Aggregate Root:

| 凍結項目 | 内容 |
|---|---|
| **(1) エンティティ寿命が Stage と一致しない** | 差し戻し後も Gate は履歴として保持される（複数ラウンド可、同 Task の同 Stage で REJECTED → 再 directive → 別 Gate 生成） |
| **(2) トランザクション境界が異なる** | Task の状態遷移と Gate の判断は別の人間（Agent vs CEO）が異なるタイミングで行う。Gate の approve は CEO の UI 操作。application 層 `GateService` が UoW で連結 |
| **(3) 複数 Aggregate にまたがる更新は application 層で管理** | Gate APPROVED → `task.approve_review(...)` の連鎖は `GateService.approve()` が application 層で実行 |

### 確定 R1-B: 判断状態（decision）PENDING → 1 回のみ遷移

判断は 1 回限り（PENDING → APPROVED / REJECTED / CANCELLED）。既に判断済みの Gate に再度 approve / reject / cancel を試みると業務エラーとして拒否される。record_view は判断を変えず audit_trail に閲覧記録を追加するのみ（4 状態すべてで許可）。

### 確定 R1-C: audit_trail は追記のみ許可（監査要件）

audit_trail に一度記録されたエントリは改ざん・削除・並び替え禁止。「誰がいつ何を見たか / 判断したか」を監査ログとして完全保持する業務要件。

### 確定 R1-D: deliverable_snapshot は Gate 生成時に確定し以後不変

Gate 生成時の Deliverable（成果物スナップショット）は inline コピーで確定。以後変更不可（Deliverable 側で添付差し替えがあっても Gate snapshot は不変）。監査要件として「どの成果物に対して判断したか」を確定する。

### 確定 R1-E: record_view の冪等性なし（監査要件）

同一の CEO が複数回 record_view を呼ぶと、audit_trail に複数エントリが積まれる。「何度確認したか」を追跡できる監査要件。冪等にすると CEO の閲覧パターンが追跡できなくなり監査要件と矛盾する。

### 確定 R1-F: エラーメッセージの webhook URL / secret は伏字化される（多層防御）

CEO が approve コメントや reject コメントに webhook URL / API key を貼り付け得るため、業務ルール違反のエラーメッセージでも当該 URL は伏字化される（多層防御）。

### 確定 R1-G: エラーメッセージは 2 行構造（`[FAIL] failure` + `Next: action`）

全業務ルール違反エラーは「失敗事実（1 行目）+ 次に何をすべきか（2 行目）」の 2 行構造で提供する（room §確定 I 踏襲）。

### 確定 R1-H: 3 masking カラムに raw secret を DB に保存しない

CEO が入力した approve / reject コメント（`feedback_text`）、audit エントリコメント（`audit_entries.comment`）、および Agent 出力（`deliverable_snapshot.body_markdown`）には secret が混入し得るため、Repository 永続化前に `MaskedText` TypeDecorator でマスキングする。domain 層は raw 保持し、Repository 層でマスキング（多層防御の各層が独立して secret 漏洩を防ぐ）。

### 確定 R1-I: Gate の状態は再起動跨ぎで保持される

Gate の判断状態・audit_trail・Deliverable スナップショットはアプリ再起動を跨いで永続化される。CEO は永続化を意識しない透明な責務（UC-ERG-005）。

## 8. 制約・前提

| 区分 | 内容 |
|-----|------|
| 既存運用規約 | GitFlow / Conventional Commits（[`CONTRIBUTING.md`](../../../CONTRIBUTING.md)） |
| ライセンス | MIT |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |
| ネットワーク | 該当なし — ExternalReviewGate 業務概念は外部通信を持たない |
| 依存 feature | M1 開始時点: 6 兄弟（empire / workflow / agent / room / directive / task）マージ済み / M2 開始時点: M1 ExternalReviewGate Aggregate + [`feature/persistence-foundation`](../persistence-foundation/) マージ済み |

実装技術スタック（Python 3.12 / Pydantic v2 / SQLAlchemy 2.x async / Alembic / pyright strict / pytest）は各 sub-feature の `basic-design.md §依存関係` に集約する。

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|------|---------|---------|
| 1 | CEO が有効な ExternalReviewGate を生成でき、対象 Task・Stage・Deliverable・承認者（reviewer）と関連付けられる。判断未決（PENDING）の初期状態で生成される | UC-ERG-001 | TC-UT-GT-001（[`domain/test-design.md`](domain/test-design.md)） |
| 2 | 既存の判断状態（APPROVED / REJECTED / CANCELLED）と一貫した判断時刻を持つ Gate が生成できる（永続化後の復元にも対応）| UC-ERG-001 | TC-UT-GT-002 |
| 3 | CEO が Gate を承認できる（approve → PENDING から APPROVED へ遷移、承認時刻が設定され、承認の記録が audit_trail に追加される）| UC-ERG-002 | TC-UT-GT-003 |
| 4 | CEO が Gate を差し戻せる（reject → REJECTED）/ 中止できる（cancel → CANCELLED）、各遷移・記録が残る | UC-ERG-003 | TC-UT-GT-004, TC-UT-GT-013 |
| 5 | 一度判断された Gate に再度 approve / reject / cancel を試みると拒否される（1 回限りの判断、業務ルール R1-B） | UC-ERG-002〜003 | TC-UT-GT-005 |
| 6 | CEO が Gate を閲覧するたびに閲覧記録が audit_trail に追加される。PENDING 以外の状態でも閲覧記録が残る。同一人物が複数回閲覧すると全件の記録が残る（監査要件、業務ルール R1-C / R1-E） | UC-ERG-004 | TC-UT-GT-006 |
| 7 | 未判断（PENDING）の Gate は判断時刻が未設定であり、判断済みの Gate は判断時刻が設定されている（決定論的一貫性） | UC-ERG-001〜003 | TC-UT-GT-007 |
| 8 | Gate 生成時に紐付けられた Deliverable（成果物スナップショット）は変更できない（一度記録された成果物は確定、業務ルール R1-D） | UC-ERG-001 | TC-UT-GT-008 |
| 9 | Gate の audit_trail は追記のみ許可。既存の閲覧・判断記録は改ざんできない（監査ログの完全性、業務ルール R1-C） | UC-ERG-004 | TC-UT-GT-009 |
| 10 | フィードバックコメントは空文字列から 10000 文字まで有効（空での承認も可）。10001 文字以上は拒否される | UC-ERG-002〜003 | TC-UT-GT-010 |
| 11 | 業務ルール違反のエラーメッセージに Discord webhook URL が含まれていた場合、`<REDACTED:DISCORD_WEBHOOK>` として伏字化される（多層防御、業務ルール R1-F） | UC-ERG-001〜004 | TC-UT-GT-011 |
| 12 | 業務ルール違反のエラーメッセージには次に取るべき行動の案内（Next: ...）が含まれる（業務ルール R1-G） | UC-ERG-001〜004 | TC-UT-GT-021〜025 |
| 14 | ExternalReviewGate の状態がアプリ再起動跨ぎで永続化される（判断状態・audit_trail・Deliverable スナップショットが再起動後に構造的等価で復元、業務ルール R1-I） | UC-ERG-005 | TC-E2E-ERG-001（[`system-test-design.md`](system-test-design.md)） |
| 15 | `external_review_gates.snapshot_body_markdown` / `external_review_gates.feedback_text` / `external_review_audit_entries.comment` に secret を含む値を保存すると、DB には `<REDACTED:*>` でマスキングされた値が格納される（raw secret が DB に残らない、業務ルール R1-H） | UC-ERG-005 | TC-IT-ERGR-020-masking-*（[`repository/test-design.md`](repository/test-design.md)） |

E2E（受入基準 14）は [`system-test-design.md`](system-test-design.md) で詳細凍結。受入基準 1〜12 は domain sub-feature の IT / UT で検証（[`domain/test-design.md`](domain/test-design.md)）。受入基準 15 は repository sub-feature の IT で検証（[`repository/test-design.md`](repository/test-design.md)）。

**注**: 受入基準 #13 は本 feature では設定しない（frozen による構造的等価判定は domain 内部品質基準として sub-feature の `test-design.md §内部品質基準` で管理）。

## 10. 開発者品質基準（CI 担保、業務要求ではない）

各 sub-feature の `basic-design.md §モジュール契約` / `test-design.md §カバレッジ基準` で個別に管理する。本書では業務要求のみ凍結。

参考: domain は `domain/external_review_gate/` カバレッジ 95% 以上、repository は実装ファイル群で 90% 以上を目標としているが、これは sub-feature 側の凍結事項。pyright strict pass / ruff 警告ゼロも sub-feature 側で保証する。

## 11. 開放論点 (Open Questions)

凍結時点で未確定の論点はなし — 設計レビューで全件凍結済み（§確定 R1-A〜I として §7 に集約）。

## 12. sub-feature 一覧とマイルストーン整理

[`README.md`](README.md) を参照。

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Gate.feedback_text | CEO の判断コメント（自然言語、長文の可能性） | **高**（webhook URL / API key が混入し得る、Repository 永続化前マスキング必須）|
| Gate.audit_trail[*].comment | audit エントリのコメント | **高**（同上） |
| Gate.deliverable_snapshot.body_markdown | Agent 出力 Markdown（Agent の成果物、secret 混入の可能性） | **高**（MaskedText 必須） |
| Gate.id / task_id / stage_id / reviewer_id | UUID 識別子 | 低 |
| Gate.decision | 判断状態（4 値） | 低 |
| Gate.created_at / decided_at | UTC datetime | 低 |
| 永続化テーブル | `external_review_gates` / `external_review_gate_attachments` / `external_review_audit_entries` | 低〜高（masking 対象 3 カラムのみ MaskedText、その他は masking 対象なし） |

## 14. 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 不変条件検査は O(N) where N = audit_trail 件数（最大想定 100 程度）。1ms 未満。永続化層 50ms 未満を目標 |
| 可用性 | 永続化層の WAL モード + crash safety（[`feature/persistence-foundation`](../persistence-foundation/) 担保）により、書き込み中のクラッシュでも Gate 状態が破損しない |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ domain 95% 以上 / repository 90% 以上（各 sub-feature の `test-design.md §カバレッジ基準` で管理） |
| 可搬性 | 純 Python のみ（domain 層）。OS / ファイルシステム依存なし（SQLite はクロスプラットフォーム） |
| セキュリティ | `feedback_text` / `audit_trail[*].comment` / `deliverable_snapshot.body_markdown` に webhook URL / API key が混入し得る。Repository 永続化前マスキング必須（業務ルール R1-H）。業務ルール違反例外の auto-mask で例外経路の多層防御（業務ルール R1-F）。詳細は [`docs/design/threat-model.md`](../../design/threat-model.md) |
