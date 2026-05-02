"""InternalReviewService — INTERNAL_REVIEW Gate の CRUD と downstream 連携。

InternalReviewGateExecutor から呼び出される application 層サービス。
Gate の生成・Verdict 提出・downstream 連携
（Task 差し戻し / 次フェーズ遷移）を担う。

session_factory を使って各操作ごとに独立した AsyncSession を生成する（§確定 I）。
WeakValueDictionary[InternalGateId, asyncio.Lock] で Lost Update を防止する（§確定 H）。

設計書: docs/features/internal-review-gate/application/basic-design.md §モジュール契約
        docs/features/internal-review-gate/application/detailed-design.md §確定 F〜J
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.application.exceptions.gate_exceptions import (
    InternalReviewGateNotFoundError,
    UnauthorizedGateRoleError,
)
from bakufu.application.exceptions.task_exceptions import (
    IllegalTaskStateError,
    TaskNotFoundError,
)
from bakufu.application.exceptions.workflow_exceptions import IllegalWorkflowStructureError
from bakufu.application.ports.event_bus import EventBusPort
from bakufu.domain.events import TaskStateChangedEvent
from bakufu.domain.internal_review_gate.internal_review_gate import InternalReviewGate
from bakufu.domain.value_objects import (
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

    from bakufu.application.ports.room_repository import RoomRepository
    from bakufu.application.ports.workflow_repository import WorkflowRepository
    from bakufu.domain.task.task import Task

logger = logging.getLogger(__name__)


class InternalReviewService:
    """INTERNAL_REVIEW Gate の CRUD と downstream 連携を担う application サービス。

    InternalReviewGateExecutor から呼び出される。
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
        event_bus: EventBusPort,
    ) -> None:
        """サービスを初期化する。

        Args:
            session_factory: 各操作ごとに独立した AsyncSession を生成するファクトリ。
                InternalReviewGateExecutor が並列実行するため、セッション共有不可
                （§確定 I）。
            event_bus: Gate 状態変化 Domain Event 発行用。
        """
        self._session_factory = session_factory
        self._event_bus = event_bus
        # §確定 H: Gate ID ごとの Lost Update 防止 Lock。
        # WeakValueDictionary により Gate 確定後に GC で自動回収される。
        self._locks: WeakValueDictionary[InternalGateId, asyncio.Lock] = WeakValueDictionary()

    async def create_gate(
        self,
        task_id: TaskId,
        stage_id: StageId,
        required_gate_roles: frozenset[GateRole],
    ) -> InternalReviewGate | None:
        """Gate を生成し DB に保存して返す（§確定 F）。

        事前条件の確認順序:
        1. required_gate_roles が空集合 → None を返す（Gate を生成しない）
        2. Task.status != IN_PROGRESS → IllegalTaskStateError（Fail Fast）
        3. 既存 PENDING Gate が存在 → そのまま返す（べき等保証）
        4. 新規 Gate を生成・保存して返す

        Args:
            task_id: 対象 Task の識別子。
            stage_id: INTERNAL_REVIEW Stage の識別子。
            required_gate_roles: Gate に必要な GateRole 集合。

        Returns:
            新規 InternalReviewGate、または既存 PENDING Gate。
            required_gate_roles が空の場合は None。

        Raises:
            TaskNotFoundError: Task が存在しない場合。
            IllegalTaskStateError: Task.status != IN_PROGRESS の場合。
        """
        if not required_gate_roles:
            return None

        from bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository import (  # noqa: E501
            SqliteInternalReviewGateRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )

        async with self._session_factory() as session, session.begin():
            task_repo = SqliteTaskRepository(session)
            gate_repo = SqliteInternalReviewGateRepository(session)

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

        asyncio.Lock で同一 Gate への並列 submit_verdict を直列化（Lost Update 防止）。
        WeakValueDictionary により、Gate 確定後の Lock は GC で自動回収される。

        処理フロー:
        1. Gate read-modify-write（短トランザクション）
        2. Gate 決定（ALL_APPROVED / REJECTED）時の downstream 連携（別セッション）
        3. Gate 決定時の audit_log 記録（§確定 J）

        Args:
            gate_id: 対象 Gate の識別子。
            role: 提出する GateRole（gate.required_gate_roles に含まれること）。
            agent_id: 提出 Agent の識別子。
            decision: APPROVED または REJECTED。
            comment: 審査根拠・フィードバック（500 文字以内）。

        Returns:
            更新後の GateDecision（PENDING / ALL_APPROVED / REJECTED）。

        Raises:
            InternalReviewGateNotFoundError: Gate が存在しない場合。
            UnauthorizedGateRoleError: role が required_gate_roles に含まれない場合（T1）。
            InternalReviewGateInvariantViolation: domain 不変条件違反。
        """
        from bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository import (  # noqa: E501
            SqliteInternalReviewGateRepository,
        )

        async with self._locks.setdefault(gate_id, asyncio.Lock()):
            # Phase 1: Gate read-modify-write（短トランザクション）
            async with self._session_factory() as session, session.begin():
                gate_repo = SqliteInternalReviewGateRepository(session)
                gate = await gate_repo.find_by_id(gate_id)
                if gate is None:
                    raise InternalReviewGateNotFoundError(gate_id)

                # T1: GateRole 詐称防止（A01 対応）
                # gate.required_gate_roles に含まれない role からの提出を拒否する。
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
            task_id: TaskId = gate.task_id
            stage_id: StageId = gate.stage_id

            if updated_gate.gate_decision == GateDecision.ALL_APPROVED:
                # §確定 J: audit_log — ALL_APPROVED 遷移（comment は含めない / T3）
                self._audit_log_gate_decided(
                    gate=updated_gate,
                    task_id=task_id,
                    approved_by_roles=[v.role for v in updated_gate.verdicts],
                )
                await self._handle_all_approved(updated_gate, task_id, stage_id)
            elif updated_gate.gate_decision == GateDecision.REJECTED:
                # 最初の REJECTED Verdict の role を特定する。
                rejected_by_role: GateRole = next(
                    (
                        v.role
                        for v in updated_gate.verdicts
                        if v.decision == VerdictDecision.REJECTED
                    ),
                    role,  # fallback: 今回提出の role
                )
                # §確定 J: audit_log — REJECTED 遷移（comment は含めない / T3）
                self._audit_log_gate_decided(
                    gate=updated_gate,
                    task_id=task_id,
                    rejected_by_role=rejected_by_role,
                )
                await self._handle_rejected(updated_gate, task_id, stage_id)

            return updated_gate.gate_decision

    # ---- プライベートメソッド: downstream 連携 -----------------------------------------

    async def _handle_all_approved(
        self,
        gate: InternalReviewGate,
        task_id: TaskId,
        stage_id: StageId,
    ) -> None:
        """ALL_APPROVED 遷移後: Task を次 Stage に進める。

        Workflow DAG で INTERNAL_REVIEW Stage の次 Stage を特定し、
        Task.advance_to_next() で遷移する。次 Stage が EXTERNAL_REVIEW の場合は
        Task.request_external_review() を呼んで AWAITING_EXTERNAL_REVIEW に遷移する。
        ExternalReviewGate の生成は Outbox Dispatcher（M6-A）に委ねる。
        """
        from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
            SqliteRoomRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
            SqliteWorkflowRepository,
        )

        now = datetime.now(UTC)
        async with self._session_factory() as session:
            task_repo = SqliteTaskRepository(session)
            workflow_repo = SqliteWorkflowRepository(session)
            room_repo = SqliteRoomRepository(session)

            async with session.begin():
                task = await task_repo.find_by_id(task_id)
                if task is None:
                    logger.error(
                        "event=handle_all_approved_task_not_found task_id=%s gate_id=%s",
                        task_id,
                        gate.id,
                    )
                    return

                # 次 Stage を Workflow DAG から特定する。
                next_stage_id, next_stage_kind = await self._find_next_stage(
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
                    # 次が EXTERNAL_REVIEW → AWAITING_EXTERNAL_REVIEW に遷移。
                    # ExternalReviewGate 生成は Outbox Dispatcher（M6-A）が担う。
                    updated_task = task.request_external_review(updated_at=now)
                else:
                    # 次が WORK 等 → IN_PROGRESS のまま current_stage_id を進める。
                    updated_task = task.advance_to_next(
                        transition_id=uuid4(),
                        by_owner_id=UUID(int=0),  # system sentinel（audit では削除される）
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
        """REJECTED 遷移後: Task を前段 WORK Stage に差し戻す（§確定 G）。

        Workflow DAG を逆引きして前段 WORK Stage を特定し、
        Task.advance_to_next() で差し戻す（IN_PROGRESS 状態のまま current_stage_id を変更）。
        """
        from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
            SqliteRoomRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )
        from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
            SqliteWorkflowRepository,
        )

        now = datetime.now(UTC)
        async with self._session_factory() as session:
            task_repo = SqliteTaskRepository(session)
            workflow_repo = SqliteWorkflowRepository(session)
            room_repo = SqliteRoomRepository(session)

            async with session.begin():
                task = await task_repo.find_by_id(task_id)
                if task is None:
                    logger.error(
                        "event=handle_rejected_task_not_found task_id=%s gate_id=%s",
                        task_id,
                        gate.id,
                    )
                    return

                prev_stage_id = await self._find_prev_work_stage_id(
                    task, stage_id, workflow_repo, room_repo
                )

                old_status = task.status
                updated_task = task.advance_to_next(
                    transition_id=uuid4(),
                    by_owner_id=UUID(int=0),  # system sentinel（audit では削除される）
                    next_stage_id=prev_stage_id,
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

    async def _find_next_stage(
        self,
        task: Task,
        stage_id: StageId,
        workflow_repo: WorkflowRepository,
        room_repo: RoomRepository,
    ) -> tuple[StageId | None, StageKind | None]:
        """Workflow DAG で INTERNAL_REVIEW Stage の次 Stage を特定する（§確定 G）。

        Returns:
            (next_stage_id, next_stage_kind) のタプル。次 Stage が存在しない場合は
            (None, None) を返す。
        """

        room = await room_repo.find_by_id(task.room_id)
        if room is None:
            return None, None
        workflow = await workflow_repo.find_by_id(room.workflow_id)
        if workflow is None:
            return None, None

        # INTERNAL_REVIEW からの outgoing transition を探す。
        next_transition = next(
            (t for t in workflow.transitions if t.from_stage_id == stage_id),
            None,
        )
        if next_transition is None:
            return None, None

        stages_by_id = {s.id: s for s in workflow.stages}
        next_stage = stages_by_id.get(next_transition.to_stage_id)
        if next_stage is None:
            return next_transition.to_stage_id, None

        return next_stage.id, next_stage.kind

    async def _find_prev_work_stage_id(
        self,
        task: Task,
        stage_id: StageId,
        workflow_repo: WorkflowRepository,
        room_repo: RoomRepository,
    ) -> StageId:
        """Workflow DAG を逆引きして前段 WORK Stage を特定する（§確定 G）。

        stage_id（INTERNAL_REVIEW Stage）に to_stage_id が一致する transition を逆引きし、
        from_stage が WORK kind であるものを返す。

        Raises:
            IllegalWorkflowStructureError: 前段に WORK Stage が存在しない場合（設計バグ）。
        """
        room = await room_repo.find_by_id(task.room_id)
        if room is None:
            raise IllegalWorkflowStructureError(
                task_id=str(task.id),
                stage_id=str(stage_id),
                reason="Room が見つかりません",
            )
        workflow = await workflow_repo.find_by_id(room.workflow_id)
        if workflow is None:
            raise IllegalWorkflowStructureError(
                task_id=str(task.id),
                stage_id=str(stage_id),
                reason="Workflow が見つかりません",
            )

        # stage_id に to_stage_id が一致する transitions を逆引きする。
        incoming_transitions = [t for t in workflow.transitions if t.to_stage_id == stage_id]
        stages_by_id = {s.id: s for s in workflow.stages}

        for transition in incoming_transitions:
            from_stage = stages_by_id.get(transition.from_stage_id)
            if from_stage is not None and from_stage.kind == StageKind.WORK:
                return from_stage.id

        raise IllegalWorkflowStructureError(
            task_id=str(task.id),
            stage_id=str(stage_id),
            reason=(
                f"前段に kind=WORK の Stage が見つかりません。"
                f"逆引き対象 from_stage_id: "
                f"{[str(t.from_stage_id) for t in incoming_transitions]}"
            ),
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
        禁止: Verdict の comment（T3 対策 — raw 文字列は MaskedText 永続化前は非マスク）。
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
