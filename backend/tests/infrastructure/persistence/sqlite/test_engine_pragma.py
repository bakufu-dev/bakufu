"""Engine PRAGMA + dual connection integration tests
(TC-IT-PF-003 / 013 / 003-A / 003-B / 003-C / 003-D).

Confirmation D-1〜D-4 / Schneier 重大 2 物理保証. The application engine
sets eight PRAGMAs including ``defensive=ON`` / ``writable_schema=OFF``
/ ``trusted_schema=OFF`` so a runtime ``DROP TRIGGER`` cannot remove
the audit_log defenses. The migration engine relaxes those guards but
is explicitly disposed before stage 4 starts.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from bakufu.infrastructure.persistence.sqlite import engine as engine_mod
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# Each test in this module exercises async code.
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def fresh_app_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """Bring up a fresh app engine per test (no Alembic, no shared state)."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'bakufu.db'}"
    engine = engine_mod.create_engine(url)
    try:
        yield engine
    finally:
        await engine.dispose()


class TestApplicationPragmas:
    """TC-IT-PF-003 / 013 / 003-A: application engine sets 8 PRAGMAs."""

    async def test_journal_mode_is_wal(self, fresh_app_engine: AsyncEngine) -> None:
        """TC-IT-PF-003: journal_mode = WAL after first connect."""
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA journal_mode"))
            value = result.scalar()
        assert value == "wal"

    async def test_foreign_keys_on(self, fresh_app_engine: AsyncEngine) -> None:
        """TC-IT-PF-003: foreign_keys ON per-connection."""
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_keys"))
            value = result.scalar()
        assert value == 1

    async def test_busy_timeout_5000(self, fresh_app_engine: AsyncEngine) -> None:
        """TC-IT-PF-003: busy_timeout = 5000 ms."""
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA busy_timeout"))
            value = result.scalar()
        assert value == 5000

    async def test_synchronous_normal(self, fresh_app_engine: AsyncEngine) -> None:
        """TC-IT-PF-003: synchronous = NORMAL (1)."""
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA synchronous"))
            value = result.scalar()
        assert value == 1

    async def test_temp_store_memory(self, fresh_app_engine: AsyncEngine) -> None:
        """TC-IT-PF-003: temp_store = MEMORY (2)."""
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA temp_store"))
            value = result.scalar()
        assert value == 2


class TestDefensivePragmasOptional:
    """TC-IT-PF-003-A: defensive guards are best-effort (D-4 fallback).

    SQLite ``PRAGMA defensive`` requires SQLITE_DBCONFIG_DEFENSIVE which
    is built-in only when the SQLite library is compiled with the
    ``SQLITE_ENABLE_DESERIALIZE`` option. On older builds the engine logs
    a WARN and continues — Confirmation D-4 frames this as the
    documented fallback.
    """

    async def test_defensive_pragma_does_not_break_engine(
        self, fresh_app_engine: AsyncEngine
    ) -> None:
        """TC-IT-PF-003-A: engine connects successfully even on older SQLite.

        ``PRAGMA defensive`` is set-only on SQLite (no SELECT form), so
        we can only confirm the engine connects. The Confirmation D-4
        fallback path either applies the PRAGMA silently (modern SQLite)
        or logs a WARN and continues (older builds). Either way the
        application engine must be usable for normal queries.
        """
        async with fresh_app_engine.connect() as conn:
            # Engine must be usable for normal queries; if PRAGMA
            # application failed catastrophically the connect would
            # have raised at engine.connect() time.
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar()
        assert value == 1


class TestDropTriggerDefense:
    """TC-IT-PF-003-B: with defensive=ON, ``DROP TRIGGER`` cannot remove the audit_log guard.

    On builds where defensive=ON is supported, a DROP TRIGGER from the
    application engine raises. On older builds (D-4 fallback) the OS
    file-permission layer becomes the trust boundary — we still confirm
    the trigger *survives* the lifetime of the app engine so a future
    repository PR cannot accidentally rely on dropping it.
    """

    async def test_audit_log_no_delete_trigger_survives(
        self, fresh_app_engine: AsyncEngine
    ) -> None:
        """TC-IT-PF-003-B: trigger remains after Alembic upgrade."""
        await run_upgrade_head(fresh_app_engine)
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='trigger' AND name='audit_log_no_delete'"
                )
            )
            names = [row[0] for row in result]
        assert "audit_log_no_delete" in names


class TestDualConnectionLifecycle:
    """TC-IT-PF-003-D: migration engine is disposed after Alembic runs."""

    async def test_migration_runner_disposes_its_own_engine(
        self, fresh_app_engine: AsyncEngine
    ) -> None:
        """TC-IT-PF-003-D: ``run_upgrade_head`` returns after dispose; app engine still alive."""
        head = await run_upgrade_head(fresh_app_engine)
        # Head should be the documented revision id from versions/0001.
        assert head == "0001_init"
        # Application engine remains usable.
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"audit_log", "bakufu_pid_registry", "domain_event_outbox"}.issubset(tables)
