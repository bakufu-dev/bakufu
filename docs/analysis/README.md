# `docs/analysis/` — 要求分析（Vモデル左上 1）

bakufu の **要求分析** を凍結するディレクトリ。Vモデル工程の最上位（要求分析 ↔ 受入テスト）に対応する。

## 本ディレクトリの役割

「**誰のために・何を作るのか・なぜ必要なのか**」を凍結する。観察主体（ペルソナ）の業務上の痛点・期待・ビジョンを記録する場。

**書くこと**:
- ペルソナ（CEO / Owner Reviewer / AI Agent）
- 着想元と差別化（ai-team / ClawEmpire / shikomi）
- bakufu が解決する業務課題（解決する痛点）
- bakufu 全体のビジョンと提供価値

**書かないこと**（後段の工程ディレクトリへ追い出す）:
- システム機能要件（CRUD / API / UI 仕様等） → [`../requirements/`](../requirements/)
- 主要ユースケース・コンテキスト図 → [`../requirements/`](../requirements/)
- ドメインモデル / 技術スタック / 脅威モデル → [`../design/`](../design/)
- 各 feature の業務仕様 → [`../features/<name>/feature-spec.md`](../features/)

## 所収ファイル

| ファイル | 役割 |
|---|---|
| [`personas.md`](personas.md) | ペルソナ定義（CEO / Owner Reviewer / AI Agent） |
| [`business-context.md`](business-context.md) | 着想元と差別化、bakufu と ai-team の関係 |
| [`pain-points.md`](pain-points.md) | 解決する業務課題、現状の痛点 |
| [`business-vision.md`](business-vision.md) | bakufu 全体のビジョンと提供価値 |

## 対応するテストレベル

要求分析 ↔ **受入テスト**: [`../acceptance-tests/scenarios/`](../acceptance-tests/scenarios/)（PR2 で新設）

## 関連

- [`../requirements/`](../requirements/) — 次工程（要件定義）
- [`../design/`](../design/) — 基本設計
- [`../features/`](../features/) — 詳細設計工程の各 feature
