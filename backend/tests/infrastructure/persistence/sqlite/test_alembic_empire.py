"""Alembic 2nd revision テスト (TC-IT-EMR-008 / 015 / 016)。

``docs/features/empire-repository/test-design.md`` に従う。
実際の SQLite ファイルに対する Alembic upgrade / downgrade、
および chain integrity チェック:
``0001_init`` → ``0002_empire_aggregate`` が線形 (head fork なし)
であることを確認。

``tests/infrastructure/`` の conftest は Alembic の ``fileConfig``
をパッチして、ログキャプチャが migration 中も生き残るようにする；
M2 persistence-foundation テストが依存している同じ回避策。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from alembic.config import Config
from alembic.script import ScriptDirectory
from bakufu.infrastructure.persistence.sqlite import engine as engine_mod
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def empty_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """マイグレーションを実行せずに新規 app エンジンを起動する。"""
    url = f"sqlite+aiosqlite:///{tmp_path / 'bakufu.db'}"
    engine = engine_mod.create_engine(url)
    try:
        yield engine
    finally:
        await engine.dispose()


def _alembic_config() -> Config:
    """ScriptDirectory inspection 用に bakufu Alembic config を解決する。"""
    # migrations モジュールが内部で使用するのと同じパス；
    # このテストが private helper をインポートしないように walk を複製。
    backend_root = Path(__file__).resolve().parents[4]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    return cfg


# ---------------------------------------------------------------------------
# TC-IT-EMR-008: 2nd revision applies the 3 Empire tables + indexes
# ---------------------------------------------------------------------------
class TestSecondRevisionApplied:
    """TC-IT-EMR-008: ``alembic upgrade head`` が Empire スキーマを追加する。"""

    async def test_three_empire_tables_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-EMR-008: empires / empire_room_refs / empire_agent_refs が存在する。"""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"empires", "empire_room_refs", "empire_agent_refs"}.issubset(tables)

    async def test_unique_indexes_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-EMR-008: (empire_id, room_id) / (empire_id, agent_id) 上の UNIQUE インデックス。

        SQLite はテーブル作成時に宣言された UNIQUE 制約ごと
        に ``sqlite_autoindex_*`` を発行する。``CREATE INDEX``
        という名前のインデックスもここに格納される；
        Alembic 0002 revision がインライン UNIQUE 制約形式
        を使用しているため、どちらの形態も受け入れる。
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name, tbl_name FROM sqlite_master WHERE type='index'")
            )
            rows = list(result)
        room_indexes = [name for name, tbl in rows if tbl == "empire_room_refs"]
        agent_indexes = [name for name, tbl in rows if tbl == "empire_agent_refs"]
        assert room_indexes, "empire_room_refs は少なくとも 1 つのインデックスを宣言する必要がある"
        assert agent_indexes, (
            "empire_agent_refs は少なくとも 1 つのインデックスを宣言する必要がある"
        )


# ---------------------------------------------------------------------------
# TC-IT-EMR-015: upgrade / downgrade are idempotent
# ---------------------------------------------------------------------------
class TestUpgradeDowngradeIdempotent:
    """TC-IT-EMR-015: Alembic up + down + up でスキーマが head 状態に残る。"""

    async def test_full_cycle_leaves_empire_tables_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-EMR-015: upgrade head → downgrade base → upgrade head。"""
        # Up.
        await run_upgrade_head(empty_engine)
        # Alembic コマンドで base にダウン (asyncio 内で同期)。
        from alembic import command  # ローカルインポートはグローバルサイドエフェクト回避

        cfg = _alembic_config()
        url = str(empty_engine.url)
        cfg.set_main_option("sqlalchemy.url", url)

        def _do_downgrade() -> None:
            command.downgrade(cfg, "base")

        await asyncio.to_thread(_do_downgrade)

        # スキーマは今空 — Empire テーブルがなくなったことをアサート。
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert tables.isdisjoint({"empires", "empire_room_refs", "empire_agent_refs"})

        # もう一度 Up — head に戻る。
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"empires", "empire_room_refs", "empire_agent_refs"}.issubset(tables)


# ---------------------------------------------------------------------------
# TC-IT-EMR-016: revision chain is linear (no head fork)
# ---------------------------------------------------------------------------
class TestRevisionChainLinear:
    """TC-IT-EMR-016: ``0001_init`` → ``0002_empire_aggregate`` (単一 head)。"""

    async def test_alembic_heads_returns_single_revision(self) -> None:
        """TC-IT-EMR-016: ``ScriptDirectory.get_heads()`` が正確に 1 つの revision を返す。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"Alembic head は線形である必要があります； branched heads {heads} を得た。"
            f"各 Aggregate Repository PR は単一 revision を追加します；"
            f"branching は CI runners 全体で ``alembic upgrade head`` を破壊します。"
        )

    async def test_0002_revision_has_correct_down_revision(self) -> None:
        """TC-IT-EMR-016: ``0002_empire_aggregate.down_revision == "0001_init"``。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        rev = script.get_revision("0002_empire_aggregate")
        assert rev is not None
        assert rev.down_revision == "0001_init"
