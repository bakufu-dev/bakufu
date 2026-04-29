"""WorkflowService — Workflow Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from bakufu.application.ports.workflow_repository import WorkflowRepository


class WorkflowService:
    """Workflow Aggregate 操作の thin CRUD サービス骨格 (確定 F)。"""

    def __init__(self, repo: WorkflowRepository) -> None:
        self._repo = repo
