# システムテスト戦略 — external-review-gate

> 関連: feature-spec.md §9 受入基準 14（受入基準 15 は repository IT — [`repository/test-design.md`](repository/test-design.md) TC-IT-ERGR-020-masking-* が担当）
> 対象: UC-ERG-005（ExternalReviewGate の状態がアプリ再起動跨ぎで永続化）

本ドキュメントは ExternalReviewGate **業務概念全体** の E2E テスト戦略を凍結する。sub-feature（domain / repository）の IT / UT はそれぞれの `test-design.md` が担当する。

## E2E テストケース

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| TC-E2E-ERG-001 | CEO | Gate ラウンドトリップ（アプリ再起動跨ぎ）| 1) PENDING Gate を保存 → 2) アプリ再起動 → 3) `find_by_id` で復元 → 4) 復元 Gate が元 Gate と構造的等価（id / task_id / stage_id / reviewer_id / decision / feedback_text / deliverable_snapshot / audit_trail / created_at / decided_at 全属性一致）| 再起動後も Gate の全属性が保持されている |
| TC-E2E-ERG-002 | CEO | 判断済み Gate（approve）の再起動跨ぎ保持 | 1) PENDING Gate を保存 → 2) `approve(comment='OK', decided_at=now)` → `save` → 3) アプリ再起動 → 4) `find_by_id` で復元 | 復元 Gate の decision=APPROVED、decided_at 設定済み、audit_trail に APPROVED エントリ 1 件（閲覧記録と judgment 記録が全件保持）|
| TC-E2E-ERG-003 | CEO | 複数ラウンド Gate の履歴保持（差し戻し後の再起票） | 1) Gate_1 を REJECTED で保存 → 2) Gate_2（同 task_id）を PENDING で保存 → 3) アプリ再起動 → 4) `find_by_task_id(task_id)` | 戻り値リストに Gate_1（REJECTED）/ Gate_2（PENDING）の 2 件が時系列昇順（created_at ASC）で存在 |
