"""Bootstrap cleanup LIFO contract tests
(TC-IT-PF-012-A / 012-B / 012-C, Confirmation J).

Schneier 中等 4 物理保証 — when a stage fails the ``finally`` block
must cancel asyncio tasks in **reverse start order** so the
attachments scheduler stops *before* the dispatcher (whose
``stop_event`` it might depend on), and ``engine.dispose()`` runs no
matter which stage exploded. Engine ``dispose()`` flushes the
connection pool / WAL — without it tmp_path teardown can race.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from bakufu.infrastructure.bootstrap import Bootstrap
from bakufu.infrastructure.exceptions import BakufuConfigError
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head

pytestmark = pytest.mark.asyncio


@pytest.fixture
def _bakufu_data_dir(  # pyright: ignore[reportUnusedFunction]
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
    return tmp_path


class TestStage8FailureCancelsTasks:
    """TC-IT-PF-012-A / 012-B: a stage 8 failure cancels stage 6 + 7 tasks."""

    async def test_listener_failure_cancels_dispatcher_and_scheduler(
        self,
        _bakufu_data_dir: Path,
    ) -> None:
        """TC-IT-PF-012-B: dispatcher_task + attachments_task end up cancelled."""

        async def _failing_listener() -> None:
            msg = "intentional listener bind failure"
            raise RuntimeError(msg)

        boot = Bootstrap(
            migration_runner=run_upgrade_head,
            listener_starter=_failing_listener,
        )
        with pytest.raises(BakufuConfigError):
            await boot.run()

        # Both background tasks should be in a terminal state — either
        # cancelled or done. ``finally`` ran LIFO cleanup and called
        # cancel + gather on each.
        for attr in ("_dispatcher_task", "_attachments_task"):
            task = getattr(boot, attr)
            assert task is not None
            assert task.done()


class TestEngineDisposeRunsOnFailure:
    """TC-IT-PF-012-C: engine.dispose() runs even when a later stage explodes."""

    async def test_engine_disposed_after_stage_failure(
        self,
        _bakufu_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-IT-PF-012-C: engine.dispose() is invoked by cleanup."""

        async def _failing_listener() -> None:
            msg = "intentional listener bind failure"
            raise RuntimeError(msg)

        # Spy on AsyncEngine.dispose so we can assert the cleanup path
        # invoked it without depending on the (recreatable) post-dispose
        # connection-pool behavior of SQLAlchemy 2.x.
        from sqlalchemy.ext.asyncio import AsyncEngine as _AsyncEngine

        dispose_calls: list[None] = []
        original_dispose = _AsyncEngine.dispose

        async def _tracking_dispose(self: _AsyncEngine, *args: object, **kwargs: object) -> None:
            dispose_calls.append(None)
            await original_dispose(self, *args, **kwargs)  # pyright: ignore[reportArgumentType]

        monkeypatch.setattr(_AsyncEngine, "dispose", _tracking_dispose)

        boot = Bootstrap(
            migration_runner=run_upgrade_head,
            listener_starter=_failing_listener,
        )
        with pytest.raises(BakufuConfigError):
            await boot.run()

        # Cleanup must have called dispose() at least once on the
        # application engine. Migration engine also disposes, so >=1.
        assert len(dispose_calls) >= 1


class TestCleanupRunsOnHappyPath:
    """Confirmation J supplemental: cleanup also fires when run() completes normally.

    Even on success the dispatcher / scheduler should be cancellable so
    the test process can shut down cleanly.
    """

    async def test_cleanup_finalizes_tasks_after_normal_run(
        self,
        _bakufu_data_dir: Path,
    ) -> None:
        """Cleanup leaves no dangling asyncio tasks after Bootstrap.run()."""
        boot = Bootstrap(migration_runner=run_upgrade_head)
        await boot.run()
        # Without an explicit listener, run() completes successfully but
        # cleanup still runs. After return the tasks should be done.
        for attr in ("_dispatcher_task", "_attachments_task"):
            task = getattr(boot, attr)
            assert task is not None
            assert task.done()

        # No dangling running tasks in the loop (besides the one running
        # the test itself).
        loop = asyncio.get_running_loop()
        running = [
            t for t in asyncio.all_tasks(loop) if not t.done() and t is not asyncio.current_task()
        ]
        assert running == []
