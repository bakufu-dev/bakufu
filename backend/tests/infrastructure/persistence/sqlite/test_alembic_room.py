"""Alembic 5th revision tests (TC-IT-RR-012 — chain + DDL + idempotency).

Per ``docs/features/room-repository/test-design.md``. Real Alembic
upgrade / downgrade against a real SQLite file, plus a chain
integrity check that makes sure
``0001_init`` → ``0002_empire_aggregate`` → ``0003_workflow_aggregate``
→ ``0004_agent_aggregate`` → ``0005_room_aggregate`` stays linear
(no head fork).

Also verifies:
* ``rooms`` + ``room_members`` tables created by the 5th revision.
* ``ix_rooms_empire_id_name`` composite index present (§確定 R1-F).
* BUG-EMR-001 FK closure: ``empire_room_refs.room_id`` now has a FK
  constraint onto ``rooms.id`` (added via ``batch_alter_table``).

The conftest from ``tests/infrastructure/`` patches Alembic's
``fileConfig`` so log capture survives migration; same workaround the
M2 persistence-foundation tests rely on.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from alembic.config import Config
from alembic.script import ScriptDirectory
from bakufu.infrastructure.persistence.sqlite import engine as engine_mod
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def empty_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """Bring up a fresh app engine without running any migrations."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'bakufu.db'}"
    engine = engine_mod.create_engine(url)
    try:
        yield engine
    finally:
        await engine.dispose()


def _alembic_config() -> Config:
    """Resolve the bakufu Alembic config for ScriptDirectory inspection."""
    backend_root = Path(__file__).resolve().parents[4]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    return cfg


# ---------------------------------------------------------------------------
# TC-IT-RR-012: 5th revision creates rooms + room_members tables + index
# ---------------------------------------------------------------------------
class TestFifthRevisionApplied:
    """TC-IT-RR-012: ``alembic upgrade head`` adds the Room schema."""

    async def test_two_room_tables_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """rooms + room_members exist after upgrade head."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"rooms", "room_members"}.issubset(tables), (
            f"[FAIL] rooms or room_members missing from schema after upgrade head.\n"
            f"Tables found: {tables}"
        )

    async def test_rooms_empire_id_name_index_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """``ix_rooms_empire_id_name`` composite index is created (§確定 R1-F).

        The index left-prefix optimises ``WHERE empire_id = ?`` and
        ``WHERE empire_id = ? AND name = ?`` for ``find_by_name``.
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='index' AND tbl_name='rooms'"
                )
            )
            index_names = {row[0] for row in result}
        assert "ix_rooms_empire_id_name" in index_names, (
            f"[FAIL] ix_rooms_empire_id_name index missing on rooms table.\n"
            f"Indexes found: {index_names}\n"
            f"Next: ensure ``op.create_index('ix_rooms_empire_id_name', ...)`` "
            f"is present in 0005_room_aggregate.py upgrade()."
        )

    async def test_empire_room_refs_fk_closure_applied(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """BUG-EMR-001 FK closure: ``empire_room_refs.room_id → rooms.id``.

        ``0005_room_aggregate.py`` adds the FK via ``batch_alter_table``
        (SQLite does not support ALTER TABLE ... ADD CONSTRAINT). After
        upgrade head, ``PRAGMA foreign_key_list('empire_room_refs')``
        must list a reference to the ``rooms`` table.
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("PRAGMA foreign_key_list('empire_room_refs')")
            )
            fk_rows = list(result)
        # PRAGMA foreign_key_list returns rows with columns:
        #   id, seq, table, from, to, on_update, on_delete, match
        referenced_tables = {row[2] for row in fk_rows}  # col index 2 = 'table'
        assert "rooms" in referenced_tables, (
            f"[FAIL] empire_room_refs has no FK to rooms (BUG-EMR-001 not closed).\n"
            f"FK references found: {referenced_tables}\n"
            f"Next: ensure op.batch_alter_table('empire_room_refs') in 0005_room_aggregate.py "
            f"adds the FK to rooms.id."
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-012 補強: upgrade / downgrade are idempotent
# ---------------------------------------------------------------------------
class TestUpgradeDowngradeIdempotent:
    """upgrade head → downgrade base → upgrade head again all green."""

    async def test_full_cycle_leaves_room_tables_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """upgrade head → downgrade base → upgrade head again."""
        await run_upgrade_head(empty_engine)
        from alembic import command  # local import to avoid global side effects

        cfg = _alembic_config()
        url = str(empty_engine.url)
        cfg.set_main_option("sqlalchemy.url", url)

        def _do_downgrade() -> None:
            command.downgrade(cfg, "base")

        await asyncio.to_thread(_do_downgrade)

        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert tables.isdisjoint({"rooms", "room_members"}), (
            f"[FAIL] rooms/room_members still present after downgrade to base.\n"
            f"Tables: {tables}"
        )

        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"rooms", "room_members"}.issubset(tables), (
            f"[FAIL] rooms/room_members missing after re-upgrade.\n"
            f"Tables: {tables}"
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-012: revision chain is linear (no head fork)
# ---------------------------------------------------------------------------
class TestRevisionChainLinear:
    """0001 → 0002 → 0003 → 0004 → 0005 single-head chain."""

    async def test_alembic_heads_returns_single_revision(self) -> None:
        """``ScriptDirectory.get_heads()`` returns exactly one revision."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"Alembic head must be linear; got branched heads {heads}.\n"
            f"Each Aggregate Repository PR appends a single revision."
        )

    async def test_0005_revision_has_correct_down_revision(self) -> None:
        """``0005_room_aggregate.down_revision == "0004_agent_aggregate"``."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        rev = script.get_revision("0005_room_aggregate")
        assert rev is not None
        assert rev.down_revision == "0004_agent_aggregate", (
            f"[FAIL] 0005_room_aggregate.down_revision is {rev.down_revision!r}; "
            f"expected '0004_agent_aggregate'."
        )

    async def test_chain_walks_from_0005_back_to_base(self) -> None:
        """Walking ``down_revision`` reaches base in 5 hops (no branching)."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        chain: list[str] = []
        current_id: str | None = "0005_room_aggregate"
        for _ in range(10):  # generous bound for safety
            if current_id is None:
                break
            rev = script.get_revision(current_id)
            assert rev is not None, f"Revision {current_id!r} not found"
            chain.append(rev.revision)
            down = rev.down_revision
            if isinstance(down, tuple | list):
                pytest.fail(f"Revision {rev.revision!r} has multiple down_revisions {down}")
            current_id = down  # pyright: ignore[reportAssignmentType]

        assert chain == [
            "0005_room_aggregate",
            "0004_agent_aggregate",
            "0003_workflow_aggregate",
            "0002_empire_aggregate",
            "0001_init",
        ], f"Unexpected revision chain: {chain}"
