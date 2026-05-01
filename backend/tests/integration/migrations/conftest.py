"""Alembic migration テスト共通フィクスチャ。

Issue: #123
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from bakufu.infrastructure.persistence.sqlite import engine as engine_mod


@pytest_asyncio.fixture
async def empty_engine(tmp_path: Path) -> AsyncIterator[object]:
    """マイグレーション未適用の新規アプリエンジン。"""
    url = f"sqlite+aiosqlite:///{tmp_path / 'migration_test.db'}"
    engine = engine_mod.create_engine(url)
    try:
        yield engine
    finally:
        await engine.dispose()
