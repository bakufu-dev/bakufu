# システムテスト戦略 — external-review-gate

> 関連: feature-spec.md §9 受入基準 14 / 受入基準 3〜5（受入基準 15 は repository IT — [`repository/test-design.md`](repository/test-design.md) TC-IT-ERGR-020-masking-* が担当）
> 対象: UC-ERG-001〜005 / http-api 操作フロー（HTTP 黒箱）

本ドキュメントは ExternalReviewGate **業務概念全体** の E2E テスト戦略を凍結する。sub-feature（domain / repository / http-api）の IT / UT はそれぞれの `test-design.md` が担当する。

## E2E テストケース

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| TC-E2E-ERG-001 | CEO | Gate ラウンドトリップ（アプリ再起動跨ぎ）| 1) PENDING Gate を保存 → 2) アプリ再起動 → 3) `find_by_id` で復元 → 4) 復元 Gate が元 Gate と構造的等価（id / task_id / stage_id / reviewer_id / decision / feedback_text / deliverable_snapshot / audit_trail / created_at / decided_at 全属性一致）| 再起動後も Gate の全属性が保持されている |
| TC-E2E-ERG-002 | CEO | 判断済み Gate（approve）の再起動跨ぎ保持 | 1) PENDING Gate を保存 → 2) `approve(comment='OK', decided_at=now)` → `save` → 3) アプリ再起動 → 4) `find_by_id` で復元 | 復元 Gate の decision=APPROVED、decided_at 設定済み、audit_trail に APPROVED エントリ 1 件（閲覧記録と judgment 記録が全件保持）|
| TC-E2E-ERG-003 | CEO | 複数ラウンド Gate の履歴保持（差し戻し後の再起票） | 1) Gate_1 を REJECTED で保存 → 2) Gate_2（同 task_id）を PENDING で保存 → 3) アプリ再起動 → 4) `find_by_task_id(task_id)` | 戻り値リストに Gate_1（REJECTED）/ Gate_2（PENDING）の 2 件が時系列昇順（created_at ASC）で存在 |
| TC-E2E-ERG-HTTP-001 | CEO | approve フロー（HTTP 黒箱）| 1) PENDING Gate を DB に seed → 2) `POST /api/gates/{id}/approve` + `Authorization: Bearer <reviewer_id>` → 3) `GET /api/gates/{id}` | `POST` が HTTP 200 + `decision="APPROVED"`。`GET` が `decided_at` 設定済み + `audit_trail` に APPROVED エントリ 1 件 |
| TC-E2E-ERG-HTTP-002 | CEO | reject フロー（HTTP 黒箱）| 1) PENDING Gate を DB に seed → 2) `POST /api/gates/{id}/reject` + `Authorization: Bearer <reviewer_id>` + `{"feedback_text": "要修正"}` → 3) `GET /api/gates/{id}` | `POST` が HTTP 200 + `decision="REJECTED"`。`GET` が `feedback_text="要修正"` + `audit_trail` に REJECTED エントリ |
| TC-E2E-ERG-HTTP-003 | CEO | 二重決定拒否（HTTP 黒箱）| 1) AWAITING Gate（APPROVED 済み）を実 approved transition seed → 2) `POST /api/gates/{id}/approve`（同 reviewer）| HTTP 409 `conflict`（`decision_already_decided` 業務ルール R1-B 検証）|
| TC-E2E-ERG-HTTP-004 | CEO | PENDING Gate 一覧取得（HTTP 黒箱）| 1) `reviewer_id=R` の PENDING Gate 2 件 + 別 `reviewer_id` の Gate 1 件を seed → 2) `GET /api/gates?reviewer_id=R` | HTTP 200, `total=2`（reviewer フィルタ）|
