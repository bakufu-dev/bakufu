# マイルストーン

bakufu MVP（v0.1.0）の開発マイルストーンと完了基準を凍結する。各 feature の業務仕様 / sub-feature 起票時に本書のマイルストーンに紐付ける。

## マイルストーン一覧

| マイルストーン | 完了基準 |
|----|----|
| **M1: ドメイン骨格** | domain/ の Aggregate が pyright pass、ユニットテスト 80% カバレッジ |
| **M2: SQLite 永続化** | Repository 実装、Alembic マイグレーション、CRUD の結合テスト |
| **M3: HTTP API** | FastAPI router で全 Aggregate の CRUD が動く、OpenAPI で UI 開発開始可能 |
| **M4: WebSocket** | Domain Event の WebSocket ブロードキャスト、UI でリアルタイム反映 |
| **M5: LLM Adapter** | Claude Code CLI で 1 Stage を完走（Agent が deliverable を返す） |
| **M6: ExternalReviewGate UI** | 承認 / 差し戻しの人間操作、Discord 通知 |
| **M7: V モデル E2E** | Workflow プリセット → directive → 全 Stage 完走 → DONE |
| **v0.1.0 リリース** | release/0.1.0 ブランチ、CHANGELOG 確定、main マージ + tag |

## 着手すべき最初の feature（M1）

ai-team 開発室の運用合意（[`../analysis/business-context.md`](../analysis/business-context.md) §bakufu と ai-team の関係）より、M1 の着手順:

1. `feature/empire-aggregate`: Empire Aggregate Root 実装
2. `feature/room-aggregate`: Room Aggregate
3. `feature/workflow-aggregate`: Workflow + Stage + Transition
4. `feature/agent-aggregate`: Agent Aggregate
5. `feature/task-aggregate`: Task Aggregate + 状態遷移
6. `feature/external-review-gate`: ExternalReviewGate Aggregate

各 feature は単一 Aggregate に閉じる粒度で起票する（[`../features/`](../features/) 配下に Vモデル設計書セットを配置）。

## 関連

- [`functional-scope.md`](functional-scope.md) — 機能スコープ
- [`acceptance-criteria.md`](acceptance-criteria.md) — 受入基準
- [`../analysis/business-vision.md`](../analysis/business-vision.md) — MVP 達成後の展望
