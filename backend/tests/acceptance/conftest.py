"""受入テスト共通フィクスチャ。

全テストはインプロセス SQLite + 完全なアプリケーションスタック（HTTP API + リポジトリ）で動作する。
LLM 呼び出しは FakeRoundBasedLLMProvider で代替する。
StageExecutorService.dispatch_stage() を直接呼び出してステージ実行を制御する。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


@dataclass
class AcceptanceCtx:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]


@pytest_asyncio.fixture
async def acceptance_ctx(tmp_path: Path) -> AsyncIterator[AcceptanceCtx]:
    """受入テスト用 client + session_factory。"""
    from bakufu.infrastructure.event_bus import InMemoryEventBus
    from bakufu.infrastructure.security import masking as masking_mod
    from bakufu.interfaces.http.app import create_app

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    masking_mod.init()
    app = create_app()
    engine = make_test_engine(tmp_path / "acceptance_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    event_bus = InMemoryEventBus()

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.event_bus = event_bus
    # ConnectionManager が必要なエンドポイントのために初期化する
    from bakufu.interfaces.http.connection_manager import ConnectionManager

    app.state.connection_manager = ConnectionManager()
    app.state.allowed_origins = ["http://test"]

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield AcceptanceCtx(client=client, session_factory=session_factory)

    await engine.dispose()
