"""DagTraversal — Workflow DAG traversal ヘルパ（内部モジュール）。

InternalReviewService から委譲を受け、DAG 逆引き・次 Stage 探索を担う。
application 層のポートのみに依存し、infrastructure 具象クラスを import しない。

設計書: docs/features/internal-review-gate/application/detailed-design.md §確定 G
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bakufu.application.exceptions.workflow_exceptions import IllegalWorkflowStructureError
from bakufu.domain.value_objects import StageId, StageKind, TransitionId

if TYPE_CHECKING:
    from bakufu.application.ports.room_repository import RoomRepository
    from bakufu.application.ports.workflow_repository import WorkflowRepository
    from bakufu.domain.task.task import Task

logger = logging.getLogger(__name__)


class DagTraversal:
    """Workflow DAG traversal ヘルパ（InternalReviewService 内部クラス）。

    _find_next_stage / _find_prev_work_stage_id を InternalReviewService から
    分離することで、DAG 探索ロジックを単独でテスト・変更可能にする。
    """

    @staticmethod
    async def find_next_stage(
        task: Task,
        stage_id: StageId,
        workflow_repo: WorkflowRepository,
        room_repo: RoomRepository,
    ) -> tuple[TransitionId | None, StageId | None, StageKind | None]:
        """Workflow DAG で INTERNAL_REVIEW Stage の次 Stage を特定する（§確定 G）。

        Returns:
            (transition_id, next_stage_id, next_stage_kind) のタプル。
            次 Stage が存在しない場合は (None, None, None) を返す。
            transition_id は ``advance_to_next()`` 監査引数に渡す正当な Transition ID。
        """
        room = await room_repo.find_by_id(task.room_id)
        if room is None or room.workflow_id is None:
            return None, None, None
        workflow = await workflow_repo.find_by_id(room.workflow_id)
        if workflow is None:
            return None, None, None

        next_transition = next(
            (t for t in workflow.transitions if t.from_stage_id == stage_id),
            None,
        )
        if next_transition is None:
            return None, None, None

        stages_by_id = {s.id: s for s in workflow.stages}
        next_stage = stages_by_id.get(next_transition.to_stage_id)
        if next_stage is None:
            return next_transition.id, next_transition.to_stage_id, None

        return next_transition.id, next_stage.id, next_stage.kind

    @staticmethod
    async def find_prev_work_stage_id(
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
        if room.workflow_id is None:
            raise IllegalWorkflowStructureError(
                task_id=str(task.id),
                stage_id=str(stage_id),
                reason="Room.workflow_id が未設定です",
            )
        workflow = await workflow_repo.find_by_id(room.workflow_id)
        if workflow is None:
            raise IllegalWorkflowStructureError(
                task_id=str(task.id),
                stage_id=str(stage_id),
                reason="Workflow が見つかりません",
            )

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
