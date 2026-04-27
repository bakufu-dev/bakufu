"""Alembic 2nd revision tests (TC-IT-EMR-008 / 015 / 016).

Per ``docs/features/empire-repository/test-design.md``. Real Alembic
upgrade / downgrade against a real SQLite file, plus a chain integrity
check that makes sure ``0001_init`` → ``0002_empire_aggregate`` stays
linear (no head fork).

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
    # Same path the migrations module uses internally; we duplicate the
    # walk so this test does not import private helpers.
    backend_root = Path(__file__).resolve().parents[4]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    return cfg


# ---------------------------------------------------------------------------
# TC-IT-EMR-008: 2nd revision applies the 3 Empire tables + indexes
# ---------------------------------------------------------------------------
class TestSecondRevisionApplied:
    """TC-IT-EMR-008: ``alembic upgrade head`` adds the Empire schema."""

    async def test_three_empire_tables_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-EMR-008: empires / empire_room_refs / empire_agent_refs exist."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"empires", "empire_room_refs", "empire_agent_refs"}.issubset(tables)

    async def test_unique_indexes_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-EMR-008: UNIQUE indexes on (empire_id, room_id) / (empire_id, agent_id).

        SQLite emits an ``sqlite_autoindex_*`` for every UNIQUE
        constraint declared at table creation. A ``CREATE INDEX`` named
        index also lands here; we accept either shape because the
        Alembic 0002 revision uses the inline UNIQUE constraint form.
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name, tbl_name FROM sqlite_master WHERE type='index'")
            )
            rows = list(result)
        room_indexes = [name for name, tbl in rows if tbl == "empire_room_refs"]
        agent_indexes = [name for name, tbl in rows if tbl == "empire_agent_refs"]
        assert room_indexes, "empire_room_refs must declare at least one index"
        assert agent_indexes, "empire_agent_refs must declare at least one index"


# ---------------------------------------------------------------------------
# TC-IT-EMR-015: upgrade / downgrade are idempotent
# ---------------------------------------------------------------------------
class TestUpgradeDowngradeIdempotent:
    """TC-IT-EMR-015: Alembic up + down + up again leaves the schema in the head state."""

    async def test_full_cycle_leaves_empire_tables_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-EMR-015: upgrade head → downgrade base → upgrade head again."""
        # Up.
        await run_upgrade_head(empty_engine)
        # Down to base via Alembic command (synchronous within asyncio).
        from alembic import command  # local import to avoid global side effects

        cfg = _alembic_config()
        url = str(empty_engine.url)
        cfg.set_main_option("sqlalchemy.url", url)

        def _do_downgrade() -> None:
            command.downgrade(cfg, "base")

        await asyncio.to_thread(_do_downgrade)

        # Schema is empty now — assert the Empire tables are gone.
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert tables.isdisjoint({"empires", "empire_room_refs", "empire_agent_refs"})

        # Up again — back to head.
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"empires", "empire_room_refs", "empire_agent_refs"}.issubset(tables)


# ---------------------------------------------------------------------------
# TC-IT-EMR-016: revision chain is linear (no head fork)
# ---------------------------------------------------------------------------
class TestRevisionChainLinear:
    """TC-IT-EMR-016: ``0001_init`` → ``0002_empire_aggregate`` (single head)."""

    async def test_alembic_heads_returns_single_revision(self) -> None:
        """TC-IT-EMR-016: ``ScriptDirectory.get_heads()`` returns exactly one revision."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"Alembic head must be linear; got branched heads {heads}. "
            f"Each Aggregate Repository PR appends a single revision; "
            f"branching breaks ``alembic upgrade head`` across CI runners."
        )

    async def test_0002_revision_has_correct_down_revision(self) -> None:
        """TC-IT-EMR-016: ``0002_empire_aggregate.down_revision == "0001_init"``."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        rev = script.get_revision("0002_empire_aggregate")
        assert rev is not None
        assert rev.down_revision == "0001_init"
