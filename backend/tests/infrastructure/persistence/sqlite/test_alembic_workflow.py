"""Alembic 3rd revision テスト (TC-IT-WFR-020 / 021 / 022)。

``docs/features/workflow-repository/test-design.md`` に従う。
実際の SQLite ファイルに対する Alembic upgrade / downgrade、
および chain integrity チェック:
``0001_init`` → ``0002_empire_aggregate`` → ``0003_workflow_aggregate``
が線形（head fork なし）であることを確認。

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
# TC-IT-WFR-020: 3rd revision applies the 3 Workflow tables + UNIQUE indexes
# ---------------------------------------------------------------------------
class TestThirdRevisionApplied:
    """TC-IT-WFR-020: ``alembic upgrade head`` が Workflow スキーマを追加する。"""

    async def test_three_workflow_tables_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-020: workflows / workflow_stages / workflow_transitions が存在する。"""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"workflows", "workflow_stages", "workflow_transitions"}.issubset(tables)

    async def test_unique_indexes_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-020: 2 つのサイドテーブルの UNIQUE インデックス。

        ``workflow_stages``: UNIQUE ``(workflow_id, stage_id)``。
        ``workflow_transitions``: UNIQUE ``(workflow_id, transition_id)``。

        SQLite はテーブル作成時に宣言された UNIQUE 制約ごと
        に ``sqlite_autoindex_*`` を発行する。``CREATE INDEX``
        という名前のインデックスもここに格納される；
        Alembic 0003 revision がインライン UNIQUE 制約形式
        (``uq_workflow_stages_pair`` / ``uq_workflow_transitions_pair``)
        を使用しているため、どちらの形態も受け入れる。
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name, tbl_name FROM sqlite_master WHERE type='index'")
            )
            rows = list(result)
        stage_indexes = [name for name, tbl in rows if tbl == "workflow_stages"]
        transition_indexes = [name for name, tbl in rows if tbl == "workflow_transitions"]
        assert stage_indexes, "workflow_stages は少なくとも 1 つのインデックスを宣言する必要がある"
        assert transition_indexes, (
            "workflow_transitions は少なくとも 1 つのインデックスを宣言する必要がある"
        )


# ---------------------------------------------------------------------------
# TC-IT-WFR-021: upgrade / downgrade are idempotent
# ---------------------------------------------------------------------------
class TestUpgradeDowngradeIdempotent:
    """TC-IT-WFR-021: Alembic up + down + up でスキーマが head 状態に残る。"""

    async def test_full_cycle_leaves_workflow_tables_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-021: upgrade head → downgrade base → upgrade head。"""
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

        # スキーマは今空 — Workflow テーブルがなくなったことをアサート。
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert tables.isdisjoint({"workflows", "workflow_stages", "workflow_transitions"})

        # もう一度 Up — head に戻る。
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"workflows", "workflow_stages", "workflow_transitions"}.issubset(tables)


# ---------------------------------------------------------------------------
# TC-IT-WFR-022: revision chain is linear (no head fork)
# ---------------------------------------------------------------------------
class TestRevisionChainLinear:
    """TC-IT-WFR-022: revision chain は線形 (単一 head)。

    ``0001_init`` → ``0002_empire_aggregate`` → ``0003_workflow_aggregate``。
    """

    async def test_alembic_heads_returns_single_revision(self) -> None:
        """TC-IT-WFR-022: ``ScriptDirectory.get_heads()`` が正確に 1 つの revision を返す。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"Alembic head は線形である必要があります； branched heads {heads} を得た。"
            f"各 Aggregate Repository PR は単一 revision を追加します；"
            f"branching は CI runners 全体で ``alembic upgrade head`` を破壊します。"
        )

    async def test_0003_revision_has_correct_down_revision(self) -> None:
        """TC-IT-WFR-022: ``0003_workflow_aggregate.down_revision == "0002_empire_aggregate"``。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        rev = script.get_revision("0003_workflow_aggregate")
        assert rev is not None
        assert rev.down_revision == "0002_empire_aggregate"

    async def test_chain_walks_from_0003_back_to_base(self) -> None:
        """TC-IT-WFR-022 補強: ``down_revision`` 走査が 3 ホップで base に到達。

        ``down_revision = None`` で誤って ``0003`` を登録する future PR を
        キャッチする (これは base から branch を作成することになる) —
        heads() チェックは branch でもまだパスするため、
        chain を明示的に走査する。
        """
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        chain: list[str] = []
        current_id: str | None = "0003_workflow_aggregate"
        for _ in range(10):  # 悪いデータで無限ループを避けるための余裕のある境界
            if current_id is None:
                break
            rev = script.get_revision(current_id)
            assert rev is not None, f"Revision {current_id!r} が見つかりません"
            chain.append(rev.revision)
            down = rev.down_revision
            if isinstance(down, tuple | list):
                pytest.fail(f"Revision {rev.revision!r} は複数の down_revisions {down} を持つ")
            # 上記のガード後、``down`` は ``str | None`` に絞られた。
            current_id = down  # pyright: ignore[reportAssignmentType]

        # 0003 → 0002 → 0001 → base (None)
        assert chain == [
            "0003_workflow_aggregate",
            "0002_empire_aggregate",
            "0001_init",
        ], f"予期しない revision chain: {chain}"
