"""Room application-layer exceptions (確定 F)."""

from __future__ import annotations

from bakufu.application.exceptions.agent_exceptions import AgentNotFoundError
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


class RoomDeliverableMismatch:
    """不足 deliverable の単位情報。"""

    __slots__ = ("stage_id", "stage_name", "template_id")

    def __init__(self, stage_id: str, stage_name: str, template_id: str) -> None:
        self.stage_id = stage_id
        self.stage_name = stage_name
        self.template_id = template_id


class RoomDeliverableMatchingError(Exception):
    """Room-role マッチング検証失敗 (MSG-RM-MATCH-001)。

    validate_coverage が不足 deliverable を返し、assign_agent が raise する。
    """

    def __init__(
        self,
        room_id: str,
        role: str,
        missing: list[RoomDeliverableMismatch],
    ) -> None:
        n = len(missing)
        missing_strs = ", ".join(f"{m.stage_name} → {m.template_id}" for m in missing)
        message = (
            f"[FAIL] Room {room_id} の役割 {role} は {n} 件の必須成果物テンプレートを"
            f"提供できません。不足: {missing_strs}\n"
            f"Next: RoleProfile の deliverable_template_refs にテンプレートを追加するか、"
            f"Room レベルのオーバーライドを設定してください"
            f"（PUT /api/rooms/{room_id}/role-overrides/{role}）。"
        )
        super().__init__(message)
        self.room_id = room_id
        self.role = role
        self.missing = missing
        self.message = message


__all__ = [
    "AgentNotFoundError",
    "RoomArchivedError",
    "RoomDeliverableMatchingError",
    "RoomDeliverableMismatch",
    "RoomNameAlreadyExistsError",
    "RoomNotFoundError",
    "WorkflowNotFoundError",
]
