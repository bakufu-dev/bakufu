"""workflow / http-api 結合テスト共有フィクスチャ。

``docs/features/workflow/http-api/test-design.md`` §外部 I/O 依存マップ 準拠。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from tests.integration.test_workflow_http_api.helpers import WfTestCtx


@pytest_asyncio.fixture
async def wf_ctx(tmp_path: Path) -> AsyncIterator[WfTestCtx]:
    """Workflow テスト用 AsyncClient + session_factory。

    ``room_ctx`` と同一パターン。
    """
    from bakufu.interfaces.http.app import create_app
    from httpx import ASGITransport, AsyncClient

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    app = create_app()
    engine = make_test_engine(tmp_path / "workflow_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    from bakufu.infrastructure.event_bus import InMemoryEventBus

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.event_bus = InMemoryEventBus()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield WfTestCtx(client=client, session_factory=session_factory)

    await engine.dispose()
