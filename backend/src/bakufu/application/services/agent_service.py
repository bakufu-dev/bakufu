"""AgentService — Agent Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from bakufu.application.ports.agent_repository import AgentRepository


class AgentService:
    """Agent Aggregate 操作の thin CRUD サービス骨格 (確定 F)。"""

    def __init__(self, repo: AgentRepository) -> None:
        self._repo = repo
