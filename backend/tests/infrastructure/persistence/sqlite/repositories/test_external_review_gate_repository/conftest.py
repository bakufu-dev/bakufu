"""Pytest fixtures shared across external-review-gate-repository integration tests.

ExternalReviewGate has one mandatory FK:
  - ``external_review_gates.task_id REFERENCES tasks.id ON DELETE CASCADE``

Task itself requires:
  - ``tasks.room_id REFERENCES rooms.id ON DELETE CASCADE``
  - ``tasks.directive_id REFERENCES directives.id ON DELETE CASCADE``

Full dependency graph:
  empires
    └── workflows
          └── rooms  ← tasks.room_id FK / directives.target_room_id FK
                └── directives  ← tasks.directive_id FK
                      └── tasks  ← external_review_gates.task_id FK
                            └── external_review_gates  ← test body saves these

``seeded_gate_context`` seeds this hierarchy and returns ``(task_id, stage_id, reviewer_id)``
so Gate tests can call ``make_gate(task_id=..., stage_id=..., reviewer_id=...)`` and save
without hitting IntegrityError.

``stage_id`` and ``reviewer_id`` have no FK (§設計決定 ERGR-001: Aggregate boundary);
they are generated as uuid4() constants for predictable test values.

Per ``docs/features/external-review-gate-repository/test-design.md`` §conftest.py 設計.
Issue #36 — M2 0008.
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
from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
    SqliteTaskRepository,
)
from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
    SqliteWorkflowRepository,
)

from tests.factories.directive import make_directive
from tests.factories.empire import make_empire
from tests.factories.room import make_room
from tests.factories.task import make_task
from tests.factories.workflow import make_workflow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture(autouse=True)
def _bakufu_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Set ``BAKUFU_DATA_DIR`` for every test in this package."""
    monkeypatch.setenv("BAKUFU_DATA_DIR", "/tmp/bakufu-test-root")


@pytest_asyncio.fixture
async def seeded_gate_context(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[UUID, UUID, UUID]:
    """Seed empire → workflow → room → directive → task and return (task_id, stage_id, reviewer_id).

    Dependency graph:
        empires (INSERT via save)
          └── workflows (INSERT via save)
                └── rooms (INSERT via save)  ← tasks.room_id FK
                      └── directives (INSERT via save)  ← tasks.directive_id FK
                            └── tasks (INSERT via save)  ← external_review_gates.task_id FK
                                  └── external_review_gates  ← test body saves these

    stage_id and reviewer_id are uuid4() constants — they have no FK constraint
    (§設計決定 ERGR-001: Aggregate boundary). GateService validates these at the
    application layer.

    Returns:
        tuple[UUID, UUID, UUID]: (task.id, stage_id, reviewer_id)
    """
    empire = make_empire()
    workflow = make_workflow()
    room = make_room(workflow_id=workflow.id)
    directive = make_directive(target_room_id=room.id)
    task = make_task(room_id=room.id, directive_id=directive.id)

    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
    async with session_factory() as session, session.begin():
        await SqliteWorkflowRepository(session).save(workflow)
    async with session_factory() as session, session.begin():
        await SqliteRoomRepository(session).save(room, empire.id)
    async with session_factory() as session, session.begin():
        await SqliteDirectiveRepository(session).save(directive)
    async with session_factory() as session, session.begin():
        await SqliteTaskRepository(session).save(task)

    stage_id = uuid4()
    reviewer_id = uuid4()
    return task.id, stage_id, reviewer_id


async def seed_gate_context(
    session_factory: async_sessionmaker[AsyncSession],
    task_id: UUID | None = None,
    reviewer_id: UUID | None = None,
) -> tuple[UUID, UUID, UUID]:
    """Persist empire → workflow → room → directive → task.

    Returns (task_id, stage_id, reviewer_id).

    For tests that need multiple independent gate contexts (e.g. count_by_decision
    isolation, cross-task isolation). Each call creates fresh rows so contexts are
    fully independent.

    Returns:
        tuple[UUID, UUID, UUID]: (task.id, stage_id, reviewer_id)
    """
    empire = make_empire(empire_id=uuid4())
    workflow = make_workflow(workflow_id=uuid4())
    room = make_room(room_id=uuid4(), workflow_id=workflow.id)
    directive = make_directive(directive_id=uuid4(), target_room_id=room.id)
    actual_task_id = task_id if task_id is not None else uuid4()
    task = make_task(task_id=actual_task_id, room_id=room.id, directive_id=directive.id)

    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
    async with session_factory() as session, session.begin():
        await SqliteWorkflowRepository(session).save(workflow)
    async with session_factory() as session, session.begin():
        await SqliteRoomRepository(session).save(room, empire.id)
    async with session_factory() as session, session.begin():
        await SqliteDirectiveRepository(session).save(directive)
    async with session_factory() as session, session.begin():
        await SqliteTaskRepository(session).save(task)

    stage_id = uuid4()
    actual_reviewer_id = reviewer_id if reviewer_id is not None else uuid4()
    return actual_task_id, stage_id, actual_reviewer_id
