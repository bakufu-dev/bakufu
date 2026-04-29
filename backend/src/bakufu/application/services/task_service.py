"""TaskService — Task Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from bakufu.application.ports.task_repository import TaskRepository


class TaskService:
    """Task Aggregate 操作の thin CRUD サービス骨格 (確定 F)。"""

    def __init__(self, repo: TaskRepository) -> None:
        self._repo = repo
