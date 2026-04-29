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
    """``empire_room_refs`` FK を満たすため ``workflows`` + ``rooms`` 行をシードする。

    ``empire_room_refs.room_id → rooms.id`` FK (ON DELETE CASCADE) は
    Alembic 0005 で BUG-EMR-001 FK クロージャとして追加。
    このヘルパーは最小限の前提条件行を挿入し、Empire の ``rooms`` リストを
    設定するテストが ``FOREIGN KEY constraint failed`` を発生させずに
    ``SqliteEmpireRepository.save()`` を呼び出せるようにする。

    ステップ:
    1. Empire 行が存在することを確認する (``INSERT OR IGNORE`` ——
       呼び出し元が最初の ``save()`` の前後どちらでシードできるよう冪等)。
    2. rooms が FK 経由で参照できる ``workflows`` 行をシードする。
    3. ``empire_id`` と ``workflow_id`` を外部キーとして、
       ``room_id`` ごとに 1 つの ``rooms`` 行をシードする。

    使用した ``workflow_id`` を返す (渡されない場合は新規生成)。
    """
    wf_id = workflow_id if workflow_id is not None else uuid4()

    async with session_factory() as session, session.begin():
        # ステップ 1: rooms.empire_id FK が解決するよう Empire 行が存在することを確認。
        # INSERT OR IGNORE は SqliteEmpireRepository.save() が既に UPSERT 経由で
        # Empire 行を作成していても安全。
        await session.execute(
            text("INSERT OR IGNORE INTO empires (id, name) VALUES (:id, :name)"),
            {"id": empire_id.hex, "name": "seed-empire"},
        )

        # ステップ 2: rooms.workflow_id FK が解決するよう最小限の workflow 行をシード。
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

        # ステップ 3: room_id ごとに 1 つの rooms 行をシード。
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
