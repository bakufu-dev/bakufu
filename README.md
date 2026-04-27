# bakufu（幕府）

UI で **Room（部屋）** を自由に編成し、AI エージェント群が任意のワークフロー（V モデル / アジャイル / 雑談 / アシスタント等）で協業する、ローカルファーストのエージェント・エンパイア・オーケストレーター。各工程の **外部レビュー（人間承認）** を一級概念として扱い、AI 協業による品質向上を人間のチェックポイントで担保する。

## 特徴

- **Room First**: UI で Room（開発室・雑談・アシスタント等）を自由に作成。各 Room は独自のワークフロー＋採用メンバー＋プロンプトを持つ
- **DAG ワークフロー**: 工程の並列・差し戻しループ・条件分岐を柔軟に定義
- **External Review Gate**: 工程間の人間チェックポイントを独立した集約として一級扱い。複数ラウンドの承認/差戻し履歴を保持
- **Multi-Provider Agents**: Claude Code / Codex / Gemini ほか CLI・API ベースのエージェントを部門横断で配備
- **Local-First**: SQLite ベースのローカル実行、データはマシン上に留まる

## 動作環境

| カテゴリ | 対応 |
|----|------|
| OS | Windows 10/11、macOS 12+、Linux（glibc 2.35+） |
| ランタイム | Python 3.12+、Node.js 20 LTS+、SQLite 3.40+ |

## ステータス

開発初期。MVP（V モデル開発室 1 部屋でタスク完走 + 外部レビューゲート）に向けた設計フェーズ。詳細は [`docs/architecture/`](docs/architecture/) および [`docs/features/`](docs/features/) を参照。

## ビルド方法（開発者向け）

開発環境のセットアップは [`CONTRIBUTING.md`](CONTRIBUTING.md) を参照してください。

```bash
git clone https://github.com/bakufu-dev/bakufu.git
cd bakufu

# Unix
bash scripts/setup.sh

# Windows
pwsh scripts/setup.ps1
```

## セキュリティ

脆弱性を発見した場合は [`SECURITY.md`](SECURITY.md) の手順に従ってご報告ください。

## ライセンス

[MIT License](LICENSE) — Copyright © 2026 bakufu Contributors
