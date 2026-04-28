"""Pytest fixtures shared across directive-repository integration tests.

Directive has a mandatory FK: ``directives.target_room_id REFERENCES rooms.id
ON DELETE CASCADE``. Room itself requires ``rooms.empire_id REFERENCES empires.id``
and ``rooms.workflow_id REFERENCES workflows.id``. This conftest seeds the full
three-level parent hierarchy (empire → workflow → room) so Directive tests can
insert rows without hitting IntegrityError.

Per ``docs/features/directive-repository/test-design.md`` §conftest.py 設計.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
    SqliteEmpireRepository,
)
from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
    SqliteRoomRepository,
)
from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
    SqliteWorkflowRepository,
)

from tests.factories.empire import make_empire
from tests.factories.room import make_room
from tests.factories.workflow import make_workflow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture(autouse=True)
def _bakufu_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Set ``BAKUFU_DATA_DIR`` for every test in this package."""
    monkeypatch.setenv("BAKUFU_DATA_DIR", "/tmp/bakufu-test-root")


@pytest_asyncio.fixture
async def seeded_room_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> UUID:
    """Seed empire → workflow → room and return room.id for FK satisfaction.

    Dependency graph:
        empires (INSERT via save)
          └── workflows (INSERT via save)
                └── rooms (INSERT via save)  ← seeded_room_id returns this id
    """
    empire = make_empire()
    workflow = make_workflow()
    room = make_room(workflow_id=workflow.id)

    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
    async with session_factory() as session, session.begin():
        await SqliteWorkflowRepository(session).save(workflow)
    async with session_factory() as session, session.begin():
        await SqliteRoomRepository(session).save(room, empire.id)

    return room.id


async def seed_room(
    session_factory: async_sessionmaker[AsyncSession],
    room_id: UUID | None = None,
    empire_id: UUID | None = None,
    workflow_id: UUID | None = None,
) -> UUID:
    """Persist empire → workflow → room and return room.id.

    For tests that need multiple Rooms (e.g. cross-Room isolation,
    TC-UT-DRR-004c). Returns the room_id that was actually persisted.

    If ``empire_id`` / ``workflow_id`` are provided the existing rows
    are reused (no INSERT OR IGNORE conflict). If ``None``, fresh rows
    are created so each call is fully independent.
    """
    empire = make_empire(empire_id=empire_id if empire_id is not None else uuid4())
    workflow = make_workflow(workflow_id=workflow_id if workflow_id is not None else uuid4())
    room = make_room(
        room_id=room_id if room_id is not None else uuid4(),
        workflow_id=workflow.id,
    )

    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
    async with session_factory() as session, session.begin():
        await SqliteWorkflowRepository(session).save(workflow)
    async with session_factory() as session, session.begin():
        await SqliteRoomRepository(session).save(room, empire.id)

    return room.id
