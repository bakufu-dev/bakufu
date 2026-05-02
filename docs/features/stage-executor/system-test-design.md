# システムテスト設計書

> feature: `stage-executor`
> 関連: [`feature-spec.md`](feature-spec.md) §9 受入基準

## 本書の役割

本書は **stage-executor 業務概念全体のシステムテスト戦略** を凍結する。sub-feature（application / worker / bootstrap）の境界を跨いで観察される業務ふるまいを、ブラックボックスで検証する。

各 sub-feature の `test-design.md` は IT / UT のみを担当する。**システムテストは本書だけが扱う**（`application/test-design.md` にシステムテストを書かない）。

## システムテスト スコープ

- WORK Stage 実行（Queue 投入 → LLM 呼び出し → deliverable 保存 → 次 Stage 進行）の End-to-End
- LLMProviderError 発生 → Task BLOCKED の End-to-End
- BLOCKED → retry → IN_PROGRESS + 再キューの End-to-End
- EXTERNAL_REVIEW Stage 遷移 → ExternalReviewGate 生成の End-to-End
- 並行数制御（BAKUFU_MAX_CONCURRENT_STAGES=1 でのシリアル実行）の End-to-End
- M5-B 完了後: INTERNAL_REVIEW Stage 委譲 → 全 APPROVED → 次 Stage 進行 の End-to-End（TC-ST-ME-002 は M5-B 実装後に実施）

## 観察主体

bakufu Backend プロセス内部（[`feature-spec.md §4 ペルソナ`](feature-spec.md)）。本テストでは pytest + asyncio + SQLite インメモリ DB + LLM mock adapter を用いて、Task が Stage を自動実行する業務シナリオを観察する。LLM 呼び出しは `FakeLLMProvider`（テスト専用 fake adapter）で代替し、実際の Claude Code CLI は起動しない。

## システムテストケース

| テストID | シナリオ | セットアップ | 期待結果（観察可能事象）| 紐付く受入基準 |
|---|---|---|---|---|
| TC-ST-ME-001 | WORK Stage 完走（単一 Stage Workflow）| Task を IN_PROGRESS にして WORK Stage を Queue に投入。FakeLLMProvider が deliverable を返す | Task.status = DONE、Task.deliverables に Stage の deliverable が保存されている | feature-spec.md §9 #1 |
| TC-ST-ME-002 | INTERNAL_REVIEW Stage 委譲 | Task を IN_PROGRESS にして INTERNAL_REVIEW Stage を Queue に投入（M5-B stub 使用）| InternalReviewGateExecutorPort.execute() が呼び出される | feature-spec.md §9 #2（M5-B 実装後）|
| TC-ST-ME-003 | EXTERNAL_REVIEW Stage 遷移 | Task を IN_PROGRESS にして EXTERNAL_REVIEW Stage を Queue に投入 | Task.status = AWAITING_EXTERNAL_REVIEW、ExternalReviewGate が生成されている | feature-spec.md §9 #3 |
| TC-ST-ME-004 | AuthExpired → BLOCKED | FakeLLMProvider が LLMProviderAuthExpiredError を送出するよう設定。WORK Stage を実行 | Task.status = BLOCKED、Task.last_error に masked エラー情報が保存されている | feature-spec.md §9 #4 |
| TC-ST-ME-005 | BLOCKED → retry → 再実行 | TC-ST-ME-004 の後継。StageExecutorService.retry_blocked_task() を呼び出す | Task.status = IN_PROGRESS（BLOCKED → IN_PROGRESS）、Queue に Stage が再投入されている | feature-spec.md §9 #5（M5-C 実装後）|
| TC-ST-ME-006 | シリアル実行（BAKUFU_MAX_CONCURRENT_STAGES=1）| 2 つの Task が同時に WORK Stage を Queue に投入。FakeLLMProvider は 1 回目の応答を遅延させる | 2 回目の Stage は 1 回目の完了後に開始される（実行オーバーラップがない）| feature-spec.md §9 #6 |

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | SQLite インメモリ DB（pytest fixture で起動・破棄）|
| domain 層 | 実 Aggregate（モックなし）|
| application 層 | 直接呼び出し（StageExecutorService / StageWorker を直接テスト）|
| LLM 外部呼び出し | `FakeLLMProvider`（LLMProviderPort を実装する fake adapter）。deliverable 内容・エラー種別を fixture で設定する |
| EventBus | `InMemoryEventBus`（既存実装）。publish されたイベント一覧を検証する |
| pid_registry | インメモリ DB の `bakufu_pid_registry` テーブルを使用。subprocess 実行は行わない（FakeLLMProvider のため）|

## カバレッジ基準

- 受入基準（[`feature-spec.md §9`](feature-spec.md)）が **システムテストで最低 1 件** 検証される（TC-ST-ME-NNN との対応表参照）
- StageKind 3 分岐（WORK / INTERNAL_REVIEW / EXTERNAL_REVIEW）それぞれに TC が存在する
- エラーパス（BLOCKED）と回復パス（retry）それぞれに TC が存在する

## テストディレクトリ構造

```
backend/tests/system/
└── test_stage_executor_lifecycle.py    # TC-ST-ME-001〜006
```

## 関連

- [`feature-spec.md §9`](feature-spec.md) — 受入基準（テストの真実源）
- [`application/test-design.md`](application/test-design.md) — application sub-feature の IT / UT（ヤン・ルカン担当）
- [`../../acceptance-tests/scenarios/`](../../acceptance-tests/scenarios/) — feature 跨ぎの受入シナリオ（M7 で実施）
