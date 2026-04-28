# マイルストーン

プロジェクト MVP の開発マイルストーンと完了基準を凍結する。各 feature の業務仕様 / sub-feature 起票時に本書のマイルストーンに紐付ける。

## マイルストーン一覧

| マイルストーン | 完了基準 |
|---|---|
| **M1: \<最初のマイルストーン名\>** | \<例: domain/ の Aggregate が型検査 pass、ユニットテスト カバレッジ N% 以上\> |
| **M2: \<次のマイルストーン\>** | \<例: 永続化基盤完成、CRUD の結合テスト pass\> |
| **M3: \<HTTP API\>** | \<例: 全 Aggregate の CRUD が動く、OpenAPI で UI 開発開始可能\> |
| **M4: \<リアルタイム同期 / WebSocket\>** | \<例: Domain Event ブロードキャスト、UI でリアルタイム反映\> |
| **M5: \<外部連携 Adapter\>** | \<例: 外部 API / CLI で 1 つの業務単位を完走\> |
| **M6: \<人間チェックポイント UI\>** | \<例: 承認 / 差し戻し UI、通知\> |
| **M7: \<E2E\>** | \<例: 主要シナリオを最初から最後まで完走\> |
| **v0.1.0 リリース** | \<例: release/0.1.0 ブランチ、CHANGELOG 確定、main マージ + tag\> |

## 着手すべき最初の feature

[`../analysis/business-context.md`](../analysis/business-context.md) §関連プロダクトとの関係 / 想定ペルソナの優先度より、M1 の着手順:

1. `feature/<最優先 feature 1>`: \<理由\>
2. `feature/<次の feature 2>`: \<理由\>
3. `feature/<feature 3>`: \<理由\>

各 feature は **単一業務概念に閉じる粒度** で起票する（[`../features/`](../features/) 配下に Vモデル設計書セットを配置）。

## 関連

- [`functional-scope.md`](functional-scope.md) — 機能スコープ
- [`acceptance-criteria.md`](acceptance-criteria.md) — 受入基準
- [`../analysis/business-vision.md`](../analysis/business-vision.md) — MVP 達成後の展望
