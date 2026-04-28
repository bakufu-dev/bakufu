"""Pytest fixtures shared across room-repository integration tests.

Two responsibilities:

1. Set ``BAKUFU_DATA_DIR`` env var (mirror of other repository conftest files).
2. Provide :func:`seed_empire` and :func:`seed_workflow` helpers + matching
   fixtures so Room FK constraints on both ``rooms.empire_id`` and
   ``rooms.workflow_id`` can be satisfied.

Room is the first Aggregate whose Repository requires **two** parent tables to
be seeded before a Room row can be inserted:

* ``rooms.empire_id REFERENCES empires.id ON DELETE CASCADE``
* ``rooms.workflow_id REFERENCES workflows.id ON DELETE RESTRICT``

Without both seeds every ``save(room, empire_id)`` would raise
``IntegrityError: FOREIGN KEY constraint failed``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
    SqliteEmpireRepository,
)
from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
    SqliteWorkflowRepository,
)

from tests.factories.empire import make_empire
from tests.factories.workflow import make_workflow

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

    Use this when the test only needs one empire to attach Rooms to.
    For multi-Empire tests (e.g. ``find_by_name`` cross-Empire
    isolation), call :func:`seed_empire` directly with explicit ids.
    """
    empire = make_empire()
    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
    return empire.id


@pytest_asyncio.fixture
async def seeded_workflow_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> UUID:
    """Seed a single Workflow row and return its id for FK satisfaction.

    Room's ``workflow_id REFERENCES workflows.id ON DELETE RESTRICT`` means
    a Workflow row must exist before any Room can be inserted.
    """
    workflow = make_workflow()
    async with session_factory() as session, session.begin():
        await SqliteWorkflowRepository(session).save(workflow)
    return workflow.id


async def seed_empire(
    session_factory: async_sessionmaker[AsyncSession],
    empire_id: UUID | None = None,
) -> UUID:
    """Persist an Empire row whose id is ``empire_id`` (or fresh).

    Helper for tests that need to control which empire_id Rooms
    attach to (e.g. cross-Empire isolation, multi-empire seeding).
    Returns the id that was actually persisted.
    """
    empire = make_empire(empire_id=empire_id if empire_id is not None else uuid4())
    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
    return empire.id


async def seed_workflow(
    session_factory: async_sessionmaker[AsyncSession],
    workflow_id: UUID | None = None,
) -> UUID:
    """Persist a Workflow row whose id is ``workflow_id`` (or fresh).

    Helper for tests that need to control which workflow_id Rooms
    attach to. Returns the id that was actually persisted.
    """
    workflow = make_workflow(workflow_id=workflow_id if workflow_id is not None else uuid4())
    async with session_factory() as session, session.begin():
        await SqliteWorkflowRepository(session).save(workflow)
    return workflow.id
