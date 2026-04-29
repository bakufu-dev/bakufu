"""Bootstrap end-to-end sequence 統合テスト
(TC-IT-PF-012 / 031 / 032 / 036 / 037)。

Confirmation G + Schneier 中等 4 物理保証 — 8 ステージ冷起動が
実際の SQLite + 実際の Alembic + 実際のマスキングゲートウェイに対して
実行される。リスナー (ステージ 8) は ``None`` のままにする（別 PR で予定されている
FastAPI HTTP surface を引き込まないため）。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from bakufu.infrastructure.bootstrap import Bootstrap
from bakufu.infrastructure.exceptions import BakufuConfigError, BakufuMigrationError
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


@pytest.fixture
def _bakufu_data_dir(  # pyright: ignore[reportUnusedFunction]
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """BAKUFU_DATA_DIR を新規の tmp_path サブディレクトリに指す。"""
    monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
    return tmp_path


class TestBootstrapHappyPath:
    """TC-IT-PF-012 / 036: Bootstrap.run() が 0→8 を実際の Alembic で実行。"""

    async def test_full_run_creates_db_with_schema(
        self,
        _bakufu_data_dir: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-012 / 036: end-to-end Bootstrap.run() が成功。"""
        boot = Bootstrap(migration_runner=run_upgrade_head)
        with caplog.at_level(logging.INFO):
            await boot.run()
        try:
            # ステージログが文書化された 0→8 順序をトレースする。
            info_messages = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
            for stage in range(1, 8):
                assert any(f"Bootstrap stage {stage}/8" in m for m in info_messages), (
                    f"ステージ {stage} の INFO ログが不足"
                )

            # Bootstrap が戻った後、DB ファイル + スキーマが存在する。
            db_path = _bakufu_data_dir / "bakufu.db"
            assert db_path.exists()

            # ステージ 5 で attachments ディレクトリが準備された。
            attachments_dir = _bakufu_data_dir / "attachments"
            assert attachments_dir.is_dir()
        finally:
            if boot.app_engine is not None:
                await boot.app_engine.dispose()


class TestStageFailFast:
    """TC-IT-PF-031: ステージ 1 の失敗がカスケードを停止。"""

    async def test_relative_data_dir_fails_at_stage_1(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-IT-PF-031: BAKUFU_DATA_DIR=./relative がステージ 1 で中止。"""
        monkeypatch.setenv("BAKUFU_DATA_DIR", "./relative-path")
        boot = Bootstrap(migration_runner=run_upgrade_head)
        with pytest.raises(BakufuConfigError) as excinfo:
            await boot.run()
        assert excinfo.value.msg_id == "MSG-PF-001"

    async def test_migration_failure_propagates_as_bakufu_migration_error(
        self,
        _bakufu_data_dir: Path,
    ) -> None:
        """TC-IT-PF-031: ステージ 3 が Alembic 失敗時に ``BakufuMigrationError`` を raise。"""

        async def _exploding_migration(_engine: object) -> str:
            msg = "意図的なマイグレーション爆発"
            raise RuntimeError(msg)

        boot = Bootstrap(migration_runner=_exploding_migration)
        with pytest.raises(BakufuMigrationError) as excinfo:
            await boot.run()
        assert excinfo.value.msg_id == "MSG-PF-004"
        assert "Alembic migration failed" in excinfo.value.message


class TestStage4NonFatal:
    """TC-IT-PF-032: ステージ 4 (pid_gc) 失敗が起動を中止しない。"""

    async def test_pid_gc_failure_is_logged_and_bootstrap_continues(
        self,
        _bakufu_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-032: pid_gc raise → WARN だが、ステージ 5-8 はまだ実行。"""

        async def _explode(_factory: object) -> dict[str, int]:
            msg = "pid_gc 崩壊"
            raise RuntimeError(msg)

        from bakufu.infrastructure.persistence.sqlite import pid_gc

        monkeypatch.setattr(pid_gc, "run_startup_gc", _explode)

        boot = Bootstrap(migration_runner=run_upgrade_head)
        with caplog.at_level(logging.WARNING):
            await boot.run()
        try:
            warn_messages = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
            assert any(
                "Bootstrap stage 4/8" in m and "continuing startup" in m for m in warn_messages
            )
        finally:
            if boot.app_engine is not None:
                await boot.app_engine.dispose()


class TestEmptyHandlerRegistryWarn:
    """TC-IT-PF-008-A: ステージ 6 は handler_registry が空のとき WARN をログ。"""

    async def test_empty_registry_warn_at_startup(
        self,
        _bakufu_data_dir: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-008-A: 'No event handlers registered' WARN が出現。"""
        boot = Bootstrap(migration_runner=run_upgrade_head)
        with caplog.at_level(logging.WARNING):
            await boot.run()
        try:
            warn_messages = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
            assert any("No event handlers registered" in m for m in warn_messages)
        finally:
            if boot.app_engine is not None:
                await boot.app_engine.dispose()


class TestUmaskAtStage0:
    """TC-IT-PF-001-A / TC-UT-PF-001-A: ステージ 0 が umask 0o077 を設定 (POSIX)。"""

    async def test_umask_applied_at_stage_0(
        self,
        _bakufu_data_dir: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-UT-PF-001-A: ステージ 0 INFO ログが ``umask set to 0o077`` に言及。"""
        import platform

        if platform.system() == "Windows":
            pytest.skip("os.umask は Windows では no-op")
        boot = Bootstrap(migration_runner=run_upgrade_head)
        with caplog.at_level(logging.INFO):
            await boot.run()
        try:
            info_messages = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
            assert any("Bootstrap stage 0/8: umask set to 0o077" in m for m in info_messages)
        finally:
            if boot.app_engine is not None:
                await boot.app_engine.dispose()

    async def test_db_file_has_secure_mode(
        self,
        _bakufu_data_dir: Path,
    ) -> None:
        """TC-IT-PF-001-A: umask 0o077 の下で書き込まれた DB ファイルは 0o600 モード。"""
        import platform

        if platform.system() == "Windows":
            pytest.skip("POSIX 限定ファイルモードビット")
        boot = Bootstrap(migration_runner=run_upgrade_head)
        await boot.run()
        try:
            db_path = _bakufu_data_dir / "bakufu.db"
            mode = db_path.stat().st_mode & 0o777
            # 0o600 が厳密な目標； ここで 0o644 は umask が
            # 適用されていないことを意味する。0o600 のみを許可。
            assert mode == 0o600
        finally:
            if boot.app_engine is not None:
                await boot.app_engine.dispose()


class TestFullDbContractAfterBootstrap:
    """TC-IT-PF-036: Bootstrap 後の DB が文書化されたコントラクトと一致。"""

    async def test_three_tables_and_two_triggers_present(
        self,
        _bakufu_data_dir: Path,
    ) -> None:
        """TC-IT-PF-036: テーブル + トリガー + インデックスが生 SQL で可視。"""
        boot = Bootstrap(migration_runner=run_upgrade_head)
        await boot.run()

        engine = boot.app_engine
        assert engine is not None
        try:
            async with engine.connect() as conn:
                tables_result = await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
                tables = {row[0] for row in tables_result}
                triggers_result = await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='trigger'")
                )
                triggers = {row[0] for row in triggers_result}
            assert {"audit_log", "bakufu_pid_registry", "domain_event_outbox"}.issubset(tables)
            assert {"audit_log_no_delete", "audit_log_update_restricted"}.issubset(triggers)
        finally:
            await engine.dispose()
