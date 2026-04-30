# システムテスト戦略 — deliverable-template

> 関連: feature-spec.md §9 受入基準 1〜7 / UC-DT-001〜005
> 対象: UC-DT-001〜005 / http-api 操作フロー（HTTP 黒箱）

本ドキュメントは DeliverableTemplate **業務概念全体** の E2E テスト戦略を凍結する。sub-feature（domain / repository / http-api）の IT / UT はそれぞれの `test-design.md` が担当する。

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
