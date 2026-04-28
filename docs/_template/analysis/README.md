# `analysis/` — 要求分析（Vモデル左上 1）

「**誰のために・何を作るのか・なぜ必要なのか**」を凍結する。観察主体（ペルソナ）の業務上の痛点・期待・ビジョンを記録する場。

## 本ディレクトリの役割

**書くこと**:
- ペルソナ（プライマリ / セカンダリ / エクスターナル）
- 着想元と差別化（先行プロダクト / 思想 / 関連プロダクトとの関係）
- 解決する業務課題（現状の痛点）
- プロジェクト全体のビジョン

**書かないこと**（後段の工程ディレクトリへ追い出す）:
- システム機能要件（CRUD / API / UI 仕様等） → [`../requirements/`](../requirements/)
- 主要ユースケース・コンテキスト図 → [`../requirements/`](../requirements/)
- ドメインモデル / 技術スタック / 脅威モデル → [`../design/`](../design/)
- 各 feature の業務仕様 → [`../features/<feature-name>/feature-spec.md`](../features/)

## 所収ファイル

| ファイル | 役割 |
|---|---|
| [`personas.md`](personas.md) | ペルソナ定義 |
| [`business-context.md`](business-context.md) | 着想元と差別化、関連プロダクトとの関係 |
| [`pain-points.md`](pain-points.md) | 解決する業務課題、現状の痛点 |
| [`business-vision.md`](business-vision.md) | プロジェクト全体のビジョンと提供価値 |

## 対応するテストレベル

要求分析 ↔ **受入テスト**: [`../acceptance-tests/scenarios/`](../acceptance-tests/scenarios/)

## 関連

- [`../requirements/`](../requirements/) — 次工程（要件定義）
- [`../design/`](../design/) — 基本設計
- [`../features/`](../features/) — 詳細設計工程の各 feature
