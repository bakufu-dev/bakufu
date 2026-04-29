"""Workflow application-layer exceptions (確定 F)."""

from __future__ import annotations


class WorkflowNotFoundError(Exception):
    """Workflow が見つからない場合 (MSG-WF-HTTP-001)。"""

    def __init__(self, workflow_id: str) -> None:
        super().__init__(f"Workflow not found: {workflow_id}")
        self.workflow_id = workflow_id


class WorkflowArchivedError(Exception):
    """アーカイブ済み Workflow への更新操作 (MSG-WF-HTTP-002)。"""

    def __init__(self, workflow_id: str, kind: str = "update") -> None:
        super().__init__(f"Workflow is archived: {workflow_id}")
        self.workflow_id = workflow_id
        self.kind = kind


class WorkflowPresetNotFoundError(Exception):
    """指定したプリセット名が存在しない場合 (MSG-WF-HTTP-004)。"""

    def __init__(self, preset_name: str) -> None:
        super().__init__(f"Workflow preset not found: {preset_name}")
        self.preset_name = preset_name


class WorkflowIrreversibleError(Exception):
    """notify_channels がマスク済みの Workflow への PATCH 拒否 (MSG-WF-HTTP-008)。

    EXTERNAL_REVIEW Stage を含む Workflow は永続化時に notify_channels の
    webhook URL がマスクされる（§確定 H 不可逆性）。その後 find_by_id が
    masked URL を pydantic で再バリデーションして ValidationError を送出した場合、
    application 層がここで変換して 409 に写す。
    """

    def __init__(self, workflow_id: str) -> None:
        super().__init__(
            f"Workflow {workflow_id} contains masked notify_channels and cannot be modified."
        )
        self.workflow_id = workflow_id


__all__ = [
    "WorkflowArchivedError",
    "WorkflowIrreversibleError",
    "WorkflowNotFoundError",
    "WorkflowPresetNotFoundError",
]
