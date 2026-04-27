#!/usr/bin/env bash
# scripts/ci/check_masking_columns.sh
# CI 三層防衛 (1/3): masking 対象カラムが MaskedJSONEncoded / MaskedText 型で
# 宣言されているか、また「対象なし」と凍結されたテーブルが Masked* を
# 含んでいないかを strict 検証する。
#
# 真実源: docs/architecture/domain-model/storage.md §逆引き表
# 詳細設計: docs/features/persistence-foundation/requirements-analysis.md §確定 R1-D 補強条項
#           docs/features/empire-repository/detailed-design.md §確定 E (Empire 拡張、
#           「対象なし」明示登録テンプレート)
#
# 後続 Repository PR がカラムを追加して MaskedJSONEncoded / MaskedText 型を
# 指定し忘れた瞬間、このスクリプトが CI を落として漏洩を未然に防ぐ。
# 対象なしと凍結されたテーブルに Masked* が混入したら同じく CI 落下。
# 動的生成カラム / __table_args__ 経由のメタデータ追加は本 grep をすり抜けるが、
# layer (2) の SQLAlchemy metadata 走査テスト (test_masking_columns.py) で
# 補完する。

set -euo pipefail

readonly TABLES_DIR="backend/src/bakufu/infrastructure/persistence/sqlite/tables"

if [[ ! -d "$TABLES_DIR" ]]; then
    echo "[FAIL] $TABLES_DIR が見つかりません。リポジトリルートで実行してください。" >&2
    exit 1
fi

# Layer 1-A: 正のチェック ─ masking 対象カラムは Masked* で宣言されること。
# 逆引き表から「カラム名 → 期待される TypeDecorator 型」を抽出。
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

# Layer 1-B: 負のチェック ─ 「masking 対象なし」と凍結された Aggregate
# テーブル群に Masked* TypeDecorator が混入していないこと。
# storage.md §逆引き表「Empire 関連カラム: masking 対象なし」を強制。
# 後続 Aggregate Repository PR は同方針で本リストに追加する。
readonly NO_MASK_FILES=(
    "${TABLES_DIR}/empires.py"
    "${TABLES_DIR}/empire_room_refs.py"
    "${TABLES_DIR}/empire_agent_refs.py"
)

for file in "${NO_MASK_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        # ファイル未作成（後続 PR が追加予定）。スキップ。
        continue
    fi
    leaks=$(grep -nE "Masked(JSONEncoded|Text)" "$file" || true)
    if [[ -n "$leaks" ]]; then
        echo "[FAIL] no-mask table file declares a Masked* TypeDecorator: $file" >&2
        echo "$leaks" >&2
        echo "       Next: this table is registered as 'masking 対象なし' in" >&2
        echo "       docs/architecture/domain-model/storage.md §逆引き表; either" >&2
        echo "       remove the Masked* type or update the table entry first." >&2
        violations=$((violations + 1))
    fi
done

if [[ "$violations" -gt 0 ]]; then
    echo "[FAIL] check_masking_columns: ${violations} violation(s) detected" >&2
    exit 1
fi

echo "[OK] check_masking_columns: positive (Masked* required) + negative (no-mask) checks passed"
