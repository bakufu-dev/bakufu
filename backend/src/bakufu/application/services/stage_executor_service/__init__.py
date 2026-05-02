"""StageExecutorService パッケージ — Stage 実行オーケストレータ（REQ-ME-001〜005）。

WORK / INTERNAL_REVIEW / EXTERNAL_REVIEW の 3 分岐を担い、LLMProviderError 5 分類
に対するリトライ戦略を実装する。UoW（``async with session.begin()``）は
読み取りフェーズと書き込みフェーズを分離する — LLM 呼び出しは長時間処理のため
DB トランザクション外で実行する。

**パッケージ内部構成**:
- ``_error_handler``: _LLMErrorHandler — LLM エラー 5 分類・リトライ・BLOCK 帰着
- ``_dispatcher``: _StageDispatcher — StageKind ルーティングと実行ロジック
- ``__init__``: StageExecutorService — 公開 API シェル（合成で委譲）

設計書:
  docs/features/stage-executor/application/basic-design.md REQ-ME-001〜005
  docs/features/stage-executor/application/detailed-design.md §確定 A〜H
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from bakufu.application.ports.agent_repository import AgentRepository
from bakufu.application.ports.event_bus import EventBusPort
from bakufu.application.ports.internal_review_gate_executor_port import (
    InternalReviewGateExecutorPort,
)
from bakufu.application.ports.llm_provider_port import LLMProviderPort
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.application.ports.workflow_repository import WorkflowRepository
from bakufu.application.services.stage_executor_service._dispatcher import (
    _StageDispatcher,
)
from bakufu.application.services.stage_executor_service._error_handler import (
    _LLMErrorHandler,
)
from bakufu.domain.value_objects import StageId, TaskId

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

#: StageWorker から注入される再キュー関数の型エイリアス。
type EnqueueFn = Callable[[TaskId, StageId], None]


class StageExecutorService:
    """Stage 実行オーケストレータ（REQ-ME-001〜005）。

    StageKind に応じて WORK / INTERNAL_REVIEW / EXTERNAL_REVIEW の 3 分岐を実行する。
    LLMProviderError 5 分類のリトライ戦略を実装し、回復不能時は Task.block() に帰着
    させる。

    **不変条件（§確定 F）**:
    - ``dispatch_stage()`` 呼び出し時点で Task.status = IN_PROGRESS であること。
    - ``retry_blocked_task()`` 呼び出し時点で Task.status = BLOCKED であること。
    いずれも満たさない場合は ValueError を raise する（Fail Fast）。

    **セキュリティ（セキュリティ設計 T1）**:
    - LLM 出力・エラー情報は必ず masking.mask() を通してから永続化する。
    - deliverable の body_markdown と last_error はマスキング済み値のみ DB に書く。
    """

    def __init__(
        self,
        task_repo: TaskRepository,
        workflow_repo: WorkflowRepository,
        agent_repo: AgentRepository,
        room_repo: RoomRepository,
        session: AsyncSession,
        llm_provider: LLMProviderPort,
        internal_review_port: InternalReviewGateExecutorPort,
        event_bus: EventBusPort,
        enqueue_fn: EnqueueFn,
    ) -> None:
        error_handler = _LLMErrorHandler(
            task_repo=task_repo,
            session=session,
            llm_provider=llm_provider,
            event_bus=event_bus,
        )
        self._dispatcher = _StageDispatcher(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            session=session,
            llm_provider=llm_provider,
            internal_review_port=internal_review_port,
            event_bus=event_bus,
            enqueue_fn=enqueue_fn,
            error_handler=error_handler,
        )

    async def dispatch_stage(self, task_id: TaskId, stage_id: StageId) -> None:
        """Stage を StageKind に応じて実行する（REQ-ME-001〜003）。

        **Fail Fast（§確定 F）**: Task.status が IN_PROGRESS でない場合、または
        Stage が見つからない場合は ValueError を raise する。
        """
        await self._dispatcher.dispatch_stage(task_id, stage_id)

    async def retry_blocked_task(self, task_id: TaskId) -> None:
        """BLOCKED Task を IN_PROGRESS に戻して最後の Stage を再キューする（REQ-ME-005）。

        **Fail Fast（§確定 F）**: Task が不在または BLOCKED でない場合は ValueError を raise。
        """
        await self._dispatcher.retry_blocked_task(task_id)


__all__ = ["EnqueueFn", "StageExecutorService"]
