"""LLMErrorHandler — LLM エラー分類・リトライ・Task.block() 帰着（§確定 H）。

dispatch_stage から呼ばれる内部ヘルパー。Task を BLOCKED に遷移させる唯一の
経路を集約し、LLM エラーの 5 分類戦略と RateLimited backoff リトライを提供する。

設計書:
  docs/features/stage-executor/application/basic-design.md REQ-ME-004
  docs/features/stage-executor/application/detailed-design.md §確定 E / §確定 H
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from bakufu.application.ports.event_bus import EventBusPort
from bakufu.application.ports.llm_provider_port import LLMProviderPort
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.domain.events import TaskStateChangedEvent
from bakufu.domain.exceptions.llm_provider import (
    LLMProviderError,
    LLMProviderRateLimitedError,
)
from bakufu.domain.value_objects import TaskStatus
from bakufu.infrastructure.security import masking

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from bakufu.domain.task.task import Task
    from bakufu.domain.value_objects.chat_result import ChatResult

logger = logging.getLogger(__name__)

# §確定 E: RateLimited backoff 固定値（秒）。
_RATE_LIMIT_BACKOFFS: tuple[int, ...] = (60, 300, 900)


class LLMErrorHandler:
    """LLM エラー分類・リトライ・Task.block() 帰着を担う内部ヘルパー（§確定 H）。

    StageDispatcher から合成（composition）され、Task を BLOCKED に遷移させる
    唯一の経路となる。本クラスは StageDispatcher からのみ使用される（公開 API 不可）。

    **責務**:
    - ``handle_llm_error``: LLMProviderError を 5 分類し即 BLOCK に帰着（REQ-ME-004）。
    - ``retry_rate_limited``: RateLimited backoff 3 回リトライ（§確定 E）。
    - ``block_task``: Task を BLOCKED に遷移させ保存・イベント発行（共有ヘルパー）。
    """

    def __init__(
        self,
        *,
        task_repo: TaskRepository,
        session: AsyncSession,
        llm_provider: LLMProviderPort,
        event_bus: EventBusPort,
    ) -> None:
        self._task_repo = task_repo
        self._session = session
        self._llm_provider = llm_provider
        self._event_bus = event_bus

    async def handle_llm_error(self, task: Task, exc: LLMProviderError) -> None:
        """LLMProviderError を分類し MSG-ME-001 を出力して Task.block() に帰着（REQ-ME-004）。

        AuthExpired / ProcessError / EmptyResponse は即 BLOCK。
        SessionLost / RateLimited は呼び出し元でリトライ済みでここに到達する。
        """
        error_kind = type(exc).__name__
        masked_summary = masking.mask(exc.message)
        msg = (
            f"[FAIL] Stage execution failed: {error_kind} — {masked_summary}\n"
            f"Next: run 'bakufu admin retry-task {task.id}' after resolving the issue,"
            f" or 'bakufu admin cancel-task {task.id} --reason <reason>'"
        )
        logger.error("%s", msg)
        await self.block_task(task, reason=error_kind, error_summary=masked_summary)

    async def retry_rate_limited(
        self,
        task: Task,
        messages: list[dict[str, str]],
        system_prompt: str,
        agent_name: str,
    ) -> ChatResult | None:
        """RateLimited: backoff 3 回リトライ（§確定 E）。

        成功した場合は ChatResult を返す。3 回全て失敗した場合は Task.block() を呼び出し
        None を返す。途中で別の LLMProviderError が発生した場合も block して None を返す。
        """
        for wait_secs in _RATE_LIMIT_BACKOFFS:
            logger.warning(
                "[WARN] LLM rate limited on task=%s; waiting %ds before retry",
                task.id,
                wait_secs,
            )
            await asyncio.sleep(wait_secs)
            try:
                return await self._llm_provider.chat(
                    messages=messages,
                    system=system_prompt,
                    agent_name=agent_name,
                    session_id=str(uuid4()),
                )
            except LLMProviderRateLimitedError:
                continue
            except LLMProviderError as exc:
                await self.handle_llm_error(task, exc)
                return None

        # 3 回全て RateLimited → BLOCK
        masked_summary = masking.mask("rate limit persisted after 3 retries")
        error_kind = "LLMProviderRateLimitedError"
        msg = (
            f"[FAIL] Stage execution failed: {error_kind} — {masked_summary}\n"
            f"Next: run 'bakufu admin retry-task {task.id}' after resolving the issue,"
            f" or 'bakufu admin cancel-task {task.id} --reason <reason>'"
        )
        logger.error("%s", msg)
        await self.block_task(task, reason=error_kind, error_summary=masked_summary)
        return None

    async def block_task(
        self,
        task: Task,
        *,
        reason: str,
        error_summary: str,
    ) -> None:
        """Task を BLOCKED に遷移させ保存・イベント発行する。

        StageDispatcher からも直接呼ばれる（LLM 以外のブロック要因にも対応）。
        error_summary は masking.mask() 適用済みであること（セキュリティ設計 T1）。
        """
        now = self._now()
        async with self._session.begin():
            # 最新状態を再取得（並行更新の考慮）
            current_task = await self._task_repo.find_by_id(task.id)
            if current_task is None:
                logger.error(
                    "[FAIL] block_task: task=%s disappeared before block()",
                    task.id,
                )
                return
            if current_task.status not in (
                TaskStatus.IN_PROGRESS,
                TaskStatus.AWAITING_EXTERNAL_REVIEW,
            ):
                logger.warning(
                    "[WARN] block_task: task=%s status=%s; cannot block from this state",
                    task.id,
                    current_task.status,
                )
                return

            updated = current_task.block(
                reason=reason,
                last_error=error_summary or "unknown error",
                updated_at=now,
            )
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

    @staticmethod
    def _now() -> datetime:
        """タイムゾーン付き現在時刻を返す（テスト差し替え可能な単一出口）。"""
        return datetime.now(UTC)
