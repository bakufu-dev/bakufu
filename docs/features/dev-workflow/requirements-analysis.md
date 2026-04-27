# 要求分析書

<!-- feature単位で1ファイル。新規featureならテンプレートコピー、既存featureなら既存ファイルをREAD→EDIT -->
<!-- 配置先: docs/features/dev-workflow/requirements-analysis.md -->

## 人間の要求

bakufu リポジトリ初期化時の対話で、リポジトリオーナー（`@kkm-horikawa`）から以下の方針が示された:

> shikomi の `docs/features/dev-workflow/` を bakufu でも踏襲したい。Vモデル 5 ファイル丸ごと作り起こし。CONTRIBUTING / SECURITY 等の流用も提示通りで OK。`biome` と `pyright` を採用する。

shikomi は同オーナーが運営する別 OSS（クリップボード管理ツール、Rust 製）であり、その `dev-workflow` feature では「**clone 直後から有効になる Git フック運用**」を `lefthook` + `just` + `convco` + `gitleaks` + `scripts/setup.{sh,ps1}` で実装している。bakufu でも同じローカルファースト品質保証思想を採用するが、技術スタックが異なるため翻訳と一部設計判断の更新が必要となる。

## 背景・目的

### 想定される痛点（bakufu 着手前の予防）

bakufu はまだ実装が存在しない MVP 前段階だが、以下の痛点はソフトウェアプロジェクト全般に共通であり、shikomi の `dev-workflow` 設計時に実証済みである:

1. **CI を最後の砦にする構造的限界**: GitHub Actions のクレジットを `ruff format --check` のような秒で終わるチェックで消費するのは、時間・コスト双方で無駄。**ローカルで品質を担保し、CI は最終確認の位置付け**にする方針が筋。
2. **手動セットアップの忘却**: `pre-commit install` 相当の手動有効化を要求する方式は、新規参画者・エージェント（Claude Code 等）・既存メンバーで環境のばらつきを生む。clone 直後にワンステップで有効化される必要がある。
3. **`--no-verify` の安易なバイパス**: ローカルフックは Git の仕様上必ず opt-out 可能。CI 側で同一チェックを再実行する二段防護が不可欠。
4. **AI 生成フッターのコミット履歴汚染**: Claude Code 等のエージェントが既定で挿入する `🤖 Generated with Claude Code` / `Co-Authored-By: Claude <noreply@anthropic.com>` 等の trailer は、コミット履歴の真実源性を損ない、将来的な企業利用でのコード所有権明確化要求と相容れない。
5. **サプライチェーン信頼性**: 開発ツールバイナリ（lefthook / gitleaks 等）を取得する経路で改ざんが入ると、開発者ローカル環境および CI ランナーが汚染される。SHA256 検証が必須。

### 解決されれば変わること

- 開発者ローカルで lint / typecheck / format / test 失敗が早期に検出され、push 前に修正が完結する
- CI は「ローカルをバイパスした場合のセーフティネット」として機能し、通常フローでは緑通過が既定になる
- 新規参画者・エージェント・既存メンバーが**同一の setup スクリプト 1 本**で環境を揃えられる
- `--no-verify` による意図的バイパスはユーザー責任領域として明示され、規約違反として扱える
- AI 生成フッターは commit-msg フックで水際阻止され、コミット履歴がプロジェクトの真実源として維持される

### ビジネス価値

- CI コスト削減（lint 落ち程度のやり直し PR を減らす）
- 外部レビュー（人間チェックポイント）への差戻し頻度低減 → リードタイム短縮
- オンボーディング時間の短縮（新規コントリビュータ・エージェントの環境構築ばらつき排除）
- AI エージェント協業時のコミット履歴の権利関係明確化

## 議論結果

### 設計担当による採用前提

bakufu は **Python 3.12+ バックエンド（FastAPI）** + **TypeScript フロントエンド（React + Vite）** の構成。shikomi（Rust）と異なり、Rust toolchain は前提としない。よって以下を採用する:

- **フックツール**: `lefthook`（Go 製バイナリ、YAML 設定、並列実行、Windows ネイティブ対応）— shikomi と同
- **タスクランナー**: `just`（Rust 製バイナリ、Windows ネイティブ対応）— shikomi と同
- **commit-msg 検査**: `convco`（Rust 製、Conventional Commits 専用）— shikomi と同
- **secret スキャン**: `gitleaks`（Go 製、staged diff 対応）— shikomi と同
- **Python lint + format**: `ruff`（Astral 製、極めて高速）
- **Python 型チェック**: `pyright`（Microsoft 製、mypy より高速・高機能）
- **TypeScript lint + format**: `biome`（Rust 製、eslint + prettier の統合代替）
- **TypeScript 型チェック**: `tsc --noEmit`（TypeScript 公式）
- **Python テスト**: `pytest`
- **TypeScript テスト**: `vitest`
- **Python 依存監査**: `pip-audit`（OSV/PyPI advisory データベース照合）
- **TypeScript 依存監査**: `osv-scanner`（npm 含む横断スキャナ、Google 製）
- **Python パッケージ管理**: `uv`（Astral 製、極めて高速）
- **Node パッケージ管理**: `pnpm`
- **セットアップ**: `scripts/setup.sh`（Unix）+ `scripts/setup.ps1`（Windows）の 2 本

### 却下候補と根拠

| 候補 | 却下理由 |
|-----|---------|
| `pre-commit` framework (Python) | Python ランタイム依存。bakufu は Python を使うが、フックツールに別の Python 環境を要求すると環境隔離が壊れる。lefthook は単一バイナリで完結 |
| `husky` (Node.js) | Node.js 依存を必須化。lefthook は単一バイナリで Node 不要 |
| `commitlint` (Node.js) | 同上 |
| `mypy` | `pyright` より遅い。型推論の精度・速度・JSON 出力対応で `pyright` が優位 |
| `eslint` + `prettier` | 2 ツール構成は設定の二重管理を生む。`biome` は両者を Rust 実装で統合し、桁違いに高速 |
| `flake8` | `ruff` が機能上位互換、桁違いに高速 |
| `black` | 同上（`ruff format` が代替） |
| `npm audit` 単独 | npm 限定で範囲が狭い。`osv-scanner` は OSV データベース横断で npm + Python + Go 等を一括監査可能 |
| `safety` (Python) | `pip-audit` が PyPA 公式、OSV データベース統合 |
| `Makefile` | Windows ネイティブで動かない |
| `npm scripts` / `package.json` scripts | Node 依存。バックエンドは Python のため統一不能 |
| `tox` / `nox` (Python) | Python 限定でフロントエンド統合不能 |
| `core.hooksPath` + 生シェル | Windows の CRLF / 実行ビット / POSIX 互換シェル依存で罠が多い |
| `build.rs` 相当の暗黙副作用方式 | 該当する Python/TS の仕組みは存在しない（明示的 setup スクリプトで OK） |

### 「clone 直後から完全自動」の扱い

Git の仕様上、`.git/hooks/` は clone で配布できない（`.git/` はリポジトリ本体の外）。よって **どの方式でも最低 1 コマンドの有効化操作は必要**。本 feature では「`git clone` 後に `scripts/setup.{sh,ps1}` を 1 回実行すれば完了」を「**実現可能な最短**」として受容する。README / CONTRIBUTING にこの 1 ステップを明文化する。

### 重要な選定確定

#### 確定 A: 全開発ツールを **GitHub Releases バイナリ + SHA256 検証で統一導入**（bakufu 固有判断）

shikomi は Rust toolchain 前提のため、Rust 製ツール（`just` / `convco`）を `cargo install --locked` で導入していた。bakufu は **Rust toolchain を前提としない**（バックエンドが Python のため）。よって setup スクリプトでは:

- **Rust 製の `just` / `convco`** も GitHub Releases から OS/arch に合致するバイナリを取得し、SHA256 検証で導入する
- **Go 製の `lefthook` / `gitleaks`** も同様（shikomi と同じ経路）
- **Python の `uv` / `ruff` / `pyright` / `pip-audit`** は uv 経由で `tool install` する（uv 自体は GitHub Releases バイナリ + SHA256 検証で導入）
- **Node の `pnpm`** は corepack 経由（Node 同梱）またはバイナリで導入。`biome` / `osv-scanner` は pnpm 経由で導入

これにより**配布経路を「GitHub Releases バイナリ + SHA256 検証」と「言語パッケージマネージャ（uv/pnpm）」の 2 種に集約**でき、shikomi の「Rust 製は cargo install、Go 製は GitHub Releases」という 2 経路混在を解消する。**bakufu の方が一貫性が高い設計となる**。

#### 確定 B: Windows は **PowerShell 7+ 必須**（shikomi と同じ案 B 採用）

`setup.ps1` 冒頭で `$PSVersionTable.PSVersion.Major -lt 7` を検査し、未満なら Fail Fast + `winget install Microsoft.PowerShell` の導入コマンドを提示する。Windows 10 21H2 初期環境でも `winget` は OS 標準で利用可能、1 コマンドで完了するため新規参画者の導線は確保される。README 対応 OS 表に「Windows: PowerShell 7+ 必須」を明記する。

#### 確定 C: Secret 検出フックを **pre-commit に追加**（gitleaks 単独）

shikomi は `gitleaks` + `scripts/ci/audit-secret-paths.sh`（shikomi 独自の secret 経路契約検証）の 2 本立てだったが、bakufu には対応する既存契約がない。よって **`gitleaks` 単独**で pre-commit に組み込む。bakufu 固有の secret 経路契約（例: 外部レビューゲート署名の非ログ出力）が必要になった時点で `scripts/ci/audit-secret-paths.sh` を新設し、`just audit-secrets` レシピから引き回す（YAGNI）。

#### 確定 D: `--no-verify` と git history 残留への対応

`--no-verify` は Git の設計上**技術的に止められない**。よって以下 2 段構えで対処する:

1. **CI 側再実行による事後検知**: push 済みコミットに対し同一 `just <recipe>` を CI で再実行。通らないコミットは PR マージ不可
2. **secret 混入時の履歴リライト手順を CONTRIBUTING に明記**: `git filter-repo` 推奨、GitHub 側 secret scanning + revoke の順で対応する運用を文書化

#### 確定 E: 型チェックの配置層 — **pre-commit に含める**（暫定、measurement で再判定）

shikomi では Rust の型チェックは `cargo check` 経由で `cargo clippy` に統合され、pre-commit に含まれていた（数秒）。bakufu の `pyright` + `tsc --noEmit` も pre-commit に含めて 5 秒以内に収まるかは MVP 後のドメイン規模で変わる。

設計時の判断: **pre-commit に typecheck を含める**ことを基本とし、5 秒以内が崩れる measurement が出た場合は pre-push に移すか、`pyright --outputjson` で差分のみ検査する形に切り替える。後段の判断条件は基本設計書の §処理フローに「再判定条件」として明記する。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 鎌田 大樹（27） | OSS 新規コントリビュータ（Python + TS 中級） | Python 3 年、TS 2 年、Linux 主、VS Code | Issue を拾って feature ブランチで初 PR を上げる | clone → setup 1 回 → 通常の `git commit` / `git push` でローカル検証が自動で走り、push 前に落ちる失敗を push 後に知らずに済む |
| Agent-C（Claude Code） | 自動化エージェント（LLM） | Python/TS トリビア平均、シェル実行可 | Issue からドラフト PR を生成、CI 結果を見てループ修正 | 手動で `lefthook install` を忘れない。setup スクリプト 1 本で決定論的に環境を用意できる。**コミットメッセージに AI 生成フッター（`🤖 Generated with Claude Code` / `Co-Authored-By: Claude <noreply@anthropic.com>` 等の trailer）を付与しない**（REQ-DW-018 / MSG-DW-013、CONTRIBUTING.md §AI 生成フッターの禁止）。Agent-C は既定で当該 trailer を自動挿入する実装のため、本ペルソナは「明示的に抑止設定した状態で動作する」こと自体をゴールに含む |
| 春日 結衣（34） | レビュワー兼メンテナ（Python + TS 上級） | Python 7 年、TS 5 年、3 OS（Mac/Win/Linux）で検証 | 全 PR の最終承認、外部レビューゲートの人間判断、release/* ブランチ運用 | ローカルで `just check-all` 相当を一発で回せる。CI を通過するコミットがローカルで必ず通ることの担保 |

## 前提条件・制約

| 区分 | 内容 |
|-----|------|
| 既存技術スタック | Python 3.12+（FastAPI バックエンド）、TypeScript 5+（React フロントエンド）、SQLite 3.40+（ローカル永続化）、Node.js 20 LTS+ |
| 既存 CI | GitHub Actions 3 ワークフロー（`branch-policy.yml` / `back-merge-check.yml` / `pr-title-check.yml`、いずれも言語非依存）。**削除禁止**（本 feature は CI を補強するものであり置換ではない） |
| 既存ブランチ戦略 | GitFlow（`develop` → `feature/*`、`release/*` → `main`）。CONTRIBUTING.md §ブランチ戦略参照 |
| コミット規約 | Conventional Commits。`pr-title-check` ワークフローで PR タイトルを検証済み |
| line endings | `.gitattributes` 未設定（本 feature の Sub-issue で必要に応じて追加）。setup スクリプトの Windows 版も LF でコミット |
| 実行権限 | 管理者権限不要。Python・Node・Git・PowerShell 7+（Windows のみ）が導入済みであることを前提とする |
| ネットワーク | GitHub Releases / pypi.org / npmjs.com への接続を要する。オフライン環境は本 feature のスコープ外（YAGNI） |
| 対象 OS | Windows 10 21H2 以上 / macOS 12 以上 / Linux（glibc 2.35+）。README §動作環境と同一 |

## 機能一覧

| 機能ID | 機能名 | 概要 | 優先度 |
|--------|-------|------|--------|
| REQ-DW-001 | フックツール導入 | `lefthook.yml` をリポジトリにコミットし、`lefthook install` で `.git/hooks/` に配置する | 必須 |
| REQ-DW-002 | pre-commit フック | コミット時に `just fmt-check` / `just lint` / `just typecheck` / `just audit-secrets` を並列実行 | 必須 |
| REQ-DW-003 | pre-push フック | push 時に `just test` を走らせる | 必須 |
| REQ-DW-004 | commit-msg フック | Conventional Commits 規約（`convco check --from-stdin --strip`）でメッセージ検証 | 必須 |
| REQ-DW-005 | タスクランナー導入 | `justfile` を配置し、`fmt-check` / `fmt` / `lint` / `typecheck` / `test` / `test-backend` / `test-frontend` / `audit` / `audit-secrets` / `audit-pin-sync` / `check-all` / `commit-msg-check` / `commit-msg-no-ai-footer` のレシピを定義 | 必須 |
| REQ-DW-006 | CI との単一実行経路化 | GitHub Actions ワークフロー（`lint.yml` / `typecheck.yml` / `test-backend.yml` / `test-frontend.yml` / `audit.yml`）を `just <recipe>` 呼び出しに統一し、ローカルと CI で同一コマンドを走らせる | 必須 |
| REQ-DW-007 | setup スクリプト（Unix） | `scripts/setup.sh`: `just` / `convco` / `lefthook` / `gitleaks` / `uv` を GitHub Releases から SHA256 検証つきで導入し、`uv tool install` で Python ツール（`ruff` / `pyright` / `pip-audit`）を、`pnpm` で Node ツール（`biome` / `osv-scanner`）を導入し、`lefthook install` を実行 | 必須 |
| REQ-DW-008 | setup スクリプト（Windows） | `scripts/setup.ps1`: **PowerShell 7+ 必須**（REQ-DW-014 で明示検査）。同等の導入処理を PowerShell で実装 | 必須 |
| REQ-DW-009 | 冪等性と再実行耐性 | setup スクリプトは既にインストール済みのツールをスキップし、複数回実行しても差分を出さない | 必須 |
| REQ-DW-010 | README / CONTRIBUTING 更新 | `git clone` 後のワンステップ setup 手順、`--no-verify` 禁止ポリシー、利用可能な `just` レシピ一覧、AI 生成フッター禁止ポリシーを明文化 | 必須 |
| REQ-DW-011 | `--no-verify` バイパス検知 | サーバ側 CI で全チェックを再実行し、バイパスされたコミットを必ず落とす（CI を最後の砦として維持） | 必須 |
| REQ-DW-012 | フック失敗時のメッセージ品質 | 失敗した際にユーザーが次に取るべきコマンド（例: `just fmt` で自動修正）を提示。`[FAIL] <要約>` / `次のコマンド: just <recipe>` の **2 行固定構造** | 必須 |
| REQ-DW-013 | Secret 混入検知 pre-commit フック | `gitleaks protect --staged --no-banner` による汎用 secret スキャンを pre-commit で実行する | 必須 |
| REQ-DW-014 | PowerShell 7+ 必須化 | Windows 開発者に PowerShell 7+ を必須前提とし、`setup.ps1` 冒頭で未満バージョンを検出して Fail Fast する | 必須 |
| REQ-DW-015 | 開発ツールバイナリの完全性検証 | `setup.{sh,ps1}` は `just` / `convco` / `lefthook` / `gitleaks` / `uv` バイナリを GitHub Releases からダウンロードし、setup スクリプトにピンされた SHA256 と照合。不一致なら Fail Fast | 必須 |
| REQ-DW-016 | 開発ワークフロー設定ファイルの CODEOWNERS 保護 | `lefthook.yml` / `justfile` / `scripts/setup.{sh,ps1}` / `scripts/ci/**` を CODEOWNERS で保護し、PR レビューなしの改変を不能にする | 必須 |
| REQ-DW-017 | Git 履歴からの secret リムーブ運用 | push 後に secret 混入が判明した場合の履歴書換え手順（`git filter-repo` 推奨）と GitHub 側 secret scanning + revoke 運用を CONTRIBUTING に明記 | 必須 |
| REQ-DW-018 | AI 生成フッターのコミットメッセージ混入禁止 | commit-msg フックで `🤖 Generated with Claude Code` / `Co-Authored-By: Claude <noreply@anthropic.com>` 等の AI 生成識別フッターを含むコミットメッセージを検出して reject する。CONTRIBUTING にも禁止ポリシーを明記。背景: コミット履歴はプロジェクトの真実源であり、著者情報は `author` / `committer` フィールドで表現されるため、trailer による生成元識別は重複・冗長 | 必須 |

## Sub-issue分割計画

本 feature は bakufu のリポジトリ初期化と並行して進めるため、Issue 起票は MVP 着手前のドキュメント駆動開発として扱う。**設計確定（本書 + 基本設計書 + 詳細設計書）の後、以下 4 本の Sub-issue を `gh issue create` で一括発行する**。REQ-DW-001〜018 の全 18 要件をいずれかの Sub-issue に紐付け、孤児要件を作らない。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| **A**: `feat(dev-workflow): introduce just as task runner` | REQ-DW-005, 006, 011, **018（レシピ側）** | `justfile` 作成（13 レシピ: default / fmt-check / fmt / lint / typecheck / test / test-backend / test-frontend / audit / audit-secrets / audit-pin-sync / check-all / commit-msg-check / commit-msg-no-ai-footer）。CI 5 ワークフロー（`lint` / `typecheck` / `test-backend` / `test-frontend` / `audit`）を `just <recipe>` 呼び出しへ統一 | なし（先行着手可） |
| **B**: `feat(dev-workflow): add lefthook for local git hooks with secret scan` | REQ-DW-001, 002, 003, 004, 012, 013, 016, **018（フック側）** | `lefthook.yml` 作成（pre-commit は `fmt-check` / `lint` / `typecheck` / `audit-secrets` の 4 並列、pre-push は `test`、commit-msg は `convco` と `no-ai-footer` の 2 コマンド並列）。`fail_text` は詳細設計書の MSG-DW-001〜004, 010, 013 確定文言を静的文字列として埋め込み（2 行構造）。`.github/CODEOWNERS` に 5 パスを追記（REQ-DW-016） | A に依存（フックから `just` レシピを呼ぶため） |
| **C**: `feat(dev-workflow): add cross-platform setup scripts with SHA256 verification` | REQ-DW-007, 008, 009, 014, 015 | `scripts/setup.sh` / `scripts/setup.ps1` 作成。`just` / `convco` / `lefthook` / `gitleaks` / `uv` を GitHub Releases からバイナリ取得 + SHA256 ピン定数で改ざん検証。Python ツール（`ruff` / `pyright` / `pip-audit`）は `uv tool install`、Node ツール（`biome` / `osv-scanner`）は `pnpm install -g`。`setup.ps1` 冒頭で PowerShell 7+ を検査し未満なら Fail Fast + `winget install Microsoft.PowerShell` 案内（REQ-DW-014、MSG-DW-011）。`.git/` 検査・冪等実行のすべてを実装。ピン定数の初期値は本 Sub-issue 実装時に upstream の公式 `checksums.txt` から転記 | B に依存 |
| **D**: `docs(dev-workflow): update README and CONTRIBUTING for local-first quality workflow` | REQ-DW-010, 017, **018（ポリシー側）** | README 更新（setup 1 ステップ、対応 OS 表に「Windows: PowerShell 7+ 必須」追記、`winget` コマンド案内）。CONTRIBUTING 更新（`--no-verify` 禁止ポリシー / MSG-DW-007 / `just` レシピ一覧 / **§Secret 混入時の緊急対応**: 即 revoke → `git filter-repo` → GitHub secret scanning resolve の 3 段手順を REQ-DW-017 に従い明文化。`main` / `develop` への force-push は引き続き禁止、feature ブランチ限定で実施する旨も明記 / **§AI 生成フッターの禁止**: `Co-Authored-By: Claude` / `🤖 Generated with Claude Code` 等の trailer をコミットメッセージに含めないポリシーを REQ-DW-018 に従い明文化） | C に依存（実際の手順が確定してから文書化） |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | pre-commit は **5 秒以内**（fmt-check + lint + typecheck + audit-secrets の差分のみ）、pre-push は **3 分以内**（test の冷たい初回を除く）。キャッシュ効くケースを基準に測定。typecheck が 5 秒を超える measurement が出た場合は pre-push へ移動（基本設計書の再判定条件参照） |
| 可用性 | ネットワーク断でも setup 済みの環境ではフックが動作すること（GitHub Releases / pypi.org / npmjs.com への接続は初回のみ、以降はローカルバイナリ実行） |
| 保守性 | フック定義・レシピ定義・CI ワークフローの 3 層で**同一コマンド**を参照すること（DRY）。変更は `justfile` 一箇所で反映 |
| 可搬性 | Windows/macOS/Linux の 3 OS すべてで同一の `just <recipe>` が動作。MVP 段階では Windows CI ジョブは未設定（後続 Issue で windows-latest 追加） |
| セキュリティ | 全ツールバイナリを SHA256 検証つきで導入（REQ-DW-015）。サプライチェーンリスクを最小化 |
| ドキュメント性 | `just` 実行時のヘルプ（`just --list`）で全レシピと 1 行説明を自動表示。コメントをレシピ直上に記述し `--list` に反映 |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | `git clone` 直後に `scripts/setup.sh`（または `.ps1`）を 1 回実行するだけで、フックが有効化される | 新規作業ディレクトリで clone → setup → 意図的に lint 違反を含むコミットを試み、pre-commit が阻止することを確認 |
| 2 | pre-commit が fmt / lint / typecheck の違反を検知してコミットを中断する | 同上、コミット結果の exit code が非 0 |
| 3 | pre-push が `pytest` / `vitest` 失敗を検知して push を中断する | 意図的に落ちるテストを追加し `git push`、push 拒否されることを確認 |
| 4 | commit-msg が Conventional Commits 違反を検知する | `feat` や `fix` 以外の type を含まないメッセージを試し、コミットが拒否される |
| 5 | CI ワークフロー（`lint.yml` / `typecheck.yml` / `test-backend.yml` / `test-frontend.yml` / `audit.yml`）が `just <recipe>` 呼び出しに統一されている | 該当 YAML の `run:` 行を grep し、直接 `ruff` / `biome` / `pytest` 等の呼び出しが消えていることを確認 |
| 6 | setup スクリプトを 2 回連続で実行しても差分が発生せず、成功終了する（冪等） | 連続実行して exit code 0 を確認 |
| 7 | Windows / macOS / Linux の 3 OS で setup → コミット → push が同一手順で動作する | 3 OS で手動検証（将来 CI で matrix 化） |
| 8 | `--no-verify` で意図的にバイパスしたコミットを push しても CI が全ジョブで同一のチェックを再実行して落とす | GitHub Actions 実行結果で確認 |
| 9 | README / CONTRIBUTING に setup 1 ステップと `--no-verify` 禁止ポリシーが明記されている | 対応 PR の diff で確認 |
| 10 | `just --list` ですべてのレシピが 1 行説明つきで一覧表示される | `just --list` のコンソール出力で確認 |
| 11 | pre-commit / pre-push / commit-msg の各失敗時に stderr の**最終行が `[FAIL] <原因要約>` → 次行に `次のコマンド: just <recipe>` の 2 行構造**で表示される（REQ-DW-012 の検証基準） | 意図的に違反コミットを試み、stderr 末尾 2 行を assertion で確認。MSG-DW-001〜004 の文言が一致 |
| 12 | `gitleaks` で secret 混入を含むコミットが阻止される（REQ-DW-013 の検証基準） | テスト用に `AKIA` + 16 桁 + secret 40 桁の擬似値を含むファイルを staged し、コミットが exit 非 0 で中止されることを確認 |
| 13 | `setup.ps1` を PowerShell 5.1 で起動した場合、exit 非 0 + MSG-DW-011 の Fail Fast が発火する（REQ-DW-014 の検証基準） | Windows 10 21H2 の既定 PowerShell 5.1 で起動 → 失敗メッセージの文言確認 |
| 14 | `setup.{sh,ps1}` が各バイナリダウンロード時に SHA256 検証を行い、改ざんされたバイナリを拒否する（REQ-DW-015 の検証基準） | ダウンロード後のファイルをテスト用に書換え → 再 setup で MSG-DW-012 が発火することを確認 |
| 15 | `.github/CODEOWNERS` に `/lefthook.yml` / `/justfile` / `/scripts/setup.sh` / `/scripts/setup.ps1` / `/scripts/ci/` が登録され、該当 PR でオーナーレビューが要求される（REQ-DW-016 の検証基準） | CODEOWNERS を grep で確認、該当ファイル変更 PR の GitHub UI でレビュー要求表示を確認 |
| 16 | CONTRIBUTING.md に **§Secret 混入時の緊急対応** 節が存在し、以下 3 項目が明記されている（REQ-DW-017 の検証基準）: (a) 該当キーを発行元で即 revoke (b) `git filter-repo --path <file> --invert-paths` による履歴書換えと feature ブランチ限定 force-push（`main` / `develop` への force-push は禁止を明記）(c) GitHub Support への cache purge 依頼と secret scanning alert の resolve | 対応 PR の CONTRIBUTING.md 該当節を diff 確認。見出しと 3 項目の存在を grep で検証 |
| 17 | commit-msg フックが以下 3 パターンのいずれかを含むコミットメッセージを検出して reject する（REQ-DW-018 の検証基準）: (a) `🤖 Generated with Claude Code` または `🤖` + `Generated with` + `Claude` を含む行 (b) `Co-Authored-By:` で始まり `@anthropic.com` ドメインを含む trailer (c) `Co-Authored-By:` で始まり `Claude` を name に含む trailer | 意図的に各パターンを含むコミットを試み、exit 非 0 で中止され MSG-DW-013 が stderr に出力されることを確認。大文字小文字は無視（case-insensitive 照合） |

## 扱うデータと機密レベル

本 feature はソースコードの品質検査と開発者ワークフロー整備のみが対象であり、**bakufu のエンドユーザーが扱う機密情報（OAuth トークン / Empire データ / 外部レビュー署名等）には触れない**。ただし以下 2 点のセキュリティ境界に留意する。

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| 開発者ローカル環境の改変 | `.git/hooks/` へのフック書込み | 低（開発者自身の作業ツリーに閉じる） |
| GitHub Releases / pypi.org / npmjs.com 経由のサプライチェーン | `just` / `convco` / `lefthook` / `gitleaks` / `uv` バイナリ、`ruff` / `pyright` / `pip-audit` / `biome` / `osv-scanner` パッケージの脆弱性・供給元信頼性 | 中（SHA256 検証 + `pip-audit` / `osv-scanner` チェックで緩和。ローカル開発環境限定、配布バイナリには含まれない） |
