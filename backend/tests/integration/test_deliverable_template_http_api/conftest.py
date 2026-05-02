"""deliverable-template / http-api 結合テスト共有フィクスチャ。

``docs/features/deliverable-template/http-api/test-design/index.md`` §外部 I/O 依存マップ 準拠。

pytest の ``tmp_path`` 配下に実 SQLite を用いる ── DB のモックは行わない。
http-api-foundation / room の conftest.py と同一パターン:
``app.state.session_factory`` を直接注入して本番 lifespan をバイパスする。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass
class DtTestCtx:
    """DeliverableTemplate 結合テスト用コンテキスト。

    ``client``: HTTP リクエスト送信 (FastAPI ASGI)
    ``session_factory``: Repository 直接呼び出し用セッションファクトリ
    """

    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]


@pytest_asyncio.fixture
async def dt_ctx(tmp_path: Path) -> AsyncIterator[DtTestCtx]:
    """DeliverableTemplate テスト用 AsyncClient + session_factory。

    ``tests/integration/test_room_http_api/conftest.py`` と同一パターン。
    create_all_tables で DDL を適用（Alembic なし）。
    raise_app_exceptions=False で 5xx レスポンスを httpx 例外なしに受け取れるようにする。
    """
    from bakufu.interfaces.http.app import create_app
    from httpx import ASGITransport

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    app = create_app()
    engine = make_test_engine(tmp_path / "dt_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    from bakufu.infrastructure.event_bus import InMemoryEventBus

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.event_bus = InMemoryEventBus()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield DtTestCtx(client=client, session_factory=session_factory)

    await engine.dispose()


__all__ = ["DtTestCtx", "dt_ctx"]
