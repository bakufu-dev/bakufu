"""FastAPI アプリケーション初期化。"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from bakufu.interfaces.http.error_handlers import (
    CsrfOriginMiddleware,
    agent_archived_handler,
    agent_invariant_violation_handler,
    agent_name_already_exists_handler,
    agent_not_found_handler,
    composition_cycle_handler,
    deliverable_template_invariant_violation_handler,
    deliverable_template_not_found_handler,
    deliverable_template_version_downgrade_handler,
    directive_invariant_violation_handler,
    empire_already_exists_handler,
    empire_archived_handler,
    empire_invariant_violation_handler,
    empire_not_found_handler,
    gate_already_decided_handler,
    gate_authorization_error_handler,
    gate_not_found_handler,
    http_exception_handler,
    internal_error_handler,
    invalid_role_handler,
    pydantic_validation_error_handler,
    role_profile_invariant_violation_handler,
    role_profile_not_found_handler,
    room_archived_handler,
    room_deliverable_matching_error_handler,
    room_invariant_violation_handler,
    room_name_already_exists_handler,
    room_not_found_handler,
    room_role_override_invariant_violation_handler,
    task_authorization_error_handler,
    task_invariant_violation_handler,
    task_not_found_handler,
    task_state_conflict_handler,
    validation_error_handler,
    workflow_archived_handler,
    workflow_invariant_violation_handler,
    workflow_irreversible_handler,
    workflow_not_found_handler,
    workflow_preset_not_found_handler,
)
from bakufu.interfaces.http.routers.agents import agents_router, empire_agents_router
from bakufu.interfaces.http.routers.deliverable_template import (
    router as deliverable_template_router,
)
from bakufu.interfaces.http.routers.directives import room_directives_router
from bakufu.interfaces.http.routers.empire import router as empire_router
from bakufu.interfaces.http.routers.external_review_gates import gates_router, task_gates_router
from bakufu.interfaces.http.routers.health import router as health_router
from bakufu.interfaces.http.routers.role_profile import router as role_profile_router
from bakufu.interfaces.http.routers.rooms import empire_rooms_router, rooms_router
from bakufu.interfaces.http.routers.tasks import room_tasks_router, tasks_router
from bakufu.interfaces.http.routers.workflows import room_workflows_router, workflows_router


def _parse_allowed_origins() -> list[str]:
    """BAKUFU_ALLOWED_ORIGINS 環境変数をカンマ区切りでパース (確定 C)。"""
    raw = os.environ.get("BAKUFU_ALLOWED_ORIGINS", "")
    if not raw.strip():
        return ["http://localhost:5173"]
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """lifespan: startup で session_factory / event_bus を保持、shutdown で dispose (確定 B)。"""
    from bakufu.infrastructure.config import data_dir as data_dir_mod
    from bakufu.infrastructure.event_bus import InMemoryEventBus
    from bakufu.infrastructure.persistence.sqlite.engine import create_engine
    from bakufu.infrastructure.persistence.sqlite.session import make_session_factory

    resolved_data_dir = data_dir_mod.resolve()
    url = f"sqlite+aiosqlite:///{resolved_data_dir / 'bakufu.db'}"
    engine = create_engine(url)
    session_factory = make_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory
    # REQ-WSB-007: InMemoryEventBus をアプリケーションライフタイムで共有
    # Issue #159 で ConnectionManager の subscribe() が追加される
    app.state.event_bus = InMemoryEventBus()

    yield

    await engine.dispose()


def create_app() -> FastAPI:
    """FastAPI アプリケーションを生成して返す。"""
    disable_docs = os.environ.get("BAKUFU_DISABLE_DOCS", "").lower() in {"true", "1"}
    allowed_origins = _parse_allowed_origins()

    app = FastAPI(
        title="bakufu API",
        version="0.1.0",
        openapi_url=None if disable_docs else "/openapi.json",
        docs_url=None if disable_docs else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    # CORS (確定 C)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        allow_credentials=False,
    )

    # CSRF Origin 検証 (確定 D)
    app.add_middleware(CsrfOriginMiddleware, allowed_origins=allowed_origins)

    # エラーハンドラ
    # empire / room 専用ハンドラを先に登録する (より具体的な例外を優先, 確定 C)
    from pydantic import ValidationError

    from bakufu.application.exceptions.agent_exceptions import (
        AgentArchivedError,
        AgentNameAlreadyExistsError,
        AgentNotFoundError,
    )
    from bakufu.application.exceptions.deliverable_template_exceptions import (
        CompositionCycleError,
        DeliverableTemplateNotFoundError,
        DeliverableTemplateVersionDowngradeError,
        InvalidRoleError,
        RoleProfileNotFoundError,
    )
    from bakufu.application.exceptions.empire_exceptions import (
        EmpireAlreadyExistsError,
        EmpireArchivedError,
        EmpireNotFoundError,
    )
    from bakufu.application.exceptions.gate_exceptions import (
        GateAlreadyDecidedError,
        GateAuthorizationError,
        GateNotFoundError,
    )
    from bakufu.application.exceptions.room_exceptions import (
        RoomArchivedError,
        RoomDeliverableMatchingError,
        RoomNameAlreadyExistsError,
        RoomNotFoundError,
    )
    from bakufu.application.exceptions.task_exceptions import (
        TaskAuthorizationError,
        TaskNotFoundError,
        TaskStateConflictError,
    )
    from bakufu.application.exceptions.workflow_exceptions import (
        WorkflowArchivedError,
        WorkflowIrreversibleError,
        WorkflowNotFoundError,
        WorkflowPresetNotFoundError,
    )
    from bakufu.domain.exceptions import (
        AgentInvariantViolation,
        DeliverableTemplateInvariantViolation,
        DirectiveInvariantViolation,
        EmpireInvariantViolation,
        RoleProfileInvariantViolation,
        RoomInvariantViolation,
        RoomRoleOverrideInvariantViolation,
        TaskInvariantViolation,
        WorkflowInvariantViolation,
    )

    app.add_exception_handler(EmpireNotFoundError, empire_not_found_handler)
    app.add_exception_handler(EmpireAlreadyExistsError, empire_already_exists_handler)
    app.add_exception_handler(EmpireArchivedError, empire_archived_handler)
    app.add_exception_handler(EmpireInvariantViolation, empire_invariant_violation_handler)
    # room 専用ハンドラ (empire ハンドラ群の直後 / HTTPException・Exception より前)
    app.add_exception_handler(RoomNotFoundError, room_not_found_handler)
    app.add_exception_handler(RoomNameAlreadyExistsError, room_name_already_exists_handler)
    app.add_exception_handler(RoomArchivedError, room_archived_handler)
    app.add_exception_handler(RoomDeliverableMatchingError, room_deliverable_matching_error_handler)
    app.add_exception_handler(
        RoomRoleOverrideInvariantViolation,
        room_role_override_invariant_violation_handler,
    )
    app.add_exception_handler(WorkflowNotFoundError, workflow_not_found_handler)
    app.add_exception_handler(WorkflowArchivedError, workflow_archived_handler)
    app.add_exception_handler(WorkflowIrreversibleError, workflow_irreversible_handler)
    app.add_exception_handler(WorkflowPresetNotFoundError, workflow_preset_not_found_handler)
    app.add_exception_handler(WorkflowInvariantViolation, workflow_invariant_violation_handler)
    # agent 専用ハンドラ (workflow ハンドラ群の直後 / HTTPException・Exception より前)
    app.add_exception_handler(AgentNotFoundError, agent_not_found_handler)
    app.add_exception_handler(AgentNameAlreadyExistsError, agent_name_already_exists_handler)
    app.add_exception_handler(AgentArchivedError, agent_archived_handler)
    app.add_exception_handler(AgentInvariantViolation, agent_invariant_violation_handler)
    app.add_exception_handler(RoomInvariantViolation, room_invariant_violation_handler)
    app.add_exception_handler(DirectiveInvariantViolation, directive_invariant_violation_handler)
    app.add_exception_handler(TaskNotFoundError, task_not_found_handler)
    app.add_exception_handler(TaskStateConflictError, task_state_conflict_handler)
    app.add_exception_handler(TaskAuthorizationError, task_authorization_error_handler)
    app.add_exception_handler(TaskInvariantViolation, task_invariant_violation_handler)
    # gate 専用ハンドラ (P-3: task ハンドラ群の直後)
    app.add_exception_handler(GateNotFoundError, gate_not_found_handler)
    app.add_exception_handler(GateAlreadyDecidedError, gate_already_decided_handler)
    app.add_exception_handler(GateAuthorizationError, gate_authorization_error_handler)
    # deliverable-template / role-profile 専用ハンドラ (gate ハンドラ群の直後)
    app.add_exception_handler(
        DeliverableTemplateNotFoundError, deliverable_template_not_found_handler
    )
    app.add_exception_handler(RoleProfileNotFoundError, role_profile_not_found_handler)
    app.add_exception_handler(CompositionCycleError, composition_cycle_handler)
    app.add_exception_handler(
        DeliverableTemplateVersionDowngradeError,
        deliverable_template_version_downgrade_handler,
    )
    app.add_exception_handler(
        DeliverableTemplateInvariantViolation,
        deliverable_template_invariant_violation_handler,
    )
    app.add_exception_handler(
        RoleProfileInvariantViolation,
        role_profile_invariant_violation_handler,
    )
    # InvalidRoleError: role パスパラメータの不正値を 422 に変換（スコープ限定の専用例外）
    app.add_exception_handler(InvalidRoleError, invalid_role_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)

    # ルーター
    app.include_router(health_router)
    app.include_router(empire_router)
    app.include_router(empire_rooms_router)
    app.include_router(rooms_router)
    app.include_router(room_workflows_router)
    app.include_router(workflows_router)
    app.include_router(empire_agents_router)
    app.include_router(agents_router)
    app.include_router(room_directives_router)
    app.include_router(room_tasks_router)
    app.include_router(tasks_router)
    app.include_router(gates_router)
    app.include_router(task_gates_router)
    app.include_router(deliverable_template_router)
    app.include_router(role_profile_router)

    return app


app = create_app()
