"""CSRF Origin 検証ミドルウェア。"""

from __future__ import annotations

from typing import Any, Final

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from bakufu.interfaces.http.error_handlers._common import FORBIDDEN
from bakufu.interfaces.http.schemas.common import ErrorDetail, ErrorResponse

# 確定 D: CSRF チェック対象外メソッド
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
