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
    audit_log,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    empire_agent_refs,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    empire_room_refs,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    empires,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    outbox,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    pid_registry,  # noqa: F401  # pyright: ignore[reportUnusedImport]
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
]

# No-mask contract: §逆引き表「Empire 関連カラム: masking 対象なし」.
# Each subsequent Aggregate Repository PR extends this list with the
# tables it adds when those tables are designated "no masking".
_NO_MASK_TABLES: list[str] = [
    "empires",
    "empire_room_refs",
    "empire_agent_refs",
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
