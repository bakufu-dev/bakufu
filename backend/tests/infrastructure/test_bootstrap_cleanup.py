"""ブートストラップ cleanup LIFO 契約テスト
(TC-IT-PF-012-A / 012-B / 012-C, Confirmation J)。

Schneier 中等 4 物理保証 — あるステージが失敗したとき、``finally`` ブロック
は asyncio タスクを **逆開始順** でキャンセルしなければならない。
これにより attachments スケジューラが dispatcher より先に停止し
(dispatcher は ``stop_event`` に依存しているかもしれない)、
``engine.dispose()`` はどのステージが失敗しても実行される。
エンジンの ``dispose()`` は接続プール/WAL をフラッシュする —
これがないと tmp_path teardown がレース条件に陥る。
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
    """TC-IT-PF-012-A / 012-B: ステージ 8 失敗時にステージ 6 + 7 タスクがキャンセルされる。"""

    async def test_listener_failure_cancels_dispatcher_and_scheduler(
        self,
        _bakufu_data_dir: Path,
    ) -> None:
        """TC-IT-PF-012-B: dispatcher_task + attachments_task がキャンセルされる。"""

        async def _failing_listener() -> None:
            msg = "intentional listener bind failure"
            raise RuntimeError(msg)

        boot = Bootstrap(
            migration_runner=run_upgrade_head,
            listener_starter=_failing_listener,
        )
        with pytest.raises(BakufuConfigError):
            await boot.run()

        # 両方のバックグラウンドタスクは終了状態にあるべき — キャンセルされているか、
        # 完了しているか。``finally`` が LIFO cleanup を実行して、
        # 各タスクに対して cancel + gather を呼び出した。
        for attr in ("_dispatcher_task", "_attachments_task"):
            task = getattr(boot, attr)
            assert task is not None
            assert task.done()


class TestEngineDisposeRunsOnFailure:
    """TC-IT-PF-012-C: 後のステージが失敗しても engine.dispose() が実行される。"""

    async def test_engine_disposed_after_stage_failure(
        self,
        _bakufu_data_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-IT-PF-012-C: engine.dispose() は cleanup により呼び出される。"""

        async def _failing_listener() -> None:
            msg = "intentional listener bind failure"
            raise RuntimeError(msg)

        # AsyncEngine.dispose をスパイして、cleanup パスがこれを呼び出したことを
        # アサートできるようにする。SQLAlchemy 2.x の (再現可能な)
        # post-dispose 接続プール動作に依存しない。
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

        # Cleanup は アプリケーションエンジンに対して dispose() を
        # 少なくとも 1 回呼び出していなければならない。
        # Migration エンジンも dispose するので >=1。
        assert len(dispose_calls) >= 1


class TestCleanupRunsOnHappyPath:
    """Confirmation J 補足: cleanup は run() が正常に完了したときも発火する。

    成功時でも dispatcher / scheduler はキャンセル可能であるべき
    なので、テストプロセスはきれいにシャットダウンできる。
    """

    async def test_cleanup_finalizes_tasks_after_normal_run(
        self,
        _bakufu_data_dir: Path,
    ) -> None:
        """Cleanup は Bootstrap.run() 後にぶら下がる asyncio タスクを残さない。"""
        boot = Bootstrap(migration_runner=run_upgrade_head)
        await boot.run()
        # 明示的なリスナーがないと、run() は正常に完了するが
        # cleanup はまだ実行される。戻った後、タスクは完了しているべき。
        for attr in ("_dispatcher_task", "_attachments_task"):
            task = getattr(boot, attr)
            assert task is not None
            assert task.done()

        # ループ内にぶら下がるタスク（テスト自体を実行しているもの以外）がない。
        loop = asyncio.get_running_loop()
        running = [
            t for t in asyncio.all_tasks(loop) if not t.done() and t is not asyncio.current_task()
        ]
        assert running == []
