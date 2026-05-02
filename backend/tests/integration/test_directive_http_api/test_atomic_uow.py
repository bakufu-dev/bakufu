"""Directive HTTP API atomic Unit-of-Work integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn
from uuid import UUID

import pytest
from bakufu.application.services.directive_service import DirectiveService
from bakufu.interfaces.http.dependencies import SessionDep, get_directive_service
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory
from tests.integration.test_room_http_api.helpers import (
    _create_empire,
    _create_room,
    _seed_workflow,
)

pytestmark = pytest.mark.asyncio


class _FailingTaskRepository:
    async def save(self, task: object) -> NoReturn:
        raise IntegrityError("INSERT INTO tasks", {}, RuntimeError("synthetic task save failure"))


async def test_issue_rolls_back_directive_when_task_save_fails(tmp_path: Path) -> None:
    """TC-IT-DRH-017: Task save failure must not leave an orphan Directive."""
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )
    from bakufu.interfaces.http.app import create_app

    app = create_app()
    engine = make_test_engine(tmp_path / "atomic_uow.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    from bakufu.infrastructure.event_bus import InMemoryEventBus

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.event_bus = InMemoryEventBus()

    async def _override_directive_service(session: SessionDep) -> DirectiveService:
        return DirectiveService(
            directive_repo=SqliteDirectiveRepository(session),
            task_repo=_FailingTaskRepository(),  # type: ignore[arg-type]
            room_repo=SqliteRoomRepository(session),
            workflow_repo=SqliteWorkflowRepository(session),
            session=session,
        )

    app.dependency_overrides[get_directive_service] = _override_directive_service

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        empire = await _create_empire(client, name="atomic-uow")
        workflow = await _seed_workflow(session_factory)
        room = await _create_room(client, str(empire["id"]), str(workflow.id))  # type: ignore[attr-defined]

        response = await client.post(
            f"/api/rooms/{room['id']}/directives",
            json={"text": "Task 保存失敗を起こす"},
        )

    try:
        assert response.status_code == 500, response.text
        async with session_factory() as session:
            directives = await SqliteDirectiveRepository(session).find_by_room(
                UUID(str(room["id"]))
            )
        assert directives == []
    finally:
        await engine.dispose()
