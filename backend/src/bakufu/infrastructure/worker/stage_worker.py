"""StageWorker — asyncio Queue + Semaphore による Stage 実行コンシューマ（REQ-ME-006）。

Bootstrap Stage 6.5 として登録し、Outbox Dispatcher（Stage 6）と
FastAPI listener（Stage 8）の間に起動する（§確定 C）。
BAKUFU_MAX_CONCURRENT_STAGES 環境変数で並行数を制御する（§確定 D）。

設計書:
  docs/features/stage-executor/application/basic-design.md REQ-ME-006
  docs/features/stage-executor/application/detailed-design.md §確定 A〜D
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from bakufu.application.ports.event_bus import EventBusPort
from bakufu.application.ports.internal_review_gate_executor_port import (
    InternalReviewGateExecutorPort,
)
from bakufu.application.ports.llm_provider_port import LLMProviderPort
from bakufu.application.services.stage_executor_service import StageExecutorService
from bakufu.domain.value_objects import StageId, TaskId
from bakufu.infrastructure.security import masking

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# §確定 D: 環境変数名と既定値。
_ENV_KEY = "BAKUFU_MAX_CONCURRENT_STAGES"
_DEFAULT_MAX_CONCURRENT = 1

# Queue の sentinel: stop() が run_loop() に終了を通知するために送る。
_SENTINEL: None = None


def _resolve_max_concurrent() -> int:
    """BAKUFU_MAX_CONCURRENT_STAGES を読み込む。不正値・未設定時は 1 に fallback（§確定 D）。"""
    raw = os.environ.get(_ENV_KEY, "")
    if not raw:
        return _DEFAULT_MAX_CONCURRENT
    try:
        value = int(raw)
        if value < 1:
            raise ValueError(f"{_ENV_KEY} must be >= 1 (got {value})")
        return value
    except (ValueError, TypeError):
        logger.warning(
            "[WARN] %s=%r is invalid; falling back to %d",
            _ENV_KEY,
            raw,
            _DEFAULT_MAX_CONCURRENT,
        )
        return _DEFAULT_MAX_CONCURRENT


class _NullInternalReviewGateExecutor:
    """M5-A 用 null stub: INTERNAL_REVIEW Stage が来た場合に NotImplementedError を raise する。

    M5-B（#164）が InternalReviewGateExecutorPort の実際の実装を提供する。
    """

    async def execute(
        self,
        task_id: TaskId,
        stage_id: StageId,
        required_gate_roles: frozenset,  # type: ignore[type-arg]
    ) -> None:
        raise NotImplementedError(
            f"InternalReviewGateExecutor is not implemented in M5-A "
            f"(task_id={task_id}, stage_id={stage_id}). "
            "Install M5-B (#164) to handle INTERNAL_REVIEW stages."
        )


class StageWorker:
    """Stage 実行 asyncio Queue consumer（REQ-ME-006）。

    Semaphore（BAKUFU_MAX_CONCURRENT_STAGES）で並行数を制御し、Queue から
    （task_id, stage_id）を取り出して StageExecutorService.dispatch_stage() を呼ぶ。
    session_factory からセッションを生成してディスパッチごとに UoW を構築する。

    **ライフサイクル**:
    1. ``start()`` — asyncio.create_task で ``_run_loop()`` をスケジュール。
    2. ``enqueue(task_id, stage_id)`` — Queue に要求を追加（非ブロッキング）。
    3. ``stop()`` — ``_running = False`` + sentinel を Queue に投入して loop を終了。

    **セッション管理**:
    StageExecutorService は dispatch ごとに新規 AsyncSession を受け取る。
    session_factory は Bootstrap の _session_factory を Bootstrap から引き継ぐ。
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        llm_provider: LLMProviderPort,
        event_bus: EventBusPort,
        internal_review_port: InternalReviewGateExecutorPort | None = None,
        max_concurrent: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._llm_provider = llm_provider
        self._event_bus = event_bus
        self._internal_review_port: InternalReviewGateExecutorPort = (
            internal_review_port
            if internal_review_port is not None
            else _NullInternalReviewGateExecutor()  # type: ignore[assignment]
        )
        resolved = max_concurrent if max_concurrent is not None else _resolve_max_concurrent()
        self._semaphore = asyncio.Semaphore(resolved)
        self._queue: asyncio.Queue[tuple[TaskId, StageId] | None] = asyncio.Queue()
        self._running = False
        self._loop_task: asyncio.Task[None] | None = None
        # 実行中の fire-and-forget タスクを追跡する（RUF006 対応）。
        # タスク完了後に自動削除するため、GC でオブジェクトが解放されない。
        self._active_tasks: set[asyncio.Task[None]] = set()
        logger.info(
            "[INFO] StageWorker initialized (max_concurrent=%d)",
            resolved,
        )

    def start(self) -> None:
        """asyncio.create_task で _run_loop() をスケジュールする（§確定 C）。"""
        self._running = True
        self._loop_task = asyncio.create_task(self._run_loop(), name="stage-worker-loop")
        logger.info("[INFO] StageWorker started")

    async def stop(self) -> None:
        """_running フラグをクリアし sentinel を投入して run_loop を終了させる。

        現在実行中の dispatch が完了してから loop が終了する。
        loop_task をキャンセルして完了を待つ。
        """
        self._running = False
        # sentinel で _run_loop の queue.get() ブロックを解除する
        await self._queue.put(_SENTINEL)
        if self._loop_task is not None:
            self._loop_task.cancel()
            await asyncio.gather(self._loop_task, return_exceptions=True)
            self._loop_task = None
        logger.info("[INFO] StageWorker stopped")

    def enqueue(self, task_id: TaskId, stage_id: StageId) -> None:
        """Stage 実行要求を Queue に追加する（非ブロッキング）。

        呼び出し元は await しない。Semaphore 制御は _run_loop 側で行う。
        """
        self._queue.put_nowait((task_id, stage_id))
        logger.debug(
            "[INFO] StageWorker enqueued (task_id=%s, stage_id=%s, queue_size=%d)",
            task_id,
            stage_id,
            self._queue.qsize(),
        )

    # ------------------------------------------------------------------
    # プライベートメソッド
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Queue consumer のメインループ。

        §確定J: ループ開始前に IN_PROGRESS 孤立 Task をスキャンしてキューに再投入する。
        Semaphore を acquire → dispatch_stage → release のサイクルを繰り返す。
        sentinel（None）を受信するか _running が False になると終了する。
        dispatch_stage の例外は StageExecutorService 内で Task.block() 済みのため
        ここでは catchall ログのみ出して次のアイテムへ進む（REQ-ME-006 エラー時）。
        """
        await self._recovery_scan()
        logger.info("[INFO] StageWorker _run_loop started")
        while self._running:
            item = await self._queue.get()
            if item is _SENTINEL:
                break
            task_id, stage_id = item  # type: ignore[misc]

            # Semaphore acquire（上限に達した場合は自然にキューイングして待機）
            await self._semaphore.acquire()
            dispatch_task = asyncio.create_task(
                self._dispatch_and_release(task_id, stage_id),  # type: ignore[arg-type]
                name=f"stage-dispatch-{task_id}-{stage_id}",
            )
            # 完了コールバックで self._active_tasks から自動削除する（RUF006 対応）。
            self._active_tasks.add(dispatch_task)
            dispatch_task.add_done_callback(self._active_tasks.discard)

        logger.info("[INFO] StageWorker _run_loop finished")

    async def _recovery_scan(self) -> None:
        """起動時 IN_PROGRESS 孤立 Task リカバリスキャン（§確定J）。

        StageWorker 起動時（Queue 処理ループ開始前）に ``IN_PROGRESS`` 状態の
        全 Task を DB から取得し、Queue に再投入する。

        admin-cli の ``retry-task`` が BLOCKED → IN_PROGRESS に変更した Task を
        次回サーバー再起動時に自動的にピックアップする機構（Q-OPEN-2 解決策 Option A）。

        冪等性: 起動時は Queue が空のため、同一 Task の二重投入は発生しない。
        Queue maxsize 超過時は ``await self._queue.put()`` で自然に backpressure が発生
        する（正常動作）。
        """
        from bakufu.domain.value_objects import TaskStatus

        try:
            async with self._session_factory() as session:
                from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
                    SqliteTaskRepository,
                )

                repo = SqliteTaskRepository(session)
                in_progress_tasks = await repo.list_by_status(TaskStatus.IN_PROGRESS)

            if not in_progress_tasks:
                logger.info("[INFO] StageWorker: 起動時リカバリスキャン — 孤立 Task なし。")
                return

            count = len(in_progress_tasks)
            for task in in_progress_tasks:
                await self._queue.put((task.id, task.current_stage_id))

            logger.info(
                "[INFO] StageWorker: 起動時リカバリスキャン — %d 件の"
                " IN_PROGRESS Task をキューに投入しました。",
                count,
            )
        except Exception as exc:
            logger.exception(
                "[FAIL] StageWorker: 起動時リカバリスキャンに失敗しました: %s",
                masking.mask(str(exc)),
            )

    async def _dispatch_and_release(self, task_id: TaskId, stage_id: StageId) -> None:
        """dispatch_stage を呼び出し、完了後に Semaphore を release する。

        例外は全て捕捉してログに出す。StageExecutorService は内部でエラー分類・
        Task.block() 処理を行うため、ここへの伝播は予期しない infrastructure 障害のみ。
        """
        try:
            async with self._session_factory() as session:
                service = self._build_service(session)
                await service.dispatch_stage(task_id, stage_id)
        except Exception as exc:
            logger.exception(
                "[FAIL] StageWorker unexpected error in dispatch (task_id=%s stage_id=%s): %s",
                task_id,
                stage_id,
                masking.mask(str(exc)),
            )
        finally:
            self._semaphore.release()

    def _build_service(self, session: AsyncSession) -> StageExecutorService:
        """セッションを受け取って StageExecutorService を構築する。

        import は infrastructure → application の依存方向を遵守するため、
        Repository は infrastructure 層の実装クラスを直接使用する（DI 不要）。
        """
        # 遅延 import: infrastructure → infrastructure の直接依存のみ許可。
        # infrastructure → application（ポートのみ）は OK。
        from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
            SqliteAgentRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
            SqliteRoomRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
            SqliteWorkflowRepository,
        )

        return StageExecutorService(
            task_repo=SqliteTaskRepository(session),
            workflow_repo=SqliteWorkflowRepository(session),
            agent_repo=SqliteAgentRepository(session),
            room_repo=SqliteRoomRepository(session),
            session=session,
            llm_provider=self._llm_provider,
            internal_review_port=self._internal_review_port,
            event_bus=self._event_bus,
            enqueue_fn=self.enqueue,
        )


__all__ = ["StageWorker"]
