# 外部連携

プロジェクトが連携する外部システムと連携プロトコルを凍結する。各 feature の業務仕様（[`../features/<feature-name>/feature-spec.md`](../features/)）が本書を引用して連携先を共有する。

## Phase 1（MVP）

| 連携先 | 目的 | プロトコル | 認証 |
|---|---|---|---|
| \<外部システム A\> | \<連携目的\> | \<例: REST / WebSocket / gRPC / subprocess\> | \<認証方式\> |
| \<外部システム B\> | \<連携目的\> | \<プロトコル\> | \<認証方式\> |
| \<外部システム C\> | \<連携目的\> | \<プロトコル\> | \<認証方式\> |
| \<パッケージレジストリ\> | \<開発ツール配布\> | HTTPS + SHA256 検証 | 不要（公開 registry） |

## Phase 2 以降（拡張）

| 連携先 | 目的 |
|---|---|
| \<拡張連携先 A\> | \<将来の機能拡張\> |
| \<拡張連携先 B\> | \<将来の機能拡張\> |

## 関連

- [`system-context.md`](system-context.md) — システムコンテキスト図（連携の概観）
- [`non-functional.md`](non-functional.md) — 非機能要件（セキュリティ含む）
- [`../design/threat-model.md`](../design/threat-model.md) — 外部連携を含む脅威モデル
