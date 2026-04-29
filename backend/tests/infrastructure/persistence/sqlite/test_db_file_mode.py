"""DB ファイルモード フォレンジック監査の結合テスト
(TC-IT-PF-002-A / 002-B / 002-C, REQ-PF-002-A, Schneier 致命1)。

Bootstrap stage 0 が ``umask 0o077`` を設定し、新規作成 SQLite ファイルは
``0o600`` を継承する。本テスト群は *フォレンジック* 契約を固定する:
直前の bakufu 実行が ``bakufu.db`` / ``bakufu.db-wal`` / ``bakufu.db-shm``
を ``0o644`` で残した場合、:func:`db_file_mode.verify_and_repair` 監査は:

* 異常を **検出** する（status=``"repaired"``）。
* 事後分析のため元のモードを **WARN ログ** に記録する。
* 次プロセスが安全になるよう ``0o600`` に **修復** する。
* **継続** する ── Fail Fast せず、オペレータが起動アボートで
  フォレンジック痕跡を失わないようにする。

Linux/macOS のみ。Windows は全ファイルに対し ``"windows_skip"`` を返す。
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

# POSIX モードビットが適用できないため、Windows ではモジュール全体をスキップ。
pytestmark = pytest.mark.skipif(
    platform.system() == "Windows",
    reason="POSIX file mode bits unavailable on Windows",
)


def _write_with_mode(path: Path, mode: int) -> None:
    """``path`` にプレースホルダファイルを作成し、``mode`` に chmod する。"""
    path.write_bytes(b"sqlite-test-stub")
    path.chmod(mode)


class TestNewFilesAlready0o600:
    """TC-IT-PF-002-A: 既に 0o600 のファイル → status ``"ok"``、WARN なし。"""

    def test_new_db_at_0o600_is_marked_ok(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-A: 0o600 で作成された bakufu.db は status='ok' を得る。"""
        _write_with_mode(tmp_path / "bakufu.db", SECURE_FILE_MODE)

        with caplog.at_level(logging.WARNING):
            results = verify_and_repair(tmp_path)

        assert results["bakufu.db"] == "ok"
        # クリーンなファイルでは WARN を発火させてはならない。
        warn_msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert all("DB file mode anomaly" not in m for m in warn_msgs)

    def test_post_audit_mode_unchanged(self, tmp_path: Path) -> None:
        """TC-IT-PF-002-A: クリーンファイルのモードは変更されない。"""
        target = tmp_path / "bakufu.db"
        _write_with_mode(target, SECURE_FILE_MODE)
        verify_and_repair(tmp_path)
        assert stat.S_IMODE(target.stat().st_mode) == SECURE_FILE_MODE


class TestExistingFileAt0o644Repairs:
    """TC-IT-PF-002-B: 0o644 ファイル → WARN + 0o600 へ chmod + status ``"repaired"``。"""

    def test_anomaly_detected_and_repaired(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-B: 0o644 の bakufu.db が 0o600 に修復される。"""
        target = tmp_path / "bakufu.db"
        _write_with_mode(target, 0o644)

        with caplog.at_level(logging.WARNING):
            results = verify_and_repair(tmp_path)

        assert results["bakufu.db"] == "repaired"
        assert stat.S_IMODE(target.stat().st_mode) == SECURE_FILE_MODE

    def test_warn_log_carries_original_mode(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-B: フォレンジック WARN は *元の* モードを記録しなければならない。"""
        _write_with_mode(tmp_path / "bakufu.db", 0o644)

        with caplog.at_level(logging.WARNING):
            verify_and_repair(tmp_path)

        warn_msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        # フォレンジックメッセージは (a) ファイル名を記載し、(b) プロセス監査ログと
        # 突き合わせるため元のモードを 8 進数で含み、(c) umask-0o077 の
        # 強制ギャップを記述しなければならない。
        assert any("DB file mode anomaly" in m for m in warn_msgs)
        assert any("0o644" in m for m in warn_msgs)
        assert any("umask" in m for m in warn_msgs)

    def test_repair_does_not_block_startup(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-B: フォレンジックポリシーは「継続せよ、Fail Fast するな」。"""
        _write_with_mode(tmp_path / "bakufu.db", 0o644)
        # 関数が（raise せず）status dict を返すことが、起動がブロックされない証拠そのもの。
        with caplog.at_level(logging.WARNING):
            results = verify_and_repair(tmp_path)
        assert isinstance(results, dict)
        assert results["bakufu.db"] in {"repaired", "repair_failed"}


class TestWalAndShmFilesAuditedToo:
    """TC-IT-PF-002-C: bakufu.db-wal と bakufu.db-shm も同じ監査に従う。"""

    def test_wal_at_0o644_is_repaired(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-C: bakufu.db-wal の修復経路。"""
        wal = tmp_path / "bakufu.db-wal"
        _write_with_mode(wal, 0o644)

        with caplog.at_level(logging.WARNING):
            results = verify_and_repair(tmp_path)

        assert results["bakufu.db-wal"] == "repaired"
        assert stat.S_IMODE(wal.stat().st_mode) == SECURE_FILE_MODE

    def test_shm_at_0o644_is_repaired(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-C: bakufu.db-shm の修復経路。"""
        shm = tmp_path / "bakufu.db-shm"
        _write_with_mode(shm, 0o644)

        with caplog.at_level(logging.WARNING):
            results = verify_and_repair(tmp_path)

        assert results["bakufu.db-shm"] == "repaired"
        assert stat.S_IMODE(shm.stat().st_mode) == SECURE_FILE_MODE

    def test_absent_wal_and_shm_are_marked_absent(self, tmp_path: Path) -> None:
        """TC-IT-PF-002-C: upgrade 直後は WAL/SHM が無い場合がある ── status='absent'。"""
        # メイン DB のみ存在。WAL/SHM は最初の書き込みでマテリアライズされる。
        _write_with_mode(tmp_path / "bakufu.db", SECURE_FILE_MODE)

        results = verify_and_repair(tmp_path)
        assert results["bakufu.db"] == "ok"
        assert results["bakufu.db-wal"] == "absent"
        assert results["bakufu.db-shm"] == "absent"

    def test_three_files_audited_independently(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-IT-PF-002-C: 3 ファイルそれぞれが独自の status エントリを得る。"""
        for name in DB_FILE_NAMES:
            _write_with_mode(tmp_path / name, 0o644)

        with caplog.at_level(logging.WARNING):
            results = verify_and_repair(tmp_path)

        assert set(results.keys()) == set(DB_FILE_NAMES)
        for name in DB_FILE_NAMES:
            assert results[name] == "repaired"
            assert stat.S_IMODE((tmp_path / name).stat().st_mode) == SECURE_FILE_MODE


class TestRepairFailureDoesNotRaise:
    """REQ-PF-002-A 継続性: chmod 失敗は ERROR ログで記録され、決して raise しない。"""

    def test_chmod_failure_is_swallowed(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """REQ-PF-002-A: chmod が OSError を投げる → status='repair_failed'、raise なし。"""
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
        # ops ダッシュボードがアラートできるよう、監査は失敗を ERROR レベルで表面化する。
        error_msgs = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
        assert any("DB file mode repair failed" in m for m in error_msgs)


class TestDbFileModeBootstrapIntegration:
    """Bootstrap stage 3 が監査を配線する。モード辞書が INFO ログに現れる。"""

    @pytest.mark.asyncio
    async def test_bootstrap_logs_mode_audit_results(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """REQ-PF-002-A: Bootstrap.run() が 'DB file mode audit:' INFO 行を出力する。"""
        from bakufu.infrastructure.bootstrap import Bootstrap
        from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head

        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
        boot = Bootstrap(migration_runner=run_upgrade_head)
        with caplog.at_level(logging.INFO):
            await boot.run()

        info_msgs = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
        assert any("DB file mode audit:" in m for m in info_msgs)


# レポート集約時にカバレッジが正しいソースファイルにテストを紐付けるよう、
# モジュールを再エクスポートする。
_ = db_file_mode
