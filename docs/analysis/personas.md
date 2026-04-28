# ペルソナ

bakufu の設計判断の軸として、代表ペルソナを定義する。後続 feature の業務仕様（[`feature-spec.md`](../features/)）・要件定義（[`../requirements/`](../requirements/)）・基本設計（[`../design/`](../design/)）は本ペルソナに対する価値で判断する。

## ペルソナ A: 個人開発者 CEO — **プライマリ**

| 区分 | 内容 |
|---|---|
| 背景 | フリーランス / インディー開発者。複数の小規模プロジェクトを並行で進める |
| 技術レベル | GitHub / Docker / CLI を日常使用、ローカル LLM ツール（Claude Code 等）の経験あり |
| 利用シーン | 新規 OSS プロジェクトの要求分析〜実装を AI エージェント群に分担させる、自分は外部レビューと方針決定に集中する |
| 期待 | 「Discord に閉じない Web UI で運用したい」「Vモデルの工程ロックで品質を担保したい」「AI が暴走しないよう人間チェックポイントを必ず通したい」 |
| ペインポイント | 単独開発で全工程を回す時間がない。AI エージェントだけに任せると品質ばらつきと脱線が発生する |

## ペルソナ B: AI Agent — **Agent-C 系**

| 区分 | 内容 |
|---|---|
| 本体 | Claude Code / Codex / Gemini 等の LLM CLI エージェント |
| 能力 | ファイル読み書き、bash/PowerShell 実行、Web 検索、git 操作 |
| 利用文脈 | bakufu Backend からプロンプト + コンテキスト + 過去会話を渡され、Stage の deliverable を生成する |
| 期待 | 「会話セッションが工程をまたいで継続する（CLI セッション ID 保持）」「Agent ごとの persona / role / skills が事前注入されている」「他 Agent の発言を Conversation ログから引ける」 |
| 制約 | AI 生成フッター（`Co-Authored-By: Claude` 等）をコミットメッセージに含めない（[`CONTRIBUTING.md §AI 生成フッターの禁止`](../../CONTRIBUTING.md)） |

## ペルソナ C: Owner Reviewer / チームレビュワー — **セカンダリ**

| 区分 | 内容 |
|---|---|
| 背景 | CEO と分離したい場合の品質責任者（小規模チームの技術リード）。MVP では通常 CEO 兼任 |
| 技術レベル | コードレビュー経験あり、ドメイン知識保持 |
| 利用シーン | 複数 Empire の外部レビューゲートを横断で担当、Discord 通知から UI を開いて承認 / 差し戻し |
| 期待 | 「複数 Empire のレビュー待ちが 1 ダッシュボードで見える」「差し戻し履歴が監査ログとして残る」「コメントだけ書いて差し戻し処理を実行できる」 |

## 関連

- [`business-context.md`](business-context.md) — bakufu の着想元と差別化（ペルソナがなぜ bakufu を必要とするか）
- [`pain-points.md`](pain-points.md) — 各ペルソナが直面する具体的な業務課題
- [`../requirements/system-context.md`](../requirements/system-context.md) — ペルソナとシステムの関係（コンテキスト図 + アクター）
