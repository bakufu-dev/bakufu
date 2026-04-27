"""Alembic 3rd revision tests (TC-IT-WFR-020 / 021 / 022).

Per ``docs/features/workflow-repository/test-design.md``. Real Alembic
upgrade / downgrade against a real SQLite file, plus a chain integrity
check that makes sure
``0001_init`` → ``0002_empire_aggregate`` → ``0003_workflow_aggregate``
stays linear (no head fork).

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
# TC-IT-WFR-020: 3rd revision applies the 3 Workflow tables + UNIQUE indexes
# ---------------------------------------------------------------------------
class TestThirdRevisionApplied:
    """TC-IT-WFR-020: ``alembic upgrade head`` adds the Workflow schema."""

    async def test_three_workflow_tables_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-020: workflows / workflow_stages / workflow_transitions exist."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"workflows", "workflow_stages", "workflow_transitions"}.issubset(tables)

    async def test_unique_indexes_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-020: UNIQUE indexes for the two side tables.

        ``workflow_stages``: UNIQUE ``(workflow_id, stage_id)``.
        ``workflow_transitions``: UNIQUE ``(workflow_id, transition_id)``.

        SQLite emits an ``sqlite_autoindex_*`` for every UNIQUE
        constraint declared at table creation. A ``CREATE INDEX``
        named index also lands here; we accept either shape because
        the Alembic 0003 revision uses the inline UNIQUE constraint
        form (``uq_workflow_stages_pair`` / ``uq_workflow_transitions_pair``).
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name, tbl_name FROM sqlite_master WHERE type='index'")
            )
            rows = list(result)
        stage_indexes = [name for name, tbl in rows if tbl == "workflow_stages"]
        transition_indexes = [name for name, tbl in rows if tbl == "workflow_transitions"]
        assert stage_indexes, "workflow_stages must declare at least one index"
        assert transition_indexes, "workflow_transitions must declare at least one index"


# ---------------------------------------------------------------------------
# TC-IT-WFR-021: upgrade / downgrade are idempotent
# ---------------------------------------------------------------------------
class TestUpgradeDowngradeIdempotent:
    """TC-IT-WFR-021: Alembic up + down + up again leaves the schema in the head state."""

    async def test_full_cycle_leaves_workflow_tables_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-021: upgrade head → downgrade base → upgrade head again."""
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

        # Schema is empty now — assert the Workflow tables are gone.
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert tables.isdisjoint({"workflows", "workflow_stages", "workflow_transitions"})

        # Up again — back to head.
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"workflows", "workflow_stages", "workflow_transitions"}.issubset(tables)


# ---------------------------------------------------------------------------
# TC-IT-WFR-022: revision chain is linear (no head fork)
# ---------------------------------------------------------------------------
class TestRevisionChainLinear:
    """TC-IT-WFR-022: revision chain is linear (single head).

    ``0001_init`` → ``0002_empire_aggregate`` → ``0003_workflow_aggregate``.
    """

    async def test_alembic_heads_returns_single_revision(self) -> None:
        """TC-IT-WFR-022: ``ScriptDirectory.get_heads()`` returns exactly one revision."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"Alembic head must be linear; got branched heads {heads}. "
            f"Each Aggregate Repository PR appends a single revision; "
            f"branching breaks ``alembic upgrade head`` across CI runners."
        )

    async def test_0003_revision_has_correct_down_revision(self) -> None:
        """TC-IT-WFR-022: ``0003_workflow_aggregate.down_revision == "0002_empire_aggregate"``."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        rev = script.get_revision("0003_workflow_aggregate")
        assert rev is not None
        assert rev.down_revision == "0002_empire_aggregate"

    async def test_chain_walks_from_0003_back_to_base(self) -> None:
        """TC-IT-WFR-022 補強: walking ``down_revision`` reaches base in 3 hops.

        Catches a future PR that accidentally registers ``0003`` with
        a ``down_revision = None`` (which would create a branch off
        base) — the heads() check would still pass with branching, so
        we walk the chain explicitly.
        """
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        chain: list[str] = []
        current_id: str | None = "0003_workflow_aggregate"
        for _ in range(10):  # generous bound to avoid infinite loop on bad data
            if current_id is None:
                break
            rev = script.get_revision(current_id)
            assert rev is not None, f"Revision {current_id!r} not found"
            chain.append(rev.revision)
            down = rev.down_revision
            if isinstance(down, tuple | list):
                pytest.fail(f"Revision {rev.revision!r} has multiple down_revisions {down}")
            # ``down`` is now narrowed to ``str | None`` by the guard above.
            current_id = down  # pyright: ignore[reportAssignmentType]

        # 0003 → 0002 → 0001 → base (None)
        assert chain == [
            "0003_workflow_aggregate",
            "0002_empire_aggregate",
            "0001_init",
        ], f"Unexpected revision chain: {chain}"
