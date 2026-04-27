# scripts/setup.ps1
# bakufu 開発環境セットアップ（Windows、PowerShell 7+ 必須）。
# clone 直後に 1 回実行すれば、開発ツール一式と Git フックが配置される。
# 詳細設計: docs/features/dev-workflow/detailed-design.md §setup.ps1 ステップ契約

[CmdletBinding()]
param(
    [switch]$ToolsOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# ───────────────────────────────────────────────────────────────
# Step 0. PowerShell 7+ 検査（確定 B、REQ-DW-014）
# ───────────────────────────────────────────────────────────────
if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Error -Message @"
[FAIL] PowerShell 7 以上が必要です（検出: $($PSVersionTable.PSVersion)）。
次のコマンド: winget install Microsoft.PowerShell
"@
    exit 1
}

# ───────────────────────────────────────────────────────────────
# ピン定数（5 ツール × 5 プラットフォーム + 5 VERSION = 30 値）
# 値の確定は Sub-issue C にて upstream の checksums.txt から転記する。
# 空のままだと Fail Fast（REQ-DW-015、設計時凍結）。
# setup.sh と完全同期させること（audit-pin-sync.sh が機械的に検証）。
# ───────────────────────────────────────────────────────────────
$UV_VERSION = ""
$UV_SHA256_LINUX_X86_64 = ""
$UV_SHA256_LINUX_ARM64 = ""
$UV_SHA256_DARWIN_X86_64 = ""
$UV_SHA256_DARWIN_ARM64 = ""
$UV_SHA256_WINDOWS_X86_64 = ""

$JUST_VERSION = ""
$JUST_SHA256_LINUX_X86_64 = ""
$JUST_SHA256_LINUX_ARM64 = ""
$JUST_SHA256_DARWIN_X86_64 = ""
$JUST_SHA256_DARWIN_ARM64 = ""
$JUST_SHA256_WINDOWS_X86_64 = ""

$CONVCO_VERSION = ""
$CONVCO_SHA256_LINUX_X86_64 = ""
$CONVCO_SHA256_LINUX_ARM64 = ""
$CONVCO_SHA256_DARWIN_X86_64 = ""
$CONVCO_SHA256_DARWIN_ARM64 = ""
$CONVCO_SHA256_WINDOWS_X86_64 = ""

$LEFTHOOK_VERSION = ""
$LEFTHOOK_SHA256_LINUX_X86_64 = ""
$LEFTHOOK_SHA256_LINUX_ARM64 = ""
$LEFTHOOK_SHA256_DARWIN_X86_64 = ""
$LEFTHOOK_SHA256_DARWIN_ARM64 = ""
$LEFTHOOK_SHA256_WINDOWS_X86_64 = ""

$GITLEAKS_VERSION = ""
$GITLEAKS_SHA256_LINUX_X86_64 = ""
$GITLEAKS_SHA256_LINUX_ARM64 = ""
$GITLEAKS_SHA256_DARWIN_X86_64 = ""
$GITLEAKS_SHA256_DARWIN_ARM64 = ""
$GITLEAKS_SHA256_WINDOWS_X86_64 = ""

# ───────────────────────────────────────────────────────────────
# Step 4. .git/ 検査（リポジトリルート確認）
# ───────────────────────────────────────────────────────────────
if (-not (Test-Path .git)) {
    Write-Error -Message @"
[FAIL] .git/ ディレクトリが見つかりません。リポジトリルートで実行してください。
現在のディレクトリ: $(Get-Location)
"@
    exit 1
}

# ───────────────────────────────────────────────────────────────
# Step 5. 言語ランタイム検査
# ───────────────────────────────────────────────────────────────
function Test-Runtime {
    $py = Get-Command python3 -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
    if (-not $py) {
        Write-Error -Message @"
[FAIL] Python 3.12+ または Node 20+ が未検出です。
次のコマンド: README.md §動作環境のセットアップ手順を参照してください。
"@
        exit 1
    }
    $pyVersionOutput = & $py --version 2>&1
    if ($pyVersionOutput -notmatch 'Python 3\.(1[2-9]|[2-9][0-9])') {
        Write-Error -Message @"
[FAIL] Python 3.12+ または Node 20+ が未検出です。
次のコマンド: README.md §動作環境のセットアップ手順を参照してください。
"@
        exit 1
    }

    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) {
        Write-Error -Message @"
[FAIL] Python 3.12+ または Node 20+ が未検出です。
次のコマンド: README.md §動作環境のセットアップ手順を参照してください。
"@
        exit 1
    }
    $nodeVersion = (& node --version) -replace '^v', ''
    $nodeMajor = [int]($nodeVersion -split '\.')[0]
    if ($nodeMajor -lt 20) {
        Write-Error -Message @"
[FAIL] Python 3.12+ または Node 20+ が未検出です。
次のコマンド: README.md §動作環境のセットアップ手順を参照してください。
"@
        exit 1
    }
}
Test-Runtime

# ───────────────────────────────────────────────────────────────
# ピン定数の空チェック（Fail Fast）
# ───────────────────────────────────────────────────────────────
function Test-Pins {
    $missing = @()
    foreach ($name in @('UV_VERSION', 'JUST_VERSION', 'CONVCO_VERSION', 'LEFTHOOK_VERSION', 'GITLEAKS_VERSION')) {
        $val = (Get-Variable -Name $name -ValueOnly)
        if ([string]::IsNullOrEmpty($val)) {
            $missing += $name
        }
    }
    if ($missing.Count -gt 0) {
        Write-Error -Message @"
[FAIL] 開発ツールバージョンピン定数が未確定です（$($missing.Count) 件）。
次のコマンド: docs/features/dev-workflow/detailed-design.md §ピン同期の担保 を参照し、
             upstream の checksums.txt から転記してください（Sub-issue C 範囲）。
"@
        exit 1
    }
}
Test-Pins

# ───────────────────────────────────────────────────────────────
# 各ツールの GitHub Releases からの導入は Sub-issue C で実装する。
# 本スケルトンでは、ピン定数の確定後に以下を実装する想定:
#
#   Install-Uv       - astral-sh/uv の OS/arch に対応した tar.gz/zip を取得
#   Install-Just     - casey/just
#   Install-Convco   - convco/convco
#   Install-Lefthook - evilmartians/lefthook
#   Install-Gitleaks - gitleaks/gitleaks
#
# 各関数は以下を共通実装:
#   1. Get-Command で既存検査 → あれば MSG-DW-006 を表示してスキップ
#   2. プラットフォームに対応した URL を合成
#   3. Invoke-WebRequest でダウンロード
#   4. (Get-FileHash -Algorithm SHA256).Hash で実測値を取得し、ピン値と -eq 比較
#   5. Expand-Archive で展開し、$env:USERPROFILE\.local\bin\ に配置
# ───────────────────────────────────────────────────────────────

$BinDir = Join-Path $env:USERPROFILE '.local\bin'
if (-not (Test-Path $BinDir)) {
    New-Item -ItemType Directory -Path $BinDir | Out-Null
}

# Step 11. Python ツール導入
function Install-PythonTools {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Error '[FAIL] uv の導入後に再実行してください。'
        exit 1
    }
    & uv tool install ruff
    & uv tool install pyright
    & uv tool install pip-audit
}

# Step 12. Node ツール導入
function Install-NodeTools {
    & corepack enable
    & pnpm install -g '@biomejs/biome' 'osv-scanner'
}

# Step 13. lefthook install（--ToolsOnly でなければ）
function Invoke-LefthookInstall {
    if ($ToolsOnly) { return }
    if (-not (Get-Command lefthook -ErrorAction SilentlyContinue)) {
        Write-Error '[FAIL] lefthook の導入後に再実行してください。'
        exit 1
    }
    & lefthook install
}

Install-PythonTools
Install-NodeTools
Invoke-LefthookInstall

# ───────────────────────────────────────────────────────────────
# Step 14. 完了ログ
# ───────────────────────────────────────────────────────────────
Write-Host '[OK] Setup complete. Git フックが有効化されました。'
