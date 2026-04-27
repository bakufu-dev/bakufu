"""Shared fixtures for infrastructure-layer integration tests.

The fixtures here intentionally use **real** SQLite + **real** Alembic
+ **real** filesystem under ``tmp_path``. The only thing we mock is
``psutil`` (in ``test_pid_gc.py``) because the OS doesn't let CI spawn
real subprocess trees safely.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from bakufu.infrastructure.config import data_dir
from bakufu.infrastructure.persistence.sqlite import engine as engine_mod
from bakufu.infrastructure.persistence.sqlite import session as session_mod
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head
from bakufu.infrastructure.persistence.sqlite.outbox import handler_registry
from bakufu.infrastructure.security import masking

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@pytest.fixture(autouse=True)
def _reset_data_dir() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """Clear the data_dir singleton before / after every test."""
    data_dir.reset()
    yield
    data_dir.reset()


@pytest.fixture(autouse=True)
def _clear_handler_registry() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """Tests must start with an empty handler registry (Confirmation K)."""
    handler_registry.clear()
    yield
    handler_registry.clear()


@pytest.fixture(autouse=True)
def _initialize_masking(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Initialize masking once per test with no provider env vars set."""
    for env_key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "OAUTH_CLIENT_SECRET",
        "BAKUFU_DISCORD_BOT_TOKEN",
    ):
        monkeypatch.delenv(env_key, raising=False)
    masking.init()


@pytest_asyncio.fixture
async def app_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """Real application engine pointed at tmp_path/bakufu.db.

    Runs Alembic ``upgrade head`` so the schema + triggers are in place
    before the test body executes. Disposes the engine on teardown so
    tmp_path can be removed cleanly.

    BUG-PF-002 fix: ``alembic/env.py`` now passes
    ``disable_existing_loggers=False`` so the previous test-side
    workarounds (``_re_enable_bakufu_loggers`` / ``_patch_alembic_file_config``)
    are no longer needed.
    """
    db_path = tmp_path / "bakufu.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = engine_mod.create_engine(url)
    await run_upgrade_head(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(
    app_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """SessionFactory bound to the migrated test engine."""
    return session_mod.make_session_factory(app_engine)
