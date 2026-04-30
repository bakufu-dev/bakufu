"""Alembic migration 0012 テスト: DeliverableTemplate / RoleProfile テーブル追加 (Issue #119).

TC-IT-MIGR-012-001〜005:
- upgrade: deliverable_templates / role_profiles 2 テーブル追加
- upgrade: role_profiles UNIQUE(empire_id, role) 制約存在
- downgrade: role_profiles → deliverable_templates の逆順削除（FK 安全順序）
- upgrade → downgrade → upgrade ラウンドトリップ冪等性
- revision chain 一直線 (0012 が単一 head / down_revision == 0011_stage_required_deliverables)

§確定 K (docs/features/deliverable-template/repository/detailed-design.md):
  revision id: "0012_deliverable_template_aggregate"
  down_revision: "0011_stage_required_deliverables"
  upgrade: deliverable_templates → role_profiles の順
  downgrade: role_profiles → deliverable_templates の逆順
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from alembic.script import ScriptDirectory
from bakufu.infrastructure.persistence.sqlite import engine as engine_mod
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

_REVISION_ID = "0012_deliverable_template_aggregate"
_DOWN_REVISION = "0011_stage_required_deliverables"


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def empty_engine(tmp_path: Path) -> AsyncIterator[engine_mod.AsyncEngine]:
    """スキーマ未適用の新規 SQLite エンジン。"""
    from sqlalchemy.ext.asyncio import AsyncEngine

    url = f"sqlite+aiosqlite:///{tmp_path / 'bakufu_0012.db'}"
    engine: AsyncEngine = engine_mod.create_engine(url)
    try:
        yield engine
    finally:
        await engine.dispose()


def _alembic_config() -> Config:
    """bakufu の Alembic 設定オブジェクトを返す。"""
    backend_root = Path(__file__).resolve().parents[4]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    return cfg


# ---------------------------------------------------------------------------
# TC-IT-MIGR-012-001: upgrade で 2 テーブル追加
# ---------------------------------------------------------------------------
class TestMigration0012Upgrade:
    """TC-IT-MIGR-012-001: alembic upgrade head 後のスキーマ確認。"""

    async def test_deliverable_templates_table_exists_after_upgrade(
        self,
        empty_engine: engine_mod.AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-012-001a: upgrade head → deliverable_templates テーブルが存在する。"""
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = empty_engine
        await run_upgrade_head(engine)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert "deliverable_templates" in tables, (
            "[FAIL] deliverable_templates テーブルが存在しない。\n"
            "Next: 0012_deliverable_template_aggregate.upgrade() を確認せよ。"
        )

    async def test_role_profiles_table_exists_after_upgrade(
        self,
        empty_engine: engine_mod.AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-012-001b: upgrade head → role_profiles テーブルが存在する。"""
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = empty_engine
        await run_upgrade_head(engine)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert "role_profiles" in tables, (
            "[FAIL] role_profiles テーブルが存在しない。\n"
            "Next: 0012_deliverable_template_aggregate.upgrade() を確認せよ。"
        )


# ---------------------------------------------------------------------------
# TC-IT-MIGR-012-002: upgrade 後 UNIQUE(empire_id, role) 制約が存在する
# ---------------------------------------------------------------------------
class TestMigration0012UniqueConstraint:
    """TC-IT-MIGR-012-002: role_profiles に UNIQUE(empire_id, role) 制約が存在する。"""

    async def test_role_profiles_has_unique_index_after_upgrade(
        self,
        empty_engine: engine_mod.AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-012-002: PRAGMA index_list で UNIQUE インデックスが存在する (§確定 H)。"""
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = empty_engine
        await run_upgrade_head(engine)
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA index_list(role_profiles)"))
            indexes = list(result)
        # UNIQUE インデックスが少なくとも 1 件存在すること
        assert indexes, (
            "[FAIL] role_profiles に UNIQUE インデックスが存在しない。\n"
            "Next: 0012 migration の UniqueConstraint(empire_id, role) を確認せよ。"
        )
        # いずれかのインデックスが UNIQUE (unique=1)
        unique_indexes = [idx for idx in indexes if idx[2] == 1]  # idx[2] = unique flag
        assert unique_indexes, (
            "[FAIL] role_profiles のインデックスに UNIQUE なものが存在しない。\n"
            "Next: 0012 migration の UniqueConstraint 定義を確認せよ (§確定 H)。"
        )


# ---------------------------------------------------------------------------
# TC-IT-MIGR-012-003: downgrade で 2 テーブル削除（FK 安全順序）
# ---------------------------------------------------------------------------
class TestMigration0012Downgrade:
    """TC-IT-MIGR-012-003: downgrade で role_profiles → deliverable_templates の逆順削除。"""

    async def test_downgrade_removes_both_tables(
        self,
        empty_engine: engine_mod.AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-012-003: downgrade to 0011 → 2 テーブルが削除される。"""
        from alembic import command
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = empty_engine
        await run_upgrade_head(engine)

        cfg = _alembic_config()
        cfg.set_main_option("sqlalchemy.url", str(engine.url))

        def _downgrade() -> None:
            command.downgrade(cfg, _DOWN_REVISION)

        await asyncio.to_thread(_downgrade)

        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}

        assert "deliverable_templates" not in tables, (
            "[FAIL] downgrade 後も deliverable_templates テーブルが残存。\n"
            "Next: 0012 downgrade() の op.drop_table を確認せよ。"
        )
        assert "role_profiles" not in tables, (
            "[FAIL] downgrade 後も role_profiles テーブルが残存。\n"
            "Next: 0012 downgrade() の op.drop_table を確認せよ。"
        )

    async def test_downgrade_preserves_other_tables(
        self,
        empty_engine: engine_mod.AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-012-003b: downgrade 後も workflow_stages 等の他テーブルが残る。"""
        from alembic import command
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = empty_engine
        await run_upgrade_head(engine)

        cfg = _alembic_config()
        cfg.set_main_option("sqlalchemy.url", str(engine.url))

        def _downgrade() -> None:
            command.downgrade(cfg, _DOWN_REVISION)

        await asyncio.to_thread(_downgrade)

        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}

        # 他テーブルは残っているはず
        assert "workflow_stages" in tables, (
            "[FAIL] downgrade で workflow_stages まで削除されてしまった。"
        )


# ---------------------------------------------------------------------------
# TC-IT-MIGR-012-004: upgrade → downgrade → upgrade ラウンドトリップ
# ---------------------------------------------------------------------------
class TestMigration0012RoundTrip:
    """TC-IT-MIGR-012-004: upgrade head → downgrade → upgrade head が冪等。"""

    async def test_round_trip_leaves_schema_at_head(
        self,
        empty_engine: engine_mod.AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-012-004: up → down to 0011 → up が 2 テーブルを正規状態に戻す。"""
        from alembic import command
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = empty_engine

        # 1st upgrade
        await run_upgrade_head(engine)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables_after_up = {row[0] for row in result}
        assert "deliverable_templates" in tables_after_up
        assert "role_profiles" in tables_after_up

        # downgrade
        cfg = _alembic_config()
        cfg.set_main_option("sqlalchemy.url", str(engine.url))

        def _downgrade() -> None:
            command.downgrade(cfg, _DOWN_REVISION)

        await asyncio.to_thread(_downgrade)

        # 2nd upgrade
        await run_upgrade_head(engine)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables_after_reup = {row[0] for row in result}

        assert "deliverable_templates" in tables_after_reup, (
            "[FAIL] 2nd upgrade 後に deliverable_templates がない。"
        )
        assert "role_profiles" in tables_after_reup, (
            "[FAIL] 2nd upgrade 後に role_profiles がない。"
        )


# ---------------------------------------------------------------------------
# TC-IT-MIGR-012-005: revision chain 一直線
# ---------------------------------------------------------------------------
class TestMigration0012RevisionChain:
    """TC-IT-MIGR-012-005: 0012 が単一 head かつ down_revision チェーンが正しい。"""

    async def test_alembic_has_single_head(self) -> None:
        """TC-IT-MIGR-012-005a: ScriptDirectory.get_heads() は 1 件だけ返す。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"[FAIL] Alembic head が複数存在: {heads}。"
            "各 Repository PR は単一 revision を追加する。"
        )

    async def test_0012_has_correct_down_revision(self) -> None:
        """TC-IT-MIGR-012-005b: 0012.down_revision == '0011_stage_required_deliverables'。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        rev = script.get_revision(_REVISION_ID)
        assert rev is not None, f"Revision {_REVISION_ID!r} が見つからない"
        assert rev.down_revision == _DOWN_REVISION, (
            f"[FAIL] 0012.down_revision = {rev.down_revision!r}, 期待値 = {_DOWN_REVISION!r}"
        )
