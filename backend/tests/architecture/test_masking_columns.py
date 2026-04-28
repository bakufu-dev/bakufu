"""CI 三層防衛 (2/3): SQLAlchemy metadata に対する arch test.

真実源: ``docs/architecture/domain-model/storage.md`` §逆引き表
詳細設計: ``docs/features/persistence-foundation/requirements-analysis.md``
§確定 R1-D 補強条項
        ``docs/features/empire-repository/detailed-design.md`` §確定 E
        (Empire 拡張、「対象なし」明示登録テンプレート)

``check_masking_columns.sh`` は ``mapped_column(<TYPE>, ...)`` の
ソースリテラルを grep するが、``__table_args__`` / ``Column(...)`` /
プログラム的な metadata 構築をすり抜ける。本テストは
SQLAlchemy が `Base.metadata.tables` に積んだ実カラムオブジェクトの
``type`` を参照することで、ソース表記に依らず実行時の型を物理保証する。

Two contract surfaces:

* **Positive contract** — each row in §逆引き表「masking 対象あり」は
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

# Importing the table modules registers every ORM mapping with
# ``Base.metadata`` so the assertions below see the same set of
# tables that production / Alembic see. The imported names are
# intentionally unused — only the import side effect matters.
from bakufu.infrastructure.persistence.sqlite.tables import (
    agent_providers,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    agent_skills,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    agents,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    audit_log,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    deliverable_attachments,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    deliverables,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    directives,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    empire_agent_refs,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    empire_room_refs,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    empires,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    outbox,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    pid_registry,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    room_members,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    rooms,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    task_assigned_agents,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    tasks,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    workflow_stages,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    workflow_transitions,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    workflows,  # noqa: F401  # pyright: ignore[reportUnusedImport]
)

# Positive contract: §逆引き表「masking 対象あり」.
# Future Repository PRs append rows for ``Persona.prompt_body`` /
# ``PromptKit.prefix_markdown`` / ``Conversation.body_markdown`` etc.
_MASKING_CONTRACT: list[tuple[str, str, type]] = [
    ("audit_log", "args_json", MaskedJSONEncoded),
    ("audit_log", "error_text", MaskedText),
    ("bakufu_pid_registry", "cmd", MaskedText),
    ("domain_event_outbox", "payload_json", MaskedJSONEncoded),
    ("domain_event_outbox", "last_error", MaskedText),
    # Workflow Repository (PR #31, detailed-design.md §確定 H).
    ("workflow_stages", "notify_channels_json", MaskedJSONEncoded),
    # Agent Repository (PR #32, detailed-design.md §確定 H + Schneier
    # 申し送り #3 实適用).
    ("agents", "prompt_body", MaskedText),
    # Room Repository (PR #33, detailed-design.md §確定 R1-E +
    # room §確定 G 実適用).
    ("rooms", "prompt_kit_prefix_markdown", MaskedText),
    # Directive Repository (PR #34, detailed-design.md §確定 R1-E).
    ("directives", "text", MaskedText),
    # Task Repository (PR #35, detailed-design.md §確定 R1-E):
    # tasks.last_error — BLOCKED 隔離理由(LLM error に secret 混入の可能性).
    ("tasks", "last_error", MaskedText),
    # conversation_messages.body_markdown は §BUG-TR-002 凍結済みのため除外。
    # deliverables.body_markdown — Agent 出力に secret 混入の可能性.
    ("deliverables", "body_markdown", MaskedText),
]

# No-mask contract: §逆引き表「Empire 関連カラム: masking 対象なし」 +
# Workflow root + Workflow transitions.
# Each subsequent Aggregate Repository PR extends this list with the
# tables it adds when those tables are designated "no masking".
_NO_MASK_TABLES: list[str] = [
    "empires",
    "empire_room_refs",
    "empire_agent_refs",
    # Workflow Repository (PR #31, detailed-design.md §確定 E):
    # workflows / workflow_transitions register zero masking targets;
    # only workflow_stages.notify_channels_json is secret-bearing.
    "workflows",
    "workflow_transitions",
    # Agent Repository (PR #32, detailed-design.md §確定 E):
    # agent_providers / agent_skills carry no Schneier #6 secret
    # categories; only agents.prompt_body is masked.
    "agent_providers",
    "agent_skills",
    # Room Repository (PR #33, detailed-design.md §確定 R1-E):
    # room_members carries no secret semantics; agent_id is not masked.
    "room_members",
    # Task Repository (PR #35, detailed-design.md §確定 R1-E):
    # task_assigned_agents / deliverable_attachments carry no secret semantics.
    # tasks / deliverables are registered in _PARTIAL_MASK_TABLES (each has
    # exactly one masked column). conversations / conversation_messages are
    # §BUG-TR-002 凍結済みのため除外。
    "task_assigned_agents",
    "deliverable_attachments",
]

# Partial-mask contract: tables that have **exactly one** masked
# column. Used to catch over-masking — a future PR that switches
# another column on the same table to a Masked* TypeDecorator must
# update §逆引き表 first; otherwise this assertion fires.
#
# Format: ``(table_name, allowed_column_name)``.
_PARTIAL_MASK_TABLES: list[tuple[str, str]] = [
    ("workflow_stages", "notify_channels_json"),
    # Agent Repository (PR #32, detailed-design.md §確定 E):
    # agents.prompt_body is the only masked column; persona-adjacent
    # scalar fields stay un-masked.
    ("agents", "prompt_body"),
    # Room Repository (PR #33, detailed-design.md §確定 R1-E):
    # rooms.prompt_kit_prefix_markdown is the only masked column (room
    # §確定 G 実適用); other columns (name / description / archived) stay
    # un-masked.
    ("rooms", "prompt_kit_prefix_markdown"),
    # Directive Repository (PR #34, detailed-design.md §確定 R1-E):
    # directives.text is the only masked column; target_room_id /
    # created_at / task_id carry no secret semantics.
    ("directives", "text"),
    # Task Repository (PR #35, detailed-design.md §確定 R1-E):
    # tasks.last_error is the only masked column; room_id / directive_id /
    # current_stage_id / status / created_at / updated_at carry no secret
    # semantics.
    ("tasks", "last_error"),
    # conversation_messages.body_markdown は §BUG-TR-002 凍結済みのため除外。
    # deliverables.body_markdown is the only masked column;
    # id / task_id / stage_id / committed_by / committed_at carry no secret
    # semantics.
    ("deliverables", "body_markdown"),
]


class TestMaskingColumnContract:
    """Each row in §逆引き表 maps a column to the Masked* type it must use."""

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
        """Assert ``Base.metadata.tables[table].c[column].type`` is the contracted ``Masked*`` type.

        Failing here means a refactor swapped the column type back to
        the un-masked variant (``JSONEncoded`` / ``Text``), which would
        leak raw secrets to disk on the next INSERT.
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
            f"docs/architecture/domain-model/storage.md §逆引き表."
        )


class TestNoMaskContract:
    """Tables explicitly registered as 'masking 対象なし' must stay un-masked.

    Empire Repository PR (#25) introduced the "explicit no-mask"
    pattern: a table that the design freezes as carrying no secrets
    asserts the absence of every ``Masked*`` column type at runtime.
    A future PR that swaps a column to a secret-bearing semantic
    must update §逆引き表 first; otherwise this assertion fires.
    """

    @pytest.mark.parametrize(
        "table_name",
        _NO_MASK_TABLES,
        ids=_NO_MASK_TABLES,
    )
    def test_table_has_no_masked_columns(self, table_name: str) -> None:
        """Assert the table's columns include zero ``Masked*`` types."""
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
            f"docs/architecture/domain-model/storage.md §逆引き表; either "
            f"remove the Masked* type or update the §逆引き表 entry first."
        )


class TestPartialMaskContract:
    """Tables registered as 'partial mask' must mask exactly one named column.

    Workflow Repository (PR #31) introduces the 'partial mask'
    pattern: ``workflow_stages.notify_channels_json`` is the *only*
    masked column on the table; every other column must stay un-masked
    so we don't bleed over-masking into ``deliverable_template`` /
    ``completion_policy_json`` / etc. A future PR that masks an
    additional column must update §逆引き表 first; otherwise this
    assertion fires.
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
        """Assert exactly one masked column, and that it's the allowed one."""
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
            f"docs/architecture/domain-model/storage.md §逆引き表; either "
            f"revert the extra Masked* type or update the §逆引き表 entry first."
        )
