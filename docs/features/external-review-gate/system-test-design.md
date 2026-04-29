# システムテスト戦略 — external-review-gate

> 関連: feature-spec.md §9 受入基準 14（受入基準 15 は repository IT — [`repository/test-design.md`](repository/test-design.md) TC-IT-ERGR-020-masking-* が担当）
> 対象: UC-ERG-005（ExternalReviewGate の状態がアプリ再起動跨ぎで永続化）

本ドキュメントは ExternalReviewGate **業務概念全体** の E2E テスト戦略を凍結する。CEO が操作できる公開 HTTP API だけを呼び、レスポンスとして観測できる一覧・詳細・判断結果・履歴で判定する。公開 API 以外の内部呼び出し、永続化ストアの直接参照、テスト用裏口は使わない。sub-feature（domain / repository / http-api）の IT / UT はそれぞれの `test-design.md` が担当する。

## E2E テストケース

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| TC-E2E-ERG-001 | CEO | Gate ラウンドトリップ（アプリ再起動跨ぎ）| 1) CEO が `GET /api/gates?decision=PENDING` で対象 Gate を確認 → 2) `GET /api/gates/{id}` で詳細を開き、表示された id / task_id / stage_id / reviewer_id / decision / feedback_text / deliverable_snapshot / audit_trail / created_at / decided_at を証跡に記録 → 3) アプリを再起動 → 4) CEO が同じ Bearer token で `GET /api/gates/{id}` を再実行 | 再起動後の HTTP レスポンスで、再起動前に CEO が観測した Gate の業務属性が維持される。詳細再取得により追加される VIEWED audit は追記として観測され、既存 audit は欠落・改変されない |
| TC-E2E-ERG-002 | CEO | 判断済み Gate（approve）の再起動跨ぎ保持 | 1) CEO が `GET /api/gates?decision=PENDING` で対象 Gate を選ぶ → 2) `POST /api/gates/{id}/approve` に comment を送信 → 3) レスポンスで APPROVED / decided_at / APPROVED audit を観測 → 4) アプリを再起動 → 5) `GET /api/gates/{id}` と `GET /api/tasks/{task_id}/gates` を実行 | 再起動後も detail と task 履歴の両方で decision=APPROVED、decided_at 設定済み、CEO の comment と APPROVED audit が観測できる。対象 Gate は PENDING 一覧には戻らない |
| TC-E2E-ERG-003 | CEO | 複数ラウンド Gate の履歴保持（差し戻し後の再起票） | 1) CEO が対象 task の PENDING Gate を `GET /api/tasks/{task_id}/gates` で確認 → 2) `POST /api/gates/{id}/reject` で差し戻す → 3) 通常ワークフローが同一 task の新しい PENDING Gate を生成した後、アプリを再起動 → 4) CEO が `GET /api/tasks/{task_id}/gates` を実行 | HTTP 履歴に旧 Gate（REJECTED）と新 Gate（PENDING）の 2 件が作成順で観測できる。旧 Gate の feedback / audit は保持され、新 Gate は別 id として PENDING 一覧にも出る |
