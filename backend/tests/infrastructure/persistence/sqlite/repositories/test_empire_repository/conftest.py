"""empire-repository 統合テスト用の Pytest フィクスチャ。

``empire_room_refs.room_id → rooms.id`` FK制約を満たすセッドヘルパーを提供
(Alembic 0005_room_aggregate により追加、BUG-EMR-001 FK クロージャ)。

背景: Alembic 0005 より前、``empire_room_refs.room_id`` は rooms.id への
**FK を持たなかった** (rooms テーブルがまだ存在しなかった)。0005 の後、
FK は ``ON DELETE CASCADE`` で配線されるため、empire_room_refs への任意の
INSERT は rooms の一致する行を要求する。``SqliteEmpireRepository.save(empire)``
を完全に充実した Empire で呼び出すテスト、または empire_room_refs に
生 SQL を発行するテストは、最初に rooms テーブルをシードする必要。

使用法::

    from tests.infrastructure.persistence.sqlite.repositories.\
        test_empire_repository.conftest import seed_rooms

    empire = make_populated_empire(n_rooms=2, n_agents=3)
    await seed_rooms(session_factory, empire.id, [r.room_id for r in empire.rooms])
    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def seed_rooms(
    session_factory: async_sessionmaker[AsyncSession],
    empire_id: UUID,
    room_ids: list[UUID],
    *,
    workflow_id: UUID | None = None,
) -> UUID:
    """Seed ``workflows`` + ``rooms`` rows to satisfy ``empire_room_refs`` FK.

    ``empire_room_refs.room_id → rooms.id`` FK (ON DELETE CASCADE) was added
    in Alembic 0005 as BUG-EMR-001 FK closure. This helper inserts the
    minimal prerequisite rows so tests that populate an Empire's ``rooms``
    list can call ``SqliteEmpireRepository.save()`` without hitting
    ``FOREIGN KEY constraint failed``.

    Steps:
    1. Ensure the Empire row exists (``INSERT OR IGNORE`` — idempotent so
       the caller can seed before or after the first ``save()``).
    2. Seed one ``workflows`` row that the rooms can reference via FK.
    3. Seed one ``rooms`` row per ``room_id`` with ``empire_id`` and
       ``workflow_id`` as foreign keys.

    Returns the ``workflow_id`` that was used (generated fresh if not passed).
    """
    wf_id = workflow_id if workflow_id is not None else uuid4()

    async with session_factory() as session, session.begin():
        # Step 1: ensure the empire row exists so rooms.empire_id FK resolves.
        # INSERT OR IGNORE is safe even after SqliteEmpireRepository.save()
        # has already created the empire row via UPSERT.
        await session.execute(
            text("INSERT OR IGNORE INTO empires (id, name) VALUES (:id, :name)"),
            {"id": empire_id.hex, "name": "seed-empire"},
        )

        # Step 2: seed a minimal workflow row so rooms.workflow_id FK resolves.
        await session.execute(
            text(
                "INSERT INTO workflows (id, name, entry_stage_id) "
                "VALUES (:id, :name, :entry_stage_id)"
            ),
            {
                "id": wf_id.hex,
                "name": "seed-workflow",
                "entry_stage_id": uuid4().hex,
            },
        )

        # Step 3: seed one rooms row per room_id.
        for room_id in room_ids:
            await session.execute(
                text(
                    "INSERT OR IGNORE INTO rooms "
                    "(id, empire_id, workflow_id, name, description, "
                    "prompt_kit_prefix_markdown, archived) "
                    "VALUES (:id, :empire_id, :workflow_id, :name, "
                    ":description, :prefix, :archived)"
                ),
                {
                    "id": room_id.hex,
                    "empire_id": empire_id.hex,
                    "workflow_id": wf_id.hex,
                    "name": "seed-room",
                    "description": "",
                    "prefix": "",
                    "archived": False,
                },
            )

    return wf_id
