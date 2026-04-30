"""Alembic migration 0011 テスト: Stage.required_deliverables (Issue #117).

TC-IT-MIGR-011-001〜004:
- upgrade: required_deliverables_json 追加 / deliverable_template 削除
- downgrade: required_deliverables_json 削除 / deliverable_template 復元
- upgrade/downgrade/upgrade のラウンドトリップ
- revision chain が線形 (0011 が head = 最新単一 head)

§確定 L (docs/features/workflow/repository/detailed-design.md):
  SQLite 3.35.0+ が DROP COLUMN を提供する。pyproject.toml requires-python = ">=3.12"
  → Python 3.12 同梱 SQLite は 3.42.0 以上が保証されるため追加要件なし。
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

_REVISION_ID = "0011_stage_required_deliverables"
_DOWN_REVISION = "0010_workflow_archived"


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def empty_engine(tmp_path: Path) -> AsyncIterator[engine_mod.AsyncEngine]:  # type: ignore[name-defined]
    """スキーマ未適用の新規 SQLite エンジン。"""
    from sqlalchemy.ext.asyncio import AsyncEngine

    url = f"sqlite+aiosqlite:///{tmp_path / 'bakufu_0011.db'}"
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
# TC-IT-MIGR-011-001: upgrade で required_deliverables_json 追加 / deliverable_template 削除
# ---------------------------------------------------------------------------
class TestMigration0011Upgrade:
    """TC-IT-MIGR-011-001: alembic upgrade head 後のスキーマ確認。"""

    async def test_required_deliverables_json_column_exists_after_upgrade(
        self,
        empty_engine: engine_mod.AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-011-001a: upgrade head → required_deliverables_json が存在する。

        workflow_stages テーブルに列が追加されていることを PRAGMA table_info で確認。
        §確定 L: 0011 upgrade = DROP deliverable_template + ADD required_deliverables_json。
        """
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = empty_engine  # type: ignore[assignment]
        await run_upgrade_head(engine)
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(workflow_stages)"))
            columns = {row[1] for row in result}  # row[1] = column name
        assert "required_deliverables_json" in columns, (
            "[FAIL] required_deliverables_json が workflow_stages に存在しない。\n"
            "Next: 0011_stage_required_deliverables.upgrade() を確認せよ。"
        )

    async def test_deliverable_template_column_absent_after_upgrade(
        self,
        empty_engine: engine_mod.AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-011-001b: upgrade head → 旧 deliverable_template 列が削除されている。"""
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = empty_engine  # type: ignore[assignment]
        await run_upgrade_head(engine)
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(workflow_stages)"))
            columns = {row[1] for row in result}
        assert "deliverable_template" not in columns, (
            "[FAIL] deliverable_template 列が upgrade 後も残存している。\n"
            "Next: 0011_stage_required_deliverables.upgrade() で op.drop_column を確認せよ。"
        )

    async def test_required_deliverables_json_default_is_empty_array(
        self,
        empty_engine: engine_mod.AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-011-001c: required_deliverables_json の server_default が '[]' である。

        §確定 L: DEFAULT '[]' — MVP 時点で本番データなし、変換不要。
        """
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = empty_engine  # type: ignore[assignment]
        await run_upgrade_head(engine)
        # 最小行を挿入して DEFAULT 値を確認する
        from uuid import uuid4

        wf_id = uuid4().hex
        stage_id = uuid4().hex
        async with engine.connect() as conn:
            await conn.execute(
                text(
                    "INSERT INTO workflows (id, name, entry_stage_id) VALUES (:id, :name, :entry)"
                ),
                {"id": wf_id, "name": "test-wf", "entry": stage_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO workflow_stages "
                    "(workflow_id, stage_id, name, kind, roles_csv, "
                    "completion_policy_json, notify_channels_json) "
                    "VALUES (:wf_id, :s_id, :name, :kind, :roles, :policy, :channels)"
                ),
                {
                    "wf_id": wf_id,
                    "s_id": stage_id,
                    "name": "test-stage",
                    "kind": "WORK",
                    "roles": "DEVELOPER",
                    "policy": '{"kind": "approved_by_reviewer", "description": ""}',
                    "channels": "[]",
                },
            )
            result = await conn.execute(
                text(
                    "SELECT required_deliverables_json FROM workflow_stages WHERE stage_id = :sid"
                ),
                {"sid": stage_id},
            )
            row = result.fetchone()
            await conn.commit()
        assert row is not None
        assert row[0] == "[]", (
            f"[FAIL] required_deliverables_json の DEFAULT が '[]' でなく {row[0]!r}。\n"
            "Next: 0011 migration の server_default=sa.text(\"'[]'\") を確認せよ。"
        )


# ---------------------------------------------------------------------------
# TC-IT-MIGR-011-002: downgrade で deliverable_template 復元 / required_deliverables_json 削除
# ---------------------------------------------------------------------------
class TestMigration0011Downgrade:
    """TC-IT-MIGR-011-002: downgrade 後のスキーマ確認。"""

    async def test_downgrade_removes_required_deliverables_json(
        self,
        empty_engine: engine_mod.AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-011-002a: downgrade → required_deliverables_json が削除される。"""
        from alembic import command
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = empty_engine  # type: ignore[assignment]
        await run_upgrade_head(engine)

        cfg = _alembic_config()
        cfg.set_main_option("sqlalchemy.url", str(engine.url))

        def _downgrade() -> None:
            command.downgrade(cfg, _DOWN_REVISION)

        await asyncio.to_thread(_downgrade)

        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(workflow_stages)"))
            columns = {row[1] for row in result}
        assert "required_deliverables_json" not in columns, (
            "[FAIL] downgrade 後も required_deliverables_json が残存している。\n"
            "Next: 0011_stage_required_deliverables.downgrade() で op.drop_column を確認せよ。"
        )

    async def test_downgrade_restores_deliverable_template(
        self,
        empty_engine: engine_mod.AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-011-002b: downgrade → deliverable_template 列が復元される。"""
        from alembic import command
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = empty_engine  # type: ignore[assignment]
        await run_upgrade_head(engine)

        cfg = _alembic_config()
        cfg.set_main_option("sqlalchemy.url", str(engine.url))

        def _downgrade() -> None:
            command.downgrade(cfg, _DOWN_REVISION)

        await asyncio.to_thread(_downgrade)

        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(workflow_stages)"))
            columns = {row[1] for row in result}
        assert "deliverable_template" in columns, (
            "[FAIL] downgrade 後に deliverable_template 列が存在しない。\n"
            "Next: 0011_stage_required_deliverables.downgrade() で op.add_column を確認せよ。"
        )


# ---------------------------------------------------------------------------
# TC-IT-MIGR-011-003: upgrade / downgrade / upgrade ラウンドトリップ
# ---------------------------------------------------------------------------
class TestMigration0011RoundTrip:
    """TC-IT-MIGR-011-003: upgrade head → downgrade → upgrade head が冪等。"""

    async def test_round_trip_leaves_schema_at_head(
        self,
        empty_engine: engine_mod.AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-011-003: up → down to 0010 → up が workflow_stages を正規状態に戻す。"""
        from alembic import command
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = empty_engine  # type: ignore[assignment]
        # 1st upgrade
        await run_upgrade_head(engine)
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(workflow_stages)"))
            cols_after_up = {row[1] for row in result}
        assert "required_deliverables_json" in cols_after_up
        assert "deliverable_template" not in cols_after_up

        # downgrade
        cfg = _alembic_config()
        cfg.set_main_option("sqlalchemy.url", str(engine.url))

        def _downgrade() -> None:
            command.downgrade(cfg, _DOWN_REVISION)

        await asyncio.to_thread(_downgrade)

        # 2nd upgrade
        await run_upgrade_head(engine)
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(workflow_stages)"))
            cols_after_reup = {row[1] for row in result}
        assert "required_deliverables_json" in cols_after_reup, (
            "[FAIL] 2nd upgrade 後に required_deliverables_json がない。"
        )
        assert "deliverable_template" not in cols_after_reup, (
            "[FAIL] 2nd upgrade 後に旧 deliverable_template 列が残存している。"
        )


# ---------------------------------------------------------------------------
# TC-IT-MIGR-011-004: revision chain 線形性
# ---------------------------------------------------------------------------
class TestMigration0011RevisionChain:
    """TC-IT-MIGR-011-004: 0011 が単一 head かつ down_revision チェーンが正しい。"""

    async def test_alembic_has_single_head(self) -> None:
        """TC-IT-MIGR-011-004a: ScriptDirectory.get_heads() は 1 件だけ返す。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"[FAIL] Alembic head が複数存在: {heads}。"
            "各 Repository PR は単一 revision を追加する。"
        )

    async def test_0011_has_correct_down_revision(self) -> None:
        """TC-IT-MIGR-011-004b: 0011 の down_revision == '0010_workflow_archived'。"""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        rev = script.get_revision(_REVISION_ID)
        assert rev is not None, f"Revision {_REVISION_ID!r} が見つからない"
        assert rev.down_revision == _DOWN_REVISION, (
            f"[FAIL] 0011.down_revision = {rev.down_revision!r}, 期待値 = {_DOWN_REVISION!r}"
        )
