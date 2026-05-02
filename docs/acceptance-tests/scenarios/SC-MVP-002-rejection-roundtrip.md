# SC-MVP-002: INTERNAL_REVIEW 差し戻し → 再提出 → 複数ラウンド完走

> シナリオ ID: `SC-MVP-002`
> マイルストーン: MVP M7
> カバーする受入基準: [`acceptance-criteria.md`](../../requirements/acceptance-criteria.md) #6, #18
> 戦略: [`../README.md`](../README.md)
> ステータス: 実装中 — Issue #168 (M7)

## 1. ペルソナと前提

| 区分 | 内容 |
|---|---|
| ペルソナ | 個人開発者 CEO（[`personas.md`](../../analysis/personas.md)）、観察主体として操作の起点 |
| 観察主体 | CEO 自身（直接観察）。差し戻し〜再提出の挙動は Agent 自動進行を観察する |
| 環境 | bakufu Backend (`127.0.0.1:8000`) + Frontend (`127.0.0.1:5173`) 起動済み（`docker compose up`）、SQLite 初期化済み、Claude Code CLI fake adapter 設定済み |
| 起動状態 | SC-MVP-001 Step 1 完了状態（Empire + V-model Room + Agent 登録済み）を前提とする。または本シナリオ独立起動用の初期セットアップを事前 fixture で注入する |

## 2. 業務シナリオ

### Step 1: directive 投入 → 要件定義 Stage 開始

**観察主体の操作**:
1. Room の入力欄に directive を入力し（例: `$ 差し戻しシナリオ用 TodoApp 要件定義`）送信する
2. Task 詳細画面を開き、Stage 進行を観察する

**観察可能事象**:
- Task が起票され `status=IN_PROGRESS`、`current_stage="要件定義"` になる
- LEADER role Agent が deliverable を生成し、Conversation ログに発言が記録される
- 「要件定義」Stage 完了後、Transition condition=APPROVED で「要件レビュー」（INTERNAL_REVIEW）Stage に遷移する

**カバー受入基準**: #3（directive → Task 起票）

### Step 2: 要件レビュー Stage で REVIEWER Agent が REJECTED を出す

**観察主体の操作**:
1. Task 詳細画面で「要件レビュー」Stage が進行中であることを確認する（操作不要）
2. Conversation ログで REVIEWER Agent の判定を観察する

> **テスト制御**: fake adapter を「1ラウンド目は必ず REJECTED を返す」設定で起動し、決定論的に差し戻しを再現する

**観察可能事象**:
- REVIEWER Agent が `REJECTED` + feedback コメントを Conversation ログに出力する
- Transition condition=REJECTED が発火し、Task の `current_stage` が「要件レビュー」から「要件定義」へ戻る
- WebSocket で Stage 差し戻しイベントがブロードキャストされ、UI が手動リロード不要で `current_stage="要件定義"` を表示する
- InternalReviewGate の audit_trail にラウンド 1 の verdict（REJECTED）と feedback コメントが記録される

**カバー受入基準**: #18（REJECTED → 前段 Stage 差し戻し）

### Step 3: 差し戻し後 — Agent が feedback を考慮して再提出

**観察主体の操作**:
1. Task 詳細画面で「要件定義」Stage が再開されていることを確認する（操作不要）
2. Conversation ログで 2ラウンド目の Agent 発言を観察する

**観察可能事象**:
- LEADER role Agent が「ラウンド 1 の feedback を考慮した改訂版 deliverable」を生成し、Conversation ログに 2ラウンド目の発言が記録される
- Conversation ログ上でラウンド 1 とラウンド 2 の発言が時系列で区別できる（audit_trail 観察）
- 改訂版 deliverable 生成完了後、再び「要件レビュー」Stage に遷移する

**カバー受入基準**: #4（Stage 遷移）, #6（差し戻し後の再生成経路）

### Step 4: 2 ラウンド目の要件レビューで APPROVED → 次 Stage へ

**観察主体の操作**:
1. Task 詳細画面で 2 ラウンド目の「要件レビュー」Stage が進行中であることを確認する（操作不要）

> **テスト制御**: fake adapter を「2ラウンド目以降は APPROVED を返す」設定にする

**観察可能事象**:
- REVIEWER Agent が `APPROVED` を Conversation ログに出力する
- Transition condition=APPROVED が発火し、Task の `current_stage` が「基本設計」Stage へ進む
- WebSocket で Stage 遷移イベントがブロードキャストされ、UI が更新される
- 2 ラウンド目の APPROVED が audit_trail に追記される

**カバー受入基準**: #17（全 APPROVED で次 Stage 到達）

### Step 5: Gate 履歴（audit_trail）の完全性を確認する

**観察主体の操作**:
1. Task 詳細画面の Gate 履歴タブ（または Conversation ログ）を参照する

**観察可能事象**:
- InternalReviewGate の audit_trail に以下がすべて記録されている:
  - ラウンド 1: verdict=REJECTED、feedback コメント、タイムスタンプ
  - ラウンド 2: verdict=APPROVED、タイムスタンプ
- 2 ラウンドの記録が削除・上書きされておらず、完全に保持されている

**カバー受入基準**: #6（複数ラウンドの Gate 履歴保持）

## 3. 関連 feature の system-test-design.md

各 feature の `system-test-design.md` は本シナリオで観察される事象のうち feature 内に閉じる部分を担保する。本シナリオは feature 跨ぎの統合観察を担当する。

| Step | 関連 feature | 関連 system-test-design |
|---|---|---|
| Step 1 | task / stage-executor | `features/task/system-test-design.md` / `features/stage-executor/system-test-design.md` |
| Step 2 | internal-review-gate / stage-executor | `features/internal-review-gate/system-test-design.md` / `features/stage-executor/system-test-design.md` |
| Step 3 | task / stage-executor | `features/task/system-test-design.md` |
| Step 4 | internal-review-gate | `features/internal-review-gate/system-test-design.md` |
| Step 5 | internal-review-gate | `features/internal-review-gate/system-test-design.md` |

注: 上記の各 feature の `system-test-design.md` は階層化が完了した時点で存在する想定。現状実存しないものは各 feature 階層化 PR で順次起票する。

## 4. 検証手段

| 観点 | 採用方法 |
|---|---|
| UI 操作 | Playwright（Frontend 起動状態で UI 自動操作）|
| Backend API | pytest + httpx（Task / Gate API 経由で状態確認）|
| Claude Code CLI | テスト用 fake adapter（1ラウンド目 REJECTED / 2ラウンド目以降 APPROVED を返す決定論的 stub）|
| SQLite | 実 SQLite + テスト用 tempfile DB（都度リセット）|
| WebSocket | Playwright で Stage 差し戻しイベント受信を確認（`aria-label` 観察）|

## 5. 想定実装ファイル

```
backend/tests/acceptance/
└── test_sc_mvp_002_rejection_roundtrip.py   # 本シナリオの自動化（pytest + httpx）
frontend/tests/e2e/
└── sc-mvp-002-rejection-roundtrip.spec.ts   # Playwright で UI 部分（差し戻し State 遷移表示）
```

実装方針:
- fake adapter を「ラウンド番号ベース」で制御し、ラウンド 1 は REJECTED、ラウンド 2 以降は APPROVED を返す
- pytest + httpx で Gate audit_trail を直接 API 取得して assert する
- Playwright で UI 上の `current_stage` 更新を WebSocket イベントで観察する

## 6. カバレッジ基準

- 本シナリオの 5 ステップすべてが自動テストでカバーされる
- `acceptance-criteria.md` の受入基準 #6（複数ラウンドの Gate 履歴保持）, #18（REJECTED → 前段差し戻し）の各々がシナリオ内で観察される
- 本シナリオは差し戻しの最小ケース（1回 REJECTED → 2回目 APPROVED）のみ対象とする。複数回差し戻しの境界値は YAGNI により Phase 2 で追加

## 7. 未決課題（M7 実装時に解決）

- fake adapter の「ラウンド番号ベース制御」の実装方式（環境変数 / config file / spy パターン）
- SC-MVP-001 との fixture 共有方針（Empire / Room / Agent 初期化の重複排除）
- Playwright での `audit_trail` 表示 UI の確認方法（UI に audit_trail が表示されない場合は Backend API 直接確認で代替）

## 8. 関連設計書

- [`docs/requirements/acceptance-criteria.md`](../../requirements/acceptance-criteria.md) §受入基準 #6, #18
- [`docs/requirements/use-cases.md`](../../requirements/use-cases.md) — 主要ユースケース
- [`docs/acceptance-tests/README.md`](../README.md) — 受入テスト戦略
- [`docs/acceptance-tests/scenarios/SC-MVP-001-vmodel-fullflow.md`](SC-MVP-001-vmodel-fullflow.md) — ハッピーパス完走シナリオ（本シナリオの前提設定を共有）
- [`docs/features/stage-executor/feature-spec.md`](../../features/stage-executor/feature-spec.md) — Stage 実行ロジック
