"""基盤ハンドラ群: HTTP / RequestValidation / Internal / Pydantic ValidationError。"""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from bakufu.interfaces.http.error_handlers._common import (
    INTERNAL_ERROR,
    NOT_FOUND,
    VALIDATION_ERROR,
    error_response,
)


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
        return error_response(NOT_FOUND, "Resource not found.", status)
    elif status == 403:
        code = "forbidden"
    elif status == 405:
        code = "method_not_allowed"
    elif status == 422:
        # 422 は常に validation_error に統一する。
        # get_reviewer_id() Depends が raise する HTTPException(422) を含む全 422 経路を
        # "validation_error" で返すことで、API クライアントが一貫した code で分岐できる
        # （basic-design.md §エラーハンドリング方針 / ラムス指摘対応）。
        code = VALIDATION_ERROR
    else:
        code = f"http_error_{status}"

    return error_response(code, str(exc.detail) if exc.detail else "HTTP error.", status)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI RequestValidationError → HTTP 422 / validation_error。"""
    if not isinstance(exc, RequestValidationError):
        raise TypeError(f"Expected RequestValidationError, got {type(exc).__name__}")
    detail = "; ".join(
        f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in exc.errors()
    )
    return error_response(VALIDATION_ERROR, f"Request validation failed: {detail}", 422)


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """未捕捉例外 → HTTP 500 / internal_error。"""
    return error_response(INTERNAL_ERROR, "An internal server error occurred.", 500)


async def pydantic_validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """application/domain 構築時の Pydantic ValidationError → HTTP 422。"""
    from pydantic import ValidationError

    if not isinstance(exc, ValidationError):
        raise TypeError(f"Expected ValidationError, got {type(exc).__name__}")
    detail = "; ".join(
        f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in exc.errors()
    )
    return error_response(VALIDATION_ERROR, f"Validation failed: {detail}", 422)
