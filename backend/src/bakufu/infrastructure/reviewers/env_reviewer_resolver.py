"""環境設定から ExternalReviewGate reviewer を解決するアダプタ。"""

from __future__ import annotations

import os
from uuid import UUID

from bakufu.application.ports.external_review_reviewer_resolver import (
    ExternalReviewReviewerResolver,
)
from bakufu.domain.task.task import Task
from bakufu.domain.value_objects import OwnerId, StageId, WorkflowId


class EnvExternalReviewReviewerResolver:
    """HTTP 実行環境の owner 設定を reviewer 解決ポートへ適合する。"""

    async def resolve(
        self,
        *,
        task: Task,
        workflow_id: WorkflowId,
        stage_id: StageId,
    ) -> OwnerId | None:
        del task, workflow_id, stage_id
        configured_owner_id = os.environ.get("BAKUFU_OWNER_ID", "")
        if not configured_owner_id:
            return None
        try:
            return UUID(configured_owner_id)
        except ValueError:
            return None


__all__ = ["EnvExternalReviewReviewerResolver", "ExternalReviewReviewerResolver"]
