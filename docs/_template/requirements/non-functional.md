# 非機能要件

プロジェクト MVP の非機能要件を凍結する。各 feature の業務仕様（[`../features/<feature-name>/feature-spec.md`](../features/)）はここに従う。詳細は各 feature の sub-feature 設計書（[`requirements.md`](../features/) / [`basic-design.md`](../features/)）に展開する。

## 非機能要件一覧

| 区分 | 指標 | 目標 |
|---|---|---|
| パフォーマンス | API 応答（CRUD） | \<例: p95 200ms 以下\> |
| パフォーマンス | \<その他指標\> | \<目標値\> |
| 可用性 | \<可用性要求\> | \<例: ローカルファースト / SLA 99.9%\> |
| 永続化 | \<DB 設定\> | \<例: WAL モード / バックアップ\> |
| 対応 OS | 最低ライン | \<例: Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+\> |
| ランタイム | バックエンド | \<例: Python 3.12+\> |
| ランタイム | フロントエンド / ツール | \<例: Node.js 20 LTS+\> |
| ライセンス | — | \<例: MIT / Apache-2.0\> |
| セキュリティ | コミット署名 | \<必須 / 任意\> |
| セキュリティ | secret 検知 | \<例: pre-commit gitleaks + CI audit-secrets\> |
| セキュリティ | サプライチェーン | \<例: 依存ツール SHA256 検証\> |
| 監査性 | \<監査要件\> | \<例: 全操作を audit_log に記録\> |

## 関連

- [`functional-scope.md`](functional-scope.md) — 機能スコープ
- [`acceptance-criteria.md`](acceptance-criteria.md) — 受入基準
- [`../design/threat-model.md`](../design/threat-model.md) — セキュリティ詳細（脅威モデル）
- [`../design/tech-stack.md`](../design/tech-stack.md) — 採用技術と根拠
