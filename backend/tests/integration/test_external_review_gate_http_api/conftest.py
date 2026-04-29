"""ExternalReviewGate HTTP API integration fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from .helpers import TOKEN, ExternalReviewGateHttpCtx


@pytest_asyncio.fixture
async def external_review_gate_http_ctx(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[ExternalReviewGateHttpCtx]:
    """実 SQLite と実 FastAPI app を配線する。"""
    from bakufu.interfaces.http.app import HttpApplicationFactory

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    reviewer_id = uuid4()
    monkeypatch.setenv("BAKUFU_OWNER_API_TOKEN", TOKEN)
    monkeypatch.setenv("BAKUFU_OWNER_ID", str(reviewer_id))

    app = HttpApplicationFactory.create()
    engine = make_test_engine(tmp_path / "test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield ExternalReviewGateHttpCtx(client, session_factory, reviewer_id)

    await engine.dispose()
