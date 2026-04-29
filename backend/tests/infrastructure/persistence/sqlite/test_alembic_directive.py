"""Alembic 6th revision tests — directive aggregate (TC-IT-DRR-001〜006).

REQ-DRR-003 / §確定 R1-B / §確定 R1-C.

Real Alembic upgrade/downgrade against a real SQLite file, plus chain
integrity check that makes sure the 0001→…→0006 chain stays linear.

Also verifies:
* ``directives`` table created with correct columns.
* ``ix_directives_target_room_id_created_at`` composite index present.
* ``target_room_id`` FK → ``rooms.id`` ON DELETE CASCADE exists.
* §BUG-DRR-001: ``task_id → tasks.id`` FK does NOT exist at 0006 level.

Per ``docs/features/directive-repository/test-design.md`` TC-IT-DRR-001〜006.
Issue #34 — M2 0006.
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
# TC-IT-DRR-001: 0006 creates directives table + INDEX + FK (受入基準 9)
# ---------------------------------------------------------------------------
class TestSixthRevisionApplied:
    """TC-IT-DRR-001: alembic upgrade head が Directive スキーマを追加。"""

    async def test_directives_table_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """upgrade head 後に ``directives`` テーブルが存在。"""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert "directives" in tables, (
            f"[FAIL] directives table missing after upgrade head.\nTables found: {tables}"
        )

    async def test_directives_composite_index_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """``ix_directives_target_room_id_created_at`` コンポジット
        インデックスが存在 (§確定 R1-D)。
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='directives'")
            )
            index_names = {row[0] for row in result}
        assert "ix_directives_target_room_id_created_at" in index_names, (
            f"[FAIL] ix_directives_target_room_id_created_at index missing on directives.\n"
            f"Indexes found: {index_names}\n"
            f"Next: ensure op.create_index(...) is in 0006_directive_aggregate.py upgrade()."
        )

    async def test_directives_fk_to_rooms_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """PRAGMA foreign_key_list('directives') が rooms への FK を表示 (§確定 R1-B)。"""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_key_list('directives')"))
            fk_rows = list(result)
        # PRAGMA foreign_key_list columns: id, seq, table, from, to, ...
        referenced_tables = {row[2] for row in fk_rows}
        assert "rooms" in referenced_tables, (
            f"[FAIL] directives has no FK to rooms (§確定 R1-B).\n"
            f"FK references found: {referenced_tables}\n"
            f"Next: verify ForeignKey('rooms.id', ondelete='CASCADE') in 0006."
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-002: Alembic chain 0001→...→0006 single head (分岐なし)
# ---------------------------------------------------------------------------
class TestRevisionChainLinear:
    """TC-IT-DRR-002: 0001→0002→0003→0004→0005→0006 単一-head チェーン。"""

    async def test_alembic_heads_returns_single_revision(self) -> None:
        """ScriptDirectory.get_heads() が正確に 1 つの revision を返す。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"[FAIL] Alembic head は線形である必要があります；分岐した heads {heads} を得た。\n"
            f"各アグリゲートリポジトリ PR は単一 revision を追加します。"
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-003: upgrade/downgrade idempotent (受入基準 9)
# ---------------------------------------------------------------------------
class TestUpgradeDowngradeIdempotent:
    """TC-IT-DRR-003: upgrade head → downgrade base → upgrade head 再び。"""

    async def test_full_cycle_leaves_directives_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """upgrade head → downgrade base → upgrade head — directives が生き残る。"""
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
        assert "directives" not in tables, (
            f"[FAIL] directives still present after downgrade to base.\nTables: {tables}"
        )

        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert "directives" in tables, (
            f"[FAIL] directives missing after re-upgrade.\nTables: {tables}"
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-004: 0006.down_revision == "0005_room_aggregate"
# ---------------------------------------------------------------------------
class TestDownRevision:
    """TC-IT-DRR-004: 0006_directive_aggregate が 0005_room_aggregate にチェーン。"""

    async def test_0006_revision_has_correct_down_revision(self) -> None:
        """0006_directive_aggregate.down_revision == '0005_room_aggregate'。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        rev = script.get_revision("0006_directive_aggregate")
        assert rev is not None
        assert rev.down_revision == "0005_room_aggregate", (
            f"[FAIL] 0006_directive_aggregate.down_revision は {rev.down_revision!r} ；"
            f"'0005_room_aggregate' を期待。"
        )

    async def test_chain_walks_from_0006_back_to_base(self) -> None:
        """0006 から down_revision を走査すると 6 ホップで base に到達。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        chain: list[str] = []
        current_id: str | None = "0006_directive_aggregate"
        for _ in range(15):
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
            "0006_directive_aggregate",
            "0005_room_aggregate",
            "0004_agent_aggregate",
            "0003_workflow_aggregate",
            "0002_empire_aggregate",
            "0001_init",
        ], f"予期しない revision chain: {chain}"


# ---------------------------------------------------------------------------
# TC-IT-DRR-005: target_room_id FK ON DELETE CASCADE (§確定 R1-B, 受入基準 10)
# ---------------------------------------------------------------------------
class TestCascadeDeleteOnRoomDeletion:
    """TC-IT-DRR-005: Room を削除すると Directives が自動削除される (CASCADE)。"""

    async def test_room_deletion_cascades_to_directives(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """DELETE FROM rooms → Directive 行が自動削除される (CASCADE)。

        リポジトリ層の依存性を避けるために、生 SQL 経由で
        empire → workflow → room → directive を挿入。次に room を
        DELETE して、ON DELETE CASCADE により directive 行が消えることを検証。
        """
        from uuid import uuid4

        await run_upgrade_head(empty_engine)

        empire_id = uuid4().hex
        workflow_id = uuid4().hex
        room_id = uuid4().hex
        directive_id = uuid4().hex
        from datetime import UTC, datetime

        created_at = datetime.now(UTC).isoformat()

        async with empty_engine.begin() as conn:
            await conn.execute(text("PRAGMA foreign_keys = ON"))
            await conn.execute(
                text("INSERT INTO empires (id, name) VALUES (:id, :name)"),
                {"id": empire_id, "name": "test_empire"},
            )
            await conn.execute(
                text(
                    "INSERT INTO workflows (id, name, entry_stage_id) "
                    "VALUES (:id, :name, :entry_stage_id)"
                ),
                {"id": workflow_id, "name": "test_workflow", "entry_stage_id": workflow_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO rooms (id, empire_id, workflow_id, name, description, "
                    "prompt_kit_prefix_markdown, archived) "
                    "VALUES (:id, :eid, :wid, :name, '', '', 0)"
                ),
                {"id": room_id, "eid": empire_id, "wid": workflow_id, "name": "test_room"},
            )
            await conn.execute(
                text(
                    "INSERT INTO directives (id, text, target_room_id, created_at, task_id) "
                    "VALUES (:id, :text, :room_id, :created_at, NULL)"
                ),
                {
                    "id": directive_id,
                    "text": "テスト指令",
                    "room_id": room_id,
                    "created_at": created_at,
                },
            )

        # delete 前に directive が存在することを確認
        async with empty_engine.connect() as conn:
            await conn.execute(text("PRAGMA foreign_keys = ON"))
            result = await conn.execute(
                text("SELECT id FROM directives WHERE id = :id"),
                {"id": directive_id},
            )
            assert result.first() is not None, "CASCADE テスト前に Directive が存在する必要がある"

        # room を削除 — CASCADE が directive を削除すべき
        async with empty_engine.begin() as conn:
            await conn.execute(text("PRAGMA foreign_keys = ON"))
            await conn.execute(
                text("DELETE FROM rooms WHERE id = :id"),
                {"id": room_id},
            )

        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT id FROM directives WHERE id = :id"),
                {"id": directive_id},
            )
            remaining = result.first()
        assert remaining is None, (
            "[FAIL] Directive 行が Room 削除後も存在します。\n"
            "directives.target_room_id → rooms.id ON DELETE CASCADE が動作していません。\n"
            "次：tables/directives.py で ForeignKey('rooms.id', ondelete='CASCADE') を検証。"
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-006: §BUG-DRR-001 — task_id FK does NOT exist at 0006 (受入基準 11)
# ---------------------------------------------------------------------------
class TestBugDrr001TaskIdFkClosure:
    """TC-IT-DRR-006: BUG-DRR-001 closure 確認 — directives.task_id FK が現在存在。

    §BUG-DRR-001 (BUG-EMR-001 パターン): 0006 レベルで OPEN であった (tasks テーブルが
    存在しなかった)。Alembic revision 0007_task_aggregate は
    ``op.batch_alter_table('directives')`` 経由で
    ``fk_directives_task_id`` (``directives.task_id → tasks.id`` ON DELETE RESTRICT)
    を追加することで、これを閉じた。

    このテストは物理的に closure を確認：HEAD (0007) で FK が存在。
    test_alembic_task.py の TC-IT-TR-008 が正規の closure テスト；
    このテストは directive 側が当該アサーションと一致することを確認。
    """

    async def test_task_id_fk_present_in_directives_at_head(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """PRAGMA foreign_key_list('directives') が HEAD で 'tasks' への参照を持つ。

        BUG-DRR-001 closure: 0007_task_aggregate が batch_alter_table 経由で FK を追加。
        upgrade head (0007) では、directives.task_id → tasks.id FK が存在する必要がある。
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_key_list('directives')"))
            fk_rows = list(result)
        # PRAGMA foreign_key_list カラム: id, seq, table, from, to, ...
        referenced_tables = {row[2] for row in fk_rows}
        assert "tasks" in referenced_tables, (
            f"[FAIL] directives.task_id FK to 'tasks' が HEAD レベルで不足。\n"
            f"BUG-DRR-001 closure は 0007_task_aggregate が batch_alter_table"
            f"('directives') 経由で fk_directives_task_id ('tasks' の 'task_id' on "
            f"delete RESTRICT) を追加することを必要とする。\n"
            f"FK 参照が見つかりました: {referenced_tables}"
        )

    async def test_task_id_column_exists_as_nullable(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """task_id カラムが directives に存在するが、FK なしで nullable。"""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info('directives')"))
            columns = {row[1]: {"notnull": row[3], "dflt": row[4]} for row in result}
        assert "task_id" in columns, (
            f"[FAIL] task_id カラムが directives から不足。\n"
            f"カラムが見つかりました: {list(columns.keys())}"
        )
        assert columns["task_id"]["notnull"] == 0, (
            "[FAIL] task_id は 0006 レベルで nullable である必要があります (§BUG-DRR-001)。"
        )
