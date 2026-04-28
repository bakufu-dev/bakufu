# ビジネスビジョン

bakufu 全体の長期ビジョンと、MVP（v0.1.0）が目指す具体的な提供価値を凍結する。

## bakufu の長期ビジョン

bakufu は **AI エージェント群と人間が協業して業務を遂行する組織オーケストレーター** を目指す。bakufu インスタンスは個人または小規模チームが立ち上げる「組織コンテナ」であり、複数の業務概念（Vモデル開発室 / アジャイル開発室 / 雑談 Room / アシスタント Room / ブログ編集部 等）を編成して運用する。

長期的に目指す姿:

- **AI 協業の品質を人間チェックポイントで担保**: 各業務工程の external review gate が一級概念として組織のフロー上に存在し、AI の暴走や脱線を物理的に防ぐ
- **業務概念の可塑性**: Workflow Designer により「業務に応じた Vモデル / アジャイル / 自由フロー」を CEO が UI で編成可能
- **ローカルファースト**: ユーザー端末上で完結する。クラウド依存を最小化（外部 LLM のみネットワーク必須）
- **dogfooding 自己ホスティング**: bakufu 自身が完成すれば、bakufu で bakufu の Phase 2 機能拡張を進める

## MVP（v0.1.0）の提供価値

> **「UI で V モデル開発室を作って、Agent 5 体でタスクを実行し、各工程の外部レビューを人間が承認/差し戻しできる」**

これが動けば、bakufu の核心思想（Room First / DAG ワークフロー / External Review Gate）が実証される。

MVP の業務的な意義:

1. CEO が「組織を建てて運用する」最初のループが回る
2. Vモデル工程の強制（人間の意識に依存しない）が実装レベルで成立する
3. 外部レビューが Discord 通知 → UI 承認 で完結する
4. 再起動跨ぎでの状態保持により「使い捨てツール」ではなく「継続的な組織運営ツール」として成立する

## MVP 達成後の展望

MVP マージ後の Phase 2 では、ai-team の運用機能（雑談 Room / アシスタント Room / ブログ編集部）を bakufu へ移植し、bakufu インスタンスで bakufu の Phase 3 機能（マルチプロバイダ / ピクセルアート UI / ビジュアル Workflow Designer 等）を開発する自己ホスティング体制へ移行する。

詳細な機能スコープは [`../requirements/functional-scope.md`](../requirements/functional-scope.md) を参照。

## 関連

- [`personas.md`](personas.md) — ペルソナ定義
- [`business-context.md`](business-context.md) — 着想元と差別化
- [`pain-points.md`](pain-points.md) — bakufu が解決する業務課題
- [`../requirements/functional-scope.md`](../requirements/functional-scope.md) — MVP の機能スコープ（含める / 含めない）
- [`../requirements/milestones.md`](../requirements/milestones.md) — マイルストーン M1〜M7
- [`../requirements/acceptance-criteria.md`](../requirements/acceptance-criteria.md) — MVP 完了の判定基準
