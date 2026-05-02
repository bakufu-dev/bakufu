# SC-MVP-001: Vモデル開発室でディレクティブから Task 完走

> シナリオ ID: `SC-MVP-001`
> マイルストーン: MVP M7
> カバーする受入基準: [`acceptance-criteria.md`](../../requirements/acceptance-criteria.md) #1, #2, #3, #4, #5 (UI承認のみ — Discord通知は Phase 2 M6-A), #7, #9, #17, #18
> 戦略: [`../README.md`](../README.md)
> ステータス: 実装中 — Issue #168 (M7)

## 1. ペルソナと前提

| 区分 | 内容 |
|---|---|
| ペルソナ | 個人開発者 CEO（[`personas.md`](../../analysis/personas.md)） |
| 観察主体 | CEO 自身（直接観察）。Discord 通知は Phase 2（M6-A post-MVP）のため本シナリオでは不要 |
| 環境 | bakufu Backend (`127.0.0.1:8000`) + Frontend (`127.0.0.1:5173`) 起動済み（`docker compose up`）、SQLite 初期化済み、Claude Code CLI 認証済み |
| 起動状態 | 既存 Empire・Room・Agent・Task すべてゼロ |

## 2. 業務シナリオ

### Step 1: Empire / Vモデル開発室を 1 クリックで建てる

**観察主体の操作**:
1. UI トップ画面で「Empire 構築」ボタン押下、name="山田の幕府" を入力
2. 構築された Empire 詳細画面で「プリセットから Room を建てる」を選択
3. プリセット一覧から `display_name="V モデル"` (`preset_name="v-model"`) を選択する
4. V-model プリセット定義（14 Stage / 16 Transition）に従い Workflow が Room に割り当てられることを確認する
5. Room に紐づく Agent が各 required_role（LEADER / DEVELOPER / TESTER / REVIEWER）を担当できる状態で登録されていることを確認する

**観察可能事象**:
- Empire 詳細画面に Empire 名・Room 1 件・Workflow 1 件（V モデル、14 Stage）が表示される
- ダッシュボードで Empire 数 = 1, Room 数 = 1 が更新される
- WebSocket で各 Aggregate 作成イベントが配信され、UI が手動リロード不要で更新される

**カバー受入基準**: #1（CRUD）, #2（プリセット）, #9（WebSocket）

### Step 2: CEO directive で Task を起票する

**観察主体の操作**:
1. Vモデル開発室の入力欄に `$ ToDo アプリのドメイン設計をお願い` を入力
2. Enter で送信

**観察可能事象**:
- Task が Room に紐づいて起票される（`status = PENDING → IN_PROGRESS`、`current_stage = "要件定義"`）
- ダッシュボードに Task 件数 = 1 が表示される
- Conversation ログに directive メッセージが記録される

**カバー受入基準**: #3（directive → Task 起票）

### Step 3: Stage が進行し、Agent が deliverable を生成する

**観察主体の操作**:
1. Task 詳細画面で進行を確認（操作不要、Agent が自動進行）
2. Conversation ログタブで各 Agent の発言を観察

**観察可能事象**:
- WORK Stage（要件定義 / 基本設計 / 詳細設計 / コーディング / 単体テスト / 結合テスト / システムテスト）では担当 Agent（LEADER / DEVELOPER / TESTER）が Claude Code CLI 経由で deliverable を生成し、Conversation ログに発言が記録される
- INTERNAL_REVIEW Stage（要件レビュー / 基本設計レビュー / 詳細設計レビュー / 単体テストレビュー / システムテストレビュー / リリース承認）では REVIEWER role の Agent が判定（`APPROVED`）を出し、Transition condition=APPROVED で次 Stage へ遷移する
- 各 Stage 完了時に WebSocket で Task 状態変化がブロードキャストされ、UI が手動リロード不要で `current_stage` 表示を更新する

**カバー受入基準**: #4（Stage 遷移 + deliverable 生成）, #9（WebSocket）

### Step 3.5: 内部レビュー（INTERNAL_REVIEW Stage での REVIEWER Agent 判定）

**観察主体の操作**:
1. WORK Stage の deliverable 生成完了後、InternalReviewGate が自動生成される（V-model プリセットの INTERNAL_REVIEW Stage が担う）
2. REVIEWER role の Agent が deliverable を評価し、`APPROVED` または `REJECTED` の verdict を出す（操作不要）

**観察可能事象**:
- Conversation ログに REVIEWER Agent の判定（`APPROVED` + コメント）が記録される
- 全 verdict APPROVED → Transition condition=APPROVED が発火し、次 WORK Stage へ遷移する（Step 3 の繰り返し）
- 1 件でも REJECTED → Transition condition=REJECTED が発火し、前段 WORK Stage に差し戻す（SC-MVP-002 で詳細検証）
- 本シナリオ（ハッピーパス）では全 INTERNAL_REVIEW Stage が APPROVED で通過し、最終 Stage「リリース承認」（INTERNAL_REVIEW）まで進む
- WebSocket で各 Stage 遷移イベントが配信され、UI が手動リロード不要で更新される

**カバー受入基準**: #17（全 APPROVED で外部レビュー到達 — 本シナリオでは Step 4 の EXTERNAL_REVIEW を指す）, #18（REJECTED → 前段差し戻しは SC-MVP-002 で検証）, #9（WebSocket）

### Step 4: External Review Gate で UI 直接承認

> **Note — Phase 2 (M6-A)**: Discord 通知（`notify_channels` への Webhook 送信）は post-MVP のため本シナリオでは発生しない。CEO は UI を手動で確認して承認する。notify_channels=[] の状態でも Gate 自体は正常に生成・完了できることを確認する（[受入基準 #5 注記参照](../../requirements/acceptance-criteria.md)）。

**観察主体の操作**:
1. V-model プリセットの最終 WORK Stage 群（コーディング / 単体テスト / 結合テスト / システムテスト）が INTERNAL_REVIEW Stage を経由した後、Stage 14「リリース前承認」（`kind=EXTERNAL_REVIEW`）に到達する
2. CEO は UI の Task 詳細画面または Gate 一覧画面で ExternalReviewGate の存在を確認する
3. deliverable を閲覧し、「承認」ボタンを押下する

**観察可能事象**:
- Task 詳細画面に ExternalReviewGate が `status=PENDING` で表示される
- CEO が承認すると Gate が `status=APPROVED` に遷移し、Task は次 Stage（終端）へ進む
- Gate.audit_trail に CEO の操作時刻が記録される
- WebSocket で Gate ステータス変化がブロードキャストされ、UI が手動リロード不要で更新される

**カバー受入基準**: #5 (UI 承認操作 — Discord 通知は Phase 2 M6-A)

### Step 5: 全 Stage 完了で Task が DONE になる

**観察主体の操作**:
1. Stage 14「リリース前承認」（EXTERNAL_REVIEW）を CEO が承認する（Step 4）
2. 終端 Stage がない（Stage 14 が終端）ため、Task は DONE に遷移する

**観察可能事象**:
- Task 詳細画面で `status = "DONE"`、`current_stage = null`
- ダッシュボードで Task 件数（DONE）= 1
- Conversation ログで全 Stage の議論が時系列保存されている
- Task DONE イベントが WebSocket でブロードキャストされ、ダッシュボードが更新される

**カバー受入基準**: #7（DONE 遷移）, #9（WebSocket）

## 3. 関連 feature の system-test-design.md

各 feature の `system-test-design.md` は本シナリオで観察される事象のうち feature 内に閉じる部分を担保する。本シナリオは feature 跨ぎの統合観察を担当する。

| Step | 関連 feature | 関連 e2e-test-design |
|---|---|---|
| Step 1 | empire / room / agent / workflow | `features/empire/system-test-design.md` / `features/room/system-test-design.md` / `features/agent/system-test-design.md` / `features/workflow/system-test-design.md` |
| Step 2 | task / directive | `features/task/system-test-design.md` / `features/directive/system-test-design.md` |
| Step 3 | task / agent / claude-code-adapter | `features/task/system-test-design.md` / `features/claude-code-adapter/system-test-design.md` |
| Step 4 | external-review-gate | `features/external-review-gate/system-test-design.md`（discord-notifier は Phase 2）|
| Step 5 | task / persistence-foundation | `features/task/system-test-design.md` |

注: 上記の各 feature の `system-test-design.md` は階層化（業務概念単位ディレクトリ化）が完了した時点で存在する想定。現状は `empire/system-test-design.md` のみ実存。残りは各 feature の階層化 PR で順次起票。

## 4. 検証手段

| 観点 | 採用方法 |
|---|---|
| UI 操作 | Playwright（Frontend 起動状態で UI 自動操作）|
| Backend API | pytest + httpx（API 経由でも観察可能なシナリオ）|
| Discord 通知 | 該当なし — Phase 2 (M6-A)。notify_channels=[] のため送信処理自体が発生しない |
| Claude Code CLI | テスト用 fake adapter（CLI 起動はせず stub 応答）|
| SQLite | 実 SQLite + テスト用 tempfile DB |
| WebSocket | Playwright で UI イベント発火を観察（`page.routeWebSocket` 活用）|

## 5. 想定実装ファイル

```
backend/tests/acceptance/
└── test_sc_mvp_001_vmodel_fullflow.py     # 本シナリオの自動化（pytest + httpx）
frontend/tests/e2e/
└── sc-mvp-001-vmodel-fullflow.spec.ts     # Playwright で UI 部分
```

実装方針:
- pytest + httpx で Backend 経由のシナリオ進行（Task 起票 / Stage 遷移 / Gate 操作）を駆動
- Playwright で UI からの操作可能性（Empire 構築 / directive 入力 / Gate 承認）+ WebSocket イベント観察
- Claude Code CLI は fake adapter（stub 応答）で代替し、CI 環境でも再現可能にする
- SQLite は テスト用 tempfile DB を都度リセットして再現性を担保する

## 6. カバレッジ基準

- 本シナリオの 5 ステップすべてが自動テストでカバーされる
- 受入基準 #1, #2, #3, #4, #5 (UI承認), #7, #9, #17 の各々がシナリオ内で観察される
- 受入基準 #5 の Discord 通知部分は Phase 2（M6-A post-MVP）のため本シナリオでは対象外
- 本シナリオで観察できない受入基準（#6 差し戻し / #8 再起動 / #10 just check-all / #11〜#16 / #18）は別シナリオ（SC-MVP-002〜008）で担保（[`../README.md §受入基準カバレッジ表`](../README.md)）

## 7. 未決課題（M7 実装時に解決）

- Claude Code CLI の fake adapter 実装方針（response 録画 vs 静的応答 — 再現性のため静的応答を推奨）
- Playwright と pytest の統合（CI ジョブで両方走らせるか、pytest の subprocess で Playwright を起動するか）
- V-model プリセットに Stage 14「リリース前承認」（EXTERNAL_REVIEW, notify_channels=[]）を追加する `workflow_presets.py` 変更が完了していること（[`workflow/feature-spec.md §9 受入基準 #10`](../../features/workflow/feature-spec.md) 参照）
- Discord Bot のテストモード実装方法（Mock サーバ vs 専用テスト Channel）は Phase 2（M6-A）で解決

## 8. 関連設計書

- [`docs/requirements/acceptance-criteria.md`](../../requirements/acceptance-criteria.md) §受入基準
- [`docs/requirements/use-cases.md`](../../requirements/use-cases.md) — 主要ユースケースのシーケンス図（本シナリオの根拠）
- [`docs/acceptance-tests/README.md`](../README.md) — 受入テスト戦略
