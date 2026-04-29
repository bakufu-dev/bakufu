"""Attachment FS root 統合テスト
(TC-IT-PF-011 / 029, TC-UT-PF-030)。

Confirmation E + REQ-PF-009: ``ensure_root`` が POSIX 上で
``0o700`` でディレクトリを作成。``start_orphan_gc_scheduler`` は
きれいにキャンセルできる asyncio.Task を返す。
"""

from __future__ import annotations

import asyncio
import platform
from pathlib import Path

import pytest
from bakufu.infrastructure.exceptions import BakufuConfigError
from bakufu.infrastructure.storage import attachment_root


class TestEnsureRootCreatesDirectory:
    """TC-IT-PF-011: POSIX 上で 0o700 でディレクトリを作成。"""

    def test_creates_attachments_subdir(self, tmp_path: Path) -> None:
        """TC-IT-PF-011: 呼び出し後に <DATA_DIR>/attachments が存在。"""
        result = attachment_root.ensure_root(tmp_path)
        assert result == tmp_path / "attachments"
        assert result.is_dir()

    @pytest.mark.skipif(platform.system() == "Windows", reason="POSIX 限定モードビット")
    def test_directory_mode_is_0o700(self, tmp_path: Path) -> None:
        """TC-IT-PF-011: chmod 0o700 を強制 (POSIX のみ)。"""
        result = attachment_root.ensure_root(tmp_path)
        mode = result.stat().st_mode & 0o777
        assert mode == 0o700

    def test_idempotent_when_directory_exists(self, tmp_path: Path) -> None:
        """TC-IT-PF-011: 既存ディレクトリで再実行は no-op。"""
        first = attachment_root.ensure_root(tmp_path)
        second = attachment_root.ensure_root(tmp_path)
        assert first == second
        assert first.is_dir()


class TestEnsureRootRejectsUnwritableParent:
    """TC-IT-PF-029: 親ディレクトリ読み取り専用 → BakufuConfigError(MSG-PF-003)。"""

    @pytest.mark.skipif(platform.system() == "Windows", reason="POSIX 限定モードビット")
    def test_unwritable_parent_raises(self, tmp_path: Path) -> None:
        """TC-IT-PF-029: 親が 0o500 → mkdir 失敗 → MSG-PF-003。"""
        # tmp_path を読み取り専用に (読み取り + 実行、書き込みなし)。
        tmp_path.chmod(0o500)
        try:
            with pytest.raises(BakufuConfigError) as excinfo:
                attachment_root.ensure_root(tmp_path)
            assert excinfo.value.msg_id == "MSG-PF-003"
            assert "Attachment FS root initialization failed" in excinfo.value.message
        finally:
            # tmp cleanup が動作するよう復元。
            tmp_path.chmod(0o700)


class TestWindowsBranch:
    """TC-UT-PF-030: Windows で ``os.chmod`` をスキップ。"""

    def test_windows_skips_chmod(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-UT-PF-030: platform=Windows → ensure_root が chmod なしで成功。"""
        monkeypatch.setattr("platform.system", lambda: "Windows")
        # 実際の Windows には chmod 呼び出しはないが、POSIX runner では
        # テストがプラットフォームブランチがスキップを選択することを検証 —
        # 関数はまだ成功し、ディレクトリが存在する必要がある。
        result = attachment_root.ensure_root(tmp_path)
        assert result.is_dir()


class TestOrphanScheduler:
    """Confirmation J 補足: スケジューラタスクはキャンセル可能。"""

    @pytest.mark.asyncio
    async def test_scheduler_task_cancels_cleanly(self) -> None:
        """スケジューラがリークなしでキャンセルできる asyncio.Task を返す。"""
        import contextlib

        task = attachment_root.start_orphan_gc_scheduler()
        try:
            assert isinstance(task, asyncio.Task)
            await asyncio.sleep(0)  # スケジューラがループに入るのを待つ
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        assert task.cancelled() or task.done()
