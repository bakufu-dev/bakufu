"""Shared fixtures for E2E tests.

E2E tests use the full production app (empire router + all handlers) with a
real SQLite tempdb.  No test-only routes are injected — all access is through
the public API.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def empire_e2e_client(tmp_path: Path) -> AsyncClient:  # type: ignore[override]
    """httpx.AsyncClient for E2E tests — full production app + real SQLite tempdb.

    Mirrors the integration ``empire_app_client`` fixture but lives here so
    E2E tests are structurally independent of integration fixtures.
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
        yield client  # type: ignore[misc]

    await engine.dispose()


@pytest_asyncio.fixture
async def room_e2e_ctx(tmp_path: Path) -> AsyncIterator[object]:
    """Room E2E テスト用 AsyncClient + session_factory.

    TC-E2E-RM-004/005 用。empire_e2e_client と同一アプリ構成で、加えて
    Workflow / Agent の直接 DB シード用 session_factory を公開する。
    """
    from bakufu.interfaces.http.app import create_app

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory
    from tests.integration.test_room_http_api.helpers import RoomTestCtx

    app = create_app()
    engine = make_test_engine(tmp_path / "room_e2e_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield RoomTestCtx(client=client, session_factory=session_factory)

    await engine.dispose()
