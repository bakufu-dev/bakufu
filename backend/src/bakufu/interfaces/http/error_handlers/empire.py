"""Empire / Room / Workflow / Agent / Directive 専用ハンドラ群。"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from bakufu.interfaces.http.error_handlers._common import (
    CONFLICT,
    NOT_FOUND,
    VALIDATION_ERROR,
    clean_domain_message,
    error_response,
)
from bakufu.interfaces.http.schemas.common import ErrorDetail, ErrorResponse

# ── Empire ───────────────────────────────────────────────────────────────────


async def empire_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``EmpireNotFoundError`` → HTTP 404 / not_found (MSG-EM-HTTP-002)。"""
    from bakufu.application.exceptions.empire_exceptions import EmpireNotFoundError

    if not isinstance(exc, EmpireNotFoundError):
        raise TypeError(f"Expected EmpireNotFoundError, got {type(exc).__name__}")
    return error_response(NOT_FOUND, "Empire not found.", 404)


async def empire_already_exists_handler(request: Request, exc: Exception) -> JSONResponse:
    """``EmpireAlreadyExistsError`` → HTTP 409 / conflict (MSG-EM-HTTP-001)。"""
    from bakufu.application.exceptions.empire_exceptions import EmpireAlreadyExistsError

    if not isinstance(exc, EmpireAlreadyExistsError):
        raise TypeError(f"Expected EmpireAlreadyExistsError, got {type(exc).__name__}")
    return error_response(CONFLICT, "Empire already exists.", 409)


async def empire_archived_handler(request: Request, exc: Exception) -> JSONResponse:
    """``EmpireArchivedError`` → HTTP 409 / conflict (MSG-EM-HTTP-003)。"""
    from bakufu.application.exceptions.empire_exceptions import EmpireArchivedError

    if not isinstance(exc, EmpireArchivedError):
        raise TypeError(f"Expected EmpireArchivedError, got {type(exc).__name__}")
    return error_response(CONFLICT, "Empire is archived and cannot be modified.", 409)


async def empire_invariant_violation_handler(request: Request, exc: Exception) -> JSONResponse:
    """``EmpireInvariantViolation`` → HTTP 422 / validation_error (MSG-EM-HTTP-004)。"""
    from bakufu.domain.exceptions import EmpireInvariantViolation

    if not isinstance(exc, EmpireInvariantViolation):
        raise TypeError(f"Expected EmpireInvariantViolation, got {type(exc).__name__}")
    return error_response(VALIDATION_ERROR, clean_domain_message(str(exc)), 422)


# ── Room ─────────────────────────────────────────────────────────────────────


async def room_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``RoomNotFoundError`` → HTTP 404 / not_found (MSG-RM-HTTP-002)。"""
    from bakufu.application.exceptions.room_exceptions import RoomNotFoundError

    if not isinstance(exc, RoomNotFoundError):
        raise TypeError(f"Expected RoomNotFoundError, got {type(exc).__name__}")
    return error_response(NOT_FOUND, "Room not found.", 404)


async def room_name_already_exists_handler(request: Request, exc: Exception) -> JSONResponse:
    """``RoomNameAlreadyExistsError`` → HTTP 409 / conflict (MSG-RM-HTTP-001)。"""
    from bakufu.application.exceptions.room_exceptions import RoomNameAlreadyExistsError

    if not isinstance(exc, RoomNameAlreadyExistsError):
        raise TypeError(f"Expected RoomNameAlreadyExistsError, got {type(exc).__name__}")
    return error_response(CONFLICT, "Room name already exists in this empire.", 409)


async def room_archived_handler(request: Request, exc: Exception) -> JSONResponse:
    """``RoomArchivedError`` → HTTP 409 / conflict (MSG-RM-HTTP-003)。"""
    from bakufu.application.exceptions.room_exceptions import RoomArchivedError

    if not isinstance(exc, RoomArchivedError):
        raise TypeError(f"Expected RoomArchivedError, got {type(exc).__name__}")
    return error_response(CONFLICT, "Room is archived and cannot be modified.", 409)


async def room_invariant_violation_handler(request: Request, exc: Exception) -> JSONResponse:
    """``RoomInvariantViolation`` → HTTP 404 or 422 (MSG-RM-HTTP-005 / MSG-RM-HTTP-007)。

    処理ルール (確定 C 凍結):
    1. ``kind='member_not_found'`` → HTTP 404 / not_found (MSG-RM-HTTP-005)
    2. その他の kind → HTTP 422 / validation_error (MSG-RM-HTTP-007 前処理済み本文)
    """
    from bakufu.domain.exceptions import RoomInvariantViolation

    if not isinstance(exc, RoomInvariantViolation):
        raise TypeError(f"Expected RoomInvariantViolation, got {type(exc).__name__}")

    if exc.kind == "member_not_found":
        return error_response(NOT_FOUND, "Agent membership not found in this room.", 404)

    return error_response(VALIDATION_ERROR, clean_domain_message(str(exc)), 422)


# ── Workflow ──────────────────────────────────────────────────────────────────


async def workflow_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``WorkflowNotFoundError`` → HTTP 404 / not_found (MSG-WF-HTTP-001)。"""
    from bakufu.application.exceptions.workflow_exceptions import WorkflowNotFoundError

    if not isinstance(exc, WorkflowNotFoundError):
        raise TypeError(f"Expected WorkflowNotFoundError, got {type(exc).__name__}")
    return error_response(NOT_FOUND, "Workflow not found.", 404)


async def workflow_archived_handler(request: Request, exc: Exception) -> JSONResponse:
    """``WorkflowArchivedError`` → HTTP 409 / conflict (MSG-WF-HTTP-002)。"""
    from bakufu.application.exceptions.workflow_exceptions import WorkflowArchivedError

    if not isinstance(exc, WorkflowArchivedError):
        raise TypeError(f"Expected WorkflowArchivedError, got {type(exc).__name__}")
    return error_response(CONFLICT, "Workflow is archived and cannot be modified.", 409)


async def workflow_preset_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``WorkflowPresetNotFoundError`` → HTTP 404 / not_found (MSG-WF-HTTP-004)。"""
    from bakufu.application.exceptions.workflow_exceptions import WorkflowPresetNotFoundError

    if not isinstance(exc, WorkflowPresetNotFoundError):
        raise TypeError(f"Expected WorkflowPresetNotFoundError, got {type(exc).__name__}")
    return error_response(NOT_FOUND, "Workflow preset not found.", 404)


async def workflow_irreversible_handler(request: Request, exc: Exception) -> JSONResponse:
    """``WorkflowIrreversibleError`` → HTTP 409 / conflict (MSG-WF-HTTP-008)。"""
    from bakufu.application.exceptions.workflow_exceptions import WorkflowIrreversibleError

    if not isinstance(exc, WorkflowIrreversibleError):
        raise TypeError(f"Expected WorkflowIrreversibleError, got {type(exc).__name__}")
    return error_response(
        CONFLICT,
        "Workflow contains masked notify_channels and cannot be modified."
        " Please recreate the workflow with new webhook URLs.",
        409,
    )


async def workflow_invariant_violation_handler(request: Request, exc: Exception) -> JSONResponse:
    """``WorkflowInvariantViolation`` → HTTP 422 / validation_error (MSG-WF-HTTP-005)。"""
    from bakufu.domain.exceptions import WorkflowInvariantViolation

    if not isinstance(exc, WorkflowInvariantViolation):
        raise TypeError(f"Expected WorkflowInvariantViolation, got {type(exc).__name__}")
    return error_response(VALIDATION_ERROR, clean_domain_message(str(exc)), 422)


# ── Agent ─────────────────────────────────────────────────────────────────────


async def agent_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``AgentNotFoundError`` → HTTP 404 / not_found (MSG-AG-HTTP-001)。"""
    from bakufu.application.exceptions.agent_exceptions import AgentNotFoundError

    if not isinstance(exc, AgentNotFoundError):
        raise TypeError(f"Expected AgentNotFoundError, got {type(exc).__name__}")
    return error_response(NOT_FOUND, "Agent not found.", 404)


async def agent_name_already_exists_handler(request: Request, exc: Exception) -> JSONResponse:
    """``AgentNameAlreadyExistsError`` → HTTP 409 / conflict (MSG-AG-HTTP-002)。"""
    from bakufu.application.exceptions.agent_exceptions import AgentNameAlreadyExistsError

    if not isinstance(exc, AgentNameAlreadyExistsError):
        raise TypeError(f"Expected AgentNameAlreadyExistsError, got {type(exc).__name__}")
    return error_response(CONFLICT, "Agent with this name already exists in the Empire.", 409)


async def agent_archived_handler(request: Request, exc: Exception) -> JSONResponse:
    """``AgentArchivedError`` → HTTP 409 / conflict (MSG-AG-HTTP-003)。"""
    from bakufu.application.exceptions.agent_exceptions import AgentArchivedError

    if not isinstance(exc, AgentArchivedError):
        raise TypeError(f"Expected AgentArchivedError, got {type(exc).__name__}")
    return error_response(CONFLICT, "Agent is archived and cannot be modified.", 409)


async def agent_invariant_violation_handler(request: Request, exc: Exception) -> JSONResponse:
    """``AgentInvariantViolation`` → HTTP 422 / validation_error (MSG-AG-HTTP-004)。"""
    from bakufu.domain.exceptions import AgentInvariantViolation

    if not isinstance(exc, AgentInvariantViolation):
        raise TypeError(f"Expected AgentInvariantViolation, got {type(exc).__name__}")
    return error_response(VALIDATION_ERROR, clean_domain_message(str(exc)), 422)


# ── Directive ─────────────────────────────────────────────────────────────────


async def directive_invariant_violation_handler(request: Request, exc: Exception) -> JSONResponse:
    """``DirectiveInvariantViolation`` → HTTP 422 / validation_error。"""
    from bakufu.domain.exceptions import DirectiveInvariantViolation

    if not isinstance(exc, DirectiveInvariantViolation):
        raise TypeError(f"Expected DirectiveInvariantViolation, got {type(exc).__name__}")
    return error_response(VALIDATION_ERROR, clean_domain_message(str(exc)), 422)


# ── Room Matching ─────────────────────────────────────────────────────────────


async def room_deliverable_matching_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """``RoomDeliverableMatchingError`` → HTTP 422 / deliverable_matching_failed。

    MSG-RM-MATCH-001 対応。detail.missing に不足 deliverable 全件を含む。
    """
    from bakufu.application.exceptions.room_exceptions import RoomDeliverableMatchingError

    if not isinstance(exc, RoomDeliverableMatchingError):
        raise TypeError(f"Expected RoomDeliverableMatchingError, got {type(exc).__name__}")

    first_line = exc.message.split("\n")[0]
    detail: dict[str, object] = {
        "room_id": exc.room_id,
        "role": exc.role,
        "missing": [
            {
                "stage_id": m.stage_id,
                "stage_name": m.stage_name,
                "template_id": m.template_id,
            }
            for m in exc.missing
        ],
    }
    body = ErrorResponse(
        error=ErrorDetail(
            code="deliverable_matching_failed",
            message=first_line,
            detail=detail,
        )
    )
    return JSONResponse(content=body.model_dump(), status_code=422)


async def room_role_override_invariant_violation_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """``RoomRoleOverrideInvariantViolation`` → HTTP 422 / validation_error。"""
    from bakufu.domain.exceptions import RoomRoleOverrideInvariantViolation

    if not isinstance(exc, RoomRoleOverrideInvariantViolation):
        raise TypeError(f"Expected RoomRoleOverrideInvariantViolation, got {type(exc).__name__}")
    return error_response(VALIDATION_ERROR, clean_domain_message(str(exc)), 422)
