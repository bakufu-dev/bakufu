# 主要ユースケース

プロジェクトの代表的な業務シナリオをシーケンス図で凍結する。本ファイルは [`../acceptance-tests/scenarios/`](../acceptance-tests/scenarios/) の根拠となる。

## ユースケース 1: \<業務シナリオ名\>

```mermaid
sequenceDiagram
    participant User as \<プライマリペルソナ\>
    participant UI as \<Frontend\>
    participant BE as \<Backend\>
    participant DB as \<永続化\>
    participant Ext as \<外部システム\>

    User->>UI: 1. \<業務操作\>
    UI->>BE: API call
    BE->>DB: \<永続化\>

    User->>UI: 2. \<次の操作\>
    UI->>BE: POST /api/...
    BE->>Ext: \<外部呼び出し\>
    Ext-->>BE: \<結果\>
    BE->>DB: \<状態更新\>
    BE-->>UI: \<レスポンス\>
    UI-->>User: \<UI 更新\>

    Note over BE,Ext: 3. \<業務上の重要分岐\>

    alt \<分岐 A\>
        BE->>DB: \<分岐 A の処理\>
    else \<分岐 B\>
        BE->>DB: \<分岐 B の処理\>
    end
```

## ユースケース 2: \<次の業務シナリオ\>

```mermaid
sequenceDiagram
    ...
```

## 関連

- [`system-context.md`](system-context.md) — システムコンテキスト図 + アクター
- [`functional-scope.md`](functional-scope.md) — 機能スコープ
- [`acceptance-criteria.md`](acceptance-criteria.md) — 受入基準
- [`../acceptance-tests/scenarios/`](../acceptance-tests/scenarios/) — 本ユースケースを E2E で検証する受入テスト
