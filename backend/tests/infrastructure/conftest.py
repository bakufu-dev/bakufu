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


def _re_enable_bakufu_loggers() -> None:
    """Re-enable bakufu loggers after Alembic ``fileConfig`` disabled them.

    Bug discovered while wiring TC-IT-PF-008-* — ``alembic/env.py``
    calls :func:`logging.config.fileConfig` without
    ``disable_existing_loggers=False``, which silences every previously
    created logger in the process. Confirmation K's Fail Loud contract
    (dispatcher WARNs about empty handler registry / backlog) breaks
    silently in production after stage 3 completes.

    Test-side workaround: re-enable every ``bakufu.*`` logger after we
    run migrations so caplog / propagation can observe them again. The
    production fix lives in ``alembic/env.py`` (filed in the bug
    report appended to the test execution report).
    """
    import logging

    for name in list(logging.root.manager.loggerDict.keys()):
        if name.startswith("bakufu"):
            target = logging.getLogger(name)
            target.disabled = False
            target.propagate = True


@pytest.fixture(autouse=True)
def _patch_alembic_file_config(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neutralize the Alembic ``fileConfig`` call that silences bakufu loggers.

    See BUG-PF-001 in the test report — ``backend/alembic/env.py``
    invokes :func:`logging.config.fileConfig`, which (a) disables every
    previously created non-root logger and (b) reconfigures root level
    + handlers from ``alembic.ini``. Both side effects break caplog and
    any in-flight log assertions for stages 4〜8.

    Test-side patch: replace ``fileConfig`` with a no-op for the
    duration of the test. Alembic does not depend on the fileConfig
    behavior beyond cosmetic logging, so migrations still run normally
    while the existing logger config (caplog handler + INFO level)
    survives.

    The production fix lives in ``alembic/env.py``: pass
    ``disable_existing_loggers=False`` (and consider gating the
    fileConfig call on a CLI-only flag).
    """
    import logging.config as logging_config

    def _no_op_file_config(
        fname: object,
        defaults: object | None = None,
        disable_existing_loggers: bool = True,
        encoding: str | None = None,
    ) -> None:
        # Intentional no-op so the test logger stays usable.
        del fname

    monkeypatch.setattr(logging_config, "fileConfig", _no_op_file_config)
    # ``alembic/env.py`` imports ``fileConfig`` at module level. Once
    # the env module has been imported, the local binding caches the
    # original. Patch that binding too if the module is already loaded.
    import sys

    env_module = sys.modules.get("env")  # alembic loads ``env.py`` under name 'env'
    if env_module is not None and hasattr(env_module, "fileConfig"):
        monkeypatch.setattr(env_module, "fileConfig", _no_op_file_config)


@pytest_asyncio.fixture
async def app_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """Real application engine pointed at tmp_path/bakufu.db.

    Runs Alembic ``upgrade head`` so the schema + triggers are in place
    before the test body executes. Disposes the engine on teardown so
    tmp_path can be removed cleanly.

    See :func:`_re_enable_bakufu_loggers` for the post-Alembic logging
    workaround.
    """
    db_path = tmp_path / "bakufu.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = engine_mod.create_engine(url)
    await run_upgrade_head(engine)
    _re_enable_bakufu_loggers()
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
