# 業務コンテキスト

bakufu の **着想元・差別化・bakufu と ai-team の関係** を凍結する。なぜ bakufu を作るのか、何が他と違うのかの業務的根拠。

## プロダクト概要

**bakufu**（幕府）は、UI で **Room（部屋）** を自由に編成し、AI エージェント群が任意のワークフロー（Vモデル / アジャイル / 雑談 / アシスタント等）で協業する、ローカルファーストのエージェント・エンパイア・オーケストレーター。各工程の **外部レビュー（人間承認）** を一級概念として扱い、AI 協業による品質向上を人間のチェックポイントで担保する。

## 着想元と差別化

| 着想元 | 引き継ぐ思想 | bakufu での扱い |
|----|----|----|
| **ai-team**（同オーナー運営、Discord ベース AI エージェント協業） | 「**開発室**」概念、Vモデル工程強制、**内部レビュー機構**（reviewer / ux / security 3 ロール並列ゲート + `[合格]` / `[却下]` テキストタグ抽出 + 全合格時の自動外部提出）、`#外部レビュー` チャネルでの人間承認、複数 AI エージェントの役割分担 | **コア思想を bakufu に移植**。Discord チャネルを Web UI の Room に、`#外部レビュー` を `ExternalReviewGate` Aggregate として一級概念に昇格、**内部レビュー機構を `InternalReviewGate`（または Stage 内ゲート）として Workflow に組み込み、外部レビュー到達前の品質担保ループを構築** |
| **ClawEmpire**（OSS、AI agent office simulator） | Empire / Department、git worktree 隔離、`$` プレフィックス CEO directive、ローカルファースト | 思想は踏襲、ただしコード品質に課題があるため**ゼロから DDD で再設計** |
| **shikomi**（同オーナー運営、Rust 製クリップボードツール） | dev-workflow（lefthook + just + convco + gitleaks）、Vモデルで開発フロー自体を機能として定義する手法 | dev-workflow を Python+TypeScript に翻訳して移植 |

## bakufu と ai-team の関係

- **ai-team は bakufu の実装担当**: ai-team の各エージェント（リーダー・設計責任者・プログラマー・テスト担当・品質担当）が Discord 上の協業で bakufu を開発する
- **bakufu は将来 ai-team を吸収しうる後継プロダクト**: Web UI ベースで運用しやすく、Discord 環境に閉じない
- **bakufu の MVP 達成後**、ai-team の運用機能（雑談 Room / アシスタント Room / ブログ編集部）を bakufu に順次移植する想定（Phase 2）

## bakufu 自身が完成すれば、bakufu で bakufu の機能拡張ができる

MVP 達成後、bakufu インスタンスを立ち上げて bakufu Empire を作成し、bakufu 自身の Phase 2 機能拡張を ai-team から bakufu へ移植する経路が成立する（自己ホスティング、dogfooding）。

## 関連

- [`personas.md`](personas.md) — bakufu のペルソナ
- [`pain-points.md`](pain-points.md) — bakufu が解決する業務課題
- [`business-vision.md`](business-vision.md) — bakufu 全体のビジョン
