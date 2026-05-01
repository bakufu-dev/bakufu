"""SqliteDeliverableRecordRepository 結合テスト共通フィクスチャ。

in-memory SQLite（:memory:）実接続でテーブルを create_all で作成。
Alembic マイグレーションは使わない（TC-IT-MIGR は別テスト）。

Issue: #123
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory


@pytest.fixture(autouse=True)
def _initialize_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    """masking を初期化する（MaskedText TypeDecorator の動作保証）。"""
    for env_key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "OAUTH_CLIENT_SECRET",
        "BAKUFU_DISCORD_BOT_TOKEN",
    ):
        monkeypatch.delenv(env_key, raising=False)
    from bakufu.infrastructure.security import masking

    masking.init()


@pytest_asyncio.fixture
async def repo_session_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """create_all でスキーマ作成済みの session_factory を提供する。"""
    engine = make_test_engine(tmp_path / "repo_test.db")
    await create_all_tables(engine)
    sf = make_test_session_factory(engine)
    try:
        yield sf
    finally:
        await engine.dispose()
