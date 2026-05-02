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
| UT（単体）| `_parse_verdict_decision()` / `_build_prompt()` / `_find_prev_work_stage_id()` 各ロジック | pytest + mock |

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
| 手順 | `create_gate(task_id, stage_id, frozenset())` を呼ぶ |
| 期待結果 | `None` が返る / InternalReviewGateRepository.save() が呼ばれない |
| 受入基準 | #10（空集合 Gate 非生成）|

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
| 手順 | mock AgentRepository が "agent_id" の role_profile に "security" を含まない設定 → `submit_verdict(gate_id, "security", agent_id=..., APPROVED, ...)` |
| 期待結果 | `UnauthorizedGateRoleError` が発生 / MSG-IRG-A002 のキーワードを含む |

### TC-IT-IRG-A006: `InternalReviewGateExecutor.execute()` — 並列 LLM 実行の動作確認

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-A002`（Executor 並列実行）|
| 手順 | 1) mock LLMProviderPort（reviewer: "APPROVED: OK", security: "APPROVED: 問題なし"）を設定 → 2) `executor.execute(task_id, stage_id, {"reviewer","security"})` を await |
| 期待結果 | LLMProviderPort.chat() が 2 回呼ばれる（並列）/ Gate が ALL_APPROVED に遷移 / session_id が 2 回とも異なる UUID v4 |

### TC-IT-IRG-A007: `execute()` — REJECTED 時の LLM エラー → 例外送出

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-A002`（エラーハンドリング）+ §確定 B（return_exceptions=True）|
| 手順 | mock LLMProvider が `LLMProviderTimeoutError` を送出するよう設定 → `executor.execute(...)` を await |
| 期待結果 | `LLMProviderTimeoutError` が再送出される（StageExecutorService が Task.block() に帰着させる）|

## ユニットテスト（UT）

### TC-UT-IRG-A101: `_parse_verdict_decision()` — APPROVED パターン

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 D（LLM 出力解析）|
| 手順 | "APPROVED: コードに問題なし" / "承認: LGTM" / "LGTM\n詳細..." を渡す |
| 期待結果 | 全て `VerdictDecision.APPROVED` |

### TC-UT-IRG-A102: `_parse_verdict_decision()` — REJECTED パターン（曖昧含む）

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 D + feature-spec.md R1-F（ambiguous → REJECTED）|
| 手順 | "REJECTED: バグあり" / "条件付き承認" / "" / "解析不能テキスト" を渡す |
| 期待結果 | 全て `VerdictDecision.REJECTED` |

### TC-UT-IRG-A103: `_build_prompt()` — 必須セクションの存在確認

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 E（プロンプトテンプレート構造）|
| 手順 | `_build_prompt(role="security", deliverable_summary="テスト成果物")` を呼ぶ |
| 期待結果 | プロンプトに "security" / "APPROVED" / "REJECTED" / "1行目" のキーワードが含まれる |

### TC-UT-IRG-A104: `_find_prev_work_stage_id()` — DAG traversal の正確性

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 G（DAG traversal）+ ジェンセン決定 ③|
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
| 手順 | 3 GateRole で execute() を呼び、mock LLMProvider への chat() 呼び出しの session_id を記録 |
| 期待結果 | 3 つの session_id が全て異なる UUID v4 / Stage ID と一致しない |

### TC-UT-IRG-A107: `execute()` — `return_exceptions=True` で一部エラーでも全 gather 完了

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 B（return_exceptions=True）|
| 手順 | reviewer: 正常 / ux: `LLMProviderTimeoutError` / security: 正常 の 3 GateRole で execute() |
| 期待結果 | `LLMProviderTimeoutError` が最終的に再送出される / reviewer と security の submit_verdict が呼ばれた（ux は未呼び出し）|

## カバレッジ基準

| 対象 | カバレッジ目標 |
|-----|------------|
| `InternalReviewService`（全 method + private）| line 90% 以上 |
| `InternalReviewGateExecutor`（execute + private）| line 90% 以上 |
| IT テスト全 7 件全緑 | — |
| UT テスト全 7 件全緑 | — |
| pyright strict pass | 型エラーゼロ |

## 実装前提条件

- repository sub-feature（`InternalReviewGateRepositoryPort` + `SqliteInternalReviewGateRepository`）が完成していること
- `InternalReviewGateExecutorPort`（M5-A で定義済み）が `application/ports/` に存在すること
- `LLMProviderPort`（M5-A で定義済み）+ `ExternalReviewGateService`（M3 で実装済み）が利用可能なこと

## テスト実行方法

```
# IT
pytest backend/tests/integration/test_internal_review_gate_application.py -v

# UT: InternalReviewService
pytest backend/tests/unit/test_internal_review_service.py -v

# UT: InternalReviewGateExecutor
pytest backend/tests/unit/test_internal_review_gate_executor.py -v

# カバレッジ
pytest --cov=bakufu.application.services.internal_review_service \
       --cov=bakufu.infrastructure.reviewers.internal_review_gate_executor \
       --cov-report=term-missing
```
