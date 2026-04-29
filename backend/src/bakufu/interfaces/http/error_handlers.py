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


async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(NOT_FOUND, "Resource not found.", 404)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    validation_exc = exc if isinstance(exc, RequestValidationError) else RequestValidationError([])
    detail = "; ".join(
        f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
        for e in validation_exc.errors()
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
