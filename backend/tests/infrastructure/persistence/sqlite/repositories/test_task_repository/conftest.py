"""Pytest fixtures shared across task-repository integration tests.

Task has two mandatory FKs:
  - ``tasks.room_id REFERENCES rooms.id ON DELETE CASCADE``
  - ``tasks.directive_id REFERENCES directives.id ON DELETE CASCADE``

Directive itself requires ``directives.target_room_id REFERENCES rooms.id``,
and Room requires ``rooms.empire_id REFERENCES empires.id`` and
``rooms.workflow_id REFERENCES workflows.id``.

Full dependency graph:
  empires
    └── workflows
          └── rooms  ← tasks.room_id FK / directives.target_room_id FK
                └── directives  ← tasks.directive_id FK
                      └── tasks  ← test body saves these

``seeded_task_context`` seeds this hierarchy and returns ``(room_id, directive_id)``
so Task tests can call ``make_task(room_id=..., directive_id=...)`` and save without
hitting IntegrityError.

Per ``docs/features/task-repository/test-design.md`` §conftest.py 設計.
Issue #35 — M2 0007.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
    SqliteDirectiveRepository,
)
from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
    SqliteEmpireRepository,
)
from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
    SqliteRoomRepository,
)
from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
    SqliteWorkflowRepository,
)

from tests.factories.directive import make_directive
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
async def seeded_task_context(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[UUID, UUID]:
    """Seed empire → workflow → room → directive and return (room_id, directive_id).

    Dependency graph:
        empires (INSERT via save)
          └── workflows (INSERT via save)
                └── rooms (INSERT via save)  ← tasks.room_id FK
                      └── directives (INSERT via save)  ← tasks.directive_id FK
                            └── tasks  ← test body saves these

    Returns:
        tuple[UUID, UUID]: (room.id, directive.id)
    """
    empire = make_empire()
    workflow = make_workflow()
    room = make_room(workflow_id=workflow.id)
    directive = make_directive(target_room_id=room.id)

    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
    async with session_factory() as session, session.begin():
        await SqliteWorkflowRepository(session).save(workflow)
    async with session_factory() as session, session.begin():
        await SqliteRoomRepository(session).save(room, empire.id)
    async with session_factory() as session, session.begin():
        await SqliteDirectiveRepository(session).save(directive)

    return room.id, directive.id


async def seed_task_context(
    session_factory: async_sessionmaker[AsyncSession],
    room_id: UUID | None = None,
    empire_id: UUID | None = None,
    workflow_id: UUID | None = None,
    directive_id: UUID | None = None,
) -> tuple[UUID, UUID]:
    """Persist empire → workflow → room → directive and return (room_id, directive_id).

    For tests that need multiple independent task contexts (e.g. count_by_room
    isolation). If IDs are provided, fresh rows are created so each call is
    fully independent.

    Returns:
        tuple[UUID, UUID]: (room.id, directive.id)
    """
    empire = make_empire(empire_id=empire_id if empire_id is not None else uuid4())
    workflow = make_workflow(workflow_id=workflow_id if workflow_id is not None else uuid4())
    actual_room_id = room_id if room_id is not None else uuid4()
    room = make_room(room_id=actual_room_id, workflow_id=workflow.id)
    actual_directive_id = directive_id if directive_id is not None else uuid4()
    directive = make_directive(
        directive_id=actual_directive_id,
        target_room_id=actual_room_id,
    )

    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
    async with session_factory() as session, session.begin():
        await SqliteWorkflowRepository(session).save(workflow)
    async with session_factory() as session, session.begin():
        await SqliteRoomRepository(session).save(room, empire.id)
    async with session_factory() as session, session.begin():
        await SqliteDirectiveRepository(session).save(directive)

    return actual_room_id, actual_directive_id
