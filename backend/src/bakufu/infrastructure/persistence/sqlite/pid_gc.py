"""Bootstrap stage 4 のオーファン プロセス ガベージ コレクション（§確定 E）。

bakufu の前回実行がサブプロセス（claude / codex 等）ツリーを生かしたままにする
場合がある — クラッシュ、親プロセスの SIGKILL、OS の特殊な状態など。本モジュール
は起動時に :class:`PidRegistryRow` エントリをスイープし、各行を分類して、行のみを
DELETE するか（PID が消失している、または無関係なプロセスに再利用されている）、
子孫プロセスを kill してから DELETE するかを決める。

分類ロジック
------------
各行はオリジナルの ``psutil.Process.create_time()`` から取得したスナップショット
``started_at`` を保持する。このタイムスタンプが **PID 衝突ガード** となる: 別の
プロセスが同じ PID にたまたま入った場合、``create_time()`` が一致しないため
kill してはならない。

| psutil 結果                            | 分類             | アクション                       |
|----------------------------------------|------------------|----------------------------------|
| ``NoSuchProcess``                      | ``absent``       | 行のみ DELETE                    |
| プロセス存在 + ``create_time`` 一致    | ``orphan_kill``  | 子孫を kill + DELETE             |
| プロセス存在 + ``create_time`` 不一致  | ``protected``    | 行のみ DELETE（PID 再利用）      |
| ``AccessDenied``                       | （分類なし）     | WARN、行は次回 GC に残す         |
"""

from __future__ import annotations

import logging
import signal
import time
from datetime import datetime
from typing import Literal

import psutil
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bakufu.infrastructure.persistence.sqlite.tables.pid_registry import (
    PidRegistryRow,
)

logger = logging.getLogger(__name__)

# Confirmation E: SIGKILL の前に与える SIGTERM 猶予。
SIGTERM_GRACE_SECONDS: int = 5

PidClassification = Literal["orphan_kill", "protected", "absent"]


async def run_startup_gc(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    """``bakufu_pid_registry`` をスイープして OS に対して整合性を取る。

    Args:
        session_factory: registry 行の読み取り／DELETE に使用する AsyncSession
            ファクトリ。

    Returns:
        ``killed`` / ``protected`` / ``absent`` / ``access_denied`` のキーを持つ
        カウント辞書。Bootstrap が stage-4 完了ログに含められる。
    """
    counts = {"killed": 0, "protected": 0, "absent": 0, "access_denied": 0}

    async with session_factory() as session:
        rows = (await session.execute(select(PidRegistryRow))).scalars().all()

    for row in rows:
        try:
            classification = _classify_row(row.pid, row.started_at)
        except psutil.AccessDenied:
            logger.warning(
                "[WARN] pid_registry GC: psutil.AccessDenied for pid=%d, retry next cycle",
                row.pid,
            )
            counts["access_denied"] += 1
            continue

        if classification == "orphan_kill":
            _kill_descendants(row.pid)
            counts["killed"] += 1
        elif classification == "protected":
            counts["protected"] += 1
        else:  # "absent"
            counts["absent"] += 1

        async with session_factory() as session, session.begin():
            await session.execute(
                delete(PidRegistryRow).where(PidRegistryRow.pid == row.pid),
            )

    return counts


def _classify_row(pid: int, recorded_started_at: datetime) -> PidClassification:
    """記録された ``started_at`` と現在のプロセスを比較する。

    Raises:
        psutil.AccessDenied: 上位に伝播するため、呼び元は当該行を WARN ログに
            残し DELETE をスキップできる（次回 GC で再試行）。
    """
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return "absent"

    try:
        live_create_time = proc.create_time()
    except psutil.NoSuchProcess:
        return "absent"
    except psutil.AccessDenied:
        raise

    # ``psutil.Process.create_time`` は POSIX 秒を返す。一方こちらは tz-aware の
    # datetime を保存している。psutil バージョン間の丸めノイズを吸収するため
    # ミリ秒単位の許容で比較する。
    recorded_seconds = recorded_started_at.timestamp()
    if abs(live_create_time - recorded_seconds) > 0.001:
        return "protected"
    return "orphan_kill"


def _kill_descendants(pid: int) -> None:
    """全子孫に SIGTERM → 5 秒待機 → 残存プロセスに SIGKILL。

    ``psutil.Process.children(recursive=True)`` を使い、サブツリー全体
    （claude → codex → 孫プロセス）を刈り取る — 直接子のみではない。
    """
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return

    try:
        descendants = proc.children(recursive=True)
    except psutil.NoSuchProcess:
        return

    targets = [proc, *descendants]

    for target in targets:
        try:
            target.send_signal(signal.SIGTERM)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            logger.warning(
                "[WARN] pid_registry GC: SIGTERM failed for pid=%s: %r",
                getattr(target, "pid", "?"),
                exc,
            )

    deadline = time.monotonic() + SIGTERM_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not any(t.is_running() for t in targets):
            return
        time.sleep(0.1)

    for target in targets:
        if not target.is_running():
            continue
        try:
            target.send_signal(signal.SIGKILL)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:  # pragma: no cover
            logger.warning(
                "[WARN] pid_registry GC: SIGKILL failed for pid=%s: %r",
                getattr(target, "pid", "?"),
                exc,
            )


__all__ = [
    "SIGTERM_GRACE_SECONDS",
    "PidClassification",
    "run_startup_gc",
]
