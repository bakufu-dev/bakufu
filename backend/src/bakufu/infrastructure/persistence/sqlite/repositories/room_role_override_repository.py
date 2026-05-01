""":class:`bakufu.application.ports.RoomRoleOverrideRepository` の SQLite アダプタ (Issue #120)。

PK は (room_id, role) — id カラムなし。
UPSERT / SELECT / DELETE を実装する。

リポジトリは ``session.commit()`` / ``session.rollback()`` を **決して** 呼ばない。
呼び元のサービスが ``async with session.begin():`` を実行することで、UoW 境界を
管理する。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.room.value_objects import RoomRoleOverride
from bakufu.domain.value_objects import DeliverableTemplateRef, RoomId
from bakufu.domain.value_objects.enums import Role
from bakufu.infrastructure.persistence.sqlite.tables.room_role_overrides import RoomRoleOverrideRow


class SqliteRoomRoleOverrideRepository:
    """:class:`RoomRoleOverrideRepository` の SQLite 実装。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_room_and_role(
        self,
        room_id: RoomId,
        role: Role,
    ) -> RoomRoleOverride | None:
        """``(room_id, role)`` に対応する RoomRoleOverride を返す。該当なしは ``None``。"""
        stmt = select(RoomRoleOverrideRow).where(
            RoomRoleOverrideRow.room_id == room_id,
            RoomRoleOverrideRow.role == role.value,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return self._from_row(row)

    async def find_all_by_room(self, room_id: RoomId) -> list[RoomRoleOverride]:
        """指定 Room の全 RoomRoleOverride を ``ORDER BY role ASC`` で返す。"""
        stmt = (
            select(RoomRoleOverrideRow)
            .where(RoomRoleOverrideRow.room_id == room_id)
            .order_by(RoomRoleOverrideRow.role)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [self._from_row(row) for row in rows]

    async def save(self, override: RoomRoleOverride) -> None:
        """``room_role_overrides`` テーブルへの UPSERT で永続化する。

        PK (room_id, role) 衝突時に deliverable_template_refs_json と updated_at を更新する。
        """
        row = self._to_row(override)
        upsert_stmt = sqlite_insert(RoomRoleOverrideRow).values(row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["room_id", "role"],
            set_={
                "deliverable_template_refs_json": (
                    upsert_stmt.excluded.deliverable_template_refs_json
                ),
                "updated_at": upsert_stmt.excluded.updated_at,
            },
        )
        await self._session.execute(upsert_stmt)

    async def delete(self, room_id: RoomId, role: Role) -> None:
        """指定 (room_id, role) の行を削除する。存在しない場合は no-op。"""
        await self._session.execute(
            text("DELETE FROM room_role_overrides WHERE room_id = :room_id AND role = :role"),
            {
                "room_id": str(room_id).replace("-", ""),
                "role": role.value,
            },
        )

    # ---- private domain ↔ row converters --------------------------------
    def _to_row(self, override: RoomRoleOverride) -> dict[str, Any]:
        """``override`` を ``room_role_overrides`` 行の dict に変換する。"""
        now = datetime.now(UTC)
        return {
            "room_id": override.room_id,
            "role": override.role.value,
            "deliverable_template_refs_json": [
                r.model_dump(mode="json") for r in override.deliverable_template_refs
            ],
            "created_at": now,
            "updated_at": now,
        }

    def _from_row(self, row: RoomRoleOverrideRow) -> RoomRoleOverride:
        """行から :class:`RoomRoleOverride` VO を水和する。"""
        ref_payloads = cast(
            "list[dict[str, Any]]",
            row.deliverable_template_refs_json or [],
        )
        deliverable_template_refs = tuple(
            DeliverableTemplateRef.model_validate(d) for d in ref_payloads
        )
        return RoomRoleOverride.model_validate(
            {
                "room_id": _uuid(row.room_id),
                "role": Role(row.role),
                "deliverable_template_refs": deliverable_template_refs,
            }
        )


def _uuid(value: UUID | str) -> UUID:
    """行の値を :class:`uuid.UUID` に強制変換する。"""
    if isinstance(value, UUID):
        return value
    return UUID(value)


__all__ = ["SqliteRoomRoleOverrideRepository"]
