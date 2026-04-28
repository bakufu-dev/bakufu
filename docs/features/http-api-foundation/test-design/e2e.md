# テストケース詳細 — E2E / 結合

<!-- feature: http-api-foundation -->
<!-- 配置先: docs/features/http-api-foundation/test-design/e2e.md -->
<!-- マトリクス・受入基準一覧は index.md を参照 -->

## E2E テスト（受入基準検証）

---

#### TC-E2E-HAF-001: GET /health → {"status":"ok"}（受入基準 1）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-005 |
| 工程 | 要件定義 |
| 種別 | 正常系 |
| 前提条件 | FastAPI アプリ起動済み（TestClient）。認証不要 |
| 操作 | `GET /health` |
| 期待結果 | HTTP 200 / レスポンス body に `"status": "ok"` を含む |

---

#### TC-E2E-HAF-002: GET /health → version フィールド存在（受入基準 1 補足）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-005 |
| 工程 | 要件定義 |
| 種別 | 正常系 |
| 前提条件 | FastAPI アプリ起動済み |
| 操作 | `GET /health` |
| 期待結果 | HTTP 200 / レスポンス body に `"version"` フィールドが存在し空文字列でない |

---

#### TC-E2E-HAF-003: GET /openapi.json → HTTP 200（受入基準 2）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 要件定義 |
| 種別 | 正常系 |
| 前提条件 | FastAPI アプリ起動済み |
| 操作 | `GET /openapi.json` |
| 期待結果 | HTTP 200 / Content-Type: application/json |

---

#### TC-E2E-HAF-004: 不正 JSON POST → {"error":...} 形式（受入基準 3、RequestValidationError）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 要件定義 |
| 種別 | 異常系 |
| 前提条件 | FastAPI アプリ起動済み。Pydantic body を期待するエンドポイントが存在する |
| 操作 | `POST /api/<endpoint>` に `Content-Type: application/json` + 不正な JSON ボディ（例: `{"invalid_field": 123}`） |
| 期待結果 | HTTP 422 / body が `{"error":{"code":"VALIDATION_ERROR","message":"..."}}` 形式 |

---

#### TC-E2E-HAF-005: HTTPException → {"error":...} 形式（受入基準 3、HTTPException）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 要件定義 |
| 種別 | 異常系 |
| 前提条件 | テスト用ルート（`HTTPException(status_code=404, detail="Not found")` を raise）が存在 |
| 操作 | テスト用ルートへの GET リクエスト |
| 期待結果 | HTTP 404 / body が `{"error":{"code":"HTTP_404","message":"Not found"}}` |

---

## 結合テスト（基本設計 モジュール間連携）

---

#### TC-IT-HAF-001: lifespan エンジン初期化（§確定 A、REQ-HAF-001）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | `create_app()` に実 lifespan を渡して TestClient を生成 |
| 操作 | TestClient の context manager 入退出（`with TestClient(create_app()) as client:`） |
| 期待結果 | `app.state.async_sessionmaker` が `None` でない / `AsyncEngine` が生成されエラーなく dispose される |

---

#### TC-IT-HAF-002: `app.state.async_sessionmaker` 格納確認（§確定 A）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | lifespan 付き TestClient |
| 操作 | lifespan 実行後に `app.state.async_sessionmaker` を参照 |
| 期待結果 | `async_sessionmaker` インスタンスが格納されている（`async_sessionmaker` 型） |

---

#### TC-IT-HAF-003: `get_session()` request スコープ（§確定 B、REQ-HAF-002）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-002 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | in-memory SQLite sessionmaker を `app.state` に注入。session の close を記録するテスト用ルート |
| 操作 | テスト用ルートに 2 回リクエスト送信 |
| 期待結果 | リクエストごとに別の `AsyncSession` インスタンスが生成され、各リクエスト終了後に session が close される |

---

#### TC-IT-HAF-004: DI factory `get_empire_repository` 型確認（REQ-HAF-002）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-002 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | in-memory SQLite セッションで `get_empire_repository(session)` を呼び出せるテスト |
| 操作 | `session` を直接渡して `get_empire_repository(session)` を呼び出す |
| 期待結果 | 戻り値が `EmpireRepository` Protocol を満たす（duck typing: `find_by_id` / `count` / `save` を持つ） |

---

#### TC-IT-HAF-005: DI 連鎖 full path（REQ-HAF-002、§確定 G）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-002 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | in-memory SQLite + lifespan 付き TestClient |
| 操作 | `Depends(get_empire_service)` を使うテスト用ルートへの GET リクエスト |
| 期待結果 | ルートハンドラが `EmpireService` インスタンスを受け取りエラーなく実行できる |

---

#### TC-IT-HAF-006: `app.state` 未初期化 → HTTP 500（REQ-HAF-002 異常系）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-002 |
| 工程 | 基本設計 |
| 種別 | 異常系 |
| 前提条件 | `create_app(lifespan=None)` かつ `app.state` に sessionmaker を注入しない |
| 操作 | `Depends(get_session)` を使うルートへのリクエスト |
| 期待結果 | HTTP 500 / `{"error":{"code":"INTERNAL_ERROR","message":"..."}}` |

---

#### TC-IT-HAF-008: GET /openapi.json → HTTP 200 + JSON（REQ-HAF-001）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | TestClient 起動済み |
| 操作 | `GET /openapi.json` |
| 期待結果 | HTTP 200 / body が JSON 解析可能 / `"paths"` キーを含む OpenAPI スキーマ |

---

#### TC-IT-HAF-009: CORS 未設定デフォルト（§確定 R1-F、REQ-HAF-001）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | `BAKUFU_CORS_ORIGINS` 未設定で `create_app()` |
| 操作 | `Origin: http://localhost:5173` ヘッダ付きリクエスト |
| 期待結果 | レスポンスに `Access-Control-Allow-Origin: http://localhost:5173` が含まれる |

---

#### TC-IT-HAF-010: CORS 未許可 Origin 拒否（§確定 R1-F）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 基本設計 |
| 種別 | 異常系 |
| 前提条件 | `BAKUFU_CORS_ORIGINS` 未設定 |
| 操作 | `Origin: https://evil.example.com` ヘッダ付きリクエスト |
| 期待結果 | レスポンスに `Access-Control-Allow-Origin` ヘッダが含まれない |

---

#### TC-IT-HAF-011: `HTTPException` 変換（REQ-HAF-003、§確定 E）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | `HTTPException(status_code=404, detail="Resource not found")` を raise するテスト用ルート |
| 操作 | テスト用ルートへのリクエスト |
| 期待結果 | HTTP 404 / `{"error":{"code":"HTTP_404","message":"Resource not found"}}` |

---

#### TC-IT-HAF-012: `RequestValidationError` 変換 + MSG-HAF-002 照合（REQ-HAF-003）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 基本設計 |
| 種別 | 異常系 |
| 前提条件 | Pydantic body (`id: UUID`) を期待するテスト用ルート |
| 操作 | `id` フィールドに `"not-a-uuid"` を POST |
| 期待結果 | HTTP 422 / `{"error":{"code":"VALIDATION_ERROR","message":"..."}}` / `"detail"` フィールドがリスト形式で存在 |

---

#### TC-IT-HAF-013: `IntegrityError` 変換 + MSG-HAF-003 照合 + コード分離確認（REQ-HAF-003）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 基本設計 |
| 種別 | 異常系 |
| 前提条件 | ① UNIQUE 制約違反を誘発するテスト用ルート / ② FK 違反を誘発するテスト用ルート |
| 操作 | ①②それぞれへリクエスト |
| 期待結果 | ① HTTP 409 / `code` が `"CONFLICT_DUPLICATE"` / ② HTTP 409 / `code` が `"CONFLICT_FK"` / いずれも `message` に `"[FAIL] Conflict:"` を含む |

---

#### TC-IT-HAF-014: 未捕捉 Exception → HTTP 500 + MSG-HAF-001 照合（REQ-HAF-003）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 基本設計 |
| 種別 | 異常系 |
| 前提条件 | `RuntimeError("unexpected")` を raise するテスト用ルート |
| 操作 | テスト用ルートへのリクエスト |
| 期待結果 | HTTP 500 / `{"error":{"code":"INTERNAL_ERROR","message":"Internal server error"}}` |

---

#### TC-IT-HAF-015: HTTP 500 レスポンス body にスタックトレースなし（T4 防御）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-003 |
| 工程 | 基本設計 |
| 種別 | 異常系 |
| 前提条件 | `RuntimeError("secret internal reason")` を raise するテスト用ルート |
| 操作 | テスト用ルートへのリクエスト |
| 期待結果 | HTTP 500 / response body に `"traceback"` / `"secret internal reason"` / `"Traceback"` が含まれない |

---

#### TC-IT-HAF-016: `service.find_all()` → `(items, total)` tuple（§確定 F）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-007 |
| 工程 | 基本設計 |
| 種別 | 正常系 |
| 前提条件 | in-memory SQLite に Empire 3 件 INSERT 済み |
| 操作 | `empire_service.find_all(offset=0, limit=10)` |
| 期待結果 | 戻り値が `(list[Empire], int)` 型 / `total == 3` / `len(items) == 3` |
