"""E2E テスト共有フィクスチャ。

E2E テストは完全なプロダクション用アプリ（empire ルーター + 全ハンドラー）を
リアルな SQLite テンポラリ DB で動作させる。テスト専用ルートは注入しない —
全アクセスは公開 API 経由で行う。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def empire_e2e_client(tmp_path: Path) -> AsyncClient:  # type: ignore[override]
    """E2E テスト用 httpx.AsyncClient — 完全なプロダクション用アプリ + リアル SQLite テンポラリ DB。

    integration の ``empire_app_client`` フィクスチャと同一構成だが、
    E2E テストが integration フィクスチャに依存しないよう独立して定義する。
    """
    from bakufu.interfaces.http.app import HttpApplicationFactory

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    app = HttpApplicationFactory.create()
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
    from bakufu.interfaces.http.app import HttpApplicationFactory

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory
    from tests.integration.test_room_http_api.helpers import RoomTestCtx

    app = HttpApplicationFactory.create()
    engine = make_test_engine(tmp_path / "room_e2e_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield RoomTestCtx(client=client, session_factory=session_factory)

    await engine.dispose()
