"""RoomRoleOverrideService — Room-level RoleProfile オーバーライド操作のサービス (Issue #120)。

role は ``str`` で受け取り、内部で ``Role`` StrEnum に変換する。変換失敗時は
:class:`~bakufu.application.exceptions.deliverable_template_exceptions.InvalidRoleError`
を raise し、HTTP 422 に変換される（role_profile_service と同パターン）。

refs は ``list[dict[str, Any]]`` で受け取り、内部で
:class:`~bakufu.domain.value_objects.DeliverableTemplateRef` に変換する。
これにより router が domain 型を import せず Q-3 制約を遵守できる。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.exceptions.deliverable_template_exceptions import InvalidRoleError
from bakufu.application.exceptions.room_exceptions import RoomArchivedError, RoomNotFoundError
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.application.ports.room_role_override_repository import RoomRoleOverrideRepository
from bakufu.domain.room.value_objects import RoomRoleOverride
from bakufu.domain.value_objects import DeliverableTemplateRef, RoomId
from bakufu.domain.value_objects.enums import Role


class RoomRoleOverrideService:
    """Room-level RoleProfile オーバーライドの CRUD サービス。

    session は write 操作の Unit-of-Work 管理に使用する。
    """

    def __init__(
        self,
        room_repo: RoomRepository,
        override_repo: RoomRoleOverrideRepository,
        session: AsyncSession,
    ) -> None:
        self._room_repo = room_repo
        self._override_repo = override_repo
        self._session = session

    async def upsert_override(
        self,
        room_id: RoomId,
        role: str,
        refs: list[dict[str, Any]],
    ) -> RoomRoleOverride:
        """RoomRoleOverride を UPSERT する。

        Args:
            room_id: 対象 Room の ID。
            role: Role StrEnum 値の文字列（例: ``"DEVELOPER"``）。
                無効値は :class:`InvalidRoleError` を raise する。
            refs: DeliverableTemplateRef の dict リスト
                （``{"template_id": UUID, "minimum_version": {"major": int, ...}}`` 形式）。

        Raises:
            InvalidRoleError: role が :class:`Role` StrEnum 外の値の場合。
            RoomNotFoundError: Room が存在しない場合。
            RoomArchivedError: Room がアーカイブ済みの場合。
            RoomRoleOverrideInvariantViolation: deliverable_template_refs に重複がある場合。
        """
        try:
            role_enum = Role(role)
        except ValueError as exc:
            raise InvalidRoleError(role) from exc

        refs_domain = tuple(DeliverableTemplateRef.model_validate(d) for d in refs)

        async with self._session.begin():
            room = await self._room_repo.find_by_id(room_id)
            if room is None:
                raise RoomNotFoundError(str(room_id))
            if room.archived:
                raise RoomArchivedError(str(room_id))

            override = RoomRoleOverride(
                room_id=room_id,
                role=role_enum,
                deliverable_template_refs=refs_domain,
            )
            await self._override_repo.save(override)
        return override

    async def delete_override(self, room_id: RoomId, role: str) -> None:
        """RoomRoleOverride を削除する。対象が存在しない場合は no-op。

        Args:
            room_id: 対象 Room の ID。
            role: Role StrEnum 値の文字列。無効値は :class:`InvalidRoleError` を raise する。

        Raises:
            InvalidRoleError: role が :class:`Role` StrEnum 外の値の場合。
            RoomNotFoundError: Room が存在しない場合。
            RoomArchivedError: Room がアーカイブ済みの場合。
        """
        try:
            role_enum = Role(role)
        except ValueError as exc:
            raise InvalidRoleError(role) from exc

        async with self._session.begin():
            room = await self._room_repo.find_by_id(room_id)
            if room is None:
                raise RoomNotFoundError(str(room_id))
            if room.archived:
                raise RoomArchivedError(str(room_id))

            await self._override_repo.delete(room_id, role_enum)

    async def find_overrides(self, room_id: RoomId) -> list[RoomRoleOverride]:
        """Room の全 RoomRoleOverride を返す（read-only）。

        Raises:
            RoomNotFoundError: Room が存在しない場合。
        """
        room = await self._room_repo.find_by_id(room_id)
        if room is None:
            raise RoomNotFoundError(str(room_id))
        return await self._override_repo.find_all_by_room(room_id)


__all__ = ["RoomRoleOverrideService"]
