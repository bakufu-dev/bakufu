# 主要ユースケース

bakufu の代表的な業務シナリオをシーケンス図で凍結する。本ファイルは [`../acceptance-tests/scenarios/`](../acceptance-tests/) の根拠となる（PR2 で受入テスト戦略を新設）。

## ユースケース 1: V モデル開発室で directive から Task 完走

```mermaid
sequenceDiagram
    participant CEO
    participant UI as bakufu Web UI
    participant BE as bakufu Backend
    participant DB as SQLite
    participant Agent as AI Agent (Claude Code CLI)
    participant DC as Discord
    participant GH as GitHub

    CEO->>UI: 1. Room 作成 + Agent 採用 + Workflow 選択
    UI->>BE: POST /api/rooms / agents / workflows
    BE->>DB: Aggregate 保存

    CEO->>UI: 2. $ directive 入力（"ToDo アプリを作って"）
    UI->>BE: POST /api/directives
    BE->>DB: Directive + Task 生成
    BE->>Agent: 1st Stage 担当 Agent に指示送信（CLI セッション開始）
    Agent-->>BE: deliverable（要求分析書）

    BE->>DB: Deliverable 保存、Stage が INTERNAL_REVIEW に遷移
    Note over BE,Agent: 内部レビュー（GateRole 並列、観点別独立判断）
    BE->>Agent: Reviewer / UX / Security 等の各 GateRole エージェントに同時指示
    Agent-->>BE: 各 GateRole から判定（APPROVED / REJECTED + コメント）
    alt 全 GateRole APPROVED
        BE->>DB: Stage が EXTERNAL_REVIEW に遷移
        BE->>DB: ExternalReviewGate 生成（status=PENDING）
        BE->>DC: 「外部レビュー依頼」通知
    else 1 人でも REJECTED
        BE->>DB: Stage が前段に差し戻し
        BE->>Agent: 該当 Stage 担当 Agent に再依頼（feedback 付与）
    end

    CEO->>UI: 3. 通知 → UI で deliverable 閲覧
    UI->>BE: GET /api/gates/{id}
    BE->>DB: Gate + Deliverable snapshot
    UI-->>CEO: deliverable 表示

    alt 承認
        CEO->>UI: 4a. 承認ボタン
        UI->>BE: POST /api/gates/{id}/approve
        BE->>DB: Gate.decision=APPROVED, Task.advance() で次 Stage へ
        BE->>Agent: 次 Stage 担当 Agent に指示
    else 差し戻し
        CEO->>UI: 4b. 差し戻し（コメント付き）
        UI->>BE: POST /api/gates/{id}/reject
        BE->>DB: Gate.decision=REJECTED, Task.advance(REJECTED) で前段 Stage へ
        BE->>Agent: 該当 Stage 担当 Agent に再依頼（feedback 付与）
    end

    Note over BE,GH: 5. 全 Stage 完了 → Task DONE
    BE->>GH: 成果物を git push（Empire ごとに別 repo）
    BE->>UI: WebSocket で Task DONE をブロードキャスト
    UI-->>CEO: ダッシュボード更新
```

## 関連

- [`system-context.md`](system-context.md) — システムコンテキスト図 + アクター
- [`functional-scope.md`](functional-scope.md) — 機能スコープ
- [`acceptance-criteria.md`](acceptance-criteria.md) — 受入基準
- [`../acceptance-tests/scenarios/`](../acceptance-tests/) — 本ユースケースを E2E で検証する受入テスト（PR2 で新設）
