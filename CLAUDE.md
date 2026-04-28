# bakufu — Claude Code エージェント向け指示書

bakufu リポジトリで作業する Claude Code（および任意の AI エージェント）が**最初に読むべき**指示書。本書の規律はオーナー（`@kkm-horikawa`）の方針に基づき、CI / branch protection / 設計書群と連動する。**遵守できないなら作業を中断してオーナーに確認すること。**

## 0. 最優先: 作業前に読む資料

新規 feature の起票・実装に着手する**前に**、以下を必ず読む。読まずに手を動かすことは禁止。

| 順 | パス | Vモデル工程 / 役割 |
|----|----|----|
| 1 | [`docs/analysis/`](docs/analysis/) | **要求分析**: ペルソナ / 業務コンテキスト / 痛点 / ビジョン |
| 2 | [`docs/requirements/`](docs/requirements/) | **要件定義**: システムコンテキスト図 / 主要ユースケース / 機能スコープ / マイルストーン / 受入基準 / 非機能 / 外部連携 |
| 3 | [`docs/design/`](docs/design/) | **基本設計**: アーキテクチャ概観 / ドメインモデル / 採用技術 / 脅威モデル / DB マイグレーション計画 |
| 4 | [`docs/acceptance-tests/`](docs/acceptance-tests/) | **受入テスト戦略**（Vモデル右上、Issue #64 で新設） |
| 5 | [`CONTRIBUTING.md`](CONTRIBUTING.md) | GitFlow / Conventional Commits / マージ戦略 / コーディング規約 |
| 6 | [`docs/features/dev-workflow/`](docs/features/dev-workflow/) | 開発フロー（lefthook + just + convco + gitleaks）の Vモデル 5 設計書 |
| 7 | 該当 feature の `docs/features/<feature-name>/` | 実装対象 feature の Vモデル 5 設計書（既存なら必読） |

## 1. 設計責任者として動作する

bakufu のコードは ai-team が長期で運用・拡張する前提。**今日動くか**ではなく **将来の変更に安全・クリーン・シンプルに拡張できるか** を判断軸とする。

### 設計原則

- **Clean Architecture / SOLID**: 責務はクラス・モジュールに閉じ、依存方向は一方向（`interfaces` → `application` → `domain` ← `infrastructure`）。トップダウンに読めるコードを書く
- **Domain-Driven Design**: 業務概念（Empire / Room / Workflow / Agent / Task / ExternalReviewGate 等）をそのままドメインオブジェクトとして表現する。技術的詳細は infrastructure 層に閉じ込める。グローバル関数の羅列は設計の失敗
- **Tell, Don't Ask**: Aggregate Root にデータを聞いて外で処理するな。「やれ」と命令しろ
- **Fail Fast**: 不正な入力・状態は早期に検知して例外を raise。エラーを握り潰さない・中途半端な状態を引きずらない
- **DRY / YAGNI / KISS**: 重複を書かない、今必要なものだけ作る、複雑な分岐が必要なら設計が間違っている

### 範囲規律

- **依頼されたことだけやれ**: 追加機能・余計なリファクタリング・頼まれていないドキュメント整備を勝手にしない
- **スコープ外作業はオーナー確認必須**: スコープを広げる前に CONTRIBUTING / 該当 feature の設計書をオーナーに確認させる
- **既存コードに倣うな**: 既存コードはゴミである前提で、原則に従ったコードを書け（ただし破壊的リファクタは事前確認）

### コード規律

- **型は明示**: Python は `pyright` strict、TypeScript は `tsc --noEmit` strict。`any` / `Any` / 型アサーションは設計の敗北
- **エラーハンドリングは境界のみ**: ユーザー入力・外部 API・LLM 呼び出しの境界でのみ。内部コードのエラーは例外を伝播させる
- **コメントは「なぜそうするか」だけ書く**: 「何をするか」はコードが語る。投機的な抽象化・将来用の汎化・使わないオプションは書くな
- **テストは実装と同時にコミット**: 後回しにしない。Vモデル設計書の test-design.md に従う

## 2. 絶対遵守の運用規律

### 2.1 ブランチ運用（GitFlow）

- **`main` / `develop` への直接 push は禁止**（branch protection で `force push: false` 強制）
- 全変更は **PR 経由**：
  - `feature/*` → `develop`（squash merge）
  - `release/*` → `main` + `develop` への back-merge（merge commit）
  - `hotfix/*` → `main` + `develop` への back-merge（merge commit）
- ブランチ命名: `feature/{slug}` / `feature/{issue}-{slug}` / `release/X.Y.Z` / `hotfix/X.Y.Z`
- 24h 以内の back-merge を `back-merge-check` CI が監視
- **明示的承認なしに `main` へマージするな**

### 2.2 コミット規約

- **Conventional Commits 必須**（PR タイトル含む、CI `pr-title-check` で検証）
- `<type>[scope]: <description>` — `feat` / `fix` / `docs` / `chore` / `refactor` / `test` / `ci` / `build` / `perf`
- **コミット署名必須**: `main` / `develop` ともに `required_signatures = true`（SSH または GPG）
- **AI 生成フッター禁止**: `🤖 Generated with Claude Code` / `Co-Authored-By: Claude <noreply@anthropic.com>` / `Co-Authored-By: Claude` 系の trailer をメッセージに含めない（commit-msg フック + 人間レビューで二重防護）
- `Co-authored-by` は禁止、`Github-Issue:#<番号>` トレーラの利用は許可
- 関連バグ修正時は `Reported-by:<name>` トレーラ

### 2.3 dev-workflow 規律

- **`--no-verify` 禁止**: lefthook の pre-commit / pre-push / commit-msg をローカルでバイパスしない。CI で同等ジョブが再検査して必ず落ちる
- **CI 7 ジョブ全緑が PR マージ条件**: branch-policy / pr-title-check / lint / typecheck / test-backend / test-frontend / audit
- **CODEOWNERS 保護パスは改変前にオーナー確認**:
  - `/lefthook.yml` / `/justfile` / `/scripts/setup.sh` / `/scripts/setup.ps1` / `/scripts/ci/`
  - `/.github/` / `/docs/analysis/` / `/docs/requirements/` / `/docs/design/` / `/docs/acceptance-tests/` / `/docs/features/`
- **secret 混入時の緊急対応**: `CONTRIBUTING.md §Secret 混入時の緊急対応` の 3 段階手順を遵守（即 revoke → `git filter-repo` → GitHub secret scanning resolve）

### 2.4 破壊的操作

- 削除 / force push / 本番環境への変更は明示的指示なしに実行しない
- `git reset --hard` / `git push --force` / `git checkout -- <file>` は事前確認
- `secrets/` ディレクトリのファイル・`.env` を Git にコミットしない
- 一度承認された操作が次も承認されているとは思わない（毎回確認）

## 3. 新 feature 起票プロセス

bakufu は **Vモデル工程強制**。実装に進む前に、必ず設計書 5 本を起こしてレビューを通す。

### 3.1 ブランチと PR の分割（推奨）

| フェーズ | ブランチ | PR の対象 |
|----|----|----|
| 設計 PR | `feature/<name>-design` | `docs/features/<name>/` の Vモデル 5 ファイル |
| 実装 PR | `feature/<name>` | `backend/` / `frontend/` のソース + テスト |

設計 PR を先に通してオーナー承認を得てから、実装 PR を起こす。実装中に設計書の更新が必要なら別 PR で先行して直す。

### 3.2 Vモデル 5 ファイルの起こし方

`docs/features/_template/` をコピーして `docs/features/<feature-name>/` に置く。各ファイルを順に書く：

| 順 | ファイル | 役割 |
|----|----|----|
| 1 | `requirements-analysis.md` | 人間の要求・痛点・ペルソナ・議論結果・確定事項・機能一覧・受入基準 |
| 2 | `requirements.md` | 機能要件（REQ ID 付き）・CLI/API/UI 仕様・データモデル・MSG（ユーザー向けメッセージ）・依存関係 |
| 3 | `basic-design.md` | モジュール構成・クラス設計（mermaid）・処理フロー・シーケンス図・脅威モデル・エラーハンドリング方針 |
| 4 | `detailed-design.md` | 構造契約の詳細・MSG 確定文言・キー構造表・API エンドポイント詳細・確定事項（先送り撤廃） |
| 5 | `test-design.md` | テストマトリクス・外部 I/O 依存マップ・E2E / 結合 / ユニットテストケース・カバレッジ基準 |

### 3.3 着手すべき最初の feature

[`docs/requirements/milestones.md §着手すべき最初の feature（M1）`](docs/requirements/milestones.md) より、MVP M1 の着手順：

1. `feature/empire-aggregate` — Empire Aggregate Root（domain/empire.py）
2. `feature/room-aggregate` — Room Aggregate（domain/room.py）
3. `feature/workflow-aggregate` — Workflow + Stage + Transition（domain/workflow.py）
4. `feature/agent-aggregate` — Agent Aggregate（domain/agent.py）
5. `feature/task-aggregate` — Task Aggregate + 状態遷移（domain/task.py）
6. `feature/external-review-gate` — ExternalReviewGate Aggregate（domain/external_review.py）

各 feature は **単一 Aggregate に閉じる粒度**で起こす。

## 4. ローカル作業の手順

### 4.1 初回セットアップ

```bash
git clone https://github.com/bakufu-dev/bakufu.git
cd bakufu
bash scripts/setup.sh        # Unix（uv / just / convco / lefthook / gitleaks + Python/Node ツール導入 + lefthook install）
# Windows: pwsh scripts/setup.ps1
```

### 4.2 日常コマンド

```bash
just --list           # 全レシピ一覧
just check-all        # fmt-check / lint / typecheck / test / audit / audit-secrets / audit-pin-sync を順次
just fmt              # ruff + biome の自動修正
```

### 4.3 同時編集の競合対策

複数エージェントが同一リポを並行編集する場合、`<repo-root>/.worktree/<feature-name>/` で git worktree を切って作業する。これは **ai-team から複数エージェントが bakufu を実装する想定**で運用上必須。

```bash
git worktree add .worktree/feature-empire-aggregate develop -b feature/empire-aggregate
cd .worktree/feature-empire-aggregate
```

worktree 不使用で同一ブランチを別エージェントが編集すると、push 競合・コミット衝突が頻発する。

## 5. 出力スタイル

- **応答は日本語**（コード内のコメント・docstring は本リポジトリの慣習に従う）
- **直接答える**: 前置き・要約・「〜しました」の締めは不要。結論と変更点だけ伝える
- **不確実性を明示**: 確認できていないことを断定しない。調べてから答える
- **絵文字は使わない**（CLAUDE.md / コミットメッセージ / 設計書）

## 6. 困ったとき

- 設計書と実装が乖離している → **設計書を真実源**として扱い、実装側を修正する PR を立てる（設計を変えるべきと判断したら別の設計 PR で先に直す）
- CI が落ちる原因が不明 → `gh run view <run-id> --log-failed` で詳細確認、ローカルで `just <recipe>` を再現
- branch protection で push が拒否される → `feature/*` ブランチからの PR 経由か確認、CI 必須ジョブが緑か確認
- lefthook が動かない / `--no-verify` を使いたくなる → そう感じた時点で**作業を止めてオーナーに状況を報告する**（バイパスは規約違反）

---

**本書は bakufu リポジトリの作業中 Claude Code が常時参照する規律。逸脱が必要な場面は必ずオーナー（`@kkm-horikawa`）に確認すること。**
