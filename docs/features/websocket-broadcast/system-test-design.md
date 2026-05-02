# システムテスト設計書 — websocket-broadcast

> feature: `websocket-broadcast`
> 親業務仕様: [`feature-spec.md`](feature-spec.md)
> 担当: テスト担当（Issue #158 / #159 完了後に作成）

## 本書の役割

本書は **websocket-broadcast feature のシステムテスト戦略** を凍結する。[`feature-spec.md §9`](feature-spec.md) の受入基準（TC-ST-WSB-NNN）を E2E / システムテストケースとして展開する。

**本書はテスト担当が Issue #159（http-api sub-feature）完了後に作成する。現時点はプレースホルダー。**

## テストケース一覧

| TC ID | 検証内容 | 対応受入基準 | 優先度 |
|---|---|---|---|
| TC-ST-WSB-001 | `ws://localhost:8000/ws` への接続確立 | §9 #1 | 必須 |
| TC-ST-WSB-002 | Task 状態遷移後の `task.state_changed` イベント配信確認 | §9 #2 | 必須 |
| TC-ST-WSB-003 | ExternalReviewGate PENDING 時の `external_review_gate.state_changed` イベント配信確認 | §9 #3 | 必須 |
| TC-ST-WSB-004 | Agent ステータス変化後の `agent.status_changed` イベント配信確認 | §9 #4 | 必須 |
| TC-ST-WSB-005 | クライアント切断後、残存接続へのブロードキャスト継続確認 | §9 #5 | 必須 |
| TC-ST-WSB-006 | Domain Event 発行〜クライアント受信のレイテンシ測定（p95 2 秒以内） | §9 #6 | 必須 |

詳細なテストケース仕様は Issue #159 完了後に本ファイルを EDIT にて追記する。
