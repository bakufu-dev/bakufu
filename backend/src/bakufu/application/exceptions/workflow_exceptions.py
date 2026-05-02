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


class IllegalWorkflowStructureError(Exception):
    """Workflow DAG 構造が業務ルールに違反している場合（設計バグ、Fail Fast）。

    INTERNAL_REVIEW Stage の直前に WORK Stage が存在しない場合等に送出する。
    MSG-IRG-A003 に対応。
    """

    def __init__(self, task_id: str, stage_id: str, reason: str) -> None:
        super().__init__(
            f"[FAIL] Task {task_id} の前段 WORK Stage が Workflow DAG に存在しません"
            f"（stage_id: {stage_id}）。\n"
            f"Next: Workflow 設計を確認してください。INTERNAL_REVIEW Stage の直前に"
            f" WORK Stage が必要です。詳細: {reason}"
        )
        self.task_id = task_id
        self.stage_id = stage_id
        self.reason = reason


__all__ = [
    "IllegalWorkflowStructureError",
    "WorkflowArchivedError",
    "WorkflowIrreversibleError",
    "WorkflowNotFoundError",
    "WorkflowPresetNotFoundError",
]
