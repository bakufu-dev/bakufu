"""Shared fixtures for http-api-foundation integration tests.

Per ``docs/features/http-api-foundation/http-api/test-design.md`` §外部 I/O 依存マップ.

Uses real SQLite under pytest ``tmp_path`` — no mocked DB.
FastAPI lifespan is bypassed for most tests: ``app.state.session_factory`` is
injected directly so the production lifespan (file-system DB path resolution)
is not required.  TC-IT-HAF-007 tests the actual lifespan separately.

Design note — route handlers at module level
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``from __future__ import annotations`` (PEP 563) turns ALL annotations into
strings.  FastAPI resolves those strings via ``typing.get_type_hints(fn, ...)``,
which looks up names in ``fn.__globals__`` (the module-level namespace).
Therefore any route handler that uses ``SessionDep`` or local Pydantic models
**must** be defined at module level in THIS file so that both symbols are
present in ``conftest.__dict__`` when FastAPI does its introspection.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

# ── Module-level symbols needed for FastAPI annotation resolution ──────────────
from bakufu.interfaces.http.dependencies import SessionDep
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel


class _Item(BaseModel):
    """Request body model for the test validation endpoint."""

    name: str


# ── Module-level route handler functions ──────────────────────────────────────
# All handlers MUST live at module level so that FastAPI's ``get_type_hints``
# call can resolve annotations from ``conftest.__dict__``.


async def _validation_endpoint(item: _Item) -> dict[str, str]:
    """POST /test/validation-required — requires JSON body; absence → 422."""
    return {"name": item.name}


async def _exception_endpoint() -> None:
    """GET /test/raise-exception — raises RuntimeError to test 500 handler."""
    raise RuntimeError("test internal error")


async def _session_di_endpoint(session: SessionDep) -> dict[str, str]:
    """GET /test/session-type — uses SessionDep to verify DI yields AsyncSession."""
    return {"session_type": type(session).__name__}


def _build_test_router() -> APIRouter:
    """Construct the test-only router with module-level handlers pre-wired."""
    router = APIRouter()
    router.add_api_route(
        "/test/validation-required",
        _validation_endpoint,
        methods=["POST"],
    )
    router.add_api_route(
        "/test/raise-exception",
        _exception_endpoint,
        methods=["GET"],
    )
    router.add_api_route(
        "/test/session-type",
        _session_di_endpoint,
        methods=["GET"],
    )
    return router


@pytest_asyncio.fixture
async def empire_app_client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    """httpx.AsyncClient wired to the FastAPI app with empire routes + real SQLite tempdb.

    Unlike ``app_client``, no test-only routes are added (empire router is
    already registered via ``create_app()``).  ORM tables are created via
    ``create_all_tables`` so CRUD operations hit a real SQLite DB.
    """
    from bakufu.interfaces.http.app import create_app
    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    app = create_app()
    engine = make_test_engine(tmp_path / "test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await engine.dispose()


@pytest_asyncio.fixture
async def app_client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    """httpx.AsyncClient wired to the FastAPI app with test routes and real SQLite tempdb.

    Lifespan is intentionally bypassed: ``app.state.session_factory`` is set
    directly from a temp-db engine.  ``raise_app_exceptions=False`` is required
    so TC-IT-HAF-004 can assert the 500 JSON body — Starlette 1.0 ``ServerErrorMiddleware``
    always re-raises the exception after sending the response, which httpx would
    otherwise surface as a test-level ``RuntimeError``.
    """
    from bakufu.interfaces.http.app import create_app

    from tests.factories.db import make_test_engine, make_test_session_factory

    app = create_app()

    # ── Bypass production lifespan ──────────────────────────────────────────
    engine = make_test_engine(tmp_path / "test.db")
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    app.include_router(_build_test_router())

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await engine.dispose()
