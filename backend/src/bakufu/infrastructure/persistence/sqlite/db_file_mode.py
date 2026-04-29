"""REQ-PF-002-A: DB ファイルモードの forensic チェック + WARN + 修復。

Bootstrap stage 0 で ``os.umask(0o077)`` を設定するため、**新規** に作られる
SQLite ファイルは ``0o600`` を継承する。これは以降の正常系をカバーするが、
forensic な疑問は別問題: 過去の bakufu 実行（OS 既定の ``0o022`` umask で
起動された）が ``bakufu.db`` / ``bakufu.db-wal`` / ``bakufu.db-shm`` を
``0o644`` のまま残していなかったか？ もし残っていたなら、それらのファイルは
その実行期間中 world-readable だったということで、運用者は把握する必要がある。

ポリシー（Schneier 致命1）:

1. 3 つの SQLite ファイルのうち、POSIX モードビットが ``0o600`` と
   異なるものを **検出** する。
2. インシデント後の解析でプロセス監査ログと突き合わせられるよう、
   元のモードと共に **WARN ログ** を出す。
3. 次回の実行が安全になるよう、``chmod`` で **修復** して ``0o600`` にする。
4. ``Fail Fast`` ではなく **継続** する — 起動を拒否すると運用者を
   forensic の手がかりを失う手作業の ``chmod`` に追い込む。WARN 行こそが
   その手がかりとなる。

POSIX のみ。Windows ACL はスコープ外で、すべてのファイルに対して
``windows_skip`` を返す。
"""

from __future__ import annotations

import logging
import platform
import stat
from pathlib import Path
from typing import Final, Literal

logger = logging.getLogger(__name__)

# bakufu が管理する 3 つの SQLite ファイル。WAL / SHM は最初の書き込み時に
# SQLite が遅延的に作成するため、Alembic ``upgrade`` 直後には正当に
# 存在しないことがある。
DB_FILE_NAMES: Final[tuple[str, ...]] = (
    "bakufu.db",
    "bakufu.db-wal",
    "bakufu.db-shm",
)
SECURE_FILE_MODE: Final[int] = 0o600


FileModeStatus = Literal[
    "ok",  # mode == 0o600
    "absent",  # ファイルが存在しない（書き込み前の WAL/SHM では正当）
    "repaired",  # mode != 0o600 → chmod 成功
    "repair_failed",  # mode != 0o600 → chmod が例外を送出
    "windows_skip",  # Windows ACL の領域、no-op
]


def verify_and_repair(data_dir: Path) -> dict[str, FileModeStatus]:
    """DB ファイルモードの監査 + 修復を行う（Schneier 致命1）。

    Args:
        data_dir: 解決済みの BAKUFU_DATA_DIR。

    Returns:
        ファイル名 → ステータスのマッピング。Bootstrap stage がこの dict を
        ログに出すので、ファイルごとの WARN とは独立に監査証跡が残る。
    """
    if platform.system() == "Windows":
        return dict.fromkeys(DB_FILE_NAMES, "windows_skip")

    results: dict[str, FileModeStatus] = {}
    for fname in DB_FILE_NAMES:
        results[fname] = _check_one(data_dir / fname)
    return results


def _check_one(path: Path) -> FileModeStatus:
    """1 ファイルを検査し、モードが 0o600 でなければ WARN + 修復する。"""
    try:
        st = path.stat()
    except FileNotFoundError:
        return "absent"
    except OSError as exc:
        logger.warning(
            "[WARN] DB file mode check could not stat %s: %r — skipping",
            path,
            exc,
        )
        return "repair_failed"

    current = stat.S_IMODE(st.st_mode)
    if current == SECURE_FILE_MODE:
        return "ok"

    logger.warning(
        "[WARN] DB file mode anomaly: %s has mode 0o%03o "
        "(expected 0o%03o); possible historical exposure prior to "
        "umask 0o077 enforcement. Repairing to 0o%03o.\n"
        "Next: Inspect the audit_log + structured logs from the "
        "originating run for evidence of read access by other OS "
        "users; rotate any secrets that may have leaked while the "
        "file was world-readable; confirm the umask 0o077 enforcement "
        "is in effect for all bakufu launchers (systemd unit / "
        "launchd plist / docker entrypoint).",
        path,
        current,
        SECURE_FILE_MODE,
        SECURE_FILE_MODE,
    )
    try:
        path.chmod(SECURE_FILE_MODE)
    except OSError as exc:
        logger.error(
            "[ERROR] DB file mode repair failed for %s: %r — "
            "continuing without fatal exit per REQ-PF-002-A.\n"
            "Next: Manually run `chmod 0600 %s` after stopping "
            "bakufu; verify the OS user owns the file (otherwise "
            "container / sudo state mismatch is the root cause).",
            path,
            exc,
            path,
        )
        return "repair_failed"
    return "repaired"


__all__ = [
    "DB_FILE_NAMES",
    "SECURE_FILE_MODE",
    "FileModeStatus",
    "verify_and_repair",
]
