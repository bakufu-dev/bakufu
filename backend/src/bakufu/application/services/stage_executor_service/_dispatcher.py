"""_StageDispatcher — StageKind ルーティングと実行ロジック（§確定 A〜C / §確定 F）。

WORK / INTERNAL_REVIEW / EXTERNAL_REVIEW の 3 分岐を担い、UoW を読み取りフェーズと
書き込みフェーズに分離する（LLM 呼び出しはトランザクション外）。
LLM エラー処理は _LLMErrorHandler に委譲する（SRP）。

設計書:
  docs/features/stage-executor/application/basic-design.md REQ-ME-001〜003 / REQ-ME-005
  docs/features/stage-executor/application/detailed-design.md §確定 A〜C / §確定 F
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from bakufu.application.ports.agent_repository import AgentRepository
from bakufu.application.ports.event_bus import EventBusPort
from bakufu.application.ports.internal_review_gate_executor_port import (
    InternalReviewGateExecutorPort,
)
from bakufu.application.ports.llm_provider_port import LLMProviderPort
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.application.ports.workflow_repository import WorkflowRepository
from bakufu.application.services.stage_executor_service._error_handler import (
    _LLMErrorHandler,
)
from bakufu.domain.events import TaskStateChangedEvent
from bakufu.domain.exceptions.llm_provider import (
    LLMProviderError,
    LLMProviderRateLimitedError,
    LLMProviderSessionLostError,
    LLMProviderTimeoutError,
)
from bakufu.domain.value_objects import (
    Deliverable,
    GateRole,
    StageId,
    StageKind,
    TaskId,
    TaskStatus,
    TransitionCondition,
)
from bakufu.infrastructure.security import masking

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from bakufu.domain.agent.agent import Agent
    from bakufu.domain.task.task import Task
    from bakufu.domain.workflow.entities import Stage
    from bakufu.domain.workflow.workflow import Workflow

logger = logging.getLogger(__name__)

# 並列 Agent アサインが複数の場合でも先頭を代表 Agent とする（MVP シリアル前提）。
_PRIMARY_AGENT_INDEX: int = 0


class _StageDispatcher:
    """StageKind ルーティングと実行ロジック（§確定 A〜C）。

    StageExecutorService から合成（composition）される内部クラス。
    LLM エラー処理は _LLMErrorHandler に委譲する（SRP 遵守）。

    **Fail Fast（§確定 F）**:
    - dispatch_stage() 呼び出し時点で Task.status = IN_PROGRESS でなければ ValueError。
    - retry_blocked_task() 呼び出し時点で Task.status = BLOCKED でなければ ValueError。
    """

    def __init__(
        self,
        *,
        task_repo: TaskRepository,
        workflow_repo: WorkflowRepository,
        agent_repo: AgentRepository,
        room_repo: RoomRepository,
        session: AsyncSession,
        llm_provider: LLMProviderPort,
        internal_review_port: InternalReviewGateExecutorPort,
        event_bus: EventBusPort,
        enqueue_fn: Callable[[TaskId, StageId], None],
        error_handler: _LLMErrorHandler,
    ) -> None:
        self._task_repo = task_repo
        self._workflow_repo = workflow_repo
        self._agent_repo = agent_repo
        self._room_repo = room_repo
        self._session = session
        self._llm_provider = llm_provider
        self._internal_review_port = internal_review_port
        self._event_bus = event_bus
        self._enqueue_fn = enqueue_fn
        self._error_handler = error_handler

    # ------------------------------------------------------------------
    # パブリック API（StageExecutorService から委譲）
    # ------------------------------------------------------------------

    async def dispatch_stage(self, task_id: TaskId, stage_id: StageId) -> None:
        """Stage を StageKind に応じて実行する（REQ-ME-001〜003）。

        読み取りフェーズ（短トランザクション）→ 処理（LLM 呼び出しは長時間のため
        トランザクション外）→ 書き込みフェーズ（短トランザクション）の順序で進む。

        **Fail Fast（§確定 F）**: Task.status が IN_PROGRESS でない場合、または
        Stage が見つからない場合は ValueError を raise する。
        StageWorker の ``_dispatch_and_release`` が例外を捕捉して次キューアイテムへ進む。
        """
        # 読み取りフェーズ
        task, stage, workflow, agent = await self._load_context(task_id, stage_id)

        if task is None:
            msg = f"[FAIL] dispatch_stage: task not found (task_id={task_id})"
            logger.error("%s", msg)
            raise ValueError(msg)

        if task.status != TaskStatus.IN_PROGRESS:
            msg = (
                f"[FAIL] dispatch_stage: task={task_id} is not IN_PROGRESS"
                f" (status={task.status}); skipping"
            )
            logger.error("%s", msg)
            raise ValueError(msg)

        if stage is None:
            msg = (
                f"[FAIL] dispatch_stage: stage={stage_id} not found"
                f" in workflow for task={task_id}"
            )
            logger.error("%s", msg)
            raise ValueError(msg)

        # StageKind 分岐（§確定 A〜E）
        if stage.kind == StageKind.WORK:
            await self._execute_work_stage(task, stage, workflow, agent)
        elif stage.kind == StageKind.INTERNAL_REVIEW:
            await self._delegate_internal_review(task, stage)
        elif stage.kind == StageKind.EXTERNAL_REVIEW:
            await self._request_external_review(task)

    async def retry_blocked_task(self, task_id: TaskId) -> None:
        """BLOCKED Task を IN_PROGRESS に戻して最後の Stage を再キューする（REQ-ME-005）。

        **Fail Fast（§確定 F）**:
        - Task が存在しない → MSG-ME-004 をログ出力して ValueError を raise。
        - Task.status が BLOCKED でない → MSG-ME-003 をログ出力して ValueError を raise。
        """
        async with self._session.begin():
            task = await self._task_repo.find_by_id(task_id)
            if task is None:
                msg = (
                    f"[FAIL] Task {task_id} not found\n"
                    f"Next: verify the task_id with 'bakufu admin list-blocked'"
                )
                logger.error("%s", msg)
                raise ValueError(msg)
            if task.status != TaskStatus.BLOCKED:
                msg = (
                    f"[FAIL] Task {task_id} is not BLOCKED"
                    f" (current status: {task.status.value})\n"
                    f"Next: verify the task_id and its current status with"
                    f" 'bakufu admin list-blocked'"
                )
                logger.error("%s", msg)
                raise ValueError(msg)

            old_status = task.status
            updated = task.unblock_retry(updated_at=self._now())
            await self._task_repo.save(updated)

        # トランザクション commit 後に publish
        await self._event_bus.publish(
            TaskStateChangedEvent(
                aggregate_id=str(task.id),
                directive_id=str(task.directive_id),
                old_status=str(old_status),
                new_status=str(updated.status),
                room_id=str(task.room_id),
            )
        )

        # 最後の Stage を再キュー（§確定 A）
        self._enqueue_fn(updated.id, updated.current_stage_id)

    # ------------------------------------------------------------------
    # プライベートメソッド — StageKind 分岐
    # ------------------------------------------------------------------

    async def _execute_work_stage(
        self,
        task: Task,
        stage: Stage,
        workflow: Workflow,
        agent: Agent | None,
    ) -> None:
        """WORK Stage の LLM 実行→deliverable コミット→次 Stage 進行（REQ-ME-001）。

        LLM 呼び出しはトランザクション外で実行し、書き込み時に短いトランザクションを開く。
        エラー時は _LLMErrorHandler に委譲（REQ-ME-004）。
        """
        if agent is None:
            logger.error(
                "[FAIL] dispatch_stage: no agent assigned to task=%s; blocking",
                task.id,
            )
            await self._error_handler.block_task(
                task,
                reason="no_agent",
                error_summary="Task has no assigned agent",
            )
            return

        system_prompt = agent.persona.prompt_body
        messages = self._build_user_message(stage)
        session_id: str = str(stage.id)

        # LLM 呼び出し（§確定 B: session_id = Stage ID）
        try:
            chat_result = await self._llm_provider.chat(
                messages=messages,
                system=system_prompt,
                agent_name=agent.name,
                session_id=session_id,
            )
        except LLMProviderTimeoutError:
            # Timeout は SessionLost 相当に合流（§確定 H）: 新規 UUID v4 で 1 回リトライ
            new_session_id = str(uuid4())
            logger.warning(
                "[WARN] LLM timeout on task=%s stage=%s; retrying with new session_id=%s",
                task.id,
                stage.id,
                new_session_id,
            )
            try:
                chat_result = await self._llm_provider.chat(
                    messages=messages,
                    system=system_prompt,
                    agent_name=agent.name,
                    session_id=new_session_id,
                )
            except LLMProviderError as retry_exc:
                await self._error_handler.handle_llm_error(task, retry_exc)
                return
        except LLMProviderSessionLostError:
            # SessionLost: 新規 UUID v4 で 1 回リトライ（§確定 H）
            new_session_id = str(uuid4())
            logger.warning(
                "[WARN] LLM session lost on task=%s stage=%s; retrying with new session_id=%s",
                task.id,
                stage.id,
                new_session_id,
            )
            try:
                chat_result = await self._llm_provider.chat(
                    messages=messages,
                    system=system_prompt,
                    agent_name=agent.name,
                    session_id=new_session_id,
                )
            except LLMProviderError as retry_exc:
                await self._error_handler.handle_llm_error(task, retry_exc)
                return
        except LLMProviderRateLimitedError:
            # RateLimited: backoff 3 回（§確定 E）
            result = await self._error_handler.retry_rate_limited(
                task=task,
                messages=messages,
                system_prompt=system_prompt,
                agent_name=agent.name,
            )
            if result is None:
                return  # block 済み
            chat_result = result
        except LLMProviderError as exc:
            # AuthExpired / ProcessError / EmptyResponse: 即 BLOCK（§確定 H）
            await self._error_handler.handle_llm_error(task, exc)
            return

        # deliverable テキストをマスキングして保存
        masked_body = masking.mask(chat_result.response)

        # 次 Stage を Workflow transitions から決定
        next_transition = next(
            (
                t
                for t in workflow.transitions
                if t.from_stage_id == stage.id
                and t.condition in (TransitionCondition.APPROVED, TransitionCondition.CONDITIONAL)
            ),
            None,
        )
        # APPROVED/CONDITIONAL がなければ任意の outgoing transition を選択（フォールバック）
        if next_transition is None:
            next_transition = next(
                (t for t in workflow.transitions if t.from_stage_id == stage.id),
                None,
            )

        now = self._now()
        deliverable = Deliverable(
            stage_id=stage.id,
            body_markdown=masked_body,
            committed_by=agent.id,
            committed_at=now,
        )

        # 書き込みフェーズ（短トランザクション）
        async with self._session.begin():
            # LLM 実行中に状態が変わっている可能性があるため再取得
            current_task = await self._task_repo.find_by_id(task.id)
            if current_task is None or current_task.status != TaskStatus.IN_PROGRESS:
                logger.warning(
                    "[WARN] task=%s state changed during LLM execution; discarding result",
                    task.id,
                )
                return

            updated = current_task.commit_deliverable(
                stage.id,
                deliverable,
                agent.id,
                updated_at=now,
            )

            if next_transition is not None:
                updated = updated.advance_to_next(
                    next_transition.id,
                    agent.id,
                    next_transition.to_stage_id,
                    updated_at=now,
                )
            else:
                # 終端 Stage → complete
                updated = updated.complete(
                    uuid4(),
                    agent.id,
                    updated_at=now,
                )

            await self._task_repo.save(updated)

        # トランザクション commit 後に publish
        await self._event_bus.publish(
            TaskStateChangedEvent(
                aggregate_id=str(task.id),
                directive_id=str(task.directive_id),
                old_status=str(task.status),
                new_status=str(updated.status),
                room_id=str(task.room_id),
            )
        )

        # 次 Stage を enqueue（§確定 A）
        if next_transition is not None:
            self._enqueue_fn(updated.id, next_transition.to_stage_id)

    async def _delegate_internal_review(self, task: Task, stage: Stage) -> None:
        """INTERNAL_REVIEW Stage を InternalReviewGateExecutorPort に委譲（REQ-ME-002）。

        execute() は Gate 判定完了まで await する long-running coroutine（§確定 G）。
        エラー時は Task.block() に帰着させ MSG-ME-002 をログに出力する。
        """
        # Stage.required_role → GateRole 変換（小文字 slug へ）
        required_gate_roles: frozenset[GateRole] = frozenset(
            r.value.lower()
            for r in stage.required_role  # type: ignore[misc]
        )
        try:
            await self._internal_review_port.execute(
                task_id=task.id,
                stage_id=stage.id,
                required_gate_roles=required_gate_roles,
            )
        except Exception as exc:
            masked_summary = masking.mask(str(exc))
            msg = (
                f"[FAIL] Internal review gate execution failed: {masked_summary}\n"
                f"Next: run 'bakufu admin retry-task {task.id}' after resolving the issue"
            )
            logger.error("%s", msg)
            await self._error_handler.block_task(
                task,
                reason="internal_review_gate_error",
                error_summary=masked_summary,
            )

    async def _request_external_review(self, task: Task) -> None:
        """EXTERNAL_REVIEW Stage 遷移（REQ-ME-003）。

        Task.request_external_review() を呼び出して AWAITING_EXTERNAL_REVIEW に遷移。
        ExternalReviewGate 生成・Discord 通知は Outbox Dispatcher が非同期処理（M6-A）。

        **Fail Fast（§確定 F）**: DB 再取得時に状態が変わっていた場合は ValueError を raise。
        """
        now = self._now()
        async with self._session.begin():
            current_task = await self._task_repo.find_by_id(task.id)
            if current_task is None or current_task.status != TaskStatus.IN_PROGRESS:
                msg = (
                    f"[FAIL] _request_external_review: task={task.id} state changed"
                    f" before EXTERNAL_REVIEW transition"
                )
                logger.warning("%s", msg)
                raise ValueError(msg)
            updated = current_task.request_external_review(updated_at=now)
            await self._task_repo.save(updated)

        await self._event_bus.publish(
            TaskStateChangedEvent(
                aggregate_id=str(task.id),
                directive_id=str(task.directive_id),
                old_status=str(task.status),
                new_status=str(updated.status),
                room_id=str(task.room_id),
            )
        )

    # ------------------------------------------------------------------
    # プライベートメソッド — ユーティリティ
    # ------------------------------------------------------------------

    async def _load_context(
        self,
        task_id: TaskId,
        stage_id: StageId,
    ) -> tuple[Task | None, Stage | None, Workflow | None, Agent | None]:
        """Task / Stage / Workflow / Agent を読み取りフェーズで取得する。

        短いトランザクション内で全ての読み取りを完結させ、LLM 実行前にセッションを解放する。
        """
        async with self._session.begin():
            task = await self._task_repo.find_by_id(task_id)
            if task is None:
                return None, None, None, None

            room = await self._room_repo.find_by_id(task.room_id)
            if room is None:
                logger.error(
                    "[FAIL] dispatch_stage: room=%s not found for task=%s",
                    task.room_id,
                    task_id,
                )
                return task, None, None, None

            workflow = await self._workflow_repo.find_by_id(room.workflow_id)
            if workflow is None:
                logger.error(
                    "[FAIL] dispatch_stage: workflow=%s not found for task=%s",
                    room.workflow_id,
                    task_id,
                )
                return task, None, None, None

            stage = next((s for s in workflow.stages if s.id == stage_id), None)
            if stage is None:
                return task, None, workflow, None

            # 代表 Agent を取得（割り当て済みリストの先頭）
            agent: Agent | None = None
            if task.assigned_agent_ids:
                agent = await self._agent_repo.find_by_id(
                    task.assigned_agent_ids[_PRIMARY_AGENT_INDEX]
                )

        return task, stage, workflow, agent

    @staticmethod
    def _build_user_message(stage: Stage) -> list[dict[str, str]]:
        """Stage 情報から LLM へのユーザーメッセージを構築する。

        Stage 名と required_deliverables の template_id を列挙した簡潔な指示を生成する。
        テンプレート詳細（説明文）は LLM が自身の知識から補完することを期待する（MVP）。
        """
        lines = [f"Stage: {stage.name}"]
        if stage.required_deliverables:
            lines.append("\nRequired deliverables:")
            for dr in stage.required_deliverables:
                optional_marker = " (optional)" if dr.optional else ""
                lines.append(f"  - template_id={dr.template_ref.template_id}{optional_marker}")
        return [{"role": "user", "content": "\n".join(lines)}]

    @staticmethod
    def _now() -> datetime:
        """タイムゾーン付き現在時刻を返す（テスト差し替え可能な単一出口）。"""
        return datetime.now(UTC)
