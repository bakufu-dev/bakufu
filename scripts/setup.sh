#!/usr/bin/env bash
# scripts/setup.sh
# bakufu 開発環境セットアップ（Unix）。
# clone 直後に 1 回実行すれば、開発ツール一式と Git フックが配置される。
# 詳細設計: docs/features/dev-workflow/detailed-design.md §setup.sh ステップ契約

set -euo pipefail

# ───────────────────────────────────────────────────────────────
# ピン定数（5 ツール × 5 プラットフォーム + 5 VERSION = 30 値）
# 値の確定は Sub-issue C にて upstream の checksums.txt から転記する。
# 空のままだと Fail Fast（REQ-DW-015、設計時凍結）。
# ───────────────────────────────────────────────────────────────
UV_VERSION=""
UV_SHA256_LINUX_X86_64=""
UV_SHA256_LINUX_ARM64=""
UV_SHA256_DARWIN_X86_64=""
UV_SHA256_DARWIN_ARM64=""
UV_SHA256_WINDOWS_X86_64=""

JUST_VERSION=""
JUST_SHA256_LINUX_X86_64=""
JUST_SHA256_LINUX_ARM64=""
JUST_SHA256_DARWIN_X86_64=""
JUST_SHA256_DARWIN_ARM64=""
JUST_SHA256_WINDOWS_X86_64=""

CONVCO_VERSION=""
CONVCO_SHA256_LINUX_X86_64=""
CONVCO_SHA256_LINUX_ARM64=""
CONVCO_SHA256_DARWIN_X86_64=""
CONVCO_SHA256_DARWIN_ARM64=""
CONVCO_SHA256_WINDOWS_X86_64=""

LEFTHOOK_VERSION=""
LEFTHOOK_SHA256_LINUX_X86_64=""
LEFTHOOK_SHA256_LINUX_ARM64=""
LEFTHOOK_SHA256_DARWIN_X86_64=""
LEFTHOOK_SHA256_DARWIN_ARM64=""
LEFTHOOK_SHA256_WINDOWS_X86_64=""

GITLEAKS_VERSION=""
GITLEAKS_SHA256_LINUX_X86_64=""
GITLEAKS_SHA256_LINUX_ARM64=""
GITLEAKS_SHA256_DARWIN_X86_64=""
GITLEAKS_SHA256_DARWIN_ARM64=""
GITLEAKS_SHA256_WINDOWS_X86_64=""

# ───────────────────────────────────────────────────────────────
# 引数解析
# ───────────────────────────────────────────────────────────────
TOOLS_ONLY=false
for arg in "$@"; do
    case "$arg" in
        --tools-only) TOOLS_ONLY=true ;;
        -h|--help)
            cat <<EOF
Usage: bash scripts/setup.sh [--tools-only]

Options:
  --tools-only  Skip 'lefthook install' (used by CI to avoid writing .git/hooks/).
EOF
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Usage: bash scripts/setup.sh [--tools-only]" >&2
            exit 2
            ;;
    esac
done

# ───────────────────────────────────────────────────────────────
# Step 4. .git/ 検査（リポジトリルート確認）
# ───────────────────────────────────────────────────────────────
if [[ ! -d .git ]]; then
    echo "[FAIL] .git/ ディレクトリが見つかりません。リポジトリルートで実行してください。" >&2
    echo "現在のディレクトリ: $(pwd)" >&2
    exit 1
fi

# ───────────────────────────────────────────────────────────────
# Step 5. 言語ランタイム検査
# ───────────────────────────────────────────────────────────────
check_python_node() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "[FAIL] Python 3.12+ または Node 20+ が未検出です。" >&2
        echo "次のコマンド: README.md §動作環境のセットアップ手順を参照してください。" >&2
        exit 1
    fi
    local py_version
    py_version=$(python3 --version 2>&1 | awk '{print $2}')
    if ! printf '%s\n' "$py_version" | grep -qE '^3\.(1[2-9]|[2-9][0-9])'; then
        echo "[FAIL] Python 3.12+ または Node 20+ が未検出です。" >&2
        echo "次のコマンド: README.md §動作環境のセットアップ手順を参照してください。" >&2
        exit 1
    fi

    if ! command -v node >/dev/null 2>&1; then
        echo "[FAIL] Python 3.12+ または Node 20+ が未検出です。" >&2
        echo "次のコマンド: README.md §動作環境のセットアップ手順を参照してください。" >&2
        exit 1
    fi
    local node_version
    node_version=$(node --version | sed 's/^v//')
    local node_major
    node_major=${node_version%%.*}
    if [[ "$node_major" -lt 20 ]]; then
        echo "[FAIL] Python 3.12+ または Node 20+ が未検出です。" >&2
        echo "次のコマンド: README.md §動作環境のセットアップ手順を参照してください。" >&2
        exit 1
    fi
}
check_python_node

# ───────────────────────────────────────────────────────────────
# ピン定数の空チェック（Fail Fast）
# ───────────────────────────────────────────────────────────────
check_pins() {
    local missing=0
    for var in UV_VERSION JUST_VERSION CONVCO_VERSION LEFTHOOK_VERSION GITLEAKS_VERSION; do
        if [[ -z "${!var}" ]]; then
            missing=$((missing + 1))
        fi
    done
    if [[ $missing -gt 0 ]]; then
        echo "[FAIL] 開発ツールバージョンピン定数が未確定です（${missing} 件）。" >&2
        echo "次のコマンド: docs/features/dev-workflow/detailed-design.md §ピン同期の担保 を参照し、" >&2
        echo "             upstream の checksums.txt から転記してください（Sub-issue C 範囲）。" >&2
        exit 1
    fi
}
check_pins

# ───────────────────────────────────────────────────────────────
# プラットフォーム検出
# ───────────────────────────────────────────────────────────────
detect_platform() {
    local os arch
    os=$(uname -s)
    arch=$(uname -m)
    case "$os/$arch" in
        Linux/x86_64)  echo "LINUX_X86_64" ;;
        Linux/aarch64) echo "LINUX_ARM64" ;;
        Darwin/x86_64) echo "DARWIN_X86_64" ;;
        Darwin/arm64)  echo "DARWIN_ARM64" ;;
        *)
            echo "[FAIL] 未サポートのプラットフォーム: $os/$arch" >&2
            exit 1
            ;;
    esac
}

# ───────────────────────────────────────────────────────────────
# バイナリ取得 + SHA256 検証 + 配置（汎用関数）
# ───────────────────────────────────────────────────────────────
BIN_DIR="${HOME}/.local/bin"
mkdir -p "$BIN_DIR"

verify_sha256() {
    local file=$1 expected=$2
    local actual
    actual=$(sha256sum "$file" | awk '{print $1}')
    if [[ "$actual" != "$expected" ]]; then
        rm -f "$file"
        echo "[FAIL] バイナリの SHA256 検証に失敗しました。サプライチェーン改ざんの可能性があります。" >&2
        echo "次のコマンド: 一時ファイルを削除後にネットワーク状況を確認し再実行。繰り返し失敗する場合は Issue で報告してください。" >&2
        echo "  expected: $expected" >&2
        echo "  actual:   $actual" >&2
        exit 1
    fi
}

# ───────────────────────────────────────────────────────────────
# 各ツールの GitHub Releases からの導入は Sub-issue C で実装する。
# 本スケルトンでは、ピン定数の確定後に以下を実装する想定:
#
#   install_uv()       - astral-sh/uv の OS/arch に対応した tar.gz/zip を取得
#   install_just()     - casey/just
#   install_convco()   - convco/convco
#   install_lefthook() - evilmartians/lefthook
#   install_gitleaks() - gitleaks/gitleaks
#
# 各関数は以下を共通実装:
#   1. command -v で既存検査 → あれば MSG-DW-006 を表示してスキップ
#   2. プラットフォームに対応した URL を合成
#   3. curl -sSfL でダウンロード
#   4. verify_sha256 でピン値と照合
#   5. tar/unzip で展開し、$BIN_DIR に配置
#   6. chmod +x
# ───────────────────────────────────────────────────────────────

# Step 11. Python ツール導入（uv tool install）
install_python_tools() {
    if ! command -v uv >/dev/null 2>&1; then
        echo "[FAIL] uv の導入後に再実行してください。" >&2
        exit 1
    fi
    uv tool install ruff
    uv tool install pyright
    uv tool install pip-audit
}

# Step 12. Node ツール導入
install_node_tools() {
    corepack enable
    pnpm install -g @biomejs/biome osv-scanner
}

# Step 13. lefthook install（--tools-only でなければ）
finalize_lefthook() {
    if [[ "$TOOLS_ONLY" == true ]]; then
        return 0
    fi
    if ! command -v lefthook >/dev/null 2>&1; then
        echo "[FAIL] lefthook の導入後に再実行してください。" >&2
        exit 1
    fi
    lefthook install
}

# 実装の本体（ピン値が空の場合は上記 check_pins で既に exit 済み）
# 5 ツールのインストール本体は Sub-issue C で実装。本スケルトンではピン未確定により到達しない。
install_python_tools
install_node_tools
finalize_lefthook

# ───────────────────────────────────────────────────────────────
# Step 14. 完了ログ
# ───────────────────────────────────────────────────────────────
echo "[OK] Setup complete. Git フックが有効化されました。"
