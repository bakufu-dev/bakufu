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
    http_exception_handler,
    internal_error_handler,
    validation_error_handler,
)
from bakufu.interfaces.http.routers.health import router as health_router


def _parse_allowed_origins() -> list[str]:
    """BAKUFU_ALLOWED_ORIGINS 環境変数をカンマ区切りでパース (確定 C)。"""
    raw = os.environ.get("BAKUFU_ALLOWED_ORIGINS", "")
    if not raw.strip():
        return ["http://localhost:5173"]
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """lifespan: startup で session_factory を app.state に保持、shutdown で dispose (確定 B)。"""
    from bakufu.infrastructure.config import data_dir as data_dir_mod
    from bakufu.infrastructure.persistence.sqlite.engine import create_engine
    from bakufu.infrastructure.persistence.sqlite.session import make_session_factory

    resolved_data_dir = data_dir_mod.resolve()
    url = f"sqlite+aiosqlite:///{resolved_data_dir / 'bakufu.db'}"
    engine = create_engine(url)
    session_factory = make_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

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
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)

    # ルーター
    app.include_router(health_router)

    return app


app = create_app()
