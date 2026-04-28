"""Room Repository: DB constraints + arch-test reference.

TC-IT-RR-009 / TC-IT-RR-013-arch — the **UNIQUE(room_id, agent_id, role)
二重防衛** (§確定 R1-D) and the CI Layer 2 arch-test cross-reference.

§確定 R1-D: duplicate (room_id, agent_id, role) triplets are forbidden
by **two layers**:

1. **Aggregate-level**: Room construction validates member uniqueness at
   construction time.
2. **DB-level**: explicit ``UniqueConstraint("room_id", "agent_id", "role",
   name="uq_room_members_triplet")`` physically rejects the INSERT — the
   final defense line for code paths that bypass the Aggregate (raw SQL,
   future Repository implementations, dump/restore migrations, etc.).

This test exercises **layer 2 in isolation** by writing raw SQL that
sidesteps the Aggregate. A regression that drops the UniqueConstraint
DDL would let the second INSERT succeed silently.

Also tests:
* ``rooms.workflow_id FK RESTRICT``: DELETE a workflow while a room
  references it must raise ``IntegrityError`` (§確定 R1-I).
* ``room_members.room_id FK CASCADE``: DELETE a room cascades to
  room_members rows (§確定 R1-C Room entity cascade).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-IT-RR-009: UNIQUE(room_id, agent_id, role) 二重防衛 (§確定 R1-D)
# ---------------------------------------------------------------------------
class TestUniqueRoomMemberTripletDoubleDefense:
    """TC-IT-RR-009: duplicate (room_id, agent_id, role) raises IntegrityError.

    The Aggregate's member validation is the first layer; this test
    bypasses it by writing raw SQL directly so the DB constraint is the
    only thing standing between us and a silent duplicate. The first
    INSERT must succeed; the second must raise ``IntegrityError``.
    """

    async def test_duplicate_triplet_raises_integrity_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """TC-IT-RR-009: same (room_id, agent_id, role) inserted twice → IntegrityError."""
        from datetime import UTC, datetime

        from sqlalchemy.exc import IntegrityError

        room_id = uuid4()
        agent_id = uuid4()
        empire_id = seeded_empire_id
        workflow_id = seeded_workflow_id

        # Seed the rooms row first so room_members FK resolves.
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO rooms "
                    "(id, empire_id, workflow_id, name, description, "
                    "prompt_kit_prefix_markdown, archived) VALUES "
                    "(:id, :empire_id, :workflow_id, :name, :description, "
                    ":prefix, :archived)"
                ),
                {
                    "id": room_id.hex,
                    "empire_id": empire_id.hex,
                    "workflow_id": workflow_id.hex,
                    "name": "constraint-test-room",
                    "description": "",
                    "prefix": "",
                    "archived": False,
                },
            )

        joined_at = datetime.now(UTC).isoformat()

        # First member INSERT — must succeed.
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO room_members (room_id, agent_id, role, joined_at) "
                    "VALUES (:room_id, :agent_id, :role, :joined_at)"
                ),
                {
                    "room_id": room_id.hex,
                    "agent_id": agent_id.hex,
                    "role": "LEADER",
                    "joined_at": joined_at,
                },
            )

        # Second INSERT with the same (room_id, agent_id, role) triplet —
        # the uq_room_members_triplet constraint must reject it.
        with pytest.raises(IntegrityError):
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        "INSERT INTO room_members (room_id, agent_id, role, joined_at) "
                        "VALUES (:room_id, :agent_id, :role, :joined_at)"
                    ),
                    {
                        "room_id": room_id.hex,
                        "agent_id": agent_id.hex,
                        "role": "LEADER",  # same role → same triplet
                        "joined_at": joined_at,
                    },
                )

    async def test_same_agent_different_roles_are_permitted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Same (room_id, agent_id) with different roles must NOT raise.

        Confirms the uniqueness is scoped to the **triplet** — different
        roles on the same (room_id, agent_id) represent distinct membership
        records (e.g. an agent who is both DEVELOPER and REVIEWER).
        """
        from datetime import UTC, datetime

        room_id = uuid4()
        agent_id = uuid4()

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO rooms "
                    "(id, empire_id, workflow_id, name, description, "
                    "prompt_kit_prefix_markdown, archived) VALUES "
                    "(:id, :empire_id, :workflow_id, :name, :description, :prefix, :archived)"
                ),
                {
                    "id": room_id.hex,
                    "empire_id": seeded_empire_id.hex,
                    "workflow_id": seeded_workflow_id.hex,
                    "name": "multi-role-room",
                    "description": "",
                    "prefix": "",
                    "archived": False,
                },
            )

        joined_at = datetime.now(UTC).isoformat()
        async with session_factory() as session, session.begin():
            for role in ("LEADER", "REVIEWER"):
                await session.execute(
                    text(
                        "INSERT INTO room_members (room_id, agent_id, role, joined_at) "
                        "VALUES (:room_id, :agent_id, :role, :joined_at)"
                    ),
                    {
                        "room_id": room_id.hex,
                        "agent_id": agent_id.hex,
                        "role": role,
                        "joined_at": joined_at,
                    },
                )

        # Both rows present; triplet uniqueness did not fire.
        async with session_factory() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM room_members WHERE room_id = :room_id"),
                {"room_id": room_id.hex},
            )
            count = result.scalar_one()
        assert count == 2


# ---------------------------------------------------------------------------
# TC-IT-RR-009 補強: workflow_id FK RESTRICT (§確定 R1-I)
# ---------------------------------------------------------------------------
class TestWorkflowFkRestrict:
    """``rooms.workflow_id`` FK RESTRICT prevents orphan Rooms on Workflow delete.

    §確定 R1-I: Workflow is a *reference* target for Room, not an owner.
    Deleting a Workflow while Rooms still reference it is a hard failure
    at the DB level — the application layer check alone would be
    insufficient for raw-SQL paths.

    Note: SQLite FK enforcement requires ``PRAGMA foreign_keys = ON``,
    which the production engine enables at connect time.
    """

    async def test_delete_referenced_workflow_raises_integrity_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """DELETE workflow while room references it → IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        room_id = uuid4()
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO rooms "
                    "(id, empire_id, workflow_id, name, description, "
                    "prompt_kit_prefix_markdown, archived) VALUES "
                    "(:id, :empire_id, :workflow_id, :name, :description, :prefix, :archived)"
                ),
                {
                    "id": room_id.hex,
                    "empire_id": seeded_empire_id.hex,
                    "workflow_id": seeded_workflow_id.hex,
                    "name": "restrict-test-room",
                    "description": "",
                    "prefix": "",
                    "archived": False,
                },
            )

        # Now try to delete the workflow that the room references —
        # RESTRICT must fire.
        with pytest.raises(IntegrityError):
            async with session_factory() as session, session.begin():
                await session.execute(
                    text("DELETE FROM workflows WHERE id = :id"),
                    {"id": seeded_workflow_id.hex},
                )


# ---------------------------------------------------------------------------
# TC-IT-RR-009 補強: room_members CASCADE DELETE (§確定 R1-C)
# ---------------------------------------------------------------------------
class TestRoomMembersCascadeOnRoomDelete:
    """room_members rows are deleted when the parent Room is deleted.

    ``room_members.room_id REFERENCES rooms.id ON DELETE CASCADE`` —
    deleting a Room row must cascade to its member rows. This prevents
    orphan room_members rows from accumulating after Room deletion.
    """

    async def test_cascade_deletes_member_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """DELETE rooms row cascades to all room_members rows for that room."""
        from datetime import UTC, datetime

        room_id = uuid4()
        joined_at = datetime.now(UTC).isoformat()

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO rooms "
                    "(id, empire_id, workflow_id, name, description, "
                    "prompt_kit_prefix_markdown, archived) VALUES "
                    "(:id, :empire_id, :workflow_id, :name, :description, :prefix, :archived)"
                ),
                {
                    "id": room_id.hex,
                    "empire_id": seeded_empire_id.hex,
                    "workflow_id": seeded_workflow_id.hex,
                    "name": "cascade-test-room",
                    "description": "",
                    "prefix": "",
                    "archived": False,
                },
            )
            await session.execute(
                text(
                    "INSERT INTO room_members (room_id, agent_id, role, joined_at) "
                    "VALUES (:room_id, :agent_id, :role, :joined_at)"
                ),
                {
                    "room_id": room_id.hex,
                    "agent_id": uuid4().hex,
                    "role": "LEADER",
                    "joined_at": joined_at,
                },
            )

        # Delete the parent room — member rows must cascade.
        async with session_factory() as session, session.begin():
            await session.execute(
                text("DELETE FROM rooms WHERE id = :id"),
                {"id": room_id.hex},
            )

        async with session_factory() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM room_members WHERE room_id = :room_id"),
                {"room_id": room_id.hex},
            )
            count = result.scalar_one()
        assert count == 0, (
            f"[FAIL] room_members rows not cascaded on Room deletion (count={count}).\n"
            f"Next: ensure room_members.room_id FK carries ON DELETE CASCADE."
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-013-arch: Layer 2 arch-test reference — Room rows registered
# ---------------------------------------------------------------------------
class TestArchTestRegistrationStructure:
    """TC-IT-RR-013-arch: ``test_masking_columns.py`` parametrize lists include Room.

    Cross-checks that the CI Layer 2 arch test was extended to cover
    Room tables (§確定 R1-E). A future PR that drops these registrations
    (e.g. by accident during a refactor) would let an over-masking
    or under-masking change land silently — this test catches it.
    """

    async def test_rooms_prompt_kit_prefix_markdown_in_masking_contract(self) -> None:
        """``rooms.prompt_kit_prefix_markdown`` is registered as MaskedText."""
        from bakufu.infrastructure.persistence.sqlite.base import MaskedText

        from tests.architecture.test_masking_columns import (
            _MASKING_CONTRACT,  # pyright: ignore[reportPrivateUsage]
        )

        assert ("rooms", "prompt_kit_prefix_markdown", MaskedText) in _MASKING_CONTRACT, (
            "[FAIL] rooms.prompt_kit_prefix_markdown missing from _MASKING_CONTRACT.\n"
            "Next: re-add the room §確定 G 実適用 row to "
            "tests/architecture/test_masking_columns.py."
        )

    async def test_room_members_in_no_mask_list(self) -> None:
        """``room_members`` is a no-mask table (agent_id is not secret)."""
        from tests.architecture.test_masking_columns import (
            _NO_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
        )

        assert "room_members" in _NO_MASK_TABLES, (
            "[FAIL] room_members missing from _NO_MASK_TABLES.\n"
            "Next: §確定 R1-E designates room_members as 'masking 対象なし'."
        )

    async def test_rooms_partial_mask_template_registered(self) -> None:
        """``rooms`` is registered in the partial-mask template list."""
        from tests.architecture.test_masking_columns import (
            _PARTIAL_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
        )

        partial = dict(_PARTIAL_MASK_TABLES)
        assert partial.get("rooms") == "prompt_kit_prefix_markdown", (
            f"[FAIL] rooms partial-mask declared {partial.get('rooms')!r}, "
            f"expected 'prompt_kit_prefix_markdown'.\n"
            f"Next: §逆引き表 freezes prompt_kit_prefix_markdown as the sole "
            f"masked column on rooms (§確定 R1-E)."
        )
