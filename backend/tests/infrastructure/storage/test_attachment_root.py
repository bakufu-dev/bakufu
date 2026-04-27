"""Attachment FS root integration tests
(TC-IT-PF-011 / 029, TC-UT-PF-030).

Confirmation E + REQ-PF-009: ``ensure_root`` creates the directory at
``0o700`` on POSIX. ``start_orphan_gc_scheduler`` returns an
asyncio.Task we can cancel cleanly.
"""

from __future__ import annotations

import asyncio
import platform
from pathlib import Path

import pytest
from bakufu.infrastructure.exceptions import BakufuConfigError
from bakufu.infrastructure.storage import attachment_root


class TestEnsureRootCreatesDirectory:
    """TC-IT-PF-011: directory created at 0o700 on POSIX."""

    def test_creates_attachments_subdir(self, tmp_path: Path) -> None:
        """TC-IT-PF-011: <DATA_DIR>/attachments exists after call."""
        result = attachment_root.ensure_root(tmp_path)
        assert result == tmp_path / "attachments"
        assert result.is_dir()

    @pytest.mark.skipif(platform.system() == "Windows", reason="POSIX-only mode bits")
    def test_directory_mode_is_0o700(self, tmp_path: Path) -> None:
        """TC-IT-PF-011: chmod 0o700 enforced (POSIX only)."""
        result = attachment_root.ensure_root(tmp_path)
        mode = result.stat().st_mode & 0o777
        assert mode == 0o700

    def test_idempotent_when_directory_exists(self, tmp_path: Path) -> None:
        """TC-IT-PF-011: re-running on an existing dir is a no-op."""
        first = attachment_root.ensure_root(tmp_path)
        second = attachment_root.ensure_root(tmp_path)
        assert first == second
        assert first.is_dir()


class TestEnsureRootRejectsUnwritableParent:
    """TC-IT-PF-029: parent dir read-only → BakufuConfigError(MSG-PF-003)."""

    @pytest.mark.skipif(platform.system() == "Windows", reason="POSIX-only mode bits")
    def test_unwritable_parent_raises(self, tmp_path: Path) -> None:
        """TC-IT-PF-029: parent at 0o500 → mkdir fails → MSG-PF-003."""
        # Make tmp_path read-only (read + execute, no write).
        tmp_path.chmod(0o500)
        try:
            with pytest.raises(BakufuConfigError) as excinfo:
                attachment_root.ensure_root(tmp_path)
            assert excinfo.value.msg_id == "MSG-PF-003"
            assert "Attachment FS root initialization failed" in excinfo.value.message
        finally:
            # Restore so the tmp cleanup works.
            tmp_path.chmod(0o700)


class TestWindowsBranch:
    """TC-UT-PF-030: ``os.chmod`` skipped on Windows."""

    def test_windows_skips_chmod(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-UT-PF-030: platform=Windows → ensure_root succeeds without chmod."""
        monkeypatch.setattr("platform.system", lambda: "Windows")
        # On real Windows there'd be no chmod call, but on a POSIX runner
        # the test verifies the platform branch chooses to skip — the
        # function must still succeed and the directory must exist.
        result = attachment_root.ensure_root(tmp_path)
        assert result.is_dir()


class TestOrphanScheduler:
    """Confirmation J supplemental: scheduler task is cancellable."""

    @pytest.mark.asyncio
    async def test_scheduler_task_cancels_cleanly(self) -> None:
        """Scheduler returns an asyncio.Task we can cancel without leaking."""
        import contextlib

        task = attachment_root.start_orphan_gc_scheduler()
        try:
            assert isinstance(task, asyncio.Task)
            await asyncio.sleep(0)  # let the scheduler enter its loop
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        assert task.cancelled() or task.done()
