# システムテスト戦略 — deliverable-template

> 関連: feature-spec.md §9 受入基準 1〜20 / UC-DT-001〜005 / §確定 R1-G
> 対象: UC-DT-001〜005 / AC#14〜20 / http-api 操作フロー（HTTP 黒箱）

本ドキュメントは DeliverableTemplate **業務概念全体** の E2E テスト戦略を凍結する。sub-feature（domain / repository / http-api / ai-validation / template-library）の IT / UT はそれぞれの `test-design.md` が担当する。

### テスト分類

| TC 範囲 | 対象 sub-feature | 検証対象 |
|---|---|---|
| TC-E2E-DT-001〜007 | domain / repository / http-api | DeliverableTemplate / RoleProfile ラウンドトリップ・SemVer・composition・HTTP API |
| TC-E2E-DT-008 | template-library | startup seed 冪等性・HTTP 即時アクセス |
| TC-E2E-DT-009 | template-library | RoleProfile プリセット（Pending: HTTP エンドポイント実装後）|

### ブラックボックス原則

- CEO 操作可能な HTTP API のみを使う。Repository / Application Service への直接アクセスは禁止。状態確認も HTTP API レスポンスのみで行う
- DB への直接 SQL クエリ・ORM セッション直アクセスは禁止
- External Review Gate の状態変化は `GET /api/gates/{gate_id}` の HTTP レスポンスで確認する

## E2E テストケース

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| TC-E2E-DT-001 | CEO | DeliverableTemplate ラウンドトリップ（アプリ再起動跨ぎ）| 1) DeliverableTemplate を作成・保存 → 2) アプリ再起動 → 3) `find_by_id` で復元 → 4) 復元テンプレートが元テンプレートと構造的等価（id / name / type / version / body / acceptance_criteria / composed_of 全属性一致）| 再起動後も DeliverableTemplate の全属性が保持されている |
| TC-E2E-DT-002 | CEO | SemVer バージョン管理（create v1.0.0 → create_new_version to v1.1.0 → restart → 両バージョン存在）| 1) `version=1.0.0` のテンプレート T1 を作成・保存 → 2) `create_new_version(minor_bump)` で T2（`version=1.1.0`）を生成・保存 → 3) アプリ再起動 → 4) T1 / T2 それぞれ `find_by_id` で復元 | T1（v1.0.0）/ T2（v1.1.0）の両バージョンが独立して復元される。T2 の `version.is_compatible_with(T1.version)` が True（major 一致） |
| TC-E2E-DT-003 | CEO | composition 合成テンプレ（create base templates A+B → compose into C → restart → C resolves to A+B criteria）| 1) ベーステンプレート A・B をそれぞれ作成・保存 → 2) A・B を `composed_of` に持つ合成テンプレート C を作成・保存 → 3) アプリ再起動 → 4) `find_by_id(C.id)` で復元 → 5) C の `composed_of` が A・B の参照を保持しているか検証 | 再起動後も C の `composed_of` に A・B への `DeliverableTemplateRef` が存在し、acceptance_criteria が A+B の合算として解決される |
| TC-E2E-DT-004 | CEO | RoleProfile ラウンドトリップ（define DEVELOPER RoleProfile with 2 template refs → restart → restored）| 1) テンプレート T1・T2 を作成・保存 → 2) `role=DEVELOPER` かつ `template_refs=[T1.id@v1.0.0, T2.id@v1.0.0]` の RoleProfile RP を作成・保存 → 3) アプリ再起動 → 4) `find_by_id(RP.id)` で復元 | 復元 RoleProfile の `role=DEVELOPER`、`template_refs` に T1・T2 への参照が全件保持されている |
| TC-E2E-DT-005 | CEO | HTTP API ラウンドトリップ（POST /api/deliverable-templates → GET → structural equality）| 1) `POST /api/deliverable-templates` に `{name, type=MARKDOWN, version="1.0.0", body, acceptance_criteria}` を送信 → 2) レスポンスの `id` を取得 → 3) `GET /api/deliverable-templates/{id}` で取得 | `POST` が HTTP 201 + `id` を返す。`GET` が HTTP 200 + リクエスト時の全属性と一致するレスポンスを返す |
| TC-E2E-DT-006 | CEO | JSON Schema バリデーション拒否（type=JSON_SCHEMA + invalid schema body → HTTP 422）| 1) `POST /api/deliverable-templates` に `{type=JSON_SCHEMA, body="{ invalid json schema }"}` を送信 | HTTP 422 が返る。レスポンス body に `[FAIL]` + `Next:` の 2 行構造（`invalid_json_schema_body` 業務ルール検証） |
| TC-E2E-DT-007 | CEO | 循環参照拒否（create template A → try to add A as composition of A → rejected with [FAIL] + Next:）| 1) テンプレート A を作成・保存 → 2) A 自身を `composed_of` に追加しようとする（`A.add_composition(ref=A.id)`）| ドメイン層が循環参照違反として `[FAIL]` + `Next:` の 2 行構造のエラーを返す。A の状態は変更前のまま保持される |
| TC-E2E-DT-008 | CEO | テンプレートライブラリ startup seed → HTTP 即時アクセス + 再起動冪等性（AC#18/19）| 1) Bootstrap.run() を実行（Stage 3b: seed 自動実行）→ 2) `GET /api/deliverable-templates` で全件取得 → 3) 代表テンプレート（`leader-plan` / `dev-design` / `tester-testdesign`）を `GET /api/deliverable-templates/{id}` で個別取得 → 4) Bootstrap.run() を再度実行（2 回目起動模倣）→ 5) `GET /api/deliverable-templates` で再度全件取得 | (1) 初回起動後: HTTP 200 + 12 件返却（LEADER 3 件 / DEVELOPER 5 件 / TESTER 3 件 / REVIEWER 1 件）(2) 各テンプレートの `name` / `type=MARKDOWN` / `version=1.0.0` が定数定義（`definitions.py`）と一致するレスポンスが返る (3) 2 回目起動後も件数が 12 件のまま変化しない（固定 UUID5 + UPSERT 冪等性） |
| TC-E2E-DT-009 | CEO | **【Pending】** RoleProfile プリセット自動適用 → HTTP 確認 + 手動設定の上書きなし確認（AC#20）| **HTTP エンドポイント `POST /api/empires/{id}/seed-templates` 実装後に着手**。現時点では Application Service 直接呼び出しとなるため E2E シナリオとして記述不可。エンドポイント実装後に本 TC を具体化する。| — |

## トレーサビリティ

### 受入基準 ↔ TC 対応

| 受入基準（feature-spec.md §9）| カバー TC |
|---|---|
| AC#14（永続化ラウンドトリップ）| TC-E2E-DT-001 |
| AC#15（composition 永続化）| TC-E2E-DT-002, TC-E2E-DT-003 |
| AC#16（AI 評価フロー / criterion_results 記録）| TC-IT-VS-003, TC-IT-VS-004（`ai-validation/test-design.md` 参照）|
| AC#17（FAILED / UNCERTAIN / PASSED 判定規則）| TC-IT-VS-003（FAILED パス）, TC-IT-VS-004（PASSED パス）（`ai-validation/test-design.md` 参照）|
| AC#18（startup seed 12 件 / HTTP 即時アクセス）| TC-E2E-DT-008 |
| AC#19（再起動冪等性）| TC-E2E-DT-008（Step 4〜5）|
| AC#20（RoleProfile プリセット / skip 戦略）| TC-E2E-DT-009（Pending: HTTP エンドポイント実装後）|

### TC ↔ sub-feature 対応

| TC | 主担当 sub-feature | 使用 HTTP API |
|---|---|---|
| TC-E2E-DT-001〜004 | domain / repository | なし（repository 操作）|
| TC-E2E-DT-005 | http-api | POST / GET `/api/deliverable-templates` |
| TC-E2E-DT-006 | http-api | POST `/api/deliverable-templates` |
| TC-E2E-DT-007 | domain | なし（domain 操作）|
| TC-E2E-DT-008 | template-library | GET `/api/deliverable-templates` / GET `/api/deliverable-templates/{id}` |
| TC-E2E-DT-009 | template-library | **Pending** — `POST /api/empires/{id}/seed-templates` 実装後に具体化 |

### 外部 I/O 依存マップ

| 外部 I/O | TC | 扱い |
|---|---|---|
| SQLite DB | TC-E2E-DT-001〜009 全件 | テスト用 in-memory SQLite 実接続。DB 直接クエリ禁止 |
| Bootstrap（Alembic）| TC-E2E-DT-008 | 実 Alembic + 実 SQLite（tmp_path）を使用。Stage 3b seed も実行 |
