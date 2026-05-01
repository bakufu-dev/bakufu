"""RoomRoleOverride Repository ポート。"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.room.value_objects import RoomRoleOverride
from bakufu.domain.value_objects import RoomId
from bakufu.domain.value_objects.enums import Role


class RoomRoleOverrideRepository(Protocol):
    """Room-level RoleProfile オーバーライドの永続化契約。
    PK は (room_id, role)。UPSERT / SELECT / DELETE を提供する。
    """

    async def find_by_room_and_role(
        self, room_id: RoomId, role: Role
    ) -> RoomRoleOverride | None: ...

    async def find_all_by_room(self, room_id: RoomId) -> list[RoomRoleOverride]: ...

    async def save(self, override: RoomRoleOverride) -> None: ...

    async def delete(self, room_id: RoomId, role: Role) -> None: ...


__all__ = ["RoomRoleOverrideRepository"]
