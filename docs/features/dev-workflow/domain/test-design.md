# テスト設計書 — dev-workflow / domain

<!-- feature: dev-workflow / sub-feature: domain -->
<!-- 配置先: docs/features/dev-workflow/domain/test-design.md -->
<!-- 対象範囲: REQ-DW-001〜018 / MSG-DW-001〜014 / 脅威 T1〜T9 / 受入基準 1〜13 / 開発者品質基準 Q-1〜Q-6 -->

本 feature はランタイムコードを追加せず、設定ファイル（`lefthook.yml` / `justfile`）とシェル/PowerShell スクリプト（`scripts/setup.sh` / `scripts/setup.ps1` / `scripts/ci/audit-pin-sync.sh`）、CI ワークフロー（`.github/workflows/*.yml` 5 本）と文書（`CONTRIBUTING.md`）で構成される。テスト粒度は「ユニット＝設定/スクリプトの単体契約」「結合＝レシピ/フック間連携」「E2E＝ペルソナシナリオ」で定義する。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-DW-001 | `lefthook.yml` / `.git/hooks/` | TC-UT-001 | ユニット | 正常系 | 1 |
| REQ-DW-002 | `lefthook.yml::pre-commit` + `justfile::fmt-check` / `lint` / `typecheck` | TC-IT-001, TC-UT-010 | 結合/ユニット | 正常系/異常系 | 2, 11 |
| REQ-DW-003 | `lefthook.yml::pre-push` + `justfile::test` | TC-IT-002 | 結合 | 異常系 | 3 |
| REQ-DW-004 | `lefthook.yml::commit-msg.convco` + `justfile::commit-msg-check` | TC-IT-003, TC-UT-011 | 結合/ユニット | 正常系/異常系 | 4 |
| REQ-DW-005 | `justfile` 全レシピ | TC-UT-002 | ユニット | 正常系 | 10 |
| REQ-DW-006 | `.github/workflows/{lint,typecheck,test-backend,test-frontend,audit}.yml` | TC-UT-003 | ユニット | 正常系 | 5 |
| REQ-DW-007 | `scripts/setup.sh` | TC-IT-004 | 結合 | 正常系 | 1, 6, 7 |
| REQ-DW-008 | `scripts/setup.ps1` | TC-IT-005 | 結合 | 正常系 | 1, 7 |
| REQ-DW-009 | `scripts/setup.{sh,ps1}` 冪等 | TC-IT-006 | 結合 | 正常系 | 6 |
| REQ-DW-010 | `README.md` / `CONTRIBUTING.md` | TC-UT-004 | ユニット | 正常系 | 9 |
| REQ-DW-011 | `.github/workflows/*.yml` | TC-E2E-005 | E2E | 異常系 | 8 |
| REQ-DW-012 | `lefthook.yml::fail_text` 全箇所 | TC-UT-005 | ユニット | 正常系 | 11 |
| REQ-DW-013 | `lefthook.yml::pre-commit.audit-secrets` + `justfile::audit-secrets` | TC-IT-007, TC-UT-012 | 結合/ユニット | 異常系 | 12 |
| REQ-DW-014 | `scripts/setup.ps1` PS7 検査 | TC-IT-008 | 結合 | 異常系 | 13 |
| REQ-DW-015 | `scripts/setup.{sh,ps1}` SHA256 検証 | TC-IT-009, TC-UT-013 | 結合/ユニット | 異常系 | Q-1 |
| REQ-DW-016 | `.github/CODEOWNERS` | TC-UT-006 | ユニット | 正常系 | Q-2 |
| REQ-DW-017 | `CONTRIBUTING.md §Secret 混入時の緊急対応` | TC-UT-007 | ユニット | 正常系 | Q-3 |
| REQ-DW-018 | `lefthook.yml::commit-msg.no-ai-footer` + `justfile::commit-msg-no-ai-footer` | TC-IT-010, TC-UT-014〜016 | 結合/ユニット | 異常系/正常系 | Q-4 |
| REQ-DW-006（追加契約） | `scripts/ci/audit-pin-sync.sh` | TC-UT-008, TC-UT-009 | ユニット | 正常系/異常系 | 内部品質基準 |
| T9 補助 | ピン定数 upstream 同期 | TC-UT-017 | ユニット | 正常系 | 内部品質基準 |
| REQ-DW-002（typecheck 新規） | `lefthook.yml::pre-commit.typecheck` + `justfile::typecheck` | TC-IT-011, TC-UT-018 | 結合/ユニット | 異常系 | 2, 11 |

## 外部I/O依存マップ

| 外部I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| GitHub Releases `astral-sh/uv` checksums + 全プラットフォーム成果物 | setup.sh / setup.ps1 のピン値照合対象 | `tests/fixtures/characterization/raw/uv_releases_v<VER>_checksums.json`（要起票） | — | **要起票 (Issue TBD-1)**：upstream の実 SHA256 を 5 プラットフォーム分 `gh release view` で取得して固定し、ピン転記ミスを CI で検出可能にする |
| GitHub Releases `casey/just` checksums | 同上 | `tests/fixtures/characterization/raw/just_releases_v<VER>_checksums.json`（要起票） | — | **要起票 (Issue TBD-2)** |
| GitHub Releases `convco/convco` checksums | 同上 | `tests/fixtures/characterization/raw/convco_releases_v<VER>_checksums.json`（要起票） | — | **要起票 (Issue TBD-3)** |
| GitHub Releases `evilmartians/lefthook` checksums | 同上 | `tests/fixtures/characterization/raw/lefthook_releases_v<VER>_checksums.json`（要起票） | — | **要起票 (Issue TBD-4)** |
| GitHub Releases `gitleaks/gitleaks` checksums | 同上 | `tests/fixtures/characterization/raw/gitleaks_releases_v<VER>_checksums.json`（要起票） | — | **要起票 (Issue TBD-5)** |
| `convco` CLI 出力（`--help` / `check --help`） | commit-msg フック用引数形式の契約 | `tests/fixtures/characterization/raw/convco_check_help.txt`（要起票） | — | **要起票 (Issue TBD-6)**：`--from-stdin` / `--strip` 両フラグの公式仕様を固定し、誤引用が実装に流れ込むのを防ぐ |
| `gitleaks protect --staged` のデフォルトルール挙動 | secret 混入検知の精度基準 | `tests/fixtures/characterization/raw/gitleaks_default_rules_v<VER>.json`（要起票） | `tests/factories/secret_sample.py`（要起票） | **要起票 (Issue TBD-7)**：AWS `AKIAIOSFODNN7EXAMPLE` は allowlist 扱い、実在パターン（AKIA + 16 桁 + secret 40 桁）のみ reject する挙動を実観測で固定 |
| `ruff` / `pyright` / `biome` / `pytest` / `vitest` の exit code 仕様 | フックから呼ばれる際の正常/異常系 contract | 各 ツールの公式 exit code 表（README から転記） | — | 不要（公式仕様で十分、変動小） |
| Git 実コマンド（`git commit` / `git push` / `git filter-repo`） | lefthook 経由のフック連携 | — | — | 済（Git 標準仕様） |
| pypi.org（`uv tool install ruff pyright pip-audit`） | setup / CI のツール導入経路 | 不要（公式 registry、`uv.lock` 相当で再現性担保） | — | 不要 |
| npmjs.com（`pnpm install -g @biomejs/biome osv-scanner`） | setup / CI のツール導入経路 | 不要（公式 registry、`pnpm-lock.yaml` で再現性担保） | — | 不要 |
| `pwsh` (PowerShell 7+) の `$PSVersionTable` / `Invoke-WebRequest` / `Get-FileHash` | setup.ps1 動作 | — | `tests/factories/powershell_version.py`（要起票） | **要起票 (Issue TBD-8)**：Windows 10 21H2 既定 5.1 / 7.x それぞれの `$PSVersionTable` 出力形式を固定 |
| `uname -s` / `uname -m` | setup.sh `detect_platform()` | — | `tests/factories/platform_stub.sh`（要起票） | **要起票 (Issue TBD-9)**：5 プラットフォーム × aarch64/x86_64 の正規組み合わせと、未サポート条件の境界 |

**空欄（要起票）の扱い**: 上記 Issue TBD-1〜9 が起票・完了するまで、該当項目に関わる unit/integration は「assumed mock」を禁じる。外部観測値に代わる raw fixture が未整備のまま unit を書くと、仕様誤引用に対する検出力ゼロのテストになる。

## E2Eテストケース

「開発者ペルソナの受入基準 1〜13 をブラックボックスで検証する」層。DB 直接確認・内部状態参照・テスト用裏口は禁止。本 feature は CLI/Git 操作が主なので、**bash/pwsh スクリプト + 実コミット発行**で検証する。証跡として stdout/stderr/exit code と `.git/hooks/` 内の生成物を保存する。

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| TC-E2E-001 | 鎌田 大樹（Linux x86_64 新規参画者） | clone 直後の setup → 通常コミット成功（受入基準 1, 2, 10） | 1. `git clone` 空ディレクトリ 2. `bash scripts/setup.sh` 3. `just --list` 4. 通常ファイル編集 → `git commit -m "feat(x): add"` | 1〜3. exit 0、MSG-DW-005 表示、13 レシピ全てに 1 行説明 4. コミット成功（pre-commit 全 4 検査 pass + commit-msg 2 検査 pass） |
| TC-E2E-002 | 鎌田 大樹 | format 違反コミットを pre-commit が遮断（受入基準 2, 11） | 1. `*.py` または `*.ts` に format 違反を意図的に挿入 2. `git add` → `git commit -m "feat(x): break fmt"` | exit 非 0、stderr 末尾に**静的 2 行構造**で `[FAIL] ruff / biome の format 違反を検出しました。` / `次のコマンド: just fmt` が出力（MSG-DW-001 確定文言完全一致） |
| TC-E2E-003 | 鎌田 大樹 | Conventional Commits 違反を commit-msg が遮断（受入基準 4, 11） | メッセージ本文を `random nonsense` として `git commit -m "random nonsense"` | exit 非 0、stderr に MSG-DW-004 が 2 行構造で表示。**lefthook のログではなく convco 側の usage error ではないこと**（仕様誤引用での再発防止） |
| TC-E2E-004 | 鎌田 大樹 | テスト失敗を pre-push が遮断（受入基準 3） | 1. `pytest` または `vitest` で落ちる変更を入れて `git commit --no-verify` 2. `git push` | push 拒否、stderr に MSG-DW-003 |
| TC-E2E-005 | 春日 結衣（レビュワー） | `--no-verify` バイパスを CI 側再実行で検知（受入基準 8） | 1. format 違反を `--no-verify` でコミット 2. `git push --no-verify` 3. GitHub Actions の `lint.yml` 結果を確認 | `lint.yml` job が `just fmt-check` ステップで exit 非 0 になり PR チェックが赤 |
| TC-E2E-006 | 鎌田 大樹 | `setup.sh` の 2 回連続実行で差分が発生しない（受入基準 6） | 1 回目 setup → 2 回目 setup を連続実行 | 2 回目も exit 0、`[SKIP] <tool> は既にインストール済みです` を 5 ツール（uv / just / convco / lefthook / gitleaks）で表示 |
| TC-E2E-007 | Windows 開発者（非 PowerShell 7） | PowerShell 5.1 起動で即 Fail Fast（受入基準 13） | Windows 10 21H2 既定 `powershell.exe` で `.\scripts\setup.ps1` | exit 非 0、MSG-DW-011 表示、`winget install Microsoft.PowerShell` 案内 |
| TC-E2E-008 | 鎌田 大樹 | secret 混入コミットを pre-commit が遮断（受入基準 12） | AWS access key 形式（`AKIA` + 16 文字 + 40 桁 secret）の擬似値（AWS 公式 example: `AKIAIOSFODNN7EXAMPLE` を踏襲）を staged → `git commit` | exit 非 0、MSG-DW-010 表示、gitleaks 側 stdout に file:line 出力 |
| TC-E2E-009 | 鎌田 大樹 | SHA256 改ざんバイナリを setup が拒否（Q-1） | setup.sh 冒頭のピン定数を意図的に 1 文字ズラして再実行（対象ツール未導入状態で） | exit 非 0、MSG-DW-012 表示、一時ファイル削除 |
| TC-E2E-010 | Agent-C（Claude Code） | AI 生成フッター付きコミットを commit-msg が遮断（Q-4、3 パターン） | 3 ケース個別: (a) `🤖 Generated with [Claude Code](...)` (b) `Co-Authored-By: Claude <noreply@anthropic.com>` (c) `Co-Authored-By: Claude Opus 4.7 <...>` | 3 ケースとも exit 非 0、MSG-DW-013 stderr 表示 |
| TC-E2E-011 | Agent-C 境界（body 位置の Claude 言及） | `Claude Shannon` を body 位置で引用した正規コミット | `feat(x): cite Claude Shannon in info theory` | exit 0 でコミット成功（P3 の `Co-Authored-By:` 接頭辞必須契約） |
| TC-E2E-012 | 鎌田 大樹 | typecheck 違反コミットを pre-commit が遮断（受入基準 2, 11） | Python に未定義変数 / TS に型不整合を入れる | exit 非 0、MSG-DW-014 表示 |

## 結合テストケース

「フック配線 × レシピ呼び出し」層。lefthook の `.git/hooks/` ラッパが justfile レシピを呼び、期待通り exit code / stderr を返すかを検証する。外部 API（GitHub Releases / pypi.org / npmjs.com）は**実接続**ではなく raw fixture を使用。

| テストID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|----------------|---------|------|---------|
| TC-IT-001 | `lefthook::pre-commit` → `justfile::fmt-check` / `lint` / `audit-secrets` | — | format 違反ファイルを staged | `git commit -m "feat: x"` | exit 非 0、lefthook が 4 検査を parallel 実行、MSG-DW-001 が 2 行構造で出力 |
| TC-IT-002 | `lefthook::pre-push` → `justfile::test` | — | 落ちるテストを含む commit | `git push` | exit 非 0、MSG-DW-003 stderr |
| TC-IT-003 | `lefthook::commit-msg.convco` → `justfile::commit-msg-check` → `convco` | `convco_check_help.txt`（要起票） | 正規 Conventional Commits メッセージ | `git commit -m "feat(x): valid"` | **convco CLI がその引数形式を受理し exit 0 を返すこと**。`unrecognized subcommand` が混入しないこと |
| TC-IT-004 | `scripts/setup.sh` 全 step（Linux x86_64） | 5 ツール × checksums.json | 空の作業ディレクトリ + `.git/` + python3/node 済 | `bash scripts/setup.sh` | exit 0、MSG-DW-005、`~/.local/bin/{uv,just,convco,lefthook,gitleaks}` 配置、`uv tool list` に `ruff` / `pyright` / `pip-audit`、`pnpm list -g` に `@biomejs/biome` / `osv-scanner`、`.git/hooks/{pre-commit,pre-push,commit-msg}` 配線、**正規バイナリが SHA256 検証を pass する**（対象プラットフォーム 5 種全て） |
| TC-IT-005 | `scripts/setup.ps1` 全 step（Windows PowerShell 7+） | 同上 | 同上 | `pwsh scripts/setup.ps1` | 同上 |
| TC-IT-006 | `setup.{sh,ps1}` 冪等 | 同上 | 1 回目 setup 済 | 2 回目 setup を連続実行 | 5 ツール全てで MSG-DW-006 表示、exit 0 |
| TC-IT-007 | `lefthook::pre-commit.audit-secrets` → `justfile::audit-secrets` → `gitleaks` | `gitleaks_default_rules_*.json` + secret factory | 実在パターンの AWS/API トークンを staged | `git commit` | exit 非 0、MSG-DW-010 |
| TC-IT-008 | `setup.ps1` step 0（PS7 検査） | `powershell_version` factory | `$PSVersionTable.PSVersion.Major = 5` | `setup.ps1` 起動 | exit 非 0、MSG-DW-011、以降 step 非実行 |
| TC-IT-009 | `setup.{sh,ps1}` SHA256 検証の改ざん拒否 | 改ざんバイナリ raw fixture | 対象ツール未導入 + ピン定数を正値に戻す | `setup.sh`（ダウンロード成果物の 1 byte を書換えて検証関数を直接呼ぶ） | exit 非 0、MSG-DW-012、一時ファイル削除 |
| TC-IT-010 | `lefthook::commit-msg.no-ai-footer` → `justfile::commit-msg-no-ai-footer` | — | 3 パターン個別の AI フッター付き COMMIT_EDITMSG | `git commit -m "..."` | 3 パターンとも exit 非 0、MSG-DW-013 |
| TC-IT-011 | `lefthook::pre-commit.typecheck` → `justfile::typecheck` → `pyright` + `tsc` | — | Python に型不整合 / TS に型エラー | `git commit` | exit 非 0、MSG-DW-014、両ツール実行（並列）|

## ユニットテストケース

「静的設定ファイル・スクリプト単体の契約」層。factory 経由で入力バリエーションを網羅する。入力は factory（raw fixture 直読は[却下]）。

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---------|-----|------|---------------|---------|
| TC-UT-001 | `lefthook.yml` 構造 | 正常系 | YAML parser | `pre-commit.parallel: true` / `commit-msg.parallel: true` / `pre-commit.commands.{fmt-check,lint,typecheck,audit-secrets}.run == "just <name>"` / `commit-msg.commands.{convco,no-ai-footer}.run == "just commit-msg-check {1}" / "just commit-msg-no-ai-footer {1}"`、キー構造が detailed-design §lefthook キー構造表と完全一致 |
| TC-UT-002 | `justfile` レシピ全 13 本 | 正常系 | `just --summary` / `just --list` 出力 | 13 レシピ名が `default / fmt / fmt-check / lint / typecheck / test / test-backend / test-frontend / audit / audit-secrets / audit-pin-sync / check-all / commit-msg-check / commit-msg-no-ai-footer` と完全一致、各レシピに**有意な 1 行説明**が付与 |
| TC-UT-003 | `.github/workflows/*.yml` 5 本 | 正常系 | YAML parser | `lint.yml` / `typecheck.yml` / `test-backend.yml` / `test-frontend.yml` / `audit.yml` の `run:` 行に直接 `ruff` / `biome` / `pytest` / `vitest` が残っていないこと、`bash scripts/setup.sh --tools-only` + `just <recipe>` 呼び出しのみ |
| TC-UT-004 | `CONTRIBUTING.md` / `README.md` | 正常系 | Markdown 目次 | §開発環境セットアップに `bash scripts/setup.sh` / `pwsh scripts/setup.ps1` 1 ステップ表記 + §AI 生成フッターの禁止節の存在 |
| TC-UT-005 | `lefthook.yml::fail_text` 全 7 箇所 | 正常系 | YAML + 文字列照合 | 7 箇所（fmt-check/lint/typecheck/audit-secrets/test/convco/no-ai-footer）全てが MSG-DW-001/002/014/010/003/004/013 確定文言と文字単位で一致、`{variables}` / `{files}` 等の動的展開が含まれない（T7 対策） |
| TC-UT-006 | `.github/CODEOWNERS` | 正常系 | grep | `/lefthook.yml` / `/justfile` / `/scripts/setup.sh` / `/scripts/setup.ps1` / `/scripts/ci/` の 5 パスが `@kkm-horikawa` 所有で登録 |
| TC-UT-007 | `CONTRIBUTING.md §Secret 混入時の緊急対応` | 正常系 | Markdown 節抽出 + 3 項目 grep | (a) 該当キーを発行元で即 revoke (b) **`git filter-repo --path <file> --invert-paths` の具体コマンド + feature ブランチ限定 force-push + `main`/`develop` への force-push 禁止の明記** (c) **GitHub Support への cache purge 依頼と secret scanning alert の resolve の明記** — 3 項目全てが存在（Q-3） |
| TC-UT-008 | `audit-pin-sync.sh` positive | 正常系 | setup.sh / setup.ps1 が同期済み | exit 0、`[OK] pin 定数の sh/ps1 同期を確認しました（30 件）`（5 ツール × 5 プラットフォーム + 5 VERSION）|
| TC-UT-009 | `audit-pin-sync.sh` negative | 異常系 | 30 定数の 1 箇所を意図的に乖離 | exit 1、`[FAIL] <VAR> が setup.sh / setup.ps1 で乖離しています` / 2 ファイルの値が diff 表示 |
| TC-UT-010 | `justfile::fmt-check` 単体 | 異常系 | format 違反 factory（Python + TS 両方） | exit 非 0（`ruff format --check` / `biome format` の exit code を集約） |
| TC-UT-011 | `justfile::commit-msg-check` 単体 | 異常系 | convco が受理するメッセージ factory + 受理しないメッセージ factory | convco の実 CLI（`check --from-stdin --strip`）が受理する引数形式で呼ばれていること。**存在しないサブコマンドで exit 2 を返さないこと** |
| TC-UT-012 | `justfile::audit-secrets` 単体 | 異常系 | 実在 AWS キーパターン factory | `gitleaks protect --staged --no-banner` が exit 1 |
| TC-UT-013 | `setup.{sh,ps1}::sha256_of / Get-Sha256` + ピン照合 | 異常系 | 改ざんバイナリ factory | SHA256 不一致で exit 1 + MSG-DW-012、一時ファイル削除 |
| TC-UT-014 | `justfile::commit-msg-no-ai-footer` P1 | 異常系 | `🤖 + Generated with + Claude` を含むファイル factory（大小文字・改行位置バリエーション） | 全バリエーションで exit 1 |
| TC-UT-015 | 同 P2 | 異常系 | `Co-Authored-By: + @anthropic.com` ドメイン factory（大小文字・トレーラ前後空白バリエーション） | 全バリエーションで exit 1 |
| TC-UT-016 | 同 P3 | 異常系 | `Co-Authored-By: + \bClaude\b` factory（モデル名揺れ / Claude 単体） | 全バリエーションで exit 1。**注記**: `Co-Authored-By: Claude Shannon <...>` も P3 にヒットして reject される（設計意図通り） |
| TC-UT-017 | ピン定数 ↔ upstream checksums 同期 | 正常系 | 5 ツール × checksums.json（要起票） | 25 SHA256 定数（5 ツール × 5 プラットフォーム）が upstream の公式 checksums.txt と**文字単位で一致** |
| TC-UT-018 | `justfile::typecheck` 単体 | 異常系 | 型エラー factory（Python + TS 両方） | exit 非 0（`pyright` / `tsc --noEmit` の exit code を集約） |

## カバレッジ基準

本 feature はランタイムコードを持たないため C0/C1 等の伝統的カバレッジ指標は取らない。代わりに以下のトレーサビリティ充足を必須とする:

- REQ-DW-001〜018 の各要件が最低 1 件のテストケース（ユニット/結合/E2E のいずれか）で検証されている
- MSG-DW-001〜014 の 14 文言が全て静的文字列で照合されている（TC-UT-005 + TC-E2E 各種）
- 受入基準 1〜13 の各々が最低 1 件の E2E テストケースで検証されている（Q-1〜Q-6 は domain/test-design.md §結合/ユニットテストケースで網羅）
- T1〜T9 の各脅威に対する対策が最低 1 件のテストケースで有効性を確認されている

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` / `gh run list` で 5 ワークフロー全てが緑であること
- ローカル: `bash scripts/setup.sh` → `just check-all` → `just --list` の順でワンショット確認
- Windows ローカル: `pwsh scripts/setup.ps1` → `just check-all`

## テストディレクトリ構造（将来）

```
tests/
  fixtures/
    characterization/
      raw/
        uv_releases_v<VER>_checksums.json           # 要起票 TBD-1
        just_releases_v<VER>_checksums.json         # 要起票 TBD-2
        convco_releases_v<VER>_checksums.json       # 要起票 TBD-3
        lefthook_releases_v<VER>_checksums.json     # 要起票 TBD-4
        gitleaks_releases_v<VER>_checksums.json     # 要起票 TBD-5
        convco_check_help.txt                       # 要起票 TBD-6
        gitleaks_default_rules_v<VER>.json          # 要起票 TBD-7
      schema/
        (raw の型 + 統計。factory 設計ソース)
  factories/
    secret_sample.py / platform_stub.sh / powershell_version.py  # 要起票 TBD-8, TBD-9
  e2e/
    (TC-E2E-001〜012 を bash / pwsh で実装、実コミット発行、証跡を保存)
  integration/
    (TC-IT-001〜011。raw fixture を使用)
  unit/
    (TC-UT-001〜018。factory を使用。YAML/bash/PowerShell の単体契約テスト)
```

**ただし言語慣習**: 本 feature はランタイムコードを追加しないため上記は**スクリプトテスト**として扱う。bakufu のドメインテスト（`backend/tests/` / `frontend/tests/`）とは独立したディレクトリに置く。

## 未決課題・要起票 characterization task

| # | タスク | 起票先 |
|---|-------|--------|
| TBD-1 | uv 最新版 upstream SHA256 の raw fixture 化 + CI 定期照合 | Issue（Sub-issue C 着手後） |
| TBD-2 | just 同上 | 同上 |
| TBD-3 | convco 同上 | 同上 |
| TBD-4 | lefthook 同上 | 同上 |
| TBD-5 | gitleaks 同上 | 同上 |
| TBD-6 | convco `check --help` の raw fixture 化 | 同上 |
| TBD-7 | gitleaks デフォルトルール allowlist の実観測固定 | 同上 |
| TBD-8 | PowerShell 5.1 / 7.x `$PSVersionTable` 出力の factory 化 | 同上 |
| TBD-9 | `uname -s` / `uname -m` 5 プラットフォーム × 2 arch の factory 化 | 同上 |
