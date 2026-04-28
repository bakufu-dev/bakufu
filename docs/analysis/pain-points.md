# 解決する業務課題

bakufu のペルソナ（[`personas.md`](personas.md)）が直面する業務課題と、bakufu がそれをどう解決するかを凍結する。要求分析の核心であり、各 feature の業務仕様（[`../features/<name>/feature-spec.md`](../features/)）が本ファイルを引用して業務根拠を主張する。

## 課題と解決方針

| # | 課題 | bakufu の対応 |
|---|----|----|
| 1 | ai-team の Discord ベースはチャネル運用が口頭規律で揺らぎ、Vモデル工程の遵守が個人の意識に依存する | Workflow / Stage / Transition を **ドメインモデル上の Aggregate として強制**。工程ロック・差し戻し経路は UI で逸脱不能 |
| 2 | 外部レビューが「忘れられがち」「差し戻し履歴がチャネル発言に埋もれて追えない」 | **`ExternalReviewGate` を独立 Aggregate**として一級昇格。複数ラウンドの判断履歴・閲覧監査ログを保持 |
| 3 | 「複数 AI エージェントを協業させる」セットアップに開発者の時間が取られる（プロンプト設計、役割定義、会話継続） | UI で **Empire / Room / Agent / Workflow を編成可能**。プリセット（Vモデル開発室 / アジャイル開発室）からの 1 クリック生成 |
| 4 | Discord 上では各 Agent の発言が時系列に流れ、後から特定 Stage の議論を遡るのが困難 | Conversation を **Stage ごとに分離**して保持。UI に Stage 別タブで表示 |
| 5 | ClawEmpire は同方向だがコード品質に課題があり、長期運用に不安 | **DDD + Clean Architecture でゼロから設計**。Aggregate 境界を文章で固めてから実装（ai-team 開発室が担当） |
| 6 | 個人開発者が複数プロジェクトを並行で進める際、各 Empire の状況を一画面で把握できない | bakufu Web UI のダッシュボードで **全 Empire / Room / Task の状態を可視化** |
| 7 | 1 対 1 で LLM CLI を使う運用では、人間チェック前の deliverable 品質が低く、レビュアー（CEO）に到達した時点で大量の指摘事項が発生する | **内部レビューゲート機構**: 各工程末尾で複数の観点別レビュワー Agent（reviewer / ux / security 等）が **並列・独立** に判定し、全 APPROVED でないと外部（人間）レビューに到達しない設計。Vモデルの「ピアレビュー」相当のチェックポイントとして、bakufu の差別化価値の核心 |

## 関連

- [`personas.md`](personas.md) — ペルソナ定義（CEO / Owner Reviewer / AI Agent）
- [`business-context.md`](business-context.md) — 着想元と差別化
- [`business-vision.md`](business-vision.md) — bakufu 全体のビジョンと提供価値
- [`../requirements/`](../requirements/) — 上記課題をシステム機能として翻訳した要件定義
