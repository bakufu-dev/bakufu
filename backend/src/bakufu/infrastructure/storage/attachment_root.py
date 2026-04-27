"""Attachments FS root + 24h orphan-GC scheduler skeleton.

Bootstrap stage 5 calls :func:`ensure_root` to materialize the
``<DATA_DIR>/attachments/`` directory with mode ``0o700`` (POSIX).
Stage 7 calls :func:`start_orphan_gc_scheduler` to launch the
periodic GC asyncio task.

The actual GC (matching FS files against ``Conversation`` /
``Deliverable`` references and deleting orphans) lives in the
``feature/attachment-store`` PR. Here we lay down the skeleton so
Bootstrap's stage list is complete on day 1 and the cleanup contract
in Confirmation J has a real ``Task`` to cancel.
"""

from __future__ import annotations

import asyncio
import logging
import platform
from pathlib import Path

from bakufu.infrastructure.exceptions import BakufuConfigError

logger = logging.getLogger(__name__)

ATTACHMENTS_SUBDIR: str = "attachments"
ATTACHMENTS_MODE: int = 0o700

# 24 hours per docs/features/persistence-foundation/requirements.md REQ-PF-009.
ORPHAN_GC_INTERVAL_SECONDS: int = 24 * 60 * 60


def ensure_root(data_dir: Path) -> Path:
    """Create the attachments directory and enforce ``0700`` (POSIX).

    Args:
        data_dir: The resolved BAKUFU_DATA_DIR.

    Raises:
        BakufuConfigError: ``msg_id='MSG-PF-003'`` if mkdir or chmod
            fails. Bootstrap exits non-zero.
    """
    root = data_dir / ATTACHMENTS_SUBDIR
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BakufuConfigError(
            msg_id="MSG-PF-003",
            message=(
                f"[FAIL] Attachment FS root initialization failed at "
                f"{root}: {exc!r}"
            ),
        ) from exc

    if platform.system() != "Windows":
        try:
            root.chmod(ATTACHMENTS_MODE)
        except OSError as exc:
            raise BakufuConfigError(
                msg_id="MSG-PF-003",
                message=(
                    f"[FAIL] Attachment FS root initialization failed at "
                    f"{root}: chmod 0700 failed ({exc!r})"
                ),
            ) from exc

    return root


def start_orphan_gc_scheduler() -> asyncio.Task[None]:
    """Schedule the 24-hour orphan-GC sweep.

    Returns:
        The asyncio task wrapping the loop. Bootstrap stores it for
        LIFO cleanup.

    The actual sweep logic (matching FS files against the
    ``Conversation`` / ``Deliverable`` Aggregate references) lives in
    ``feature/attachment-store`` and replaces :func:`_run_loop` there.
    """
    return asyncio.create_task(_run_loop())


async def _run_loop() -> None:
    """Periodic sweep loop. No-op skeleton in this PR."""
    while True:
        # The body is intentionally empty until ``feature/attachment-store``
        # provides the sweep implementation. Sleeping the full interval
        # keeps the asyncio task alive for Bootstrap's cancel path.
        try:
            await asyncio.sleep(ORPHAN_GC_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info(
                "[INFO] Attachment orphan GC scheduler cancelled."
            )
            raise


__all__ = [
    "ATTACHMENTS_MODE",
    "ATTACHMENTS_SUBDIR",
    "ORPHAN_GC_INTERVAL_SECONDS",
    "ensure_root",
    "start_orphan_gc_scheduler",
]
