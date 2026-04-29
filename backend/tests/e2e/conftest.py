"""Shared fixtures for E2E tests.

E2E tests use the full production app (empire router + all handlers) with a
real SQLite tempdb.  No test-only routes are injected — all access is through
the public API.
"""

from __future__ import annotations

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
