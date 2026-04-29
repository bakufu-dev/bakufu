"""例外ハンドラと CSRF Origin 検証ミドルウェア。"""

from __future__ import annotations

import re
from typing import Any, Final

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from bakufu.interfaces.http.schemas.common import ErrorDetail, ErrorResponse

# ── 確定 A: エラーコード定数 ──────────────────────────────────────────
NOT_FOUND: Final[str] = "not_found"
VALIDATION_ERROR: Final[str] = "validation_error"
INTERNAL_ERROR: Final[str] = "internal_error"
FORBIDDEN: Final[str] = "forbidden"
CONFLICT: Final[str] = "conflict"


def _error_response(code: str, message: str, status_code: int) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(content=body.model_dump(), status_code=status_code)


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """StarletteHTTPException を ErrorResponse に変換する。

    404 は "not_found"、その他は status_code に応じた code を返す。
    関数名 not_found_handler では 401/405/409 等も誤って 404 として返すため
    status_code で正確に分岐する (ヘルスバーグ指摘 #1)。
    """
    from starlette.exceptions import HTTPException as StarletteHTTPException

    if not isinstance(exc, StarletteHTTPException):
        raise TypeError(f"Expected StarletteHTTPException, got {type(exc).__name__}")

    status = exc.status_code
    if status == 404:
        # MSG-HAF-001: 確定文言 "Resource not found." を使う (exc.detail は "Not Found" で異なる)
        return _error_response(NOT_FOUND, "Resource not found.", status)
    elif status == 403:
        code = FORBIDDEN
    elif status == 405:
        code = "method_not_allowed"
    else:
        code = f"http_error_{status}"

    return _error_response(code, str(exc.detail) if exc.detail else "HTTP error.", status)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise TypeError(f"Expected RequestValidationError, got {type(exc).__name__}")
    validation_exc = exc
    detail = "; ".join(
        f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in validation_exc.errors()
    )
    return _error_response(VALIDATION_ERROR, f"Request validation failed: {detail}", 422)


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(INTERNAL_ERROR, "An internal server error occurred.", 500)


# ── 確定 C: empire 専用例外ハンドラ群 ────────────────────────────────────
# 登録順: 既存 HTTPException / RequestValidationError / Exception ハンドラより前
# (より具体的な例外を先に登録する FastAPI 慣習に従う)


async def empire_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``EmpireNotFoundError`` → HTTP 404 / not_found (MSG-EM-HTTP-002)。"""
    from bakufu.application.exceptions.empire_exceptions import EmpireNotFoundError

    if not isinstance(exc, EmpireNotFoundError):
        raise TypeError(f"Expected EmpireNotFoundError, got {type(exc).__name__}")
    return _error_response(NOT_FOUND, "Empire not found.", 404)


async def empire_already_exists_handler(request: Request, exc: Exception) -> JSONResponse:
    """``EmpireAlreadyExistsError`` → HTTP 409 / conflict (MSG-EM-HTTP-001)。"""
    from bakufu.application.exceptions.empire_exceptions import EmpireAlreadyExistsError

    if not isinstance(exc, EmpireAlreadyExistsError):
        raise TypeError(f"Expected EmpireAlreadyExistsError, got {type(exc).__name__}")
    return _error_response(CONFLICT, "Empire already exists.", 409)


async def empire_archived_handler(request: Request, exc: Exception) -> JSONResponse:
    """``EmpireArchivedError`` → HTTP 409 / conflict (MSG-EM-HTTP-003)。"""
    from bakufu.application.exceptions.empire_exceptions import EmpireArchivedError

    if not isinstance(exc, EmpireArchivedError):
        raise TypeError(f"Expected EmpireArchivedError, got {type(exc).__name__}")
    return _error_response(CONFLICT, "Empire is archived and cannot be modified.", 409)


# 確定 C: [FAIL] プレフィックスと \nNext:... 除去パターン (凍結)
_FAIL_PREFIX_RE: Final = re.compile(r"^\[FAIL\]\s*")


async def empire_invariant_violation_handler(request: Request, exc: Exception) -> JSONResponse:
    """``EmpireInvariantViolation`` → HTTP 422 / validation_error (MSG-EM-HTTP-004)。

    前処理ルール (確定 C):
    1. ``[FAIL] `` プレフィックスを除去
    2. ``\\nNext:`` 以降を除去して domain 内部フォーマットを隠蔽する
    """
    from bakufu.domain.exceptions import EmpireInvariantViolation

    if not isinstance(exc, EmpireInvariantViolation):
        raise TypeError(f"Expected EmpireInvariantViolation, got {type(exc).__name__}")
    raw = str(exc)
    cleaned = _FAIL_PREFIX_RE.sub("", raw).split("\nNext:")[0].strip()
    return _error_response(VALIDATION_ERROR, cleaned, 422)


# ── 確定 C: room 専用例外ハンドラ群 ──────────────────────────────────────
# 登録順: empire ハンドラ群の直後 (より具体的な例外を先に登録する FastAPI 慣習)


async def room_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``RoomNotFoundError`` → HTTP 404 / not_found (MSG-RM-HTTP-002)。"""
    from bakufu.application.exceptions.room_exceptions import RoomNotFoundError

    if not isinstance(exc, RoomNotFoundError):
        raise TypeError(f"Expected RoomNotFoundError, got {type(exc).__name__}")
    return _error_response(NOT_FOUND, "Room not found.", 404)


async def room_name_already_exists_handler(request: Request, exc: Exception) -> JSONResponse:
    """``RoomNameAlreadyExistsError`` → HTTP 409 / conflict (MSG-RM-HTTP-001)。"""
    from bakufu.application.exceptions.room_exceptions import RoomNameAlreadyExistsError

    if not isinstance(exc, RoomNameAlreadyExistsError):
        raise TypeError(f"Expected RoomNameAlreadyExistsError, got {type(exc).__name__}")
    return _error_response(CONFLICT, "Room name already exists in this empire.", 409)


async def room_archived_handler(request: Request, exc: Exception) -> JSONResponse:
    """``RoomArchivedError`` → HTTP 409 / conflict (MSG-RM-HTTP-003)。"""
    from bakufu.application.exceptions.room_exceptions import RoomArchivedError

    if not isinstance(exc, RoomArchivedError):
        raise TypeError(f"Expected RoomArchivedError, got {type(exc).__name__}")
    return _error_response(CONFLICT, "Room is archived and cannot be modified.", 409)


async def workflow_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``WorkflowNotFoundError`` → HTTP 404 / not_found (MSG-WF-HTTP-001)。"""
    from bakufu.application.exceptions.workflow_exceptions import WorkflowNotFoundError

    if not isinstance(exc, WorkflowNotFoundError):
        raise TypeError(f"Expected WorkflowNotFoundError, got {type(exc).__name__}")
    return _error_response(NOT_FOUND, "Workflow not found.", 404)


async def workflow_archived_handler(request: Request, exc: Exception) -> JSONResponse:
    """``WorkflowArchivedError`` → HTTP 409 / conflict (MSG-WF-HTTP-002)。"""
    from bakufu.application.exceptions.workflow_exceptions import WorkflowArchivedError

    if not isinstance(exc, WorkflowArchivedError):
        raise TypeError(f"Expected WorkflowArchivedError, got {type(exc).__name__}")
    return _error_response(CONFLICT, "Workflow is archived and cannot be modified.", 409)


async def workflow_preset_not_found_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """``WorkflowPresetNotFoundError`` → HTTP 404 / not_found (MSG-WF-HTTP-004)。"""
    from bakufu.application.exceptions.workflow_exceptions import WorkflowPresetNotFoundError

    if not isinstance(exc, WorkflowPresetNotFoundError):
        raise TypeError(
            f"Expected WorkflowPresetNotFoundError, got {type(exc).__name__}"
        )
    return _error_response(NOT_FOUND, "Workflow preset not found.", 404)


async def workflow_invariant_violation_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """``WorkflowInvariantViolation`` → HTTP 422 / validation_error (MSG-WF-HTTP-005)。

    前処理ルール (確定 C):
    1. ``[FAIL] `` プレフィックスを除去
    2. ``\\nNext:`` 以降を除去して domain 内部フォーマットを隠蔽する
    """
    from bakufu.domain.exceptions import WorkflowInvariantViolation

    if not isinstance(exc, WorkflowInvariantViolation):
        raise TypeError(
            f"Expected WorkflowInvariantViolation, got {type(exc).__name__}"
        )
    raw = str(exc)
    cleaned = _FAIL_PREFIX_RE.sub("", raw).split("\nNext:")[0].strip()
    return _error_response(VALIDATION_ERROR, cleaned, 422)


async def agent_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``AgentNotFoundError`` → HTTP 404 / not_found (MSG-RM-HTTP-004)。"""
    from bakufu.application.exceptions.room_exceptions import AgentNotFoundError

    if not isinstance(exc, AgentNotFoundError):
        raise TypeError(f"Expected AgentNotFoundError, got {type(exc).__name__}")
    return _error_response(NOT_FOUND, "Agent not found.", 404)


async def room_invariant_violation_handler(request: Request, exc: Exception) -> JSONResponse:
    """``RoomInvariantViolation`` → HTTP 404 or 422 (MSG-RM-HTTP-005 / MSG-RM-HTTP-007)。

    処理ルール (確定 C 凍結):
    1. ``kind='member_not_found'`` → HTTP 404 / not_found (MSG-RM-HTTP-005)
    2. その他の kind → HTTP 422 / validation_error (MSG-RM-HTTP-007 前処理済み本文)

    前処理ルール (empire http-api §確定C と同一パターン):
    1. ``[FAIL] `` プレフィックスを除去
    2. ``\\nNext:`` 以降を除去して domain 内部フォーマットを隠蔽する
    """
    from bakufu.domain.exceptions import RoomInvariantViolation

    if not isinstance(exc, RoomInvariantViolation):
        raise TypeError(f"Expected RoomInvariantViolation, got {type(exc).__name__}")

    if exc.kind == "member_not_found":
        return _error_response(NOT_FOUND, "Agent membership not found in this room.", 404)

    raw = str(exc)
    cleaned = _FAIL_PREFIX_RE.sub("", raw).split("\nNext:")[0].strip()
    return _error_response(VALIDATION_ERROR, cleaned, 422)


# ── 確定 D: CSRF Origin 検証ミドルウェア ─────────────────────────────────
_SAFE_METHODS: Final[frozenset[str]] = frozenset({"GET", "OPTIONS", "HEAD"})


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    """MVP 段階の CSRF 防御 (Cookie なし前提)。

    - GET / OPTIONS / HEAD: スキップ
    - POST etc. + Origin なし: MVP では通過 (AI エージェント・curl 対応)
    - POST etc. + Origin あり + 許可一覧不一致: 403

    Phase 2 で Cookie セッション追加時に「Origin なし → 403」に変更。
    """

    def __init__(self, app: Any, *, allowed_origins: list[str]) -> None:
        super().__init__(app)
        self._allowed: Final[frozenset[str]] = frozenset(allowed_origins)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        origin = request.headers.get("origin")
        if origin is None:
            # MVP: Cookie なし環境では CSRF リスクが成立しない。
            # AI エージェント・SDK は Origin を送信しないため通過させる。
            return await call_next(request)

        if origin not in self._allowed:
            body = ErrorResponse(
                error=ErrorDetail(code=FORBIDDEN, message="CSRF check failed: Origin not allowed.")
            )
            return JSONResponse(content=body.model_dump(), status_code=403)

        return await call_next(request)
