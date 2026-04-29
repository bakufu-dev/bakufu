# 詳細設計書 — dev-workflow / domain

> feature: `dev-workflow` / sub-feature: `domain`
> 親 spec: [`../feature-spec.md`](../feature-spec.md) §9 受入基準 1〜13 / §10 Q-1〜Q-6
> 関連: [`basic-design.md`](basic-design.md) §モジュール契約

## 記述ルール（必ず守ること）

詳細設計に**疑似コード・サンプル実装（python/ts/go等の言語コードブロック）を書くな**。
ソースコードと二重管理になりメンテナンスコストしか生まない。

## クラス設計（詳細）

本 feature はランタイムクラスを持たないため、各設定ファイルの**構造契約**を詳細レベルで示す。各ファイルの実装（最終的な YAML / justfile / sh / ps1）は Sub-issue の実装 PR で書き、本設計書とは**構造契約と意図**のみで整合を取る。

### 設定ファイルの構造契約

```mermaid
classDiagram
    class Justfile {
        +set windows-shell
        +default: list
        +fmt-check() exit_code
        +fmt() exit_code
        +lint() exit_code
        +typecheck() exit_code
        +test() exit_code
        +test-backend() exit_code
        +test-frontend() exit_code
        +audit() exit_code
        +audit-secrets() exit_code
        +audit-pin-sync() exit_code
        +check-all() exit_code
        +commit-msg-check(file) exit_code
        +commit-msg-no-ai-footer(file) exit_code
    }
    class LefthookYml {
        +preCommitParallel
        +preCommit_fmtCheck
        +preCommit_lint
        +preCommit_typecheck
        +preCommit_auditSecrets
        +prePush_test
        +commitMsgParallel
        +commitMsg_convco
        +commitMsg_noAiFooter
    }
    class SetupSh {
        +shebang: #!/usr/bin/env bash
        +strict: set -euo pipefail
        +arg_parse: --tools-only
        +step_check_runtime() exit_code
        +step_install_uv() exit_code
        +step_install_just() exit_code
        +step_install_convco() exit_code
        +step_install_lefthook() exit_code
        +step_install_gitleaks() exit_code
        +step_uv_tool_install() exit_code
        +step_pnpm_install() exit_code
        +step_lefthook_install() exit_code
    }
    class SetupPs1 {
        +param: ToolsOnly
        +strict: ErrorActionPreference=Stop
        +strict: Set-StrictMode -Version Latest
        +step_check_powershell()
        +step_check_runtime()
        +step_install_uv()
        +step_install_just()
        +step_install_convco()
        +step_install_lefthook()
        +step_install_gitleaks()
        +step_uv_tool_install()
        +step_pnpm_install()
        +step_lefthook_install()
    }
    class WorkflowLintYml {
        +step_checkout
        +step_setup_tools_only
        +step_just_fmt_check
        +step_just_lint
    }
    class WorkflowTypecheckYml {
        +step_checkout
        +step_setup_tools_only
        +step_just_typecheck
    }
    class WorkflowTestBackendYml {
        +step_checkout
        +step_setup_tools_only
        +step_just_test_backend
    }
    class WorkflowTestFrontendYml {
        +step_checkout
        +step_setup_tools_only
        +step_just_test_frontend
    }
    class WorkflowAuditYml {
        +step_checkout
        +step_setup_tools_only
        +step_just_audit
        +step_just_audit_secrets
        +step_just_audit_pin_sync
    }

    LefthookYml ..> Justfile : run:
    WorkflowLintYml ..> Justfile : run:
    WorkflowTypecheckYml ..> Justfile : run:
    WorkflowTestBackendYml ..> Justfile : run:
    WorkflowTestFrontendYml ..> Justfile : run:
    WorkflowAuditYml ..> Justfile : run:
    SetupSh ..> LefthookYml : lefthook install
    SetupPs1 ..> LefthookYml : lefthook install
```

### 確定事項（先送り撤廃）

#### 確定 A: 全開発ツールバイナリを **GitHub Releases + SHA256 検証で統一導入**

shikomi（Rust 前提）は Rust 製ツールを `cargo install --locked`、Go 製を GitHub Releases バイナリで導入する 2 経路混在だった。bakufu は **Rust toolchain を前提としない**ため、`just` / `convco`（Rust 製）も GitHub Releases バイナリ経由で導入する。これにより:

- 経路を「GitHub Releases バイナリ + SHA256 検証」と「言語パッケージマネージャ（uv/pnpm）」の **2 種に集約**
- ピン管理対象の `<TOOL>_VERSION` / `<TOOL>_SHA256_*` 定数が **5 ツール × 5 プラットフォーム = 25 SHA256**（lefthook / gitleaks / just / convco / uv 各 5）
- Python ツール（ruff / pyright / pip-audit）は **`uv tool install`** で導入（uv 自体は SHA256 検証で導入済み）
- Node ツール（biome / osv-scanner）は **`pnpm install -g`**（pnpm は corepack 経由で Node 同梱、または GitHub Releases バイナリ）

設計時の根拠: bakufu の開発者は Python と Node のランタイムを既に持っているが、Rust toolchain の有無は不定。Rust 製ツールを cargo 経由で導入する設計は Rust 開発者にしか優しくない（Python+TS 開発者には別途 rustup を要求する破綻経路）。SHA256 検証つきバイナリ取得は OS / 言語に依存しない最小公倍数。

#### 確定 B: Windows の shell 選定 — **PowerShell 7+ 必須化**

`justfile` は `set windows-shell := ["pwsh", "-Cu", "-c"]` を宣言する。`powershell.exe`（5.1）フォールバックは**採用しない**。根拠は shikomi と同じ:

- 案 A（setup.ps1 で pwsh を強制導入）は権限昇格要求・winget 非搭載環境での失敗経路で導線破綻
- 案 C（`just` 側で `powershell.exe` フォールバック）は Windows のみ振る舞い差分を抱え、`pwsh` と 5.1 の構文互換性差で潜在的バグ源
- 案 B 採用: `setup.ps1` 冒頭の PowerShell バージョン検査で Fail Fast + winget 導入案内（MSG-DW-011）

検出: `$PSVersionTable.PSVersion.Major -lt 7` → exit 非 0。導入コマンド `winget install Microsoft.PowerShell` を stderr に 1 行提示。

出典: Microsoft Learn "Installing PowerShell on Windows" https://learn.microsoft.com/powershell/scripting/install/installing-powershell-on-windows

#### 確定 C: テストの粒度 — **backend / frontend 分離 + 統合**

bakufu はモノレポ（backend = Python / frontend = TypeScript）。CI ジョブも分離する。`just test` は両者を順次実行（失敗時に途中終了）し、ローカル開発者が「全部回す」用途に使う。CI は `test-backend.yml` / `test-frontend.yml` を独立ジョブにすることで:

- **並列 CI 実行で高速化**
- **片側の壊れ方が他方に伝播しない**（フロントだけ壊れたとき、バックエンドジョブは緑が維持される）

レシピ:
- `just test`: `just test-backend` → `just test-frontend`（順次、失敗時途中終了）
- `just test-backend`: `uv run pytest backend/`
- `just test-frontend`: `pnpm --dir frontend vitest run`

将来 e2e テストが必要になったら `just test-e2e` を追加（YAGNI、Sub-issue で対応）。

#### 確定 D: secret 検知 — **gitleaks 単独**（shikomi の `audit-secret-paths.sh` は不採用）

shikomi 固有の secret 経路契約（TC-CI-012〜015）に対応する独自スクリプトは bakufu には存在しないため、**`gitleaks protect --staged --no-banner` 単独**で pre-commit に組み込む。bakufu 固有の secret 経路契約（例: 外部レビューゲート署名の非ログ出力、Agent CLI セッション ID の漏洩防止）が必要になった時点で `scripts/ci/audit-secret-paths.sh` を新設し、`just audit-secrets` レシピから引き回す（YAGNI）。

#### 確定 E: `convco` の commit-msg 呼び出し CLI — **`convco check --from-stdin --strip`**

shikomi の検証で確定した内容を bakufu でも踏襲する。convco には `check-message` というサブコマンドは存在せず、公式が提供するのは `convco check` の `--from-stdin` / `--strip` フラグ:

- `--from-stdin`: 単一のコミットメッセージを stdin から読み、Conventional Commits 1.0 準拠を検証
- `--strip`: 先頭が `#` のコメント行と空白を除去（`git commit --cleanup=strip` 相当、COMMIT_EDITMSG がコメント付きでも正しく検証できる）
- 検証失敗時は非 0 で exit、fail_text で MSG-DW-004 を出力

レシピ定義: `just commit-msg-check {{FILE}}` → 本体は `convco check --from-stdin --strip < {{FILE}}`。`set windows-shell := ["pwsh", "-Cu", "-c"]` 環境で `<` が PowerShell の ParserError になるため、shebang bash レシピを使い Git for Windows の `bash.exe` に閉じる。

出典: `convco check --help`（v0.6.x）の Options セクション https://github.com/convco/convco

### 設計判断の補足

#### なぜ `justfile` をルート直下に置くか

- `just` は実行ディレクトリから親方向へ `justfile` を探索する。リポジトリルートに置くことで、サブディレクトリ（`backend/` / `frontend/`）からも `just <recipe>` を呼べる
- pyproject.toml の `[tool.uv]` script や package.json の `scripts` に分散させると、フロント・バックを横断するコマンドが書けない（`just check-all` のような統合レシピが筋）

#### なぜ `set windows-shell := ["pwsh", "-Cu", "-c"]` を宣言するか

- `just` のデフォルトは Windows で `sh` を探しに行く。Git Bash のみ導入環境での振る舞いに差が出ることを避けるため `pwsh`（PowerShell 7+）を明示する
- 確定 B の通り `powershell.exe`（5.1）フォールバックは採用しない

#### なぜ `lefthook.yml` で `parallel: true` を `pre-commit` に設定するか

- `fmt-check` / `lint` / `typecheck` / `audit-secrets` は独立かつ並列化可能
- lefthook のデフォルトは並列非実行。明示宣言で体感時間を短縮
- `pre-push` の `test` は単一レシピなので `parallel` 指定不要

#### なぜ `fail_text` を lefthook 側で持ち、justfile 側で持たないか

- `justfile` は CI からも呼ばれる。CI で fmt 違反を「`just fmt` で修正しろ」と表示するのは文脈ミスマッチ（CI は自動判定が仕事、人間は PR 結果画面で見る）
- lefthook の `fail_text` は **ローカル開発者向けメッセージ**として適切な配置層

#### なぜバイナリを `~/.local/bin/` に置くか

- POSIX/XDG 規約に準拠したユーザレベルバイナリディレクトリ
- shikomi では `~/.cargo/bin/` を使っていたが、bakufu は Rust toolchain 前提でないため `~/.cargo/bin/` の存在自体が保証されない
- `~/.local/bin/` は多くのディストロで PATH 既定（macOS は `eval "$(/opt/homebrew/bin/brew shellenv)"` 等で追加が必要だが、bakufu の README にセットアップガイドとして明記）
- Windows: `$env:USERPROFILE\.local\bin\` を使い、setup.ps1 が PATH に追加する（既存セッション + プロファイル）

#### なぜ `lefthook install` を setup に含めるか

- lefthook は **`lefthook install` を実行して初めて** `.git/hooks/` にラッパを配置する
- setup スクリプト内で 1 コマンドだけなので、開発者に別ステップを要求しない KISS 設計
- ただし CI では `--tools-only` で `lefthook install` を skip する（CI ランナーで `.git/hooks/` を書く意味がないため）

#### なぜ `core.hooksPath` を変更しないか

- lefthook は `.git/hooks/` の既定パスに書き込む設計。`core.hooksPath` を別ディレクトリに向ける必要はない
- `core.hooksPath` を変更すると、他のツール（Git GUI クライアント等）との相互作用で予期せぬ挙動が出うる。デフォルト経路を保つことで想定外副作用を避ける（KISS）

#### CI ワークフローの構造方針

- **5 ジョブ独立**: `lint` / `typecheck` / `test-backend` / `test-frontend` / `audit` を独立ワークフローで並列実行（高速化と障害局所化）
- **共通プレステップ**: 各ワークフローの最初に `actions/checkout@v4` → `bash scripts/setup.sh --tools-only`（setup スクリプトの inline 実行）
- **キャッシュ**: 後続 Issue で `actions/cache@v4` を使い `~/.local/bin/` と `uv tool` ディレクトリをキャッシュ（MVP では未導入、YAGNI）
- **Windows ジョブ**: MVP では未設定。後続 Issue で windows-latest matrix を追加

## ユーザー向けメッセージの確定文言

`../feature-spec.md` §機能要件一覧 で ID のみ定義した MSG-DW-001〜014 の **正確な文言**を本節で凍結する。実装者・Sub-issue が勝手に改変できない契約として扱う。変更は本設計書の更新 PR のみで許可される。

### プレフィックス統一

全メッセージは 5 種類のプレフィックスのいずれかで始まる。色非対応端末でもプレフィックスのテキストだけで重要度が識別可能（A09 対策）。

| プレフィックス | 意味 | 色（対応端末時） |
|--------------|-----|--------------|
| `[FAIL]` | 処理中止を伴う失敗 | 赤 |
| `[OK]` | 成功完了 | 緑 |
| `[SKIP]` | 冪等実行による省略 | 灰 |
| `[WARN]` | 警告（処理は継続） | 黄 |
| `[INFO]` | 情報提供（処理は継続） | 既定色 |

色付けは `just` / `lefthook` / `ruff` / `biome` / `pyright` のデフォルトに従い、TTY 非検出時は自動で無効化される（既存ツールの振る舞い）。**本 feature で独自に ANSI エスケープを出力しない**（KISS）。

### 2 行構造ルール

失敗メッセージ（`[FAIL]` プレフィックス）は常に **2 行構造**とする。検証は受入基準 11 で assertion される。

```
[FAIL] <何が失敗したかを日本語 1 文で要約>
次のコマンド: <実行すべき復旧コマンド 1 つ>
```

改行は LF 固定。`fail_text` 内で動的変数（ファイル名・ユーザ名等）は使わない（T7 対策）。

### MSG 確定文言表

| ID | 出力先 | 文言（改行区切りで上下 2 行） |
|----|------|------------------------------|
| MSG-DW-001 | lefthook `fail_text` | `[FAIL] ruff / biome の format 違反を検出しました。` / `次のコマンド: just fmt` |
| MSG-DW-002 | lefthook `fail_text` | `[FAIL] ruff / biome の lint 違反を検出しました。` / `次のコマンド: just lint`（自動修正可能なものは pnpm biome check --write . / uv run ruff check --fix .） |
| MSG-DW-003 | lefthook `fail_text` | `[FAIL] pytest / vitest に失敗しました。` / `次のコマンド: just test` |
| MSG-DW-004 | lefthook `fail_text` | `[FAIL] コミットメッセージが Conventional Commits 1.0 に準拠していません。` / `規約: CONTRIBUTING.md §コミット規約 または https://www.conventionalcommits.org/ja/v1.0.0/` |
| MSG-DW-005 | setup stdout | `[OK] Setup complete. Git フックが有効化されました。`（1 行のみ、成功は 2 行構造ルールの例外） |
| MSG-DW-006 | setup stdout | `[SKIP] {tool} は既にインストール済みです。` / `バージョン: {version}`（`{tool}` / `{version}` は setup スクリプトが動的挿入、ただし **stdout のみ・CI ログ共有なし**のため T7 対象外） |
| MSG-DW-007 | CONTRIBUTING.md 静的記載 | `[WARN] --no-verify の使用は規約で原則禁止です。` / `PR 本文に理由を明記してください。CI が同一チェックを再実行します。` |
| MSG-DW-008 | setup stderr | `[FAIL] Python 3.12+ または Node 20+ が未検出です。` / `次のコマンド: README.md §動作環境のセットアップ手順を参照してください。` |
| MSG-DW-009 | setup stderr | `[FAIL] .git/ ディレクトリが見つかりません。リポジトリルートで実行してください。` / `現在のディレクトリ: {cwd}`（`{cwd}` は setup stdout のみ、CI ログには流れない） |
| MSG-DW-010 | lefthook `fail_text` | `[FAIL] secret の混入が検出されました。該当行を除去後、git add を再実行してください。` / `既に push 済みの場合: CONTRIBUTING.md §Secret 混入時の緊急対応` |
| MSG-DW-011 | setup stderr | `[FAIL] PowerShell 7 以上が必要です（検出: {version}）。` / `次のコマンド: winget install Microsoft.PowerShell` |
| MSG-DW-012 | setup stderr | `[FAIL] {tool} バイナリの SHA256 検証に失敗しました。サプライチェーン改ざんの可能性があります。` / `次のコマンド: 一時ファイルを削除後にネットワーク状況を確認し再実行。繰り返し失敗する場合は Issue で報告してください。` |
| MSG-DW-013 | lefthook `fail_text` | `[FAIL] コミットメッセージに AI 生成フッターが含まれています（🤖 Generated with Claude Code / Co-Authored-By: Claude 等）。` / `次のコマンド: 該当行を削除して再コミット。許可されない trailer のポリシーは CONTRIBUTING.md §AI 生成フッターの禁止 を参照。` |
| MSG-DW-014 | lefthook `fail_text` | `[FAIL] pyright / tsc の型エラーを検出しました。` / `次のコマンド: just typecheck` |

**gitleaks / ruff / biome / pyright / tsc の `file:line` 出力**: これらのツール自体の stdout に検出箇所が出力される。`fail_text` には載せず、ツール出力との「縦の情報階層」（ツール出力 → 空行 → `[FAIL]` 2 行）を形成する。

## 開発ツールバイナリの配布経路と SHA256 検証（REQ-DW-015 詳細）

### バイナリ取得 URL のテンプレート

setup スクリプト冒頭に以下の定数を置き、アップデート時は PR で明示差分を提示する:

| 定数名（プレフィックス） | 対象ツール | 例 | 用途 |
|-------|-----|-----|------|
| `UV_VERSION` / `UV_SHA256_*` | uv（Astral 製） | `0.5.4` | Python パッケージマネージャ |
| `JUST_VERSION` / `JUST_SHA256_*` | just | `1.36.0` | タスクランナー |
| `CONVCO_VERSION` / `CONVCO_SHA256_*` | convco | `0.6.3` | Conventional Commits 検証 |
| `LEFTHOOK_VERSION` / `LEFTHOOK_SHA256_*` | lefthook | `1.7.18` | Git フック |
| `GITLEAKS_VERSION` / `GITLEAKS_SHA256_*` | gitleaks | `8.30.1` | Secret スキャン |

各ツール × 5 プラットフォーム（Linux x86_64 / Linux ARM64 / macOS x86_64 / macOS ARM64 / Windows x86_64）= **25 SHA256 定数**を sh / ps1 で同期して持つ。

**初期値は Sub-issue C の実装 PR で確定**させる。本設計書では「定数として設置する」契約だけを凍結し、具体値は実装時に upstream の公式 `checksums.txt`（`gh release view <tag> --repo <owner>/<repo>`）を取得して転記する運用とする。

**例外（convco）**: convco の公式 GitHub Releases には `checksums.txt` 相当のファイルが提供されていない。よって setup スクリプト実装時に各 release zip を `curl` で取得し、`sha256sum` で計算した値をピン値とする。HTTPS + GitHub Releases の認証経路で担保する範囲内で、公式 checksums と等価の運用を保つ。macOS については `convco-macos.zip` 1 ファイルのみが配布されており（Universal Binary か Intel-only かは upstream で未明示）、`DARWIN_X86_64` と `DARWIN_ARM64` は同一 SHA256 を採用する。upstream で個別配布が始まった時点で本書を更新して分離する。

### ダウンロード → 検証 → 配置の手順

1. URL 合成（例: lefthook）: `https://github.com/evilmartians/lefthook/releases/download/v${LEFTHOOK_VERSION}/lefthook_${LEFTHOOK_VERSION}_${PLATFORM}.${EXT}`
   - `PLATFORM`: OS と arch から決定（例: `Linux_x86_64`, `Darwin_arm64`, `Windows_x86_64`）
   - `EXT`: Unix は `tar.gz`、Windows は `zip`
2. `curl -sSfL <URL> -o <tmpfile>` でダウンロード（`-f` で HTTP エラー時に Fail Fast）
3. 実測 SHA256 を取得:
   - Unix: `sha256sum <tmpfile>` の先頭 64 hex を抽出
   - Windows: `(Get-FileHash <tmpfile> -Algorithm SHA256).Hash.ToLower()`
4. ピン定数と**完全一致**（大小文字・空白含め）を検証。不一致なら:
   - 一時ファイルを削除
   - MSG-DW-012 を stderr に出して exit 非 0
5. 一致なら展開し、バイナリを `~/.local/bin/`（Windows は `$env:USERPROFILE\.local\bin\`）に移動
6. Unix のみ `chmod +x <binary>` を適用

5 ツール（uv / just / convco / lefthook / gitleaks）すべてが同じ手順で導入される。

### CODEOWNERS で保護する 5 パス（REQ-DW-016 詳細）

`.github/CODEOWNERS` に Sub-issue B で以下を追記（Step 1 で既に記載済みのため、本 feature では既存記述を維持確認のみ）:

| パス | 保護対象の理由（T5・T8 脅威対応） |
|-----|----------------------------------|
| `/lefthook.yml` | フック定義の改変で検知スキップ・任意コマンド実行を仕込める |
| `/justfile` | レシピ内のコマンド改変で CI とローカルの乖離を作れる |
| `/scripts/setup.sh` | ダウンロード URL / SHA256 ピン改変でサプライチェーン攻撃経路を作れる |
| `/scripts/setup.ps1` | 同上 |
| `/scripts/ci/` | ピン同期検査スクリプト改変で乖離検知を無効化できる |

## データ構造

本 feature は永続化データを持たないため、主要な **設定ファイルのキー構造**を表形式で定義する。

### `lefthook.yml` のキー構造

| キー | 型 | 用途 | デフォルト値 / 採用値 |
|-----|---|------|-----------------|
| `pre-commit.parallel` | bool | fmt-check / lint / typecheck / audit-secrets の並列実行可否 | `true` |
| `pre-commit.commands.fmt-check.run` | string | 実行コマンド | `just fmt-check` |
| `pre-commit.commands.fmt-check.fail_text` | string | 失敗時メッセージ（静的 2 行） | MSG-DW-001 |
| `pre-commit.commands.lint.run` | string | 実行コマンド | `just lint` |
| `pre-commit.commands.lint.fail_text` | string | 失敗時メッセージ（静的 2 行） | MSG-DW-002 |
| `pre-commit.commands.typecheck.run` | string | 実行コマンド | `just typecheck` |
| `pre-commit.commands.typecheck.fail_text` | string | 失敗時メッセージ（静的 2 行） | MSG-DW-014 |
| `pre-commit.commands.audit-secrets.run` | string | 実行コマンド（REQ-DW-013） | `just audit-secrets` |
| `pre-commit.commands.audit-secrets.fail_text` | string | 失敗時メッセージ（静的 2 行） | MSG-DW-010 |
| `pre-push.commands.test.run` | string | 実行コマンド | `just test` |
| `pre-push.commands.test.fail_text` | string | 失敗時メッセージ（静的 2 行） | MSG-DW-003 |
| `commit-msg.parallel` | bool | convco と no-ai-footer の並列実行可否 | `true`（両者とも grep 相当の軽量検査、数百ミリ秒で完了） |
| `commit-msg.commands.convco.run` | string | 実行コマンド（`{1}` はメッセージファイルパス） | `just commit-msg-check {1}` |
| `commit-msg.commands.convco.fail_text` | string | 失敗時メッセージ（静的 2 行） | MSG-DW-004 |
| `commit-msg.commands.no-ai-footer.run` | string | AI 生成フッター検出コマンド（REQ-DW-018） | `just commit-msg-no-ai-footer {1}` |
| `commit-msg.commands.no-ai-footer.fail_text` | string | 失敗時メッセージ（静的 2 行） | MSG-DW-013 |
| `skip_output` | 配列 | 出力抑制対象 | 未設定（lefthook のデフォルト挙動に従う。MSG の 2 行構造が埋もれない限り抑制しない） |
| `colors` | string | 色出力制御 | 未設定（lefthook デフォルトで TTY 自動判定。CI 非 TTY で自動無効化）|

出典: lefthook Configuration Reference https://lefthook.dev/configuration/ の `Commands` / `fail_text` / `parallel` / `skip_output` 各節

### `justfile` のレシピ契約（初期定義 13 レシピ）

| レシピ名 | 引数 | 実行コマンド（論理） | 対応する CI ワークフロー |
|---------|-----|------------------|--------------------|
| `default` | なし | `just --list` を呼ぶ | — |
| `fmt-check` | なし | `uv run ruff format --check .` + `pnpm biome format .`（並列、両方の exit code を集約） | `lint.yml` step |
| `fmt` | なし | `uv run ruff format .` + `pnpm biome format --write .`（自動修正） | — |
| `lint` | なし | `uv run ruff check .` + `pnpm biome check .` | `lint.yml` step |
| `typecheck` | なし | `uv run pyright` + `pnpm tsc --noEmit`（並列） | `typecheck.yml` step |
| `test` | なし | `just test-backend` → `just test-frontend`（順次、失敗時途中終了） | `test-backend.yml` + `test-frontend.yml` |
| `test-backend` | なし | `uv run pytest backend/` | `test-backend.yml` |
| `test-frontend` | なし | `pnpm --dir frontend vitest run` | `test-frontend.yml` |
| `audit` | なし | `uv run pip-audit` + `pnpm dlx osv-scanner --recursive .` | `audit.yml` |
| `audit-secrets` | なし | `gitleaks protect --staged --no-banner` | pre-commit 経由（REQ-DW-013） |
| `audit-pin-sync` | なし | `bash scripts/ci/audit-pin-sync.sh` | `audit.yml` |
| `check-all` | なし | `fmt-check` → `lint` → `typecheck` → `test` → `audit` → `audit-secrets` → `audit-pin-sync` を順次呼ぶ（失敗時に途中終了） | 全 CI 相当 |
| `commit-msg-check` | `file` 引数 1 個 | **shebang bash レシピ**で `convco check --from-stdin --strip < {{FILE}}` を実行（確定 E）。shebang を使う理由は `windows-shell := pwsh` 環境で `<` が PowerShell の ParserError になるため、Git for Windows の `bash.exe` に閉じる必要があるから | — |
| `commit-msg-no-ai-footer` | `file` 引数 1 個 | `grep -iqE '<PATTERN>' {{file}} && exit 1 \|\| exit 0` を実行（REQ-DW-018、下記 §AI 生成フッター検出パターンを参照）。POSIX 互換なので Windows でも Git for Windows の `bash.exe` 経由で動作 | — |

### `scripts/setup.sh` のステップ契約

| ステップ | 処理 | Fail Fast 条件 |
|---------|-----|-------------|
| 1. shebang / strict mode | `#!/usr/bin/env bash` + `set -euo pipefail` | — |
| 2. 引数解析 | `--tools-only` フラグの有無を判定 | 不正な引数 → exit 非 0、usage 表示 |
| 3. ピン定数宣言 | 5 ツール × 5 プラットフォーム = 25 SHA256 + 5 VERSION を冒頭で定数定義 | 値が空なら即 exit（未確定状態でのマージ防止） |
| 4. cwd 検査 | リポジトリルート（`.git/` が存在）で実行されているか | 非リポジトリで実行 → exit 非 0、MSG-DW-009 |
| 5. 言語ランタイム検査 | `python3 --version`（3.12+）/ `node --version`（20+） | 失敗 → MSG-DW-008 |
| 6. `uv` 導入 | GitHub Releases から取得 → SHA256 検証 → `~/.local/bin/uv` 配置 | SHA256 不一致 → MSG-DW-012 |
| 7. `just` 導入 | 同上 | 同上 |
| 8. `convco` 導入 | 同上 | 同上 |
| 9. `lefthook` 導入 | 同上 | 同上 |
| 10. `gitleaks` 導入 | 同上 | 同上 |
| 11. Python ツール導入 | `uv tool install ruff pyright pip-audit`（既にあればスキップ） | `uv` 失敗 → exit 非 0 |
| 12. Node ツール導入 | `corepack enable` → `pnpm install -g @biomejs/biome osv-scanner` | `corepack` / `pnpm` 失敗 → exit 非 0 |
| 13. `lefthook install` | `--tools-only` 指定なしの場合のみ `.git/hooks/` へラッパ配置 | 失敗 → MSG-DW-009 |
| 14. 完了ログ | MSG-DW-005 を表示 | — |

### `scripts/setup.ps1` のステップ契約

setup.sh と **同一のステップ番号・同一の責務**。差分のみ表記。

| ステップ | sh 版 | ps1 版（差分） |
|---------|-----|------------|
| 0（ps1 専用） | — | **冒頭で `$PSVersionTable.PSVersion.Major -lt 7` を検査**、未満なら MSG-DW-011 で exit（確定 B）|
| 1 | `#!/usr/bin/env bash` + `set -euo pipefail` | 冒頭 `$ErrorActionPreference = 'Stop'`。`Set-StrictMode -Version Latest` を併用 |
| 2 | `--tools-only` フラグ判定 | `param([switch]$ToolsOnly)` |
| 3 | ピン定数を bash 変数で宣言 | PowerShell 変数（`$LEFTHOOK_VERSION` 等）で同値を宣言。**ピン値は sh / ps1 で完全同期させる**（二重管理だが、共通化のための third file を作るのは YAGNI） |
| 4 | `.git/` 検査（`-d .git`） | `Test-Path .git` |
| 5 | `python3 --version` / `node --version` | 同左、`$LASTEXITCODE` 非 0 を検査 |
| 6-10 | `curl -sSfL` → `sha256sum` → 文字列比較 | `Invoke-WebRequest -Uri <URL> -OutFile <tmp>` → `(Get-FileHash <tmp> -Algorithm SHA256).Hash.ToLower()` → `-eq` 比較 |
| 11 | `uv tool install ruff pyright pip-audit` | 同左 |
| 12 | `corepack enable` → `pnpm install -g @biomejs/biome osv-scanner` | 同左 |
| 13-14 | 同一 | 同一 |

**ピン同期の担保（設計時確定）**: `setup.sh` と `setup.ps1` の `<TOOL>_VERSION` / 各 SHA256 値が乖離すると、Windows 開発者だけ別バイナリを引く事故（T4 脅威のバリエーション）が起きる。Sub-issue C で **`scripts/ci/audit-pin-sync.sh`（および `just audit-pin-sync` レシピ・`audit.yml` ステップ）を必須実装**する。挙動: 両ファイルから同一変数名の値を正規表現で抽出し、各組で文字列完全一致を検証、乖離があれば exit 非 0。これにより**人間の注意力に依存せず機械的にピン同期を強制**する（Fail Fast 原則）。判断は本設計書で凍結し Sub-issue 側での再判定は行わない。

### AI 生成フッター検出パターン（REQ-DW-018 詳細、確定パターン）

`just commit-msg-no-ai-footer FILE` レシピは、以下 3 パターンを **case-insensitive** な **拡張正規表現（ERE）** で照合する。いずれか 1 件でもヒットすれば exit 1 でコミットを中止する。lefthook `parallel: true` により既存の convco 検査と独立に走る。

| # | パターン（拡張正規表現・ERE） | 検出対象の例 | 意図 |
|---|---------------------------|-----------|------|
| P1 | `🤖.*Generated with.*Claude` | `🤖 Generated with [Claude Code](https://claude.com/claude-code)` | Claude Code が自動挿入する emoji 付きフッター行 |
| P2 | `Co-Authored-By:.*@anthropic\.com` | `Co-Authored-By: Claude <noreply@anthropic.com>` | anthropic.com ドメインを含む Co-Authored-By trailer（メールアドレスドメインで識別） |
| P3 | `Co-Authored-By:.*\bClaude\b` | `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` | Claude を name に含む Co-Authored-By trailer（モデル名の揺れに強い） |

**実装契約**:
- 3 パターンを `\|`（ERE のアルタネーション）で結合し、単一の `grep -iqE '(P1)|(P2)|(P3)' FILE` 呼び出しで検査する（サブプロセス起動を最小化）
- `-i` で大小文字を無視（`co-authored-by` / `CO-AUTHORED-BY` 等の表記揺れを吸収）
- `-E` で拡張正規表現（`\|` でアルタネーション、`\b` で単語境界）
- `-q` で match 時に出力抑止（match/no-match は exit code のみ）
- match（exit 0）なら shell 側で `exit 1` へ反転してコミット中止、no-match（exit 1）なら `exit 0` へ反転してコミット続行

**誤検知の境界**:
- `Claude` という単語を**本文・ファイル名・PR 番号**等で引用する正規のコミットメッセージは、P3 の単語境界（`\bClaude\b`）と Co-Authored-By 行のみの照合制約により誤検知しない（P3 は `Co-Authored-By:.*\bClaude\b` なので `Co-Authored-By:` 接頭辞を必須とする）
- 将来「Claude」を別の文脈（例: プロジェクトオーナー名が偶然 Claude）で合法的に使うケースが出た場合は、本設計書を更新して例外経路を追加する（現時点では bakufu プロジェクトのオーナー `@kkm-horikawa` に該当者なし）

**対象外（YAGNI）**:
- 他の AI（ChatGPT / Gemini / Copilot 等）のフッター検出は本 Issue のスコープ外。オーナーが同様の懸念を表明した時点で追加パターンを登録する（パターン追加は本設計書の P4 以降として正規表現 1 行を追記すれば完了）
- コミット **body / description** に散文として Claude を言及するケースは P3 の `Co-Authored-By:` 前置制約により自動的に対象外

**`--no-verify` バイパス時の対応**:
- T9 脅威で述べた通り、ローカル commit-msg フックは `--no-verify` で無効化可能。`pre-receive` hook は GitHub 無料プランで提供されず、機械的な完全遮断は不可能
- 代替: (a) CONTRIBUTING.md §AI 生成フッターの禁止 で明文化し、Agent-C ペルソナ（Claude Code 等）への明示的教示 (b) PR レビュー時の人間レビュワー / `@kkm-horikawa` による目視検知 (c) 将来 squash merge 時に GitHub UI が自動挿入する Co-Authored-By への対応は後続 Issue（YAGNI）

### `.github/workflows/*.yml` の編集契約

| ファイル | `run:` の内容 | 備考 |
|---------|---------|------|
| `lint.yml` | `bash scripts/setup.sh --tools-only` → `just fmt-check` → `just lint` | 既存の ruff / biome 設定（pyproject.toml / biome.json）を尊重 |
| `typecheck.yml` | `bash scripts/setup.sh --tools-only` → `just typecheck` | pyright / tsc は両方並列、片方落ちても他方の結果は表示 |
| `test-backend.yml` | `bash scripts/setup.sh --tools-only` → `just test-backend` | `uv run pytest backend/`。fixtures / coverage の詳細はテスト設計書 |
| `test-frontend.yml` | `bash scripts/setup.sh --tools-only` → `just test-frontend` | `pnpm --dir frontend vitest run`。Storybook / Playwright は YAGNI |
| `audit.yml` | `bash scripts/setup.sh --tools-only` → `just audit` → `just audit-secrets` → `just audit-pin-sync` | 3 監査ステップを 1 ジョブで連続実行（ピン同期は他より軽量） |

### CI ワークフローで追加する secret scan ステップ

`audit.yml` に**二重防護**のため `just audit-secrets` ステップを追加する（T8 脅威対応）。ローカル pre-commit が `lefthook.yml` 改変で無効化された場合でも CI 側で独立に検知。

| ステップ順 | `run:` | 目的 |
|---------|-------|------|
| 1 | `actions/checkout@v4`（`fetch-depth: 0`）| gitleaks に履歴全体を渡すため全履歴取得 |
| 2 | `bash scripts/setup.sh --tools-only` | 開発ツール配置 |
| 3 | `just audit` | `pip-audit` + `osv-scanner` |
| 4 | `just audit-secrets`（または `gitleaks detect --no-banner` を直接） | 履歴全体に対する secret 検知 |
| 5 | `just audit-pin-sync` | sh / ps1 のピン同期検証 |

## ビジュアルデザイン

該当なし — 理由: 本 feature は CLI のみで GUI 要素を持たない。フック失敗時のテキスト出力は `lefthook` / `just` / `ruff` / `biome` / `pyright` / `tsc` のデフォルト配色・書式に従う。

---

## 出典・参考

- lefthook 公式ドキュメント: https://lefthook.dev/ / https://github.com/evilmartians/lefthook
- lefthook Configuration Reference: https://lefthook.dev/configuration/
- lefthook Releases: https://github.com/evilmartians/lefthook/releases
- just 公式: https://just.systems/
- just `windows-shell` 設定: https://just.systems/man/en/chapter_33.html
- convco: https://github.com/convco/convco
- gitleaks: https://github.com/gitleaks/gitleaks
- gitleaks `protect` サブコマンド: https://github.com/gitleaks/gitleaks#scan-commands
- uv 公式: https://docs.astral.sh/uv/
- uv `tool install`: https://docs.astral.sh/uv/concepts/tools/
- ruff 公式: https://docs.astral.sh/ruff/
- pyright 公式: https://microsoft.github.io/pyright/
- biome 公式: https://biomejs.dev/
- pip-audit 公式: https://pypi.org/project/pip-audit/
- osv-scanner 公式: https://google.github.io/osv-scanner/
- pnpm 公式: https://pnpm.io/
- corepack 公式: https://nodejs.org/api/corepack.html
- Git `core.hooksPath` ドキュメント: https://git-scm.com/docs/githooks#_core_hookspath
- Conventional Commits 1.0 仕様: https://www.conventionalcommits.org/ja/v1.0.0/
- `git filter-repo` 公式: https://github.com/newren/git-filter-repo
- GitHub Secret scanning: https://docs.github.com/en/code-security/secret-scanning/about-secret-scanning
- Microsoft Learn "Installing PowerShell on Windows": https://learn.microsoft.com/powershell/scripting/install/installing-powershell-on-windows
- OWASP Top 10 2021: https://owasp.org/Top10/
