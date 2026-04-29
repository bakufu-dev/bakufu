# 機能仕様書 — dev-workflow

> feature: `dev-workflow`
> Vモデル階層: 階層 2（feature 業務概念）

## 1. 概要

bakufu リポジトリに「clone 直後から有効になる Git フック運用」を `lefthook` + `just` + `convco` + `gitleaks` + `scripts/setup.{sh,ps1}` で実装する。ローカルファースト品質保証思想に基づき、pre-commit / pre-push / commit-msg フックと CI の単一実行経路化を実現する。

## 2. 背景・目的

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

## 3. ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 鎌田 大樹（27） | OSS 新規コントリビュータ（Python + TS 中級） | Python 3 年、TS 2 年、Linux 主、VS Code | Issue を拾って feature ブランチで初 PR を上げる | clone → setup 1 回 → 通常の `git commit` / `git push` でローカル検証が自動で走り、push 前に落ちる失敗を push 後に知らずに済む |
| Agent-C（Claude Code） | 自動化エージェント（LLM） | Python/TS トリビア平均、シェル実行可 | Issue からドラフト PR を生成、CI 結果を見てループ修正 | 手動で `lefthook install` を忘れない。setup スクリプト 1 本で決定論的に環境を用意できる。**コミットメッセージに AI 生成フッター（`🤖 Generated with Claude Code` / `Co-Authored-By: Claude <noreply@anthropic.com>` 等の trailer）を付与しない**（REQ-DW-018 / MSG-DW-013、CONTRIBUTING.md §AI 生成フッターの禁止）。Agent-C は既定で当該 trailer を自動挿入する実装のため、本ペルソナは「明示的に抑止設定した状態で動作する」こと自体をゴールに含む |
| 春日 結衣（34） | レビュワー兼メンテナ（Python + TS 上級） | Python 7 年、TS 5 年、3 OS（Mac/Win/Linux）で検証 | 全 PR の最終承認、外部レビューゲートの人間判断、release/* ブランチ運用 | ローカルで `just check-all` 相当を一発で回せる。CI を通過するコミットがローカルで必ず通ることの担保 |

## 4. ユースケース

| UC-ID | ユースケース名 | 主アクター |
|---|---|---|
| UC-DW-001 | 新規参画者がセットアップスクリプトで開発環境を構築する | 鎌田 大樹 / Agent-C |
| UC-DW-002 | 開発者がコミット操作でローカル品質検証を通過する | 鎌田 大樹 / Agent-C |
| UC-DW-003 | 開発者が push でテスト検証を通過する | 鎌田 大樹 / 春日 結衣 |
| UC-DW-004 | commit-msg フックが規約・AI フッターを検証する | 鎌田 大樹 / Agent-C |
| UC-DW-005 | CI がローカルと同一レシピでチェックを再実行する | 春日 結衣 |

## 5. スコープ

### In Scope

- REQ-DW-001: `lefthook.yml` をリポジトリにコミットし、`lefthook install` で `.git/hooks/` に配置する（フックツール導入）
- REQ-DW-002: コミット時に `just fmt-check` / `just lint` / `just typecheck` / `just audit-secrets` を並列実行する（pre-commit フック）
- REQ-DW-003: push 時に `just test` を走らせる（pre-push フック）
- REQ-DW-004: Conventional Commits 規約（`convco check --from-stdin --strip`）でメッセージ検証する（commit-msg フック）
- REQ-DW-005: `justfile` を配置し、13 レシピを定義する（タスクランナー導入）
- REQ-DW-006: GitHub Actions ワークフロー 5 本を `just <recipe>` 呼び出しに統一する（CI との単一実行経路化）
- REQ-DW-007: `scripts/setup.sh`（Unix 向けセットアップスクリプト）
- REQ-DW-008: `scripts/setup.ps1`（Windows 向けセットアップスクリプト）
- REQ-DW-009: setup スクリプトの冪等性と再実行耐性
- REQ-DW-010: README / CONTRIBUTING 更新（setup 1 ステップ、`--no-verify` 禁止ポリシー等）
- REQ-DW-011: `--no-verify` バイパス検知（CI 側での全チェック再実行）
- REQ-DW-012: フック失敗時のメッセージ品質（2 行固定構造）
- REQ-DW-013: Secret 混入検知 pre-commit フック（gitleaks 単独）
- REQ-DW-014: PowerShell 7+ 必須化（`setup.ps1` 冒頭での Fail Fast）
- REQ-DW-015: 開発ツールバイナリの完全性検証（SHA256 検証）
- REQ-DW-016: 開発ワークフロー設定ファイルの CODEOWNERS 保護
- REQ-DW-017: Git 履歴からの secret リムーブ運用（CONTRIBUTING 手順明記）
- REQ-DW-018: AI 生成フッターのコミットメッセージ混入禁止

### Out of Scope（参照）

- Windows CI matrix 追加（後続 Issue で windows-latest を追加、YAGNI）
- gitleaks カスタムルール（`.gitleaks.toml`）の設定（bakufu 固有 secret 経路契約が必要になった時点で追加、YAGNI）
- 他の AI（ChatGPT / Gemini / Copilot 等）のフッター検出（YAGNI）
- e2e テスト（`just test-e2e`）の実装（YAGNI）
- `actions/cache@v4` によるツールキャッシュ（後続 Issue、YAGNI）
- オフライン環境のサポート

## 6. 業務ルールの確定（要求としての凍結）

### 確定 R1-A: 全開発ツールを GitHub Releases バイナリ + SHA256 検証で統一導入

shikomi は Rust toolchain 前提のため、Rust 製ツール（`just` / `convco`）を `cargo install --locked` で導入していた。bakufu は **Rust toolchain を前提としない**（バックエンドが Python のため）。よって setup スクリプトでは:

- **Rust 製の `just` / `convco`** も GitHub Releases から OS/arch に合致するバイナリを取得し、SHA256 検証で導入する
- **Go 製の `lefthook` / `gitleaks`** も同様（shikomi と同じ経路）
- **Python の `uv` / `ruff` / `pyright` / `pip-audit`** は uv 経由で `tool install` する（uv 自体は GitHub Releases バイナリ + SHA256 検証で導入）
- **Node の `pnpm`** は corepack 経由（Node 同梱）またはバイナリで導入。`biome` / `osv-scanner` は pnpm 経由で導入

これにより**配布経路を「GitHub Releases バイナリ + SHA256 検証」と「言語パッケージマネージャ（uv/pnpm）」の 2 種に集約**でき、shikomi の「Rust 製は cargo install、Go 製は GitHub Releases」という 2 経路混在を解消する。**bakufu の方が一貫性が高い設計となる**。

### 確定 R1-B: Windows は PowerShell 7+ 必須

`setup.ps1` 冒頭で `$PSVersionTable.PSVersion.Major -lt 7` を検査し、未満なら Fail Fast + `winget install Microsoft.PowerShell` の導入コマンドを提示する。Windows 10 21H2 初期環境でも `winget` は OS 標準で利用可能、1 コマンドで完了するため新規参画者の導線は確保される。README 対応 OS 表に「Windows: PowerShell 7+ 必須」を明記する。

### 確定 R1-C: Secret 検出フックを pre-commit に追加（gitleaks 単独）

shikomi は `gitleaks` + `scripts/ci/audit-secret-paths.sh`（shikomi 独自の secret 経路契約検証）の 2 本立てだったが、bakufu には対応する既存契約がない。よって **`gitleaks` 単独**で pre-commit に組み込む。bakufu 固有の secret 経路契約（例: 外部レビューゲート署名の非ログ出力）が必要になった時点で `scripts/ci/audit-secret-paths.sh` を新設し、`just audit-secrets` レシピから引き回す（YAGNI）。

### 確定 R1-D: --no-verify と git history 残留への対応

`--no-verify` は Git の設計上**技術的に止められない**。よって以下 2 段構えで対処する:

1. **CI 側再実行による事後検知**: push 済みコミットに対し同一 `just <recipe>` を CI で再実行。通らないコミットは PR マージ不可
2. **secret 混入時の履歴リライト手順を CONTRIBUTING に明記**: `git filter-repo` 推奨、GitHub 側 secret scanning + revoke の順で対応する運用を文書化

### 確定 R1-E: 型チェックの配置層 — pre-commit に含める（再判定条件あり）

shikomi では Rust の型チェックは `cargo check` 経由で `cargo clippy` に統合され、pre-commit に含まれていた（数秒）。bakufu の `pyright` + `tsc --noEmit` も pre-commit に含めて 5 秒以内に収まるかは MVP 後のドメイン規模で変わる。

設計時の判断: **pre-commit に typecheck を含める**ことを基本とし、5 秒以内が崩れる measurement が出た場合は pre-push に移すか、`pyright --outputjson` で差分のみ検査する形に切り替える。後段の判断条件は `domain/basic-design.md` の §処理フローに「再判定条件」として明記する。

## 7. 機能要件一覧（概要）

| 機能ID | 機能名 | 優先度 |
|--------|-------|--------|
| REQ-DW-001 | フックツール導入（lefthook） | 必須 |
| REQ-DW-002 | pre-commit フック | 必須 |
| REQ-DW-003 | pre-push フック | 必須 |
| REQ-DW-004 | commit-msg フック（Conventional Commits） | 必須 |
| REQ-DW-005 | タスクランナー導入（just） | 必須 |
| REQ-DW-006 | CI との単一実行経路化 | 必須 |
| REQ-DW-007 | setup スクリプト（Unix, `scripts/setup.sh`） | 必須 |
| REQ-DW-008 | setup スクリプト（Windows, `scripts/setup.ps1`） | 必須 |
| REQ-DW-009 | 冪等性と再実行耐性 | 必須 |
| REQ-DW-010 | README / CONTRIBUTING 更新 | 必須 |
| REQ-DW-011 | `--no-verify` バイパス検知 | 必須 |
| REQ-DW-012 | フック失敗時のメッセージ品質 | 必須 |
| REQ-DW-013 | Secret 混入検知 pre-commit フック | 必須 |
| REQ-DW-014 | PowerShell 7+ 必須化 | 必須 |
| REQ-DW-015 | 開発ツールバイナリの完全性検証 | 必須 |
| REQ-DW-016 | 開発ワークフロー設定ファイルの CODEOWNERS 保護 | 必須 |
| REQ-DW-017 | Git 履歴からの secret リムーブ運用 | 必須 |
| REQ-DW-018 | AI 生成フッターのコミットメッセージ混入禁止 | 必須 |

詳細は [`domain/basic-design.md §モジュール契約`](domain/basic-design.md) を参照。

## 8. 制約・前提

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

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|---|---|---|
| 1 | `git clone` 直後に `scripts/setup.sh`（または `.ps1`）を 1 回実行するだけで、フックが有効化される | UC-DW-001 | TC-E2E-001 |
| 2 | pre-commit が fmt / lint / typecheck の違反を検知してコミットを中断する | UC-DW-002 | TC-E2E-002, TC-E2E-012 |
| 3 | pre-push が `pytest` / `vitest` 失敗を検知して push を中断する | UC-DW-003 | TC-E2E-004 |
| 4 | commit-msg が Conventional Commits 違反を検知する | UC-DW-004 | TC-E2E-003 |
| 5 | CI ワークフロー 5 本が `just <recipe>` 呼び出しに統一されている | UC-DW-005 | TC-UT-003 |
| 6 | setup スクリプトを 2 回連続で実行しても差分が発生せず、成功終了する（冪等） | UC-DW-001 | TC-E2E-006, TC-IT-006 |
| 7 | Windows / macOS / Linux の 3 OS で setup → コミット → push が同一手順で動作する | UC-DW-001 | TC-IT-004, TC-IT-005 |
| 8 | `--no-verify` で意図的にバイパスしたコミットを push しても CI が全ジョブで同一のチェックを再実行して落とす | UC-DW-005 | TC-E2E-005 |
| 9 | README / CONTRIBUTING に setup 1 ステップと `--no-verify` 禁止ポリシーが明記されている | UC-DW-001 | TC-UT-004 |
| 10 | `just --list` ですべてのレシピが 1 行説明つきで一覧表示される | UC-DW-002 | TC-UT-002 |
| 11 | pre-commit / pre-push / commit-msg の各失敗時に stderr の最終行が `[FAIL] <原因要約>` → 次行に `次のコマンド: just <recipe>` の 2 行構造で表示される | UC-DW-002 | TC-UT-005, TC-E2E-002 |
| 12 | `gitleaks` で secret 混入を含むコミットが阻止される | UC-DW-002 | TC-E2E-008, TC-IT-007 |
| 13 | `setup.ps1` を PowerShell 5.1 で起動した場合、exit 非 0 + MSG-DW-011 の Fail Fast が発火する | UC-DW-001 | TC-E2E-007, TC-IT-008 |
| ~~14~~ | （欠番 — SHA256 改ざん拒否検証は §10 Q-1 に移動） | — | — |
| ~~15~~ | （欠番 — CODEOWNERS 保護検証は §10 Q-2 に移動） | — | — |
| ~~16~~ | （欠番 — CONTRIBUTING §Secret 手順検証は §10 Q-3 に移動） | — | — |
| ~~17~~ | （欠番 — AI 生成フッター reject 検証は §10 Q-4 に移動） | — | — |

## 10. 開発者品質基準（CI 担保、業務要求ではない）

| # | 基準 | 検証方法 |
|---|---|---|
| Q-1 | `setup.{sh,ps1}` が SHA256 不一致バイナリを拒否する（REQ-DW-015） | TC-E2E-009, TC-IT-009, TC-UT-013 |
| Q-2 | `.github/CODEOWNERS` に 5 パスが `@kkm-horikawa` 所有で登録されている（REQ-DW-016） | TC-UT-006 |
| Q-3 | `CONTRIBUTING.md §Secret 混入時の緊急対応` 節が 3 項目（revoke / filter-repo / secret scanning）で存在する（REQ-DW-017） | TC-UT-007 |
| Q-4 | commit-msg フックが AI 生成フッター 3 パターン（REQ-DW-018）を reject する | TC-E2E-010, TC-IT-010, TC-UT-014〜016 |
| Q-5 | `scripts/ci/audit-pin-sync.sh` で setup.sh / setup.ps1 のピン定数（30 件）が同期している | TC-UT-008, TC-UT-009 |
| Q-6 | ピン定数 25 件（5 ツール × 5 プラットフォーム）が upstream の公式 checksums.txt と一致している | TC-UT-017 |

## 11. 開放論点 (Open Questions)

| # | 論点 | 起票先 |
|---|---|---|
| TBD-DW-1〜9 | 外部 I/O characterization fixture 起票（checksums.json 等、詳細は `domain/test-design.md §外部I/O依存マップ`） | 別 Issue |

## 12. Sub-issue 分割計画

本 feature は bakufu のリポジトリ初期化と並行して進めるため、Issue 起票は MVP 着手前のドキュメント駆動開発として扱う。**設計確定（本書 + 基本設計書 + 詳細設計書）の後、以下 4 本の Sub-issue を `gh issue create` で一括発行する**。REQ-DW-001〜018 の全 18 要件をいずれかの Sub-issue に紐付け、孤児要件を作らない。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| **A**: `feat(dev-workflow): introduce just as task runner` | REQ-DW-005, 006, 011, **018（レシピ側）** | `justfile` 作成（13 レシピ: default / fmt-check / fmt / lint / typecheck / test / test-backend / test-frontend / audit / audit-secrets / audit-pin-sync / check-all / commit-msg-check / commit-msg-no-ai-footer）。CI 5 ワークフロー（`lint` / `typecheck` / `test-backend` / `test-frontend` / `audit`）を `just <recipe>` 呼び出しへ統一 | なし（先行着手可） |
| **B**: `feat(dev-workflow): add lefthook for local git hooks with secret scan` | REQ-DW-001, 002, 003, 004, 012, 013, 016, **018（フック側）** | `lefthook.yml` 作成（pre-commit は `fmt-check` / `lint` / `typecheck` / `audit-secrets` の 4 並列、pre-push は `test`、commit-msg は `convco` と `no-ai-footer` の 2 コマンド並列）。`fail_text` は詳細設計書の MSG-DW-001〜004, 010, 013 確定文言を静的文字列として埋め込み（2 行構造）。`.github/CODEOWNERS` に 5 パスを追記（REQ-DW-016） | A に依存（フックから `just` レシピを呼ぶため） |
| **C**: `feat(dev-workflow): add cross-platform setup scripts with SHA256 verification` | REQ-DW-007, 008, 009, 014, 015 | `scripts/setup.sh` / `scripts/setup.ps1` 作成。`just` / `convco` / `lefthook` / `gitleaks` / `uv` を GitHub Releases からバイナリ取得 + SHA256 ピン定数で改ざん検証。Python ツール（`ruff` / `pyright` / `pip-audit`）は `uv tool install`、Node ツール（`biome` / `osv-scanner`）は `pnpm install -g`。`setup.ps1` 冒頭で PowerShell 7+ を検査し未満なら Fail Fast + `winget install Microsoft.PowerShell` 案内（REQ-DW-014、MSG-DW-011）。`.git/` 検査・冪等実行のすべてを実装。ピン定数の初期値は本 Sub-issue 実装時に upstream の公式 `checksums.txt` から転記 | B に依存 |
| **D**: `docs(dev-workflow): update README and CONTRIBUTING for local-first quality workflow` | REQ-DW-010, 017, **018（ポリシー側）** | README 更新（setup 1 ステップ、対応 OS 表に「Windows: PowerShell 7+ 必須」追記、`winget` コマンド案内）。CONTRIBUTING 更新（`--no-verify` 禁止ポリシー / MSG-DW-007 / `just` レシピ一覧 / **§Secret 混入時の緊急対応**: 即 revoke → `git filter-repo` → GitHub secret scanning resolve の 3 段手順を REQ-DW-017 に従い明文化。`main` / `develop` への force-push は引き続き禁止、feature ブランチ限定で実施する旨も明記 / **§AI 生成フッターの禁止**: `Co-Authored-By: Claude` / `🤖 Generated with Claude Code` 等の trailer をコミットメッセージに含めないポリシーを REQ-DW-018 に従い明文化） | C に依存（実際の手順が確定してから文書化） |

## 13. 扱うデータと機密レベル

本 feature はソースコードの品質検査と開発者ワークフロー整備のみが対象であり、**bakufu のエンドユーザーが扱う機密情報（OAuth トークン / Empire データ / 外部レビュー署名等）には触れない**。ただし以下 2 点のセキュリティ境界に留意する。

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| 開発者ローカル環境の改変 | `.git/hooks/` へのフック書込み | 低（開発者自身の作業ツリーに閉じる） |
| GitHub Releases / pypi.org / npmjs.com 経由のサプライチェーン | `just` / `convco` / `lefthook` / `gitleaks` / `uv` バイナリ、`ruff` / `pyright` / `pip-audit` / `biome` / `osv-scanner` パッケージの脆弱性・供給元信頼性 | 中（SHA256 検証 + `pip-audit` / `osv-scanner` チェックで緩和。ローカル開発環境限定、配布バイナリには含まれない） |

## 14. 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | pre-commit は **5 秒以内**（fmt-check + lint + typecheck + audit-secrets の差分のみ）、pre-push は **3 分以内**（test の冷たい初回を除く）。キャッシュ効くケースを基準に測定。typecheck が 5 秒を超える measurement が出た場合は pre-push へ移動（domain/basic-design.md の再判定条件参照） |
| 可用性 | ネットワーク断でも setup 済みの環境ではフックが動作すること（GitHub Releases / pypi.org / npmjs.com への接続は初回のみ、以降はローカルバイナリ実行） |
| 保守性 | フック定義・レシピ定義・CI ワークフローの 3 層で**同一コマンド**を参照すること（DRY）。変更は `justfile` 一箇所で反映 |
| 可搬性 | Windows/macOS/Linux の 3 OS すべてで同一の `just <recipe>` が動作。MVP 段階では Windows CI ジョブは未設定（後続 Issue で windows-latest 追加） |
| セキュリティ | 全ツールバイナリを SHA256 検証つきで導入（REQ-DW-015）。サプライチェーンリスクを最小化 |
| ドキュメント性 | `just` 実行時のヘルプ（`just --list`）で全レシピと 1 行説明を自動表示。コメントをレシピ直上に記述し `--list` に反映 |
