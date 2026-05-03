"""InternalReviewGateQueryService — InternalReviewGate の参照系 application サービス。

audit trail 確認用の HTTP API (``GET /api/tasks/{task_id}/internal-review-gates``)
が利用するクエリサービス。Task の assigned_agent_ids に owner_id が含まれない場合は
IDOR 防御として例外を送出する（Finding 2 残存修正）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bakufu.application.exceptions.gate_exceptions import TaskAuthorizationError

if TYPE_CHECKING:
    from bakufu.application.ports.internal_review_gate_repository import (
        InternalReviewGateRepository,
    )
    from bakufu.application.ports.task_repository import TaskRepository
    from bakufu.domain.internal_review_gate.internal_review_gate import InternalReviewGate
    from bakufu.domain.value_objects import OwnerId, TaskId


class InternalReviewGateQueryService:
    """InternalReviewGate 参照系 application サービス。

    HTTP API 層が ``bakufu.infrastructure`` を直接 import せずに済むよう、
    repo Protocol だけに依存する application 層境界を提供する。
    """

    def __init__(
        self,
        gate_repo: InternalReviewGateRepository,
        task_repo: TaskRepository,
    ) -> None:
        self._gate_repo = gate_repo
        self._task_repo = task_repo

    async def find_all_by_task_with_authorization(
        self,
        task_id: TaskId,
        owner_id: OwnerId,
    ) -> list[InternalReviewGate]:
        """Task に紐づく全 InternalReviewGate を返す（IDOR 防御つき）。

        owner_id が Task の assigned_agent_ids に含まれない（または Task 不在）
        場合は :class:`GateAuthorizationError` を送出する。
        """
        task = await self._task_repo.find_by_id(task_id)
        if task is None or owner_id not in task.assigned_agent_ids:
            raise TaskAuthorizationError(task_id=task_id, owner_id=owner_id)
        return await self._gate_repo.find_all_by_task_id(task_id)
