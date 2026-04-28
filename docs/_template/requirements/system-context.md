# システムコンテキスト

システムコンテキスト図とアクター一覧を凍結する。要件定義工程の起点。各 feature の業務仕様（[`../features/<feature-name>/feature-spec.md`](../features/)）が本書を引用してシステム境界を共有する。

## システムコンテキスト図

```mermaid
flowchart TB
    User["\<プライマリペルソナ\>"]
    External["\<セカンダリ / 外部アクター\>"]

    subgraph Host["\<システム配置単位\>"]
        Frontend["\<Frontend\>"]
        Backend["\<Backend\>"]
        DB[("\<永続化先\>")]
    end

    subgraph ExternalSystems["外部システム"]
        ExtA[\<外部システム A\>]
        ExtB[\<外部システム B\>]
    end

    User -- HTTPS --> Frontend
    Frontend --> Backend
    Backend <--> DB
    Backend -- \<プロトコル\> --> ExtA
    Backend -- \<プロトコル\> --> ExtB
    ExtA -- 通知 --> External
```

## アクター

| アクター | 役割 | 期待 |
|---|---|---|
| \<プライマリペルソナ\> | \<主要操作者\> | \<UI / API 経由で...できる\> |
| \<セカンダリペルソナ\> | \<副次操作者\> | \<承認 / 監査 / レビュー 等\> |
| \<外部システム A\> | \<連携目的\> | \<プロトコル A 経由で呼び出される\> |
| \<外部システム B\> | \<連携目的\> | \<プロトコル B 経由で連携\> |

## 関連

- [`use-cases.md`](use-cases.md) — 主要ユースケース（シーケンス図）
- [`functional-scope.md`](functional-scope.md) — 機能スコープ
- [`../analysis/personas.md`](../analysis/personas.md) — ペルソナ定義（業務観点）
- [`../design/architecture.md`](../design/architecture.md) — 技術観点での全体構造（粒度が異なる）
