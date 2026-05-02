# テスト設計書 — internal-review-gate / application

> feature: `internal-review-gate` / sub-feature: `application`
> 親業務仕様: [`../feature-spec.md`](../feature-spec.md)
> 関連: [`basic-design.md`](basic-design.md) / [`detailed-design.md`](detailed-design.md)
> 担当 Issue: [#164 feat(M5-B): InternalReviewGate infrastructure実装](https://github.com/bakufu-dev/bakufu/issues/164)

## 本書の役割

本書は **internal-review-gate / application sub-feature の IT（結合テスト）と UT（単体テスト）** を凍結する。システムテスト（TC-ST-IRG-XXX）は [`../system-test-design.md`](../system-test-design.md) が担当する。

## テスト方針

| レベル | 対象 | 手段 |
|-------|------|------|
| IT（結合）| `InternalReviewService` + InMemoryRepository / `InternalReviewGateExecutor` + mock LLMProvider + InMemoryRepository | pytest AsyncMock + InMemory実装 |
| UT（単体）| `_execute_single_role()`（ツール呼び出し登録・再指示ロジック）/ `_build_prompt()` / `_find_prev_work_stage_id()` 各ロジック | pytest + AsyncMock |

## 結合テスト（IT）

テストファイル: `backend/tests/integration/test_internal_review_gate_application.py`

### TC-IT-IRG-A001: Gate 生成 → 全 GateRole APPROVED → ExternalReviewGate 生成

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-A001`（create_gate / submit_verdict）+ `REQ-IRG-A003`（ALL_APPROVED 後処理）|
| 手順 | 1) `InternalReviewService.create_gate(task_id, stage_id, {"reviewer","ux"})` → 2) mock AgentRepository で GateRole 権限認可 → 3) `submit_verdict(gate_id, "reviewer", APPROVED, ...)` → 4) `submit_verdict(gate_id, "ux", APPROVED, ...)` → 5) ExternalReviewGateService への委譲確認 |
| 期待結果 | Gate が ALL_APPROVED に遷移 / mock ExternalReviewGateService.create() が 1 回呼ばれる / EventBus に InternalReviewGateDecidedEvent が発行される |
| 受入基準 | #8（ALL_APPROVED 後の次フェーズ）|

### TC-IT-IRG-A002: REJECTED → Task 差し戻し → 前段 WORK Stage ID の正確性

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-A004`（DAG traversal）+ `REQ-IRG-A003`（REJECTED 後処理）|
| 手順 | 1) mock Workflow（stages: [WORK_A → INTERNAL_REVIEW_B]）を設定 → 2) Gate 生成 → 3) `submit_verdict(..., "security", REJECTED, ...)` → 4) TaskRepository への rollback_to_stage 呼び出し確認 |
| 期待結果 | `task.rollback_to_stage(stage_id=WORK_A.id)` が呼ばれる / Gate が REJECTED に遷移 / EventBus に InternalReviewGateDecidedEvent(decision=REJECTED) が発行される |
| 受入基準 | #9（REJECTED 後の Task 差し戻し）|

### TC-IT-IRG-A003: required_gate_roles が空集合 → Gate 非生成

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-A001`（空集合チェック）|
| 手順 | 1) `create_gate(task_id, stage_id, frozenset())` を呼ぶ → 2) `gate_repo.find_by_task_and_stage(task_id, stage_id)` で永続化有無を確認 |
| 期待結果 | `None` が返る / `find_by_task_and_stage` も `None` を返す（Gate が永続化されていない）|
| 受入基準 | #10（空集合 Gate 非生成）|
| 注記 | IT では「save() が呼ばれない」という内部呼び出し確認（whitebox）は行わない。`find_by_task_and_stage` の戻り値 None で永続化されていないことを振る舞いベースで確認する |

### TC-IT-IRG-A004: `create_gate()` のべき等性 — 既存 PENDING Gate の重複生成防止

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-A001` + §確定 F（べき等性）|
| 手順 | 1) `create_gate(task_id, stage_id, {"reviewer"})` で Gate 生成 → 2) 同一引数で再度 `create_gate()` を呼ぶ |
| 期待結果 | 同一 Gate が返る（id が一致）/ Repository.save() が 2 回目以降呼ばれない |

### TC-IT-IRG-A005: GateRole 権限なし → 認可エラー

| 項目 | 内容 |
|-----|------|
| 対象 | セキュリティ T1（GateRole 詐称防止）|
| 手順 | Gate を `required_gate_roles={"security"}` で生成 → `submit_verdict(gate_id, "security", agent_id=..., APPROVED, ...)` を呼ぶが、当該 `agent_id` は `gate.required_gate_roles` に存在しない role で提出 |
| 期待結果 | `UnauthorizedGateRoleError` が発生 / MSG-IRG-A002 のキーワードを含む |

### TC-IT-IRG-A006: `InternalReviewGateExecutor.execute()` — 並列 LLM 実行の動作確認

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-A002`（Executor 並列実行）+ §確定 D（ツール呼び出し登録方式）|
| 手順 | 1) mock LLMProviderPort の `chat_with_tools()` が各 role に対して `submit_verdict(decision="APPROVED", reason="OK")` ツール呼び出しを含む応答を返すよう設定 → 2) `executor.execute(task_id, stage_id, {"reviewer","security"})` を await |
| 期待結果 | `LLMProviderPort.chat_with_tools()` が 2 回呼ばれる（並列）/ Gate が ALL_APPROVED に遷移 |
| 注記 | 「session_id が 2 回とも異なる UUID v4」の確認は内部実装詳細（whitebox）のため IT スコープ外。TC-UT-IRG-A106 に委ねる |

### TC-IT-IRG-A007: `execute()` — LLM エラー → 例外送出

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-A002`（エラーハンドリング）+ §確定 B（return_exceptions=True）|
| 手順 | mock LLMProvider の `chat_with_tools()` が `LLMProviderTimeoutError` を送出するよう設定 → `executor.execute(...)` を await |
| 期待結果 | `LLMProviderTimeoutError` が再送出される（StageExecutorService が Task.block() に帰着させる）|

### TC-IT-IRG-A008: `execute()` — 初回ツール未呼び出し → 再指示後成功 → Gate 決定

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 D（再指示ロジック・最大 2 回リトライ）|
| 手順 | 1) mock LLMProvider の `chat_with_tools()` を "1 回目: ツール呼び出しなし（テキスト応答のみ）、2 回目: `submit_verdict(decision="APPROVED", reason="OK")` ツール呼び出し" を返すよう設定 → 2) `executor.execute(task_id, stage_id, {"reviewer"})` を await |
| 期待結果 | `chat_with_tools()` が 2 回呼ばれる / 2 回目でツール呼び出しが検出され `submit_verdict()` が 1 回呼ばれる / Gate が ALL_APPROVED に遷移する |
| 種別 | 正常系（再指示経路）|

### TC-IT-IRG-A009: `execute()` — 3 回全てツール未呼び出し → REJECTED 強制登録

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 D（3 回全て未登録時の処理：REJECTED 強制 + audit_log 記録）+ feature-spec.md R1-F（ambiguous → REJECTED）|
| 手順 | 1) mock LLMProvider の `chat_with_tools()` が 3 回全てツール呼び出しを含まないテキスト応答を返すよう設定 → 2) `executor.execute(task_id, stage_id, {"reviewer"})` を await |
| 期待結果 | `chat_with_tools()` が 3 回呼ばれる（初回 + 再指示 2 回）/ `InternalReviewService.submit_verdict()` が `decision=REJECTED`、`comment` に "[SYSTEM]" を含む内容で 1 回呼ばれる / Gate が REJECTED に遷移する / audit_log に `event="tool_not_called_all_retries"` が記録される |
| 種別 | 異常系（ツール未呼び出し全試行）|

## ユニットテスト（UT）

### TC-UT-IRG-A101: `_execute_single_role()` — 初回ツール呼び出し成功 → APPROVED

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 D（ツール呼び出し登録方式 ステップ 1→2→3a）|
| 手順 | mock `LLMProviderPort.chat_with_tools()` が `submit_verdict(decision="APPROVED", reason="コードに問題なし")` ツール呼び出しを返すよう設定 → `_execute_single_role(gate_id, "reviewer", task_id, stage_id)` を await |
| 期待結果 | `chat_with_tools()` が 1 回呼ばれる / `InternalReviewService.submit_verdict()` が `decision=APPROVED` で 1 回呼ばれる / リトライなし（`MAX_TOOL_RETRIES` 消費なし）|
| 種別 | 正常系 |

### TC-UT-IRG-A102: `_execute_single_role()` — 初回ツール呼び出し成功 → REJECTED

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 D（ツール呼び出し登録方式 ステップ 1→2→3a）|
| 手順 | mock `chat_with_tools()` が `submit_verdict(decision="REJECTED", reason="SQLインジェクション脆弱性を発見")` ツール呼び出しを返すよう設定 → `_execute_single_role(gate_id, "security", task_id, stage_id)` を await |
| 期待結果 | `chat_with_tools()` が 1 回呼ばれる / `InternalReviewService.submit_verdict()` が `decision=REJECTED` で 1 回呼ばれる / リトライなし |
| 種別 | 正常系 |

### TC-UT-IRG-A103: `_build_prompt()` — 必須セクションの存在確認

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 E（プロンプトテンプレート構造）|
| 手順 | `_build_prompt(role="security", deliverable_summary="テスト成果物")` を呼ぶ |
| 期待結果 | プロンプトに "security" / "submit_verdict" / "APPROVED" / "REJECTED" / "必ず" のキーワードが含まれる。旧来の "1行目" という文言が含まれない |
| 種別 | 正常系 |

### TC-UT-IRG-A104: `_find_prev_work_stage_id()` — DAG traversal の正確性

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 G（DAG traversal）|
| 手順 | mock Workflow（transitions: [WORK_A → INTERNAL_REVIEW_B]）を設定 → `_find_prev_work_stage_id(task_id, INTERNAL_REVIEW_B.id)` |
| 期待結果 | `WORK_A.id` が返る |

### TC-UT-IRG-A105: `_find_prev_work_stage_id()` — 前段 WORK Stage なし → IllegalWorkflowStructureError

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 G（Fail Fast）|
| 手順 | mock Workflow（transitions: [WORK_A]、INTERNAL_REVIEW Stage なし）で INTERNAL_REVIEW_B の前段を検索 |
| 期待結果 | `IllegalWorkflowStructureError` が発生 / MSG-IRG-A003 のキーワードを含む |

### TC-UT-IRG-A106: `execute()` — 各 GateRole の session_id が独立した UUID v4

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 A（session_id 戦略）|
| 手順 | 3 GateRole で execute() を呼び、mock LLMProvider への `chat_with_tools()` 呼び出しで渡された session_id を記録（各 role は初回でツール呼び出しに成功する mock 設定）|
| 期待結果 | 3 つの session_id が全て異なる UUID v4 / Stage ID と一致しない |

### TC-UT-IRG-A107: `execute()` — `return_exceptions=True` で一部エラーでも全 gather 完了

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 B（return_exceptions=True）|
| 手順 | reviewer: `chat_with_tools()` が `submit_verdict(APPROVED)` ツール呼び出しを返す / ux: `chat_with_tools()` が `LLMProviderTimeoutError` を送出 / security: `chat_with_tools()` が `submit_verdict(APPROVED)` ツール呼び出しを返す — 3 GateRole で execute() を await |
| 期待結果 | `LLMProviderTimeoutError` が最終的に再送出される / reviewer と security の `submit_verdict` が呼ばれた（ux は未呼び出し）|

### TC-UT-IRG-A108: `_execute_single_role()` — 初回ツール未呼び出し → 再指示 1 回目プロンプト注入確認

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 D（再指示プロンプト注入内容・試行 2 回目）|
| 手順 | 1 回目の `chat_with_tools()` がツール呼び出しを含まないテキスト応答（例: "コードを確認しました。問題はありません。"）を返す mock を設定、2 回目は `submit_verdict(APPROVED)` ツール呼び出しを返す設定 → `_execute_single_role()` を await → 2 回目の `chat_with_tools()` に渡されたプロンプトを検査 |
| 期待結果 | 2 回目のプロンプトに「前回の応答で判定ツールの呼び出しが確認できませんでした」の文言が含まれる / `{tool_not_called}` 箇所に「ツールを呼び出さずテキストのみで応答しました」（固定文言）が注入されている / `{prev_response_summary}` 箇所に 1 回目応答テキストの先頭 200 文字が注入されている / "これが最終機会" は含まれない（2 回目のため）|
| 種別 | 境界値（再指示 1 回目）|

### TC-UT-IRG-A109: `_execute_single_role()` — 再指示 2 回目（最終機会）プロンプト注入確認

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 D（再指示プロンプト注入内容・試行 3 回目）|
| 手順 | 1・2 回目の `chat_with_tools()` がツール呼び出しなしのテキスト応答、3 回目が `submit_verdict(APPROVED)` ツール呼び出しを返す mock を設定 → `_execute_single_role()` を await → 3 回目の `chat_with_tools()` に渡されたプロンプトを検査 |
| 期待結果 | 3 回目のプロンプトに「**これが最終機会です。**」の文言が含まれる / REJECTED が自動登録される旨の予告が含まれる / `{prev_response_summary}` に 2 回目応答先頭 200 文字が注入されている / `chat_with_tools()` が計 3 回呼ばれる |
| 種別 | 境界値（再指示 2 回目・最終機会）|

### TC-UT-IRG-A110: `_execute_single_role()` — 3 回全てツール未呼び出し → REJECTED 強制登録 + audit_log 記録

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 D（3 回全て未登録時の処理）+ §確定 J（audit_log 記録）+ feature-spec.md R1-F（ambiguous → REJECTED）|
| 手順 | mock `chat_with_tools()` を 3 回全てツール呼び出しなし（テキスト応答のみ）で設定 → `_execute_single_role()` を await |
| 期待結果 | `chat_with_tools()` が計 3 回呼ばれる（初回 + 再指示 2 回）/ `InternalReviewService.submit_verdict()` が `decision=REJECTED`、`comment` に "[SYSTEM] 全試行でツール未呼び出し" を含む内容で 1 回呼ばれる / mock audit_log に `{event="tool_not_called_all_retries", retry_count=3}` が記録される |
| 種別 | 異常系（ツール未呼び出し上限超過）|

### TC-UT-IRG-A111: `_execute_single_role()` — prev_response_summary は 200 文字でトランケートされる（T3 対策）

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 D（注入変数 `{prev_response_summary}` の 200 文字上限・T3 raw LLM ログ禁止制約）|
| 手順 | 1 回目の `chat_with_tools()` が 500 文字のテキスト応答を返す mock を設定（2 回目は `submit_verdict(APPROVED)` を返す）→ `_execute_single_role()` を await → 2 回目プロンプトに注入された `prev_response_summary` の文字数を確認 |
| 期待結果 | 注入された `prev_response_summary` が 200 文字以下にトランケートされている / ログに raw LLM 出力全体（500 文字）が含まれていない（`prev_response_length` の整数値のみ許可）|
| 種別 | 境界値（T3 制約）|

## 外部I/O依存マップ

| 外部I/O | 種別 | テストレベル | raw fixture | factory | characterization 状態 |
|---------|------|------------|------------|---------|----------------------|
| `LLMProviderPort`（`chat_with_tools()` LLM 呼び出し）| 外部 API | IT/UT | — | `tests/factories/stub_llm_provider.py`（既存 `make_stub_llm_provider` を `chat_with_tools` 対応に拡張が必要）| 充足（M5-A で characterization 済み）/ **要拡張**: `chat_with_tools()` メソッドのツール呼び出し応答形式を M5-B で追加 |
| `InternalReviewGateRepositoryPort`（Gate 永続化）| 内部 Port | IT | — | InMemory 実装または `tests/factories/internal_review_gate.py`（新規作成必要）| 要起票: InMemory Repository 実装が未存在 |
| `ExternalReviewGateService`（ALL_APPROVED 後の委譲）| 内部サービス | IT | — | mock（`AsyncMock`）または InMemory 実装 | 要起票: M3 既存サービスの mock 方針を `conftest.py` で確立 |
| `TaskRepository`（Task 差し戻し保存）| 内部 Port | IT | — | InMemory 実装または `AsyncMock` | 既存 `tests/factories/task.py` で Task 生成可能 |
| `WorkflowRepository`（DAG traversal）| 内部 Port | IT | — | `tests/factories/workflow.py`（既存: `make_workflow`, `make_transition`）| 充足 |
| `AgentRepository`（GateRole 権限認可）| 内部 Port | IT | — | `tests/factories/agent.py`（既存: `make_agent`）| 充足 |
| `EventBusPort`（Gate 状態変化 Event 発行）| 内部 Port | IT | — | `InMemoryEventBus`（既存）| 充足（M5-A で使用済み）|
| `audit_log`（Gate 決定時記録・OWASP A09）| 内部 Port | IT/UT | — | mock（`AsyncMock`）または InMemory 実装 | 要起票: audit_log Port の mock 方針を確立（§確定 J・TC-IT-IRG-A009・TC-UT-IRG-A110 で使用）|

**モック方針**:
- IT（結合テスト）: LLMProviderPort は `make_stub_llm_provider()` の `chat_with_tools()` 対応版でモック。DB は InMemory 実装を使用（外部 SQLite 接続不要）。リトライテスト（TC-IT-IRG-A008・A009）は `chat_with_tools()` の呼び出し回数に応じて返却値を切り替える `side_effect` 方式で設定する
- UT（単体テスト）: 全外部依存を `AsyncMock` でモック。`chat_with_tools()` は `AsyncMock(side_effect=[...])` でツール呼び出しあり/なし応答を試行ごとに制御する
- `ExternalReviewGateService` は IT では `AsyncMock` でモック（外部サービスの副作用を分離）
- assumed mock（根拠なき返却値リテラル）は禁止。`chat_with_tools()` のツール呼び出し応答形式は M5-A characterization fixture の `LLMToolCallResponse` 型に準拠すること

## カバレッジ基準

| 対象 | カバレッジ目標 |
|-----|------------|
| `InternalReviewService`（全 method + private）| line 90% 以上 |
| `InternalReviewGateExecutor`（execute + private）| line 90% 以上 |
| IT テスト全 9 件全緑（TC-IT-IRG-A001〜A009）| — |
| UT テスト全 11 件全緑（TC-UT-IRG-A101〜A111）| — |
| pyright strict pass | 型エラーゼロ |

## 実装前提条件

- repository sub-feature（`InternalReviewGateRepositoryPort` + `SqliteInternalReviewGateRepository`）が完成していること
- `InternalReviewGateExecutorPort`（M5-A で定義済み）が `application/ports/` に存在すること
- `LLMProviderPort.chat_with_tools(prompt, tools, session_id)` が M5-B で追加されていること（M5-A の `chat()` 変更なし）
- `ExternalReviewGateService`（M3 で実装済み）が利用可能なこと
- `make_stub_llm_provider()` が `chat_with_tools()` メソッドに対応する形に拡張されていること（既存 `chat()` 用 fixture の影響なし）

## テスト実行方法

```
# IT（結合テスト）
pytest backend/tests/integration/test_internal_review_gate_application.py -v

# UT: InternalReviewService
pytest backend/tests/unit/test_internal_review_service.py -v

# UT: InternalReviewGateExecutor（ツール呼び出し・再指示ロジック含む）
pytest backend/tests/unit/test_internal_review_gate_executor.py -v

# カバレッジ
pytest --cov=bakufu.application.services.internal_review_service \
       --cov=bakufu.infrastructure.reviewers.internal_review_gate_executor \
       --cov-report=term-missing
```
