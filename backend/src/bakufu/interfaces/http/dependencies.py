"""FastAPI DI ファクトリ群。"""

from __future__ import annotations

import hmac
import os
from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.ports.agent_repository import AgentRepository
from bakufu.application.ports.directive_repository import DirectiveRepository
from bakufu.application.ports.empire_repository import EmpireRepository
from bakufu.application.ports.external_review_gate_repository import (
    ExternalReviewGateRepository,
)
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.application.ports.workflow_repository import WorkflowRepository
from bakufu.application.services.agent_service import AgentService
from bakufu.application.services.directive_service import DirectiveService
from bakufu.application.services.empire_service import EmpireService
from bakufu.application.services.external_review_gate_service import (
    AuthenticatedSubject,
    ExternalReviewGateService,
)
from bakufu.application.services.room_service import RoomService
from bakufu.application.services.task_service import TaskService
from bakufu.application.services.workflow_service import WorkflowService

# 未使用 import の警告抑制: 型チェック用途で再エクスポートしている。
__all__ = [
    "AgentRepository",
    "AgentServiceDep",
    "DirectiveRepository",
    "DirectiveServiceDep",
    "EmpireRepository",
    "ExternalReviewGateRepository",
    "ExternalReviewGateServiceDep",
    "ExternalReviewSubjectDep",
    "HttpDependencies",
    "RoomRepository",
    "SessionDep",
    "TaskRepository",
    "TaskServiceDep",
    "WorkflowRepository",
]


class HttpDependencies:
    """HTTP 境界の共通 DI を閉じ込める。"""

    @classmethod
    async def get_session(cls, request: Request) -> AsyncGenerator[AsyncSession, None]:
        """AsyncSession を yield する DI ファクトリ (確定 E)。"""
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            yield session

    @classmethod
    async def get_empire_service(cls, session: SessionDep) -> EmpireService:
        """EmpireService を DI 注入する。"""
        from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
            SqliteEmpireRepository,
        )

        repo = SqliteEmpireRepository(session)
        return EmpireService(repo, session)

    @classmethod
    async def get_room_service(cls, session: SessionDep) -> RoomService:
        """RoomService を DI 注入する (確定 D)。"""
        from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
            SqliteAgentRepository,
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

        room_repo = SqliteRoomRepository(session)
        empire_repo = SqliteEmpireRepository(session)
        workflow_repo = SqliteWorkflowRepository(session)
        agent_repo = SqliteAgentRepository(session)
        return RoomService(
            room_repo=room_repo,
            empire_repo=empire_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            session=session,
        )

    @classmethod
    async def get_workflow_service(cls, session: SessionDep) -> WorkflowService:
        """WorkflowService を DI 注入する。"""
        from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
            SqliteRoomRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
            SqliteWorkflowRepository,
        )

        workflow_repo = SqliteWorkflowRepository(session)
        room_repo = SqliteRoomRepository(session)
        return WorkflowService(workflow_repo=workflow_repo, room_repo=room_repo, session=session)

    @classmethod
    async def get_agent_service(cls, session: SessionDep) -> AgentService:
        """AgentService を DI 注入する。"""
        from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
            SqliteAgentRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
            SqliteEmpireRepository,
        )

        agent_repo = SqliteAgentRepository(session)
        empire_repo = SqliteEmpireRepository(session)
        return AgentService(agent_repo=agent_repo, empire_repo=empire_repo, session=session)

    @classmethod
    async def get_task_service(cls, session: SessionDep) -> TaskService:
        """TaskService を DI 注入する。"""
        from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
            SqliteAgentRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (  # noqa: E501
            SqliteExternalReviewGateRepository,
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
            external_review_gate_repo=SqliteExternalReviewGateRepository(session),
            session=session,
        )

    @classmethod
    async def get_directive_service(cls, session: SessionDep) -> DirectiveService:
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


SessionDep = Annotated[AsyncSession, Depends(HttpDependencies.get_session)]
AgentServiceDep = Annotated[AgentService, Depends(HttpDependencies.get_agent_service)]
TaskServiceDep = Annotated[TaskService, Depends(HttpDependencies.get_task_service)]
DirectiveServiceDep = Annotated[DirectiveService, Depends(HttpDependencies.get_directive_service)]


class ExternalReviewGateDependencies:
    """ExternalReviewGate HTTP 境界の DI を閉じ込める。"""

    @classmethod
    async def get_service(
        cls,
        session: SessionDep,
    ) -> ExternalReviewGateService:
        """ExternalReviewGateService を DI 注入する。"""
        # 遅延 import: interfaces → infrastructure の直接依存を避けるため
        # モジュールロード時の循環参照リスクを回避し、
        # 依存方向 interfaces → application → infrastructure を遵守する
        from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (  # noqa: E501
            SqliteExternalReviewGateRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )

        repo = SqliteExternalReviewGateRepository(session)
        return ExternalReviewGateService(repo, session, SqliteTaskRepository(session))

    @classmethod
    async def get_subject(
        cls,
        authorization: Annotated[str | None, Header()] = None,
    ) -> AuthenticatedSubject:
        """Bearer token から ExternalReviewGate reviewer subject を解決する。"""
        configured_token = os.environ.get("BAKUFU_OWNER_API_TOKEN", "")
        configured_owner_id = os.environ.get("BAKUFU_OWNER_ID", "")
        if not cls._is_valid_bearer_token(authorization, configured_token):
            raise HTTPException(status_code=401, detail="Authentication failed.")
        try:
            owner_id = UUID(configured_owner_id)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Authentication failed.") from exc
        return AuthenticatedSubject.from_owner_id(owner_id)

    @classmethod
    def _is_valid_bearer_token(cls, authorization: str | None, configured_token: str) -> bool:
        if len(configured_token.encode("utf-8")) < 32:
            return False
        if authorization is None:
            return False
        scheme, separator, token = authorization.partition(" ")
        if separator != " " or scheme.lower() != "bearer":
            return False
        return hmac.compare_digest(token, configured_token)


ExternalReviewGateServiceDep = Annotated[
    ExternalReviewGateService,
    Depends(ExternalReviewGateDependencies.get_service),
]


ExternalReviewSubjectDep = Annotated[
    AuthenticatedSubject,
    Depends(ExternalReviewGateDependencies.get_subject),
]
