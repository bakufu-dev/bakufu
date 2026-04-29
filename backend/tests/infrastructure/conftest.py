"""infrastructure 層の統合テスト向け共有フィクスチャ。

ここで定義するフィクスチャは、意図的に **本物の** SQLite + **本物の**
Alembic + **本物の** ファイルシステム（``tmp_path`` 配下）を用いる。
モックするのは ``psutil`` のみ（``test_pid_gc.py`` で使用）。これは OS が
CI 上で実プロセスツリーを安全に生成することを許さないためである。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from bakufu.infrastructure.config import data_dir
from bakufu.infrastructure.persistence.sqlite import engine as engine_mod
from bakufu.infrastructure.persistence.sqlite import session as session_mod
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head
from bakufu.infrastructure.persistence.sqlite.outbox import handler_registry
from bakufu.infrastructure.security import masking

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@pytest.fixture(autouse=True)
def _reset_data_dir() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """各テストの前後で data_dir シングルトンをクリアする。"""
    data_dir.reset()
    yield
    data_dir.reset()


@pytest.fixture(autouse=True)
def _clear_handler_registry() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """テストはハンドラレジストリが空の状態で開始しなければならない（Confirmation K）。"""
    handler_registry.clear()
    yield
    handler_registry.clear()


@pytest.fixture(autouse=True)
def _initialize_masking(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """provider 系の環境変数を全て外した状態で、テストごとに masking を 1 回だけ初期化する。"""
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
    masking.init()


@pytest_asyncio.fixture
async def app_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """tmp_path/bakufu.db を指す本物のアプリケーションエンジン。

    テスト本体が走る前に Alembic ``upgrade head`` を実行してスキーマと
    トリガを整えておく。後始末ではエンジンを dispose し、tmp_path を
    クリーンに削除できるようにする。

    BUG-PF-002 修正: ``alembic/env.py`` が
    ``disable_existing_loggers=False`` を渡すようになったため、これまで
    のテスト側回避策（``_re_enable_bakufu_loggers`` /
    ``_patch_alembic_file_config``）はもう不要。
    """
    db_path = tmp_path / "bakufu.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = engine_mod.create_engine(url)
    await run_upgrade_head(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(
    app_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """マイグレーション済みテストエンジンに紐付いた SessionFactory。"""
    return session_mod.make_session_factory(app_engine)
