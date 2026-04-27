# Security Policy

## サポートバージョン

| バージョン | サポート状況 |
|-----------|------------|
| latest（main） | ✅ セキュリティ修正あり |
| 1 つ前のマイナーリリース | ✅ Critical / High のみ |
| それ以前 | ❌ |

## 脆弱性の報告（Reporting a Vulnerability）

**脆弱性は GitHub の公開 Issue に投稿しないでください。** 悪用される前に修正する機会を確保するため、非公開での報告をお願いします。

### 報告方法

**GitHub Security Advisories**（唯一の報告窓口）:
[https://github.com/bakufu-dev/bakufu/security/advisories/new](https://github.com/bakufu-dev/bakufu/security/advisories/new) から非公開で報告してください。GitHub のプライベートフォーク機能を使い、修正コードを報告者と共同でレビューすることもできます。

### 報告内容に含めるべき情報

- 脆弱性の種類（例: 認証バイパス、情報漏洩、コマンドインジェクション）
- 影響を受けるコンポーネント・バージョン
- 再現手順（可能であれば PoC）
- 想定される影響範囲
- 発見者の情報（クレジット希望の有無）

## 対応プロセス

| フェーズ | タイムライン |
|---------|-----------|
| 受信確認 | 72h 以内 |
| 初期トリアージ（Severity 評価） | 5 営業日以内 |
| 修正リリース（High / Critical） | 14 日以内（状況により延長の場合あり） |
| 修正リリース（Medium 以下） | 次回定期リリースに含める |
| 公開開示 | 修正リリースから 90 日後（または報告者との合意日） |

## Severity 基準

[CVSS v3.1](https://www.first.org/cvss/v3.1/specification-document) に基づき評価します。

| Severity | CVSS スコア | 対応方針 |
|----------|-----------|---------|
| Critical | 9.0 – 10.0 | 緊急 hotfix、即時リリース |
| High | 7.0 – 8.9 | 14 日以内に hotfix |
| Medium | 4.0 – 6.9 | 次回マイナーリリースに含める |
| Low | 0.1 – 3.9 | 次回マイナーまたはパッチリリース |

## 脅威モデルのスコープ

以下は **bakufu の脅威モデルのスコープ内** です（報告を歓迎します）:

- SQLite データ（Empire / Room / Agent / Task 定義）の不正読取・改竄
- REST API / WebSocket の認証バイパス・権限昇格
- Agent CLI（Claude Code / Codex / Gemini 等）経由のコマンドインジェクション
- 外部レビューゲートにおける承認・差戻し決定の偽装
- OAuth トークン（GitHub / Google 等）の不適切な保存・露出
- サプライチェーン攻撃（Python / Node 依存ライブラリ）

以下は **スコープ外** です:

- ローカルの物理アクセスがある攻撃者（同一端末に物理アクセスできる場合は OS 側の問題）
- 脆弱性の実証なしのソーシャルエンジニアリング
- ユーザーが明示的に信頼していない Agent プロバイダの動作

## クレジット

報告者のご希望に応じて、修正リリースの CHANGELOG および GitHub Security Advisory にクレジットを掲載します。
