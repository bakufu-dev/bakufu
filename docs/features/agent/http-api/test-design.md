# テスト設計書

> feature: `agent` / sub-feature: `http-api`
> 関連 Issue: [#59 feat(agent-http-api): Agent CRUD HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/59)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../system-test-design.md`](../system-test-design.md)

## 本書の役割

本書は **テストケースで検証可能な単位までトレーサビリティを担保する**。`basic-design.md §モジュール契約` の REQ-AG-HTTP-NNN / `detailed-design.md` の MSG-AG-HTTP-NNN / 親 `feature-spec.md` の受入基準 / セキュリティ脅威 T1〜T5 を、それぞれ最低 1 件のテストケースで検証する。

**書くこと**:
- REQ-AG-HTTP-NNN / MSG-AG-HTTP-NNN / 受入基準 # / 脅威 T を実テストケース（TC-IT / TC-UT）に紐付けるマトリクス
- 外部 I/O 依存マップ（raw fixture / factory / characterization 状態）
- 各レベルのテストケース定義（IT / UT）
- カバレッジ基準

**書かないこと**:
- E2E / システムテスト（TC-E2E-AG-004 等）→ 親 [`../system-test-design.md`](../system-test-design.md) が扱う
- 受入テスト → [`docs/acceptance-tests/scenarios/`](../../../acceptance-tests/scenarios/)

## テストケース ID 採番規則

| 番号帯 | 用途 |
|---|---|
| TC-IT-AGH-001〜027 | 結合テスト（HTTP リクエスト / DI / 例外ハンドラ）|
| TC-IT-AGH-030〜 | 予約番号帯（将来の Agent 拡張 API で利用）|
| TC-UT-AGH-001〜009 | ユニットテスト（スキーマ / ハンドラ / 依存方向）|

## テストマトリクス

| 要件 ID | 実装アーティファクト | テストケース ID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-AG-HTTP-001（正常系）| `agent_router` POST + `AgentService.hire` + `SqliteAgentRepository.save` | TC-IT-AGH-001 | 結合 | 正常系 | feature-spec.md §9 #13 |
| REQ-AG-HTTP-001（Empire 不在）| `AgentService.hire` → `EmpireNotFoundError` → `empire_not_found_handler` | TC-IT-AGH-002 | 結合 | 異常系 | — |
| REQ-AG-HTTP-001（name 重複）| `AgentService.hire` → `AgentNameAlreadyExistsError` → `agent_name_already_exists_handler` | TC-IT-AGH-003 | 結合 | 異常系 | — |
| REQ-AG-HTTP-001（R1-2 違反: providers=0）| `AgentService.hire` → `AgentInvariantViolation` → `agent_invariant_violation_handler` | TC-IT-AGH-004 | 結合 | 異常系 | — |
| REQ-AG-HTTP-001（R1-3 違反: is_default 2 件）| `AgentService.hire` → `AgentInvariantViolation` → `agent_invariant_violation_handler` | TC-IT-AGH-005 | 結合 | 異常系 | — |
| REQ-AG-HTTP-001（R1-9 masking / A02）| POST レスポンス `persona.prompt_body` masked | TC-IT-AGH-006 | 結合 | セキュリティ | feature-spec.md §9 #13 |
| REQ-AG-HTTP-002（正常系）| `agent_router` GET list + `AgentService.find_by_empire` + `SqliteAgentRepository.find_all_by_empire` | TC-IT-AGH-007 | 結合 | 正常系 | feature-spec.md §9 #14 |
| REQ-AG-HTTP-002（0 件）| `AgentService.find_by_empire` → 空リスト | TC-IT-AGH-008 | 結合 | 正常系 | feature-spec.md §9 #14 |
| REQ-AG-HTTP-002（Empire 不在）| `AgentService.find_by_empire` → `EmpireNotFoundError` | TC-IT-AGH-009 | 結合 | 異常系 | — |
| REQ-AG-HTTP-002（アーカイブ済み含む）| GET list がアーカイブ済み Agent を含む | TC-IT-AGH-010 | 結合 | 正常系 | — |
| REQ-AG-HTTP-003（正常系）| `agent_router` GET + `AgentService.find_by_id` + `SqliteAgentRepository.find_by_id` | TC-IT-AGH-011 | 結合 | 正常系 | feature-spec.md §9 #15 |
| REQ-AG-HTTP-003（Agent 不在）| `AgentService.find_by_id` → `AgentNotFoundError` → `agent_not_found_handler` | TC-IT-AGH-012 | 結合 | 異常系 | — |
| REQ-AG-HTTP-003（R1-9 masking / A02）| GET レスポンス `persona.prompt_body` が `<REDACTED:*>` | TC-IT-AGH-013 | 結合 | セキュリティ | feature-spec.md §9 #15 |
| REQ-AG-HTTP-004（name のみ更新）| `agent_router` PATCH + `AgentService.update` + `SqliteAgentRepository.save` | TC-IT-AGH-014 | 結合 | 正常系 | feature-spec.md §9 #16 |
| REQ-AG-HTTP-004（providers 全置換）| PATCH で providers を全置換 | TC-IT-AGH-015 | 結合 | 正常系 | feature-spec.md §9 #16 |
| REQ-AG-HTTP-004（Agent 不在）| `AgentService.update` → `AgentNotFoundError` | TC-IT-AGH-016 | 結合 | 異常系 | — |
| REQ-AG-HTTP-004（archived）| `AgentService.update` → `AgentArchivedError` → `agent_archived_handler` | TC-IT-AGH-017 | 結合 | 異常系 | feature-spec.md §9 #17 |
| REQ-AG-HTTP-004（name 重複）| `AgentService.update` → `AgentNameAlreadyExistsError` | TC-IT-AGH-018 | 結合 | 異常系 | — |
| REQ-AG-HTTP-004（不変条件違反）| `AgentService.update` → `AgentInvariantViolation` | TC-IT-AGH-019 | 結合 | 異常系 | — |
| REQ-AG-HTTP-004（R1-9 masking / A02）| PATCH レスポンス `persona.prompt_body` masked | TC-IT-AGH-020 | 結合 | セキュリティ | feature-spec.md §9 #16 |
| REQ-AG-HTTP-005（正常系）| `agent_router` DELETE + `AgentService.archive` + `SqliteAgentRepository.save` | TC-IT-AGH-021 | 結合 | 正常系 | feature-spec.md §9 #17 |
| REQ-AG-HTTP-005（Agent 不在）| `AgentService.archive` → `AgentNotFoundError` | TC-IT-AGH-022 | 結合 | 異常系 | — |
| REQ-AG-HTTP-005（冪等性: §確定G）| DELETE 2 回目 → 204（※設計不整合 BUG-AG-001 参照） | TC-IT-AGH-023 | 結合 | 正常系 | — |
| T3（不正 UUID）| FastAPI `UUID` 型強制 → 422 | TC-IT-AGH-024 | 結合 | 異常系 | — |
| T1（CSRF）| `Origin: http://evil.example.com` → POST → 403 | TC-IT-AGH-025 | 結合 | セキュリティ | — |
| T2（スタックトレース非露出）| generic_exception_handler → 500 body に stacktrace なし | TC-IT-AGH-026 | 結合 | セキュリティ | — |
| T5（SkillRef path traversal）| `path="../../../etc/passwd"` → 422 | TC-IT-AGH-027 | 結合 | セキュリティ | — |
| MSG-AG-HTTP-001 | `agent_not_found_handler` | TC-UT-AGH-001 | ユニット | 異常系 | — |
| MSG-AG-HTTP-002 | `agent_name_already_exists_handler` | TC-UT-AGH-002 | ユニット | 異常系 | — |
| MSG-AG-HTTP-003 | `agent_archived_handler` | TC-UT-AGH-003 | ユニット | 異常系 | — |
| MSG-AG-HTTP-004 | `agent_invariant_violation_handler`（§確定C 前処理ルール）| TC-UT-AGH-004 | ユニット | 異常系 | — |
| `AgentCreate` スキーマ（§確定A）| `schemas/agent.py` | TC-UT-AGH-005 | ユニット | 正常系 / 異常系 | — |
| `AgentUpdate` スキーマ（§確定A）| `schemas/agent.py` | TC-UT-AGH-006 | ユニット | 正常系 / 異常系 | — |
| `PersonaCreate` スキーマ（§確定A）| `schemas/agent.py` | TC-UT-AGH-007 | ユニット | 正常系 | — |
| `PersonaResponse` field_serializer（R1-9 / A02）| `PersonaResponse.prompt_body` masked シリアライズ | TC-UT-AGH-008 | ユニット | セキュリティ | feature-spec.md §9 #15 |
| 依存方向（interfaces → domain 直参照禁止）| `interfaces/http/` 配下全 `.py`（静的解析）| TC-UT-AGH-009 | ユニット（静的解析）| 異常系 | — |

**マトリクス充足の証拠**:
- REQ-AG-HTTP-001〜005 すべてに最低 1 件の正常系テストケース（TC-IT-AGH-001/007/011/014/021）
- REQ-AG-HTTP-001/002/003/004/005 の異常系（例外経路）が各々最低 1 件検証
- MSG-AG-HTTP-001〜004 の各 `code` / `message` 文字列が静的照合で確認
- 親受入基準 13〜17 のすべてが TC-IT-AGH-001/007/011/014/021 で対応（1:1）
- T1〜T5 脅威への対策が TC-IT-AGH-025/026/024/006+013+020/027 で有効性確認
- 孤児要件なし

## 設計上の発見事項

### ⚠️ BUG-AG-001: DELETE 冪等性の設計不整合（要リーダー判断）

| 文書 | 記述 |
|---|---|
| `detailed-design.md §確定G` | `archive` の冪等性: 2 回目の DELETE も **204** を返す |
| `basic-design.md §UX 設計` | `DELETE` を 2 回呼び出し（冪等）→ 2 回目も **204** |
| `system-test-design.md` TC-E2E-AG-004 ステップ 8 | DELETE（再試行）→ **404** |

`detailed-design.md` と `basic-design.md` は **2 回目 204** を凍結。`system-test-design.md` は **2 回目 404** を記述しており矛盾する。

**本 test-design.md の判定**: `detailed-design.md §確定G` に従い TC-IT-AGH-023 は **2 回目 204** で検証する。`system-test-design.md` の TC-E2E-AG-004 ステップ 8 は別 PR で修正が必要。リーダーに確認を要請。

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 |
|---|---|---|---|---|
| SQLite（テスト用 DB）| `get_session()` DI / lifespan 経由の Session / AgentRepository / EmpireRepository | `tests/fixtures/test_db.db`（tempdir）| `tests/factories/db.py`（http-api-foundation で定義済み）/ `tests/factories/agent.py`（**要新規作成** — TBD-1 参照）| 実 DB（pytest `tmp_path` 配下 tempfile）|
| FastAPI ASGI | HTTP リクエスト送信 | — | — | `httpx.AsyncClient(app=app, base_url="http://test")`（http-api-foundation 確定済み）|

**`tests/factories/agent.py` ステータス**: **要起票（TBD-1）**。`make_agent()` / `make_persona()` / `make_provider_config()` / `make_skill_ref()` を実装着手前に作成すること。空欄のまま IT 実装に進むことはできない。

## 結合テストケース

| テストID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|---|
| TC-IT-AGH-001 | `agent_router` → `AgentService.hire` → `SqliteAgentRepository.save` | 実 SQLite tempdb | Empire 存在・Agent 未存在 | `POST /api/empires/{empire_id}/agents` 正常 payload（name / persona / role / providers 1 件 is_default=True / skills=[]）| HTTP 201, `AgentResponse`（id / empire_id / name / persona / role / providers / skills / archived=false）|
| TC-IT-AGH-002 | `AgentService.hire` → `EmpireNotFoundError` → `empire_not_found_handler` | 実 SQLite tempdb | Empire 未存在 | `POST /api/empires/{ランダム UUID}/agents` 正常 payload | HTTP 404, `{"error": {"code": "not_found", "message": "Empire not found."}}` |
| TC-IT-AGH-003 | `AgentService.hire` → `AgentNameAlreadyExistsError` → `agent_name_already_exists_handler` | 実 SQLite tempdb | Empire 存在・同名 Agent 既存 | `POST /api/empires/{empire_id}/agents` 同名 payload | HTTP 409, `{"error": {"code": "conflict", "message": "Agent with this name already exists in the Empire."}}` |
| TC-IT-AGH-004 | `AgentService.hire` → `AgentInvariantViolation` → `agent_invariant_violation_handler` | 実 SQLite tempdb | Empire 存在 | `POST /api/empires/{empire_id}/agents` providers=[]（R1-2 違反）| HTTP 422, `{"error": {"code": "validation_error", <前処理済み本文>}}`、`[FAIL]` / `\nNext:` が body に含まれない |
| TC-IT-AGH-005 | `AgentService.hire` → `AgentInvariantViolation` | 実 SQLite tempdb | Empire 存在 | `POST /api/empires/{empire_id}/agents` providers に is_default=True が 2 件（R1-3 違反）| HTTP 422, `{"error": {"code": "validation_error", ...}}` |
| TC-IT-AGH-006 | POST レスポンス `persona.prompt_body` masking（R1-9 / T4 / A02）| 実 SQLite tempdb | Empire 存在 | `POST` payload の `persona.prompt_body` に raw token（例: `"ANTHROPIC_API_KEY=sk-ant-xxxx"`）| HTTP 201, レスポンスの `persona.prompt_body` に raw token が含まれない（`<REDACTED:*>` 形式）|
| TC-IT-AGH-007 | `agent_router` → `AgentService.find_by_empire` → `SqliteAgentRepository.find_all_by_empire` | 実 SQLite tempdb | Empire 存在・Agent 1 件存在 | `GET /api/empires/{empire_id}/agents` | HTTP 200, `{"items": [<AgentResponse>], "total": 1}` |
| TC-IT-AGH-008 | `AgentService.find_by_empire` → 空リスト | 実 SQLite tempdb | Empire 存在・Agent 0 件 | `GET /api/empires/{empire_id}/agents` | HTTP 200, `{"items": [], "total": 0}` |
| TC-IT-AGH-009 | `AgentService.find_by_empire` → `EmpireNotFoundError` → `empire_not_found_handler` | 実 SQLite tempdb | Empire 未存在 | `GET /api/empires/{ランダム UUID}/agents` | HTTP 404, `{"error": {"code": "not_found", "message": "Empire not found."}}` |
| TC-IT-AGH-010 | `AgentService.find_by_empire` → アーカイブ済み含む | 実 SQLite tempdb | Empire 存在・Agent 2 件（active 1 + archived 1）| `GET /api/empires/{empire_id}/agents` | HTTP 200, `{"total": 2}`（アーカイブ済みも含む — 設計 REQ-AG-HTTP-002 より）|
| TC-IT-AGH-011 | `agent_router` → `AgentService.find_by_id` → `SqliteAgentRepository.find_by_id` | 実 SQLite tempdb | Agent 存在 | `GET /api/agents/{agent_id}` | HTTP 200, `AgentResponse`（id / name 等が保存時と一致）|
| TC-IT-AGH-012 | `AgentService.find_by_id` → `AgentNotFoundError` → `agent_not_found_handler` | 実 SQLite tempdb | Agent 未存在 | `GET /api/agents/{ランダム UUID}` | HTTP 404, `{"error": {"code": "not_found", "message": "Agent not found."}}` |
| TC-IT-AGH-013 | GET レスポンス `persona.prompt_body` masking（R1-9 / T4 / A02）| 実 SQLite tempdb | prompt_body に raw token を含む Agent が永続化済み | `GET /api/agents/{agent_id}` | HTTP 200, `persona.prompt_body` が `<REDACTED:*>` 形式（raw token 不在）|
| TC-IT-AGH-014 | `agent_router` → `AgentService.update` → `SqliteAgentRepository.save` | 実 SQLite tempdb | Agent 存在（archived=false）| `PATCH /api/agents/{agent_id}` `{"name": "新名前"}` | HTTP 200, `AgentResponse`（name="新名前", その他フィールド変化なし）|
| TC-IT-AGH-015 | `AgentService.update` → providers 全置換 | 実 SQLite tempdb | Agent 存在（archived=false）| `PATCH /api/agents/{agent_id}` 新 providers list（全置換）| HTTP 200, `AgentResponse`（providers が新 list に差し替わる）|
| TC-IT-AGH-016 | `AgentService.update` → `AgentNotFoundError` → `agent_not_found_handler` | 実 SQLite tempdb | Agent 未存在 | `PATCH /api/agents/{ランダム UUID}` `{"name": "変更"}` | HTTP 404, `{"error": {"code": "not_found", "message": "Agent not found."}}` |
| TC-IT-AGH-017 | `AgentService.update` → `AgentArchivedError` → `agent_archived_handler` | 実 SQLite tempdb | Agent 存在（archived=true）| `PATCH /api/agents/{agent_id}` `{"name": "変更試み"}` | HTTP 409, `{"error": {"code": "conflict", "message": "Agent is archived and cannot be modified."}}` |
| TC-IT-AGH-018 | `AgentService.update` → `AgentNameAlreadyExistsError` → `agent_name_already_exists_handler` | 実 SQLite tempdb | Agent A 存在・Agent B（同 Empire）存在 | `PATCH /api/agents/{agent_A_id}` `{"name": "<agent_B の name>"}` | HTTP 409, `{"error": {"code": "conflict", "message": "Agent with this name already exists in the Empire."}}` |
| TC-IT-AGH-019 | `AgentService.update` → `AgentInvariantViolation` → `agent_invariant_violation_handler` | 実 SQLite tempdb | Agent 存在（archived=false）| `PATCH /api/agents/{agent_id}` providers に is_default=True が 2 件 | HTTP 422, `{"error": {"code": "validation_error", ...}}` |
| TC-IT-AGH-020 | PATCH レスポンス `persona.prompt_body` masking（R1-9 / T4 / A02）| 実 SQLite tempdb | Agent 存在（archived=false）| `PATCH /api/agents/{agent_id}` `{"persona": {"prompt_body": "GITHUB_PAT=ghp_xxxx"}}` | HTTP 200, `persona.prompt_body` に raw token が含まれない（`<REDACTED:*>` 形式）|
| TC-IT-AGH-021 | `agent_router` → `AgentService.archive` → `SqliteAgentRepository.save` | 実 SQLite tempdb | Agent 存在（archived=false）| `DELETE /api/agents/{agent_id}` | HTTP 204 No Content |
| TC-IT-AGH-022 | `AgentService.archive` → `AgentNotFoundError` → `agent_not_found_handler` | 実 SQLite tempdb | Agent 未存在 | `DELETE /api/agents/{ランダム UUID}` | HTTP 404, `{"error": {"code": "not_found", "message": "Agent not found."}}` |
| TC-IT-AGH-023 | DELETE 冪等性（§確定G — ⚠️ BUG-AG-001 確認後に更新要）| 実 SQLite tempdb | Agent 存在（archived=false）| `DELETE /api/agents/{agent_id}` を 2 回連続 | 1 回目 HTTP 204 / 2 回目 HTTP 204（§確定G 凍結値 — `system-test-design.md` の 404 記述と不整合、リーダー判断待ち）|
| TC-IT-AGH-024 | FastAPI `UUID` 型強制（T3）| — | — | `GET /api/agents/not-a-valid-uuid` 等、パスパラメータに不正 UUID 文字列 | HTTP 422 |
| TC-IT-AGH-025 | CSRF ミドルウェア（T1）| 実 SQLite tempdb | Empire 存在 | `POST /api/empires/{empire_id}/agents` に `Origin: http://evil.example.com` ヘッダ付与 | HTTP 403（http-api-foundation 確定D）|
| TC-IT-AGH-026 | generic_exception_handler（T2 スタックトレース非露出）| 実 SQLite tempdb | — | 内部エラーを誘発（例: リポジトリを意図的に壊す）| HTTP 500, レスポンス body に `"stacktrace"` / `"traceback"` / `"Traceback"` 等が含まれない（`{"error": {"code": "internal_error", ...}}` のみ）|
| TC-IT-AGH-027 | SkillRef path traversal 防御（T5）| 実 SQLite tempdb | Empire 存在 | `POST /api/empires/{empire_id}/agents` skills に `path="../../../etc/passwd"` を含む SkillRef | HTTP 422（domain H1〜H10 パストラバーサル防御 → `AgentInvariantViolation` → `agent_invariant_violation_handler`）|

## ユニットテストケース

| テストID | 対象 | 種別 | 入力（factory / 直接）| 期待結果 |
|---|---|---|---|---|
| TC-UT-AGH-001 | `agent_not_found_handler`（MSG-AG-HTTP-001）| 異常系 | `AgentNotFoundError(agent_id="test-id")` | HTTP 404, `{"error": {"code": "not_found", "message": "Agent not found."}}` |
| TC-UT-AGH-002 | `agent_name_already_exists_handler`（MSG-AG-HTTP-002）| 異常系 | `AgentNameAlreadyExistsError(empire_id="eid", name="n")` | HTTP 409, `{"error": {"code": "conflict", "message": "Agent with this name already exists in the Empire."}}` |
| TC-UT-AGH-003 | `agent_archived_handler`（MSG-AG-HTTP-003）| 異常系 | `AgentArchivedError(agent_id="test-id")` | HTTP 409, `{"error": {"code": "conflict", "message": "Agent is archived and cannot be modified."}}` |
| TC-UT-AGH-004 | `agent_invariant_violation_handler`（MSG-AG-HTTP-004 前処理ルール §確定C）| 異常系 | (a) `AgentInvariantViolation("[FAIL] providers must have exactly one default provider.\nNext: set is_default=True for exactly one provider.")` (b) `AgentInvariantViolation("[FAIL] Agent name は 1〜40 文字でなければなりません。")` | (a) HTTP 422, `message` が `"providers must have exactly one default provider."` — `[FAIL]` プレフィックスと `\nNext:.*` が除去されていること (b) HTTP 422, `message` に `[FAIL]` / `Next:` が含まれないこと |
| TC-UT-AGH-005 | `AgentCreate` スキーマ（§確定A）| 正常系 / 異常系 | (a) 有効 payload（name 40 文字以内 / persona / role / providers 1 件 is_default=True）(b) `name=""` (c) `name="x"*41` (d) `providers=[]`（`min_length=1` 違反）(e) 余分フィールド `extra="z"` | (a) バリデーション通過 (b) min_length 違反 `ValidationError` (c) max_length 違反 `ValidationError` (d) min_length 違反 `ValidationError` (e) extra 禁止 `ValidationError` |
| TC-UT-AGH-006 | `AgentUpdate` スキーマ（§確定A）| 正常系 / 異常系 | (a) 全フィールド None（no-op）(b) `name="更新名"` のみ (c) `providers=[valid_provider]` のみ (d) `name=""`（min_length 違反）| (a) バリデーション通過（no-op として有効）(b) 通過 (c) 通過 (d) min_length 違反 `ValidationError` |
| TC-UT-AGH-007 | `PersonaCreate` スキーマ（§確定A）| 正常系 | (a) `prompt_body=None` (b) `prompt_body="raw_token_value"` (c) `archetype=None` | (a) `None` のまま通過（domain に委譲、masking はレスポンス層で実施）(b) raw 値のまま通過 (c) `None` のまま通過 |
| TC-UT-AGH-008 | `PersonaResponse` field_serializer による `prompt_body` masking（R1-9 / T4 / A02）| セキュリティ | raw token 文字列（例: `"ANTHROPIC_API_KEY=sk-ant-xxxx"`）を持つ `Persona` オブジェクト → `PersonaResponse` でシリアライズ | シリアライズ後の `prompt_body` フィールドに raw token が含まれない（`<REDACTED:*>` 形式）|
| TC-UT-AGH-009 | 依存方向（静的解析）| 異常系 | `ast.parse()` で `interfaces/http/` 配下の全 `.py` を解析し、トップレベル `import` / `from ... import` を抽出 | `bakufu.domain` / `bakufu.infrastructure` への直接 import が存在しないこと（http-api-foundation TC-UT-HAF-010 と同一検証パターン）|

## カバレッジ基準

- REQ-AG-HTTP-001〜005 の各要件が **最低 1 件の正常系** テストケース（TC-IT-AGH-001/007/011/014/021）で検証されている
- REQ-AG-HTTP-001/002/003/004/005 の異常系（例外経路）が各々 **最低 1 件** 検証されている
- MSG-AG-HTTP-001〜004 の各 `code` / `message` 文字列が **静的文字列で照合** されている（`assert response.json()["error"]["code"] == "conflict"` 等）
- 親受入基準 13〜17（[`../feature-spec.md §9`](../feature-spec.md)）が TC-IT-AGH-001/007/011/014/021 で 1:1 に対応
- T1〜T5 脅威への対策が TC-IT-AGH-025/026/024/006+013+020/027 で有効性確認
- 行カバレッジ目標: **90% 以上**（Q-2 基準）

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全 7 ジョブ緑であること
- ローカル:
  ```sh
  just test-backend   # pytest 実行（--cov で coverage 確認）
  ```
- 手動確認（uvicorn 起動後）:
  ```sh
  # Empire 作成
  curl -X POST http://localhost:8000/api/empires \
    -H "Content-Type: application/json" \
    -d '{"name": "テスト幕府"}' | jq .
  # → 201 {"id": "<empire_id>", ...}

  # Agent 採用（prompt_body に raw token を含む）
  curl -X POST "http://localhost:8000/api/empires/<empire_id>/agents" \
    -H "Content-Type: application/json" \
    -d '{"name": "ダリオ", "persona": {"display_name": "ダリオ", "archetype": "CEO", "prompt_body": "ANTHROPIC_API_KEY=sk-ant-secret"}, "role": "DEVELOPER", "providers": [{"provider_kind": "CLAUDE_CODE", "model": "claude-sonnet-4-5", "is_default": true}], "skills": []}' | jq .
  # → 201 {"persona": {"prompt_body": "<REDACTED:ANTHROPIC_KEY>"}, ...}  ← raw token 非露出を確認
  ```

## テストディレクトリ構造

```
backend/tests/
├── factories/
│   └── agent.py                                 # 要新規作成（TBD-1）: make_agent / make_persona / make_provider_config / make_skill_ref
├── unit/
│   └── test_agent_http_api/
│       ├── __init__.py
│       └── test_handlers.py                     # TC-UT-AGH-001〜009
└── integration/
    └── test_agent_http_api/
        ├── __init__.py
        ├── conftest.py                           # AgTestCtx fixture / wiring（AgentService DI）
        ├── helpers.py                            # _create_empire / _create_agent_direct / _seed_agent_with_prompt_body 等
        ├── test_hire.py                          # TC-IT-AGH-001〜006
        ├── test_list.py                          # TC-IT-AGH-007〜010
        ├── test_get.py                           # TC-IT-AGH-011〜013
        ├── test_update.py                        # TC-IT-AGH-014〜020
        ├── test_archive.py                       # TC-IT-AGH-021〜023
        └── test_security.py                      # TC-IT-AGH-024〜027
```

## 未決課題・要起票 characterization task

| # | 内容 | 起票先 |
|---|---|---|
| TBD-1 | `tests/factories/agent.py` 新規作成（`make_agent` / `make_persona` / `make_provider_config` / `make_skill_ref`）。実装着手前に完了必須。空欄のまま IT 実装に進んだ場合レビューで却下する | 実装 PR 着手前 |
| TBD-2 | **BUG-AG-001**: `system-test-design.md` TC-E2E-AG-004 ステップ 8「2 回目 DELETE → 404」と `detailed-design.md §確定G`「2 回目 DELETE → 204」の設計不整合をリーダーに確認し、設計書 PR で修正すること | 設計書 PR |
| TBD-3 | `AgentRepository.find_all_by_empire`（前提条件 P-1）実装完了を TC-IT-AGH-007〜010 実行前に確認すること | 実装担当確認 |
| TBD-4 | `AgentNotFoundError` の `room_exceptions.py` → `agent_exceptions.py` 正式移転（前提条件 P-2）完了を本 IT 実行前に確認すること | 実装担当確認 |

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — 機能要件（REQ ID）
- [`detailed-design.md`](detailed-design.md) — MSG 確定文言 / スキーマ仕様 / §確定G 冪等性
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様（受入基準 §9 #13〜18）
- [`../system-test-design.md`](../system-test-design.md) — E2E テスト（TC-E2E-AG-004）
- [`../../http-api-foundation/http-api/test-design.md`](../../http-api-foundation/http-api/test-design.md) — 共通テストパターン参照（TC-UT-HAF-010 依存方向検証パターン等）
