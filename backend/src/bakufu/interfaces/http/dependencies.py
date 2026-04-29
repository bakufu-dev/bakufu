"""FastAPI DI ファクトリ群。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.ports.agent_repository import AgentRepository
from bakufu.application.ports.empire_repository import EmpireRepository
from bakufu.application.ports.external_review_gate_repository import (
    ExternalReviewGateRepository,
)
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.application.ports.workflow_repository import WorkflowRepository
from bakufu.application.services.agent_service import AgentService
from bakufu.application.services.empire_service import EmpireService
from bakufu.application.services.external_review_gate_service import (
    ExternalReviewGateService,
)
from bakufu.application.services.room_service import RoomService
from bakufu.application.services.task_service import TaskService
from bakufu.application.services.workflow_service import WorkflowService

# 未使用 import の警告抑制: 型チェック用途で再エクスポートしている。
__all__ = [
    "AgentRepository",
    "EmpireRepository",
    "ExternalReviewGateRepository",
    "RoomRepository",
    "SessionDep",
    "TaskRepository",
    "WorkflowRepository",
    "get_agent_service",
    "get_empire_service",
    "get_external_review_gate_service",
    "get_room_service",
    "get_session",
    "get_task_service",
    "get_workflow_service",
]


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """AsyncSession を yield する DI ファクトリ (確定 E)。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_empire_service(session: SessionDep) -> EmpireService:
    """EmpireService を DI 注入する。

    session を repo と service の両方に渡す:
    - repo: SQLite クエリ実行に使用
    - service: UoW (``async with session.begin()``) の管理に使用
    """
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
        SqliteEmpireRepository,
    )

    repo = SqliteEmpireRepository(session)
    return EmpireService(repo, session)


async def get_room_service(session: SessionDep) -> RoomService:
    """RoomService を DI 注入する。"""
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )

    repo = SqliteRoomRepository(session)
    return RoomService(repo)


async def get_workflow_service(session: SessionDep) -> WorkflowService:
    """WorkflowService を DI 注入する。"""
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    repo = SqliteWorkflowRepository(session)
    return WorkflowService(repo)


async def get_agent_service(session: SessionDep) -> AgentService:
    """AgentService を DI 注入する。"""
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
        SqliteAgentRepository,
    )

    repo = SqliteAgentRepository(session)
    return AgentService(repo)


async def get_task_service(session: SessionDep) -> TaskService:
    """TaskService を DI 注入する。"""
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )

    repo = SqliteTaskRepository(session)
    return TaskService(repo)


async def get_external_review_gate_service(
    session: SessionDep,
) -> ExternalReviewGateService:
    """ExternalReviewGateService を DI 注入する。"""
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (  # noqa: E501
        SqliteExternalReviewGateRepository,
    )

    repo = SqliteExternalReviewGateRepository(session)
    return ExternalReviewGateService(repo)
