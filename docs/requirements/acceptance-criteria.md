# 受入基準

bakufu MVP（v0.1.0）完了の判定基準を凍結する。本書は **受入テストの真実源** であり、[`../acceptance-tests/scenarios/`](../acceptance-tests/) の各シナリオが本書の受入基準を 1:N で網羅する（PR2 で acceptance-tests を新設）。

## 受入基準（MVP 完了の判定）

1. UI から Empire / Room / Agent / Workflow を作成・編集・アーカイブできる
2. プリセットから V モデル開発室を 1 クリックで作成できる
3. CEO が `$` プレフィックスで directive を入力すると、対象 Room で Task が起票される
4. Task の current_stage が遷移すると、Agent（Claude Code CLI 経由）が deliverable を生成する
5. EXTERNAL_REVIEW Stage で UI で承認 / 差し戻し操作ができる（Discord 通知は Phase 2 — M6-A post-MVP 決定 [R133]。`notify_channels=[]` でも Gate は正常に生成・完了できることを MVP で確認する）
6. 差し戻すと Task が前段 Stage に戻り、複数ラウンドの Gate 履歴が保持される
7. すべての Stage が APPROVED で完了すると、Task は DONE になる
8. 再起動後も Empire / Room / Agent / Task / Gate の状態が SQLite から復元される
9. WebSocket で UI がリアルタイム更新される（手動リロード不要）
10. `just check-all` がローカル / CI 双方で緑になる
11. LLM Adapter が復旧不能エラー（`AuthExpired` 等）を返したとき Task が `BLOCKED` 状態に隔離され、`bakufu admin list-blocked` で発見でき、`bakufu admin retry-task <task_id>` で再開できる
12. Notifier 失敗（Discord 障害等）が発生しても Outbox が retry し、最大 5 回失敗で dead-letter 化、`bakufu admin list-dead-letters` で発見でき、`bakufu admin retry-event <event_id>` で再投入できる
13. すべての Admin CLI 操作が `audit_log` に記録され、DELETE は SQLite トリガで拒否される
14. 添付ファイルの filename パストラバーサル（`..%2F` 等）、MIME spoofing（`text/html` 偽装）、サイズ超過は受領時に拒否される
15. LLM subprocess の stdout / stderr に含まれる既知 secret（`sk-ant-api03-...` / `ghp_...` / 環境変数値）が DB 永続化時に伏字化される
16. 既定起動で外部 IP からの接続は不可（`127.0.0.1:8000` のみバインド）。`BAKUFU_TRUST_PROXY=true` 時のみ reverse proxy 経由を許可
17. Workflow に紐付く全 GateRole（reviewer / ux / security 等、Workflow 定義時に観点指定）から `APPROVED` を受けない限り、ExternalReviewGate が生成されず、人間レビュー UI に Gate が表示されない（内部レビュー全合格が外部レビューの前提）
18. 内部レビューで 1 人でも `REJECTED` を出すと、Task は前段 Stage に戻り、該当 Stage 担当 Agent が修正後再提出する経路が起動する（feedback コメント付き）

## 受入テスト紐付け（PR2 で確定）

各受入基準は [`../acceptance-tests/scenarios/`](../acceptance-tests/) の SC-MVP-NNN シナリオで観察される（PR2 で新設）。

| 受入基準 # | カバーするシナリオ ID |
|---|---|
| 1, 2, 3, 4, 5 (UI承認), 7, 9, 17 | SC-MVP-001（V モデル開発室で Task 完走）|
| 6, 18 | SC-MVP-002（差し戻しの複数ラウンド）|
| 8 | SC-MVP-003（再起動跨ぎでの全状態復元） |
| 10 | SC-MVP-008（`just check-all` 緑） |
| 11 | SC-MVP-004（BLOCKED Task の admin 救済） |
| 12 | SC-MVP-005（dead-letter event の admin 救済） |
| 13 | SC-MVP-007（Admin CLI の audit_log 記録） |
| 14, 15, 16 | SC-MVP-006（secret マスキング / TLS / 添付安全） |
| 17, 18 | SC-MVP-001（V モデル開発室で Task 完走、Step 3.5 内部レビューフェーズ） |

## 関連

- [`functional-scope.md`](functional-scope.md) — 機能スコープ
- [`milestones.md`](milestones.md) — マイルストーン M1〜M7
- [`../acceptance-tests/`](../acceptance-tests/) — 受入テスト戦略（PR2 で新設）
- [`../design/threat-model.md`](../design/threat-model.md) — 受入基準 #14, #15, #16 の根拠
