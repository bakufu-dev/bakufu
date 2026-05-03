"""ExternalReviewGateService — ExternalReviewGate Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from bakufu.application.exceptions.gate_exceptions import (
    GateAlreadyDecidedError,
    GateAuthorizationError,
    GateNotFoundError,
)
from bakufu.application.ports.deliverable_template_repository import (
    DeliverableTemplateRepository,
)
from bakufu.application.ports.event_bus import EventBusPort
from bakufu.application.ports.external_review_gate_repository import (
    ExternalReviewGateRepository,
)
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.application.ports.workflow_repository import WorkflowRepository
from bakufu.application.security import masking
from bakufu.domain.events import ExternalReviewGateStateChangedEvent
from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.external_review_gate.gate import ExternalReviewGate
from bakufu.domain.value_objects import (
    AcceptanceCriterion,
    Deliverable,
    DeliverableTemplateId,
    GateId,
    OwnerId,
    StageId,
    TaskId,
    TaskStatus,
    TransitionCondition,
)


class ExternalReviewGateService:
    """ExternalReviewGate Aggregate 操作の application 層サービス。

    reviewer_id 照合責務の凍結: approve / reject / cancel の各メソッドは
    Service 内で ``gate.reviewer_id != reviewer_id`` を照合し、
    GateAuthorizationError を raise する（basic-design.md §確定 UC4 参照）。
    save() はこのクラスに含めない。呼び出し元 router が UoW 内で管理する
    （detailed-design.md §確定E）。

    criteria 収集責務（§確定 J、R1-J）: create() は Stage.required_deliverables
    に紐づく各 DeliverableTemplate.acceptance_criteria を引き込み、
    ``required_deliverable_criteria`` として Gate に渡す。
    """

    def __init__(
        self,
        repo: ExternalReviewGateRepository,
        template_repo: DeliverableTemplateRepository,
        event_bus: EventBusPort,
        task_repo: TaskRepository | None = None,
        room_repo: RoomRepository | None = None,
        workflow_repo: WorkflowRepository | None = None,
    ) -> None:
        self._repo = repo
        self._template_repo = template_repo
        self._event_bus = event_bus
        # 後処理 (apply_post_approve_task_state_update) で利用する。HTTP 経路以外の
        # 呼び出し元は Task 側状態遷移を行わないため Optional として注入する。
        self._task_repo = task_repo
        self._room_repo = room_repo
        self._workflow_repo = workflow_repo

    async def create(
        self,
        *,
        task_id: TaskId,
        stage_id: StageId,
        deliverable_snapshot: Deliverable,
        reviewer_id: OwnerId,
        required_deliverable_template_ids: list[DeliverableTemplateId],
        created_at: datetime,
    ) -> ExternalReviewGate:
        """PENDING の ExternalReviewGate を生成して返す（保存は呼び出し元の責務）。

        Stage.required_deliverables に紐づく各 DeliverableTemplate の
        acceptance_criteria を引き込み、``required_deliverable_criteria`` として
        Gate に snapshot する（§確定 J、R1-J）。

        Args:
            task_id: 対象 Task の ID。
            stage_id: EXTERNAL_REVIEW kind の Stage ID。
            deliverable_snapshot: Gate 生成時の成果物スナップショット（§確定 D）。
            reviewer_id: 人間レビュワー（CEO）の OwnerId。
            required_deliverable_template_ids: Stage.required_deliverables から
                収集した DeliverableTemplateId のリスト。各 template の
                acceptance_criteria を収集するために使用する。
            created_at: Gate 起票時刻（呼び出し元が datetime.now(UTC) で生成）。

        Returns:
            PENDING 状態の新規 ExternalReviewGate。呼び出し元が
            ``async with session.begin():`` 内で ``save()`` する。
        """
        # Stage.required_deliverables から各 DeliverableTemplate の acceptance_criteria
        # を収集する（§確定 J - GateService の責務）。
        # 全 criteria をそのまま順序通り tuple に変換する（重複除去は行わない）。
        # dangling ref（template が見つからない場合）は silently skip する（MVP 方針）。
        all_criteria: list[AcceptanceCriterion] = []
        for template_id in required_deliverable_template_ids:
            template = await self._template_repo.find_by_id(template_id)
            if template is None:
                continue
            all_criteria.extend(template.acceptance_criteria)

        return ExternalReviewGate(
            id=uuid4(),
            task_id=task_id,
            stage_id=stage_id,
            deliverable_snapshot=deliverable_snapshot,
            reviewer_id=reviewer_id,
            required_deliverable_criteria=tuple(all_criteria),
            created_at=created_at,
        )

    async def find_by_id_or_raise(self, gate_id: GateId) -> ExternalReviewGate:
        """gate_id の Gate を返す。不在の場合は GateNotFoundError を raise。"""
        gate = await self._repo.find_by_id(gate_id)
        if gate is None:
            raise GateNotFoundError(gate_id)
        return gate

    async def find_pending_for_reviewer(self, reviewer_id: OwnerId) -> list[ExternalReviewGate]:
        """reviewer_id の全 PENDING Gate を返す（created_at DESC, id DESC）。"""
        return await self._repo.find_pending_by_reviewer(reviewer_id)

    async def find_by_task(self, task_id: TaskId) -> list[ExternalReviewGate]:
        """task_id の全 Gate を時系列昇順で返す（created_at ASC, id ASC）。"""
        return await self._repo.find_by_task_id(task_id)

    async def approve(
        self,
        gate: ExternalReviewGate,
        reviewer_id: OwnerId,
        comment: str,
        decided_at: datetime,
    ) -> ExternalReviewGate:
        """Gate を承認する。

        reviewer_id 照合（→ GateAuthorizationError 403）を Service 内で実行した後、
        domain の gate.approve() に委譲する。
        ExternalReviewGateInvariantViolation(kind='decision_already_decided')
        → GateAlreadyDecidedError (409) に変換する。save() は呼び出し元 router が
        async with session.begin() 内で行う（§確定E）。

        domain 操作成功後に ``ExternalReviewGateStateChangedEvent`` を publish する。
        ``reviewer_comment`` は ``masking.mask()`` 適用済みの値を渡す（§確定 F）。
        """
        if gate.reviewer_id != reviewer_id:
            raise GateAuthorizationError(
                gate_id=gate.id,
                reviewer_id=reviewer_id,
                expected_reviewer_id=gate.reviewer_id,
            )
        try:
            updated = gate.approve(by_owner_id=reviewer_id, comment=comment, decided_at=decided_at)
        except ExternalReviewGateInvariantViolation as exc:
            if exc.kind == "decision_already_decided":
                raise GateAlreadyDecidedError(
                    gate_id=gate.id,
                    current_decision=gate.decision,
                ) from exc
            raise
        # domain 操作成功後に publish（§確定 F: reviewer_comment は masking.mask() 適用）
        await self._event_bus.publish(
            ExternalReviewGateStateChangedEvent(
                aggregate_id=str(gate.id),
                task_id=str(gate.task_id),
                old_status=str(gate.decision),
                new_status=str(updated.decision),
                reviewer_comment=masking.mask(comment),
            )
        )
        return updated

    async def reject(
        self,
        gate: ExternalReviewGate,
        reviewer_id: OwnerId,
        feedback_text: str,
        decided_at: datetime,
    ) -> ExternalReviewGate:
        """Gate を差し戻す。

        approve と同構造。domain の gate.reject() に委譲する。

        domain 操作成功後に ``ExternalReviewGateStateChangedEvent`` を publish する。
        ``reviewer_comment`` は ``masking.mask()`` 適用済みの値を渡す（§確定 F）。
        """
        if gate.reviewer_id != reviewer_id:
            raise GateAuthorizationError(
                gate_id=gate.id,
                reviewer_id=reviewer_id,
                expected_reviewer_id=gate.reviewer_id,
            )
        try:
            updated = gate.reject(
                by_owner_id=reviewer_id, comment=feedback_text, decided_at=decided_at
            )
        except ExternalReviewGateInvariantViolation as exc:
            if exc.kind == "decision_already_decided":
                raise GateAlreadyDecidedError(
                    gate_id=gate.id,
                    current_decision=gate.decision,
                ) from exc
            raise
        # domain 操作成功後に publish（§確定 F: reviewer_comment は masking.mask() 適用）
        await self._event_bus.publish(
            ExternalReviewGateStateChangedEvent(
                aggregate_id=str(gate.id),
                task_id=str(gate.task_id),
                old_status=str(gate.decision),
                new_status=str(updated.decision),
                reviewer_comment=masking.mask(feedback_text),
            )
        )
        return updated

    async def cancel(
        self,
        gate: ExternalReviewGate,
        reviewer_id: OwnerId,
        reason: str,
        decided_at: datetime,
    ) -> ExternalReviewGate:
        """Gate をキャンセルする。

        approve と同構造。domain の gate.cancel() に委譲する。
        """
        if gate.reviewer_id != reviewer_id:
            raise GateAuthorizationError(
                gate_id=gate.id,
                reviewer_id=reviewer_id,
                expected_reviewer_id=gate.reviewer_id,
            )
        try:
            return gate.cancel(by_owner_id=reviewer_id, reason=reason, decided_at=decided_at)
        except ExternalReviewGateInvariantViolation as exc:
            if exc.kind == "decision_already_decided":
                raise GateAlreadyDecidedError(
                    gate_id=gate.id,
                    current_decision=gate.decision,
                ) from exc
            raise

    async def apply_post_approve_task_state_update(
        self,
        gate: ExternalReviewGate,
        reviewer_owner_id: OwnerId,
        now: datetime,
    ) -> None:
        """Gate 承認後の Task 状態遷移を適用する（§暫定実装）。

        Outbox Dispatcher 未実装のため、approve_gate router からの直接呼び出しで
        Task の AWAITING_EXTERNAL_REVIEW → IN_PROGRESS → (DONE | 次 Stage) 遷移を
        担う。Workflow の Transition を辿って次 Stage を決定する。

        この処理に必要な ``task_repo`` / ``room_repo`` / ``workflow_repo`` が未注入
        の場合は何もしない（HTTP 経路以外からは Task 側遷移は行わない設計）。
        """
        if self._task_repo is None or self._room_repo is None or self._workflow_repo is None:
            return
        task = await self._task_repo.find_by_id(gate.task_id)
        if task is None or task.status != TaskStatus.AWAITING_EXTERNAL_REVIEW:
            return

        next_stage_id: StageId | None = None
        room = await self._room_repo.find_by_id(task.room_id)
        if room is not None and room.workflow_id is not None:
            workflow = await self._workflow_repo.find_by_id(room.workflow_id)
            if workflow is not None:
                for transition in workflow.transitions:
                    if (
                        transition.from_stage_id == gate.stage_id
                        and transition.condition == TransitionCondition.APPROVED
                    ):
                        next_stage_id = transition.to_stage_id
                        break

        if next_stage_id is None:
            # 次 Stage なし → AWAITING_EXTERNAL_REVIEW → IN_PROGRESS → DONE
            # gate.stage_id（EXTERNAL_REVIEW Stage）を current_stage_id として保持し、
            # Task が最後に完了した Stage を記録する（§確定 K）。
            in_progress_task = task.approve_review(
                transition_id=uuid4(),
                by_owner_id=reviewer_owner_id,
                next_stage_id=gate.stage_id,
                updated_at=now,
            )
            completed_task = in_progress_task.complete(
                transition_id=uuid4(),
                by_owner_id=reviewer_owner_id,
                updated_at=now,
            )
            await self._task_repo.save(completed_task)
        else:
            # 次 Stage あり → Task を IN_PROGRESS に（StageWorker が別途処理）
            advanced_task = task.approve_review(
                transition_id=uuid4(),
                by_owner_id=reviewer_owner_id,
                next_stage_id=next_stage_id,
                updated_at=now,
            )
            await self._task_repo.save(advanced_task)

    async def save(self, gate: ExternalReviewGate) -> None:
        """Gate を永続化する。

        呼び出し元の router handler が `async with session.begin():` 内で
        本メソッドを呼ぶこと（detailed-design.md §確定E）。
        Service 内でトランザクション管理を行わない設計。
        """
        await self._repo.save(gate)
