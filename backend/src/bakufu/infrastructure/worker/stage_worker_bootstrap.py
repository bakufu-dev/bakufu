"""StageWorkerBootstrap — Bootstrap Stage 6.5 起動ヘルパー（§確定 C）。

Bootstrap クラスから Stage 6.5 の起動ロジックを分離し、単一責務を保つ。
LLM プロバイダ未設定時は WARNING を出して StageWorker をスキップする（他機能への
影響ゼロ）。EventBus 未注入時は InMemoryEventBus を自動生成する。

設計書:
  docs/features/stage-executor/application/basic-design.md §確定 C
  docs/features/stage-executor/infrastructure/detailed-design.md §確定 D
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bakufu.application.ports.event_bus import EventBusPort
from bakufu.application.ports.llm_provider_port import LLMProviderPort

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from bakufu.infrastructure.worker.stage_worker import StageWorker

logger = logging.getLogger(__name__)


class StageWorkerBootstrap:
    """Bootstrap Stage 6.5 — StageWorker の起動・状態管理を担う（§確定 C）。

    Bootstrap から ``_stage_6_5_stage_worker()`` ロジックを分離して単一責務を保つ。
    ``start()`` 完了後は ``worker`` / ``event_bus`` / ``llm_provider`` プロパティで
    起動結果を取得できる。

    **LLM 未設定時の振る舞い**: ``BAKUFU_LLM_PROVIDER`` が未設定または解決不能の場合、
    StageWorker を起動せず WARNING ログのみで継続する（``worker`` は None）。
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBusPort | None = None,
        llm_provider: LLMProviderPort | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._llm_provider = llm_provider
        self._worker: StageWorker | None = None

    @property
    def worker(self) -> StageWorker | None:
        """起動済み StageWorker。未起動（LLM 未設定）の場合は None。"""
        return self._worker

    @property
    def event_bus(self) -> EventBusPort | None:
        """使用する EventBus（start() 後は必ず non-None）。"""
        return self._event_bus

    @property
    def llm_provider(self) -> LLMProviderPort | None:
        """使用する LLMProviderPort。LLM 未設定の場合は None。"""
        return self._llm_provider

    async def start(self) -> None:
        """EventBus / LLMProvider を確保して StageWorker を起動する。

        LLM プロバイダの構築に失敗した場合は WARNING のみで早期 return する。
        その場合 ``worker`` は None のままとなる。
        """
        self._ensure_event_bus()
        if not await self._ensure_llm_provider():
            return
        self._launch_worker()

    # ------------------------------------------------------------------
    # プライベートメソッド
    # ------------------------------------------------------------------

    def _ensure_event_bus(self) -> None:
        """EventBus が未注入の場合 InMemoryEventBus を生成する。"""
        if self._event_bus is not None:
            return
        # 遅延 import: infrastructure 内部の循環参照リスクを回避。
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        self._event_bus = InMemoryEventBus()
        logger.info("[INFO] Bootstrap stage 6.5/8: InMemoryEventBus created for StageWorker")

    async def _ensure_llm_provider(self) -> bool:
        """LLMProviderPort が未注入の場合 env から構築を試みる。

        Returns:
            True — プロバイダが利用可能。False — 構築失敗（WARNING ログ済み）。
        """
        if self._llm_provider is not None:
            return True
        try:
            from bakufu.infrastructure.llm.config import LLMCliConfig
            from bakufu.infrastructure.llm.factory import llm_provider_factory

            cli_config = LLMCliConfig.load()
            self._llm_provider = llm_provider_factory(
                cli_config,
                session_factory=self._session_factory,
            )
            logger.info(
                "[INFO] Bootstrap stage 6.5/8: LLMProviderPort created (provider=%s)",
                self._llm_provider.provider,
            )
            return True
        except Exception as exc:
            logger.warning(
                "[WARN] Bootstrap stage 6.5/8: LLM provider initialization failed: %s; "
                "StageWorker will not start (LLM-dependent stages will not execute). "
                "Set BAKUFU_LLM_PROVIDER to enable stage execution.",
                exc,
            )
            return False

    def _launch_worker(self) -> None:
        """StageWorker を生成して start() を呼ぶ。

        InternalReviewGateExecutor を構築して StageWorker に注入する（§確定 G / I）。
        repo factory callable を InternalReviewService に注入することで、
        application 層が infrastructure 具象クラスを直接 import しない設計を保全する。
        """
        from uuid import uuid4

        from bakufu.application.services.internal_review_service import InternalReviewService
        from bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository import (  # noqa: E501
            SqliteInternalReviewGateRepository,
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
        from bakufu.infrastructure.reviewers.internal_review_gate_executor import (
            InternalReviewGateExecutor,
        )
        from bakufu.infrastructure.worker.stage_worker import StageWorker

        assert self._event_bus is not None
        assert self._llm_provider is not None

        review_svc = InternalReviewService(
            session_factory=self._session_factory,
            gate_repo_factory=SqliteInternalReviewGateRepository,
            task_repo_factory=SqliteTaskRepository,
            workflow_repo_factory=SqliteWorkflowRepository,
            room_repo_factory=SqliteRoomRepository,
            event_bus=self._event_bus,
        )

        internal_review_executor = InternalReviewGateExecutor(
            review_svc=review_svc,
            llm_provider=self._llm_provider,
            agent_id=uuid4(),
            session_factory=self._session_factory,
        )

        worker = StageWorker(
            session_factory=self._session_factory,
            llm_provider=self._llm_provider,
            event_bus=self._event_bus,
            internal_review_port=internal_review_executor,
        )
        worker.start()
        self._worker = worker
        logger.info(
            "[INFO] Bootstrap stage 6.5/8: StageWorker started (with InternalReviewGateExecutor)"
        )


__all__ = ["StageWorkerBootstrap"]
