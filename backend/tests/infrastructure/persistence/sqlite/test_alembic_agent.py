"""Alembic 4th revision tests (TC-IT-AGR-008 — chain + DDL + idempotency).

Per ``docs/features/agent-repository/test-design.md``. Real Alembic
upgrade / downgrade against a real SQLite file, plus a chain
integrity check that makes sure
``0001_init`` → ``0002_empire_aggregate`` → ``0003_workflow_aggregate``
→ ``0004_agent_aggregate`` stays linear (no head fork).

The conftest from ``tests/infrastructure/`` patches Alembic's
``fileConfig`` so log capture survives migration; same workaround the
M2 persistence-foundation tests rely on.
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
    """マイグレーションを実行せずに新規 app エンジンを起動。"""
    url = f"sqlite+aiosqlite:///{tmp_path / 'bakufu.db'}"
    engine = engine_mod.create_engine(url)
    try:
        yield engine
    finally:
        await engine.dispose()


def _alembic_config() -> Config:
    """ScriptDirectory inspection 用に bakufu Alembic config を解決。"""
    backend_root = Path(__file__).resolve().parents[4]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    return cfg


# ---------------------------------------------------------------------------
# TC-IT-AGR-008: 4th revision creates the 3 Agent tables + indexes
# ---------------------------------------------------------------------------
class TestFourthRevisionApplied:
    """TC-IT-AGR-008: ``alembic upgrade head`` が Agent スキーマを追加。"""

    async def test_three_agent_tables_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """upgrade head 後に agents / agent_providers / agent_skills が存在。"""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"agents", "agent_providers", "agent_skills"}.issubset(tables)

    async def test_partial_unique_index_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """``uq_agent_providers_default`` partial unique index が作成される。

        SQLite は partial-index DDL を ``sqlite_master.sql`` に格納；
        partial 性を確認するため ``WHERE`` 句を grep
        (通常の unique index は ``is_default=0``
        重複をブロックしない)。
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT name, sql FROM sqlite_master "
                    "WHERE type='index' AND tbl_name='agent_providers'"
                )
            )
            rows = list(result)
        partial_indexes = [
            (name, sql) for name, sql in rows if sql is not None and "WHERE" in sql.upper()
        ]
        assert partial_indexes, (
            "[FAIL] agent_providers は §確定 G 二重防衛のため"
            "WHERE 句を含む partial unique index を宣言する必要がある。\n"
            f"agent_providers のすべてのインデックス: {rows}"
        )
        # 述語は is_default = 1 を参照する必要がある。
        assert any("is_default" in sql and "1" in sql for _, sql in partial_indexes), (
            f"Partial index が is_default = 1 をターゲットにしていない: {partial_indexes}"
        )


# ---------------------------------------------------------------------------
# TC-IT-AGR-008 補強: upgrade / downgrade are idempotent
# ---------------------------------------------------------------------------
class TestUpgradeDowngradeIdempotent:
    """upgrade head → downgrade base → upgrade head 再び全て成功。"""

    async def test_full_cycle_leaves_agent_tables_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """upgrade head → downgrade base → upgrade head 再び。"""
        await run_upgrade_head(empty_engine)
        from alembic import command  # グローバルサイドエフェクトを回避するためのローカルインポート

        cfg = _alembic_config()
        url = str(empty_engine.url)
        cfg.set_main_option("sqlalchemy.url", url)

        def _do_downgrade() -> None:
            command.downgrade(cfg, "base")

        await asyncio.to_thread(_do_downgrade)

        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert tables.isdisjoint({"agents", "agent_providers", "agent_skills"})

        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"agents", "agent_providers", "agent_skills"}.issubset(tables)


# ---------------------------------------------------------------------------
# TC-IT-AGR-008: revision chain is linear (no head fork)
# ---------------------------------------------------------------------------
class TestRevisionChainLinear:
    """0001 → 0002 → 0003 → 0004 単一-head チェーン。"""

    async def test_alembic_heads_returns_single_revision(self) -> None:
        """``ScriptDirectory.get_heads()`` が正確に 1 つの revision を返す。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"Alembic head は線形である必要があります；分岐した heads {heads} を得た。\n"
            f"各アグリゲートリポジトリ PR は単一 revision を追加します。"
        )

    async def test_0004_revision_has_correct_down_revision(self) -> None:
        """``0004_agent_aggregate.down_revision == "0003_workflow_aggregate"``。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        rev = script.get_revision("0004_agent_aggregate")
        assert rev is not None
        assert rev.down_revision == "0003_workflow_aggregate"

    async def test_chain_walks_from_0004_back_to_base(self) -> None:
        """``down_revision`` を走査すると 4 ホップで base に到達 (分岐なし)。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        chain: list[str] = []
        current_id: str | None = "0004_agent_aggregate"
        for _ in range(10):  # 安全性のための余裕のある境界
            if current_id is None:
                break
            rev = script.get_revision(current_id)
            assert rev is not None, f"Revision {current_id!r} が見つかりません"
            chain.append(rev.revision)
            down = rev.down_revision
            if isinstance(down, tuple | list):
                pytest.fail(f"Revision {rev.revision!r} は複数の down_revisions {down} を持つ")
            current_id = down  # pyright: ignore[reportAssignmentType]

        assert chain == [
            "0004_agent_aggregate",
            "0003_workflow_aggregate",
            "0002_empire_aggregate",
            "0001_init",
        ], f"予期しない revision chain: {chain}"
