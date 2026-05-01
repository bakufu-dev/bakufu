"""CI 三層防衛 (2/3): SQLAlchemy metadata に対する arch test.

真実源: ``docs/design/domain-model/storage.md`` §逆引き表
詳細設計: ``docs/features/persistence-foundation/requirements-analysis.md``
§確定 R1-D 補強条項
        ``docs/features/empire-repository/detailed-design.md`` §確定 E
        (Empire 拡張、「対象なし」明示登録テンプレート)

``check_masking_columns.sh`` は ``mapped_column(<TYPE>, ...)`` の
ソースリテラルを grep するが、``__table_args__`` / ``Column(...)`` /
プログラム的な metadata 構築をすり抜ける。本テストは
SQLAlchemy が `Base.metadata.tables` に積んだ実カラムオブジェクトの
``type`` を参照することで、ソース表記に依らず実行時の型を物理保証する。

二つの契約面:

* **Positive contract** — §逆引き表「masking 対象あり」の各行は
  指定された ``Masked*`` 型で宣言されていること。
* **No-mask contract** — Empire 関連テーブルなど「対象なし」と
  凍結された Aggregate のテーブル群は ``MaskedJSONEncoded`` /
  ``MaskedText`` のいずれの型のカラムも持たないこと。後続 Repository
  PR が同方針で本リストを拡張する。
"""

from __future__ import annotations

import pytest
from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedJSONEncoded,
    MaskedText,
)

# テーブルモジュールを import することで全 ORM マッピングが ``Base.metadata`` に
# 登録される ── 後続のアサーションは本番 / Alembic と同一のテーブル集合を見る。
# import 名自体は意図的に未使用 ── import 副作用のみが目的。
from bakufu.infrastructure.persistence.sqlite.tables import (
    agent_providers,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    agent_skills,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    agents,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    audit_log,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    deliverable_attachments,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    deliverable_templates,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    deliverables,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    directives,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    empire_agent_refs,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    empire_room_refs,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    empires,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    external_review_audit_entries,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    external_review_gate_attachments,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    external_review_gate_criteria,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    external_review_gates,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    outbox,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    pid_registry,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    role_profiles,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    room_members,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    rooms,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    task_assigned_agents,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    tasks,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    workflow_stages,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    workflow_transitions,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    workflows,  # noqa: F401  # pyright: ignore[reportUnusedImport]
)

# Positive contract: §逆引き表「masking 対象あり」.
# 今後の Repository PR で ``Persona.prompt_body`` /
# ``PromptKit.prefix_markdown`` / ``Conversation.body_markdown`` 等の行を追加する。
_MASKING_CONTRACT: list[tuple[str, str, type]] = [
    ("audit_log", "args_json", MaskedJSONEncoded),
    ("audit_log", "error_text", MaskedText),
    ("bakufu_pid_registry", "cmd", MaskedText),
    ("domain_event_outbox", "payload_json", MaskedJSONEncoded),
    ("domain_event_outbox", "last_error", MaskedText),
    # Workflow Repository (PR #31, detailed-design.md §確定 H).
    ("workflow_stages", "notify_channels_json", MaskedJSONEncoded),
    # Agent Repository (PR #32, detailed-design.md §確定 H + Schneier
    # 申し送り #3 実適用).
    ("agents", "prompt_body", MaskedText),
    # Room Repository (PR #33, detailed-design.md §確定 R1-E +
    # room §確定 G 実適用).
    ("rooms", "prompt_kit_prefix_markdown", MaskedText),
    # Directive Repository (PR #34, detailed-design.md §確定 R1-E).
    ("directives", "text", MaskedText),
    # Task Repository (PR #35, detailed-design.md §確定 R1-E):
    # tasks.last_error ── BLOCKED 隔離理由(LLM error に secret 混入の可能性).
    ("tasks", "last_error", MaskedText),
    # conversation_messages.body_markdown は §BUG-TR-002 凍結済みのため除外。
    # deliverables.body_markdown ── Agent 出力に secret 混入の可能性.
    ("deliverables", "body_markdown", MaskedText),
    # ExternalReviewGate Repository (PR #36, detailed-design.md §確定 R1-E,
    # §設計決定 ERGR-002):
    # external_review_gates.snapshot_body_markdown ── Agent 出力に secret 混入.
    ("external_review_gates", "snapshot_body_markdown", MaskedText),
    # external_review_gates.feedback_text ── CEO レビューコメント。approve /
    # reject / cancel の入力経路は webhook URL / API キーを運び得る。
    ("external_review_gates", "feedback_text", MaskedText),
    # external_review_audit_entries.comment ── CEO 記述の自由テキスト。
    # feedback_text と同じく secret を含み得る入力経路。
    ("external_review_audit_entries", "comment", MaskedText),
]

# No-mask contract: §逆引き表「Empire 関連カラム: masking 対象なし」 +
# Workflow ルート + Workflow transitions。
# 後続の Aggregate Repository PR が、masking 対象なしと指定したテーブルを
# 本リストに順次追加する。
_NO_MASK_TABLES: list[str] = [
    "empires",
    "empire_room_refs",
    "empire_agent_refs",
    # Workflow Repository (PR #31, detailed-design.md §確定 E):
    # workflows / workflow_transitions は masking 対象を持たない。
    # secret を運ぶのは workflow_stages.notify_channels_json のみ。
    "workflows",
    "workflow_transitions",
    # Agent Repository (PR #32, detailed-design.md §確定 E):
    # agent_providers / agent_skills は Schneier #6 secret カテゴリを
    # 持たない。masking 対象は agents.prompt_body のみ。
    "agent_providers",
    "agent_skills",
    # Room Repository (PR #33, detailed-design.md §確定 R1-E):
    # room_members は secret セマンティクスを持たない。agent_id は masking しない。
    "room_members",
    # Task Repository (PR #35, detailed-design.md §確定 R1-E):
    # task_assigned_agents / deliverable_attachments は secret セマンティクスを持たない。
    # tasks / deliverables は _PARTIAL_MASK_TABLES に登録される (各 1 列のみ masking)。
    # conversations / conversation_messages は §BUG-TR-002 凍結済みのため除外。
    "task_assigned_agents",
    "deliverable_attachments",
    # ExternalReviewGate Repository (PR #36, detailed-design.md §確定 R1-E):
    # external_review_gate_attachments は secret セマンティクスを持たない ──
    # ファイルメタデータ (sha256 / filename / mime_type / size_bytes) は
    # Schneier #6 secret カテゴリに該当しない。
    "external_review_gate_attachments",
    # DeliverableTemplate Repository (Issue #119, deliverable-template §確定 §13
    # 業務判断): deliverable_templates / role_profiles は secret セマンティクスを
    # 持たない。テンプレートメタデータ / ロールプロファイルは Schneier #6
    # secret カテゴリに該当しない。
    "deliverable_templates",
    "role_profiles",
    # ExternalReviewGate criteria (Issue #121, REQ-ERGR-009):
    # external_review_gate_criteria は secret セマンティクスを持たない ──
    # description は deliverable-template §13 で機密レベル「低」と業務判定済み
    # （PR #137 acceptance_criteria_json 凍結と同一業務判断）。
    "external_review_gate_criteria",
]

# Partial-mask contract: **ちょうど 1 列**だけ masking されているテーブル。
# 過剰 masking を検出する用途 ── 同テーブル上の別カラムを
# Masked* TypeDecorator に切り替える PR は、まず §逆引き表 を更新せよ。
# さもないと本アサーションが発火する。
#
# 形式: ``(table_name, allowed_column_name)``.
_PARTIAL_MASK_TABLES: list[tuple[str, str]] = [
    ("workflow_stages", "notify_channels_json"),
    # Agent Repository (PR #32, detailed-design.md §確定 E):
    # masking されるのは agents.prompt_body のみ。
    # ペルソナ周辺のスカラフィールドは masking しない。
    ("agents", "prompt_body"),
    # Room Repository (PR #33, detailed-design.md §確定 R1-E):
    # masking されるのは rooms.prompt_kit_prefix_markdown のみ
    # (room §確定 G 実適用)。他カラム (name / description / archived) は
    # masking しない。
    ("rooms", "prompt_kit_prefix_markdown"),
    # Directive Repository (PR #34, detailed-design.md §確定 R1-E):
    # masking されるのは directives.text のみ。target_room_id /
    # created_at / task_id は secret セマンティクスを持たない。
    ("directives", "text"),
    # Task Repository (PR #35, detailed-design.md §確定 R1-E):
    # masking されるのは tasks.last_error のみ。room_id / directive_id /
    # current_stage_id / status / created_at / updated_at は
    # secret セマンティクスを持たない。
    ("tasks", "last_error"),
    # conversation_messages.body_markdown は §BUG-TR-002 凍結済みのため除外。
    # masking されるのは deliverables.body_markdown のみ。
    # id / task_id / stage_id / committed_by / committed_at は
    # secret セマンティクスを持たない。
    ("deliverables", "body_markdown"),
    # ExternalReviewGate Repository (PR #36, detailed-design.md §確定 R1-E):
    # masking されるのは external_review_audit_entries.comment のみ。
    # id / gate_id / actor_id / action / occurred_at は
    # secret セマンティクスを持たない。
    ("external_review_audit_entries", "comment"),
]

# Dual-mask contract: **ちょうど 2 列**だけ masking されているテーブル。
# 過小 masking (必要な masking 列の削除) と過剰 masking
# (secret でないカラムを誤って masking) の双方を検出する。
#
# ExternalReviewGate Repository (PR #36, detailed-design.md §確定 R1-E +
# §設計決定 ERGR-002): external_review_gates は厳密に 2 つの masking 列を
# 必要とする (Agent 由来の snapshot_body_markdown と CEO 由来の
# feedback_text)。
#
# 形式: ``(table_name, frozenset_of_allowed_column_names)``.
_DUAL_MASK_TABLES: list[tuple[str, frozenset[str]]] = [
    (
        "external_review_gates",
        frozenset({"snapshot_body_markdown", "feedback_text"}),
    ),
]


class TestMaskingColumnContract:
    """§逆引き表の各行は、該当カラムが使用すべき Masked* 型を規定する。"""

    @pytest.mark.parametrize(
        ("table_name", "column_name", "expected_type"),
        _MASKING_CONTRACT,
        ids=[f"{tbl}.{col}" for tbl, col, _ in _MASKING_CONTRACT],
    )
    def test_column_uses_masked_typedecorator(
        self,
        table_name: str,
        column_name: str,
        expected_type: type,
    ) -> None:
        """``Base.metadata.tables[table].c[column].type`` が契約された
        ``Masked*`` 型であることを表明する。

        失敗時は、リファクタリングでカラム型が masking なしバリアント
        (``JSONEncoded`` / ``Text``) に戻された状態 ── 次の INSERT で
        生 secret がディスクへ漏れる危険がある。
        """
        table = Base.metadata.tables.get(table_name)
        assert table is not None, (
            f"table {table_name!r} missing from Base.metadata; "
            f"check that tables/{table_name}.py is imported in tables/__init__.py"
        )
        column = table.columns.get(column_name)
        assert column is not None, f"column {table_name}.{column_name} missing from metadata"
        assert isinstance(column.type, expected_type), (
            f"[FAIL] {table_name}.{column_name} uses "
            f"{type(column.type).__name__}, expected {expected_type.__name__}\n"
            f"Next: switch the column to "
            f"`mapped_column({expected_type.__name__}, ...)` per "
            f"docs/design/domain-model/storage.md §逆引き表."
        )


class TestNoMaskContract:
    """'masking 対象なし' と明示登録されたテーブルは masking なしを維持しなければならない。

    Empire Repository PR (#25) で「explicit no-mask」パターンを導入。
    secret を持たないと設計上凍結したテーブルは、実行時に
    あらゆる ``Masked*`` カラム型を含まないことをアサートする。
    ある PR でカラムを secret セマンティクスに切り替える場合は、
    まず §逆引き表 を更新せよ ── さもないと本アサーションが発火する。
    """

    @pytest.mark.parametrize(
        "table_name",
        _NO_MASK_TABLES,
        ids=_NO_MASK_TABLES,
    )
    def test_table_has_no_masked_columns(self, table_name: str) -> None:
        """テーブルのカラム集合に ``Masked*`` 型が一つも含まれないことを表明する。"""
        table = Base.metadata.tables.get(table_name)
        assert table is not None, (
            f"table {table_name!r} missing from Base.metadata; "
            f"check that tables/{table_name}.py is imported in tables/__init__.py"
        )
        masked_columns = [
            col.name
            for col in table.columns
            if isinstance(col.type, MaskedJSONEncoded | MaskedText)
        ]
        assert masked_columns == [], (
            f"[FAIL] {table_name} unexpectedly declares Masked* columns: "
            f"{masked_columns}\n"
            f"Next: this table is registered as 'masking 対象なし' in "
            f"docs/design/domain-model/storage.md §逆引き表; either "
            f"remove the Masked* type or update the §逆引き表 entry first."
        )


class TestPartialMaskContract:
    """'partial mask' 登録のテーブルは指定の 1 カラムのみを masking しなければならない。

    Workflow Repository (PR #31) で 'partial mask' パターンを導入。
    ``workflow_stages.notify_channels_json`` のみが masking 対象で、
    他カラムは masking しない ── ``required_deliverables_json`` /
    ``completion_policy_json`` 等への過剰 masking を防ぐため。
    別カラムを追加で masking する PR は、まず §逆引き表 を更新せよ。
    さもないと本アサーションが発火する。
    """

    @pytest.mark.parametrize(
        ("table_name", "allowed_column"),
        _PARTIAL_MASK_TABLES,
        ids=[f"{tbl}.{col}" for tbl, col in _PARTIAL_MASK_TABLES],
    )
    def test_table_has_only_allowed_masked_column(
        self,
        table_name: str,
        allowed_column: str,
    ) -> None:
        """masking 列がちょうど 1 つで、それが許可列であることを表明する。"""
        table = Base.metadata.tables.get(table_name)
        assert table is not None, (
            f"table {table_name!r} missing from Base.metadata; "
            f"check that tables/{table_name}.py is imported in tables/__init__.py"
        )
        masked_columns = sorted(
            col.name
            for col in table.columns
            if isinstance(col.type, MaskedJSONEncoded | MaskedText)
        )
        assert masked_columns == [allowed_column], (
            f"[FAIL] {table_name} masking surface should be exactly "
            f"['{allowed_column}'], got {masked_columns}.\n"
            f"Next: only '{allowed_column}' is registered as masked in "
            f"docs/design/domain-model/storage.md §逆引き表; either "
            f"revert the extra Masked* type or update the §逆引き表 entry first."
        )


class TestDualMaskContract:
    """'dual mask' 登録のテーブルは指定の 2 カラムのみを masking しなければならない。

    ExternalReviewGate Repository (PR #36) で 'dual mask' パターンを導入。
    ``external_review_gates`` は 2 つの secret 列を持つ
    (Agent 出力の ``snapshot_body_markdown`` と CEO レビューコメントの
    ``feedback_text``)。両方とも必須で、§逆引き表 を更新せずに
    どちらかを削除したり 3 つ目を追加することはできない。

    別カラムを追加で masking する / 既存を削除する PR は、まず §逆引き表
    を更新せよ ── さもないと本アサーションが発火する。
    """

    @pytest.mark.parametrize(
        ("table_name", "allowed_columns"),
        _DUAL_MASK_TABLES,
        ids=[tbl for tbl, _ in _DUAL_MASK_TABLES],
    )
    def test_table_has_only_allowed_masked_columns(
        self,
        table_name: str,
        allowed_columns: frozenset[str],
    ) -> None:
        """許可された masking 列がちょうど含まれ、それ以外を持たないことを表明する。"""
        table = Base.metadata.tables.get(table_name)
        assert table is not None, (
            f"table {table_name!r} missing from Base.metadata; "
            f"check that tables/{table_name}.py is imported in tables/__init__.py"
        )
        masked_columns = sorted(
            col.name
            for col in table.columns
            if isinstance(col.type, MaskedJSONEncoded | MaskedText)
        )
        assert masked_columns == sorted(allowed_columns), (
            f"[FAIL] {table_name} masking surface should be exactly "
            f"{sorted(allowed_columns)}, got {masked_columns}.\n"
            f"Next: only {sorted(allowed_columns)} are registered as masked in "
            f"docs/design/domain-model/storage.md §逆引き表; either "
            f"revert extra Masked* types or update the §逆引き表 entry first."
        )
