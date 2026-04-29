"""Task application-layer exceptions."""

from __future__ import annotations

from bakufu.domain.value_objects import TaskId, TaskStatus


class TaskNotFoundError(Exception):
    """Task が見つからない場合（MSG-TS-HTTP-001）。"""

    def __init__(self, task_id: TaskId | str) -> None:
        super().__init__(f"Task not found: {task_id}")
        self.task_id = str(task_id)


class TaskStateConflictError(Exception):
    """Task の現在状態では要求された操作を実行できない場合（MSG-TS-HTTP-002）。"""

    def __init__(
        self,
        task_id: TaskId | str,
        current_status: TaskStatus | str,
        action: str,
        message: str | None = None,
    ) -> None:
        super().__init__(message or f"Task state conflict: {task_id}")
        self.task_id = str(task_id)
        self.current_status = str(current_status)
        self.action = action


__all__ = [
    "TaskNotFoundError",
    "TaskStateConflictError",
]
