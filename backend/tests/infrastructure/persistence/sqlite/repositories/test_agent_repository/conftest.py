"""Pytest fixtures shared across agent-repository integration tests.

Two responsibilities:

1. Set ``BAKUFU_DATA_DIR`` env var so ``SkillRef.path`` H10 validation
   passes (mirror of ``tests/domain/agent/conftest.py``).
2. Provide a :func:`seed_empire` helper that creates an Empire row in
   the test DB so the ``agents.empire_id`` FK resolves. Without this
   helper, every ``save(agent)`` would fail with ``IntegrityError:
   FOREIGN KEY constraint failed`` because the schema declares
   ``agents.empire_id REFERENCES empires.id ON DELETE CASCADE``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
    SqliteEmpireRepository,
)

from tests.factories.empire import make_empire

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture(autouse=True)
def _bakufu_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Set ``BAKUFU_DATA_DIR`` for every test in this package.

    Autouse fixture — pytest invokes via dependency injection, so the
    function appears unused to pyright. The pragma silences that.
    """
    monkeypatch.setenv("BAKUFU_DATA_DIR", "/tmp/bakufu-test-root")


@pytest_asyncio.fixture
async def seeded_empire_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> UUID:
    """Seed a single Empire row and return its id for FK satisfaction.

    Use this when the test only needs ``one`` empire to attach Agents
    to. For multi-Empire tests (e.g. ``find_by_name`` cross-Empire
    isolation), call :func:`seed_empire` directly with explicit ids.
    """
    empire = make_empire()
    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
    return empire.id


async def seed_empire(
    session_factory: async_sessionmaker[AsyncSession],
    empire_id: UUID | None = None,
) -> UUID:
    """Persist an Empire row whose id is ``empire_id`` (or fresh).

    Helper for tests that need to control which empire_id Agents
    attach to (e.g. cross-Empire isolation, multi-empire seeding).
    Returns the id that was actually persisted.
    """
    empire = make_empire(empire_id=empire_id if empire_id is not None else uuid4())
    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
    return empire.id
