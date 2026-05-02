"""FastAPI DI ファクトリ群。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.ports.agent_repository import AgentRepository
from bakufu.application.ports.directive_repository import DirectiveRepository
from bakufu.application.ports.empire_repository import EmpireRepository
from bakufu.application.ports.event_bus import EventBusPort
from bakufu.application.ports.external_review_gate_repository import (
    ExternalReviewGateRepository,
)
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.application.ports.workflow_repository import WorkflowRepository
from bakufu.application.services.agent_service import AgentService
from bakufu.application.services.deliverable_template_service import (
    DeliverableTemplateService,
)
from bakufu.application.services.directive_service import DirectiveService
from bakufu.application.services.empire_service import EmpireService
from bakufu.application.services.external_review_gate_service import (
    ExternalReviewGateService,
)
from bakufu.application.services.role_profile_service import RoleProfileService
from bakufu.application.services.room_matching_service import RoomMatchingService
from bakufu.application.services.room_role_override_service import RoomRoleOverrideService
from bakufu.application.services.room_service import RoomService
from bakufu.application.services.task_service import TaskService
from bakufu.application.services.workflow_service import WorkflowService

# 未使用 import の警告抑制: 型チェック用途で再エクスポートしている。
__all__ = [
    "AgentRepository",
    "AgentServiceDep",
    "DeliverableTemplateService",
    "DirectiveRepository",
    "DirectiveServiceDep",
    "EmpireRepository",
    "EventBusPort",
    "ExternalReviewGateRepository",
    "GateServiceDep",
    "RoleProfileService",
    "RoomMatchingService",
    "RoomRepository",
    "RoomRoleOverrideService",
    "SessionDep",
    "TaskRepository",
    "TaskServiceDep",
    "WorkflowRepository",
    "get_agent_service",
    "get_deliverable_template_service",
    "get_directive_service",
    "get_empire_service",
    "get_event_bus",
    "get_external_review_gate_service",
    "get_role_profile_service",
    "get_room_matching_service",
    "get_room_role_override_service",
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


def get_event_bus(request: Request) -> EventBusPort:
    """InMemoryEventBus を app.state から取得する DI ファクトリ（REQ-WSB-007）。

    lifespan で生成された ``InMemoryEventBus`` を返す。
    Issue #159 で ConnectionManager の subscribe() が追加される。
    """
    return request.app.state.event_bus  # type: ignore[no-any-return]


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


async def get_room_matching_service(session: SessionDep) -> RoomMatchingService:
    """RoomMatchingService を DI 注入する。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.role_profile_repository import (
        SqliteRoleProfileRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.room_role_override_repository import (  # noqa: E501
        SqliteRoomRoleOverrideRepository,
    )

    override_repo = SqliteRoomRoleOverrideRepository(session)
    role_profile_repo = SqliteRoleProfileRepository(session)
    return RoomMatchingService(
        override_repo=override_repo,
        role_profile_repo=role_profile_repo,
    )


async def get_room_role_override_service(session: SessionDep) -> RoomRoleOverrideService:
    """RoomRoleOverrideService を DI 注入する。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.room_role_override_repository import (  # noqa: E501
        SqliteRoomRoleOverrideRepository,
    )

    room_repo = SqliteRoomRepository(session)
    override_repo = SqliteRoomRoleOverrideRepository(session)
    return RoomRoleOverrideService(
        room_repo=room_repo,
        override_repo=override_repo,
        session=session,
    )


async def get_room_service(session: SessionDep) -> RoomService:
    """RoomService を DI 注入する (確定 D)。

    4 つの Repository と session を RoomService に渡す。各 repo は同一 session を
    共有し、service が管理する UoW (``async with session.begin()``) 内で動作する。
    """
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
        SqliteAgentRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
        SqliteEmpireRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.role_profile_repository import (
        SqliteRoleProfileRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.room_role_override_repository import (  # noqa: E501
        SqliteRoomRoleOverrideRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    room_repo = SqliteRoomRepository(session)
    empire_repo = SqliteEmpireRepository(session)
    workflow_repo = SqliteWorkflowRepository(session)
    agent_repo = SqliteAgentRepository(session)
    override_repo = SqliteRoomRoleOverrideRepository(session)
    role_profile_repo = SqliteRoleProfileRepository(session)
    matching_svc = RoomMatchingService(
        override_repo=override_repo,
        role_profile_repo=role_profile_repo,
    )
    return RoomService(
        room_repo=room_repo,
        empire_repo=empire_repo,
        workflow_repo=workflow_repo,
        agent_repo=agent_repo,
        session=session,
        matching_svc=matching_svc,
        override_repo=override_repo,
    )


async def get_workflow_service(session: SessionDep) -> WorkflowService:
    """WorkflowService を DI 注入する。"""
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    workflow_repo = SqliteWorkflowRepository(session)
    room_repo = SqliteRoomRepository(session)
    return WorkflowService(workflow_repo=workflow_repo, room_repo=room_repo, session=session)


async def get_agent_service(session: SessionDep) -> AgentService:
    """AgentService を DI 注入する（§確定 H: EmpireRepository + session を追加）。

    Empire 存在確認のため EmpireRepository を直接受け取る。
    循環依存を避けるため get_empire_service() への依存は持たない
    （workflow_service.py §確定 H と同パターン）。
    """
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
        SqliteAgentRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
        SqliteEmpireRepository,
    )

    agent_repo = SqliteAgentRepository(session)
    empire_repo = SqliteEmpireRepository(session)
    return AgentService(agent_repo=agent_repo, empire_repo=empire_repo, session=session)


AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]


async def get_task_service(session: SessionDep, request: Request) -> TaskService:
    """TaskService を DI 注入する。"""
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
        SqliteAgentRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )

    return TaskService(
        task_repo=SqliteTaskRepository(session),
        room_repo=SqliteRoomRepository(session),
        agent_repo=SqliteAgentRepository(session),
        session=session,
        event_bus=get_event_bus(request),
    )


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


async def get_directive_service(session: SessionDep) -> DirectiveService:
    """DirectiveService を DI 注入する。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
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

    return DirectiveService(
        directive_repo=SqliteDirectiveRepository(session),
        task_repo=SqliteTaskRepository(session),
        room_repo=SqliteRoomRepository(session),
        workflow_repo=SqliteWorkflowRepository(session),
        session=session,
    )


DirectiveServiceDep = Annotated[DirectiveService, Depends(get_directive_service)]


async def get_external_review_gate_service(
    session: SessionDep,
    request: Request,
) -> ExternalReviewGateService:
    """ExternalReviewGateService を DI 注入する。"""
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories.deliverable_template_repository import (  # noqa: E501
        SqliteDeliverableTemplateRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (  # noqa: E501
        SqliteExternalReviewGateRepository,
    )

    repo = SqliteExternalReviewGateRepository(session)
    template_repo = SqliteDeliverableTemplateRepository(session)
    return ExternalReviewGateService(
        repo=repo,
        template_repo=template_repo,
        event_bus=get_event_bus(request),
    )


GateServiceDep = Annotated[ExternalReviewGateService, Depends(get_external_review_gate_service)]


async def get_deliverable_template_service(session: SessionDep) -> DeliverableTemplateService:
    """DeliverableTemplateService を DI 注入する（§確定 A）。"""
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories import (
        deliverable_template_repository as _dt_mod,
    )

    repo = _dt_mod.SqliteDeliverableTemplateRepository(session)
    return DeliverableTemplateService(repo, session)


async def get_role_profile_service(session: SessionDep) -> RoleProfileService:
    """RoleProfileService を DI 注入する（§確定 A）。"""
    # 遅延 import: interfaces → infrastructure の直接依存を避けるため
    # モジュールロード時の循環参照リスクを回避し、
    # 依存方向 interfaces → application → infrastructure を遵守する
    from bakufu.infrastructure.persistence.sqlite.repositories import (
        deliverable_template_repository as _dt_mod,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
        SqliteEmpireRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.role_profile_repository import (
        SqliteRoleProfileRepository,
    )

    return RoleProfileService(
        rp_repo=SqliteRoleProfileRepository(session),
        dt_repo=_dt_mod.SqliteDeliverableTemplateRepository(session),
        empire_repo=SqliteEmpireRepository(session),
        session=session,
    )
