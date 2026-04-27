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
# setup.sh と完全同期させること（audit-pin-sync.sh が機械的に検証）。
# 詳細設計: docs/features/dev-workflow/detailed-design.md §開発ツールバイナリの配布経路と SHA256 検証
# ───────────────────────────────────────────────────────────────

# uv 0.11.7 (Astral)
$UV_VERSION = "0.11.7"
$UV_SHA256_LINUX_X86_64 = "6681d691eb7f9c00ac6a3af54252f7ab29ae72f0c8f95bdc7f9d1401c23ea868"
$UV_SHA256_LINUX_ARM64 = "f2ee1cde9aabb4c6e43bd3f341dadaf42189a54e001e521346dc31547310e284"
$UV_SHA256_DARWIN_X86_64 = "0a4bc8fcde4974ea3560be21772aeecab600a6f43fa6e58169f9fa7b3b71d302"
$UV_SHA256_DARWIN_ARM64 = "66e37d91f839e12481d7b932a1eccbfe732560f42c1cfb89faddfa2454534ba8"
$UV_SHA256_WINDOWS_X86_64 = "fe0c7815acf4fc45f8a5eff58ed3cf7ae2e15c3cf1dceadbd10c816ec1690cc1"

# just 1.50.0
$JUST_VERSION = "1.50.0"
$JUST_SHA256_LINUX_X86_64 = "27e011cd6328fadd632e59233d2cf5f18460b8a8c4269acd324c1a8669f34db0"
$JUST_SHA256_LINUX_ARM64 = "3beb4967ce05883cf09ac12d6d128166eb4c6d0b03eff74b61018a6880655d7d"
$JUST_SHA256_DARWIN_X86_64 = "e4fa28fe63381ca32fad101e86d4a1da7cd2d34d1b080985a37ec9dc951922fe"
$JUST_SHA256_DARWIN_ARM64 = "891262207663bff1aa422dbe799a76deae4064eaa445f14eb28aef7a388222cd"
$JUST_SHA256_WINDOWS_X86_64 = "5dc713f049e174e22de41fd06292a26c9b90f2d37c1be9390d2082fe6928b376"

# convco v0.6.3 — macOS は Universal/共通 zip のため Intel/ARM 同値
$CONVCO_VERSION = "0.6.3"
$CONVCO_SHA256_LINUX_X86_64 = "9c9998df44cebdace0813d12297685261ff91497e742d7afbb57f147b4bd81ec"
$CONVCO_SHA256_LINUX_ARM64 = "9dacefc6b2fb005d6f3c806a0c7abe0f87e510d97af69f2e1835997bea54be2d"
$CONVCO_SHA256_DARWIN_X86_64 = "6cbe5984ca5d0c0c7fdac9419d8e7f060fb81d33c798e6ee84c211dbbf247e24"
$CONVCO_SHA256_DARWIN_ARM64 = "6cbe5984ca5d0c0c7fdac9419d8e7f060fb81d33c798e6ee84c211dbbf247e24"
$CONVCO_SHA256_WINDOWS_X86_64 = "4cdd9fc2292bf8038462db2873d8f5a67135486c98cb975d8bf373eb29315f13"

# lefthook v2.1.6
$LEFTHOOK_VERSION = "2.1.6"
$LEFTHOOK_SHA256_LINUX_X86_64 = "fab3d2715a922d9625c9024e6ffb6e1271edd613aa9b213c2049482cde8ae183"
$LEFTHOOK_SHA256_LINUX_ARM64 = "3fd749629968beb7f7f68cd0fc7b1b5ab801a1ec2045892586005cce75944118"
$LEFTHOOK_SHA256_DARWIN_X86_64 = "93c6d51823f94a7f26a2bbb84f59504378b178f55d6c90744169693ed3e89013"
$LEFTHOOK_SHA256_DARWIN_ARM64 = "f07c97c32376749edb5b34179c16c6d87dd3e7ca0040aee911f38c821de0daab"
$LEFTHOOK_SHA256_WINDOWS_X86_64 = "6704b01a72414affcc921740a7d6c621fe60c3082b291c9730900a2c6a352516"

# gitleaks v8.30.1
$GITLEAKS_VERSION = "8.30.1"
$GITLEAKS_SHA256_LINUX_X86_64 = "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
$GITLEAKS_SHA256_LINUX_ARM64 = "e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080"
$GITLEAKS_SHA256_DARWIN_X86_64 = "dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709"
$GITLEAKS_SHA256_DARWIN_ARM64 = "b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5"
$GITLEAKS_SHA256_WINDOWS_X86_64 = "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e"

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
