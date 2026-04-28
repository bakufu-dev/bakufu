# `requirements/` — 要件定義（Vモデル左上 2）

「**システムが何を提供すべきか**」を機能要件・非機能要件・スコープ・主要ユースケースの観点で凍結する。要求分析（[`../analysis/`](../analysis/)）の業務的痛点をシステム機能として翻訳する場。

## 本ディレクトリの役割

**書くこと**:
- システムコンテキスト（コンテキスト図、アクター）
- 主要ユースケース（業務シナリオの代表例、シーケンス図）
- 機能スコープ（含める / 含めない / 非スコープ）
- 非機能要件（パフォーマンス、可用性、セキュリティ要求）
- 外部連携（プロトコル、認証）
- マイルストーン
- 受入基準（受入テストの真実源）

**書かないこと**（後段の工程ディレクトリへ追い出す）:
- ドメインモデル → [`../design/domain-model.md`](../design/domain-model.md)
- 採用技術 → [`../design/tech-stack.md`](../design/tech-stack.md)
- 脅威モデル → [`../design/threat-model.md`](../design/threat-model.md)
- 各 feature の業務仕様詳細 → [`../features/<feature-name>/feature-spec.md`](../features/)
- 実装方式 → [`../features/<feature-name>/<sub-feature>/`](../features/)

## 所収ファイル

| ファイル | 役割 |
|---|---|
| [`system-context.md`](system-context.md) | システムコンテキスト図 + アクター一覧 |
| [`use-cases.md`](use-cases.md) | 主要ユースケース（シーケンス図） |
| [`functional-scope.md`](functional-scope.md) | 機能スコープ（含める / 含めない / 非スコープ） |
| [`non-functional.md`](non-functional.md) | 非機能要件 |
| [`external-integrations.md`](external-integrations.md) | 外部連携 |
| [`milestones.md`](milestones.md) | マイルストーン |
| [`acceptance-criteria.md`](acceptance-criteria.md) | 受入基準（受入テストの真実源） |

## 対応するテストレベル

要件定義 ↔ **システムテスト**: 各 feature の [`features/<feature-name>/system-test-design.md`](../features/) で扱う

## 関連

- [`../analysis/`](../analysis/) — 前工程（要求分析）
- [`../design/`](../design/) — 次工程（基本設計）
- [`../acceptance-tests/`](../acceptance-tests/) — `acceptance-criteria.md` を真実源とする受入テスト
