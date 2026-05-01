"""application/services 結合テスト共通フィクスチャ。

in-memory SQLite 実接続（:memory: に近い tmp_path ファイル DB）でスキーマ作成済み
session_factory を提供する。Bootstrap 系テスト（TC-IT-TL-007）では data_dir / handler_registry の
シングルトンを各テスト前後でリセットする。

Issue: #124
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory


@pytest_asyncio.fixture
async def tl_session_factory(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """create_all でスキーマ作成済みの session_factory。

    template-library 結合テスト（TC-IT-TL-001〜009）用。
    """
    engine = make_test_engine(tmp_path / "tl_test.db")
    await create_all_tables(engine)
    sf = make_test_session_factory(engine)
    try:
        yield sf
    finally:
        await engine.dispose()


@pytest.fixture
def _reset_data_dir() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """data_dir シングルトンを各テスト前後でリセット（TC-IT-TL-007 で必要）。"""
    from bakufu.infrastructure.config import data_dir

    data_dir.reset()
    yield
    data_dir.reset()


@pytest.fixture
def _clear_handler_registry() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """handler_registry を各テスト前後でリセット（TC-IT-TL-007 で必要）。"""
    from bakufu.infrastructure.persistence.sqlite.outbox import handler_registry

    handler_registry.clear()
    yield
    handler_registry.clear()
