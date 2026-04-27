"""REQ-PF-002-A: forensic DB-file-mode check + WARN + repair.

Bootstrap stage 0 sets ``os.umask(0o077)`` so any **new** SQLite file
inherits ``0o600``. That covers the happy path going forward, but
not the forensic question: did an earlier bakufu run (started with
the OS-default ``0o022`` umask) leave behind ``bakufu.db`` /
``bakufu.db-wal`` / ``bakufu.db-shm`` at ``0o644``? If so, those
files were world-readable for the duration of that run — operators
need to know.

Policy (Schneier 致命1):

1. **Detect** any of the three SQLite files whose POSIX mode bits
   differ from ``0o600``.
2. **WARN-log** with the original mode so post-incident analysis
   can correlate against process audit logs.
3. **Repair** by ``chmod`` to ``0o600`` so the next run is safe.
4. **Continue** rather than ``Fail Fast`` — refusing to start would
   force operators into manual ``chmod`` work that loses the
   forensic trail. The WARN line is the trail.

POSIX-only. Windows ACLs are out of scope and the function returns
``windows_skip`` for every file there.
"""

from __future__ import annotations

import logging
import platform
import stat
from pathlib import Path
from typing import Final, Literal

logger = logging.getLogger(__name__)

# The three SQLite files that bakufu manages. WAL / SHM are created
# lazily by SQLite at first write so they may legitimately be absent
# right after Alembic ``upgrade``.
DB_FILE_NAMES: Final[tuple[str, ...]] = (
    "bakufu.db",
    "bakufu.db-wal",
    "bakufu.db-shm",
)
SECURE_FILE_MODE: Final[int] = 0o600


FileModeStatus = Literal[
    "ok",  # mode == 0o600
    "absent",  # file does not exist (legitimate for WAL/SHM pre-write)
    "repaired",  # mode != 0o600 → chmod succeeded
    "repair_failed",  # mode != 0o600 → chmod raised
    "windows_skip",  # Windows ACL territory, no-op
]


def verify_and_repair(data_dir: Path) -> dict[str, FileModeStatus]:
    """Audit + repair DB file modes (Schneier 致命1).

    Args:
        data_dir: Resolved BAKUFU_DATA_DIR.

    Returns:
        Mapping of filename → status. Bootstrap stage logs the dict so
        the audit trail survives independently of the per-file WARN.
    """
    if platform.system() == "Windows":
        return dict.fromkeys(DB_FILE_NAMES, "windows_skip")

    results: dict[str, FileModeStatus] = {}
    for fname in DB_FILE_NAMES:
        results[fname] = _check_one(data_dir / fname)
    return results


def _check_one(path: Path) -> FileModeStatus:
    """Inspect one file, WARN + repair if mode is not 0o600."""
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
