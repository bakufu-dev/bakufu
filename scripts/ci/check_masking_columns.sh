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
    # ExternalReviewGate Repository (PR #36, detailed-design.md §確定 R1-E):
    # external_review_gate_attachments carries no secret semantics — file
    # metadata (sha256 / filename / mime_type / size_bytes) is content-
    # addressing with no Schneier #6 secret category.
    # external_review_gates / external_review_audit_entries are registered in
    # PARTIAL_MASK_FILES (masked columns: snapshot_body_markdown + feedback_text
    # and comment respectively).
    "${TABLES_DIR}/external_review_gate_attachments.py"
    # DeliverableTemplate Repository (Issue #119, deliverable-template §確定 §13
    # 業務判断): template metadata / role profile carry no Schneier #6 secret
    # categories. MaskedJSONEncoded / MaskedText are absent by design.
    "${TABLES_DIR}/deliverable_templates.py"
    "${TABLES_DIR}/role_profiles.py"
    # ExternalReviewGate criteria (Issue #121, REQ-ERGR-009):
    # external_review_gate_criteria carries no Schneier #6 secret semantics —
    # description is classified as "low confidentiality" per
    # deliverable-template/feature-spec.md §13 (same business judgment as
    # acceptance_criteria_json in PR #137). MaskedText / MaskedJSONEncoded
    # are absent by design. CI Layer 1/2 enforce no over-masking.
    "${TABLES_DIR}/external_review_gate_criteria.py"
    # DeliverableRecord Repository (Issue #123, ai-validation §確定 E):
    # criterion_validation_results carries no Schneier #6 secret semantics —
    # reason is LLM evaluation rationale text, classified as no-mask per
    # ai-validation detailed-design §データ構造. MaskedText / MaskedJSONEncoded
    # are absent by design. CI Layer 1/2 enforce no over-masking.
    "${TABLES_DIR}/criterion_validation_results.py"
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
# 「許可カラムが期待型でそれぞれ宣言されている」+「他カラムに Masked* が
# 一切登場しない」の両方を assert する。
#
# 1 ファイルに複数の許可カラムを登録できる（ExternalReviewGate #36 から導入）。
# ループが同一ファイルの全エントリを集約してから照合するため、
# 許可カラムが 1 本でも 2 本以上でも正しく動作する。
#
# 登録されている partial-mask テーブル:
#   * Workflow Repository (PR #31, detailed-design.md §確定 E):
#     workflow_stages.notify_channels_json だけが MaskedJSONEncoded。
#   * Agent Repository (PR #32, detailed-design.md §確定 E):
#     agents.prompt_body だけが MaskedText。Schneier 申し送り #3 实適用。
#   * ExternalReviewGate Repository (PR #36, detailed-design.md §確定 R1-E):
#     external_review_gates は snapshot_body_markdown + feedback_text の 2 本が
#     MaskedText（§設計決定 ERGR-002 対応で feedback_text を追加）。
#     external_review_audit_entries.comment だけが MaskedText。
#
# フォーマット: "<file>:<allowed_column>:<expected_type>"
# 同一 <file> に複数エントリを追加することで許可カラムセットを拡張できる。
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
    # ExternalReviewGate Repository (PR #36, detailed-design.md §確定 R1-E,
    # §設計決定 ERGR-002): external_review_gates は 2 本の MaskedText カラムを持つ。
    # snapshot_body_markdown — Agent 出力に secret 混入の可能性。
    "${TABLES_DIR}/external_review_gates.py:snapshot_body_markdown:MaskedText"
    # feedback_text — CEO review comment; approve/reject/cancel 入力経路が
    # webhook URL / API key を含む可能性（§設計決定 ERGR-002）。
    "${TABLES_DIR}/external_review_gates.py:feedback_text:MaskedText"
    # external_review_audit_entries.comment だけが MaskedText（CEO 入力経路）、
    # 他カラムは UUIDStr / String / UTCDateTime に閉じる。
    "${TABLES_DIR}/external_review_audit_entries.py:comment:MaskedText"
    # DeliverableRecord Repository (Issue #123, ai-validation §確定 E):
    # deliverable_records.content だけが MaskedText（Agent 出力に secret 混入の可能性、
    # Schneier 申し送り #3 実適用）、他カラムは UUIDStr / Integer / String / UTCDateTime
    # に閉じる。
    "${TABLES_DIR}/deliverable_records.py:content:MaskedText"
)

# Collect unique file paths from PARTIAL_MASK_FILES.
# Use the ${arr[@]+"${arr[@]}"} pattern so that expanding an empty array
# does not trip `set -u` on bash 3.x (the macOS default).
_partial_files=()
for _entry in "${PARTIAL_MASK_FILES[@]}"; do
    IFS=':' read -r _f _col _typ <<< "$_entry"
    _already_seen=false
    for _seen in ${_partial_files[@]+"${_partial_files[@]}"}; do
        [[ "$_seen" == "$_f" ]] && _already_seen=true && break
    done
    [[ "$_already_seen" == false ]] && _partial_files+=("$_f")
done

for _file in ${_partial_files[@]+"${_partial_files[@]}"}; do
    if [[ ! -f "$_file" ]]; then
        # ファイル未作成（後続 PR が追加予定）。スキップ。
        continue
    fi

    # Build allowed (col:type) pairs for this file from all entries.
    _allowed_pairs=()
    for _entry in "${PARTIAL_MASK_FILES[@]}"; do
        IFS=':' read -r _entry_file _col _typ <<< "$_entry"
        [[ "$_entry_file" == "$_file" ]] && _allowed_pairs+=("${_col}:${_typ}")
    done

    # Get all Masked* column declarations in this file.
    _masked_decls=$(grep -nE "^\s*[A-Za-z_][A-Za-z0-9_]*\s*:\s*Mapped.*Masked(JSONEncoded|Text)" \
        "$_file" || true)

    if [[ -z "$_masked_decls" ]]; then
        echo "[FAIL] partial-mask table file is missing all expected Masked* declarations: $_file" >&2
        for _pair in "${_allowed_pairs[@]}"; do
            _col="${_pair%%:*}"
            _typ="${_pair##*:}"
            echo "       Next: declare ${_col} with ${_typ} per" >&2
        done
        echo "       docs/architecture/domain-model/storage.md §逆引き表." >&2
        violations=$((violations + 1))
        continue
    fi

    # Check that each masked declaration is for an allowed column.
    while IFS= read -r _line; do
        [[ -z "$_line" ]] && continue

        _matched_pair=""
        for _pair in "${_allowed_pairs[@]}"; do
            _col="${_pair%%:*}"
            if [[ "$_line" == *"${_col}"* ]]; then
                _matched_pair="$_pair"
                break
            fi
        done

        if [[ -z "$_matched_pair" ]]; then
            _allowed_names=""
            for _pair in "${_allowed_pairs[@]}"; do
                _allowed_names+="'${_pair%%:*}' "
            done
            echo "[FAIL] partial-mask table file declares Masked* on an" >&2
            echo "       unexpected column: $_file" >&2
            echo "       ${_line}" >&2
            echo "       Next: only ${_allowed_names}registered as masked in" >&2
            echo "       docs/architecture/domain-model/storage.md §逆引き表;" >&2
            echo "       move the masking to the correct column or update §逆引き表." >&2
            violations=$((violations + 1))
            continue
        fi

        # Allowed column must use the expected TypeDecorator.
        _col="${_matched_pair%%:*}"
        _expected_type="${_matched_pair##*:}"
        if [[ "$_line" != *"$_expected_type"* ]]; then
            echo "[FAIL] partial-mask column '${_col}' uses the wrong Masked*" >&2
            echo "       TypeDecorator (expected ${_expected_type}): $_file" >&2
            echo "       ${_line}" >&2
            echo "       Next: switch ${_col} to mapped_column(${_expected_type}, ...) per" >&2
            echo "       docs/architecture/domain-model/storage.md §逆引き表." >&2
            violations=$((violations + 1))
        fi
    done <<< "$_masked_decls"

    # Check that all required allowed columns are present in the file.
    for _pair in "${_allowed_pairs[@]}"; do
        _col="${_pair%%:*}"
        _expected_type="${_pair##*:}"
        if ! grep -qE "^\s*${_col}\s*:\s*Mapped.*${_expected_type}" "$_file"; then
            echo "[FAIL] partial-mask required column '${_col}' with ${_expected_type}" >&2
            echo "       missing from: $_file" >&2
            echo "       Next: declare ${_col} with mapped_column(${_expected_type}, ...) per" >&2
            echo "       docs/architecture/domain-model/storage.md §逆引き表." >&2
            violations=$((violations + 1))
        fi
    done
done

if [[ "$violations" -gt 0 ]]; then
    echo "[FAIL] check_masking_columns: ${violations} violation(s) detected" >&2
    exit 1
fi

echo "[OK] check_masking_columns: positive (Masked* required) + negative (no-mask) + partial-mask over-masking checks passed"
