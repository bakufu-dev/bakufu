# Contributing to bakufu

## 目次

1. [はじめに](#はじめに)
2. [ブランチ戦略（GitFlow）](#ブランチ戦略gitflow)
3. [コミット規約（Conventional Commits）](#コミット規約conventional-commits)
4. [マージ戦略](#マージ戦略)
5. [PR 規約](#pr-規約)
6. [開発環境セットアップ](#開発環境セットアップ)
7. [AI 生成フッターの禁止](#ai-生成フッターの禁止)
8. [Secret 混入時の緊急対応](#secret-混入時の緊急対応)
9. [コーディング規約](#コーディング規約)

---

## はじめに

bakufu への貢献を歓迎します。バグ報告・機能提案・ドキュメント改善・コード PR、いずれも大歓迎です。

セキュリティ脆弱性を発見した場合は、Issue ではなく [SECURITY.md](SECURITY.md) の手順に従って非公開で報告してください。

---

## ブランチ戦略（GitFlow）

本プロジェクトは **GitFlow** を採用します。

### ブランチ構成

| ブランチ | 役割 | 起点 | マージ先 |
|---------|------|------|---------|
| `main` | リリース済みの唯一の真実源。各コミットはタグ付きリリースに対応 | — | — |
| `develop` | 次期リリースの統合ブランチ。全 `feature` がここに集約 | `main`（初回のみ） | `release/*` 経由で `main` へ |
| `feature/*` | 単一機能・単一 Issue の作業ブランチ | **`develop`** | **`develop`** |
| `release/*` | RC 期間。バージョン bump / CHANGELOG 確定のみ | `develop` | `main`（tag 付与）+ `develop`（back-merge） |
| `hotfix/*` | リリース済み版への緊急修正 | `main` | `main`（tag 付与）+ `develop`（back-merge） |

### feature ブランチの命名規則

```
feature/{issue-number}-{slug}
feature/{slug}

例:
  feature/3-room-aggregate
  feature/external-review-gate
```

### release / hotfix ブランチの命名規則

```
release/{version}   例: release/0.1.0    （v 接頭辞なし。タグ側に v を付ける）
hotfix/{version}    例: hotfix/0.1.1
```

### 作業フロー（feature）

1. `develop` から `feature/{slug}` を切る
2. 作業・コミット（Conventional Commits 必須）
3. `develop` への PR を作成（squash merge）
4. CODEOWNERS レビュー 1 名 + 必須 CI 通過でマージ

### リリースフロー（release）

1. `develop` から `release/X.Y.Z` を切る
2. `release/X.Y.Z` 上でバージョン bump / CHANGELOG 確定のみ
3. `main` への PR を作成（merge commit）— **2 名レビュー必須**
4. マージ後に `vX.Y.Z` タグを付与
5. **同じ `release/X.Y.Z` を `develop` へも back-merge する（24h 以内）**

### hotfix フロー

1. `main` から `hotfix/X.Y.(Z+1)` を切る
2. バグ修正のみ実施、バージョン bump（patch のみ）
3. `main` への PR を作成（merge commit）— **2 名レビュー必須**
4. マージ後に `vX.Y.(Z+1)` タグを付与
5. **同じ `hotfix/X.Y.(Z+1)` を `develop` へも back-merge する（24h 以内）**

> **back-merge の重要性**: release/hotfix を `main` にマージした後、同ブランチを `develop` にも merge commit で戻さないと、次回リリースで `develop` が `main` より古い状態になり衝突します。CI の `back-merge-check` が 24h 以内の back-merge 未実施を検知し、担当者に Issue で通知します。

---

## コミット規約（Conventional Commits）

全コミットメッセージは [Conventional Commits](https://www.conventionalcommits.org/) に従います。PR タイトルが squash merge 時のコミットメッセージになるため、**PR タイトルも同規約に従う必要があります**（CI の `pr-title-check` で検証）。

### フォーマット

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### 使用可能な type

| type | 用途 |
|------|------|
| `feat` | 新機能 |
| `fix` | バグ修正 |
| `docs` | ドキュメントのみの変更 |
| `chore` | ビルド・ツール・設定変更（本番コードに影響なし） |
| `refactor` | リファクタリング（バグ修正・機能追加なし） |
| `test` | テストの追加・修正 |
| `ci` | CI/CD 設定変更 |
| `build` | ビルドシステム・依存関係変更 |
| `perf` | パフォーマンス改善 |

### Breaking Change

```
feat!: remove deprecated /api/v1/agents endpoint
# または
feat(room): new workflow API

BREAKING CHANGE: workflow schema v1 is no longer supported
```

---

## マージ戦略

| PR 種別 | マージ方法 | 理由 |
|--------|----------|------|
| `feature/*` → `develop` | **squash merge** | feature 内の作業コミットを 1 commit に集約。PR タイトルがコミットメッセージになる |
| `release/*` → `main` | **merge commit**（No fast-forward） | リリース分岐の履歴を `main` に残す |
| `release/*` → `develop` | **merge commit**（No fast-forward） | back-merge 痕跡を残す |
| `hotfix/*` → `main` | **merge commit**（No fast-forward） | 同上 |
| `hotfix/*` → `develop` | **merge commit**（No fast-forward） | 同上 |

> **rebase merge は使用禁止です。** GitHub リポジトリ設定で無効化されています。

---

## PR 規約

### PR ブランチ制限

- `main` への PR は `release/*` または `hotfix/*` からのみ許可（`branch-policy` CI で強制）
- `develop` への PR は `feature/*` / `release/*` / `hotfix/*` からのみ許可

### PR チェックリスト

- [ ] PR タイトルが Conventional Commits に従っている
- [ ] 関連する Issue 番号を本文に記載している（`Closes #123`）
- [ ] `CHANGELOG.md` の更新が必要な場合は更新済み
- [ ] `release/*` / `hotfix/*` → `main` PR の場合: **24h 以内に `develop` への back-merge PR を作成する**

### lock file の変更

`uv.lock` / `pnpm-lock.yaml` のみが変更されている PR には `deps-lockfile-only` ラベルを付与し、意図的な更新である旨を本文に記載してください。

---

## 開発環境セットアップ

### 必要なツール

- [uv](https://docs.astral.sh/uv/)（Python 3.12+ 管理）
- [Node.js](https://nodejs.org/) 20 LTS 以上
- [pnpm](https://pnpm.io/) 9 以上
- [just](https://just.systems/)（タスクランナー）
- [lefthook](https://github.com/evilmartians/lefthook)（Git フック）

これらは `scripts/setup.sh` / `scripts/setup.ps1` が SHA256 検証つきで自動導入します。詳細は [`docs/features/dev-workflow/`](docs/features/dev-workflow/) の設計書一式を参照してください。

### セットアップ（1 ステップ）

```bash
# Unix
bash scripts/setup.sh

# Windows（PowerShell 7+ 必須）
pwsh scripts/setup.ps1
```

このスクリプトは冪等です。2 回目以降は既存ツールをスキップします。

### docker-compose 起動手順（推奨）

`docker compose up` 一発で backend + frontend を同時起動できます。

**前提**: [Docker Desktop](https://www.docker.com/products/docker-desktop/) または [OrbStack](https://orbstack.dev/)（Mac 推奨）が起動済みであること。

```bash
# 1. 環境変数ファイルを初期化（初回のみ）
just env-init

# 2. コンテナを起動（初回はイメージビルドを含む）
just up

# 3. バックエンドのヘルスを確認: {"status":"ok"} が返れば成功
just health

# 4. ブラウザで UI を開く
open http://localhost:5173  # Mac
# または手動で http://localhost:5173 を開く

# 5. 停止
just down

# データ（SQLite DB）ごと削除する場合
just down-v
```

> **⚠️ Mac 環境の注意**: Docker Desktop for Mac では SQLite WAL モードの bind mount に既知問題があります。`docker-compose.override.yml` の `bakufu-data` volume を bind mount に変更しないでください。named volume（既定値）を必ず維持してください。詳細は [`docs/design/tech-stack.md`](docs/design/tech-stack.md) §SQLite WAL × Docker bind mount 警告 を参照してください。

### ネイティブ起動（docker なし）

docker なしでのローカル起動も継続サポートしています。

```bash
# backend（uv 必須）
uv run python -m bakufu.main

# frontend（pnpm 必須）
pnpm --filter @bakufu/frontend dev
```

### `just` レシピ一覧

| レシピ | 用途 |
|------|------|
| `just` | レシピ一覧表示（`just --list` を実行） |
| `just env-init` | `.env.example` → `.env` をコピー（初回のみ、OS 横断対応） |
| `just up` | docker compose でコンテナ起動（ビルド含む） |
| `just down` | コンテナ停止 |
| `just down-v` | コンテナ停止 + volumes 削除（データも消える） |
| `just logs` | コンテナログをフォロー |
| `just health` | `GET http://localhost:8000/health` でバックエンド起動確認 |
| `just fmt-check` | Python (ruff) + TypeScript (biome) の format 検査 |
| `just fmt` | format 自動修正 |
| `just lint` | Python (ruff) + TypeScript (biome) の lint |
| `just typecheck` | Python (pyright) + TypeScript (tsc --noEmit) |
| `just test` | backend (pytest) + frontend (vitest) を順次実行 |
| `just test-backend` | backend のみ（pytest） |
| `just test-frontend` | frontend のみ（vitest） |
| `just audit` | 依存脆弱性監査（pip-audit + pnpm audit） |
| `just audit-secrets` | staged 差分の secret 検査（gitleaks） |
| `just audit-pin-sync` | setup.sh / setup.ps1 のピン定数同期検査 |
| `just check-all` | 全品質ゲートを順次実行（最終確認用） |
| `just commit-msg-check FILE` | コミットメッセージ検証（convco） |
| `just commit-msg-no-ai-footer FILE` | AI 生成フッター検出 |

> **`--no-verify` の使用禁止**: pre-commit / pre-push / commit-msg フックを `--no-verify` で意図的にバイパスする運用は規約で原則禁止です。やむを得ない場合は PR 本文に理由を明記してください。CI の同等ジョブで再検査され、PR チェックが赤になります。

---

## AI 生成フッターの禁止

bakufu のコミットメッセージに、AI エージェント（Claude Code 等）が自動挿入する**生成元識別フッター（trailer）を含めることを禁止**します。理由:

- コミット履歴はプロジェクトの真実源であり、著者情報は Git の `author` / `committer` フィールドで表現される。trailer による生成元識別は重複・冗長
- 将来的な企業利用におけるコード所有権明確化要求と相容れない
- 同一 OSS（shikomi 等）と方針を統一

### commit-msg フックで遮断する 3 パターン（case-insensitive）

| # | パターン（拡張正規表現） | 検出対象例 |
|---|---------------------|----------|
| P1 | `🤖.*Generated with.*Claude` | `🤖 Generated with [Claude Code](https://claude.com/claude-code)` |
| P2 | `Co-Authored-By:.*@anthropic\.com` | `Co-Authored-By: Claude <noreply@anthropic.com>` |
| P3 | `Co-Authored-By:.*\bClaude\b` | `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` |

これら 3 パターンのいずれかを検出すると、commit-msg フックが exit 非 0 でコミットを中止します。`Claude Shannon` 等を本文（body 位置）で引用する正規のコミットメッセージは、P3 の `Co-Authored-By:` 接頭辞必須制約により誤検知しません。

### Agent-C ペルソナ向け指示

Claude Code 等のエージェントは既定で当該 trailer を自動挿入する実装になっています。**bakufu リポへのコミット時は明示的に当該 trailer を抑止する設定で動作させてください**。`--no-verify` でローカルフックをバイパスした場合は、PR レビュー時に人間レビュワーまたは `@kkm-horikawa` が目視検知して差し戻します。

---

## Secret 混入時の緊急対応

push 済みコミットに secret（API キー / OAuth トークン / 秘密鍵等）の混入が判明した場合、以下の手順を**この順序**で実行してください。

### 手順

1. **(a) 該当キーを発行元で即 revoke** — GitHub PAT・AWS アクセスキー・OAuth Client Secret 等は発行元のコンソールで即座に失効させる。GitHub 側 secret scanning が検知している場合はそちらの alert からも revoke 可能
2. **(b) 履歴書換えと force-push** — `git filter-repo --path <secret-file> --invert-paths` で該当ファイルを履歴から完全除去し、対象 feature ブランチにのみ force-push する
   - **`main` / `develop` への force-push は禁止です**（GitFlow 規律）。release 前の feature ブランチ限定で実施
   - `git filter-branch` は非推奨（`git filter-repo` を使用）
3. **(c) GitHub 側の事後対応** — GitHub Support に cache purge を依頼（force-push 後も CDN にキャッシュが残る可能性があるため）し、secret scanning alert を `revoked` または `false_positive` で resolve する

### 補足

- 上記手順を踏んでも、push 済み履歴は他のクローン側に残留している可能性がある（GitHub 公式の説明: 完全除去は困難）。**revoke が最優先**
- 混入経路が pre-commit フックの bypass（`--no-verify`）であった場合、当該開発者にレビューでフィードバックする
- secret を含むファイルが復活しないよう、`.gitignore` の追加と CI の `audit-secrets` ジョブ強化で再発防止する

---

## コーディング規約

- **Clean Architecture / SOLID**: トップダウンに読めるコード。責務はクラス・モジュールに閉じる。依存の方向は一方向
- **Domain-Driven Design**: 業務概念をそのままクラス・インターフェースで表現する。技術的詳細は外に漏らさない
- **Fail Fast**: 不正な入力・状態は早期に失敗させる。エラーを握り潰さない
- **型は明示**: Python は `pyright` で strict、TypeScript は `tsc --noEmit` で strict。`any` / `Any` / 型アサーションは設計の敗北
- **エラーハンドリング**: 境界（ユーザー入力・外部 API）にのみ。内部コードのエラーは例外を伝播させる
- **コメント**: 「なぜそうするか」だけ書く。「何をするか」はコードが語る
- **AI 生成フッター禁止**: §AI 生成フッターの禁止 を参照

詳細は Vモデル工程ごとの設計書群（[`docs/analysis/`](docs/analysis/) / [`docs/requirements/`](docs/requirements/) / [`docs/design/`](docs/design/) / [`docs/acceptance-tests/`](docs/acceptance-tests/)）、各 feature の設計書（[`docs/features/`](docs/features/)）、開発プロセスガイド（[`docs/_template/process.md`](docs/_template/process.md)）を参照してください。新規 feature の起票は [`docs/_template/`](docs/_template/) のテンプレートをコピーします。
