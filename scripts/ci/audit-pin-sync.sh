#!/usr/bin/env bash
# scripts/ci/audit-pin-sync.sh
# setup.sh と setup.ps1 のピン定数（VERSION + SHA256_*）が同期しているかを検証する。
# 乖離があれば exit 非 0、Windows 開発者だけ別バイナリを引く事故（T4 脅威のバリエーション）を防止。
# 詳細設計: docs/features/dev-workflow/detailed-design.md §ピン同期の担保

set -euo pipefail

readonly SH="scripts/setup.sh"
readonly PS1="scripts/setup.ps1"

if [[ ! -f "$SH" ]]; then
    echo "[FAIL] $SH が見つかりません。リポジトリルートで実行してください。" >&2
    exit 1
fi
if [[ ! -f "$PS1" ]]; then
    echo "[FAIL] $PS1 が見つかりません。リポジトリルートで実行してください。" >&2
    exit 1
fi

# 検証対象の 30 定数（5 ツール × (1 VERSION + 5 SHA256_*)）
readonly TOOLS=(UV JUST CONVCO LEFTHOOK GITLEAKS)
readonly PLATFORMS=(LINUX_X86_64 LINUX_ARM64 DARWIN_X86_64 DARWIN_ARM64 WINDOWS_X86_64)

constants=()
for tool in "${TOOLS[@]}"; do
    constants+=("${tool}_VERSION")
    for platform in "${PLATFORMS[@]}"; do
        constants+=("${tool}_SHA256_${platform}")
    done
done

extract_sh() {
    local name=$1
    grep -oE "^${name}=\"[^\"]*\"" "$SH" 2>/dev/null | head -1 | sed 's/^[^=]*="\(.*\)"$/\1/' || echo ""
}

extract_ps1() {
    local name=$1
    grep -oE "^\\\$${name} *= *\"[^\"]*\"" "$PS1" 2>/dev/null | head -1 | sed 's/^[^=]*= *"\(.*\)"$/\1/' || echo ""
}

errors=0
checked=0
for name in "${constants[@]}"; do
    sh_val=$(extract_sh "$name")
    ps_val=$(extract_ps1 "$name")
    checked=$((checked + 1))
    if [[ "$sh_val" != "$ps_val" ]]; then
        echo "[FAIL] $name が setup.sh / setup.ps1 で乖離しています" >&2
        echo "  setup.sh:  '$sh_val'" >&2
        echo "  setup.ps1: '$ps_val'" >&2
        errors=$((errors + 1))
    fi
done

if [[ $errors -gt 0 ]]; then
    echo "" >&2
    echo "$errors / $checked 件の定数で乖離を検出しました。" >&2
    exit 1
fi

echo "[OK] pin 定数の sh/ps1 同期を確認しました（${checked} 件）"
