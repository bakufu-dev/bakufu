# SC-MVP-001: Vモデル開発室でディレクティブから Task 完走

> シナリオ ID: `SC-MVP-001`
> マイルストーン: MVP M7
> カバーする受入基準: [`acceptance-criteria.md`](../../requirements/acceptance-criteria.md) #1, #2, #3, #4, #5, #7, #9, #17, #18
> 戦略: [`../README.md`](../README.md)
> ステータス: 設計済 / 実装は M7 で起票

## 1. ペルソナと前提

| 区分 | 内容 |
|---|---|
| ペルソナ | 個人開発者 CEO（[`personas.md`](../../analysis/personas.md)） |
| 観察主体 | CEO 自身（直接観察）+ Owner Reviewer（CEO 兼任、Discord 通知経由） |
| 環境 | bakufu Backend (`127.0.0.1:8000`) + Frontend 起動済み、SQLite 初期化済み、Discord Bot 認証済み、Claude Code CLI 認証済み |
| 起動状態 | 既存 Empire・Room・Agent・Task すべてゼロ |

## 2. 業務シナリオ

### Step 1: Empire / Vモデル開発室を 1 クリックで建てる

**観察主体の操作**:
1. UI トップ画面で「Empire 構築」ボタン押下、name="山田の幕府" を入力
2. 構築された Empire 詳細画面で「プリセットから Room を建てる」を選択
3. プリセット一覧から「Vモデル開発室」を選び、Agent 5 体（leader / developer / tester / reviewer / ux）が自動採用されることを確認

**観察可能事象**:
- Empire 詳細画面に Empire 名・Room 1 件（Vモデル開発室）・Agent 5 件が表示される
- ダッシュボードで Empire 数 = 1, Room 数 = 1, Agent 数 = 5
- WebSocket で各 Aggregate 作成イベントが配信され、UI が手動リロード不要で更新される

**カバー受入基準**: #1（CRUD）, #2（プリセット）, #9（WebSocket）

### Step 2: CEO directive で Task を起票する

**観察主体の操作**:
1. Vモデル開発室の入力欄に `$ ToDo アプリのドメイン設計をお願い` を入力
2. Enter で送信

**観察可能事象**:
- Task が Vモデル開発室に紐づいて起票される（`current_stage = "requirements-analysis"`）
- ダッシュボードに Task 件数 = 1 が表示される
- Conversation ログに directive メッセージが記録される

**カバー受入基準**: #3（directive → Task 起票）

### Step 3: Stage が進行し、Agent が deliverable を生成する

**観察主体の操作**:
1. Task 詳細画面で進行を確認（操作不要、Agent が自動進行）
2. Conversation ログタブで各 Agent の発言を観察

**観察可能事象**:
- Stage 遷移が `requirements-analysis → requirements → basic-design → detailed-design → test-design → external-review` の順で進む
- 各 Stage で担当 Agent（Claude Code CLI 経由）が deliverable を生成
- Conversation ログに各 Agent の発言が時系列で表示される（Stage ごとに分離）
- 各 Stage 完了時に WebSocket で UI 更新（手動リロード不要）

**カバー受入基準**: #4（Stage 遷移 + deliverable 生成）, #9（WebSocket）

### Step 3.5: 内部レビュー（GateRole 並列、観点別独立判断）

**観察主体の操作**:
1. Stage の deliverable 生成完了後、Workflow 定義に従う GateRole エージェント（Vモデル開発室プリセットの場合は Reviewer / UX / Security の 3 ロール）が並列に内部レビューを開始
2. 各 GateRole エージェントが独立に判定（互いの意見を見ずに判断、ai-team の `_extract_verdict` 機構の bakufu 移植）

**観察可能事象**:
- Conversation ログに各 GateRole エージェントの判定（`APPROVED` / `REJECTED` + コメント）が並列で記録される
- 全 GateRole APPROVED の場合 → Stage が自動的に EXTERNAL_REVIEW に遷移し、ExternalReviewGate が生成される（CEO は手動で「内部レビュー OK」を出す必要がない）
- 1 人でも REJECTED の場合 → Task は前段 Stage に戻り、該当 Stage 担当 Agent が feedback 付きで再依頼される
- WebSocket で内部レビュー進捗（各 GateRole の verdict 提出）が UI 更新される

**カバー受入基準**: #17（全 GateRole APPROVED で外部レビュー到達）, #18（1 人 REJECTED で前段差し戻し）, #9（WebSocket）

### Step 4: External Review Gate で Discord 通知 → 承認

**観察主体の操作**:
1. EXTERNAL_REVIEW Stage 到達時、CEO の Discord に通知が届く
2. Discord 通知のリンクから UI に遷移
3. deliverable を閲覧し、「承認」ボタン押下

**観察可能事象**:
- Discord 通知メッセージに deliverable サマリと UI URL が含まれる
- UI で deliverable 全文が表示される
- 承認時、Gate ステータスが `PENDING → APPROVED` に遷移
- Gate.audit_trail に CEO の閲覧時刻・承認時刻が記録される
- Task は次 Stage に進む

**カバー受入基準**: #5（外部レビュー UI + Discord 通知）

### Step 5: 全 Stage 完了で Task が DONE になる

**観察主体の操作**:
1. 残りの External Review Stage を順次承認（Vモデルでは複数の External Review がある場合は同様の操作を繰り返し）
2. 全 Stage 完了時、Task ステータスが `DONE` に変わる

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
| Step 4 | external-review-gate / discord-notifier | `features/external-review-gate/system-test-design.md` / `features/discord-notifier/system-test-design.md` |
| Step 5 | task / persistence-foundation | `features/task/system-test-design.md` |

注: 上記の各 feature の `system-test-design.md` は階層化（業務概念単位ディレクトリ化）が完了した時点で存在する想定。現状は `empire/system-test-design.md` のみ実存。残りは各 feature の階層化 PR で順次起票。

## 4. 検証手段

| 観点 | 採用方法 |
|---|---|
| UI 操作 | Playwright（Frontend 起動状態で UI 自動操作） |
| Backend API | pytest + httpx（API 経由でも観察可能なシナリオ） |
| Discord 通知 | Discord Bot のテストモード（Mock サーバ または専用テスト Channel）|
| Claude Code CLI | テスト用 fake adapter（CLI 起動はせず stub 応答）|
| SQLite | 実 SQLite + テスト用 tempfile DB |
| WebSocket | Playwright で UI イベント発火を観察 |

## 5. 想定実装ファイル（M7 で起票）

```
backend/tests/acceptance/
└── test_sc_mvp_001_vmodel_fullflow.py     # 本シナリオの自動化（pytest + httpx）
frontend/tests/e2e/
└── sc-mvp-001-vmodel-fullflow.spec.ts     # Playwright で UI 部分
```

実装方針:
- pytest + httpx で Backend 経由のシナリオ進行を駆動
- Playwright で UI からの操作可能性 + WebSocket イベント観察
- Backend / Frontend 両方をテスト harness で起動し、両側から観察

## 6. カバレッジ基準

- 本シナリオの 5 ステップすべてが自動テストでカバーされる
- mvp-scope.md §受入基準 #1, #2, #3, #4, #5, #7, #9 の各々がシナリオ内で観察される
- 本シナリオで観察できない受入基準（#6 差し戻し / #8 再起動 / #10 just check-all / #11〜#16）は別シナリオ（SC-MVP-002〜008）で担保（[`../README.md §受入基準カバレッジ表`](../README.md)）

## 7. 未決課題（M7 起票時に解決）

- Discord Bot のテストモード実装方法（Mock サーバ vs 専用テスト Channel の選択）
- Claude Code CLI の fake adapter 実装方針（response 録画 vs 静的応答）
- Playwright と pytest の統合（CI ジョブで両方走らせるか、pytest の subprocess で Playwright を起動するか）
- Vモデル開発室プリセットの External Review が複数 Stage に存在する場合の Step 4 の繰り返し戦略

## 8. 関連設計書

- [`docs/requirements/acceptance-criteria.md`](../../requirements/acceptance-criteria.md) §受入基準
- [`docs/requirements/use-cases.md`](../../requirements/use-cases.md) — 主要ユースケースのシーケンス図（本シナリオの根拠）
- [`docs/acceptance-tests/README.md`](../README.md) — 受入テスト戦略
