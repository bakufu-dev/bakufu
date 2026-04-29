"""ExternalReviewGate reviewer 解決ポート。"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.task.task import Task
from bakufu.domain.value_objects import OwnerId, StageId, WorkflowId


class ExternalReviewReviewerResolver(Protocol):
    """Workflow/Stage 文脈から Gate reviewer を解決する application ポート。"""

    async def resolve(
        self,
        *,
        task: Task,
        workflow_id: WorkflowId,
        stage_id: StageId,
    ) -> OwnerId | None:
        """Gate reviewer を返す。解決不能なら Gate を生成しない。"""
        ...


__all__ = ["ExternalReviewReviewerResolver"]
