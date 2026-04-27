#!/usr/bin/env bash
# scripts/setup.sh
# bakufu 開発環境セットアップ（Unix）。
# clone 直後に 1 回実行すれば、開発ツール一式と Git フックが配置される。
# 詳細設計: docs/features/dev-workflow/detailed-design.md §setup.sh ステップ契約

set -euo pipefail

# ───────────────────────────────────────────────────────────────
# ピン定数（5 ツール × 5 プラットフォーム + 5 VERSION = 30 値）
# 各値は upstream の公式 checksums から転記。
# convco のみ macOS バイナリが Universal/共通 zip 配布のため Intel/ARM 同値。
# 詳細設計: docs/features/dev-workflow/detailed-design.md §開発ツールバイナリの配布経路と SHA256 検証
# ───────────────────────────────────────────────────────────────

# uv 0.11.7 (Astral) — astral-sh/uv release
UV_VERSION="0.11.7"
UV_SHA256_LINUX_X86_64="6681d691eb7f9c00ac6a3af54252f7ab29ae72f0c8f95bdc7f9d1401c23ea868"
UV_SHA256_LINUX_ARM64="f2ee1cde9aabb4c6e43bd3f341dadaf42189a54e001e521346dc31547310e284"
UV_SHA256_DARWIN_X86_64="0a4bc8fcde4974ea3560be21772aeecab600a6f43fa6e58169f9fa7b3b71d302"
UV_SHA256_DARWIN_ARM64="66e37d91f839e12481d7b932a1eccbfe732560f42c1cfb89faddfa2454534ba8"
UV_SHA256_WINDOWS_X86_64="fe0c7815acf4fc45f8a5eff58ed3cf7ae2e15c3cf1dceadbd10c816ec1690cc1"

# just 1.50.0 — casey/just release SHA256SUMS
# Linux は musl 静的バイナリ、Darwin は -apple-darwin、Windows は -pc-windows-msvc.zip
JUST_VERSION="1.50.0"
JUST_SHA256_LINUX_X86_64="27e011cd6328fadd632e59233d2cf5f18460b8a8c4269acd324c1a8669f34db0"
JUST_SHA256_LINUX_ARM64="3beb4967ce05883cf09ac12d6d128166eb4c6d0b03eff74b61018a6880655d7d"
JUST_SHA256_DARWIN_X86_64="e4fa28fe63381ca32fad101e86d4a1da7cd2d34d1b080985a37ec9dc951922fe"
JUST_SHA256_DARWIN_ARM64="891262207663bff1aa422dbe799a76deae4064eaa445f14eb28aef7a388222cd"
JUST_SHA256_WINDOWS_X86_64="5dc713f049e174e22de41fd06292a26c9b90f2d37c1be9390d2082fe6928b376"

# convco v0.6.3 — convco/convco release（公式 checksums なし、release zip の SHA256 を直接ピン）
# 注: macOS は convco-macos.zip 1 ファイルしか配布されない（Intel/ARM 同 zip）。
# Universal Binary か Intel-only かは upstream で未明示のため、Intel Mac ARM Mac 双方で同 zip を取得する。
CONVCO_VERSION="0.6.3"
CONVCO_SHA256_LINUX_X86_64="9c9998df44cebdace0813d12297685261ff91497e742d7afbb57f147b4bd81ec"
CONVCO_SHA256_LINUX_ARM64="9dacefc6b2fb005d6f3c806a0c7abe0f87e510d97af69f2e1835997bea54be2d"
CONVCO_SHA256_DARWIN_X86_64="6cbe5984ca5d0c0c7fdac9419d8e7f060fb81d33c798e6ee84c211dbbf247e24"
CONVCO_SHA256_DARWIN_ARM64="6cbe5984ca5d0c0c7fdac9419d8e7f060fb81d33c798e6ee84c211dbbf247e24"
CONVCO_SHA256_WINDOWS_X86_64="4cdd9fc2292bf8038462db2873d8f5a67135486c98cb975d8bf373eb29315f13"

# lefthook v2.1.6 — evilmartians/lefthook release lefthook_checksums.txt
# 各プラットフォームの .gz アーカイブ（中身は単一バイナリ）の SHA256
LEFTHOOK_VERSION="2.1.6"
LEFTHOOK_SHA256_LINUX_X86_64="fab3d2715a922d9625c9024e6ffb6e1271edd613aa9b213c2049482cde8ae183"
LEFTHOOK_SHA256_LINUX_ARM64="3fd749629968beb7f7f68cd0fc7b1b5ab801a1ec2045892586005cce75944118"
LEFTHOOK_SHA256_DARWIN_X86_64="93c6d51823f94a7f26a2bbb84f59504378b178f55d6c90744169693ed3e89013"
LEFTHOOK_SHA256_DARWIN_ARM64="f07c97c32376749edb5b34179c16c6d87dd3e7ca0040aee911f38c821de0daab"
LEFTHOOK_SHA256_WINDOWS_X86_64="6704b01a72414affcc921740a7d6c621fe60c3082b291c9730900a2c6a352516"

# gitleaks v8.30.1 — gitleaks/gitleaks release gitleaks_8.30.1_checksums.txt
GITLEAKS_VERSION="8.30.1"
GITLEAKS_SHA256_LINUX_X86_64="551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
GITLEAKS_SHA256_LINUX_ARM64="e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080"
GITLEAKS_SHA256_DARWIN_X86_64="dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709"
GITLEAKS_SHA256_DARWIN_ARM64="b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5"
GITLEAKS_SHA256_WINDOWS_X86_64="d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e"

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
# GitHub Releases からのバイナリ取得（共通ヘルパ）
# ───────────────────────────────────────────────────────────────
download_to_tmp() {
    # $1=URL, prints tmpfile path on stdout
    local url=$1 tmpfile
    tmpfile=$(mktemp)
    if ! curl -sSfL "$url" -o "$tmpfile"; then
        rm -f "$tmpfile"
        echo "[FAIL] ダウンロード失敗: $url" >&2
        exit 1
    fi
    echo "$tmpfile"
}

# ───────────────────────────────────────────────────────────────
# Step 6. uv 導入
# ───────────────────────────────────────────────────────────────
install_uv() {
    if command -v uv >/dev/null 2>&1; then
        echo "[SKIP] uv は既にインストール済みです。"
        echo "バージョン: $(uv --version 2>&1 | head -1)"
        return 0
    fi
    local platform asset sha url tmpfile tmpdir
    platform=$(detect_platform)
    case "$platform" in
        LINUX_X86_64)   asset="uv-x86_64-unknown-linux-gnu.tar.gz";   sha=$UV_SHA256_LINUX_X86_64 ;;
        LINUX_ARM64)    asset="uv-aarch64-unknown-linux-gnu.tar.gz";  sha=$UV_SHA256_LINUX_ARM64 ;;
        DARWIN_X86_64)  asset="uv-x86_64-apple-darwin.tar.gz";        sha=$UV_SHA256_DARWIN_X86_64 ;;
        DARWIN_ARM64)   asset="uv-aarch64-apple-darwin.tar.gz";       sha=$UV_SHA256_DARWIN_ARM64 ;;
    esac
    url="https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/${asset}"
    tmpfile=$(download_to_tmp "$url")
    verify_sha256 "$tmpfile" "$sha"
    tmpdir=$(mktemp -d)
    tar -xzf "$tmpfile" -C "$tmpdir"
    # tar.gz は uv-{platform}/uv の構造
    find "$tmpdir" -name 'uv' -type f -exec mv {} "$BIN_DIR/uv" \;
    chmod +x "$BIN_DIR/uv"
    rm -rf "$tmpdir" "$tmpfile"
    echo "[OK] uv ${UV_VERSION} を $BIN_DIR/uv に配置しました。"
}

# ───────────────────────────────────────────────────────────────
# Step 7. just 導入
# ───────────────────────────────────────────────────────────────
install_just() {
    if command -v just >/dev/null 2>&1; then
        echo "[SKIP] just は既にインストール済みです。"
        echo "バージョン: $(just --version 2>&1)"
        return 0
    fi
    local platform asset sha url tmpfile tmpdir
    platform=$(detect_platform)
    case "$platform" in
        LINUX_X86_64)   asset="just-${JUST_VERSION}-x86_64-unknown-linux-musl.tar.gz";   sha=$JUST_SHA256_LINUX_X86_64 ;;
        LINUX_ARM64)    asset="just-${JUST_VERSION}-aarch64-unknown-linux-musl.tar.gz";  sha=$JUST_SHA256_LINUX_ARM64 ;;
        DARWIN_X86_64)  asset="just-${JUST_VERSION}-x86_64-apple-darwin.tar.gz";         sha=$JUST_SHA256_DARWIN_X86_64 ;;
        DARWIN_ARM64)   asset="just-${JUST_VERSION}-aarch64-apple-darwin.tar.gz";        sha=$JUST_SHA256_DARWIN_ARM64 ;;
    esac
    url="https://github.com/casey/just/releases/download/${JUST_VERSION}/${asset}"
    tmpfile=$(download_to_tmp "$url")
    verify_sha256 "$tmpfile" "$sha"
    tmpdir=$(mktemp -d)
    tar -xzf "$tmpfile" -C "$tmpdir"
    # just の tar.gz は root 直下に just バイナリ
    mv "$tmpdir/just" "$BIN_DIR/just"
    chmod +x "$BIN_DIR/just"
    rm -rf "$tmpdir" "$tmpfile"
    echo "[OK] just ${JUST_VERSION} を $BIN_DIR/just に配置しました。"
}

# ───────────────────────────────────────────────────────────────
# Step 8. convco 導入
# ───────────────────────────────────────────────────────────────
install_convco() {
    if command -v convco >/dev/null 2>&1; then
        echo "[SKIP] convco は既にインストール済みです。"
        echo "バージョン: $(convco --version 2>&1)"
        return 0
    fi
    local platform asset sha url tmpfile tmpdir
    platform=$(detect_platform)
    case "$platform" in
        LINUX_X86_64)   asset="convco-ubuntu.zip";          sha=$CONVCO_SHA256_LINUX_X86_64 ;;
        LINUX_ARM64)    asset="convco-ubuntu-aarch64.zip";  sha=$CONVCO_SHA256_LINUX_ARM64 ;;
        DARWIN_X86_64)  asset="convco-macos.zip";           sha=$CONVCO_SHA256_DARWIN_X86_64 ;;
        DARWIN_ARM64)   asset="convco-macos.zip";           sha=$CONVCO_SHA256_DARWIN_ARM64 ;;
    esac
    url="https://github.com/convco/convco/releases/download/v${CONVCO_VERSION}/${asset}"
    tmpfile=$(download_to_tmp "$url")
    verify_sha256 "$tmpfile" "$sha"
    tmpdir=$(mktemp -d)
    unzip -q "$tmpfile" -d "$tmpdir"
    mv "$tmpdir/convco" "$BIN_DIR/convco"
    chmod +x "$BIN_DIR/convco"
    rm -rf "$tmpdir" "$tmpfile"
    echo "[OK] convco ${CONVCO_VERSION} を $BIN_DIR/convco に配置しました。"
}

# ───────────────────────────────────────────────────────────────
# Step 9. lefthook 導入
# ───────────────────────────────────────────────────────────────
install_lefthook() {
    if command -v lefthook >/dev/null 2>&1; then
        echo "[SKIP] lefthook は既にインストール済みです。"
        echo "バージョン: $(lefthook version 2>&1)"
        return 0
    fi
    local platform asset sha url tmpfile
    platform=$(detect_platform)
    case "$platform" in
        LINUX_X86_64)   asset="lefthook_${LEFTHOOK_VERSION}_Linux_x86_64.gz";   sha=$LEFTHOOK_SHA256_LINUX_X86_64 ;;
        LINUX_ARM64)    asset="lefthook_${LEFTHOOK_VERSION}_Linux_arm64.gz";    sha=$LEFTHOOK_SHA256_LINUX_ARM64 ;;
        DARWIN_X86_64)  asset="lefthook_${LEFTHOOK_VERSION}_MacOS_x86_64.gz";   sha=$LEFTHOOK_SHA256_DARWIN_X86_64 ;;
        DARWIN_ARM64)   asset="lefthook_${LEFTHOOK_VERSION}_MacOS_arm64.gz";    sha=$LEFTHOOK_SHA256_DARWIN_ARM64 ;;
    esac
    url="https://github.com/evilmartians/lefthook/releases/download/v${LEFTHOOK_VERSION}/${asset}"
    tmpfile=$(download_to_tmp "$url")
    verify_sha256 "$tmpfile" "$sha"
    # .gz は単一バイナリの圧縮
    gunzip -c "$tmpfile" > "$BIN_DIR/lefthook"
    chmod +x "$BIN_DIR/lefthook"
    rm -f "$tmpfile"
    echo "[OK] lefthook ${LEFTHOOK_VERSION} を $BIN_DIR/lefthook に配置しました。"
}

# ───────────────────────────────────────────────────────────────
# Step 10. gitleaks 導入
# ───────────────────────────────────────────────────────────────
install_gitleaks() {
    if command -v gitleaks >/dev/null 2>&1; then
        echo "[SKIP] gitleaks は既にインストール済みです。"
        echo "バージョン: $(gitleaks version 2>&1)"
        return 0
    fi
    local platform asset sha url tmpfile tmpdir
    platform=$(detect_platform)
    case "$platform" in
        LINUX_X86_64)   asset="gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz";    sha=$GITLEAKS_SHA256_LINUX_X86_64 ;;
        LINUX_ARM64)    asset="gitleaks_${GITLEAKS_VERSION}_linux_arm64.tar.gz";  sha=$GITLEAKS_SHA256_LINUX_ARM64 ;;
        DARWIN_X86_64)  asset="gitleaks_${GITLEAKS_VERSION}_darwin_x64.tar.gz";   sha=$GITLEAKS_SHA256_DARWIN_X86_64 ;;
        DARWIN_ARM64)   asset="gitleaks_${GITLEAKS_VERSION}_darwin_arm64.tar.gz"; sha=$GITLEAKS_SHA256_DARWIN_ARM64 ;;
    esac
    url="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${asset}"
    tmpfile=$(download_to_tmp "$url")
    verify_sha256 "$tmpfile" "$sha"
    tmpdir=$(mktemp -d)
    tar -xzf "$tmpfile" -C "$tmpdir"
    mv "$tmpdir/gitleaks" "$BIN_DIR/gitleaks"
    chmod +x "$BIN_DIR/gitleaks"
    rm -rf "$tmpdir" "$tmpfile"
    echo "[OK] gitleaks ${GITLEAKS_VERSION} を $BIN_DIR/gitleaks に配置しました。"
}

# ───────────────────────────────────────────────────────────────
# PATH 拡張（GitHub Actions 互換 + ローカル）
# ───────────────────────────────────────────────────────────────
export PATH="$BIN_DIR:$PATH"
if [[ -n "${GITHUB_PATH:-}" ]]; then
    echo "$BIN_DIR" >> "$GITHUB_PATH"
fi

# Step 6-10. GitHub Releases から 5 ツール導入
install_uv
install_just
install_convco
install_lefthook
install_gitleaks

# Step 11. Python ツール導入（uv tool install、冪等）
# 別経路（apt/pip 等）でも導入済みなら uv tool は走らせない。bakufu は
# 既存 ruff/pyright/pip-audit を尊重する方針（PATH に居れば OK）。
install_python_tools() {
    if ! command -v uv >/dev/null 2>&1; then
        echo "[FAIL] uv の導入後に再実行してください。" >&2
        exit 1
    fi
    for tool in ruff pyright pip-audit; do
        if command -v "$tool" >/dev/null 2>&1; then
            echo "[SKIP] $tool は既にインストール済みです。"
        else
            uv tool install "$tool"
        fi
    done
}

# Step 12. Node ツール導入
# pnpm の global bin を PNPM_HOME に固定（未設定なら ~/.local/share/pnpm）。
install_node_tools() {
    corepack enable
    if [[ -z "${PNPM_HOME:-}" ]]; then
        export PNPM_HOME="${HOME}/.local/share/pnpm"
    fi
    mkdir -p "$PNPM_HOME"
    export PATH="${PNPM_HOME}:$PATH"
    if [[ -n "${GITHUB_PATH:-}" ]]; then
        echo "$PNPM_HOME" >> "$GITHUB_PATH"
    fi

    if command -v biome >/dev/null 2>&1; then
        echo "[SKIP] biome は既にインストール済みです。"
    else
        pnpm install -g @biomejs/biome
    fi
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

install_python_tools
install_node_tools
finalize_lefthook

# ───────────────────────────────────────────────────────────────
# Step 14. 完了ログ
# ───────────────────────────────────────────────────────────────
echo "[OK] Setup complete. Git フックが有効化されました。"
