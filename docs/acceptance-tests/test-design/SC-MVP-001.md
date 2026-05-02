# SC-MVP-001 テスト設計 — Vモデル開発室でディレクティブから Task 完走

> シナリオ設計書: [`../scenarios/SC-MVP-001-vmodel-fullflow.md`](../scenarios/SC-MVP-001-vmodel-fullflow.md)
> カバー受入基準: #1, #2, #3, #4, #5（UI承認のみ）, #7, #9, #17
> 環境要件・外部I/O依存マップ・バグ記録様式: [`README.md`](./README.md)

---

## 1. テストマトリクス

| ステップ | 検証対象 | 受入基準 # | 自動化ファイル（実装予定） |
|---|---|---|---|
| Step 1: 初期セットアップ | Empire + V-model Room + Workflow が正常構築される | #1, #2 | `backend/tests/acceptance/test_sc_mvp_001_vmodel_fullflow.py` |
| Step 1c: WS 接続確認 | ConnectionIndicator が「接続済み」になる | #9 | `frontend/e2e/05-websocket.spec.ts` TC-E2E-CD-009 |
| Step 2: directive → Task 起票 | `$ directive` 入力後 Task 生成・Stage 設定 | #3 | `backend/tests/acceptance/test_sc_mvp_001_vmodel_fullflow.py` |
| Step 3: Stage 進行 | Stage 遷移順序と deliverable 生成 | #4 | 同上（fake adapter 使用）|
| Step 3.5a: 内部レビュー全 APPROVED | REVIEWER Agent 全 APPROVED → 次 Stage 遷移 | #17 | 同上 |
| Step 3.5b: 内部レビュー 1件 REJECTED | 1 REJECTED → 前段 Stage 差し戻し・ExternalReviewGate 不生成 | #18 | 同上（fake adapter REJECTED 設定）|
| Step 4: External Review Gate 承認 | UI で Gate PENDING → APPROVED, audit_trail 記録 | #5（UI承認のみ） | `frontend/e2e/03-gate-actions.spec.ts` TC-E2E-CD-005 |
| Step 5: Task DONE | 全 Stage 完了 → `status=DONE, current_stage=null` | #7 | `backend/tests/acceptance/test_sc_mvp_001_vmodel_fullflow.py` |
| Step 5: DONE WS 配信 | Task DONE イベント WS ブロードキャスト → UI 更新 | #9 | `frontend/e2e/05-websocket.spec.ts` TC-E2E-CD-009 |

---

## 2. 実行手順と検証観点

### Step 1 — Empire + V-model Room + Workflow を構築する

> **MVP UI スコープ注記（ラムス指摘）**:
> 現行 MVP UI（M6-B: React 実装）は Task 一覧 / Task 詳細 / Gate 詳細 / Directive 新規作成の
> 4 画面のみを提供する。
> 「Empire 構築」「プリセットから Room を建てる」の UI は M8 以降の予定のため、
> **Step 1 は pytest fixture または `bakufu admin` CLI** で事前セットアップし、
> UI 受入テストの前提条件として注入する。

**操作** (pytest fixture):
```python
# backend/tests/acceptance/conftest.py
@pytest.fixture(scope="module")
async def empire_room_setup(client: httpx.AsyncClient):
    """SC-MVP-001 事前セットアップ: Empire + V-model Room + Workflow を構築する"""
    # 1. Empire 作成
    resp = await client.post("/api/empires", json={"name": "山田の幕府"})
    assert resp.status_code == 201
    empire = resp.json()

    # 2. V-model Room をプリセットで作成（Room + Workflow を1回の操作で生成）
    resp = await client.post(
        f"/api/empires/{empire['id']}/rooms",
        json={"preset_name": "v-model", "name": "V モデル開発室"},
    )
    assert resp.status_code == 201
    room = resp.json()

    return {
        "empire_id": empire["id"],
        "room_id": room["id"],
        "workflow_id": room["workflow_id"],
    }
```

または `bakufu admin` CLI での代替手順:
```bash
# Empire 作成
bakufu admin create-empire --name "山田の幕府"
# → empire_id を出力

# V-model Room + Workflow 作成（プリセット指定）
bakufu admin create-room --empire-id {empire_id} --preset v-model --name "V モデル開発室"
# → room_id, workflow_id を出力
```

**検証ポイント**:
- [ ] `GET /api/empires/{empire_id}` → `name = "山田の幕府"`（受入基準 #1: CRUD）
- [ ] `GET /api/rooms/{room_id}` → `preset_name = "v-model"`, `workflow_id != null`（受入基準 #2: プリセット）
- [ ] `GET /api/workflows/{workflow_id}` → Stage 数 14, Transition 数 16（V-model プリセット仕様）
- [ ] WebSocket で Empire / Room 作成イベントが配信される（受入基準 #9）

**失敗トリガー（FAIL 宣言条件）**:
- API が 4xx/5xx を返す
- `workflow_id` が null
- Stage 数が 14 以外（V-model プリセット定義と乖離）

---

### Step 1c — WebSocket 接続を確認する

> 実装済み: `frontend/e2e/05-websocket.spec.ts` TC-E2E-CD-009

**操作** (Playwright):
```typescript
await page.routeWebSocket("ws://localhost:8000/ws", (ws) => {
  ws.connectToServer(); // 実 WS サーバーへ双方向転送
});
await page.goto("/");
await page.waitForLoadState("networkidle");
```

**検証ポイント**:
- [ ] `output[aria-label="サーバーと接続済み"]` が timeout 10s 以内に visible
- [ ] `task.state_changed` WS メッセージ注入後、StatusBadge の aria-label がページリロードなしに更新される

**失敗トリガー**:
- 10s 以内に ConnectionIndicator が「接続済み」にならない

---

### Step 2 — `$` directive で Task を起票する

**操作** (Playwright — UI フロー / pytest + httpx — API フロー):
```typescript
// Playwright: DirectiveNewPage 経由で UI から送信
await page.goto("/directives/new");
await page.waitForLoadState("networkidle");
await page.getByPlaceholder("$ directive を入力...").fill("$ ToDo アプリのドメイン設計をお願い");
await page.getByRole("button", { name: "送信" }).click();
await page.waitForLoadState("networkidle");
```

```python
# pytest + httpx: API 直接呼び出し
resp = await client.post(
    f"/api/rooms/{room_id}/directives",
    json={"content": "$ ToDo アプリのドメイン設計をお願い"},
)
assert resp.status_code == 201
```

**検証ポイント**:
- [ ] `GET /api/rooms/{room_id}/tasks` レスポンス: `total >= 1`
- [ ] 作成された Task の `current_stage` が V-model プリセットの最初の WORK Stage 名（例: `"要件定義"`）
- [ ] 作成された Task の `status = "PENDING"` または `"IN_PROGRESS"`
- [ ] Conversation ログに directive メッセージが `role="user"` で記録されている

**失敗トリガー**:
- Task が生成されない
- `current_stage` が最初の Stage 以外
- Conversation ログに directive が記録されない

---

### Step 3 — Stage が進行し、Agent が deliverable を生成する

> 本ステップは Claude Code CLI fake adapter が必要。M7 自動化で実装。

**検証ポイント** (fake adapter の stub 応答で進行):
- [ ] WORK Stage（要件定義 / 基本設計 / 詳細設計 / コーディング / 単体テスト / 結合テスト / システムテスト）:
  - 各 Stage で担当 Agent（LEADER / DEVELOPER / TESTER）が deliverable を生成
  - Conversation ログに発言が記録される
  - `GET /api/tasks/{task_id}` の `current_stage` が次 Stage に更新される
- [ ] INTERNAL_REVIEW Stage（要件レビュー / 各設計レビュー / リリース承認）:
  - REVIEWER role Agent が `APPROVED` verdict を出す（本ステップは全 APPROVED ハッピーパス）
  - Conversation ログに `APPROVED` + コメントが記録される
- [ ] 各 Stage 完了時に WebSocket で遷移イベントが配信され、UI が手動リロードなしに更新される
- [ ] Stage 遷移タイムアウトは **60s/Stage**（fake adapter 使用時）

**失敗トリガー**:
- Stage が 60s 以内に進行しない
- Stage の遷移順序が V-model プリセット定義と異なる

---

### Step 3.5a — 内部レビュー全 APPROVED → ExternalReviewGate 自動生成

**検証ポイント** (受入基準 #17):
- [ ] 全 INTERNAL_REVIEW Stage が APPROVED で完了する
- [ ] ExternalReviewGate が自動生成される:
  ```
  GET /api/gates?task_id={task_id}
  → items に decision="PENDING" の ExternalReviewGate が存在
  ```
- [ ] Task 詳細 UI に「Gate レビューへ →」リンクが表示される
  （CEO による手動「内部レビュー OK」操作は不要であることを確認）

**失敗トリガー**:
- 全 APPROVED なのに ExternalReviewGate が生成されない（受入基準 #17 違反）
- CEO の手動操作なしに Gate が生成されない（内部レビュー機構が未実装）

---

### Step 3.5b — 内部レビュー 1件 REJECTED → 前段 Stage に差し戻し

> fake adapter を「指定した INTERNAL_REVIEW Stage で REJECTED を返す」設定で起動し、
> 決定論的に差し戻しを再現する。

**検証ポイント** (受入基準 #18):
- [ ] REVIEWER Agent が `REJECTED` + feedback コメントを出す
- [ ] Task の `current_stage` が前段 WORK Stage に戻る
- [ ] ExternalReviewGate は生成されない（`GET /api/gates?task_id=...` → items 空）
- [ ] Conversation ログに feedback コメント付きの `REJECTED` が記録される
- [ ] 担当 Agent が前段 WORK Stage を再実行する（Conversation ログで 2 ラウンド目の発言を確認）

**失敗トリガー**:
- 1 件 REJECTED でも ExternalReviewGate が生成される（受入基準 #17 の前提破壊）
- Task が前段 Stage に戻らない（受入基準 #18 違反）

---

### Step 4 — External Review Gate で承認する

> 実装済み: `frontend/e2e/03-gate-actions.spec.ts` TC-E2E-CD-005
> 受入基準 #5 の Discord 通知部分は Phase 2（M6-A post-MVP）のため検証対象外。
> UI 承認操作のみを検証する。

**操作** (Playwright):
```typescript
// Step 3.5a で生成された ExternalReviewGate の task_id を使用
await page.goto(`/tasks/${task_id}`);
await page.waitForLoadState("networkidle");

// Task 詳細ページから Gate レビューへ遷移（navigate(-1) の履歴を作る）
await page.getByRole("link", { name: "Gate レビューへ →" }).click();
await page.waitForLoadState("networkidle");

await expect(page.getByRole("heading", { name: "外部レビュー Gate" })).toBeVisible();
// Deliverable スナップショット本文の表示を確認
await expect(page.getByText(/deliverable/i)).toBeVisible();

await page.getByRole("button", { name: "承認する" }).click();
await page.waitForURL(/\/tasks\//);
```

**検証ポイント**:
- [ ] Gate 詳細画面に deliverable 全文が表示される（Markdown レンダリング）
- [ ] 承認後: `GET /api/gates/{gate_id}` → `decision = "APPROVED"`
- [ ] 承認後: Task が次 Stage に進む（`current_stage` 更新）
- [ ] `GET /api/gates/{gate_id}` の audit_trail に承認記録:
  `[{event: "approved", decided_at: "...", reviewer: "CEO"}, ...]`

**失敗トリガー**:
- `decision` が `APPROVED` にならない
- audit_trail に記録がない
- 承認後に UI がナビゲートしない

---

### Step 5 — 全 Stage 完了で Task が DONE になる

**操作**: 残りの External Review Stage を順次承認（Step 4 を繰り返し）。

**検証ポイント** (受入基準 #7):
- [ ] 全 Stage 完了後: `GET /api/tasks/{task_id}` → `status = "DONE"`, `current_stage = null`
- [ ] UI タスク詳細画面の StatusBadge: `aria-label="DONE"`
- [ ] Conversation ログに全 Stage の議論が時系列で保持されている
- [ ] WebSocket で Task DONE イベントが配信され、ダッシュボードが手動リロードなしに更新される:
  - TC-E2E-CD-009 で `task.state_changed` イベント後の StatusBadge 更新を確認済み

**失敗トリガー**:
- `status` が `DONE` にならない
- `current_stage` が null にならない

---

## 3. 合否判定基準

本シナリオは以下の**すべて**が満たされた場合に **PASS** とする:

| 判定基準 | 対応受入基準 | 根拠 |
|---|---|---|
| Step 1: Empire が正常に作成される | #1 | `GET /api/empires` |
| Step 1: V-model プリセットで Room + Workflow（14 Stage）が生成される | #2 | `GET /api/rooms` + `GET /api/workflows` |
| Step 1c: WS 接続後 ConnectionIndicator が「接続済み」になる | #9 | TC-E2E-CD-009 |
| Step 2: `$` directive で Task が最初の Stage で起票される | #3 | `GET /api/tasks` |
| Step 3: WORK Stage が定義順に進行し deliverable が生成される | #4 | Conversation ログ |
| Step 3.5a: 全 APPROVED → ExternalReviewGate 自動生成（手動操作なし） | #17 | `GET /api/gates` |
| Step 3.5b: 1件 REJECTED → 前段 Stage 差し戻し・ExternalReviewGate 不生成 | #18 | `GET /api/tasks current_stage` |
| Step 4: Gate 承認で `decision=APPROVED` かつ audit_trail に記録される | #5（UI承認のみ） | `GET /api/gates` |
| Step 5: 全 Stage 完了で `status=DONE, current_stage=null` になる | #7 | `GET /api/tasks` |
| 全 Stage 遷移で手動リロードなしに UI が更新される | #9 | WS イベント観察 |

1 項目でも FAIL した場合は本シナリオを **FAIL** とし、`BUG-AT-NNN` 形式でバグレポートを起票する。

Discord 通知（受入基準 #5 の通知部分）は Phase 2（M6-A post-MVP）まで検証対象外。

---

## 4. 自動化実装ファイル対応表

| ステップ | テストレベル | 実装ファイル | 実装状態 |
|---|---|---|---|
| Step 1c, 5 (WS) | 受入テスト（UI） | `frontend/e2e/05-websocket.spec.ts` | **実装済み** — TC-E2E-CD-009/010 |
| Step 4 (Gate 承認) | 受入テスト（UI） | `frontend/e2e/03-gate-actions.spec.ts` | **実装済み** — TC-E2E-CD-005 |
| Step 1〜5 全体（API） | 受入テスト（Backend） | `backend/tests/acceptance/test_sc_mvp_001_vmodel_fullflow.py` | **未実装** — M7 で起票 |
