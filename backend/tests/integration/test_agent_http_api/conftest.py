"""agent / http-api 結合テスト共有フィクスチャ。

``docs/features/agent/http-api/test-design.md`` §外部 I/O 依存マップ 準拠。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from tests.integration.test_agent_http_api.helpers import AgTestCtx


@pytest_asyncio.fixture
async def ag_ctx(tmp_path: Path) -> AsyncIterator[AgTestCtx]:
    """Agent テスト用 AsyncClient + session_factory.

    ``room_ctx`` / ``wf_ctx`` と同一パターン。
    Agent は HTTP API が本 PR のスコープのため直接 HTTP 経由で操作できる。
    TC-IT-AGH-013 の R1-8 バイパス経路テストには session_factory を公開する。
    """
    from bakufu.interfaces.http.app import HttpApplicationFactory
    from httpx import ASGITransport, AsyncClient

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    app = HttpApplicationFactory.create()
    engine = make_test_engine(tmp_path / "agent_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield AgTestCtx(client=client, session_factory=session_factory)

    await engine.dispose()
