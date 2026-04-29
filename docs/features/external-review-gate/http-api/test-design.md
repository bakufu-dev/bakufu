# テスト設計書

> feature: `external-review-gate` / sub-feature: `http-api`
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md)

## 本書の役割

本書は basic-design.md §モジュール契約 の REQ-ERG-HTTP-001〜006、detailed-design.md の MSG-ERG-HTTP-001〜004、親 feature-spec.md の受入基準 #3〜6 / #10 / #12 / #14 / #15、脅威 T1〜T6 を、結合テストとユニットテストで検証可能な単位まで分解する。

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
| T1 | subject authorization guard | TC-IT-ERG-HTTP-008, TC-IT-ERG-HTTP-015 | 結合 | 異常系 | — |
| T2 | decision conflict | TC-IT-ERG-HTTP-007 | 結合 | 異常系 | §9 #5 |
| T3 | HTTP Repository restored response / DB masking boundary | TC-IT-ERG-HTTP-010 | 結合 | セキュリティ | §9 #15 |
| T4 | record_view side effect | TC-IT-ERG-HTTP-003 | 結合 | 監査 | §9 #6 |
| T5 | CSRF Origin guard | TC-IT-ERG-HTTP-014 | 結合 | セキュリティ | — |
| T6 | dependency CVE audit | TC-CI-ERG-HTTP-001 | CI | セキュリティ | — |
| API1 / API5 | reviewer object / function authorization | TC-IT-ERG-HTTP-008 / 015 | 結合 | セキュリティ | — |
| API2 | Bearer token operation | TC-IT-ERG-HTTP-015 / 016 | 結合 | セキュリティ | — |
| API3 | forbidden authority properties | TC-IT-ERG-HTTP-009 | 結合 | セキュリティ | — |
| API4 | request size limits | TC-IT-ERG-HTTP-009 / TC-UT-ERG-HTTP-008 | 結合 / ユニット | セキュリティ | §9 #10 |
| API6 | sensitive flow protection | TC-IT-ERG-HTTP-007 / 014 | 結合 | セキュリティ | — |
| API7 / API10 | no outbound API consumption | TC-STATIC-ERG-HTTP-001 | 静的確認 | セキュリティ | — |
| API8 / API9 | app wiring / API inventory | TC-STATIC-ERG-HTTP-002 | 静的確認 | セキュリティ | — |

**マトリクス充足の証拠**:
- REQ-ERG-HTTP-001〜006 すべてに最低 1 件の結合テストを割り当てる。
- MSG-ERG-HTTP-001〜004 すべてに文言照合を割り当てる。
- 親受入基準 #3〜6 / #10 / #12 / #14 / #15 は結合テストまたは既存 domain / repository テストで検証する。
- T1〜T6 と OWASP API Security Top 10 2023 API1〜API10 すべてに有効性確認または非該当根拠ケースがある。
- 孤児要件なし。

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | schema | factory | characterization 状態 | テスト戦略 |
|---|---|---|---|---|---|---|
| SQLite tempfile DB | Gate 永続化 / 再取得 | 不要（内部 DB。結合は実接続） | 不要 | `tests/factories/db.py`, `tests/factories/external_review_gate.py` | 対象外 | 実 DB + TestClient。DB 直接 assert は seed / fixture 準備に限定し、検証は API ラウンドトリップで行う |
| FastAPI app | ルーティング / error handler | 不要（プロセス内 ASGI） | 不要 | `create_app` fixture | 対象外 | httpx ASGITransport / TestClient で公開 API から呼ぶ |
| Clock | decided_at / viewed_at | 不要（外部サービスではない） | 不要 | monkeypatch 可能な service clock / fixed datetime factory | 対象外 | UTC aware datetime の存在、単調な順序、audit action との対応を検証 |
| Auth subject provider | reviewer 認可境界 | 不要（外部サービスではない） | 不要 | subject factory | 対象外 | `Authorization: Bearer <token>` と test config の `BAKUFU_OWNER_ID` から検証済み subject を作る。query/body/header の自己申告 ID は使わない |
| CSRF Origin middleware | 状態変更 POST の Origin 検証 | 不要（プロセス内 ASGI） | 不要 | 不要 | 対象外 | `Origin: http://evil.example.com` で approve / reject / cancel が 403 になることを確認 |
| 外部 API | 該当なし | 不要 | 不要 | 不要 | 対象外 | Mock 不要 |

**判定**: Issue #61 の対象は HTTP API + SQLite + 時刻だけで、外部 API / SaaS / ファイル入力は無い。したがって characterization raw/schema の新規起票は不要だ。DB は外部 I/O だが、結合テストでは実接続し、unit では repository / clock だけを factory 由来の値で置換する。

## モック方針

| テストレベル | モック対象 | 禁止事項 | 根拠 |
|---|---|---|---|
| 結合 | 外部 API なし。Clock と認証済み subject dependency のみ固定可 | Repository / Service / Domain をモックしない。DB 直接 assert を主検証にしない。query/body の `reviewer_id` / `viewer_id` / `actor_id` を使わない | API クライアント契約を検証する層だからだ |
| ユニット | Repository port、Clock、request factory | `mock.return_value` のインライン dict 禁止。raw fixture 直読禁止 | factory 由来の Gate / VO で分岐を潰す |
| system / acceptance | モックなし | sub-feature 側に system case を置かない | 親 `system-test-design.md` / `docs/acceptance-tests/scenarios/` の責務 |

## 結合テストケース

| テストID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|---|
| TC-IT-ERG-HTTP-001 | Router + Service + Repository | なし | subject=A、reviewer A の PENDING Gate 2 件、他 reviewer 1 件 | `GET /api/gates?decision=PENDING` | 200、A の 2 件のみ、新しい順 |
| TC-IT-ERG-HTTP-002 | Task 履歴 API | なし | subject=A、同一 task に A の Gate 2 件、B の Gate 1 件 | `GET /api/tasks/{task_id}/gates` | 200、A の 2 件のみ、古い順 |
| TC-IT-ERG-HTTP-003 | 詳細取得 + audit 保存 | なし | subject=A、A の PENDING Gate 1 件 | `GET /api/gates/{id}` | 200、audit_trail に VIEWED が 1 件増える |
| TC-IT-ERG-HTTP-004 | approve | なし | A の PENDING Gate | `POST /api/gates/{id}/approve` | 200、decision=APPROVED、decided_at set、APPROVED audit 追記 |
| TC-IT-ERG-HTTP-005 | reject | なし | A の PENDING Gate | `POST /api/gates/{id}/reject` with feedback | 200、decision=REJECTED、feedback_text set |
| TC-IT-ERG-HTTP-006 | cancel | なし | A の PENDING Gate | `POST /api/gates/{id}/cancel` | 200、decision=CANCELLED |
| TC-IT-ERG-HTTP-007 | 再承認不能 | なし | APPROVED Gate | `POST /api/gates/{id}/approve` | 409、MSG-ERG-HTTP-003 |
| TC-IT-ERG-HTTP-008 | subject 不一致拒否 | なし | Gate reviewer=A、認証済み subject=B | B が GET / approve / reject / cancel | 403、MSG-ERG-HTTP-002 の 2 行文言 |
| TC-IT-ERG-HTTP-009 | validation | なし | なし | 不正 UUID / `decision=APPROVED` / 空 feedback / body に `actor_id` 混入 | 422、MSG-ERG-HTTP-004 |
| TC-IT-ERG-HTTP-010 | HTTP Repository restored response / DB masking boundary | なし | snapshot / feedback / audit comment に webhook URL を含む Gate を Repository 経由で保存済み | 認可済み subject で GET detail | 200、HTTP response は Repository 復元値を返す。保存済み secret は redacted のまま、HTTP schema は再マスクも raw secret 復号もしない。DB 保存値の masking は repository TC-IT-ERGR-020-masking-* が担当 |
| TC-IT-ERG-HTTP-011 | HTTP API flow smoke | なし | PENDING Gate、reviewer A | 一覧 → 詳細閲覧 → approve → 詳細再取得 | 6 API のうち一覧 / 詳細 / approve がユーザー観測可能な一連の経路として成立し、audit に VIEWED と APPROVED が見える |
| TC-IT-ERG-HTTP-012 | reject API flow smoke | なし | PENDING Gate、reviewer A | 詳細閲覧 → reject with feedback → Task 履歴取得 | feedback と REJECTED が履歴 API から観測できる |
| TC-IT-ERG-HTTP-013 | cancel API flow smoke | なし | PENDING Gate、reviewer A | cancel with reason → 一覧取得 | CANCELLED 後の Gate は PENDING 一覧から消え、Task 履歴に残る |
| TC-IT-ERG-HTTP-014 | CSRF Origin guard | なし | PENDING Gate、subject=A | `Origin: http://evil.example.com` 付きで approve / reject / cancel | 403、http-api-foundation MSG-HAF-004 |
| TC-IT-ERG-HTTP-015 | auth subject required | なし | PENDING Gate | Authorization 欠落 / 不正 token / `X-Reviewer-Id` のみ指定 | 401 または 403。Service は呼ばれず、自己申告 ID では成功しない |
| TC-IT-ERG-HTTP-016 | Bearer token operation | なし | `BAKUFU_OWNER_API_TOKEN` と `BAKUFU_OWNER_ID` を test config に設定 | 32 bytes 以上の token で成功、短い token 設定 / 不一致 token / 不正 owner UUID を送る | 成功時だけ subject が作られる。失敗時は 401、token 値と Authorization ヘッダはログに出ない |

## ユニットテストケース

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---|---|---|---|---|
| TC-UT-ERG-HTTP-001 | `ExternalReviewGateResponse.model_validate` | 正常系 | Gate factory | VO が str / list / dict へ変換される |
| TC-UT-ERG-HTTP-002 | schema serializer | セキュリティ | Repository 復元値として secret / `<REDACTED:*>` を含む body / feedback / audit | `mask()` も復号も適用せず、入力値をそのまま response model に載せる |
| TC-UT-ERG-HTTP-003 | `get_and_record_view` | 正常系 | fake repo + PENDING Gate | `save` が 1 回呼ばれ VIEWED 追記 |
| TC-UT-ERG-HTTP-004 | authorization guard | 異常系 | `subject.owner_id` と `gate.reviewer_id` 不一致 | `ExternalReviewGateAuthorizationError` |
| TC-UT-ERG-HTTP-005 | reject request validation | 異常系 | `feedback_text=""` | Pydantic validation error |
| TC-UT-ERG-HTTP-006 | conflict mapper | 異常系 | `decision_already_decided` violation | `ExternalReviewGateDecisionConflictError` |
| TC-UT-ERG-HTTP-007 | list_by_task reviewer filter | セキュリティ | fake repo + A/B 混在 Gate | A の Gate だけ返る |
| TC-UT-ERG-HTTP-008 | cancel request validation | 境界値 | `reason` 10000 / 10001 文字 | 10000 は受理、10001 は validation error |
| TC-UT-ERG-HTTP-011 | error handlers | 異常系 | 各 application exception | MSG-ERG-HTTP-001〜004 の 2 行文言一致（Next 行を含む） |
| TC-UT-ERG-HTTP-012 | bearer token resolver | セキュリティ | token factory / env config | constant-time 比較を使い、欠落 / 不一致 / 不正 owner ID は 401。Authorization 値を log / response に出さない |
| TC-CI-ERG-HTTP-001 | dependency audit | セキュリティ | CI `audit` job | FastAPI / Starlette / Pydantic / httpx / SQLAlchemy / SQLite 関連の critical/high CVE が未解決なら fail |
| TC-STATIC-ERG-HTTP-001 | outbound call inventory | セキュリティ | router / service / schema | HTTP client / webhook fetch / URL dereference が追加されていない |
| TC-STATIC-ERG-HTTP-002 | API inventory and wiring | セキュリティ | app wiring / OpenAPI | 6 API だけが登録され、auth / CSRF / error handler が有効 |

## E2E 受入基準との接続

| 親受入基準 | 本 sub-feature での検証 | 親 system / acceptance での検証 |
|---|---|---|
| #3 承認 | TC-IT-ERG-HTTP-004 / 011 で HTTP approve 契約を検証 | CEO が公開 API 経由で approve し、APPROVED と audit を観測する |
| #4 差し戻し / 取消 | TC-IT-ERG-HTTP-005 / 006 / 012 / 013 | CEO が reject / cancel 後、履歴と PENDING 一覧の変化を観測する |
| #5 既決 Gate 再判断拒否 | TC-IT-ERG-HTTP-007 | 既決 Gate に再送して、ユーザーが競合メッセージを観測する |
| #6 閲覧監査 | TC-IT-ERG-HTTP-003 / 011 / 012 | 詳細閲覧後に VIEWED audit が API レスポンスで観測できる |
| #10 feedback 境界 | TC-IT-ERG-HTTP-005 / 009, TC-UT-ERG-HTTP-005 / 008 | 1〜10000 文字は受理、空 reject と 10001 文字は拒否 |
| #12 Next 文 | TC-UT-ERG-HTTP-011、TC-IT-ERG-HTTP-007 / 008 / 009 | 業務エラー時、ユーザーが次に取る行動を `Next:` 行として観測する |
| #14 再起動跨ぎ永続化 | TC-IT-ERG-HTTP-001〜006 は API ラウンドトリップ、親 `TC-E2E-ERG-001〜003` は repository 再起動 | 親 system-test-design が担当 |
| #15 secret masking | repository TC-IT-ERGR-020-masking-* | HTTP は Repository 復元値を返す。DB 保存値 masking は repository IT が確認し、本 sub-feature は HTTP が redacted 値を raw secret 復号しないことを TC-IT-ERG-HTTP-010 で固定する |

## カバレッジ基準

- REQ-ERG-HTTP-001〜006 の各要件が最低 1 件の結合テストで検証されている。
- MSG-ERG-HTTP-001〜004 の各文言が静的文字列で照合されている。
- 親受入基準 #3〜6 / #10 / #12 / #14 / #15 が既存 domain / repository テストまたは本 sub-feature 結合テストで検証されている。
- T1〜T6 と OWASP API Security Top 10 2023 API1〜API10 の各脅威に対する対策または非該当根拠が最低 1 件のテストケースで確認されている。
- Bearer token 運用（生成強度、保管、ローテーション、ログ非露出）が TC-IT-ERG-HTTP-016 / TC-UT-ERG-HTTP-012 に接続されている。
- API 6 本すべてが単発ケースとユーザー観測可能な API flow smoke のどちらかで最低 1 回通る。
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

## 未決課題

| # | タスク | 起票先 |
|---|---|---|
| 該当なし | 未決課題なし。Issue #61 の実装 PR 内で上記テストを作成する。characterization task は対象外 | — |

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — 機能要件（REQ ID）
- [`detailed-design.md`](detailed-design.md) — MSG 確定文言
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様（受入基準）
- [`../system-test-design.md`](../system-test-design.md) — システムテスト（feature 内）
