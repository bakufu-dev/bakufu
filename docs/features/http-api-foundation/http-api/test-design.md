# テスト設計書

> feature: `http-api-foundation` / sub-feature: `http-api`
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md)

## 本書の役割

本書は **テストケースで検証可能な単位までトレーサビリティを担保する**。`basic-design.md §モジュール契約` の REQ-HAF-NNN / `detailed-design.md` の MSG-HAF-NNN / 親 `feature-spec.md` の受入基準・脅威 を、それぞれ最低 1 件のテストケースで検証する。

**書くこと**:
- REQ-HAF-NNN / MSG-HAF-NNN / 受入基準 # / T 脅威 # を実テストケース（TC-IT / TC-UT）に紐付けるマトリクス
- 外部 I/O 依存マップ
- 各レベルのテストケース定義
- カバレッジ基準

**書かないこと**:
- システムテスト → 親 [`../system-test-design.md`](../system-test-design.md)
- 受入テスト → [`docs/acceptance-tests/scenarios/`](../../../acceptance-tests/scenarios/)

## テストケース ID 採番規則

本 sub-feature のテスト ID 体系:

| 番号帯 | 用途 |
|---|---|
| TC-IT-HAF-001〜009 | 結合テスト（HTTP リクエスト / DI / lifespan）|
| TC-UT-HAF-001〜003 | ユニットテスト（M3 http-api-foundation 本 PR スコープ）|
| TC-UT-HAF-004〜009 | 予約番号帯（後続 Issue B〜G が application/services/ にメソッドを追記する際に割り当て）|
| TC-UT-HAF-010〜 | 静的解析系テスト専用帯（依存方向 / import 解析）|

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-HAF-001 | `interfaces/http/app.py` | TC-IT-HAF-007 | 結合 | 正常系 | feature-spec.md §9 #7 |
| REQ-HAF-002 | `interfaces/http/routers/health.py` | TC-IT-HAF-001 | 結合 | 正常系 | feature-spec.md §9 #1 |
| REQ-HAF-003 | `interfaces/http/error_handlers.py` | TC-IT-HAF-002, TC-IT-HAF-003, TC-IT-HAF-004 | 結合 | 異常系 | feature-spec.md §9 #2, #3, #4 |
| REQ-HAF-004 | `interfaces/http/dependencies.py` | TC-IT-HAF-006 | 結合 | 正常系 | feature-spec.md §9 #6 |
| REQ-HAF-005 | `interfaces/http/schemas/common.py` | TC-UT-HAF-001, TC-UT-HAF-002 | ユニット | 正常系 / 異常系 | Q-3 |
| REQ-HAF-006 | `application/services/*.py` | TC-UT-HAF-003 | ユニット | 正常系 | Q-3 |
| REQ-HAF-007 | `main.py` | TC-IT-HAF-007 | 結合 | 正常系 | feature-spec.md §9 #7 |
| MSG-HAF-001 | `error_handlers.http_exception_handler` | TC-IT-HAF-002 | 結合 | 異常系 | Q-3 |
| MSG-HAF-002 | `error_handlers.validation_exception_handler` | TC-IT-HAF-003 | 結合 | 異常系 | Q-3 |
| MSG-HAF-003 | `error_handlers.generic_exception_handler` | TC-IT-HAF-004 | 結合 | 異常系 | Q-3 |
| MSG-HAF-004 | `error_handlers.csrf_check_middleware` | TC-IT-HAF-008 | 結合 | 異常系 | Q-3 |
| T2（CSRF） | CSRF Origin 検証ミドルウェア | TC-IT-HAF-008 | 結合 | 異常系 | feature-spec.md §9 #8 |
| T3（スタックトレース非露出） | `error_handlers.generic_exception_handler` | TC-IT-HAF-004 | 結合 | 異常系 | Q-3 |
| 依存方向（interfaces → application、domain 直参照禁止） | 全 `interfaces/http/` モジュール | TC-UT-HAF-010 | ユニット（静的解析） | 異常系 | Q-3 |
| Q-1 | pyright / ruff | CI ジョブ | — | — | Q-1 |
| Q-2 | pytest --cov | CI ジョブ | — | — | Q-2 |
| Q-3 | 各 TC-IT-HAF-002〜004, TC-IT-HAF-008, TC-UT-HAF-010 | 結合 / ユニット | — | — | Q-3 |

**マトリクス充足の証拠**:
- REQ-HAF-001〜007 すべてに最低 1 件のテストケース（TC-IT または TC-UT）
- MSG-HAF-001〜004 すべてに `code` 文字列の静的照合（`assert response.json()["error"]["code"] == "not_found"` 等）
- 親受入基準 1〜8 の各々がシステムテスト（[`../system-test-design.md`](../system-test-design.md)）または結合テストで検証
- T2 / T3 脅威に対する対策が最低 1 件のテストケースで有効性確認
- 孤児要件なし

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 |
|---|---|---|---|---|
| SQLite（テスト用 DB） | `get_session()` DI / lifespan 検証 | `tests/fixtures/test_db.db`（tempdir）| `tests/factories/db.py`（async engine 生成）| 実 DB（pytest `tmp_path` 配下 tempfile）|
| FastAPI ASGI | HTTP リクエスト送信 | — | — | `httpx.AsyncClient(app=app, base_url="http://test")` |

## 結合テストケース

| テストID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|---|
| TC-IT-HAF-001 | `health_router` → `app` | 実 SQLite tempdb | lifespan 起動済み | `GET /health` | HTTP 200, `{"status": "ok"}` |
| TC-IT-HAF-002 | `error_handlers` → `app` | 実 SQLite tempdb | lifespan 起動済み | `GET /nonexistent` | HTTP 404, `{"error": {"code": "not_found", "message": "Resource not found."}}` |
| TC-IT-HAF-003 | `error_handlers` → `app` | 実 SQLite tempdb | lifespan 起動済み、テスト用 POST エンドポイントあり | Body なしで POST | HTTP 422, `{"error": {"code": "validation_error", "message": ...}}` |
| TC-IT-HAF-004 | `error_handlers` → `app` | 実 SQLite tempdb | lifespan 起動済み、例外を raise するテスト用エンドポイントあり | GET リクエスト | HTTP 500, `{"error": {"code": "internal_error", "message": "An internal server error occurred."}}`, Body にスタックトレース含まず |
| TC-IT-HAF-006 | `dependencies.get_session` → `app` | 実 SQLite tempdb | lifespan 起動済み | セッション確認エンドポイント呼び出し | `AsyncSession` が yield され、レスポンス後に close される（セッション ID をチェック）|
| TC-IT-HAF-007 | `app.lifespan` → `app.state` | 実 SQLite tempdb | なし | `AsyncClient(lifespan=...)` で起動〜GET /health〜close | 起動時に `session_factory` が `app.state` に設定、GET /health が 200 を返す、close 後に engine が dispose される |
| TC-IT-HAF-008 | CSRF ミドルウェア → `app` | 実 SQLite tempdb | lifespan 起動済み | `Origin: http://evil.example.com` ヘッダ付きでテスト用 POST エンドポイントを呼ぶ | HTTP 403, `{"error": {"code": "forbidden", "message": "CSRF check failed: Origin not allowed."}}` |

## ユニットテストケース

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---|---|---|---|---|
| TC-UT-HAF-001 | `ErrorResponse` モデル | 正常系 | `code="not_found"`, `message="Resource not found."` | `{"error": {"code": "not_found", "message": "Resource not found."}}` にシリアライズ |
| TC-UT-HAF-002 | `ErrorResponse` モデル | 異常系（extra フィールド） | `code="x"`, `message="y"`, `unexpected_field="z"` | `ValidationError` を raise（`extra="forbid"` 確認）|
| TC-UT-HAF-003 | `EmpireService.__init__` | 正常系 | `MockEmpireRepository()` | インスタンス生成成功、`_repo` に保持 |
| TC-UT-HAF-010 | 依存方向（静的解析: `ast` モジュール） | 異常系 | `ast.parse()` で `interfaces/http/` 配下の全 `.py` を解析し、トップレベル `import` / `from ... import` 文を抽出 | `bakufu.domain` / `bakufu.infrastructure` への直接 import が存在しないことを `assert` で確認する |

## カバレッジ基準

- REQ-HAF-001〜007 の各要件が **最低 1 件** のテストケースで検証されている
- MSG-HAF-001〜004 の各 `code` 文字列が **静的文字列で照合** されている（`assert response.json()["error"]["code"] == "..."` 形式）
- 親受入基準（[`../feature-spec.md §9`](../feature-spec.md)）の各々がシステムテスト（TC-ST-HAF-NNN）または結合テスト（TC-IT-HAF-NNN）で検証されている
- T2 / T3 脅威に対する対策が最低 1 件のテストケースで有効性を確認されている
- 行カバレッジ目標: **90% 以上**（Q-2 基準: `feature-spec.md §10`）

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全 7 ジョブ緑であること
- ローカル:
  ```
  just setup          # 初回セットアップ
  just test-backend   # pytest 実行（--cov で coverage 確認）
  ```
- 手動確認（uvicorn 起動後）: `curl http://localhost:8000/health` → `{"status":"ok"}`

## テストディレクトリ構造

```
backend/tests/
├── factories/
│   └── db.py                                   # async SQLite engine / session factory 生成
├── unit/
│   └── test_http_api_foundation_http_api.py     # TC-UT-HAF-001〜010
└── integration/
    └── test_http_api_foundation_http_api.py     # TC-IT-HAF-001〜008
```

システムテスト:
```
backend/tests/system/
└── test_http_api_foundation_lifecycle.py        # TC-ST-HAF-NNN（system-test-design.md で定義）
```

## 未決課題・要起票 characterization task

該当なし（TC-UT-HAF-010 の実装方法は `ast` モジュールで凍結済み）。

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — 機能要件（REQ ID）
- [`detailed-design.md`](detailed-design.md) — MSG 確定文言（確定 A〜G）
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様（受入基準）
- [`../system-test-design.md`](../system-test-design.md) — システムテスト（feature 内）
