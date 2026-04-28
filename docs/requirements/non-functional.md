# 非機能要件

bakufu MVP の非機能要件を凍結する。各 feature の業務仕様（[`../features/<name>/feature-spec.md`](../features/)）はここに従う。詳細は各 feature の sub-feature 設計書（[`requirements.md`](../features/) / [`basic-design.md`](../features/)）に展開する。

## 非機能要件一覧

| 区分 | 指標 | 目標 |
|-----|------|------|
| パフォーマンス | API 応答（CRUD） | p95 200ms 以下 |
| パフォーマンス | WebSocket イベント配信 | p95 100ms 以下 |
| パフォーマンス | Agent CLI セッション初回確立 | p95 5 秒以下（CLI 起動時間に依存） |
| 可用性 | ローカルファースト | ネットワーク断時も既存 Task の閲覧・履歴参照は可能（LLM 呼び出しのみネットワーク必須） |
| 永続化 | SQLite WAL モード | 単一プロセス運用、ファイル所有者 0600 |
| 対応 OS | 最低ライン | Windows 10 21H2+ / macOS 12+ / Linux（glibc 2.35+） |
| ランタイム | バックエンド | Python 3.12+ |
| ランタイム | フロントエンド / ツール | Node.js 20 LTS+ |
| ライセンス | — | MIT（OSS 公開・貢献容易性優先） |
| セキュリティ | コミット署名 | 必須（branch protection で強制、SSH/GPG 鍵） |
| セキュリティ | secret 検知 | pre-commit gitleaks + CI audit-secrets の二重防護 |
| セキュリティ | サプライチェーン | 全開発ツールバイナリ SHA256 検証 |
| 監査性 | 外部レビュー判断履歴 | ExternalReviewGate.audit_trail に永続記録（誰がいつ何を見たか） |

## 関連

- [`functional-scope.md`](functional-scope.md) — 機能スコープ
- [`acceptance-criteria.md`](acceptance-criteria.md) — 受入基準
- [`../design/threat-model.md`](../design/threat-model.md) — セキュリティ詳細（脅威モデル）
- [`../design/tech-stack.md`](../design/tech-stack.md) — 採用技術と根拠
