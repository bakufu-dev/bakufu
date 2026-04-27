# 要件定義書

<!-- feature単位で1ファイル。新規featureならテンプレートコピー、既存featureなら既存ファイルをREAD→EDIT -->
<!-- 配置先: docs/features/dev-workflow/requirements.md -->

## 機能要件

### REQ-DW-001: フックツール導入（lefthook）

| 項目 | 内容 |
|------|------|
| 入力 | `lefthook install` コマンド実行、または setup スクリプト経由の呼び出し |
| 処理 | `lefthook.yml` を読み、`.git/hooks/{pre-commit,pre-push,commit-msg}` を生成・上書き |
| 出力 | `.git/hooks/` 以下に lefthook が管理するラッパスクリプトが配置され、以後の `git` 操作で自動発火 |
| エラー時 | lefthook バイナリ未検出 → 「`bash scripts/setup.sh`（Unix）または `pwsh scripts/setup.ps1`（Windows）を実行して SHA256 検証つきで lefthook を導入してください」のヒントつき exit 非 0。**lefthook は GitHub Releases バイナリ + SHA256 検証経由でのみ導入**（REQ-DW-015、確定 A） |

### REQ-DW-002: pre-commit フック

| 項目 | 内容 |
|------|------|
| 入力 | `git commit` 実行（`--no-verify` 非指定） |
| 処理 | `just fmt-check` / `just lint` / `just typecheck` / `just audit-secrets` を **並列**実行。staged ファイルのみを対象とするのではなく、**ワークツリー全体**に対し実行（バックエンドとフロントエンドの設定は ruff/biome/pyright/tsc 側で対象範囲を制御） |
| 出力 | 全チェック成功: コミット続行 / いずれか失敗: コミット中止、失敗箇所と復旧コマンド（例: `just fmt`）を stderr 表示 |
| エラー時 | exit 非 0 でコミット中止。MSG-DW-001 / MSG-DW-002 / MSG-DW-014 / MSG-DW-010 を表示 |

### REQ-DW-003: pre-push フック

| 項目 | 内容 |
|------|------|
| 入力 | `git push` 実行（`--no-verify` 非指定） |
| 処理 | `just test` を実行（`pytest` + `pnpm vitest run`） |
| 出力 | 成功: push 続行 / 失敗: push 中止、失敗テスト名と復旧手順（`just test` で再現）を stderr 表示 |
| エラー時 | exit 非 0 で push 中止。MSG-DW-003 を表示 |

### REQ-DW-004: commit-msg フック

| 項目 | 内容 |
|------|------|
| 入力 | コミットメッセージファイル（`.git/COMMIT_EDITMSG`） |
| 処理 | `convco check --from-stdin --strip < {1}` でメッセージを Conventional Commits 規約に照合（確定 E）。merge / revert / fixup コミットは convco 側のデフォルト挙動で素通り |
| 出力 | 適合: コミット続行 / 不適合: コミット中止、許可される type 一覧（CONTRIBUTING.md §コミット規約参照）を stderr 表示 |
| エラー時 | exit 非 0。MSG-DW-004 を表示 |

### REQ-DW-005: タスクランナー導入（just）

| 項目 | 内容 |
|------|------|
| 入力 | `just <recipe>` または `just --list` |
| 処理 | `justfile` を読み、該当レシピのコマンドを実行。レシピ内からは `uv run ruff ...` / `pnpm biome ...` / `pytest` / `vitest` 等を直接呼ぶ |
| 出力 | レシピ実行結果。`just --list` は全レシピを 1 行コメントつきで列挙 |
| エラー時 | レシピ未定義: just が usage を表示し exit 非 0 |

### REQ-DW-006: CI との単一実行経路化

| 項目 | 内容 |
|------|------|
| 入力 | GitHub Actions workflow job のステップ `run:` |
| 処理 | `lint.yml` / `typecheck.yml` / `test-backend.yml` / `test-frontend.yml` / `audit.yml` の **5 本すべての直接的なツール呼び出しを `just <recipe>` に置換**。各 workflow は最初のステップに「`bash scripts/setup.sh --tools-only`」を追加（`--tools-only` は `lefthook install` を skip して開発者ツールのみ配置するモード、設計時凍結）|
| 出力 | ローカルフック / 手動 `just <recipe>` / CI が同一レシピ呼び出し経路で実行される状態 |
| エラー時 | `just` バイナリ未インストール: workflow ステップが fail（CI セーフティネット） |

### REQ-DW-007: setup スクリプト（Unix, `scripts/setup.sh`）

| 項目 | 内容 |
|------|------|
| 入力 | `bash scripts/setup.sh [--tools-only]` 実行（引数任意） |
| 処理 | 1. リポジトリルート検査（`.git/` 存在）→ 非リポジトリなら MSG-DW-009 で Fail Fast 2. **言語ランタイム検査**: `python3 --version`（3.12+）/ `node --version`（20+）/ `git --version` を確認 → 未検出なら MSG-DW-008 で Fail Fast 3. **GitHub Releases バイナリ**（`uv` / `just` / `convco` / `lefthook` / `gitleaks`）を SHA256 検証つきで `~/.local/bin/` に配置（既にあれば `--version` で存在確認のみ、冪等）4. **Python ツール**（`ruff` / `pyright` / `pip-audit`）を `uv tool install` で導入（既にあればスキップ）5. **Node ツール**: `corepack enable` で `pnpm` 有効化、`pnpm install -g @biomejs/biome osv-scanner` で `biome` / `osv-scanner` 導入 6. **`--tools-only` 指定なし時のみ** `lefthook install` を実行 7. 成功ログ（MSG-DW-005）表示 |
| 出力 | exit 0 で成功、標準出力に各ステップの完了メッセージ |
| エラー時 | 途中失敗で即 exit（`set -euo pipefail`）、失敗箇所を stderr に表示 |

### REQ-DW-008: setup スクリプト（Windows, `scripts/setup.ps1`）

| 項目 | 内容 |
|------|------|
| 入力 | `pwsh scripts/setup.ps1 [-ToolsOnly]` 実行（引数任意）。**PowerShell 7+ 必須**（PowerShell 5.1 非対応） |
| 処理 | 0. **`$PSVersionTable.PSVersion.Major -lt 7` なら MSG-DW-011 で即 Fail Fast**（REQ-DW-014）1〜7. REQ-DW-007 と同一ロジックを PowerShell で表現（`command -v` は `Get-Command ... -ErrorAction SilentlyContinue`、`~/.local/bin/` は `$env:USERPROFILE\.local\bin\`）。`$ErrorActionPreference = 'Stop'` + `Set-StrictMode -Version Latest` で Fail Fast |
| 出力 | REQ-DW-007 と同様 |
| エラー時 | REQ-DW-007 と同様 |

### REQ-DW-009: 冪等性

| 項目 | 内容 |
|------|------|
| 入力 | setup スクリプトの連続再実行 |
| 処理 | 各ツールについて `command -v <tool>` / `Get-Command <tool>` で存在確認し、存在時は導入をスキップ。`lefthook install` は冪等（既存 `.git/hooks/` を上書き） |
| 出力 | 2 回目以降は「既にインストール済み」ログ（MSG-DW-006）を出して 0 秒で完了 |
| エラー時 | 初回エラーは通常通り Fail Fast |

### REQ-DW-010: README / CONTRIBUTING 更新

| 項目 | 内容 |
|------|------|
| 入力 | 設計確定と Sub-issue C 完了後の PR |
| 処理 | README.md §ビルド方法、CONTRIBUTING.md §開発環境セットアップを更新。1 コマンドで setup 完了することを冒頭で明示 |
| 出力 | 両ファイルに setup 手順、利用可能な `just` レシピ、`--no-verify` 禁止ポリシー、AI 生成フッター禁止ポリシーが追記された状態 |
| エラー時 | 該当なし（ドキュメント変更のみ） |

### REQ-DW-011: `--no-verify` バイパス検知

| 項目 | 内容 |
|------|------|
| 入力 | GitHub への push（`--no-verify` の有無に関わらず） |
| 処理 | CI の `lint` / `typecheck` / `test-backend` / `test-frontend` / `audit` が同一レシピを再実行 |
| 出力 | push 後の CI ランで結果が可視化される。規約違反は PR レビューで却下 |
| エラー時 | CI ジョブが非 0 終了。PR マージ不可 |

### REQ-DW-012: フック失敗時のメッセージ品質

| 項目 | 内容 |
|------|------|
| 入力 | pre-commit / pre-push / commit-msg のいずれかの失敗 |
| 処理 | lefthook の `fail_text` フィールドで、`[FAIL] <原因要約>` と `次のコマンド: just <recipe>` の **2 行固定構造**を静的文字列として定義 |
| 出力 | stderr に最終 2 行が固定構造で出力される |
| エラー時 | 該当なし（メッセージ表示自体は exit コードに影響しない） |

### REQ-DW-013: Secret 混入検知 pre-commit フック

| 項目 | 内容 |
|------|------|
| 入力 | `git commit` 実行時の staged 差分 |
| 処理 | `gitleaks protect --staged --no-banner` で staged 差分を汎用 secret パターンでスキャン |
| 出力 | pass: コミット続行 / 検出: コミット中止、検出箇所（ファイル・行番号）を stderr 表示 |
| エラー時 | exit 非 0。MSG-DW-010 を表示 |

### REQ-DW-014: PowerShell 7+ 必須化

| 項目 | 内容 |
|------|------|
| 入力 | `setup.ps1` 起動時の `$PSVersionTable.PSVersion` |
| 処理 | `Major -lt 7` を検出したら Fail Fast。導入方法（`winget install Microsoft.PowerShell`）を提示 |
| 出力 | 条件不一致: exit 非 0、MSG-DW-011 表示 / 条件一致: 後続ステップ続行 |
| エラー時 | 該当なし（Fail Fast 自体がエラー経路） |

### REQ-DW-015: 開発ツールバイナリの完全性検証

| 項目 | 内容 |
|------|------|
| 入力 | setup スクリプト実行時（当該ツールが未インストールの場合） |
| 処理 | 1. setup スクリプトにピンされた `<TOOL>_VERSION` と各プラットフォームの `SHA256` 定数を参照（対象: `uv` / `just` / `convco` / `lefthook` / `gitleaks` の 5 ツール）2. `curl -sSfL` / `Invoke-WebRequest` で tar.gz / zip をダウンロード 3. `sha256sum` / `Get-FileHash` で実測値を取得し、ピン値と文字列一致で照合 4. 不一致ならダウンロード成果物を削除して MSG-DW-012 で Fail Fast 5. 一致なら展開、バイナリを `~/.local/bin/` または `$env:USERPROFILE\.local\bin\` に配置 |
| 出力 | 検証成功: 配置完了 / 失敗: exit 非 0 |
| エラー時 | MSG-DW-012 表示、ダウンロード済み一時ファイルを削除 |

### REQ-DW-016: 開発ワークフロー設定ファイルの CODEOWNERS 保護

| 項目 | 内容 |
|------|------|
| 入力 | `.github/CODEOWNERS` への追記 PR（本 feature の Sub-issue B で実施） |
| 処理 | `/lefthook.yml` / `/justfile` / `/scripts/setup.sh` / `/scripts/setup.ps1` / `/scripts/ci/` を CODEOWNERS に登録。PR レビュー要求が GitHub 側で自動付与される |
| 出力 | 該当ファイルを含む PR でオーナーのレビュー要求が生成される |
| エラー時 | 該当なし（PR レビュー要求が付与されない場合は CODEOWNERS 構文エラー → PR 側で検知） |

### REQ-DW-017: Git 履歴からの secret リムーブ運用

| 項目 | 内容 |
|------|------|
| 入力 | push 済みコミットに secret 混入が判明した場合 |
| 処理 | CONTRIBUTING.md の該当節で 3 段階手順を規定: (a) **即 revoke**（該当キーを発行元で失効）(b) `git filter-repo --path <file> --invert-paths` で履歴から該当ファイルを除去し force-push を対象ブランチに対してのみ実施（`main` / `develop` は対象外、release 前の feature ブランチ限定）(c) GitHub Support に cache purge 依頼、secret scanning の alert を resolve |
| 出力 | CONTRIBUTING.md §Secret 混入時の緊急対応 に手順が明文化された状態 |
| エラー時 | 該当なし（運用手順の文書化のみ） |

### REQ-DW-018: AI 生成フッターのコミットメッセージ混入禁止

| 項目 | 内容 |
|------|------|
| 入力 | commit-msg フックから渡されるコミットメッセージファイル（`.git/COMMIT_EDITMSG` 等） |
| 処理 | `just commit-msg-no-ai-footer {1}` が case-insensitive な拡張正規表現マッチで以下 3 パターンを順に検査（詳細設計書 §確定パターン）: (a) `🤖.*Generated with.*Claude` (b) `Co-Authored-By:.*@anthropic\.com` (c) `Co-Authored-By:.*\bClaude\b`。いずれか 1 つでもヒットすれば exit 非 0、非ヒットなら exit 0 |
| 出力 | 非ヒット: コミット続行 / ヒット: コミット中止、MSG-DW-013 を stderr 表示 |
| エラー時 | exit 非 0。lefthook `fail_text` で MSG-DW-013 を表示 |

**並列実行の契約**: `commit-msg` フックでは既存の `convco` コマンドと本 `no-ai-footer` コマンドを lefthook `parallel: true` で並列実行する。双方とも短時間で完了する grep 相当の軽量検査のため、所要時間は 2 検査でも数百ミリ秒以内。

**CI 側での再検知（YAGNI）**: `--no-verify` バイパス対策として、push 後の PR において `pr-title-check` ワークフローは PR タイトルの Conventional Commits 準拠のみ検査しており、各コミットの message 本文の trailer までは検査しない。squash merge を採用している bakufu では PR タイトルがマージコミットのメッセージになるため、GitHub UI の squash dialog で自動挿入される Co-Authored-By 集約が問題となる可能性がある。本 feature のスコープとしては**ローカル commit-msg フックでの水際対応**を主とし、CI 側での PR body 検査は YAGNI として後続 Issue で扱う（実運用で漏れが発覚した時点で対応）。

## 画面・CLI仕様

### `just` レシピ一覧（初期定義）

| レシピ名 | 概要 | 対応する CI 相当 |
|---------|------|----------------|
| `just` | 引数なしで `just --list` を実行する default レシピ | — |
| `just fmt-check` | `uv run ruff format --check .` + `pnpm biome format .` を並列 | `lint.yml` step |
| `just fmt` | `uv run ruff format .` + `pnpm biome format --write .`（自動修正） | — |
| `just lint` | `uv run ruff check .` + `pnpm biome check .` | `lint.yml` step |
| `just typecheck` | `uv run pyright` + `pnpm tsc --noEmit` を並列 | `typecheck.yml` step |
| `just test` | `just test-backend` → `just test-frontend` を順次（失敗時に途中終了） | `test-backend.yml` + `test-frontend.yml` |
| `just test-backend` | `uv run pytest backend/` | `test-backend.yml` |
| `just test-frontend` | `pnpm --dir frontend vitest run` | `test-frontend.yml` |
| `just audit` | `uv run pip-audit` + `pnpm dlx osv-scanner --recursive .` | `audit.yml` |
| `just audit-secrets` | `gitleaks protect --staged --no-banner` | pre-commit 経由（REQ-DW-013） |
| `just audit-pin-sync` | `bash scripts/ci/audit-pin-sync.sh`（`setup.sh` と `setup.ps1` のピン定数同期検査、詳細設計書 §ピン同期の担保） | `audit.yml` |
| `just check-all` | `fmt-check` → `lint` → `typecheck` → `test` → `audit` → `audit-secrets` を順次実行（最終確認用） | 全ワークフロー相当 |
| `just commit-msg-check FILE` | `convco check --from-stdin --strip < {{FILE}}` を実行（確定 E） | — |
| `just commit-msg-no-ai-footer FILE` | case-insensitive `grep -iE` で 3 パターン（§REQ-DW-018）を検査し、ヒットしたら exit 1。POSIX 互換（Windows でも Git for Windows の `bash.exe` 経由で動作） | — |

### setup スクリプトの CLI

| スクリプト | 呼び出し | 引数 | 出力 |
|----------|---------|-----|------|
| `scripts/setup.sh` | `bash scripts/setup.sh [--tools-only]` | `--tools-only`（任意、`lefthook install` をスキップ） | インストール進捗ログ、最終行に「Setup complete.」 |
| `scripts/setup.ps1` | `pwsh scripts/setup.ps1 [-ToolsOnly]` | `-ToolsOnly`（任意） | 同上 |

### `lefthook.yml` の CLI 契約

本書では設定構造の外形のみ記載（詳細設計書で詳述）。ユーザ可視の CLI は無く、`git commit` / `git push` から暗黙に発火する。

## API仕様

該当なし — 理由: 本 feature は開発者ツールチェーンの整備であり、ランタイム API を提供しない。

## データモデル

| エンティティ | 属性 | 型 | 制約 | 関連 |
|-------------|------|---|------|------|
| `lefthook.yml` | `pre-commit.commands` | map<string, {run: string, fail_text: string}> | 各コマンドの `run` は `just <recipe>` を呼ぶ | `justfile` のレシピ名と一致 |
| `lefthook.yml` | `pre-commit.parallel` | bool | `true` を採用 | — |
| `lefthook.yml` | `pre-push.commands` | 同上 | `fail_text` 必須 | 同上 |
| `lefthook.yml` | `commit-msg.commands` | 同上 | 引数に `{1}` でメッセージファイルパスを受ける | `justfile` の `commit-msg-check` / `commit-msg-no-ai-footer` |
| `lefthook.yml` | `commit-msg.parallel` | bool | `true` を採用 | — |
| `justfile` | 先頭の `set` 宣言 | 平文 | `set dotenv-load := false`, `set windows-shell := ["pwsh", "-Cu", "-c"]` | — |
| `justfile` | 各 recipe | 名前・引数・本文 | 本文 1 行あたり 1 コマンド。複数行は `\` 継続ではなく recipe 分割で表現 | `lefthook.yml` / `.github/workflows/*.yml` が参照 |
| `scripts/setup.sh` | シェバン | 文字列 | `#!/usr/bin/env bash` | — |
| `scripts/setup.sh` | 冒頭 | `set -euo pipefail` | Fail Fast 必須 | — |
| `scripts/setup.ps1` | 冒頭 | `$ErrorActionPreference = 'Stop'` + `Set-StrictMode -Version Latest` | Fail Fast 必須 | — |

## ユーザー向けメッセージ一覧

| ID | 種別 | メッセージ（要旨。正確な文言は詳細設計で確定） | 表示条件 |
|----|------|----------------------------------------|---------|
| MSG-DW-001 | エラー | `[FAIL] ruff / biome の format 違反を検出しました。` / `次のコマンド: just fmt` | pre-commit で fmt-check 失敗 |
| MSG-DW-002 | エラー | `[FAIL] ruff / biome の lint 違反を検出しました。` / `次のコマンド: just lint`（自動修正可能なものは `pnpm biome check --write .` / `uv run ruff check --fix .`）| pre-commit で lint 失敗 |
| MSG-DW-003 | エラー | `[FAIL] pytest / vitest に失敗しました。` / `次のコマンド: just test` | pre-push で test 失敗 |
| MSG-DW-004 | エラー | `[FAIL] コミットメッセージが Conventional Commits 1.0 に準拠していません。` / `規約: CONTRIBUTING.md §コミット規約 または https://www.conventionalcommits.org/ja/v1.0.0/` | commit-msg で convco 失敗 |
| MSG-DW-005 | 成功 | `[OK] Setup complete. Git フックが有効化されました。` | setup スクリプト正常終了 |
| MSG-DW-006 | 情報 | `[SKIP] {tool} は既にインストール済みです。` / `バージョン: {version}` | setup 冪等実行時 |
| MSG-DW-007 | 警告 | `[WARN] --no-verify の使用は規約で原則禁止です。PR 本文に理由を明記してください。CI が同一チェックを再実行します。` | CONTRIBUTING.md に静的記載（動的表示ではない） |
| MSG-DW-008 | エラー | `[FAIL] Python 3.12+ または Node 20+ が未検出です。` / `次のコマンド: README.md §動作環境のセットアップ手順を参照してください。` | setup で `python3 --version` / `node --version` が要件未満 |
| MSG-DW-009 | エラー | `[FAIL] .git/ ディレクトリが見つかりません。リポジトリルートで実行してください。` / `現在のディレクトリ: {cwd}` | setup がリポジトリルート外で起動された場合、または lefthook install 失敗時 |
| MSG-DW-010 | エラー | `[FAIL] secret の混入が検出されました。該当行を除去後、git add を再実行してください。` / `既に push 済みの場合: CONTRIBUTING.md §Secret 混入時の緊急対応` | pre-commit の secret 検知で陽性 |
| MSG-DW-011 | エラー | `[FAIL] PowerShell 7 以上が必要です（検出: {version}）。` / `次のコマンド: winget install Microsoft.PowerShell` | `setup.ps1` が PowerShell 5.1 以下で起動 |
| MSG-DW-012 | エラー | `[FAIL] {tool} バイナリの SHA256 検証に失敗しました。サプライチェーン改ざんの可能性があります。` / `次のコマンド: 一時ファイルを削除後、ネットワーク状況を確認して再実行。繰り返し失敗する場合は Issue で報告。` | `setup.{sh,ps1}` のバイナリダウンロード時、SHA256 不一致 |
| MSG-DW-013 | エラー | `[FAIL] コミットメッセージに AI 生成フッターが含まれています（🤖 Generated with Claude Code / Co-Authored-By: Claude 等）。` / `次のコマンド: 該当行を削除して再コミット。許可されない trailer のポリシーは CONTRIBUTING.md §AI 生成フッターの禁止 を参照。` | commit-msg フックで `just commit-msg-no-ai-footer` がパターン検出 |
| MSG-DW-014 | エラー | `[FAIL] pyright / tsc の型エラーを検出しました。` / `次のコマンド: just typecheck` | pre-commit で typecheck 失敗 |

## 依存関係

| 区分 | 依存 | バージョン方針 | 導入経路 | 備考 |
|-----|------|-------------|---------|------|
| 開発ツール | `just` | **GitHub Releases バイナリ + SHA256 検証**。`<TOOL>_VERSION` / `<TOOL>_SHA256_*` 定数で setup スクリプトにピン | ローカル開発者環境 / CI ランナー | Rust 製、Windows ネイティブ対応、`just --list` 対応 |
| 開発ツール | `convco` | 同上 | 同上 | Rust 製、Conventional Commits 1.0 公式準拠、`convco check --from-stdin --strip` |
| 開発ツール | `lefthook` | 同上 | 同上 | Go 製、並列実行、YAML 設定。Evil Martians 公式配布物 |
| 開発ツール | `gitleaks` | 同上 | 同上 | Go 製、staged diff スキャン対応、正規表現ベースの汎用 secret 検知 |
| 開発ツール | `uv` | 同上 | 同上 | Astral 製、Python パッケージ管理 + ツールインストール |
| Python ツール | `ruff` | `uv tool install ruff`。バージョンは pyproject.toml の dev dependency でピン | uv 経由（uv 自体は SHA256 検証で導入） | Astral 製、Python lint + format |
| Python ツール | `pyright` | 同上 | 同上 | Microsoft 製、Python 型チェック |
| Python ツール | `pip-audit` | 同上 | 同上 | PyPA 公式、OSV/PyPI advisory データベース照合 |
| Node ツール | `pnpm` | corepack 経由（Node 20+ 同梱）または GitHub Releases バイナリ | corepack `enable` | Node パッケージ管理 |
| Node ツール | `biome` | `pnpm install -g @biomejs/biome`。バージョンは `package.json` の dev dependency でピン | pnpm 経由 | Rust 製、TS lint + format 統合 |
| Node ツール | `osv-scanner` | `pnpm install -g osv-scanner` または GitHub Releases バイナリ | pnpm / バイナリ | Google 製、OSV データベース横断スキャナ |
| Python ランタイム | `python` | 3.12+ | 各 OS パッケージマネージャ / pyenv | 既存（README 動作環境） |
| Node ランタイム | `node` | 20 LTS+ | 各 OS パッケージマネージャ / nvm / fnm | 既存（README 動作環境） |
| PowerShell（Windows） | 7.0+ | `winget install Microsoft.PowerShell` で導入 | Microsoft Store / winget | Win 10 21H2 初期環境の既定 PowerShell 5.1 は非対応（REQ-DW-014） |
| Git | Git 2.9+ | setup ガイドに明記 | 各 OS パッケージマネージャ | `core.hooksPath` は Git 2.9 で導入済み。本 feature は lefthook 経由なので `.git/hooks/` 既定パスを使う |
| Git for Windows（Windows） | 同梱 `bash.exe` | Git for Windows 導入時に自動同梱 | Git 公式インストーラ | `commit-msg-check` / `commit-msg-no-ai-footer` で POSIX shell が必要 |
| GitHub Actions | `actions/checkout@v4` | 既存利用 | 既存 | — |
| CONTRIBUTING / README | 既存 Markdown | — | — | §REQ-DW-010 で更新 |

**配布バイナリ（bakufu 本体）への影響**: 本 feature のツールは **すべて開発者ツールチェーンに閉じる**。`backend/` / `frontend/` の build artifact および `uv.lock` / `pnpm-lock.yaml` の本番依存には一切混入しない（dev dependency にのみ追加）。よってドメインモデル設計書 (`docs/architecture/domain-model.md`) とは独立な領域として扱う。
