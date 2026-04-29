"""room / http-api 結合テスト共有フィクスチャ。

``docs/features/room/http-api/test-design.md`` §外部 I/O 依存マップ 準拠。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from tests.integration.test_room_http_api.helpers import RoomTestCtx


@pytest_asyncio.fixture
async def room_ctx(tmp_path: Path) -> AsyncIterator[RoomTestCtx]:
    """Room テスト用 AsyncClient + session_factory.

    ``empire_app_client`` と同一パターン + session_factory を追加公開。
    Workflow / Agent は HTTP API が本 PR のスコープ外のため、direct DB seeding
    (assumed mock 禁止原則準拠 — characterization fixture 確認済み) を使う。
    """
    from bakufu.interfaces.http.app import create_app
    from httpx import ASGITransport, AsyncClient

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    app = create_app()
    engine = make_test_engine(tmp_path / "room_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield RoomTestCtx(client=client, session_factory=session_factory)

    await engine.dispose()
