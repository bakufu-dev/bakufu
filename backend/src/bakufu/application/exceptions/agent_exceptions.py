"""Agent application-layer exceptions（§確定 F）。

room_exceptions.py に暫定定義されていた AgentNotFoundError を正式移転し、
AgentNameAlreadyExistsError / AgentArchivedError を新規定義する。
"""

from __future__ import annotations


class AgentNotFoundError(Exception):
    """Agent が見つからない場合（MSG-AG-HTTP-001）。"""

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"Agent not found: {agent_id}")
        self.agent_id = agent_id


class AgentNameAlreadyExistsError(Exception):
    """同 Empire 内で同名 Agent が既に存在する場合（MSG-AG-HTTP-002 / 業務ルール R1-6）。"""

    def __init__(self, empire_id: str, name: str) -> None:
        super().__init__(f"Agent '{name}' already exists in empire {empire_id}")
        self.empire_id = empire_id
        self.name = name


class AgentArchivedError(Exception):
    """アーカイブ済み Agent への更新操作（MSG-AG-HTTP-003 / 業務ルール R1-5）。"""

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"Agent is archived: {agent_id}")
        self.agent_id = agent_id


__all__ = [
    "AgentArchivedError",
    "AgentNameAlreadyExistsError",
    "AgentNotFoundError",
]
