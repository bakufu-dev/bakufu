"""Empire Repository: DB制約 + アーキテクチャテストテンプレート構造。

TC-IT-EMR-013 / 014 / 017 — FK CASCADE、UNIQUE ペア強制実行、および
次の 6 つの Repository PR が拡張する CI 3層防御テンプレート。
Norman の500行ルールに従い元の ``test_empire_repository.py`` から分割。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
    SqliteEmpireRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.empire_agent_refs import (
    EmpireAgentRefRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.empire_room_refs import (
    EmpireRoomRefRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.empires import EmpireRow
from sqlalchemy import delete, select, text

from tests.factories.empire import make_empire, make_populated_empire
from tests.infrastructure.persistence.sqlite.repositories.test_empire_repository.conftest import (
    seed_rooms,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


class TestForeignKeyCascade:
    """TC-IT-EMR-013: ``DELETE FROM empires`` cascades to side tables."""

    async def test_delete_empire_cascades_to_side_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-013: FK ON DELETE CASCADE empties empire_room_refs / empire_agent_refs."""
        empire = make_populated_empire(n_rooms=2, n_agents=3)
        await seed_rooms(session_factory, empire.id, [r.room_id for r in empire.rooms])
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session, session.begin():
            await session.execute(delete(EmpireRow).where(EmpireRow.id == empire.id))

        async with session_factory() as session:
            room_rows = list(
                (
                    await session.execute(
                        select(EmpireRoomRefRow).where(EmpireRoomRefRow.empire_id == empire.id)
                    )
                ).scalars()
            )
            agent_rows = list(
                (
                    await session.execute(
                        select(EmpireAgentRefRow).where(EmpireAgentRefRow.empire_id == empire.id)
                    )
                ).scalars()
            )
        assert room_rows == []
        assert agent_rows == []


class TestUniqueConstraintViolation:
    """TC-IT-EMR-014: duplicate (empire_id, room_id) raises IntegrityError."""

    async def test_duplicate_room_pair_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-014: same (empire_id, room_id) inserted twice → DB rejects.

        The Repository's delete-then-insert flow always wipes the side
        tables before INSERT, so the constraint is never tripped through
        the Repository API. To exercise the **DB-level** UNIQUE
        contract we issue raw SQL that bypasses the Repository.
        """
        from sqlalchemy.exc import IntegrityError

        empire = make_empire()
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        room_id = uuid4()
        # Alembic 0005 で empire_room_refs.room_id → rooms.id FK が追加された（BUG-EMR-001
        # クローズ）。empire_room_refs に挿入する前に room 行を seed する。
        await seed_rooms(session_factory, empire.id, [room_id])
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO empire_room_refs (empire_id, room_id, name, archived) "
                    "VALUES (:empire_id, :room_id, :name, :archived)"
                ),
                {
                    "empire_id": empire.id.hex,
                    "room_id": room_id.hex,
                    "name": "first",
                    "archived": False,
                },
            )

        with pytest.raises(IntegrityError):
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        "INSERT INTO empire_room_refs (empire_id, room_id, name, archived) "
                        "VALUES (:empire_id, :room_id, :name, :archived)"
                    ),
                    {
                        "empire_id": empire.id.hex,
                        "room_id": room_id.hex,
                        "name": "duplicate",
                        "archived": False,
                    },
                )


# ---------------------------------------------------------------------------
# CI 三層防衛 Layer 2 — テンプレート構造の物理確認 (§確定 E / F)
# ---------------------------------------------------------------------------
class TestNoMaskTemplateStructure:
    """TC-IT-EMR-017: arch test exposes a parametrize structure future PRs can extend."""

    async def test_arch_test_module_imports_no_mask_table_list(self) -> None:
        """TC-IT-EMR-017: ``_NO_MASK_TABLES`` exists and lists the Empire 3 tables.

        Future Repository PRs add their own "no-mask" table names to
        ``_NO_MASK_TABLES`` (or the parallel ``_MASKING_CONTRACT`` for
        secret-bearing columns); the structural shape lets them extend
        without rewriting the harness.
        """
        from tests.architecture.test_masking_columns import (
            _MASKING_CONTRACT,  # pyright: ignore[reportPrivateUsage]
            _NO_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
        )

        # Empire の 3 テーブルは no-mask リストに含まれる必要がある。
        assert "empires" in _NO_MASK_TABLES
        assert "empire_room_refs" in _NO_MASK_TABLES
        assert "empire_agent_refs" in _NO_MASK_TABLES
        # Empire のカラムは masking 契約リストに **現れない** こと
        # （ポジティブ契約）。
        empire_table_names = {"empires", "empire_room_refs", "empire_agent_refs"}
        contract_tables = {tbl for tbl, _, _ in _MASKING_CONTRACT}
        assert contract_tables.isdisjoint(empire_table_names)
