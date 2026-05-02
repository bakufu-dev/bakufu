"""InternalReviewService — INTERNAL_REVIEW Gate CRUD と downstream 連携（本体）。

session_factory + repo factory callable を注入する形式で
application 層から infrastructure 具象クラスへの直接依存を排除する（§確定 I）。
WeakValueDictionary[InternalGateId, asyncio.Lock] で Lost Update を防止する（§確定 H）。

設計書: docs/features/internal-review-gate/application/detailed-design.md §確定 F〜J
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4
from weakref import WeakValueDictionary

from bakufu.application.exceptions.gate_exceptions import (
    InternalReviewGateNotFoundError,
    UnauthorizedGateRoleError,
)
from bakufu.application.exceptions.task_exceptions import (
    IllegalTaskStateError,
    TaskNotFoundError,
)
from bakufu.application.ports.event_bus import EventBusPort
from bakufu.application.services.internal_review_service._dag_traversal import _DagTraversal
from bakufu.domain.events import TaskStateChangedEvent
from bakufu.domain.internal_review_gate.internal_review_gate import InternalReviewGate
from bakufu.domain.value_objects import (
    SYSTEM_AGENT_ID,
    AgentId,
    GateDecision,
    GateRole,
    InternalGateId,
    StageId,
    StageKind,
    TaskId,
    TaskStatus,
    VerdictDecision,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from bakufu.application.ports.internal_review_gate_repository import (
        InternalReviewGateRepository,
    )
    from bakufu.application.ports.room_repository import RoomRepository
    from bakufu.application.ports.task_repository import TaskRepository
    from bakufu.application.ports.workflow_repository import WorkflowRepository

logger = logging.getLogger(__name__)


class InternalReviewService:
    """INTERNAL_REVIEW Gate CRUD と downstream 連携を担う application サービス。

    repo factory callable を注入する形式で DI を実現する（§確定 I）。
    各操作で session_factory から独立した AsyncSession を生成し、
    application 層が infrastructure 具象クラスを直接 import しない設計を保全する。

    ふるまいの不変条件（§確定 F）:
    - create_gate(): required_gate_roles が空集合 → None を返す
    - create_gate(): Task.status != IN_PROGRESS → IllegalTaskStateError
    - create_gate(): 既存 PENDING Gate が存在 → そのまま返す（べき等）
    - submit_verdict(): role を gate.required_gate_roles と照合して認可（T1）
    - submit_verdict(): ALL_APPROVED → _handle_all_approved()
    - submit_verdict(): REJECTED → _handle_rejected()
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        gate_repo_factory: Callable[[AsyncSession], InternalReviewGateRepository],
        task_repo_factory: Callable[[AsyncSession], TaskRepository],
        workflow_repo_factory: Callable[[AsyncSession], WorkflowRepository],
        room_repo_factory: Callable[[AsyncSession], RoomRepository],
        event_bus: EventBusPort,
    ) -> None:
        """サービスを初期化する。

        Args:
            session_factory: 各操作ごとに独立した AsyncSession を生成するファクトリ。
            gate_repo_factory: InternalReviewGateRepository を生成するファクトリ。
                application 層が infrastructure 具象クラスを import しないよう
                factory callable として注入する（§確定 I）。
            task_repo_factory: TaskRepository を生成するファクトリ。
            workflow_repo_factory: WorkflowRepository を生成するファクトリ。
            room_repo_factory: RoomRepository を生成するファクトリ。
            event_bus: Gate 状態変化 Domain Event 発行用。
        """
        self._session_factory = session_factory
        self._gate_repo_factory = gate_repo_factory
        self._task_repo_factory = task_repo_factory
        self._workflow_repo_factory = workflow_repo_factory
        self._room_repo_factory = room_repo_factory
        self._event_bus = event_bus
        # §確定 H: Gate ID ごとの Lost Update 防止 Lock。
        self._locks: WeakValueDictionary[InternalGateId, asyncio.Lock] = WeakValueDictionary()

    async def create_gate(
        self,
        task_id: TaskId,
        stage_id: StageId,
        required_gate_roles: frozenset[GateRole],
    ) -> InternalReviewGate | None:
        """Gate を生成し DB に保存して返す（§確定 F）。

        Returns:
            新規 InternalReviewGate、または既存 PENDING Gate。
            required_gate_roles が空の場合は None。
        """
        if not required_gate_roles:
            return None

        async with self._session_factory() as session, session.begin():
            gate_repo = self._gate_repo_factory(session)
            task_repo = self._task_repo_factory(session)

            task = await task_repo.find_by_id(task_id)
            if task is None:
                raise TaskNotFoundError(task_id)
            if task.status != TaskStatus.IN_PROGRESS:
                raise IllegalTaskStateError(task_id, task.status, "create_gate")

            existing = await gate_repo.find_by_task_and_stage(task_id, stage_id)
            if existing is not None:
                return existing

            now = datetime.now(UTC)
            new_gate = InternalReviewGate(
                id=uuid4(),
                task_id=task_id,
                stage_id=stage_id,
                required_gate_roles=required_gate_roles,
                verdicts=(),
                gate_decision=GateDecision.PENDING,
                created_at=now,
            )
            await gate_repo.save(new_gate)

        return new_gate

    async def submit_verdict(
        self,
        *,
        gate_id: InternalGateId,
        role: GateRole,
        agent_id: AgentId,
        decision: VerdictDecision,
        comment: str,
    ) -> GateDecision:
        """Verdict を登録し Gate を保存、downstream 連携を実行する（§確定 H）。

        Returns:
            更新後の GateDecision（PENDING / ALL_APPROVED / REJECTED）。
        """
        async with self._locks.setdefault(gate_id, asyncio.Lock()):
            # Phase 1: Gate read-modify-write（短トランザクション）
            async with self._session_factory() as session, session.begin():
                gate_repo = self._gate_repo_factory(session)
                gate = await gate_repo.find_by_id(gate_id)
                if gate is None:
                    raise InternalReviewGateNotFoundError(gate_id)

                if role not in gate.required_gate_roles:
                    raise UnauthorizedGateRoleError(agent_id, role)

                now = datetime.now(UTC)
                updated_gate = gate.submit_verdict(
                    role=role,
                    agent_id=agent_id,
                    decision=decision,
                    comment=comment,
                    decided_at=now,
                )
                await gate_repo.save(updated_gate)

            # Phase 2: downstream 連携（別セッション）
            task_id = updated_gate.task_id
            stage_id = updated_gate.stage_id

            approved_by_roles = [
                v.role for v in updated_gate.verdicts if v.decision == VerdictDecision.APPROVED
            ]
            rejected_by_role = next(
                (v.role for v in updated_gate.verdicts if v.decision == VerdictDecision.REJECTED),
                None,
            )

            if updated_gate.gate_decision == GateDecision.ALL_APPROVED:
                self._audit_log_gate_decided(
                    updated_gate,
                    task_id,
                    approved_by_roles=approved_by_roles,
                    rejected_by_role=None,
                )
                await self._handle_all_approved(updated_gate, task_id, stage_id)
            elif updated_gate.gate_decision == GateDecision.REJECTED:
                self._audit_log_gate_decided(
                    updated_gate,
                    task_id,
                    approved_by_roles=None,
                    rejected_by_role=rejected_by_role,
                )
                await self._handle_rejected(updated_gate, task_id, stage_id)

            return updated_gate.gate_decision

    async def _handle_all_approved(
        self,
        gate: InternalReviewGate,
        task_id: TaskId,
        stage_id: StageId,
    ) -> None:
        """ALL_APPROVED 遷移後: Task を次 Stage に進める。"""
        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            task_repo = self._task_repo_factory(session)
            workflow_repo = self._workflow_repo_factory(session)
            room_repo = self._room_repo_factory(session)

            task = await task_repo.find_by_id(task_id)
            if task is None:
                logger.error(
                    "event=handle_all_approved_task_not_found task_id=%s gate_id=%s",
                    task_id,
                    gate.id,
                )
                return

            transition_id, next_stage_id, next_stage_kind = await _DagTraversal.find_next_stage(
                task, stage_id, workflow_repo, room_repo
            )

            if next_stage_id is None:
                logger.error(
                    "event=handle_all_approved_no_next_stage task_id=%s stage_id=%s gate_id=%s",
                    task_id,
                    stage_id,
                    gate.id,
                )
                return

            old_status = task.status

            if next_stage_kind == StageKind.EXTERNAL_REVIEW:
                updated_task = task.request_external_review(updated_at=now)
            else:
                assert transition_id is not None  # next_stage_id が non-None なら必ず non-None
                updated_task = task.advance_to_next(
                    transition_id=transition_id,
                    by_owner_id=SYSTEM_AGENT_ID,
                    next_stage_id=next_stage_id,
                    updated_at=now,
                )

            await task_repo.save(updated_task)

        await self._event_bus.publish(
            TaskStateChangedEvent(
                aggregate_id=str(task_id),
                directive_id=str(task.directive_id),
                old_status=str(old_status),
                new_status=str(updated_task.status),
                room_id=str(task.room_id),
            )
        )

    async def _handle_rejected(
        self,
        gate: InternalReviewGate,
        task_id: TaskId,
        stage_id: StageId,
    ) -> None:
        """REJECTED 遷移後: Task を前段 WORK Stage に差し戻す（§確定 G）。"""
        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            task_repo = self._task_repo_factory(session)
            workflow_repo = self._workflow_repo_factory(session)
            room_repo = self._room_repo_factory(session)

            task = await task_repo.find_by_id(task_id)
            if task is None:
                logger.error(
                    "event=handle_rejected_task_not_found task_id=%s gate_id=%s",
                    task_id,
                    gate.id,
                )
                return

            prev_stage_id = await _DagTraversal.find_prev_work_stage_id(
                task, stage_id, workflow_repo, room_repo
            )

            old_status = task.status
            updated_task = task.rollback_to_stage(
                prev_stage_id=prev_stage_id,
                updated_at=now,
            )
            await task_repo.save(updated_task)

        await self._event_bus.publish(
            TaskStateChangedEvent(
                aggregate_id=str(task_id),
                directive_id=str(task.directive_id),
                old_status=str(old_status),
                new_status=str(updated_task.status),
                room_id=str(task.room_id),
            )
        )

    def _audit_log_gate_decided(
        self,
        gate: InternalReviewGate,
        task_id: TaskId,
        *,
        approved_by_roles: list[GateRole] | None = None,
        rejected_by_role: GateRole | None = None,
    ) -> None:
        """Gate 決定時に audit_log を記録する（§確定 J / OWASP A09）。

        含める情報: task_id / gate_id / decision / 各 Verdict の role と decision / timestamp。
        禁止: Verdict の comment（T3 対策）。
        """
        verdict_summary = [{"role": v.role, "decision": v.decision.value} for v in gate.verdicts]
        if gate.gate_decision == GateDecision.ALL_APPROVED:
            logger.info(
                "event=internal_review_gate_decided decision=ALL_APPROVED "
                "task_id=%s gate_id=%s approved_by_roles=%s verdicts=%s",
                task_id,
                gate.id,
                approved_by_roles,
                verdict_summary,
            )
        else:
            logger.info(
                "event=internal_review_gate_decided decision=REJECTED "
                "task_id=%s gate_id=%s rejected_by_role=%s verdicts=%s",
                task_id,
                gate.id,
                rejected_by_role,
                verdict_summary,
            )


__all__ = ["InternalReviewService"]
