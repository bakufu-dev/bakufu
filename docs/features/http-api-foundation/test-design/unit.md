# テストケース詳細 — ユニット / CI

<!-- feature: http-api-foundation -->
<!-- 配置先: docs/features/http-api-foundation/test-design/unit.md -->
<!-- マトリクス・受入基準一覧は index.md を参照 -->

## ユニットテスト（詳細設計 クラス/メソッド）

---

#### TC-UT-HAF-001: `PaginatedResponse[T]` 4 フィールド構造（§確定 C）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-004 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `PaginatedResponse(items=[...], total=5, offset=0, limit=20)` を構築 |
| 期待結果 | `items` / `total` / `offset` / `limit` の 4 フィールドが model_dump に含まれる |

---

#### TC-UT-HAF-002: `limit` 上限 100 超 → ValidationError（§確定 C）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-004 |
| 工程 | 詳細設計 |
| 種別 | 境界値 |
| 操作 | `PaginatedResponse(items=[], total=0, offset=0, limit=101)` を構築 |
| 期待結果 | `pydantic.ValidationError` が raise される |

---

#### TC-UT-HAF-003: `ErrorResponse` body 構造（§確定 E）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-004 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `ErrorResponse(error=ErrorDetail(code="HTTP_404", message="Not found"))` を構築 |
| 期待結果 | `model_dump()` が `{"error":{"code":"HTTP_404","message":"Not found"}}` と一致 |

---

#### TC-UT-HAF-004: `ErrorDetail.detail` は VALIDATION_ERROR 時のみ（§確定 E）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-004 |
| 工程 | 詳細設計 |
| 種別 | 境界値 |
| 操作 | `detail=None` で ErrorDetail 構築 / `detail=[{"field": "id", "error": "invalid"}]` で構築 |
| 期待結果 | `detail=None` の場合 model_dump で `detail` が `None` または欠落 / リスト付きの場合 `detail` フィールドにリストが入る |

---

#### TC-UT-HAF-006: `BAKUFU_BIND_HOST` 未設定 → `127.0.0.1`（§確定 D）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-006 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `BAKUFU_BIND_HOST` を unset して main.py の bind 設定読み取り関数を呼ぶ |
| 期待結果 | host が `"127.0.0.1"` |

---

#### TC-UT-HAF-007: `BAKUFU_BIND_PORT` 未設定 → `8000`（§確定 D）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-006 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `BAKUFU_BIND_PORT` を unset して bind 設定読み取り関数を呼ぶ |
| 期待結果 | port が `8000` |

---

#### TC-UT-HAF-008: `BAKUFU_BIND_PORT` 非数値 → `ValueError`（§確定 D、Fail Fast）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-006 |
| 工程 | 詳細設計 |
| 種別 | 異常系 |
| 操作 | `BAKUFU_BIND_PORT=abc` を設定して bind 設定読み取り関数を呼ぶ |
| 期待結果 | `ValueError` が raise される |

---

#### TC-UT-HAF-009: `BAKUFU_RELOAD` 未設定 → `False`（§確定 D）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-006 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `BAKUFU_RELOAD` を unset して bind 設定読み取り関数を呼ぶ |
| 期待結果 | reload が `False` |

---

#### TC-UT-HAF-010: service が Repository Protocol を受け取る（REQ-HAF-007）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-007 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `EmpireService(mock_repo)` を構築（`mock_repo` は `EmpireRepository` Protocol を満たす MagicMock） |
| 期待結果 | 構築が成功する / `service._repo is mock_repo` |

---

#### TC-UT-HAF-011: `service.save()` が `commit()` を呼ばない（§確定 R1-H）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-007 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `mock_repo` を注入した `EmpireService.save(empire)` を呼ぶ |
| 期待結果 | `mock_repo.session.commit.assert_not_called()` が pass（または commit 相当の呼び出しがない） |

---

#### TC-UT-HAF-012: `service.find_all()` が `(items, total)` tuple を返す（§確定 F）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-007 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `mock_repo.find_all.return_value = [empire1, empire2]` / `mock_repo.count.return_value = 2` で `find_all(offset=0, limit=20)` |
| 期待結果 | 戻り値が `([empire1, empire2], 2)` の tuple |

---

#### TC-UT-HAF-013: service が Repository 具象型でなく Protocol に依存（REQ-HAF-007）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-007 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | `EmpireService` のソースコードの import を確認（`SqliteEmpireRepository` を直接 import していないこと） |
| 期待結果 | `EmpireService` が `bakufu.infrastructure.*` への直接 import を持たない（pyright + grep で確認） |

---

#### TC-UT-HAF-014: エラーコード体系の文字列確認（§確定 E）

| 項目 | 内容 |
|------|------|
| 対応 §確定 E | エラーコード体系 |
| 工程 | 詳細設計 |
| 種別 | 正常系 |
| 操作 | エラーコード定数（または文字列リテラル）の値を確認 |
| 期待結果 | `"HTTP_404"` 形式 / `"VALIDATION_ERROR"` / `"CONFLICT_DUPLICATE"` / `"CONFLICT_FK"` / `"INTERNAL_ERROR"` が大文字スネークケース ASCII |

---

#### TC-UT-HAF-015: `BAKUFU_CORS_ORIGINS=*` → `ValueError` 起動拒否（T2 防御、§確定 R1-F）

| 項目 | 内容 |
|------|------|
| 対応 REQ | REQ-HAF-001 |
| 工程 | 詳細設計 |
| 種別 | 異常系 |
| 前提条件 | `BAKUFU_CORS_ORIGINS=*` を設定（monkeypatch） |
| 操作 | `create_app()` または CORS 設定読み取り関数を呼ぶ |
| 期待結果 | `ValueError` が raise される（ワイルドカード全許可は Fail Fast で起動拒否）/ `BAKUFU_BIND_HOST=0.0.0.0` + `*` の組み合わせで T2 脅威対策が無効化されることを構造的に防ぐ |

---

## CI テスト

---

#### TC-CI-HAF-001: pyright 0 errors（受入基準 5）

| 項目 | 内容 |
|------|------|
| 対応 受入基準 | 5 |
| 操作 | `uv run pyright` |
| 期待結果 | `0 errors, 0 warnings` |

---

#### TC-CI-HAF-002: CI 7 ジョブ全緑（受入基準 5）

| 項目 | 内容 |
|------|------|
| 対応 受入基準 | 5 |
| 操作 | PR の CI（branch-policy / pr-title-check / lint / typecheck / test-backend / test-frontend / audit） |
| 期待結果 | 全 7 ジョブが ✅ |
