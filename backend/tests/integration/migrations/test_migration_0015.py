"""Alembic migration 0015 テスト（TC-IT-MIGR-001〜002）。

Issue: #123
設計書: docs/features/deliverable-template/ai-validation/test-design.md §Alembic migration 0015
対応要件: REQ-AIVM-004（Alembic migration 0015 適用可否）

TC-IT-MIGR-001: alembic upgrade head で 0015 が適用される。
TC-IT-MIGR-002: alembic downgrade 0014 で 0015 がロールバックされる。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import text

from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.asyncio

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _alembic_config(url: str) -> object:
    """bakufu の Alembic Config を解決する。"""
    from alembic.config import Config

    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


class TestMigration0015:
    """TC-IT-MIGR-001〜002: 0015_deliverable_records マイグレーションテスト。"""

    async def test_upgrade_head_creates_deliverable_records_tables(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-001: alembic upgrade head で deliverable_records / criterion_validation_results が作成される。

        要件: REQ-AIVM-004
        """
        await run_upgrade_head(empty_engine)

        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables = {row[0] for row in result}

        assert "deliverable_records" in tables, (
            f"deliverable_records テーブルが存在しない。テーブル一覧: {tables}"
        )
        assert "criterion_validation_results" in tables, (
            f"criterion_validation_results テーブルが存在しない。テーブル一覧: {tables}"
        )

        # カラム確認（deliverable_records）
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("PRAGMA table_info(deliverable_records)")
            )
            columns = {row[1] for row in result}

        expected_columns = {
            "id",
            "deliverable_id",
            "template_ref_template_id",
            "template_ref_version_major",
            "template_ref_version_minor",
            "template_ref_version_patch",
            "content",
            "task_id",
            "validation_status",
            "produced_by",
            "created_at",
            "validated_at",
        }
        assert expected_columns.issubset(columns), (
            f"deliverable_records テーブルのカラム不足。\n"
            f"期待: {expected_columns}\n"
            f"実際: {columns}\n"
            f"不足: {expected_columns - columns}"
        )

        # インデックス確認
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='deliverable_records'")
            )
            indexes = {row[0] for row in result}

        expected_indexes = {
            "ix_deliverable_records_deliverable_id",
            "ix_deliverable_records_task_id",
            "ix_deliverable_records_validation_status",
        }
        assert expected_indexes.issubset(indexes), (
            f"deliverable_records のインデックス不足。\n"
            f"期待: {expected_indexes}\n"
            f"実際: {indexes}\n"
            f"不足: {expected_indexes - indexes}"
        )

    async def test_downgrade_to_0014_removes_deliverable_records_tables(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-MIGR-002: downgrade 0014 で deliverable_records / criterion_validation_results が消える。

        要件: REQ-AIVM-004, §確定D
        """
        # まず upgrade head を適用
        await run_upgrade_head(empty_engine)

        # upgrade 後にテーブルが存在することを確認
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables_after_upgrade = {row[0] for row in result}

        assert "deliverable_records" in tables_after_upgrade, (
            f"upgrade 後に deliverable_records が存在しない: {tables_after_upgrade}"
        )

        # 0014 へ downgrade
        url = str(empty_engine.url)
        cfg = _alembic_config(url)

        def _do_downgrade() -> None:
            from alembic import command
            command.downgrade(cfg, "0014_external_review_gate_criteria")  # type: ignore[arg-type]

        await asyncio.to_thread(_do_downgrade)

        # downgrade 後にテーブルが消えていることを確認
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables_after_downgrade = {row[0] for row in result}

        assert "deliverable_records" not in tables_after_downgrade, (
            f"downgrade 後も deliverable_records が残っている: {tables_after_downgrade}"
        )
        assert "criterion_validation_results" not in tables_after_downgrade, (
            f"downgrade 後も criterion_validation_results が残っている: {tables_after_downgrade}"
        )
