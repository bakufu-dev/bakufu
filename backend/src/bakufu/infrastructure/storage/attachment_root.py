"""添付ファイル FS ルート + 24 時間オーファン GC スケジューラの骨組み。

Bootstrap Stage 5 が :func:`ensure_root` を呼び、``<DATA_DIR>/attachments/``
ディレクトリをモード ``0o700``（POSIX）で実体化する。Stage 7 が
:func:`start_orphan_gc_scheduler` を呼び、定期 GC の asyncio タスクを
起動する。

実際の GC 処理（FS 上のファイルを ``Conversation`` /
``Deliverable`` の参照と突き合わせ、孤児を削除する処理）は
``feature/attachment-store`` PR で実装される。本 PR では骨組みのみを
配置し、Bootstrap の Stage 一覧を初日から完備しつつ、Confirmation J の
クリーンアップ契約が cancel 対象として実体ある ``Task`` を持てるように
する。
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

# docs/features/persistence-foundation/requirements.md REQ-PF-009 に
# 従い 24 時間。
ORPHAN_GC_INTERVAL_SECONDS: int = 24 * 60 * 60


def ensure_root(data_dir: Path) -> Path:
    """添付ファイル用ディレクトリを作成し、``0700``（POSIX）を強制する。

    Args:
        data_dir: 解決済みの BAKUFU_DATA_DIR。

    Raises:
        BakufuConfigError: ``msg_id='MSG-PF-003'``。mkdir または
            chmod が失敗した場合。Bootstrap は非ゼロ終了する。
    """
    root = data_dir / ATTACHMENTS_SUBDIR
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BakufuConfigError(
            msg_id="MSG-PF-003",
            message=(f"[FAIL] Attachment FS root initialization failed at {root}: {exc!r}"),
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
    """24 時間ごとのオーファン GC スイープをスケジュールする。

    Returns:
        ループをラップする asyncio タスク。Bootstrap は LIFO クリーン
        アップのために本タスクを保持する。

    実際のスイープロジック（FS 上のファイルを ``Conversation`` /
    ``Deliverable`` Aggregate の参照と突き合わせる処理）は
    ``feature/attachment-store`` で実装され、本ファイルの
    :func:`_run_loop` を置き換える。
    """
    return asyncio.create_task(_run_loop())


async def _run_loop() -> None:
    """定期スイープループ。本 PR では何もしない骨組み実装。"""
    while True:
        # ``feature/attachment-store`` がスイープ実装を提供するまで本体は
        # 意図的に空のまま。インターバル全体スリープすることで asyncio
        # タスクを生かしておき、Bootstrap の cancel 経路が機能するように
        # する。
        try:
            await asyncio.sleep(ORPHAN_GC_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("[INFO] Attachment orphan GC scheduler cancelled.")
            raise


__all__ = [
    "ATTACHMENTS_MODE",
    "ATTACHMENTS_SUBDIR",
    "ORPHAN_GC_INTERVAL_SECONDS",
    "ensure_root",
    "start_orphan_gc_scheduler",
]
