"""Alembic 5 番目リビジョンテスト (TC-IT-RR-012 — チェーン + DDL + べき等性)。

``docs/features/room-repository/test-design.md`` に従う。実際の SQLite ファイルに対する
実際の Alembic upgrade / downgrade、および
``0001_init`` → ``0002_empire_aggregate`` → ``0003_workflow_aggregate``
→ ``0004_agent_aggregate`` → ``0005_room_aggregate`` が
線形（head fork なし）であることを確認するチェーン完全性チェック。

また以下も検証:
* 5 番目リビジョンで作成される ``rooms`` + ``room_members`` テーブル。
* ``ix_rooms_empire_id_name`` 複合インデックスが存在 (§確定 R1-F)。
* BUG-EMR-001 FK クロージャ: ``empire_room_refs.room_id`` は
  ``rooms.id`` への FK 制約を持つようになった (``batch_alter_table`` 経由で追加)。

``tests/infrastructure/`` の conftest は Alembic の ``fileConfig`` をパッチして、
ログキャプチャがマイグレーション中も生き残るようにする；
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
# フィクスチャ
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
# TC-IT-RR-012: 5th revision creates rooms + room_members tables + index
# ---------------------------------------------------------------------------
class TestFifthRevisionApplied:
    """TC-IT-RR-012: ``alembic upgrade head`` が Room スキーマを追加。"""

    async def test_two_room_tables_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """upgrade head 後に rooms + room_members が存在。"""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"rooms", "room_members"}.issubset(tables), (
            f"[FAIL] upgrade head 後にスキーマから rooms または room_members が不足。\n"
            f"見つかったテーブル: {tables}"
        )

    async def test_rooms_empire_id_name_index_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """``ix_rooms_empire_id_name`` コンポジットインデックスが作成される (§確定 R1-F)。

        インデックスの左プリフィックスが ``WHERE empire_id = ?`` と
        ``WHERE empire_id = ? AND name = ?`` を ``find_by_name`` 向けに最適化。
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='rooms'")
            )
            index_names = {row[0] for row in result}
        assert "ix_rooms_empire_id_name" in index_names, (
            f"[FAIL] ix_rooms_empire_id_name インデックスが不足。\n"
            f"見つかったインデックス: {index_names}\n"
            f"次：0005_room_aggregate.py upgrade() に "
            f"``op.create_index('ix_rooms_empire_id_name', ...)`` が存在を確認。"
        )

    async def test_empire_room_refs_fk_closure_applied(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """BUG-EMR-001 FK closure: ``empire_room_refs.room_id → rooms.id``。

        ``0005_room_aggregate.py`` が ``batch_alter_table`` 経由で FK を追加
        (SQLite は ALTER TABLE ... ADD CONSTRAINT をサポートしない)。upgrade head 後、
        ``PRAGMA foreign_key_list('empire_room_refs')`` は
        ``rooms`` テーブルへの参照をリストアップする必要がある。
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_key_list('empire_room_refs')"))
            fk_rows = list(result)
        # PRAGMA foreign_key_list はカラムを持つ行を返す:
        #   PRAGMA foreign_key_list の列: id, seq, table, from, to, on_update, on_delete, match
        referenced_tables = {row[2] for row in fk_rows}  # カラムインデックス 2
        assert "rooms" in referenced_tables, (
            f"[FAIL] empire_room_refs は rooms への FK を持たない。\n"
            f"FK 参照が見つかりました: {referenced_tables}\n"
            f"次：0005_room_aggregate.py で batch_alter_table が "
            f"rooms.id への FK を追加を確認。"
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-012 補強: upgrade / downgrade are idempotent
# ---------------------------------------------------------------------------
class TestUpgradeDowngradeIdempotent:
    """upgrade head → downgrade base → upgrade head 再び全て成功。"""

    async def test_full_cycle_leaves_room_tables_present(
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
        assert tables.isdisjoint({"rooms", "room_members"}), (
            f"[FAIL] base への downgrade 後も rooms/room_members が存在。\nテーブル: {tables}"
        )

        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"rooms", "room_members"}.issubset(tables), (
            f"[FAIL] re-upgrade 後に rooms/room_members が不足。\nテーブル: {tables}"
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-012: revision chain is linear (no head fork)
# ---------------------------------------------------------------------------
class TestRevisionChainLinear:
    """0001 → 0002 → 0003 → 0004 → 0005 単一-head チェーン。"""

    async def test_alembic_heads_returns_single_revision(self) -> None:
        """``ScriptDirectory.get_heads()`` が正確に 1 つの revision を返す。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"Alembic head は線形である必要があります；分岐した heads {heads} を得た。\n"
            f"各アグリゲートリポジトリ PR は単一 revision を追加します。"
        )

    async def test_0005_revision_has_correct_down_revision(self) -> None:
        """``0005_room_aggregate.down_revision == "0004_agent_aggregate"``。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        rev = script.get_revision("0005_room_aggregate")
        assert rev is not None
        assert rev.down_revision == "0004_agent_aggregate", (
            f"[FAIL] 0005_room_aggregate.down_revision は {rev.down_revision!r} ；"
            f"'0004_agent_aggregate' を期待。"
        )

    async def test_chain_walks_from_0005_back_to_base(self) -> None:
        """``down_revision`` を走査すると 5 ホップで base に到達 (分岐なし)。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        chain: list[str] = []
        current_id: str | None = "0005_room_aggregate"
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
            "0005_room_aggregate",
            "0004_agent_aggregate",
            "0003_workflow_aggregate",
            "0002_empire_aggregate",
            "0001_init",
        ], f"予期しない revision chain: {chain}"
