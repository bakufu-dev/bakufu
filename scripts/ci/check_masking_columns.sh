#!/usr/bin/env bash
# scripts/ci/check_masking_columns.sh
# CI 三層防衛 (1/3): masking 対象カラムが MaskedJSONEncoded / MaskedText 型で
# 宣言されているかを strict 検証する。
#
# 真実源: docs/architecture/domain-model/storage.md §逆引き表
# 詳細設計: docs/features/persistence-foundation/requirements-analysis.md §確定 R1-D 補強条項
#
# 後続 Repository PR がカラムを追加して MaskedJSONEncoded / MaskedText 型を
# 指定し忘れた瞬間、このスクリプトが CI を落として漏洩を未然に防ぐ。
# 動的生成カラム / __table_args__ 経由のメタデータ追加は本 grep をすり抜けるが、
# layer (2) の SQLAlchemy metadata 走査テスト (test_masking_columns.py) で
# 補完する。

set -euo pipefail

readonly TABLES_DIR="backend/src/bakufu/infrastructure/persistence/sqlite/tables"

if [[ ! -d "$TABLES_DIR" ]]; then
    echo "[FAIL] $TABLES_DIR が見つかりません。リポジトリルートで実行してください。" >&2
    exit 1
fi

# 逆引き表から「カラム名 → 期待される TypeDecorator 型」を抽出。
# tables/ 配下に該当カラム名を持つ行が見つかったら、同じ行に期待型が
# 含まれることを検証する。
#
# フォーマット: "<column>:<expected_type>"
readonly EXPECTED_TYPES=(
    "args_json:MaskedJSONEncoded"
    "error_text:MaskedText"
    "payload_json:MaskedJSONEncoded"
    "last_error:MaskedText"
    "cmd:MaskedText"
    # 後続 Repository PR が追加するカラム（テーブルファイル未存在の間は no-op）
    "prompt_body:MaskedText"
    "prefix_markdown:MaskedText"
    "body_markdown:MaskedText"
)

violations=0
for entry in "${EXPECTED_TYPES[@]}"; do
    column="${entry%%:*}"
    expected="${entry##*:}"

    # ``mapped_column(<TYPE>...`` のパターンを探す。コメント行 (`#` 始まり)
    # は除外。docstring 内の説明的な言及も除外（行頭に空白後 `#` か `"""`）。
    matches=$(grep -rEn "^\s*${column}\s*:\s*Mapped" "$TABLES_DIR" || true)

    if [[ -z "$matches" ]]; then
        # カラム宣言がまだ存在しない（後続 PR で追加予定）。スキップ。
        continue
    fi

    while IFS= read -r line; do
        if [[ -z "$line" ]]; then
            continue
        fi
        if [[ "$line" == *"$expected"* ]]; then
            continue
        fi
        echo "[FAIL] masking column '${column}' is declared without ${expected}:" >&2
        echo "       ${line}" >&2
        echo "       Next: change the column type to ${expected} per docs/architecture/domain-model/storage.md §逆引き表." >&2
        violations=$((violations + 1))
    done <<< "$matches"
done

if [[ "$violations" -gt 0 ]]; then
    echo "[FAIL] check_masking_columns: ${violations} violation(s) detected" >&2
    exit 1
fi

echo "[OK] check_masking_columns: all masking-target columns declare the correct Masked* TypeDecorator"
