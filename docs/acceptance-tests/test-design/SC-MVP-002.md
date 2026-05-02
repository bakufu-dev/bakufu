# SC-MVP-002 テスト設計 — INTERNAL_REVIEW 差し戻し → 複数ラウンド完走

> シナリオ設計書: [`../scenarios/SC-MVP-002-rejection-roundtrip.md`](../scenarios/SC-MVP-002-rejection-roundtrip.md)
> カバー受入基準: #6, #18
> 環境要件・外部I/O依存マップ・バグ記録様式: [`README.md`](./README.md)

---

## 1. シナリオ概要

REVIEWER role Agent が INTERNAL_REVIEW Stage で `REJECTED` を出し、
Task が前段 WORK Stage に差し戻された後、Agent が feedback を考慮して
再提出し、2 ラウンド目の REVIEWER Agent が `APPROVED` を出すまでの
完全な差し戻しサイクルを検証する。

本シナリオは **INTERNAL_REVIEW Gate（Agent 自動判定）** の差し戻し経路を対象とする。
ExternalReview Gate（CEO UI 手動操作）の差し戻しは SC-MVP-009（M7 後起票）で担保する。

### テスト制御（fake adapter）

本シナリオは Claude Code CLI fake adapter の「ラウンドベース制御」を前提とする:

| ラウンド | fake adapter の振る舞い |
|---|---|
| ラウンド 1（要件レビュー）| REVIEWER: `REJECTED` + feedback コメントを返す |
| ラウンド 2（要件レビュー）| REVIEWER: `APPROVED` を返す |

fake adapter の実装方式（環境変数 / config file / spy パターン）は M7 自動化実装時に確定する。

---

## 2. テストマトリクス

| ステップ | 検証対象 | 受入基準 # | 自動化ファイル（実装予定） |
|---|---|---|---|
| Step 1: directive → Task 起票 | Task 起票・最初の WORK Stage 開始 | #3 | `backend/tests/acceptance/test_sc_mvp_002_rejection_roundtrip.py` |
| Step 2: REVIEWER Agent REJECTED | InternalReviewGate に REJECTED 記録 + Task が前段 Stage に差し戻し | #18 | 同上 |
| Step 3: feedback 付き再実行 | Agent がラウンド 1 feedback を考慮した deliverable を再生成 | #6 | 同上 |
| Step 4: 2ラウンド目 APPROVED → 次 Stage 遷移 | REVIEWER Agent APPROVED で次 Stage に進む | #17 | 同上 |
| Step 5: Gate 履歴（audit_trail）完全性確認 | ラウンド 1 (REJECTED) + ラウンド 2 (APPROVED) が両方保持される | #6 | 同上 |

---

## 3. 前提セットアップ

本シナリオは ExternalReviewGate 用シードデータ（`GATE_REJECT_ID` 等）を使用しない。
pytest fixture で Empire / Room / Workflow / Task を動的に構築し、fake adapter で状態を制御する。

```python
# backend/tests/acceptance/conftest.py
@pytest.fixture(scope="module")
async def sc002_setup(client: httpx.AsyncClient, fake_adapter_config):
    """SC-MVP-002 事前セットアップ: Empire + V-model Room + Task を構築する"""
    # 1. Empire + V-model Room 作成（SC-MVP-001 と共有可能）
    resp = await client.post("/api/empires", json={"name": "差し戻しテスト幕府"})
    assert resp.status_code == 201
    empire_id = resp.json()["id"]

    resp = await client.post(
        f"/api/empires/{empire_id}/rooms",
        json={"preset_name": "v-model", "name": "差し戻しテスト Room"},
    )
    assert resp.status_code == 201
    room_id = resp.json()["id"]

    # 2. fake adapter を「ラウンド 1 は REJECTED」設定で初期化
    fake_adapter_config.set_round_behavior(
        stage="要件レビュー",
        round_1="REJECTED",
        round_1_feedback="要件の集約境界が不明確。エンティティ境界を再定義せよ。",
        round_2_plus="APPROVED",
    )

    # 3. directive を投入して Task を起票
    resp = await client.post(
        f"/api/rooms/{room_id}/directives",
        json={"content": "$ 差し戻しシナリオ用 TodoApp 要件定義"},
    )
    assert resp.status_code == 201

    return {"empire_id": empire_id, "room_id": room_id}
```

---

## 4. 実行手順と検証観点

### Step 1 — directive 投入 → Task 起票・最初の WORK Stage 開始

**操作**: `前提セットアップ §3` の `sc002_setup` fixture 内で完了。

**検証ポイント**:
- [ ] `GET /api/rooms/{room_id}/tasks` → `total >= 1`
- [ ] 作成された Task の `current_stage` が最初の WORK Stage（`"要件定義"`）
- [ ] `status = "IN_PROGRESS"`
- [ ] Conversation ログに directive メッセージが記録される

**失敗トリガー**:
- Task が生成されない
- `current_stage` が最初の WORK Stage 以外

---

### Step 2 — REVIEWER Agent が REJECTED を出し、Task が前段 Stage に差し戻される

> fake adapter がラウンド 1 の「要件レビュー」Stage で `REJECTED` を返す設定であること。

**操作**: 自動進行（操作不要）。fake adapter の REJECTED 応答により決定論的に発火。

**検証ポイント** (受入基準 #18):
- [ ] `GET /api/internal-review-gates?task_id={task_id}` または
  `GET /api/tasks/{task_id}/review-gates`:
  - ラウンド 1 の InternalReviewGate が存在する
  - `verdict = "REJECTED"`
  - `feedback_comment = "要件の集約境界が不明確。..."` （fake adapter 設定値と一致）
  - `decided_at` が null 以外
- [ ] `GET /api/tasks/{task_id}` → `current_stage` が「要件定義」（前段 WORK Stage）に戻っている
- [ ] ExternalReviewGate は生成されない:
  `GET /api/gates?task_id={task_id}` → `items` が空または ExternalReviewGate の件数 = 0
- [ ] Conversation ログに REVIEWER Agent の `REJECTED` + feedback が記録されている
- [ ] DB に対して:
  ```sql
  SELECT count(*), verdict FROM internal_review_gates
  WHERE task_id = '{task_id}'
  GROUP BY verdict;
  -- → count=1, verdict='REJECTED'
  ```
- [ ] WebSocket で Stage 差し戻しイベントが配信され、UI が手動リロードなしに `current_stage="要件定義"` を表示する

**失敗トリガー**:
- InternalReviewGate が生成されない（内部レビュー機構が未実装）
- `current_stage` が前段 Stage に戻らない（受入基準 #18 違反）
- ExternalReviewGate が生成される（REJECTED なのに外部レビューへ到達した場合は受入基準 #17 の前提破壊）

---

### Step 3 — Agent が feedback を考慮して deliverable を再生成する

> fake adapter がラウンド 2 の「要件定義」Stage で LEADER Agent の deliverable を生成する。
> この時点で feedback コメントが deliverable 再生成の入力として渡される。

**操作**: 自動進行（操作不要）。

**検証ポイント** (受入基準 #6):
- [ ] Conversation ログに「ラウンド 2」を示す LEADER Agent の発言が記録される
  - ラウンド 1 とラウンド 2 の発言が時系列で区別できる
- [ ] ラウンド 2 の発言または deliverable に、ラウンド 1 の feedback（`"要件の集約境界が不明確"`）への
  言及・反映が確認できる
- [ ] ラウンド 2 完了後、`current_stage` が「要件レビュー」（INTERNAL_REVIEW Stage）に遷移する:
  `GET /api/tasks/{task_id}` → `current_stage = "要件レビュー"`

**失敗トリガー**:
- ラウンド 2 の発言が記録されない
- feedback が deliverable に反映されていない（fake adapter 実装の正確性問題）
- ラウンド 2 完了後に INTERNAL_REVIEW Stage に遷移しない

---

### Step 4 — 2ラウンド目の REVIEWER Agent が APPROVED を出し、次 Stage へ遷移する

> fake adapter がラウンド 2 の「要件レビュー」Stage で `APPROVED` を返す設定であること。

**操作**: 自動進行（操作不要）。

**検証ポイント** (受入基準 #17):
- [ ] Conversation ログにラウンド 2 の REVIEWER Agent の `APPROVED` が記録される
- [ ] `GET /api/tasks/{task_id}` → `current_stage` が次の WORK Stage（`"基本設計"`）に進む
- [ ] WebSocket で Stage 遷移イベントが配信され、UI が手動リロードなしに更新される

**失敗トリガー**:
- APPROVED なのに次 Stage に進まない（受入基準 #17 違反）

---

### Step 5 — InternalReviewGate の audit_trail 完全性を確認する

**操作**: `GET /api/internal-review-gates?task_id={task_id}` または
`GET /api/tasks/{task_id}/review-gates` で全件取得。

**検証ポイント** (受入基準 #6 「複数ラウンドの Gate 履歴が保持される」):
- [ ] InternalReviewGate の件数 >= 2（ラウンド 1 + ラウンド 2）:
  ```sql
  SELECT count(*) FROM internal_review_gates
  WHERE task_id = '{task_id}' AND stage_name = '要件レビュー';
  -- → 2 以上
  ```
- [ ] ラウンド 1 Gate: `verdict = "REJECTED"`, `feedback_comment` に差し戻し理由, `round = 1`
- [ ] ラウンド 2 Gate: `verdict = "APPROVED"`, `round = 2`
- [ ] 両 Gate の `decided_at` が null 以外（タイムスタンプ記録済み）
- [ ] ラウンド 1 の `feedback_comment` が上書き・削除されていない:
  `feedback_comment != ""` かつ `feedback_comment != null`

**失敗トリガー**:
- InternalReviewGate の件数が 1 以下（履歴が上書きされている = 受入基準 #6 違反）
- ラウンド 1 の `feedback_comment` が消えている
- `round` フィールドまたは `created_at` ソートでラウンド順序が識別できない

---

## 5. 合否判定基準

本シナリオは以下の**すべて**が満たされた場合に **PASS** とする:

| 判定基準 | 対応受入基準 | 根拠 |
|---|---|---|
| Step 2: REVIEWER Agent REJECTED → InternalReviewGate に記録 | #18 | `GET /api/internal-review-gates` |
| Step 2: REJECTED 後に Task が前段 WORK Stage に戻る | #18 | `GET /api/tasks current_stage` |
| Step 2: ExternalReviewGate は生成されない | #17 前提 | `GET /api/gates items=[]` |
| Step 3: Agent が feedback を考慮して deliverable を再生成する | #6 | Conversation ログ |
| Step 4: 2ラウンド目 APPROVED で次 Stage に進む | #17 | `GET /api/tasks current_stage` |
| Step 5: ラウンド 1 (REJECTED) + ラウンド 2 (APPROVED) 両方の Gate 履歴が保持される | #6 | DB count >= 2 |
| Step 5: ラウンド 1 の feedback_comment が削除・上書きされていない | #6 | `GET /api/internal-review-gates` |

1 項目でも FAIL した場合は本シナリオを **FAIL** とし、`BUG-AT-NNN` 形式でバグレポートを起票する。

---

## 6. 自動化実装ファイル対応表

| ステップ | テストレベル | 実装ファイル | 実装状態 |
|---|---|---|---|
| Step 1〜5 全体（API + fake adapter） | 受入テスト（Backend） | `backend/tests/acceptance/test_sc_mvp_002_rejection_roundtrip.py` | **未実装** — M7 で起票 |
| Step 2 WS 配信（UI 観察） | 受入テスト（UI） | `frontend/e2e/sc-mvp-002-rejection-roundtrip.spec.ts` | **未実装** — M7 で起票 |

> **TC-E2E-CD-006（ExternalReview UI 差し戻し）との分離**:
> `frontend/e2e/03-gate-actions.spec.ts` の TC-E2E-CD-006 は ExternalReview Gate への
> UI 差し戻し操作（CEO 手動、`external_review_gates` テーブル）を実装済みだ。
> 本 SC-MVP-002 が検証する InternalReview 差し戻し（REVIEWER Agent 自動判定、`internal_review_gates` テーブル）
> とは別 Aggregate であり、TC-E2E-CD-006 は本シナリオの自動化ファイルに含めない。
> TC-E2E-CD-006 の受入テスト昇格は SC-MVP-009 で行う。
