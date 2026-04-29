# テスト設計書

> feature: `empire` / sub-feature: `http-api`
> 関連 Issue: [#56 feat(empire-http-api): Empire HTTP API (M3-B)](https://github.com/bakufu-dev/bakufu/issues/56)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../system-test-design.md`](../system-test-design.md)

## 本書の役割

本書は **テストケースで検証可能な単位までトレーサビリティを担保する**。`basic-design.md §モジュール契約` の REQ-EM-HTTP-NNN / `detailed-design.md` の MSG-EM-HTTP-NNN / 親 `feature-spec.md` の受入基準 / 脅威 を、それぞれ最低 1 件のテストケースで検証する。

**書くこと**:
- REQ-EM-HTTP-NNN / MSG-EM-HTTP-NNN / 受入基準 # / 脅威 を実テストケース（TC-IT / TC-UT）に紐付けるマトリクス
- 外部 I/O 依存マップ
- 各レベルのテストケース定義
- カバレッジ基準

**書かないこと**:
- E2E テスト（TC-E2E-EM-003）→ 親 [`../system-test-design.md`](../system-test-design.md) が扱う
- 受入テスト → [`docs/acceptance-tests/scenarios/`](../../../acceptance-tests/scenarios/)

## テストケース ID 採番規則

本 sub-feature のテスト ID 体系:

| 番号帯 | 用途 |
|---|---|
| TC-IT-EM-HTTP-001〜009 | 結合テスト（HTTP リクエスト / DI / 例外ハンドラ）|
| TC-IT-EM-HTTP-010〜 | 予約番号帯（将来の empire 拡張 API で利用）|
| TC-UT-EM-HTTP-001〜005 | ユニットテスト（スキーマ / サービスメソッド / 依存方向）|
| TC-UT-EM-HTTP-010〜 | 静的解析系テスト専用帯（依存方向 / import 解析）|

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-EM-HTTP-001 | `empire_router` POST + `EmpireService.create` | TC-IT-EM-HTTP-001 | 結合 | 正常系 | feature-spec.md §9 #12 |
| REQ-EM-HTTP-001（R1-5 違反）| `empire_router` POST + `EmpireAlreadyExistsError` | TC-IT-EM-HTTP-002 | 結合 | 異常系 | feature-spec.md §9 #13 |
| REQ-EM-HTTP-002 | `empire_router` GET list + `EmpireService.find_all` | TC-IT-EM-HTTP-003 | 結合 | 正常系 | feature-spec.md §9 #14 |
| REQ-EM-HTTP-003 | `empire_router` GET by id + `EmpireService.find_by_id` | TC-IT-EM-HTTP-004 | 結合 | 正常系 | feature-spec.md §9 #15 |
| REQ-EM-HTTP-003（不在）| `empire_router` GET by id + `EmpireNotFoundError` | TC-IT-EM-HTTP-005 | 結合 | 異常系 | feature-spec.md §9 #16 |
| REQ-EM-HTTP-004 | `empire_router` PATCH + `EmpireService.update` | TC-IT-EM-HTTP-006 | 結合 | 正常系 | feature-spec.md §9 #17 |
| REQ-EM-HTTP-004（R1-8 違反）| `empire_router` PATCH + `EmpireArchivedError` | TC-IT-EM-HTTP-007 | 結合 | 異常系 | feature-spec.md §9 #18 |
| REQ-EM-HTTP-005 | `empire_router` DELETE + `EmpireService.archive` | TC-IT-EM-HTTP-008 | 結合 | 正常系 | feature-spec.md §9 #19 |
| REQ-EM-HTTP-005（不在）| `empire_router` DELETE + `EmpireNotFoundError` | TC-IT-EM-HTTP-009 | 結合 | 異常系 | feature-spec.md §9 #20 |
| MSG-EM-HTTP-001 | `empire_already_exists_handler` | TC-IT-EM-HTTP-002 | 結合 | 異常系 | Q-3 |
| MSG-EM-HTTP-002 | `empire_not_found_handler` | TC-IT-EM-HTTP-005 | 結合 | 異常系 | Q-3 |
| MSG-EM-HTTP-003 | `empire_archived_handler` | TC-IT-EM-HTTP-007 | 結合 | 異常系 | Q-3 |
| MSG-EM-HTTP-004 | `empire_invariant_violation_handler` | TC-UT-EM-HTTP-004 | ユニット | 異常系 | Q-3 |
| `EmpireCreate` スキーマ | `schemas/empire.py` | TC-UT-EM-HTTP-001 | ユニット | 正常系 / 異常系 | Q-3 |
| `EmpireUpdate` スキーマ | `schemas/empire.py` | TC-UT-EM-HTTP-002 | ユニット | 正常系 / 異常系 | Q-3 |
| `EmpireResponse` スキーマ | `schemas/empire.py` | TC-UT-EM-HTTP-003 | ユニット | 正常系 | Q-3 |
| `EmpireService` メソッド | `application/services/empire_service.py` | TC-UT-EM-HTTP-005 | ユニット | 正常系 | Q-3 |
| T1（CSRF）| CSRF ミドルウェア → POST /api/empires | TC-IT-EM-HTTP-002（Origin 不一致 → 403）| 結合 | 異常系 | Q-3 |
| T2（スタックトレース非露出）| `exception_handler` → 500 レスポンス | TC-IT-EM-HTTP-005（500 時 Body 検査）| 結合 | 異常系 | Q-3 |
| 依存方向（interfaces → domain 直参照禁止）| 全 `interfaces/http/` モジュール | TC-UT-EM-HTTP-010 | ユニット（静的解析）| 異常系 | Q-3 |
| Q-1 | pyright / ruff | CI ジョブ | — | — | Q-1 |
| Q-2 | pytest --cov | CI ジョブ | — | — | Q-2 |

**マトリクス充足の証拠**:
- REQ-EM-HTTP-001〜005 すべてに最低 1 件の正常系テストケース（TC-IT-EM-HTTP-001/003/004/006/008）
- REQ-EM-HTTP-001/003/004/005 の異常系（TC-IT-EM-HTTP-002/005/007/009）で拒否シグナルを検証
- MSG-EM-HTTP-001〜004 の各々が `response.json()["error"]["code"]` / `"message"` の静的照合で確認
- 親受入基準 12〜20 のすべてが TC-IT-EM-HTTP-001〜009 で対応（1:1）
- T1（CSRF）/ T2（スタックトレース）脅威への対策が最低 1 件で有効性確認
- 孤児要件なし

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 |
|---|---|---|---|---|
| SQLite（テスト用 DB）| `get_session()` DI / lifespan 経由の Session / EmpireRepository | `tests/fixtures/test_db.db`（tempdir）| `tests/factories/db.py`（http-api-foundation で定義済み）| 実 DB（pytest `tmp_path` 配下 tempfile）|
| FastAPI ASGI | HTTP リクエスト送信 | — | — | `httpx.AsyncClient(app=app, base_url="http://test")`（http-api-foundation 確定済み）|

## 結合テストケース

| テストID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|---|
| TC-IT-EM-HTTP-001 | `empire_router` → `EmpireService.create` → `SqliteEmpireRepository` | 実 SQLite tempdb | lifespan 起動済み、Empire 未存在 | `POST /api/empires` `{"name": "山田の幕府"}` | HTTP 201, `{"id": <uuid>, "name": "山田の幕府", "archived": false, "rooms": [], "agents": []}` |
| TC-IT-EM-HTTP-002 | `empire_router` → `EmpireService.create` → `EmpireAlreadyExistsError` → `empire_already_exists_handler` | 実 SQLite tempdb | lifespan 起動済み、Empire 1 件存在 | `POST /api/empires` `{"name": "2つ目の幕府"}` | HTTP 409, `{"error": {"code": "conflict", "message": "Empire already exists."}}` |
| TC-IT-EM-HTTP-003 | `empire_router` → `EmpireService.find_all` → `SqliteEmpireRepository.find_all` | 実 SQLite tempdb | lifespan 起動済み | (a) Empire 未存在 で `GET /api/empires` (b) Empire 存在下 で `GET /api/empires` | (a) HTTP 200, `{"items": [], "total": 0}` (b) HTTP 200, `{"items": [<EmpireResponse>], "total": 1}` |
| TC-IT-EM-HTTP-004 | `empire_router` → `EmpireService.find_by_id` → `SqliteEmpireRepository.find_by_id` | 実 SQLite tempdb | lifespan 起動済み、Empire 存在 | `GET /api/empires/{id}` | HTTP 200, `EmpireResponse`（name 一致確認）|
| TC-IT-EM-HTTP-005 | `empire_router` → `EmpireService.find_by_id` → `EmpireNotFoundError` → `empire_not_found_handler` | 実 SQLite tempdb | lifespan 起動済み | `GET /api/empires/{ランダム UUID}` | HTTP 404, `{"error": {"code": "not_found", "message": "Empire not found."}}` |
| TC-IT-EM-HTTP-006 | `empire_router` → `EmpireService.update` → `SqliteEmpireRepository.save` | 実 SQLite tempdb | lifespan 起動済み、Empire 存在（archived=false）| `PATCH /api/empires/{id}` `{"name": "新山田の幕府"}` | HTTP 200, `EmpireResponse`（name="新山田の幕府"）|
| TC-IT-EM-HTTP-007 | `empire_router` → `EmpireService.update` → `EmpireArchivedError` → `empire_archived_handler` | 実 SQLite tempdb | lifespan 起動済み、Empire 存在（archived=true）| `PATCH /api/empires/{id}` `{"name": "変更試み"}` | HTTP 409, `{"error": {"code": "conflict", "message": "Empire is archived and cannot be modified."}}` |
| TC-IT-EM-HTTP-008 | `empire_router` → `EmpireService.archive` → `SqliteEmpireRepository.save` | 実 SQLite tempdb | lifespan 起動済み、Empire 存在（archived=false）| `DELETE /api/empires/{id}` | HTTP 204 No Content, 続けて `GET /api/empires/{id}` → `{"archived": true}` |
| TC-IT-EM-HTTP-009 | `empire_router` → `EmpireService.archive` → `EmpireNotFoundError` → `empire_not_found_handler` | 実 SQLite tempdb | lifespan 起動済み | `DELETE /api/empires/{ランダム UUID}` | HTTP 404, `{"error": {"code": "not_found", "message": "Empire not found."}}` |

**CSRF 結合テスト補足**: TC-IT-EM-HTTP-002 の異常系バリアントとして、`Origin: http://evil.example.com` ヘッダ付きの `POST /api/empires` が HTTP 403 を返すことを確認する（http-api-foundation TC-IT-HAF-008 と同一パターン、empire router でも CSRF ミドルウェアが適用されることの物理保証）。

## ユニットテストケース

| テストID | 対象 | 種別 | 入力（factory）| 期待結果 |
|---|---|---|---|---|
| TC-UT-EM-HTTP-001 | `EmpireCreate` スキーマ | 正常系 / 異常系 | (a) `name="山田の幕府"` (b) `name=""` (c) `name="x"*81` (d) `extra_field="z"` | (a) バリデーション通過 (b) min_length 違反で `ValidationError` (c) max_length 違反で `ValidationError` (d) extra 禁止で `ValidationError` |
| TC-UT-EM-HTTP-002 | `EmpireUpdate` スキーマ | 正常系 / 異常系 | (a) `name="新名前"` (b) `name=None` (c) `name=""` | (a) バリデーション通過 (b) name=None で通過（部分更新）(c) min_length 違反で `ValidationError` |
| TC-UT-EM-HTTP-003 | `EmpireResponse` スキーマ | 正常系 | Empire ドメインオブジェクト（id / name / archived / rooms / agents）| `id` が str、`archived` が bool、`rooms` / `agents` がリストで正しくシリアライズされる |
| TC-UT-EM-HTTP-004 | `empire_invariant_violation_handler` | 異常系 | `EmpireInvariantViolation("[FAIL] Empire name は 1〜80 文字でなければなりません。\nNext: 1〜80 文字の名前を指定してください。")` | HTTP 422, `{"error": {"code": "validation_error", "message": "Empire name は 1〜80 文字でなければなりません。"}}` — `[FAIL]` プレフィックスと `\nNext:.*` が除去されていることを assert する（detailed-design.md §確定C 前処理ルール検証）|
| TC-UT-EM-HTTP-005 | `EmpireService.__init__` + `create` | 正常系 | `MockEmpireRepository(count=0, save=None)` | `create("山田の幕府")` がインスタンス生成成功し、`_repo.save()` が 1 回呼ばれる |
| TC-UT-EM-HTTP-010 | 依存方向（静的解析: `ast` モジュール）| 異常系 | `ast.parse()` で `interfaces/http/` 配下の全 `.py` を解析し、トップレベル `import` / `from ... import` 文を抽出 | `bakufu.domain` / `bakufu.infrastructure` への直接 import が存在しないことを `assert` で確認（http-api-foundation TC-UT-HAF-010 と同一検証パターン）|

## カバレッジ基準

- REQ-EM-HTTP-001〜005 の各要件が **最低 1 件の正常系** テストケースで検証されている
- REQ-EM-HTTP-001/003/004/005 の異常系（例外経路）が **最低 1 件** 検証されている
- MSG-EM-HTTP-001〜004 の各 `code` / `message` 文字列が **静的文字列で照合** されている（`assert response.json()["error"]["code"] == "conflict"` 等）
- 親受入基準（[`../feature-spec.md §9`](../feature-spec.md) #12〜20）の各々が TC-IT-EM-HTTP-001〜009 で 1:1 に検証されている
- T1（CSRF）/ T2（スタックトレース非露出）脅威への対策が最低 1 件のテストケースで有効性確認されている
- 行カバレッジ目標: **90% 以上**（Q-2 基準: [`../feature-spec.md §10`](../feature-spec.md)）

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全 7 ジョブ緑であること
- ローカル:
  ```
  just test-backend   # pytest 実行（--cov で coverage 確認）
  ```
- 手動確認（uvicorn 起動後）:
  ```
  curl -X POST http://localhost:8000/api/empires -H "Content-Type: application/json" -d '{"name": "山田の幕府"}'
  # → 201 {"id": "...", "name": "山田の幕府", "archived": false, "rooms": [], "agents": []}
  curl http://localhost:8000/api/empires
  # → 200 {"items": [...], "total": 1}
  ```

## テストディレクトリ構造

```
backend/tests/
├── unit/
│   └── test_empire_http_api.py          # TC-UT-EM-HTTP-001〜005, 010
└── integration/
    └── test_empire_http_api.py          # TC-IT-EM-HTTP-001〜009
```

E2E テスト（TC-E2E-EM-003: HTTP ライフサイクル一気通貫）:
```
backend/tests/e2e/
└── test_empire_http_api.py              # TC-E2E-EM-003（system-test-design.md で定義）
```

## 未決課題・要起票 characterization task

| # | 内容 | 起票先 |
|---|---|---|
| Q-OPEN-1 | `EmpireInvariantViolation.kind` フィールドによるエラー細分化（422 と 409 の分岐）が将来必要になった場合の設計変更 | 将来 Issue |
| Q-OPEN-2 | アーカイブ済み Empire への `hire_agent` / `establish_room` 呼び出しのドメイン層防護（domain が自分で reject するか service が guard するか）| 将来 Issue |

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — 機能要件（REQ ID）
- [`detailed-design.md`](detailed-design.md) — MSG 確定文言 / スキーマ仕様
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様（受入基準 §9 #12〜20）
- [`../system-test-design.md`](../system-test-design.md) — E2E テスト（TC-E2E-EM-003）
- [`../../http-api-foundation/http-api/test-design.md`](../../http-api-foundation/http-api/test-design.md) — 共通テストパターン参照
