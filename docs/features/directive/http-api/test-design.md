# テスト設計書

> feature: `directive` / sub-feature: `http-api`
> 関連 Issue: [#60 feat(task-http-api): Directive + Task lifecycle HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/60)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../system-test-design.md`](../system-test-design.md)

## 本書の役割

本書は **テストケースで検証可能な単位までトレーサビリティを担保する**。`basic-design.md §モジュール契約` の REQ-DR-HTTP-NNN / `detailed-design.md` の MSG-DR-HTTP-NNN / 親 `feature-spec.md` の受入基準 / 設計凍結事項（確定A〜F）を、それぞれ最低 1 件のテストケースで検証する。

**書くこと**:
- REQ-DR-HTTP-NNN / MSG-DR-HTTP-NNN / 受入基準 # / 確定A〜F を実テストケース（TC-IT / TC-UT）に紐付けるマトリクス
- 外部 I/O 依存マップ（raw fixture / factory / characterization 状態）
- 各レベルのテストケース定義（IT / UT）
- カバレッジ基準

**書かないこと**:
- E2E / システムテスト（TC-E2E-DR-003 等）→ 親 [`../system-test-design.md`](../system-test-design.md) が扱う
- 受入テスト → [`docs/acceptance-tests/scenarios/`](../../../acceptance-tests/scenarios/)

## テストケース ID 採番規則

| 番号帯 | 用途 |
|---|---|
| TC-IT-DRH-001〜016 | 結合テスト（HTTP リクエスト / DI / 例外ハンドラ）|
| TC-IT-DRH-020〜 | 予約番号帯（将来の Directive 拡張 API で利用）|
| TC-UT-DRH-001〜006 | ユニットテスト（スキーマ / ハンドラ / 依存方向）|

## テストマトリクス

| 要件 ID | 実装アーティファクト | テストケース ID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-DR-HTTP-001（正常系）| `directive_router` POST + `DirectiveService.issue` + アトミック UoW（確定B: Directive + Task 同時生成）| TC-IT-DRH-001〜005 | 結合 | 正常系 | feature-spec.md §9 #12 |
| REQ-DR-HTTP-001（確定A masking: text）| POST レスポンス `directive.text` → `<REDACTED:*>`（R1-F / T4）| TC-IT-DRH-006 | 結合 | セキュリティ | feature-spec.md §9 #13 |
| REQ-DR-HTTP-001（Room 不在 / UC-DR-006）| `DirectiveService.issue` → `RoomNotFoundError` → `room_not_found_handler` | TC-IT-DRH-007〜009 | 結合 | 異常系 | feature-spec.md §9 #14 |
| REQ-DR-HTTP-001（Room archived / UC-DR-006 / 確定E）| `DirectiveService.issue` → `RoomArchivedError` → `room_archived_handler` | TC-IT-DRH-010〜012 | 結合 | 異常系 | feature-spec.md §9 #15 |
| REQ-DR-HTTP-001（DirectiveInvariantViolation）| `DirectiveService.issue` → `DirectiveInvariantViolation` → handler | TC-IT-DRH-013 | 結合 | 異常系 | — |
| T3（不正 UUID）| FastAPI `UUID` 型強制 → 422 | TC-IT-DRH-014 | 結合 | セキュリティ | — |
| T1（CSRF）| `Origin: http://evil.example.com` → POST → 403 | TC-IT-DRH-015 | 結合 | セキュリティ | — |
| T2（スタックトレース非露出）| generic_exception_handler → 500 body に stacktrace なし | TC-IT-DRH-016 | 結合 | セキュリティ | — |
| MSG-DR-HTTP-001 | `directive_invariant_violation_handler` | TC-UT-DRH-001〜002 | ユニット | 異常系 | — |
| `DirectiveCreate` スキーマ | `schemas/directive.py` | TC-UT-DRH-003〜004 | ユニット | 正常系 / 異常系 | — |
| `DirectiveResponse` field_serializer masking（確定A / R1-F / T4）| `DirectiveResponse.text` masked シリアライズ | TC-UT-DRH-005 | ユニット | セキュリティ | feature-spec.md §9 #13 |
| 依存方向（interfaces → domain / infrastructure 直参照禁止）| `interfaces/http/routers/` + `interfaces/http/schemas/` を `ast.walk()` 全ノード走査（PR #105 退行禁止ルール準拠）| TC-UT-DRH-006 | ユニット（静的解析）| 異常系 | — |

**マトリクス充足の証拠**:
- REQ-DR-HTTP-001 に最低 1 件の正常系テストケース（TC-IT-DRH-001）
- REQ-DR-HTTP-001 の異常系（Room 不在 / archived / 業務ルール違反）が各々最低 1 件検証
- MSG-DR-HTTP-001 の `code` / `message` 文字列が静的照合で確認
- 親受入基準 12〜15（[`../feature-spec.md §9`](../feature-spec.md)）が TC-IT-DRH-001〜012 で 1:1 に対応
- T1〜T4 脅威への対策が TC-IT-DRH-015/016/014/006/TC-UT-DRH-005 で有効性確認
- 確定A〜F の全項目が最低 1 件のテストケースでカバー（確定B=TC-IT-DRH-004/005, 確定E=TC-IT-DRH-010）
- 孤児要件なし

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 |
|---|---|---|---|---|
| SQLite（テスト用 DB）| `get_session()` DI / lifespan 経由の Session / DirectiveRepository / TaskRepository / RoomRepository / EmpireRepository | `tests/fixtures/test_db.db`（tempdir）| `tests/factories/db.py`（http-api-foundation 定義済み）/ `tests/factories/directive.py`（**要新規作成** — TBD-1 参照）| 実 DB（pytest `tmp_path` 配下 tempfile）|
| FastAPI ASGI | HTTP リクエスト送信 | — | — | `httpx.AsyncClient(app=app, base_url="http://test")`（http-api-foundation 確定済み）|

**`tests/factories/directive.py` ステータス**: **要起票（TBD-1）**。`make_directive()` を実装着手前に作成すること。空欄のまま IT 実装に進むことはできない。

## 結合テストケース

| テストID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|---|
| TC-IT-DRH-001 | `directive_router` → `DirectiveService.issue` → 確定B（Directive + Task アトミック UoW）| 実 SQLite tempdb | Empire・Room 存在（archived=false）| `POST /api/rooms/{room_id}/directives` `{"text": "ブログ分析機能を実装してください"}` | HTTP 201, `DirectiveWithTaskResponse`（directive.id / task.id が文字列 UUID）|
| TC-IT-DRH-002 | `DirectiveService.issue` → response.directive.id 検証 | 実 SQLite tempdb | Empire・Room 存在 | `POST /api/rooms/{room_id}/directives` | HTTP 201, response.directive.id が有効 UUID 形式 |
| TC-IT-DRH-003 | `DirectiveService.issue` → response.directive.target_room_id 検証 | 実 SQLite tempdb | Empire・Room 存在 | `POST /api/rooms/{room_id}/directives` | HTTP 201, response.directive.target_room_id == room_id |
| TC-IT-DRH-004 | 確定B: アトミック UoW — response に task が含まれること | 実 SQLite tempdb | Empire・Room 存在 | `POST /api/rooms/{room_id}/directives` | HTTP 201, response.task が null でない（Directive + Task が同一 UoW で作成された物理証明）|
| TC-IT-DRH-005 | 確定B: Task.status = PENDING で起票されること | 実 SQLite tempdb | Empire・Room 存在 | `POST /api/rooms/{room_id}/directives` | HTTP 201, response.task.status == "PENDING" |
| TC-IT-DRH-006 | POST レスポンス `directive.text` masking（確定A / R1-F / T4）| 実 SQLite tempdb | Empire・Room 存在 | `POST /api/rooms/{room_id}/directives` `{"text": "ANTHROPIC_API_KEY=sk-ant-xxxx"}` | HTTP 201, response.directive.text に raw token が含まれない（`<REDACTED:ANTHROPIC_KEY>` 形式）— field_serializer が defense-in-depth として独立して動作することを assert |
| TC-IT-DRH-007 | `DirectiveService.issue` → `RoomNotFoundError` → `room_not_found_handler` | 実 SQLite tempdb | Room 未存在 | `POST /api/rooms/{ランダム UUID}/directives` `{"text": "テスト指令"}` | HTTP 404 |
| TC-IT-DRH-008 | `room_not_found_handler` → error code | 実 SQLite tempdb | Room 未存在 | `POST /api/rooms/{ランダム UUID}/directives` | HTTP 404, error.code == "not_found" |
| TC-IT-DRH-009 | `room_not_found_handler` → error message | 実 SQLite tempdb | Room 未存在 | `POST /api/rooms/{ランダム UUID}/directives` | HTTP 404, error.message == "Room not found." |
| TC-IT-DRH-010 | `DirectiveService.issue` → `RoomArchivedError` → `room_archived_handler`（確定E）| 実 SQLite tempdb | Room 存在（archived=true）| `POST /api/rooms/{archived_room_id}/directives` `{"text": "テスト指令"}` | HTTP 409 |
| TC-IT-DRH-011 | `room_archived_handler` → error code（確定E）| 実 SQLite tempdb | Room archived | `POST /api/rooms/{archived_room_id}/directives` | HTTP 409, error.code == "conflict" |
| TC-IT-DRH-012 | `room_archived_handler` → error message（確定E）| 実 SQLite tempdb | Room archived | `POST /api/rooms/{archived_room_id}/directives` | HTTP 409, error.message == "Room is archived and cannot be modified." |
| TC-IT-DRH-013 | `DirectiveService.issue` → `DirectiveInvariantViolation` → handler（MSG-DR-HTTP-001）| 実 SQLite tempdb | Empire・Room 存在 | `POST /api/rooms/{room_id}/directives` 業務ルール違反 payload（例: `text=""` 等）| HTTP 422, error.code == "validation_error" |
| TC-IT-DRH-014 | FastAPI `UUID` 型強制（T3）| — | — | `POST /api/rooms/not-a-valid-uuid/directives` | HTTP 422 |
| TC-IT-DRH-015 | CSRF ミドルウェア（T1）| 実 SQLite tempdb | Empire・Room 存在 | `POST /api/rooms/{room_id}/directives` に `Origin: http://evil.example.com` ヘッダ付与 | HTTP 403, error.code == "forbidden" |
| TC-IT-DRH-016 | generic_exception_handler（T2 スタックトレース非露出）| 実 SQLite tempdb | — | 内部エラーを誘発（`/test/raise-exception` エンドポイント）| HTTP 500, response body に `"Traceback"` / `"stacktrace"` 含まれない, error.code == "internal_error" |

## ユニットテストケース

| テストID | 対象 | 種別 | 入力（factory / 直接）| 期待結果 |
|---|---|---|---|---|
| TC-UT-DRH-001 | `directive_invariant_violation_handler`（MSG-DR-HTTP-001）| 異常系 | `DirectiveInvariantViolation("[FAIL] text must not be empty.\nNext: provide non-empty text.")` | HTTP 422 |
| TC-UT-DRH-002 | `directive_invariant_violation_handler` → error code | 異常系 | `DirectiveInvariantViolation(...)` | body.error.code == "validation_error" |
| TC-UT-DRH-003 | `DirectiveCreate` スキーマ（正常系）| 正常系 | `{"text": "ブログ分析機能を実装してください"}` | バリデーション通過 |
| TC-UT-DRH-004 | `DirectiveCreate` スキーマ（text="" / min_length 違反）| 異常系 | `{"text": ""}` | min_length 違反 `ValidationError` |
| TC-UT-DRH-005 | `DirectiveResponse` field_serializer による `text` masking（確定A / R1-F / T4）| セキュリティ | raw token 文字列（例: `"ANTHROPIC_API_KEY=sk-ant-xxxx"`）を持つ Directive オブジェクト → `DirectiveResponse` でシリアライズ | シリアライズ後の `text` に raw token が含まれない（`<REDACTED:ANTHROPIC_KEY>` 形式）|
| TC-UT-DRH-006 | 依存方向（静的解析）| 異常系 | `ast.walk(tree)` で `interfaces/http/routers/` + `interfaces/http/schemas/` 配下の全 `.py` を全ノード走査（PR #105 退行禁止ルール準拠。`dependencies.py` は DI 配線として対象外）| `bakufu.domain` / `bakufu.infrastructure` への直接 import が存在しないこと。クラス名: `TestStaticDependencyAnalysisDirective`（routers dir は `bakufu.interfaces.http.routers.directives` 実装後に参照）|

## カバレッジ基準

- REQ-DR-HTTP-001 が **最低 1 件の正常系** テストケース（TC-IT-DRH-001）で検証されている
- REQ-DR-HTTP-001 の異常系（Room 不在 / archived / 業務ルール違反）が各々 **最低 1 件** 検証されている
- MSG-DR-HTTP-001 の `code` 文字列が **静的文字列で照合** されている
- 親受入基準 12〜15（[`../feature-spec.md §9`](../feature-spec.md)）が TC-IT-DRH-001〜012 で 1:1 に対応
- T1〜T4 脅威への対策が TC-IT-DRH-015/016/014/006/TC-UT-DRH-005 で有効性確認
- 確定A masking: TC-IT-DRH-006 + TC-UT-DRH-005（field_serializer 独立動作）
- 確定B アトミック UoW: TC-IT-DRH-004/005（Directive + Task 同一 UoW 作成の物理証明）
- 確定E Room archived 確認: TC-IT-DRH-010〜012
- 行カバレッジ目標: **90% 以上**（`detailed-design.md §カバレッジ基準`）

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全 7 ジョブ緑であること
- ローカル:
  ```sh
  just test-backend   # pytest 実行（--cov で coverage 確認）
  ```
- 手動確認（uvicorn 起動後）:
  ```sh
  # Empire → Room 作成後
  # Directive 発行（text に raw token を含む場合 masked）
  curl -X POST http://localhost:8000/api/rooms/{room_id}/directives \
    -H "Content-Type: application/json" \
    -d '{"text": "ANTHROPIC_API_KEY=sk-ant-secret ブログ分析機能を実装してください"}' | jq .
  # → 201 {"directive": {"text": "<REDACTED:ANTHROPIC_KEY> ブログ分析機能...", ...}, "task": {"status": "PENDING", ...}}
  #   ← raw token が directive.text に露出しないことを確認

  # Room 不在 → 404
  curl -X POST http://localhost:8000/api/rooms/00000000-0000-0000-0000-000000000000/directives \
    -H "Content-Type: application/json" \
    -d '{"text": "テスト"}' | jq .
  # → 404 {"error": {"code": "not_found", "message": "Room not found."}}
  ```

## テストディレクトリ構造

```
backend/tests/
├── factories/
│   └── directive.py                              # 要新規作成（TBD-1）: make_directive
├── unit/
│   └── test_directive_http_api/
│       ├── __init__.py
│       └── test_handlers.py                     # TC-UT-DRH-001〜006
└── integration/
    └── test_directive_http_api/
        ├── __init__.py
        ├── conftest.py                           # DrTestCtx fixture / wiring（DirectiveService DI）
        ├── helpers.py                            # _create_empire / _create_room / _create_archived_room / _create_directive_via_http 等
        ├── test_issue.py                         # TC-IT-DRH-001〜013（ISSUE 正常系 + 異常系）
        └── test_security.py                      # TC-IT-DRH-014〜016
```

## 未決課題・要起票 characterization task

| # | 内容 | 起票先 |
|---|---|---|
| TBD-1 | `tests/factories/directive.py` 新規作成（`make_directive`）。実装着手前に完了必須。空欄のまま IT 実装に進んだ場合レビューで却下する | 実装 PR 着手前 |
| TBD-2 | `directive_invariant_violation_handler` の確定文言が domain 層 `str(exc)` に依存するため、`[FAIL]` / `\nNext:` 前処理ルール適用要否を実装時に確認すること（agent の `agent_invariant_violation_handler` 参照）| 実装着手前 |

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — 機能要件（REQ ID）
- [`detailed-design.md`](detailed-design.md) — MSG 確定文言 / スキーマ仕様 / 確定A〜F / アトミック UoW 実装契約
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様（受入基準 §9 #12〜15）
- [`../system-test-design.md`](../system-test-design.md) — E2E テスト（TC-E2E-DR-003）
- [`../../task/http-api/test-design.md`](../../task/http-api/test-design.md) — Task HTTP API テスト設計（Directive 発行後の Task lifecycle）
- [`../../agent/http-api/test-design.md`](../../agent/http-api/test-design.md) — 共通テストパターン参照（masking 独立防御証明、依存方向静的解析）
