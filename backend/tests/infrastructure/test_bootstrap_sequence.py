"""Bootstrap end-to-end sequence integration tests
(TC-IT-PF-012 / 031 / 032 / 036 / 037).

Confirmation G + Schneier 中等 4 物理保証 — full eight-stage cold start
runs against real SQLite + real Alembic + real masking gateway. The
listener (stage 8) is left as ``None`` so we don't drag in the FastAPI
HTTP surface that lives in a future PR.
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
    """Point BAKUFU_DATA_DIR at a fresh tmp_path subdirectory."""
    monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
    return tmp_path


class TestBootstrapHappyPath:
    """TC-IT-PF-012 / 036: Bootstrap.run() walks 0→8 with real Alembic."""

    async def test_full_run_creates_db_with_schema(
        self,
        _bakufu_data_dir: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-012 / 036: end-to-end Bootstrap.run() succeeds."""
        boot = Bootstrap(migration_runner=run_upgrade_head)
        with caplog.at_level(logging.INFO):
            await boot.run()
        try:
            # Stage logs trace the documented 0→8 ordering.
            info_messages = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
            for stage in range(1, 8):
                assert any(f"Bootstrap stage {stage}/8" in m for m in info_messages), (
                    f"missing stage {stage} INFO log"
                )

            # The DB file + schema exist after Bootstrap returns.
            db_path = _bakufu_data_dir / "bakufu.db"
            assert db_path.exists()

            # And the attachments directory was prepared in stage 5.
            attachments_dir = _bakufu_data_dir / "attachments"
            assert attachments_dir.is_dir()
        finally:
            if boot.app_engine is not None:
                await boot.app_engine.dispose()


class TestStageFailFast:
    """TC-IT-PF-031: a stage 1 failure stops the cascade."""

    async def test_relative_data_dir_fails_at_stage_1(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-IT-PF-031: BAKUFU_DATA_DIR=./relative aborts at stage 1."""
        monkeypatch.setenv("BAKUFU_DATA_DIR", "./relative-path")
        boot = Bootstrap(migration_runner=run_upgrade_head)
        with pytest.raises(BakufuConfigError) as excinfo:
            await boot.run()
        assert excinfo.value.msg_id == "MSG-PF-001"

    async def test_migration_failure_propagates_as_bakufu_migration_error(
        self,
        _bakufu_data_dir: Path,
    ) -> None:
        """TC-IT-PF-031: stage 3 raises ``BakufuMigrationError`` when Alembic fails."""

        async def _exploding_migration(_engine: object) -> str:
            msg = "intentional migration explosion"
            raise RuntimeError(msg)

        boot = Bootstrap(migration_runner=_exploding_migration)
        with pytest.raises(BakufuMigrationError) as excinfo:
            await boot.run()
        assert excinfo.value.msg_id == "MSG-PF-004"
        assert "Alembic migration failed" in excinfo.value.message


class TestStage4NonFatal:
    """TC-IT-PF-032: stage 4 (pid_gc) failure does not abort startup."""

    async def test_pid_gc_failure_is_logged_and_bootstrap_continues(
        self,
        _bakufu_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-032: pid_gc raise → WARN, but stages 5-8 still run."""

        async def _explode(_factory: object) -> dict[str, int]:
            msg = "pid_gc collapsed"
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
    """TC-IT-PF-008-A: stage 6 logs WARN when handler_registry is empty."""

    async def test_empty_registry_warn_at_startup(
        self,
        _bakufu_data_dir: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-008-A: 'No event handlers registered' WARN appears."""
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
    """TC-IT-PF-001-A / TC-UT-PF-001-A: stage 0 sets umask 0o077 (POSIX)."""

    async def test_umask_applied_at_stage_0(
        self,
        _bakufu_data_dir: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-UT-PF-001-A: stage 0 INFO log mentions ``umask set to 0o077``."""
        import platform

        if platform.system() == "Windows":
            pytest.skip("os.umask is a no-op on Windows")
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
        """TC-IT-PF-001-A: DB file written under umask 0o077 has 0o600 mode."""
        import platform

        if platform.system() == "Windows":
            pytest.skip("POSIX-only file mode bits")
        boot = Bootstrap(migration_runner=run_upgrade_head)
        await boot.run()
        try:
            db_path = _bakufu_data_dir / "bakufu.db"
            mode = db_path.stat().st_mode & 0o777
            # 0o600 is the strict goal; 0o644 here would mean umask was not
            # applied. Allow exact 0o600 only.
            assert mode == 0o600
        finally:
            if boot.app_engine is not None:
                await boot.app_engine.dispose()


class TestFullDbContractAfterBootstrap:
    """TC-IT-PF-036: the post-Bootstrap DB matches the documented contract."""

    async def test_three_tables_and_two_triggers_present(
        self,
        _bakufu_data_dir: Path,
    ) -> None:
        """TC-IT-PF-036: tables + triggers + index visible via raw SQL."""
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
