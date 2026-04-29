# 業務仕様書（feature-spec）— InternalReviewGate

> feature: `internal-review-gate`（業務概念単位）
> sub-features: [`domain/`](domain/)（M1）| repository/（将来）| http-api（将来）| ui（将来）
> 関連 Issue: [#65 feat(internal-review-gate): InternalReviewGate Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/65)
> 凍結済み設計: [`docs/design/domain-model.md`](../../design/domain-model.md) §InternalReviewGate（本 PR で追加）

## 本書の役割

本書は **InternalReviewGate という業務概念全体の業務仕様** を凍結する。bakufu 全体の要求分析（[`docs/analysis/`](../../analysis/)）を InternalReviewGate という業務概念で具体化し、ペルソナ（個人開発者 CEO / GateRole エージェント）から見て **観察可能な業務ふるまい** を実装レイヤー（domain / repository / http-api / ui）に依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature（[`domain/`](domain/) / 将来の repository / http-api / ui）は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない（本書の更新は別 PR で先行する）。

**書くこと**:
- ペルソナが InternalReviewGate という業務概念で達成できるようになる行為（ユースケース）
- 業務ルール（不変条件・Verdict 遷移・GateDecision 遷移・エラーハンドリング等、すべての sub-feature を貫く凍結）
- E2E で観察可能な事象としての受入基準（業務概念全体）
- sub-feature 間の責務分離マップ（実装レイヤー対応）

**書かないこと**（sub-feature の設計書へ追い出す）:
- 採用技術スタック（Pydantic / SQLAlchemy 等）→ sub-feature の `basic-design.md`
- 実装方式の比較・選定議論 → sub-feature の `detailed-design.md`
- 内部 API 形・メソッド名・属性名・型 → sub-feature の `basic-design.md` / `detailed-design.md`
- sub-feature 内のテスト戦略（IT / UT）→ sub-feature の `test-design.md`（E2E のみ親 [`system-test-design.md`](system-test-design.md) で扱う）
- pyright / ruff / カバレッジ等の CI 品質基準 → §10 開発者品質基準 / sub-feature の `test-design.md §カバレッジ基準`

## 1. この feature の位置付け

InternalReviewGate は **Workflow.Stage 末尾での AI エージェント間並列レビューゲート** である。ExternalReviewGate（人間 CEO による判断）の前段品質保証として機能し、複数の GateRole エージェント（reviewer / ux / security 等）が独立・並列に判定を下す。全 GateRole が APPROVED を提出した場合にのみ次フェーズ（ExternalReviewGate 生成または次 Stage 遷移）へ進み、1 件でも REJECTED が提出された場合は前段 Stage に差し戻しシグナルが発火する。

bakufu の差別化価値の核心「AI 協業品質保証」を Aggregate モデルで実現する。

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| domain | [`domain/`](domain/) | GateDecision 遷移（PENDING → ALL_APPROVED / REJECTED）・Verdict 不変条件・GateRole 重複排除・judgement 確定後の追加拒否を Aggregate 内で保証 |
| repository | （将来）| Gate の状態を再起動跨ぎで保持（永続化）、Verdict comment の secret 保護を担保 |
| http-api | （将来）| GateRole エージェントが Verdict を提出する HTTP エンドポイント |
| ui | （将来）| Gate の状態とリアルタイム Verdict 集計を表示するパネル |

本書はこれら全レイヤーを貫く **業務概念単位の凍結文書** であり、各 sub-feature は本書を引用して実装契約を凍結する。

## 2. 人間の要求

> Issue #65（M1 domain）:
>
> bakufu ai-team が Stage 末尾で複数の観点（reviewer / ux / security 等の GateRole）から並列・独立にレビューを行い、全 GateRole の APPROVED が揃った段階でのみ次フェーズへ進む **InternalReviewGate Aggregate Root** を実装する。ExternalReviewGate（人間 CEO 判断）の前段品質保証として機能し、**AI 協業品質保証** という bakufu 差別化価値の核心を Aggregate モデル上で実現する。acceptance-criteria.md §受入基準 #17/#18 がシステム要件として凍結済み。

## 3. 背景・痛点

### 現状の痛点

1. **現状**: ExternalReviewGate に到達する前に AI エージェント間の品質チェックがなく、品質担保の経路が人間 CEO のみに依存している
2. ExternalReviewGate（CEO 1 人判断）は「AI が仕上げた成果物を人間が確認する」経路を担うが、その前段で AI エージェント同士が多角的に品質検査する仕組みがない
3. GateRole（reviewer / ux / security 等）を Stage 定義時に指定できないため、Stage の性質に応じた観点別審査が不可能な状態

### 解決されれば変わること

- 並列 GateRole 審査により、人間レビュー到達前の品質を担保できる
- Stage の `required_gate_roles` で審査観点を Workflow 設計時に確定でき、審査漏れを構造的に防止できる
- `feature/external-review-gate`（Issue #38）が InternalReviewGate ALL_APPROVED 後の次フェーズとして位置づけられ、E2E 品質保証経路が成立する

### ビジネス価値

bakufu の差別化価値の核心「AI 協業品質保証」を実現する。CEO が UI で最終 approve を押す前に、AI エージェントチームが多角的な観点で品質検査を完走した証跡が可視化される。

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|-----------|------|---------|---------------|
| 個人開発者 CEO（堀川さん想定）| Workflow 設計時に Stage の required_gate_roles を指定、最終 ExternalReviewGate で approve / reject | GitHub / Docker / CLI 日常使用 | Stage の審査観点を設計時に確定し、AI チームが品質保証した成果物のみ自分の元に届く仕組みを作る |
| GateRole エージェント（Reviewer / UX / Security 担当 Agent）| 内部レビューを実行し Verdict（APPROVED / REJECTED）を提出 | Agent 実行環境 | 担当 GateRole の観点で独立してレビューを完走し、feedback comment を添えて Verdict を提出する |
| 後続 Issue 担当者 | repository / http-api sub-feature の実装者 | DDD 経験あり | domain 設計書を真実源として、追加実装を依存なく進められる |

bakufu システム全体のペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

##### ペルソナ別ジャーニー（個人開発者 CEO）

1. **Workflow 設計時**: Stage に `required_gate_roles = frozenset({"reviewer", "ux", "security"})` を指定（UC-IRG-001）
2. **Stage 到達時**: application 層が InternalReviewGate を生成、PENDING 初期状態で全 GateRole の Verdict が未提出の状態になる（UC-IRG-002）
3. **並列レビュー実行**: 各 GateRole エージェントが独立して Verdict を提出（UC-IRG-003）
4. **全 APPROVED**: ALL_APPROVED 遷移 → application 層が次フェーズへ（UC-IRG-004）
5. **REJECTED 発生**: REJECTED 遷移 → 前段差し戻しシグナル → エージェントが再作業 → 新しい InternalReviewGate が生成される（UC-IRG-005）

##### ペルソナ別ジャーニー（GateRole エージェント）

1. **審査対象確認**: application 層経由で担当 Gate の情報と Deliverable を取得
2. **独立判定**: 担当 GateRole の観点で審査し、APPROVED / REJECTED の判断を下す
3. **Verdict 提出**: `submit_verdict(role, agent_id, decision, comment, decided_at)` を呼ぶ
4. **重複防止**: 同一 GateRole からの再提出は拒否される（業務ルール R1-B）

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|-------|---------|-----------------|-------|------|
| UC-IRG-001 | CEO | Stage に required_gate_roles（1件以上の GateRole スラッグ集合）を設定できる（Workflow 設計時）| 必須 | feature/workflow |
| UC-IRG-002 | application 層 | Stage 完了時に InternalReviewGate を生成できる（PENDING 初期状態、全 required_gate_roles の Verdict 未提出）| 必須 | domain |
| UC-IRG-003 | GateRole エージェント | 各 GateRole エージェントが独立して Verdict（APPROVED / REJECTED）を提出できる | 必須 | domain |
| UC-IRG-004 | application 層 / CEO | 全 required_gate_roles が APPROVED を提出すると ALL_APPROVED に遷移し、次フェーズへ進む | 必須 | domain |
| UC-IRG-005 | application 層 / CEO | 1 件でも REJECTED が提出されると REJECTED に遷移し、前段 Stage に差し戻しシグナルが発火する | 必須 | domain |
| UC-IRG-006 | application 層 | Gate の状態が再起動跨ぎで保持される（永続化）| 必須 | repository（将来）|

## 6. スコープ

### In Scope

- InternalReviewGate 業務概念全体で観察可能な業務ふるまい（UC-IRG-001〜006）
- ふるまいの呼び出し失敗時に観察される拒否シグナル（業務ルール違反）
- 業務概念単位の E2E 検証戦略 → [`system-test-design.md`](system-test-design.md)

### Out of Scope（参照）

- Gate 操作 HTTP API → 将来の `internal-review-gate/http-api/` sub-feature
- CEO / Agent レビュー UI → 将来の `internal-review-gate/ui/` sub-feature
- application 層の Task 差し戻しロジック → `feature/task`（Task 状態機械との連携は application 層責務）
- `required_gate_roles` に対応する Workflow.Stage 属性の追加 → `feature/workflow`（別 feature）
- WebSocket でのリアルタイム Verdict 通知 → `feature/realtime-sync`（§11 開放論点）

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-A: 独立 Aggregate である理由の凍結（3 点）

InternalReviewGate は Task の子 Entity ではなく独立 Aggregate Root（ExternalReviewGate と同様の構造的根拠）:

| 凍結項目 | 内容 |
|---|---|
| **(1) エンティティ寿命が Stage と一致しない** | 差し戻し後も Gate は履歴として保持される。REJECTED 後に Agent が再作業 → 別 Gate が生成される複数ラウンド対応 |
| **(2) トランザクション境界が異なる** | 各 GateRole エージェントが独立した時刻・独立したトランザクションで Verdict を提出する。複数 Agent が並列で Verdict 提出するため、単一 Tx に縛ることが不可能 |
| **(3) 複数 Aggregate にまたがる更新は application 層で管理** | Gate ALL_APPROVED → `task.advance()` / Gate REJECTED → `task.rollback()` の連鎖は application 層 `InternalGateService` が実行する |

### 確定 R1-B: 1 GateRole = 1 Verdict（重複提出拒否）

同一 GateRole からの Verdict は 1 回のみ提出可能。既提出の GateRole からの再提出は業務エラーとして拒否される（`kind='role_already_submitted'`）。

### 確定 R1-C: 判断確定後（ALL_APPROVED / REJECTED）の追加 Verdict 提出は拒否

GateDecision が ALL_APPROVED または REJECTED に遷移した後の追加 Verdict 提出は業務エラーとして拒否される（`kind='gate_already_decided'`）。

### 確定 R1-D: ALL_APPROVED 遷移条件

`required_gate_roles` の全 GateRole が APPROVED を提出したときに ALL_APPROVED へ遷移する。1 件でも PENDING が残る場合は遷移しない。application 層が ALL_APPROVED を検出して次フェーズ（ExternalReviewGate 生成または次 Stage 遷移）を実行する。

### 確定 R1-E: REJECTED 遷移条件

`required_gate_roles` のいずれか 1 件が REJECTED を提出した時点で即座に REJECTED へ遷移する。残りの GateRole が未提出であっても即遷移する。application 層が REJECTED を検出して Task を前段 Stage に差し戻す。

### 確定 R1-F: "ambiguous" な判定は REJECTED として扱う

bakufu では明確な承認（APPROVED）のみ前進を許可する。VerdictDecision は `APPROVED` / `REJECTED` の 2 値のみ。「ambiguous」「maybe」「conditional」等の判断は application 層（caller）が REJECTED に変換してから `submit_verdict` を呼ぶ（domain 層は 2 値型のみ受け付ける）。

### 確定 R1-G: エラーメッセージは 2 行構造（`[FAIL] failure` + `Next: action`）

全業務ルール違反エラーは「失敗事実（1 行目）+ 次に何をすべきか（2 行目）」の 2 行構造で提供する（ExternalReviewGate / Room §確定 I 踏襲）。

## 8. 制約・前提

| 区分 | 内容 |
|-----|------|
| 既存運用規約 | GitFlow / Conventional Commits（[`CONTRIBUTING.md`](../../../CONTRIBUTING.md)） |
| ライセンス | MIT |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |
| ネットワーク | 該当なし — domain 層は外部通信を持たない |
| 依存 feature | `feature/workflow`（Stage に `required_gate_roles` 追加）/ `feature/task`（Task 状態機械、advance / rollback メソッド）/ `feature/external-review-gate`（後続連携：ALL_APPROVED 後に ExternalReviewGate を生成する経路）|
| 凍結済み受入基準 | `docs/acceptance-criteria.md` §受入基準 #17/#18 がシステム要件として凍結済み |

実装技術スタック（Python 3.12 / Pydantic v2 / SQLAlchemy 2.x async / Alembic / pyright strict / pytest）は各 sub-feature の `basic-design.md §依存関係` に集約する。

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|------|---------|---------|
| 1 | Stage に required_gate_roles が設定でき（1件以上）、Workflow の DAG 不変条件を満たす | UC-IRG-001 | TC-UT-IRG-001（[`domain/test-design.md`](domain/test-design.md)） |
| 2 | Stage 完了時に InternalReviewGate が生成され、PENDING 初期状態で全 required_gate_roles の Verdict が未提出の状態になる | UC-IRG-002 | TC-UT-IRG-002 |
| 3 | 各 GateRole エージェントが独立して APPROVED Verdict を提出でき、記録される | UC-IRG-003 | TC-UT-IRG-003 |
| 4 | 全 required_gate_roles が APPROVED を提出すると ALL_APPROVED に遷移する | UC-IRG-004 | TC-UT-IRG-004 |
| 5 | 1 件でも REJECTED が提出されると REJECTED に遷移し、フィードバックコメントが記録される | UC-IRG-005 | TC-UT-IRG-005 |
| 6 | 判断確定前に同一 GateRole から再提出を試みると拒否される（業務ルール R1-B）| UC-IRG-003 | TC-UT-IRG-006 |
| 7 | 判断確定後（ALL_APPROVED / REJECTED）に追加 Verdict を提出しようとすると拒否される（業務ルール R1-C）| UC-IRG-003 | TC-UT-IRG-007 |
| 8 | ALL_APPROVED 後、application 層が次フェーズ（ExternalReviewGate 生成または次 Stage 遷移）を実行できる状態になる（業務ルール R1-D）| UC-IRG-004 | TC-ST-IRG-001（[`system-test-design.md`](system-test-design.md)） |
| 9 | REJECTED 後、application 層が Task を前段 Stage に差し戻せる状態になる（業務ルール R1-E）| UC-IRG-005 | TC-ST-IRG-002 |
| 10 | required_gate_roles が空集合の Stage では InternalReviewGate が生成されない（application 層の責務だが業務ルールとして凍結）| UC-IRG-002 | TC-ST-IRG-003 |
| 11 | フィードバックコメントは 0〜5000 文字有効（空での APPROVED も可）。5001 文字以上は拒否される | UC-IRG-003 | TC-UT-IRG-008 |
| 12 | Gate の状態が再起動跨ぎで保持される（repository sub-feature で担保）| UC-IRG-006 | TC-ST-IRG-004 |

E2E（受入基準 8〜10, 12）は [`system-test-design.md`](system-test-design.md) で詳細凍結。受入基準 1〜7, 11 は domain sub-feature の IT / UT で検証（[`domain/test-design.md`](domain/test-design.md)）。

## 10. 開発者品質基準（CI 担保、業務要求ではない）

| 基準 | 内容 |
|-----|------|
| Q-1 | 型検査 / lint エラーゼロ（CI pyright strict / ruff 警告ゼロ）|
| Q-2 | カバレッジ 90% 以上（domain sub-feature、`pytest --cov=bakufu.domain.internal_review_gate`）|

各 sub-feature の `basic-design.md §モジュール契約` / `test-design.md §カバレッジ基準` で個別に管理する。本書では業務要求のみ凍結。

## 11. 開放論点 (Open Questions)

| ID | 論点 | 起票先 |
|----|-----|-------|
| Q-OPEN-1 | WebSocket でのリアルタイム Verdict 通知形式（GateRole エージェントが Verdict を提出するたびに Gate 状態を push するプロトコル）| `feature/realtime-sync` で凍結 |

設計レビューで凍結済みの論点（GateDecision 3 値 / VerdictDecision 2 値 / GateRole slug パターン / 重複拒否方針）は §7 §確定 R1-A〜G として集約。

## 12. sub-feature 一覧とマイルストーン整理

| sub-feature | 担当 Issue | 状態 |
|------------|-----------|------|
| A: domain | #65（本 Issue）| 進行中 |
| B: repository | 将来起票 | 未着手 |
| C: http-api | 将来起票 | 未着手 |
| D: ui | 将来起票 | 未着手 |

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| `InternalReviewGate.verdicts[*].comment` | GateRole エージェント出力（secret 混入の可能性）| **高**（Repository 永続化前マスキング必須、将来の repository sub-feature で担保）|
| `InternalReviewGate.id` / `task_id` / `stage_id` | UUID 識別子 | 低 |
| `VerdictDecision` | APPROVED / REJECTED（2 値）| 低 |
| `GateDecision` | PENDING / ALL_APPROVED / REJECTED（3 値）| 低 |
| `GateRole` | 審査観点スラッグ（reviewer / ux / security 等）| 低 |

## 14. 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | Verdict 提出は O(N) where N = required_gate_roles 件数（最大想定 10）。1ms 未満 |
| 可用性 | 永続化層 WAL モード + crash safety（[`feature/persistence-foundation`](../persistence-foundation/) 担保）により、書き込み中のクラッシュでも Gate 状態が破損しない |
| 保守性 | pyright strict pass / ruff 警告ゼロ / domain カバレッジ 90% 以上（各 sub-feature の `test-design.md §カバレッジ基準` で管理）|
| 可搬性 | 純 Python のみ（domain 層）。OS / ファイルシステム依存なし |
| セキュリティ | `verdicts[*].comment` に secret が混入し得る。Repository 永続化前マスキング必須（repository sub-feature で実施）。domain 層は raw 保持 |
