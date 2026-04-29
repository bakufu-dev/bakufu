"""Outbox ディスパッチャ（スケルトン、§確定 K）。

このディスパッチャは Schneier 中等 3 の方針により、本 PR では意図的に
**スケルトンのみ** とする。実ハンドラは後続の ``feature/{event-kind}-handler``
PR で導入される。本モジュールが *提供する* のは:

* ポーリング ループ構造（1 秒間隔、バッチ 50、5 分の DISPATCHING リカバリ、
  5 回試行のデッドレター上限）。
* Confirmation K Fail Loud 警告 — Bootstrap 起動時診断 + サイクル毎の
  empty-registry WARN + 100 行バックログ WARN。
* Bootstrap LIFO クリーンアップがバックグラウンドタスクをキャンセルできるよう
  クリーンな ``stop()`` 経路。

実 SELECT / UPDATE SQL はハンドラが存在するようになった時点で投入する。ここでは
表面を最小限に保ち、後続 PR で :meth:`_dispatch_one` の本体を埋めるだけで済む
ようにする。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bakufu.infrastructure.persistence.sqlite.outbox import handler_registry
from bakufu.infrastructure.persistence.sqlite.tables.outbox import OutboxRow

logger = logging.getLogger(__name__)

# Confirmation K — ``outbox.md`` を参照。
DEFAULT_BATCH_SIZE: Final = 50
DEFAULT_POLL_INTERVAL_SECONDS: Final = 1.0
DEFAULT_DISPATCHING_RECOVERY_MINUTES: Final = 5
DEFAULT_MAX_ATTEMPTS: Final = 5
BACKLOG_WARN_THRESHOLD: Final = 100


class OutboxDispatcher:
    """``domain_event_outbox`` 行のためのバックグラウンド ディスパッチャ。

    Bootstrap stage 6 がインスタンスを生成し :meth:`run` を asyncio タスクと
    してスケジュールする。Bootstrap LIFO クリーンアップ（Confirmation J）は
    シャットダウン時にループを抜けるため :meth:`stop` を呼ぶ。
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        dispatching_recovery_minutes: int = (DEFAULT_DISPATCHING_RECOVERY_MINUTES),
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._session_factory = session_factory
        self._batch_size = batch_size
        self._poll_interval = poll_interval_seconds
        self._dispatching_recovery_minutes = dispatching_recovery_minutes
        self._max_attempts = max_attempts
        self._stop_event = asyncio.Event()
        # 空のハンドラ レジストリが pending 行を見つけたことを既に警告済みかどうか
        # を追跡する。ポーリング サイクル毎にログが溢れるのを避ける（Confirmation K
        # 行 2）。
        self._empty_registry_warned: bool = False
        # バックログ WARN のスロットリング。``None`` は「まだ警告していない」を意味し、
        # 初回トリガで即座に警告して実際の ``loop.time()`` 値を記録する。以前の
        # デフォルト ``0.0``（BUG-PF-003）は OS モノトニック クロックとプロセス開始時
        # に衝突していた: ``loop.time() - 0.0`` は常に巨大値だが、再起動後にループへ
        # 再入したばかりの新規プロセスではクロックが 300s を下回り、最初の 5 分間の
        # 警告がサイレントに飲み込まれることがあった。
        self._backlog_last_warn_monotonic: float | None = None

    async def run(self) -> None:
        """ポーリング ループ。Bootstrap から ``asyncio.create_task`` で呼ぶ。

        ハンドラがまだ登録されていないため、ループは意図的に単純である — 行処理は
        まだ行わない。それでも各 tick で empty-registry / backlog の Fail Loud
        チェックは走るため、ハンドラが投入された後も同じテレメトリをオペレータが
        確認できる。
        """
        while not self._stop_event.is_set():
            try:
                await self._poll_once()
            except Exception:  # pragma: no cover — defensive
                # ディスパッチャはポーリング本体で死んではならない。ログを残し
                # 継続する。次のサイクルでリトライされる。
                logger.exception(
                    "[ERROR] Outbox dispatcher poll cycle raised; continuing to next cycle"
                )
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._poll_interval,
                )
            except TimeoutError:
                continue

    async def stop(self) -> None:
        """次のイテレーションで終了するようポーリング ループへシグナルを送る。"""
        self._stop_event.set()

    async def _poll_once(self) -> None:
        """単一のポーリング サイクル: pending 行をカウントし WARN を発火する。

        後続 PR ではここに :meth:`_dispatch_one` 経由のバッチ処理を追加する。
        現スケルトンではカウントを露出するだけで、Confirmation K の起動 / サイクル毎
        / バックログ警告が実データに対して発火するようにしている。
        """
        async with self._session_factory() as session:
            stmt = select(OutboxRow).where(OutboxRow.status == "PENDING")
            result = await session.execute(stmt)
            pending = result.scalars().all()

        pending_count = len(pending)
        registry_size = handler_registry.size()

        # Confirmation K 行 2: registry が空かつ pending 行がある場合。
        if pending_count > 0 and registry_size == 0:
            if not self._empty_registry_warned:
                logger.warning(
                    "[WARN] Outbox has %d pending events but handler_registry is empty.",
                    pending_count,
                )
                self._empty_registry_warned = True
        else:
            # ハンドラが現れるかキューが解消したら、状況が悪化した際の WARN 再発火を
            # 許可する。
            self._empty_registry_warned = False

        # Confirmation K 行 3: バックログ閾値（>100 行）。
        if pending_count > BACKLOG_WARN_THRESHOLD:
            now = asyncio.get_running_loop().time()
            five_minutes_seconds = 300.0
            should_warn = (
                self._backlog_last_warn_monotonic is None
                or now - self._backlog_last_warn_monotonic > five_minutes_seconds
            )
            if should_warn:
                logger.warning(
                    "[WARN] Outbox PENDING count=%d > %d. Inspect with bakufu admin list-pending.",
                    pending_count,
                    BACKLOG_WARN_THRESHOLD,
                )
                self._backlog_last_warn_monotonic = now


__all__ = [
    "BACKLOG_WARN_THRESHOLD",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_DISPATCHING_RECOVERY_MINUTES",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "OutboxDispatcher",
]
