# テスト設計書

> feature: `external-review-gate` / sub-feature: `http-api`
> 関連 Issue: [#61 feat(external-review-gate-http-api): ExternalReviewGate HTTP API (approve/reject/cancel, M3)](https://github.com/bakufu-dev/bakufu/issues/61)
> 関連: [`basic-design.md`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../system-test-design.md`](../system-test-design.md)

## テスト戦略の位置付け

本書は **http-api sub-feature の IT（結合テスト）+ UT（ユニットテスト）** のみを扱う。E2E / システムテストは親 [`../system-test-design.md`](../system-test-design.md) が担当する。

テスト境界:
- **IT（結合テスト）**: httpx `AsyncClient` + テスト用インメモリ SQLite でエンドポイントを HTTP 黒箱検証（外部 LLM / Discord / GitHub は対象外）
- **UT（ユニットテスト）**: `ExternalReviewGateService` の単体メソッド検証（mock Repository 使用）

## テストマトリクス

| 要件 ID | 実装アーティファクト | テストケース ID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-ERG-HTTP-001 | `GET /api/gates` + `find_pending_for_reviewer` | TC-IT-ERG-HTTP-001, TC-IT-ERG-HTTP-002 | 結合 | 正常系 / 異常系 | — |
| REQ-ERG-HTTP-002 | `GET /api/tasks/{task_id}/gates` + `find_by_task` | TC-IT-ERG-HTTP-003, TC-IT-ERG-HTTP-004 | 結合 | 正常系 / 異常系 | — |
| REQ-ERG-HTTP-003 | `GET /api/gates/{id}` + `find_by_id_or_raise` | TC-IT-ERG-HTTP-005, TC-IT-ERG-HTTP-006, TC-IT-ERG-HTTP-007, **TC-IT-ERG-HTTP-033** | 結合 | 正常系 / 異常系 | —, **受入基準 #17** |
| REQ-ERG-HTTP-004 | `POST /api/gates/{id}/approve` + `ExternalReviewGateService.approve` | TC-IT-ERG-HTTP-008〜013, TC-IT-ERG-HTTP-026 | 結合 | 正常系 / 異常系 | feature-spec 受入基準 3, 5 |
| REQ-ERG-HTTP-005 | `POST /api/gates/{id}/reject` + `ExternalReviewGateService.reject` | TC-IT-ERG-HTTP-014〜019, TC-IT-ERG-HTTP-027 | 結合 | 正常系 / 異常系 | feature-spec 受入基準 4, 5 |
| REQ-ERG-HTTP-006 | `POST /api/gates/{id}/cancel` + `ExternalReviewGateService.cancel` | TC-IT-ERG-HTTP-020〜024, TC-IT-ERG-HTTP-028 | 結合 | 正常系 / 異常系 | feature-spec 受入基準 4, 5 |
| P-1: GateNotFoundError | `error_handlers.py` | TC-IT-ERG-HTTP-006, TC-IT-ERG-HTTP-009 | 結合 | 異常系 | — |
| P-1: GateAlreadyDecidedError | `error_handlers.py` | TC-IT-ERG-HTTP-012, TC-IT-ERG-HTTP-017 | 結合 | 異常系 | feature-spec 受入基準 5 |
| P-1: GateAuthorizationError | `error_handlers.py` | TC-IT-ERG-HTTP-011, TC-IT-ERG-HTTP-016, TC-IT-ERG-HTTP-022 | 結合 | 異常系 | — |
| `get_reviewer_id()` Depends | `dependencies.py` | TC-IT-ERG-HTTP-013 | 結合 | 異常系 | — |
| §確定B（masking 挙動）| `GET /api/gates/{id}` レスポンス | TC-IT-ERG-HTTP-025 | 結合 | 正常系 | — |
| R1-G（2行エラー構造）| `error_handlers.py` MSG-ERG-HTTP-001〜004 | TC-IT-ERG-HTTP-029〜032 | 結合 | 異常系 | feature-spec 受入基準 12 |
| `ExternalReviewGateService` | Service 単体 | TC-UT-ERG-HTTP-001〜005 | ユニット | 正常系 / 異常系 | — |

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | characterization fixture | factory | characterization 状態 |
|---|---|---|---|---|
| テスト用インメモリ SQLite | Gate / Task / Stage 等のシードデータ | `tests/fixtures/db/` の conftest で管理 | `tests/factories/external_review_gate.py`（M1 確定済み）| 済（M2 PR #53 で整備）|
| httpx AsyncClient | HTTP エンドポイント黒箱テスト | — | — | 済（http-api-foundation で確立）|

**assumed mock 禁止**: 外部観測値に代わる characterization fixture が未整備のまま IT を書くことを禁じる。本 sub-feature は M2 で整備された DB fixture / factory を流用する。

## 結合テストケース（IT）

### REQ-ERG-HTTP-001: GET /api/gates（PENDING 一覧）

| テスト ID | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|
| TC-IT-ERG-HTTP-001 | `reviewer_id=A` の PENDING Gate が 2 件 seed 済み | `GET /api/gates?reviewer_id=A` | HTTP 200, `items` に 2 件、`total=2`、各要素が `GateResponse` 形式 |
| TC-IT-ERG-HTTP-002 | Gate 0 件 | `GET /api/gates?reviewer_id=A` | HTTP 200, `items=[]`, `total=0` |

### REQ-ERG-HTTP-002: GET /api/tasks/{task_id}/gates（Task 履歴）

| テスト ID | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|
| TC-IT-ERG-HTTP-003 | `task_id=T` の Gate が REJECTED（旧ラウンド）+ PENDING（新ラウンド）2 件 seed | `GET /api/tasks/T/gates` | HTTP 200, `items` に 2 件が `created_at` 昇順 |
| TC-IT-ERG-HTTP-004 | Gate 0 件 | `GET /api/tasks/T/gates` | HTTP 200, `items=[]`, `total=0` |

### REQ-ERG-HTTP-003: GET /api/gates/{id}（単件）

| テスト ID | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|
| TC-IT-ERG-HTTP-005 | PENDING Gate が seed 済み（`deliverable_snapshot`・`audit_trail` 含む、`required_deliverable_criteria` 空タプル）| `GET /api/gates/{id}` | HTTP 200, `GateDetailResponse`。`feedback_text` / `body_markdown` / `audit_trail[*].comment` が DB 値と一致（§確定B）。`required_deliverable_criteria` フィールドが存在し空配列 `[]`（空タプル seed）|
| TC-IT-ERG-HTTP-006 | Gate 不在 | `GET /api/gates/{unknown-uuid}` | HTTP 404, レスポンス body に `[FAIL]` + `Gate not found` + `Next:` が含まれる（MSG-ERG-HTTP-001 R1-G 準拠の静的照合）|
| TC-IT-ERG-HTTP-007 | — | `GET /api/gates/invalid-not-uuid` | HTTP 422 `validation_error` |

### REQ-ERG-HTTP-004: POST /api/gates/{id}/approve

| テスト ID | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|
| TC-IT-ERG-HTTP-008 | PENDING Gate（`reviewer_id=R`）seed 済み | `POST /api/gates/{id}/approve` + `Authorization: Bearer R` + `{"comment": "LGTM"}` | HTTP 200, `GateDetailResponse`（`decision="APPROVED"`、`decided_at` 設定済み、`audit_trail` に APPROVED エントリ 1 件）|
| TC-IT-ERG-HTTP-009 | Gate 不在 | approve リクエスト | HTTP 404 `not_found` |
| TC-IT-ERG-HTTP-010 | PENDING Gate seed 済み | `Authorization` ヘッダーなし | HTTP 422 `validation_error`（MSG-ERG-HTTP-004）|
| TC-IT-ERG-HTTP-011 | PENDING Gate（`reviewer_id=R`）seed 済み | `Authorization: Bearer OTHER_ID`（reviewer 不一致）| HTTP 403 `forbidden`（MSG-ERG-HTTP-003）|
| TC-IT-ERG-HTTP-012 | APPROVED Gate（決済済み）seed 済み | approve リクエスト（同 reviewer）| HTTP 409 `conflict`（MSG-ERG-HTTP-002）|
| TC-IT-ERG-HTTP-013 | PENDING Gate seed 済み | `Authorization: Bearer not-a-uuid` | HTTP 422 `validation_error` |

### REQ-ERG-HTTP-005: POST /api/gates/{id}/reject

| テスト ID | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|
| TC-IT-ERG-HTTP-014 | PENDING Gate（`reviewer_id=R`）seed 済み | `POST /api/gates/{id}/reject` + `Authorization: Bearer R` + `{"feedback_text": "要修正"}` | HTTP 200, `GateDetailResponse`（`decision="REJECTED"`、`feedback_text="要修正"`）|
| TC-IT-ERG-HTTP-015 | PENDING Gate seed 済み | `{"feedback_text": ""}` | HTTP 422 `validation_error`（空文字不可）|
| TC-IT-ERG-HTTP-016 | PENDING Gate（`reviewer_id=R`）seed 済み | `Authorization: Bearer OTHER_ID` | HTTP 403 `forbidden` |
| TC-IT-ERG-HTTP-017 | APPROVED Gate（決済済み）seed 済み | reject リクエスト（同 reviewer）| HTTP 409 `conflict` |
| TC-IT-ERG-HTTP-018 | PENDING Gate seed 済み | `Authorization` ヘッダーなし | HTTP 422 `validation_error` |
| TC-IT-ERG-HTTP-019 | Gate 不在 | reject リクエスト | HTTP 404 `not_found` |

### REQ-ERG-HTTP-006: POST /api/gates/{id}/cancel

| テスト ID | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|
| TC-IT-ERG-HTTP-020 | PENDING Gate（`reviewer_id=R`）seed 済み | `POST /api/gates/{id}/cancel` + `Authorization: Bearer R` + `{"reason": ""}` | HTTP 200, `GateDetailResponse`（`decision="CANCELLED"`）。`reason` 空文字は有効（任意）|
| TC-IT-ERG-HTTP-021 | Gate 不在 | cancel リクエスト | HTTP 404 `not_found` |
| TC-IT-ERG-HTTP-022 | PENDING Gate（`reviewer_id=R`）seed 済み | `Authorization: Bearer OTHER_ID` | HTTP 403 `forbidden` |
| TC-IT-ERG-HTTP-023 | APPROVED Gate（決済済み）seed 済み | cancel リクエスト（同 reviewer）| HTTP 409 `conflict` |
| TC-IT-ERG-HTTP-024 | PENDING Gate seed 済み | `Authorization` ヘッダーなし | HTTP 422 `validation_error` |

### §確定B 検証: masking 挙動（GET /api/gates/{id}）

| テスト ID | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|
| TC-IT-ERG-HTTP-025 | `body_markdown` に `DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy` を含む PENDING Gate を seed（DB 書き込み時に MaskedText が mask() 適用済み）| `GET /api/gates/{id}` | HTTP 200。レスポンスの `deliverable_snapshot.body_markdown` に `<REDACTED:` パターンが含まれ、元の webhook URL が含まれない（§確定B — DB 保存済みのマスク値をそのまま返す検証）|

### POST 系不正 UUID（REQ-ERG-HTTP-004〜006）

| テスト ID | 操作 | 期待結果 |
|---|---|---|
| TC-IT-ERG-HTTP-026 | `POST /api/gates/invalid-not-uuid/approve` + `Authorization: Bearer <valid-uuid>` | HTTP 422 `validation_error`（パスパラメータ UUID 型強制）|
| TC-IT-ERG-HTTP-027 | `POST /api/gates/invalid-not-uuid/reject` + `Authorization: Bearer <valid-uuid>` + `{"feedback_text": "x"}` | HTTP 422 `validation_error` |
| TC-IT-ERG-HTTP-028 | `POST /api/gates/invalid-not-uuid/cancel` + `Authorization: Bearer <valid-uuid>` | HTTP 422 `validation_error` |

### R1-G 準拠検証（MSG 2行構造 — 受入基準 #12、全4件）

| テスト ID | 対象 MSG | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|
| TC-IT-ERG-HTTP-029 | MSG-ERG-HTTP-002 | APPROVED Gate（決済済み）seed 済み | `POST /api/gates/{id}/approve`（同 reviewer）| HTTP 409。レスポンス body に `[FAIL]` + `Gate decision is already finalized` + `Next:` の文字列が全て含まれる |
| TC-IT-ERG-HTTP-030 | MSG-ERG-HTTP-001 | Gate 不在 | `GET /api/gates/{unknown-uuid}` | HTTP 404。レスポンス body に `[FAIL]` + `Gate not found` + `Next:` の文字列が全て含まれる |
| TC-IT-ERG-HTTP-031 | MSG-ERG-HTTP-003 | PENDING Gate（`reviewer_id=R`）seed 済み | `POST /api/gates/{id}/approve` + `Authorization: Bearer OTHER_ID` | HTTP 403。レスポンス body に `[FAIL]` + `Not authorized` + `Next:` の文字列が全て含まれる |
| TC-IT-ERG-HTTP-032 | MSG-ERG-HTTP-004 | PENDING Gate seed 済み | `POST /api/gates/{id}/approve`（`Authorization` ヘッダーなし）| HTTP 422。レスポンス body に `[FAIL]` + `Authorization` + `Next:` の文字列が全て含まれる |

### required_deliverable_criteria 取得（受入基準 #17）

| テスト ID | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|
| **TC-IT-ERG-HTTP-033** | `required_deliverable_criteria` に AcceptanceCriterion 2 件（required=True/False 混在）を持つ PENDING Gate を seed | `GET /api/gates/{id}` | HTTP 200, `GateDetailResponse` の `required_deliverable_criteria` が長さ 2 の配列。各要素が `AcceptanceCriterionResponse`（id: str / description: str / required: bool）として返される。order_index 順（seed 時の tuple 順序を保持）。`required_deliverable_criteria` キーが JSON レスポンスに必ず存在する（criteria が空タプルの場合も `[]` が返る）|

## ユニットテストケース（UT）

### ExternalReviewGateService

| テスト ID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---|---|---|---|---|
| TC-UT-ERG-HTTP-001 | `find_by_id_or_raise` | 正常系 | mock repo が Gate を返す | Gate を返す |
| TC-UT-ERG-HTTP-002 | `find_by_id_or_raise` | 異常系 | mock repo が `None` を返す | `GateNotFoundError` を raise |
| TC-UT-ERG-HTTP-003 | `approve` | 正常系 | PENDING Gate factory + reviewer_id | `ExternalReviewGate`（decision=APPROVED）を返す |
| TC-UT-ERG-HTTP-004 | `approve` | 異常系（決済済み）| APPROVED Gate factory + 同 reviewer_id | `GateAlreadyDecidedError` を raise |
| TC-UT-ERG-HTTP-005 | `reject` | 異常系（空文字）| `feedback_text=""` | Pydantic 422（Service より上位で補足）|

## カバレッジ基準

- REQ-ERG-HTTP-001〜006 の各要件が **最低 1 件の TC-IT-ERG-HTTP-NNN** で検証されている
- MSG-ERG-HTTP-001〜004 の各文言が**静的文字列で照合**されている（`assert "[FAIL]" in ...` + `assert "Next:" in ...` で R1-G 2行構造を検証）
- feature-spec 受入基準 3（approve 遷移）/ 4（reject / cancel 遷移）/ 5（二重決定拒否）/ 12（R1-G 2行エラー構造）がそれぞれ **最低 1 件の IT** で検証されている
- §確定B（masking 挙動）が TC-IT-ERG-HTTP-025 で検証されている（secret パターン含む seed → `<REDACTED:` 含有確認）
- **受入基準 #17（criteria 取得）** が TC-IT-ERG-HTTP-033 で検証されている（criteria 2件 seed → `GateDetailResponse.required_deliverable_criteria` に 2 件の `AcceptanceCriterionResponse` が含まれることを確認）
- C0（行カバレッジ）目標: `routers/external_review_gates.py` 90% 以上 / `services/external_review_gate_service.py` 90% 以上
- reviewer_id 照合（T1 脅威）が TC-IT-ERG-HTTP-011 / TC-IT-ERG-HTTP-016 / TC-IT-ERG-HTTP-022 で検証されている
- POST 系不正 UUID が TC-IT-ERG-HTTP-026〜028 で検証されている（3 操作すべて）

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で 7 ジョブ緑であること
- ローカル確認: `docker compose up -d` → `curl -X POST http://localhost:8000/api/gates/{id}/approve -H "Authorization: Bearer {reviewer_uuid}" -H "Content-Type: application/json" -d '{"comment":"LGTM"}'` → HTTP 200

## テストディレクトリ構造

```
backend/tests/
  factories/
    external_review_gate.py           # M1 / M2 で確立済み（PENDING / DECIDED factory）
  integration/
    test_external_review_gate_http/   # 本 sub-feature の IT（新規ディレクトリ）
      __init__.py
      conftest.py                     # app fixture / seed helpers
      test_read_flows.py              # TC-IT-ERG-HTTP-001〜007, TC-IT-ERG-HTTP-033（GET 系 + criteria 取得）
      test_approve_flow.py            # TC-IT-ERG-HTTP-008〜013
      test_reject_flow.py             # TC-IT-ERG-HTTP-014〜019
      test_cancel_flow.py             # TC-IT-ERG-HTTP-020〜024
  unit/
    services/
      test_external_review_gate_service.py  # TC-UT-ERG-HTTP-001〜005
```

**500 行ルール**: 各テストファイルは 500 行を超えない。超過する場合は `test_read_flows_extended.py` 等に分割する（task/http-api パターン踏襲）。

## 未決課題・要起票 characterization task

| # | タスク | 起票先 |
|---|---|---|
| TBD-1 | `GET /api/gates?decision=APPROVED` 等非 PENDING フィルタの実装（§確定A 参照）| 将来 Issue（MVP スコープ外） |
| TBD-2 | `GET /api/gates/{id}` 経由の `record_view()` トリガー（§確定D 参照）| ui sub-feature Issue 起票時に再検討 |

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — 機能要件（REQ-ERG-HTTP-001〜006）
- [`detailed-design.md`](detailed-design.md) — MSG 確定文言 / スキーマ仕様 / §確定A〜F
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様（受入基準 3〜5）
- [`../system-test-design.md`](../system-test-design.md) — E2E テスト（HTTP 黒箱 TC-E2E-ERG-HTTP-001〜004）
