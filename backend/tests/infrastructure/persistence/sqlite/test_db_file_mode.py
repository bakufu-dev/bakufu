"""DB file mode forensic audit integration tests
(TC-IT-PF-002-A / 002-B / 002-C, REQ-PF-002-A, Schneier 致命1).

Bootstrap stage 0 sets ``umask 0o077`` so newly-created SQLite files
inherit ``0o600``. These tests pin the *forensic* contract: when a
prior bakufu run left ``bakufu.db`` / ``bakufu.db-wal`` /
``bakufu.db-shm`` at ``0o644``, the
:func:`db_file_mode.verify_and_repair` audit must:

* **Detect** the anomaly (status=``"repaired"``).
* **WARN-log** with the original mode for post-incident analysis.
* **Repair** the file to ``0o600`` so the next process is safe.
* **Continue** — no Fail Fast — so operators do not lose the forensic
  trail by seeing a startup abort.

Linux/macOS only; Windows returns ``"windows_skip"`` for every file.
"""

from __future__ import annotations

import logging
import platform
import stat
from pathlib import Path

import pytest
from bakufu.infrastructure.persistence.sqlite import db_file_mode
from bakufu.infrastructure.persistence.sqlite.db_file_mode import (
    DB_FILE_NAMES,
    SECURE_FILE_MODE,
    verify_and_repair,
)

# Skip the whole module on Windows — POSIX mode bits do not apply.
pytestmark = pytest.mark.skipif(
    platform.system() == "Windows",
    reason="POSIX file mode bits unavailable on Windows",
)


def _write_with_mode(path: Path, mode: int) -> None:
    """Create a placeholder file at ``path`` and chmod to ``mode``."""
    path.write_bytes(b"sqlite-test-stub")
    path.chmod(mode)


class TestNewFilesAlready0o600:
    """TC-IT-PF-002-A: file already at 0o600 → status ``"ok"``, no WARN."""

    def test_new_db_at_0o600_is_marked_ok(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-A: bakufu.db created at 0o600 yields status='ok'."""
        _write_with_mode(tmp_path / "bakufu.db", SECURE_FILE_MODE)

        with caplog.at_level(logging.WARNING):
            results = verify_and_repair(tmp_path)

        assert results["bakufu.db"] == "ok"
        # No WARN should fire for a clean file.
        warn_msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert all("DB file mode anomaly" not in m for m in warn_msgs)

    def test_post_audit_mode_unchanged(self, tmp_path: Path) -> None:
        """TC-IT-PF-002-A: a clean file's mode is not altered."""
        target = tmp_path / "bakufu.db"
        _write_with_mode(target, SECURE_FILE_MODE)
        verify_and_repair(tmp_path)
        assert stat.S_IMODE(target.stat().st_mode) == SECURE_FILE_MODE


class TestExistingFileAt0o644Repairs:
    """TC-IT-PF-002-B: 0o644 file → WARN + chmod to 0o600 + status ``"repaired"``."""

    def test_anomaly_detected_and_repaired(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-B: a 0o644 bakufu.db is repaired to 0o600."""
        target = tmp_path / "bakufu.db"
        _write_with_mode(target, 0o644)

        with caplog.at_level(logging.WARNING):
            results = verify_and_repair(tmp_path)

        assert results["bakufu.db"] == "repaired"
        assert stat.S_IMODE(target.stat().st_mode) == SECURE_FILE_MODE

    def test_warn_log_carries_original_mode(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-B: forensic WARN must record the *original* mode."""
        _write_with_mode(tmp_path / "bakufu.db", 0o644)

        with caplog.at_level(logging.WARNING):
            verify_and_repair(tmp_path)

        warn_msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        # The forensic message must (a) name the file, (b) include the
        # original mode in octal so post-incident investigators can
        # correlate against process audit logs, and (c) note the
        # umask-0o077 enforcement gap.
        assert any("DB file mode anomaly" in m for m in warn_msgs)
        assert any("0o644" in m for m in warn_msgs)
        assert any("umask" in m for m in warn_msgs)

    def test_repair_does_not_block_startup(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-B: forensic policy says continue, never Fail Fast."""
        _write_with_mode(tmp_path / "bakufu.db", 0o644)
        # The function returns a status dict (no raise) — that itself is
        # the proof that startup is not blocked.
        with caplog.at_level(logging.WARNING):
            results = verify_and_repair(tmp_path)
        assert isinstance(results, dict)
        assert results["bakufu.db"] in {"repaired", "repair_failed"}


class TestWalAndShmFilesAuditedToo:
    """TC-IT-PF-002-C: bakufu.db-wal and bakufu.db-shm follow the same audit."""

    def test_wal_at_0o644_is_repaired(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-C: bakufu.db-wal repair path."""
        wal = tmp_path / "bakufu.db-wal"
        _write_with_mode(wal, 0o644)

        with caplog.at_level(logging.WARNING):
            results = verify_and_repair(tmp_path)

        assert results["bakufu.db-wal"] == "repaired"
        assert stat.S_IMODE(wal.stat().st_mode) == SECURE_FILE_MODE

    def test_shm_at_0o644_is_repaired(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-C: bakufu.db-shm repair path."""
        shm = tmp_path / "bakufu.db-shm"
        _write_with_mode(shm, 0o644)

        with caplog.at_level(logging.WARNING):
            results = verify_and_repair(tmp_path)

        assert results["bakufu.db-shm"] == "repaired"
        assert stat.S_IMODE(shm.stat().st_mode) == SECURE_FILE_MODE

    def test_absent_wal_and_shm_are_marked_absent(self, tmp_path: Path) -> None:
        """TC-IT-PF-002-C: WAL/SHM may be absent right after upgrade — status='absent'."""
        # Only the main DB exists; WAL/SHM materialise on first write.
        _write_with_mode(tmp_path / "bakufu.db", SECURE_FILE_MODE)

        results = verify_and_repair(tmp_path)
        assert results["bakufu.db"] == "ok"
        assert results["bakufu.db-wal"] == "absent"
        assert results["bakufu.db-shm"] == "absent"

    def test_three_files_audited_independently(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-C: each of the three files gets its own status entry."""
        for name in DB_FILE_NAMES:
            _write_with_mode(tmp_path / name, 0o644)

        with caplog.at_level(logging.WARNING):
            results = verify_and_repair(tmp_path)

        assert set(results.keys()) == set(DB_FILE_NAMES)
        for name in DB_FILE_NAMES:
            assert results[name] == "repaired"
            assert stat.S_IMODE((tmp_path / name).stat().st_mode) == SECURE_FILE_MODE


class TestRepairFailureDoesNotRaise:
    """REQ-PF-002-A continuity: chmod failure is logged ERROR, never raises."""

    def test_chmod_failure_is_swallowed(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """REQ-PF-002-A: chmod raising OSError → status='repair_failed', no raise."""
        target = tmp_path / "bakufu.db"
        _write_with_mode(target, 0o644)

        original_chmod = Path.chmod

        def _explode(self: Path, mode: int) -> None:
            if self == target:
                raise PermissionError("simulated chmod failure")
            original_chmod(self, mode)

        monkeypatch.setattr(Path, "chmod", _explode)

        with caplog.at_level(logging.ERROR):
            results = verify_and_repair(tmp_path)

        assert results["bakufu.db"] == "repair_failed"
        # The audit must surface the failure with an ERROR-level entry so
        # ops dashboards can alert.
        error_msgs = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
        assert any("DB file mode repair failed" in m for m in error_msgs)


class TestDbFileModeBootstrapIntegration:
    """Bootstrap stage 3 wires the audit; the mode dict appears in the INFO log."""

    @pytest.mark.asyncio
    async def test_bootstrap_logs_mode_audit_results(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """REQ-PF-002-A: Bootstrap.run() emits 'DB file mode audit:' INFO line."""
        from bakufu.infrastructure.bootstrap import Bootstrap
        from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head

        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
        boot = Bootstrap(migration_runner=run_upgrade_head)
        with caplog.at_level(logging.INFO):
            await boot.run()

        info_msgs = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
        assert any("DB file mode audit:" in m for m in info_msgs)


# Re-export the module so coverage attributes the tests to the right
# source file when reports are aggregated.
_ = db_file_mode
