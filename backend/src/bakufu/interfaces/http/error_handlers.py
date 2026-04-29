"""例外ハンドラと CSRF Origin 検証ミドルウェア。"""

from __future__ import annotations

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
        code = NOT_FOUND
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
