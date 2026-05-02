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


class TaskAuthorizationError(Exception):
    """Task 操作の application 層認可境界違反（MSG-TS-HTTP-004）。"""

    def __init__(self, task_id: TaskId | str, action: str, reason: str) -> None:
        super().__init__(reason)
        self.task_id = str(task_id)
        self.action = action
        self.reason = reason


class IllegalTaskStateError(Exception):
    """Task が操作に対して不正な状態にある場合（Fail Fast）。

    Gate 生成時に Task が IN_PROGRESS 以外の状態の場合に送出する。
    MSG-IRG-A001 的な状況。
    """

    def __init__(
        self, task_id: TaskId | str, current_status: TaskStatus | str, action: str
    ) -> None:
        super().__init__(
            f"[FAIL] Task {task_id} は action '{action}' を実行できる状態にありません"
            f"（current_status={current_status}）。\n"
            f"Next: Task が IN_PROGRESS 状態になってから再試行してください。"
        )
        self.task_id = str(task_id)
        self.current_status = str(current_status)
        self.action = action


__all__ = [
    "IllegalTaskStateError",
    "TaskAuthorizationError",
    "TaskNotFoundError",
    "TaskStateConflictError",
]
