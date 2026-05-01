"""Task / Gate 専用ハンドラ群。"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from bakufu.interfaces.http.error_handlers._common import (
    CONFLICT,
    FORBIDDEN,
    NOT_FOUND,
    VALIDATION_ERROR,
    clean_domain_message,
    error_response,
)

# ── Task ──────────────────────────────────────────────────────────────────────


async def task_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``TaskNotFoundError`` → HTTP 404 / not_found。"""
    from bakufu.application.exceptions.task_exceptions import TaskNotFoundError

    if not isinstance(exc, TaskNotFoundError):
        raise TypeError(f"Expected TaskNotFoundError, got {type(exc).__name__}")
    return error_response(NOT_FOUND, "Task not found.", 404)


async def task_state_conflict_handler(request: Request, exc: Exception) -> JSONResponse:
    """``TaskStateConflictError`` → HTTP 409 / conflict。"""
    from bakufu.application.exceptions.task_exceptions import TaskStateConflictError

    if not isinstance(exc, TaskStateConflictError):
        raise TypeError(f"Expected TaskStateConflictError, got {type(exc).__name__}")
    return error_response(CONFLICT, clean_domain_message(str(exc)), 409)


async def task_authorization_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """``TaskAuthorizationError`` → HTTP 403 / forbidden。"""
    from bakufu.application.exceptions.task_exceptions import TaskAuthorizationError

    if not isinstance(exc, TaskAuthorizationError):
        raise TypeError(f"Expected TaskAuthorizationError, got {type(exc).__name__}")
    return error_response(FORBIDDEN, exc.reason, 403)


async def task_invariant_violation_handler(request: Request, exc: Exception) -> JSONResponse:
    """``TaskInvariantViolation`` → HTTP 422 / validation_error。"""
    from bakufu.domain.exceptions import TaskInvariantViolation

    if not isinstance(exc, TaskInvariantViolation):
        raise TypeError(f"Expected TaskInvariantViolation, got {type(exc).__name__}")
    return error_response(VALIDATION_ERROR, clean_domain_message(str(exc)), 422)


# ── Gate ─────────────────────────────────────────────────────────────────────
# 確定 P-3: MSG 確定文言は basic-design.md §ユーザー向けメッセージ一覧 /
# detailed-design.md §MSG 確定文言表 で凍結されている。


async def gate_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``GateNotFoundError`` → HTTP 404 / not_found (MSG-ERG-HTTP-001)。"""
    from bakufu.application.exceptions.gate_exceptions import GateNotFoundError

    if not isinstance(exc, GateNotFoundError):
        raise TypeError(f"Expected GateNotFoundError, got {type(exc).__name__}")
    return error_response(
        NOT_FOUND,
        "[FAIL] Gate not found.\nNext: Verify the gate ID and retry,"
        " or list available gates via GET /api/gates.",
        404,
    )


async def gate_already_decided_handler(request: Request, exc: Exception) -> JSONResponse:
    """``GateAlreadyDecidedError`` → HTTP 409 / conflict (MSG-ERG-HTTP-002)。"""
    from bakufu.application.exceptions.gate_exceptions import GateAlreadyDecidedError

    if not isinstance(exc, GateAlreadyDecidedError):
        raise TypeError(f"Expected GateAlreadyDecidedError, got {type(exc).__name__}")
    return error_response(
        CONFLICT,
        "[FAIL] Gate decision is already finalized and cannot be changed.\n"
        "Next: To restart the review process, create a new gate for this task"
        " via the application layer.",
        409,
    )


async def gate_authorization_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """``GateAuthorizationError`` → HTTP 403 / forbidden (MSG-ERG-HTTP-003)。"""
    from bakufu.application.exceptions.gate_exceptions import GateAuthorizationError

    if not isinstance(exc, GateAuthorizationError):
        raise TypeError(f"Expected GateAuthorizationError, got {type(exc).__name__}")
    return error_response(
        FORBIDDEN,
        "[FAIL] Not authorized to decide on this gate.\n"
        "Next: Retry with the Bearer token corresponding to the gate's reviewer_id.",
        403,
    )
