# 受入テスト設計書 — SC-MVP-001 / SC-MVP-002

> 本書の種別: 受入テスト設計書（Vモデル最上位）
> 対象シナリオ: SC-MVP-001, SC-MVP-002
> 凍結バージョン: Issue #168 (M7) — 2026-05-02
> レビュー担当: ヘルスバーグ（品質）/ Tabriz（セキュリティ）/ ラムス（UX）
> ステータス: **凍結**

---

## 1. 本書の位置付け

本書は [`docs/acceptance-tests/README.md`](./README.md) で定義した受入テスト戦略のうち、
**SC-MVP-001** と **SC-MVP-002** の「実行手順・検証観点・合否判定基準」を凍結する。

Vモデルでの位置付け:

```
要求分析 → docs/requirements/acceptance-criteria.md
    ↕
受入テスト → docs/acceptance-tests/scenarios/SC-MVP-NNN.md  ← シナリオ設計書
                                                              ← 本書（実行手順・合否判定基準）
```

本書は **実行手順レベルまで落とし込む**。シナリオ設計書（SC-MVP-NNN.md）が
「何を観察するか」を定義するのに対し、本書は「どう操作・検証するか」を定義する。

---

## 2. テスト環境要件

### 2.1 必要サービス

| サービス | アドレス | 起動方法 |
|---|---|---|
| Backend (FastAPI) | `http://localhost:8000` | `docker compose up bakufu-backend-1` |
| Frontend (Vite) | `http://localhost:5173` | `docker compose up bakufu-frontend-1` |
| WebSocket | `ws://localhost:8000/ws` | Backend に内包（`/ws` エンドポイント） |
| SQLite | `/app/data/bakufu.db` | Backend 起動時に自動マイグレーション |

### 2.2 自動化ツール

| テストレベル | ツール | 実行コマンド |
|---|---|---|
| 受入テスト（UI + WebSocket） | Playwright (`@playwright/test` v1.59.1) | `cd frontend && npx playwright test` |
| 受入テスト（Backend API 経由） | pytest + httpx | `cd backend && python -m pytest tests/acceptance/` |
| 結合テスト | pytest + httpx | `cd backend && python -m pytest tests/integration/` |
| 全テスト一括 | just | `just check-all` |

### 2.3 シードデータ前提（E2E テスト用）

Playwright テストは以下の定数（`frontend/e2e/helpers.ts`）を使用する。
シード投入が未完了の場合テストは失敗する。

| 定数 | UUID | 説明 |
|---|---|---|
| `EMPIRE_ID` | `00000000-...0001` | E2E テスト用 Empire |
| `ROOM_ID` | `e2e00000-...0031` | E2E テスト用 Room |
| `TASK_PENDING_ID` | `e2e00000-...0051` | status=PENDING の Task（WS テスト用） |
| `TASK_APPROVE_ID` | `e2e00000-...0055` | Gate 承認テスト用 Task |
| `TASK_REJECT_ID` | `e2e00000-...0056` | Gate 差し戻しテスト用 Task |
| `GATE_APPROVE_ID` | `e2e00000-...0072` | 承認テスト用 Gate (PENDING) |
| `GATE_REJECT_ID` | `e2e00000-...0073` | 差し戻しテスト用 Gate (PENDING) |

再実行時のリセット手順:
```sql
-- backend コンテナ内で実行
sqlite3 /app/data/bakufu.db "UPDATE external_review_gates
  SET decision='PENDING', feedback_text='', decided_at=NULL
  WHERE id IN (
    'e2e00000-0000-0000-0000-000000000071',
    'e2e00000-0000-0000-0000-000000000072',
    'e2e00000-0000-0000-0000-000000000073'
  );"
```

---

## 3. 外部 I/O 依存マップ

| 外部 I/O | SC-MVP-001 | SC-MVP-002 | Fixture / Mock 状態 |
|---|---|---|---|
| SQLite (`bakufu.db`) | 依存（全 Aggregate 永続化） | 依存（Gate 履歴） | シードデータ投入済み（`e2e/helpers.ts` 定数参照） |
| WebSocket (`/ws`) | 依存（リアルタイム更新観察） | 依存（Gate 状態更新配信） | Playwright `routeWebSocket` で実サーバーへ転送（characterization 済み） |
| Claude Code CLI | 依存（deliverable 生成） | 依存（再生成） | fake adapter（CLI 起動不要、stub 応答）— SC-MVP-001/002 自動化 M7 で実装 |
| Discord Bot | 依存（#5 外部レビュー通知） | 依存（再提出通知） | **Phase 2（M6-A post-MVP）** — 本 M7 自動化では除外。UI 承認のみ検証 |
| 現在時刻 | 依存（`occurred_at`、`audit_trail`） | 依存 | UTC `datetime.now()` を使用。freeze は不要（精度検証なし） |

---

## 4. SC-MVP-001: Vモデル開発室でディレクティブから Task 完走

### 4.1 シナリオ概要

> シナリオ設計書: [`scenarios/SC-MVP-001-vmodel-fullflow.md`](./scenarios/SC-MVP-001-vmodel-fullflow.md)
> カバー受入基準: #1, #2, #3, #4, #5（UI承認のみ）, #7, #9, #17, #18

CEO が V モデル開発室を建て、directive を送信し、AI Agent が各 Stage を進行し、
内部レビュー（全 GateRole APPROVED）→ ExternalReview → 承認 → Task DONE に至る業務フローを
End-to-End で検証する。

### 4.2 テストマトリクス

| ステップ | 検証対象 | 受入基準 # | 自動化ファイル（実装予定） |
|---|---|---|---|
| Step 1a: Empire 作成 | `POST /api/empires` 201, UI に Empire 名表示 | #1 | `backend/tests/acceptance/test_sc_mvp_001_vmodel_fullflow.py` |
| Step 1b: Vモデル開発室 作成 | プリセットで Room + Agent 5体が1回の操作で生成 | #2 | 同上 |
| Step 1c: WebSocket 即時更新 | Empire/Room/Agent 作成時 WS イベント配信 → UI 更新 | #9 | `frontend/e2e/05-websocket.spec.ts` TC-E2E-CD-009 |
| Step 2: directive → Task 起票 | `$ directive` 入力後 `current_stage=requirements-analysis` のTask 生成 | #3 | `backend/tests/acceptance/test_sc_mvp_001_vmodel_fullflow.py` |
| Step 3: Stage 進行 | Stage 遷移順序と deliverable 生成を各 Stage で観察 | #4 | 同上（fake adapter 使用） |
| Step 3.5: 内部レビュー全 APPROVED | 全 GateRole APPROVED → ExternalReviewGate 自動生成 | #17 | 同上 |
| Step 3.5: 内部レビュー 1件 REJECTED | 1 REJECTED → Task が前段 Stage に差し戻し | #18 | 同上 |
| Step 4: External Review Gate 承認 | UI で Gate PENDING → APPROVED、audit_trail 記録 | #5（UI承認のみ） | `frontend/e2e/03-gate-actions.spec.ts` TC-E2E-CD-005 |
| Step 5: Task DONE | 全 Stage 完了 → `status=DONE`, `current_stage=null` | #7 | `backend/tests/acceptance/test_sc_mvp_001_vmodel_fullflow.py` |
| Step 5: DONE WS 配信 | Task DONE イベント WS ブロードキャスト → ダッシュボード更新 | #9 | `frontend/e2e/05-websocket.spec.ts` TC-E2E-CD-009 |

### 4.3 実行手順と検証観点

#### Step 1a — Empire を 1 クリックで作成する

**操作** (Playwright):
```typescript
await page.goto("/");
await page.getByRole("button", { name: "Empire 構築" }).click();
await page.getByLabel("name").fill("山田の幕府");
await page.getByRole("button", { name: "作成" }).click();
await page.waitForLoadState("networkidle");
```

**検証ポイント**:
- [ ] `GET /api/empires` レスポンス: `total >= 1`、items に `name="山田の幕府"` を含む
- [ ] UI に Empire 名「山田の幕府」が表示される
  - aria-label または heading で確認

**失敗トリガー（FAIL 宣言条件）**:
- API が 4xx / 5xx を返す
- UI に Empire 名が表示されない（networkidle 後 5s 以内）

---

#### Step 1b — Vモデル開発室プリセットで Room + Agent 5体を作成する

**操作** (Playwright):
```typescript
await page.getByRole("button", { name: "プリセットから Room を建てる" }).click();
await page.getByText("Vモデル開発室").click();
await page.getByRole("button", { name: "作成" }).click();
await page.waitForLoadState("networkidle");
```

**検証ポイント**:
- [ ] `GET /api/rooms?empire_id={empire_id}` レスポンス: `total = 1`
- [ ] `GET /api/agents?room_id={room_id}` レスポンス: `total = 5`
  - roles に `leader / developer / tester / reviewer / ux` を含む（順不同）
- [ ] UI に Room 1 件・Agent 5 件が表示される

**失敗トリガー**:
- Room 数が 1 以外
- Agent 数が 5 以外
- roles に必須ロールが欠ける

---

#### Step 1c — WebSocket リアルタイム更新を確認する

> 実装済み: `frontend/e2e/05-websocket.spec.ts` TC-E2E-CD-009

**操作** (Playwright):
```typescript
await page.routeWebSocket("ws://localhost:8000/ws", (ws) => {
  ws.connectToServer();
});
await page.goto("/");
await page.waitForLoadState("networkidle");
```

**検証ポイント**:
- [ ] `output[aria-label="サーバーと接続済み"]` が timeout 10s 以内に visible
- [ ] task.state_changed WS メッセージ注入後、StatusBadge の aria-label がページリロードなしに更新される

---

#### Step 2 — `$` directive で Task を起票する

**操作** (Playwright / API):
```typescript
// UI 操作の場合
await page.getByPlaceholder("$ directive を入力...").fill("$ ToDo アプリのドメイン設計をお願い");
await page.keyboard.press("Enter");
await page.waitForLoadState("networkidle");

// API の場合 (pytest + httpx)
resp = await client.post(f"/api/rooms/{room_id}/directives",
    json={"content": "$ ToDo アプリのドメイン設計をお願い"})
assert resp.status_code == 201
```

**検証ポイント**:
- [ ] `GET /api/rooms/{room_id}/tasks` レスポンス: `total = 1`
- [ ] 取得した Task の `current_stage = "requirements-analysis"`
- [ ] 取得した Task の `status = "PENDING"` または `"IN_PROGRESS"`
- [ ] Conversation ログに directive メッセージが `role="user"` で記録されている

**失敗トリガー**:
- Task が生成されない
- `current_stage` が `requirements-analysis` 以外

---

#### Step 3 — Stage が進行し、Agent が deliverable を生成する

> 本ステップは Claude Code CLI fake adapter が必要。M7 自動化で実装。

**検証ポイント** (非自動化部分は手動観察):
- [ ] Stage 遷移が以下の順で進む（テスト環境では fake adapter の stub 応答で進行）:
  ```
  requirements-analysis → requirements → basic-design →
  detailed-design → test-design → [internal-review] → external-review
  ```
- [ ] 各 Stage 完了後に `GET /api/tasks/{task_id}` の `current_stage` が更新される
- [ ] Conversation ログに各 Stage 担当 Agent の発言が記録される
- [ ] WebSocket で Stage 遷移イベントが配信され、UI が手動リロードなしに更新される

**失敗トリガー**:
- Stage が 60s 以内に進行しない（タイムアウト）
- Stage 順序が仕様と異なる

---

#### Step 3.5a — 内部レビュー全 GateRole APPROVED → ExternalReviewGate 自動生成

**検証ポイント** (受入基準 #17):
- [ ] Workflow 定義の全 GateRole（`reviewer / ux / security`）が `APPROVED` を提出
- [ ] Conversation ログに各 GateRole の `APPROVED` verdict が並列で記録される
- [ ] ExternalReviewGate が自動生成される:
  ```
  GET /api/gates?task_id={task_id}
  → items に decision="PENDING" の gate が存在
  ```
- [ ] Task の UI に「Gate レビューへ →」リンクが表示される（CEO による手動「内部レビュー OK」は不要）

**失敗トリガー**:
- ExternalReviewGate が生成されない（全 APPROVED なのに生成されない場合は #17 違反）
- CEO による手動承認なしに Gate が生成されない（= 内部レビュー機構が未実装）

---

#### Step 3.5b — 内部レビュー 1件 REJECTED → 前段 Stage に差し戻し

**検証ポイント** (受入基準 #18):
- [ ] いずれか 1 GateRole が `REJECTED` を提出した場合:
  - Task の `current_stage` が前段 Stage に戻る
  - ExternalReviewGate は生成されない
  - Conversation ログに feedback コメント付きの `REJECTED` が記録される
  - 担当 Agent が前段 Stage を再実行する

**失敗トリガー**:
- 1 件 REJECTED でも ExternalReviewGate が生成される（= #17 前提を破壊）
- Task が前段 Stage に戻らない

---

#### Step 4 — External Review Gate で承認する

> 実装済み: `frontend/e2e/03-gate-actions.spec.ts` TC-E2E-CD-005

**操作** (Playwright):
```typescript
await page.goto(`/tasks/${task_id}`);
await page.getByRole("link", { name: "Gate レビューへ →" }).click();
await page.waitForLoadState("networkidle");
await expect(page.getByRole("heading", { name: "外部レビュー Gate" })).toBeVisible();
await page.getByRole("button", { name: "承認する" }).click();
await page.waitForURL(/\/tasks\//);
```

**検証ポイント**:
- [ ] Gate 詳細画面に deliverable 全文が表示される（`getByText("E2E Test Deliverable")` visible）
- [ ] 承認後: `GET /api/gates/{gate_id}` → `decision = "APPROVED"`
- [ ] 承認後: Task が次 Stage に進む（`current_stage` 更新）
- [ ] audit_trail に CEO の閲覧時刻・承認時刻が記録される:
  ```
  GET /api/gates/{gate_id}
  → audit_trail: [{event: "viewed", ...}, {event: "approved", ...}]
  ```

**失敗トリガー**:
- `decision` が `APPROVED` にならない
- audit_trail に記録がない
- 承認後に UI がナビゲートしない

---

#### Step 5 — 全 Stage 完了で Task が DONE になる

**操作**: 残りの External Review Stage を順次承認（Step 4 を繰り返し）。

**検証ポイント** (受入基準 #7):
- [ ] 全 Stage 完了後: `GET /api/tasks/{task_id}` → `status = "DONE"`, `current_stage = null`
- [ ] UI タスク詳細画面の StatusBadge: `aria-label="DONE"`
- [ ] UI ダッシュボードのタスク一覧に DONE タスクが 1 件以上表示される
- [ ] Conversation ログに全 Stage の議論が時系列で保持されている
- [ ] WebSocket で Task DONE イベントが配信され、ダッシュボードが手動リロードなしに更新される

**失敗トリガー**:
- `status` が `DONE` にならない
- `current_stage` が null にならない

### 4.4 合否判定基準

本シナリオは以下の**すべて**が満たされた場合に **PASS** とする:

| 判定基準 | 対応受入基準 | 根拠 |
|---|---|---|
| Step 1a: Empire が API / UI に正常に反映される | #1 | `GET /api/empires` + UI 表示 |
| Step 1b: プリセットで Room 1件 + Agent 5体が生成される | #2 | `GET /api/agents total=5` |
| Step 1c: WS 接続後 StatusBadge が aria-label で即時更新される | #9 | TC-E2E-CD-009 |
| Step 2: `$` directive で Task が `requirements-analysis` Stage で起票される | #3 | `GET /api/tasks` |
| Step 3: Stage が定義順に進行し deliverable が生成される | #4 | Conversation ログ |
| Step 3.5a: 全 GateRole APPROVED → ExternalReviewGate 自動生成 | #17 | `GET /api/gates` |
| Step 3.5b: 1件 REJECTED → 前段 Stage 差し戻し・ExternalReviewGate 不生成 | #18 | `GET /api/tasks current_stage` |
| Step 4: Gate 承認で `decision=APPROVED` かつ audit_trail に記録される | #5（UI承認のみ） | `GET /api/gates` |
| Step 5: 全 Stage 完了で `status=DONE, current_stage=null` になる | #7 | `GET /api/tasks` |
| 全操作で手動リロードなしに UI が更新される | #9 | WS イベント観察 |

1 項目でも FAIL した場合は本シナリオを **FAIL** とし、バグレポートを起票する。
Discord 通知（受入基準 #5 の通知部分）は Phase 2（M6-A post-MVP）まで検証対象外。

---

## 5. SC-MVP-002: 差し戻しの複数ラウンドと履歴保持

### 5.1 シナリオ概要

> シナリオ設計書: [`scenarios/SC-MVP-002-rejection-roundtrip.md`](./scenarios/SC-MVP-002-rejection-roundtrip.md)
> カバー受入基準: #6

CEO が ExternalReview Gate を差し戻し、Task が前段 Stage に戻り、
Agent が再処理して再び Gate を生成し、複数ラウンドの Gate 履歴が
保持されることを検証する。

### 5.2 テストマトリクス

| ステップ | 検証対象 | 受入基準 # | 自動化ファイル（実装予定） |
|---|---|---|---|
| Step 1: 差し戻し操作 | feedback_text 入力 → Gate `decision=REJECTED`, Task が前段 Stage へ | #6 | `frontend/e2e/03-gate-actions.spec.ts` TC-E2E-CD-006 |
| Step 2: 前段 Stage 戻り確認 | `current_stage` が ExternalReview 前の Stage に戻る | #6 | `backend/tests/acceptance/test_sc_mvp_002_rejection_roundtrip.py` |
| Step 3: 再処理と再提出 | Agent が feedback 付きで Stage を再実行、新しい Gate が生成される | #6 | 同上 |
| Step 4: 複数ラウンド履歴確認 | Gate 履歴に Round 1 (REJECTED) + Round 2 (PENDING/APPROVED) の両方が保持される | #6 | 同上 |
| Step 5: 最終承認 → Task DONE | 再提出後の Gate を承認 → Task が DONE になる | #6 + #7 | `frontend/e2e/03-gate-actions.spec.ts` TC-E2E-CD-005 |

### 5.3 実行手順と検証観点

#### 前提状態の確認

**前提**: `TASK_REJECT_ID`（`e2e00000-...0056`）が `AWAITING_EXTERNAL_REVIEW` 状態、
`GATE_REJECT_ID`（`e2e00000-...0073`）が `decision=PENDING` であること。

```python
# pytest + httpx で確認
resp = await client.get(f"/api/tasks/{TASK_REJECT_ID}")
assert resp.status_code == 200
task = resp.json()
assert task["status"] == "AWAITING_EXTERNAL_REVIEW"

resp = await client.get(f"/api/gates/{GATE_REJECT_ID}")
assert resp.status_code == 200
gate = resp.json()
assert gate["decision"] == "PENDING"
```

---

#### Step 1 — CEO が Gate を差し戻す

> 実装済み: `frontend/e2e/03-gate-actions.spec.ts` TC-E2E-CD-006

**操作** (Playwright):
```typescript
await page.goto(`/tasks/${TASK_REJECT_ID}`);
await page.getByRole("link", { name: "Gate レビューへ →" }).click();
await page.waitForLoadState("networkidle");
await page.locator("#reject-feedback").fill("ドメインモデルの集約境界が不明確。再設計を要求する。");
await page.getByRole("button", { name: "差し戻す" }).click();
await page.waitForURL(/\/tasks\//);
```

**検証ポイント**:
- [ ] `GET /api/gates/{gate_id}` → `decision = "REJECTED"`
- [ ] `GET /api/gates/{gate_id}` → `feedback_text = "ドメインモデルの集約境界が不明確。..."` （入力値と一致）
- [ ] `GET /api/gates/{gate_id}` → `decided_at` が null 以外
- [ ] audit_trail に差し戻し記録: `{event: "rejected", feedback: "...", decided_at: "..."}`

**失敗トリガー**:
- `decision` が `REJECTED` にならない
- `feedback_text` が保存されない
- audit_trail に記録がない

---

#### Step 2 — Task が前段 Stage に戻ることを確認する

**検証ポイント** (受入基準 #6):
- [ ] 差し戻し後: `GET /api/tasks/{task_id}` → `status != "AWAITING_EXTERNAL_REVIEW"`
  - ExternalReview の前段 Stage（例: `test-design`）に戻る
- [ ] `current_stage` が ExternalReview 前の Stage 名と一致する
- [ ] WebSocket で Task 状態変更イベントが配信される
- [ ] UI が手動リロードなしに更新される（ConnectionIndicator が「接続済み」状態）

**失敗トリガー**:
- Task の `status` が `AWAITING_EXTERNAL_REVIEW` のまま変わらない
- `current_stage` が前段 Stage に戻らない

---

#### Step 3 — Agent が feedback 付きで Stage を再実行し、新しい Gate を生成する

> 本ステップは Claude Code CLI fake adapter が必要。M7 自動化で実装。

**検証ポイント**:
- [ ] Conversation ログに「Round 2」または再提出を示す Agent の発言が記録される
- [ ] Agent の発言に差し戻し feedback（`"ドメインモデルの集約境界が不明確"`）が引用される
- [ ] 再処理完了後、`GET /api/gates?task_id={task_id}` に新しい Gate が追加される（計 2件）
  - Round 1: `decision=REJECTED`
  - Round 2: `decision=PENDING`（新規生成）

**失敗トリガー**:
- 新しい Gate が生成されない
- Gate 履歴が 1 件しかない（Round 2 が欠ける）

---

#### Step 4 — 複数ラウンドの Gate 履歴が保持されていることを確認する

**検証ポイント** (受入基準 #6 「複数ラウンドの Gate 履歴が保持される」):
- [ ] `GET /api/tasks/{task_id}/gates` または `GET /api/gates?task_id={task_id}`:
  - 少なくとも 2 件の Gate が返る
  - Round 1 Gate: `decision=REJECTED`, `feedback_text` に差し戻し理由
  - Round 2 Gate: `decision=PENDING`（または再承認後は `APPROVED`）
- [ ] Gate に `round` または作成順（`created_at` ソート）で順序が識別できる
- [ ] DB に対して:
  ```sql
  SELECT count(*) FROM external_review_gates
  WHERE task_id = 'e2e00000-0000-0000-0000-000000000056';
  -- → 2 以上
  ```

**失敗トリガー**:
- Gate 件数が 1 以下（履歴が上書きされている場合は #6 違反）
- Round 1 の `feedback_text` が消えている

---

#### Step 5 — Round 2 Gate を承認して Task を DONE に至らせる

**操作** (Playwright):
```typescript
// Round 2 Gate を取得
const resp = await page.request.get(`${API_BASE}/api/gates?task_id=${TASK_REJECT_ID}`);
const gates = await resp.json();
const pendingGate = gates.items.find((g: {decision: string}) => g.decision === "PENDING");

await page.goto(`/gates/${pendingGate.id}`);
await page.waitForLoadState("networkidle");
await page.getByRole("button", { name: "承認する" }).click();
await page.waitForURL(/\/tasks\//);
```

**検証ポイント**:
- [ ] Round 2 Gate: `decision = "APPROVED"`
- [ ] 全 Stage が APPROVED の場合: `GET /api/tasks/{task_id}` → `status = "DONE"`
- [ ] UI ダッシュボードで DONE タスクが反映される（WebSocket 経由）

**失敗トリガー**:
- Round 2 Gate が APPROVED にならない
- Task が DONE にならない

### 5.4 合否判定基準

本シナリオは以下の**すべて**が満たされた場合に **PASS** とする:

| 判定基準 | 対応受入基準 | 根拠 |
|---|---|---|
| feedback_text 入力後に差し戻すと `decision=REJECTED` かつ保存される | #6 | `GET /api/gates` |
| 差し戻し後に Task が前段 Stage に戻る（`current_stage` 変化） | #6 | `GET /api/tasks` |
| Agent が feedback を引用して Stage を再実行し、新しい Gate を生成する | #6 | `GET /api/gates count>=2` |
| Round 1（REJECTED）と Round 2（PENDING）の両 Gate 履歴が保持される | #6 | DB count + API |
| Round 2 Gate を承認すると Task が DONE になる | #6 + #7 | `GET /api/tasks status=DONE` |

1 項目でも FAIL した場合は本シナリオを **FAIL** とし、バグレポートを起票する。

---

## 6. 自動化実装ファイル対応表

| シナリオ | テストレベル | 実装ファイル | 実装状態 |
|---|---|---|---|
| SC-MVP-001 Step 1c, 5 (WS) | 受入テスト（UI） | `frontend/e2e/05-websocket.spec.ts` | **実装済み** — TC-E2E-CD-009/010 |
| SC-MVP-001 Step 4 (Gate 承認) | 受入テスト（UI） | `frontend/e2e/03-gate-actions.spec.ts` | **実装済み** — TC-E2E-CD-005 |
| SC-MVP-002 Step 1 (Gate 差し戻し) | 受入テスト（UI） | `frontend/e2e/03-gate-actions.spec.ts` | **実装済み** — TC-E2E-CD-006 |
| SC-MVP-001 全ステップ（API） | 受入テスト（Backend） | `backend/tests/acceptance/test_sc_mvp_001_vmodel_fullflow.py` | **未実装** — M7 で起票 |
| SC-MVP-002 全ステップ（API） | 受入テスト（Backend） | `backend/tests/acceptance/test_sc_mvp_002_rejection_roundtrip.py` | **未実装** — M7 で起票 |

---

## 7. バグ発見時の記録様式

テスト実行中にバグを発見した場合は以下の形式で報告する:

```
BUG-AT-NNN: <概要>
- ファイル: <ファイルパス>:<行番号>
- 期待動作: <期待される動作>
- 実際の動作: <実際に起きたこと>
- 再現手順: <ステップ番号>
- カバーする受入基準: #NN
- 優先度: P0（シナリオ FAIL） / P1（部分的影響）
```

---

## 8. 関連設計書

- [`docs/requirements/acceptance-criteria.md`](../requirements/acceptance-criteria.md) — MVP 受入基準の真実源
- [`docs/acceptance-tests/README.md`](./README.md) — 受入テスト戦略
- [`docs/acceptance-tests/scenarios/SC-MVP-001-vmodel-fullflow.md`](./scenarios/SC-MVP-001-vmodel-fullflow.md) — SC-MVP-001 シナリオ設計書
- [`docs/acceptance-tests/scenarios/SC-MVP-002-rejection-roundtrip.md`](./scenarios/SC-MVP-002-rejection-roundtrip.md) — SC-MVP-002 シナリオ設計書（Issue #168 で起票）
- `frontend/e2e/05-websocket.spec.ts` — WS リアルタイム更新 E2E テスト実装
- `frontend/e2e/03-gate-actions.spec.ts` — Gate 承認/差し戻し E2E テスト実装
