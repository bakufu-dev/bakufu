# 受入テスト設計書 インデックス

> 本書の種別: 受入テスト設計書（Vモデル最上位）インデックス
> 対象マイルストーン: MVP M7
> 凍結バージョン: Issue #168 — 2026-05-02
> レビュー担当: ヘルスバーグ（品質）/ Tabriz（セキュリティ）/ ラムス（UX）
> ステータス: **凍結**

---

## 1. 本書の位置付け

本ディレクトリは [`docs/acceptance-tests/scenarios/SC-MVP-NNN.md`](../scenarios/) の各シナリオに対応する
「実行手順・検証観点・合否判定基準」を凍結する。

Vモデルでの位置付け:

```
要求分析 → docs/requirements/acceptance-criteria.md
    ↕
受入テスト シナリオ設計 → docs/acceptance-tests/scenarios/SC-MVP-NNN.md  ← 業務観察「何を観察するか」
受入テスト 実行手順設計 → docs/acceptance-tests/test-design/SC-MVP-NNN.md ← 本書「どう操作・検証するか」
```

## 2. 本ディレクトリの構成

| ファイル | 担当シナリオ | カバー受入基準 |
|---|---|---|
| [`SC-MVP-001.md`](./SC-MVP-001.md) | Vモデル開発室でディレクティブから Task 完走 | #1, #2, #3, #4, #5(UI承認), #7, #9, #17 |
| [`SC-MVP-002.md`](./SC-MVP-002.md) | INTERNAL_REVIEW 差し戻し → 複数ラウンド完走 | #6, #18 |

---

## 3. テスト環境要件

### 3.1 必要サービス

| サービス | アドレス | 起動方法 |
|---|---|---|
| Backend (FastAPI) | `http://localhost:8000` | `docker compose up bakufu-backend-1` |
| Frontend (Vite) | `http://localhost:5173` | `docker compose up bakufu-frontend-1` |
| WebSocket | `ws://localhost:8000/ws` | Backend に内包（`/ws` エンドポイント） |
| SQLite | `/app/data/bakufu.db` | Backend 起動時に自動マイグレーション |

### 3.2 自動化ツール

| テストレベル | ツール | 実行コマンド |
|---|---|---|
| 受入テスト（UI + WebSocket） | Playwright (`@playwright/test` v1.59.1) | `cd frontend && npx playwright test` |
| 受入テスト（Backend API 経由） | pytest + httpx | `cd backend && python -m pytest tests/acceptance/` |
| 全テスト一括 | just | `just check-all` |

### 3.3 シードデータ前提（Playwright E2E テスト用）

Playwright テストは以下の定数（`frontend/e2e/helpers.ts`）を使用する。
シード投入が未完了の場合テストは失敗する。

| 定数 | UUID | 説明 |
|---|---|---|
| `EMPIRE_ID` | `00000000-...0001` | E2E テスト用 Empire |
| `ROOM_ID` | `e2e00000-...0031` | E2E テスト用 Room |
| `TASK_PENDING_ID` | `e2e00000-...0051` | status=PENDING の Task（WS テスト用） |
| `TASK_APPROVE_ID` | `e2e00000-...0055` | ExternalReview Gate 承認テスト用 Task |
| `GATE_APPROVE_ID` | `e2e00000-...0072` | 承認テスト用 ExternalReviewGate (PENDING) |

> **SC-MVP-002 はシードデータ不要**: InternalReview 差し戻しシナリオは fake adapter で状態制御するため
> pytest fixture で Empire/Room/Agent/Task を動的に構築する。
> ExternalReviewGate 用シードデータ（`GATE_REJECT_ID`: `e2e00000-...0073`）は SC-MVP-002 では使用しない。
> ExternalReview UI 差し戻しは SC-MVP-009（M7 後起票）で担保する。

再実行時のリセット手順（SC-MVP-001 Step 4 Gateway テスト用）:
```sql
-- backend コンテナ内で実行
sqlite3 /app/data/bakufu.db "UPDATE external_review_gates
  SET decision='PENDING', feedback_text='', decided_at=NULL
  WHERE id IN (
    'e2e00000-0000-0000-0000-000000000071',
    'e2e00000-0000-0000-0000-000000000072'
  );"
```

---

## 4. 外部 I/O 依存マップ

| 外部 I/O | SC-MVP-001 | SC-MVP-002 | Fixture / Mock 状態 |
|---|---|---|---|
| SQLite (`bakufu.db`) | 依存（全 Aggregate 永続化） | 依存（InternalReviewGate 履歴） | 事前 fixture で初期化。再実行時はリセット SQL 使用 |
| WebSocket (`/ws`) | 依存（リアルタイム更新観察） | 依存（Stage 差し戻しイベント配信） | Playwright `routeWebSocket` で実サーバーへ転送（characterization 済み） |
| Claude Code CLI | 依存（deliverable 生成） | 依存（REJECTED → 再生成） | fake adapter（stub 応答、ラウンドベース制御）— M7 自動化で実装 |
| Discord Bot | 依存（#5 外部レビュー通知） | 非依存 | **Phase 2（M6-A post-MVP）** — M7 自動化では除外。UI 承認のみ検証 |
| 現在時刻 | 依存（`occurred_at`、`audit_trail`） | 依存 | UTC `datetime.now()` を使用。freeze 不要（精度検証なし） |

---

## 5. M7 スコープと残課題追跡

### 5.1 本書のカバー範囲（M7 スコープ内）

| シナリオ ID | カバー受入基準 | 実行手順ファイル |
|---|---|---|
| SC-MVP-001 | #1, #2, #3, #4, #5（UI承認のみ）, #7, #9, #17 | `SC-MVP-001.md` |
| SC-MVP-002 | #6, #18 | `SC-MVP-002.md` |

### 5.2 M7 スコープ外シナリオ（後続 Issue で起票）

以下のシナリオは本書の対象外。実装追跡先は各行に明示する。

| シナリオ ID | カバー受入基準 | 追跡先 |
|---|---|---|
| SC-MVP-003 | #8（再起動跨ぎ全状態復元） | M7 後起票 |
| SC-MVP-004 | #11（BLOCKED Task の admin 救済） | M7 後起票 |
| SC-MVP-005 | #12（dead-letter event の admin 救済） | M7 後起票 |
| **SC-MVP-006** | **#14, #15, #16（セキュリティ受入基準）** | **Issue #172 で追跡** |
| SC-MVP-007 | #13（Admin CLI audit_log 記録） | M7 後起票 |
| SC-MVP-008 | #10（`just check-all` 緑） | M7 後起票 |
| SC-MVP-009 | #6 UI操作（ExternalReview 差し戻し UI） | M7 後起票（TC-E2E-CD-006 の受入テスト昇格） |

> **SC-MVP-006 について（セキュリティ受入基準）**:
> 受入基準 #14（パストラバーサル / MIME スプーフィング / サイズ超過の拒否）/
> #15（LLM subprocess secret 伏字）/ #16（ループバック限定バインド）は
> `docs/design/threat-model.md §受入検証チェックリスト` の 9 項目と直接対応する MVP セキュリティ検証の核だ。
> 本 M7 設計書の対象外だが、**Issue #172** のスコープに明示的に含めること。
> Issue #172 クローズ時に本セクションを更新し追跡完了を記録する。

> **SC-MVP-009 について（ExternalReview UI 差し戻し）**:
> TC-E2E-CD-006（`frontend/e2e/03-gate-actions.spec.ts`）は ExternalReview Gate への
> UI 差し戻し操作が実装済みだ。この操作は受入基準 #6 の一部（UI 操作による Gate 差し戻し）を
> カバーするが、SC-MVP-002 が担う InternalReview 経路とは別 Aggregate だ。
> 受入テスト昇格（SC-MVP-009）は M7 後に起票する。

---

## 6. バグ発見時の記録様式

テスト実行中にバグを発見した場合は以下の形式で報告する:

```
BUG-AT-NNN: <概要>
- ファイル: <ファイルパス>:<行番号>
- 期待動作: <期待される動作>
- 実際の動作: <実際に起きたこと>
- 再現手順: <SC-MVP-NNN Step NN>
- カバーする受入基準: #NN
- 優先度: P0（シナリオ FAIL） / P1（部分的影響）
```

---

## 7. 関連設計書

- [`docs/requirements/acceptance-criteria.md`](../../requirements/acceptance-criteria.md) — MVP 受入基準の真実源
- [`docs/acceptance-tests/README.md`](../README.md) — 受入テスト戦略
- [`docs/acceptance-tests/scenarios/SC-MVP-001-vmodel-fullflow.md`](../scenarios/SC-MVP-001-vmodel-fullflow.md) — シナリオ設計書
- [`docs/acceptance-tests/scenarios/SC-MVP-002-rejection-roundtrip.md`](../scenarios/SC-MVP-002-rejection-roundtrip.md) — シナリオ設計書
- `frontend/e2e/05-websocket.spec.ts` — WS リアルタイム更新 E2E（TC-E2E-CD-009/010）
- `frontend/e2e/03-gate-actions.spec.ts` — Gate 承認/差し戻し E2E（TC-E2E-CD-005/006）
