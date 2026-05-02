# システムテスト戦略 — internal-review-gate

> 関連: feature-spec.md §9 受入基準 8〜10, 12（受入基準 1〜7, 11 は domain IT/UT — [`domain/test-design.md`](domain/test-design.md) が担当）
> 対象: UC-IRG-002〜006（InternalReviewGate ライフサイクル全体 E2E）
> M5-B 追加: TC-ST-IRG-005〜007（application / repository sub-feature E2E）

本ドキュメントは InternalReviewGate **業務概念全体** のシステムテスト戦略を凍結する。sub-feature（domain）の IT / UT はそれぞれの `test-design.md` が担当する。

## 観察主体

| ペルソナ | 観察対象 |
|---------|---------|
| 個人開発者 CEO（堀川さん想定）| Workflow 設計時の required_gate_roles 設定 / 最終的な Gate 状態の正確性 |
| GateRole エージェント（Reviewer / UX / Security 担当 Agent）| Verdict 提出後の Gate 状態遷移 / 差し戻しシグナルの確認 |

## 検証方法の定義

| 検証対象 | 検証手段 |
|---------|---------|
| UC-IRG-002〜005（Gate 生成・Verdict 提出・遷移）| InMemoryRepository + application 層直接呼び出し |
| UC-IRG-006（再起動跨ぎ保持）| 実 SQLite（`tempfile` による一時 DB）/ アプリ再起動シミュレーション |
| required_gate_roles 空集合（受入基準 #10）| InMemoryRepository + application 層 Gate 生成ロジック直接呼び出し |

## システムテストケース

```mermaid
sequenceDiagram
    participant App as application 層
    participant Gate as InternalReviewGate
    participant Repo as InMemoryRepository
    participant ExtGate as ExternalReviewGate（別 Aggregate）

    Note over App,ExtGate: TC-ST-IRG-001: 全 GateRole APPROVED → ExternalReviewGate 生成

    App->>Gate: create(task_id, stage_id, required_gate_roles={"reviewer","ux"})
    Gate-->>App: InternalReviewGate(PENDING)
    App->>Repo: save(gate)

    App->>Gate: submit_verdict(role="reviewer", APPROVED, comment="OK")
    Gate-->>App: InternalReviewGate(PENDING, verdicts=[1件])
    App->>Gate: submit_verdict(role="ux", APPROVED, comment="UI良好")
    Gate-->>App: InternalReviewGate(ALL_APPROVED, verdicts=[2件])
    App->>Repo: save(gate)

    App->>ExtGate: create(task_id, stage_id, ...)
    ExtGate-->>App: ExternalReviewGate(PENDING)
    Note over App,ExtGate: 受入基準 #8 達成
```

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 | 紐付く受入基準 |
|---------|---------|---------|---------|---------|------------|
| TC-ST-IRG-001 | GateRole エージェント / CEO | Stage 到達 → Gate 生成 → 全 GateRole APPROVED → ExternalReviewGate 生成 | 1) required_gate_roles={"reviewer","ux"} で Gate 生成（PENDING）→ 2) reviewer が APPROVED 提出（PENDING 継続）→ 3) ux が APPROVED 提出（ALL_APPROVED 遷移）→ 4) application 層が ExternalReviewGate を生成 | Gate が ALL_APPROVED、ExternalReviewGate が PENDING で生成される | #8 |
| TC-ST-IRG-002 | GateRole エージェント / CEO | REJECTED → Task 差し戻し → 再 Stage 実行 → 全 APPROVED | 1) Gate 生成（PENDING）→ 2) security が REJECTED 提出（REJECTED 遷移）→ 3) application 層が Task 差し戻しシグナルを検出 → 4) Agent が再作業 → 5) 新 Gate 生成（PENDING）→ 6) 全 GateRole APPROVED → ALL_APPROVED 遷移 | 旧 Gate は REJECTED として履歴保持、新 Gate が ALL_APPROVED へ遷移する | #9 |
| TC-ST-IRG-003 | application 層 | required_gate_roles 空集合の Stage では Gate が生成されない | 1) required_gate_roles=frozenset() の Stage 設定 → 2) application 層が Gate 生成ロジックを呼び出す | InternalReviewGate が生成されない（application 層が空集合チェックでスキップ）| #10 |
| TC-ST-IRG-004 | application 層 | Gate の状態が再起動後も保持される | 1) PENDING Gate を SQLite に保存 → 2) アプリ再起動シミュレーション（DB 再接続）→ 3) `find_by_id` で復元 → 4) 復元 Gate が元 Gate と構造的等価（id / task_id / stage_id / required_gate_roles / verdicts / gate_decision / created_at 全属性一致）| 再起動後も Gate の全属性が保持されている | #12 |

## シナリオフロー図（TC-ST-IRG-002: REJECTED → 差し戻しサイクル）

```mermaid
sequenceDiagram
    participant App as application 層
    participant Gate1 as InternalReviewGate(Gate_1)
    participant Gate2 as InternalReviewGate(Gate_2)
    participant Task as Task Aggregate

    Note over App,Task: TC-ST-IRG-002: REJECTED → Task 差し戻し → 再実行 → ALL_APPROVED

    App->>Gate1: create(required_gate_roles={"reviewer","security"})
    Gate1-->>App: Gate_1(PENDING)

    App->>Gate1: submit_verdict(role="security", REJECTED, "脆弱性検出")
    Gate1-->>App: Gate_1(REJECTED)

    App->>Task: rollback_to_previous_stage()
    Task-->>App: Task(前段 Stage に差し戻し)

    Note over App,Task: Agent が再作業 → Stage 完了

    App->>Gate2: create(required_gate_roles={"reviewer","security"})
    Gate2-->>App: Gate_2(PENDING)

    App->>Gate2: submit_verdict(role="reviewer", APPROVED, "問題なし")
    Gate2-->>App: Gate_2(PENDING, verdicts=[1件])
    App->>Gate2: submit_verdict(role="security", APPROVED, "脆弱性修正確認")
    Gate2-->>App: Gate_2(ALL_APPROVED)

    Note over App,Task: 受入基準 #9 達成
```

## M5-B 追加システムテストケース（application / repository sub-feature）

### TC-ST-IRG-005: 並列 GateRole LLM 実行 — asyncio.gather による独立並列審査

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 | 紐付く受入基準 |
|---------|---------|---------|---------|---------|------------|
| TC-ST-IRG-005 | GateRole エージェント（複数）| INTERNAL_REVIEW Stage に 3 GateRole が並列審査し、全 APPROVED → ExternalReviewGate 生成 | 1) mock LLMProviderPort（reviewer / ux / security 全 APPROVED 応答）を設定 → 2) `InternalReviewGateExecutor.execute(task_id, stage_id, {"reviewer","ux","security"})` を await → 3) LLMProviderPort.chat() 呼び出し確認 → 4) Gate 状態確認 | LLMProviderPort.chat() が 3 回呼ばれる（各呼び出しの session_id が互いに異なる UUID v4）/ Gate が ALL_APPROVED に遷移 / ExternalReviewGateService.create() が呼ばれる | #8（ALL_APPROVED 後の次フェーズ）|

### TC-ST-IRG-006: REJECTED → Task 差し戻し → DAG traversal による前段 WORK Stage 特定

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 | 紐付く受入基準 |
|---------|---------|---------|---------|---------|------------|
| TC-ST-IRG-006 | GateRole エージェント（security）| security が REJECTED → DAG traversal で前段 WORK Stage に差し戻し | 1) mock Workflow（DAG: WORK_A → INTERNAL_REVIEW_B）を設定 → 2) security GateRole が REJECTED を返す mock LLMProvider を設定 → 3) `executor.execute(task_id, INTERNAL_REVIEW_B.id, {"reviewer","security"})` を await → 4) TaskRepository の更新内容確認 | `task.rollback_to_stage(WORK_A.id)` が呼ばれる / Gate が REJECTED に遷移 / EventBus に InternalReviewGateDecidedEvent(decision=REJECTED) が発行される | #9（REJECTED 後の Task 差し戻し）|

### TC-ST-IRG-007: Gate の永続化 — Verdict comment の MaskedText マスキング end-to-end

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 | 紐付く受入基準 |
|---------|---------|---------|---------|---------|------------|
| TC-ST-IRG-007 | application 層 | LLM が comment に secret（webhook URL）を含んで返す → 永続化前にマスキングされる | 1) LLM 応答 comment に `"https://discord.com/api/webhooks/123/secret"` を含む mock を設定 → 2) `executor.execute()` → 3) `find_by_id()` で復元 → 4) 復元 Gate の verdicts[0].comment を確認 | DB 上の comment が `<REDACTED:DISCORD_WEBHOOK>` 形式 / 復元 Gate の comment が masked 文字列 / plain text の token が残っていない | #12（再起動跨ぎ保持）+ feature-spec.md §13 機密レベル「高」|

## カバレッジ基準

受入基準 #1〜#12 の全件が最低 1 件のテストケースで検証される:

| 受入基準 | 検証担当 | テストケース |
|---------|---------|-----------|
| #1（required_gate_roles 設定）| domain UT | TC-UT-IRG-001 |
| #2（Gate 生成・PENDING 初期状態）| domain UT | TC-UT-IRG-002 |
| #3（APPROVED Verdict 提出・記録）| domain UT | TC-UT-IRG-003 |
| #4（全 APPROVED → ALL_APPROVED）| domain UT | TC-UT-IRG-004 |
| #5（REJECTED → REJECTED 遷移）| domain UT | TC-UT-IRG-005 |
| #6（同一 GateRole 重複提出拒否）| domain UT | TC-UT-IRG-006 |
| #7（確定後 Verdict 拒否）| domain UT | TC-UT-IRG-007 |
| #8（ALL_APPROVED 後の次フェーズ）| **TC-ST-IRG-001** / **TC-ST-IRG-005**（M5-B: 並列実行を通じた ALL_APPROVED）| |
| #9（REJECTED 後の Task 差し戻し）| **TC-ST-IRG-002** / **TC-ST-IRG-006**（M5-B: DAG traversal 経由の差し戻し）| |
| #10（空集合 Gate 非生成）| **TC-ST-IRG-003** |  |
| #11（comment 文字数境界）| domain UT | TC-UT-IRG-008 |
| #12（再起動跨ぎ保持）| **TC-ST-IRG-004** / **TC-ST-IRG-007**（M5-B: masking 経由の永続化）| |
