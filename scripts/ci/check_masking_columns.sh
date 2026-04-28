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
    # Workflow Repository (PR #31): notify_channels_json holds
    # Discord webhook URLs that include the secret token segment.
    # docs/features/workflow-repository/detailed-design.md §確定 H.
    "notify_channels_json:MaskedJSONEncoded"
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
    # Workflow Repository (PR #31): only workflow_stages.notify_channels_json
    # is masked; the root + transitions tables carry no Schneier #6
    # secret categories.
    "${TABLES_DIR}/workflows.py"
    "${TABLES_DIR}/workflow_transitions.py"
    # Agent Repository (PR #32): only agents.prompt_body is masked
    # (Schneier 申し送り #3 实適用); the side tables carry no secret
    # semantics.
    "${TABLES_DIR}/agent_providers.py"
    "${TABLES_DIR}/agent_skills.py"
    # Room Repository (PR #33): only rooms.prompt_kit_prefix_markdown is
    # masked (room §確定 G 実適用); the room_members side table carries no
    # secret semantics.
    "${TABLES_DIR}/room_members.py"
    # Task Repository (PR #35, detailed-design.md §確定 R1-E):
    # task_assigned_agents / deliverable_attachments carry no secret semantics.
    # tasks / deliverables are registered in PARTIAL_MASK_FILES (each has exactly
    # one masked column). conversations / conversation_messages are §BUG-TR-002
    # 凍結済みのため除外。
    "${TABLES_DIR}/task_assigned_agents.py"
    "${TABLES_DIR}/deliverable_attachments.py"
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

# Layer 1-C: 過剰マスキング防止 ─ partially-masked テーブルで指定の
# カラム以外に Masked* が混入していないこと。各ファイルに対し
# 「許可カラムが期待型で 1 つ宣言されている」+「他カラムに Masked* が
# 一切登場しない」の両方を assert する。
#
# 登録されている partial-mask テーブル:
#   * Workflow Repository (PR #31, detailed-design.md §確定 E):
#     workflow_stages.notify_channels_json だけが MaskedJSONEncoded、
#     他カラムは JSONEncoded / String / Text に閉じる。
#   * Agent Repository (PR #32, detailed-design.md §確定 E):
#     agents.prompt_body だけが MaskedText、他カラムは String / Boolean
#     に閉じる。Schneier 申し送り #3 实適用の grep 物理保証層。
#
# フォーマット: "<file>:<allowed_column>:<expected_type>"
readonly PARTIAL_MASK_FILES=(
    "${TABLES_DIR}/workflow_stages.py:notify_channels_json:MaskedJSONEncoded"
    "${TABLES_DIR}/agents.py:prompt_body:MaskedText"
    # Room Repository (PR #33, detailed-design.md §確定 R1-E):
    # rooms.prompt_kit_prefix_markdown だけが MaskedText (room §確定 G 実適用)、
    # 他カラムは String / Boolean / Text に閉じる。
    "${TABLES_DIR}/rooms.py:prompt_kit_prefix_markdown:MaskedText"
    # Directive Repository (PR #34, detailed-design.md §確定 R1-E):
    # directives.text だけが MaskedText (directive §確定 G 実適用)、
    # 他カラムは UUIDStr / UTCDateTime に閉じる。
    "${TABLES_DIR}/directives.py:text:MaskedText"
    # Task Repository (PR #35, detailed-design.md §確定 R1-E):
    # tasks.last_error だけが MaskedText（BLOCKED 隔離理由に secret 混入の可能性）、
    # 他カラムは UUIDStr / String / UTCDateTime に閉じる。
    "${TABLES_DIR}/tasks.py:last_error:MaskedText"
    # conversation_messages.body_markdown は §BUG-TR-002 凍結済みのため除外。
    # Task domain に conversations 属性追加後、将来の PR で追記する。
    # deliverables.body_markdown だけが MaskedText（Agent 出力に secret 混入）、
    # 他カラムは UUIDStr / UTCDateTime に閉じる。
    "${TABLES_DIR}/deliverables.py:body_markdown:MaskedText"
)

for entry in "${PARTIAL_MASK_FILES[@]}"; do
    IFS=':' read -r file allowed expected_type <<< "$entry"

    if [[ ! -f "$file" ]]; then
        continue
    fi

    # All Masked* column declarations on this file. The allowed
    # column must appear exactly once with the expected type and
    # nothing else may carry a Masked* TypeDecorator.
    masked_decls=$(grep -nE "^\s*[A-Za-z_][A-Za-z0-9_]*\s*:\s*Mapped.*Masked(JSONEncoded|Text)" \
        "$file" || true)

    if [[ -z "$masked_decls" ]]; then
        echo "[FAIL] partial-mask table file is missing the expected" >&2
        echo "       ${expected_type} column declaration: $file" >&2
        echo "       Next: declare ${allowed} with ${expected_type} per" >&2
        echo "       docs/architecture/domain-model/storage.md §逆引き表." >&2
        violations=$((violations + 1))
        continue
    fi

    while IFS= read -r line; do
        [[ -z "$line" ]] && continue

        # Reject masking on a column other than the allowed one.
        if [[ "$line" != *"${allowed}"* ]]; then
            echo "[FAIL] partial-mask table file declares Masked* on a" >&2
            echo "       column other than '${allowed}': $file" >&2
            echo "       ${line}" >&2
            echo "       Next: only '${allowed}' is registered as masked in" >&2
            echo "       docs/architecture/domain-model/storage.md §逆引き表;" >&2
            echo "       move the masking to the correct column or update §逆引き表." >&2
            violations=$((violations + 1))
            continue
        fi

        # Allowed column must use the expected TypeDecorator.
        if [[ "$line" != *"$expected_type"* ]]; then
            echo "[FAIL] partial-mask column '${allowed}' uses the wrong Masked*" >&2
            echo "       TypeDecorator (expected ${expected_type}): $file" >&2
            echo "       ${line}" >&2
            echo "       Next: switch ${allowed} to mapped_column(${expected_type}, ...) per" >&2
            echo "       docs/architecture/domain-model/storage.md §逆引き表." >&2
            violations=$((violations + 1))
        fi
    done <<< "$masked_decls"
done

if [[ "$violations" -gt 0 ]]; then
    echo "[FAIL] check_masking_columns: ${violations} violation(s) detected" >&2
    exit 1
fi

echo "[OK] check_masking_columns: positive (Masked* required) + negative (no-mask) + partial-mask over-masking checks passed"
