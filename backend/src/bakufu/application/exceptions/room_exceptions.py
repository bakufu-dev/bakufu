"""Room application-layer exceptions (確定 F)."""

from __future__ import annotations

from bakufu.application.exceptions.workflow_exceptions import WorkflowNotFoundError


class RoomNotFoundError(Exception):
    """Room が見つからない場合 (MSG-RM-HTTP-002)。"""

    def __init__(self, room_id: str) -> None:
        super().__init__(f"Room not found: {room_id}")
        self.room_id = room_id


class RoomNameAlreadyExistsError(Exception):
    """同 Empire 内で同名 Room が既に存在する場合 (MSG-RM-HTTP-001 / 業務ルール R1-8)。"""

    def __init__(self, name: str, empire_id: str) -> None:
        super().__init__(f"Room '{name}' already exists in empire {empire_id}")
        self.name = name
        self.empire_id = empire_id


class RoomArchivedError(Exception):
    """アーカイブ済み Room への更新 / Agent 操作 (MSG-RM-HTTP-003 / 業務ルール R1-5)。"""

    def __init__(self, room_id: str) -> None:
        super().__init__(f"Room is archived: {room_id}")
        self.room_id = room_id


class AgentNotFoundError(Exception):
    """Agent が見つからない場合 (MSG-RM-HTTP-004)。

    agent-http-api PR で定義済みの場合はそちらから import する。
    本 PR 時点で未定義のため暫定定義 (確定 F §Q-OPEN-1)。
    """

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"Agent not found: {agent_id}")
        self.agent_id = agent_id


__all__ = [
    "AgentNotFoundError",
    "RoomArchivedError",
    "RoomNameAlreadyExistsError",
    "RoomNotFoundError",
    "WorkflowNotFoundError",
]
