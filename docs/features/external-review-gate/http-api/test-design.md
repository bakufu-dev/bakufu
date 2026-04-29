# テスト設計書

> feature: `external-review-gate` / sub-feature: `http-api`
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md)

## 本書の役割

本書は basic-design.md §モジュール契約 の REQ-ERG-HTTP-001〜006、detailed-design.md の MSG-ERG-HTTP-001〜004、親 feature-spec.md の受入基準 #3〜6 / #10 / #14 / #15、脅威 T1〜T4 を、結合テストとユニットテストで検証可能な単位まで分解する。

**書くこと**:
- REQ / MSG / 受入基準 / 脅威を TC-IT / TC-UT に紐付ける。
- 外部 I/O 依存マップを定義する。
- API 6 本の正常系・異常系を定義する。

**書かないこと**:
- システムテスト → 親 [`../system-test-design.md`](../system-test-design.md)
- 受入テスト → [`docs/acceptance-tests/scenarios/`](../../../acceptance-tests/scenarios/)

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-ERG-HTTP-001 | `routers/external_review_gates.py` | TC-IT-ERG-HTTP-001 | 結合 | 正常系 | §9 #14 |
| REQ-ERG-HTTP-002 | `ExternalReviewGateService.list_by_task` | TC-IT-ERG-HTTP-002 | 結合 | 正常系 | §9 #14 |
| REQ-ERG-HTTP-003 | `get_and_record_view` | TC-IT-ERG-HTTP-003, TC-UT-ERG-HTTP-003 | 結合 / ユニット | 正常系 | §9 #6 |
| REQ-ERG-HTTP-004 | `approve` | TC-IT-ERG-HTTP-004, TC-IT-ERG-HTTP-007 | 結合 | 正常 / 異常 | §9 #3, #5 |
| REQ-ERG-HTTP-005 | `reject` | TC-IT-ERG-HTTP-005, TC-UT-ERG-HTTP-005 | 結合 / ユニット | 正常 / 異常 | §9 #4, #10 |
| REQ-ERG-HTTP-006 | `cancel` | TC-IT-ERG-HTTP-006 | 結合 | 正常系 | §9 #4 |
| MSG-ERG-HTTP-001 | error handler | TC-UT-ERG-HTTP-011 | ユニット | 異常系 | — |
| MSG-ERG-HTTP-002 | authorization guard | TC-IT-ERG-HTTP-008 | 結合 | 異常系 | — |
| MSG-ERG-HTTP-003 | conflict mapper | TC-IT-ERG-HTTP-007 | 結合 | 異常系 | §9 #5 |
| MSG-ERG-HTTP-004 | FastAPI validation | TC-IT-ERG-HTTP-009 | 結合 | 異常系 | — |
| T1 | reviewer guard | TC-IT-ERG-HTTP-008 | 結合 | 異常系 | — |
| T2 | decision conflict | TC-IT-ERG-HTTP-007 | 結合 | 異常系 | §9 #5 |
| T3 | response masking | TC-IT-ERG-HTTP-010 | 結合 | セキュリティ | §9 #15 |
| T4 | record_view side effect | TC-IT-ERG-HTTP-003 | 結合 | 監査 | §9 #6 |

**マトリクス充足の証拠**:
- REQ-ERG-HTTP-001〜006 すべてに最低 1 件の結合テストを割り当てる。
- MSG-ERG-HTTP-001〜004 すべてに文言照合を割り当てる。
- 親受入基準 #3〜6 / #10 / #14 / #15 は結合テストまたは既存 domain / repository テストで検証する。
- T1〜T4 すべてに有効性確認ケースがある。
- 孤児要件なし。

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 |
|---|---|---|---|---|
| SQLite tempfile DB | Gate 永続化 / 再取得 | 該当なし | `tests/factories/external_review_gate.py` | 実 DB + TestClient |
| FastAPI app | ルーティング / error handler | 該当なし | `create_app` fixture | httpx / TestClient |
| Clock | decided_at / viewed_at | 該当なし | monkeypatch 可能な service clock | UTC datetime の存在と順序を検証 |
| 外部 API | 該当なし | — | — | Mock 不要 |

## 結合テストケース

| テストID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|---|
| TC-IT-ERG-HTTP-001 | Router + Service + Repository | なし | reviewer A の PENDING Gate 2 件、他 reviewer 1 件 | `GET /api/gates?reviewer_id=A&decision=PENDING` | 200、A の 2 件のみ、新しい順 |
| TC-IT-ERG-HTTP-002 | Task 履歴 API | なし | 同一 task に A の Gate 2 件、B の Gate 1 件 | `GET /api/tasks/{task_id}/gates?reviewer_id=A` | 200、A の 2 件のみ、古い順 |
| TC-IT-ERG-HTTP-003 | 詳細取得 + audit 保存 | なし | A の PENDING Gate 1 件 | `GET /api/gates/{id}?viewer_id=A` | 200、audit_trail に VIEWED が 1 件増える |
| TC-IT-ERG-HTTP-004 | approve | なし | A の PENDING Gate | `POST /api/gates/{id}/approve` | 200、decision=APPROVED、decided_at set、APPROVED audit 追記 |
| TC-IT-ERG-HTTP-005 | reject | なし | A の PENDING Gate | `POST /api/gates/{id}/reject` with feedback | 200、decision=REJECTED、feedback_text set |
| TC-IT-ERG-HTTP-006 | cancel | なし | A の PENDING Gate | `POST /api/gates/{id}/cancel` | 200、decision=CANCELLED |
| TC-IT-ERG-HTTP-007 | 再承認不能 | なし | APPROVED Gate | `POST /api/gates/{id}/approve` | 409、MSG-ERG-HTTP-003 |
| TC-IT-ERG-HTTP-008 | reviewer 不一致拒否 | なし | Gate reviewer=A | B が GET / approve / reject / cancel | 403、MSG-ERG-HTTP-002 |
| TC-IT-ERG-HTTP-009 | validation | なし | なし | 不正 UUID / `decision=APPROVED` / 空 feedback | 422、MSG-ERG-HTTP-004 |
| TC-IT-ERG-HTTP-010 | response masking | なし | snapshot / feedback / audit comment に webhook URL を含む Gate | GET detail | 200、raw secret は含まず `<REDACTED:*>` を含む |

## ユニットテストケース

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---|---|---|---|---|
| TC-UT-ERG-HTTP-001 | `ExternalReviewGateResponse.model_validate` | 正常系 | Gate factory | VO が str / list / dict へ変換される |
| TC-UT-ERG-HTTP-002 | schema serializer | セキュリティ | secret 含む body / feedback / audit | `mask()` 適用済み文字列 |
| TC-UT-ERG-HTTP-003 | `get_and_record_view` | 正常系 | fake repo + PENDING Gate | `save` が 1 回呼ばれ VIEWED 追記 |
| TC-UT-ERG-HTTP-004 | authorization guard | 異常系 | reviewer 不一致 | `ExternalReviewGateAuthorizationError` |
| TC-UT-ERG-HTTP-005 | reject request validation | 異常系 | `feedback_text=""` | Pydantic validation error |
| TC-UT-ERG-HTTP-006 | conflict mapper | 異常系 | `decision_already_decided` violation | `ExternalReviewGateDecisionConflictError` |
| TC-UT-ERG-HTTP-011 | error handlers | 異常系 | 各 application exception | MSG-ERG-HTTP-001〜003 の文言一致 |

## カバレッジ基準

- REQ-ERG-HTTP-001〜006 の各要件が最低 1 件の結合テストで検証されている。
- MSG-ERG-HTTP-001〜004 の各文言が静的文字列で照合されている。
- 親受入基準 #3〜6 / #10 / #14 / #15 が既存 domain / repository テストまたは本 sub-feature 結合テストで検証されている。
- T1〜T4 の各脅威に対する対策が最低 1 件のテストケースで有効性確認されている。
- 行カバレッジ目標: `external_review_gate_service.py` / `external_review_gates.py` / `schemas/external_review_gate.py` / `external_review_gate_exceptions.py` 合計 90% 以上。

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全ジョブ緑であること。
- ローカル: `uv run pytest backend/tests/integration/test_external_review_gate_http_api backend/tests/unit/test_external_review_gate_http_api`。

## テストディレクトリ構造

```
backend/tests/
├── integration/
│   └── test_external_review_gate_http_api/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_read.py
│       ├── test_decisions.py
│       └── test_security.py
└── unit/
    └── test_external_review_gate_http_api/
        ├── __init__.py
        ├── test_handlers.py
        ├── test_schemas.py
        └── test_service.py
```

## 未決課題・要起票 characterization task

| # | タスク | 起票先 |
|---|---|---|
| 該当なし | 未決課題なし。Issue #61 の実装 PR 内で上記テストを作成する | — |

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — 機能要件（REQ ID）
- [`detailed-design.md`](detailed-design.md) — MSG 確定文言
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様（受入基準）
- [`../system-test-design.md`](../system-test-design.md) — システムテスト（feature 内）
