"""archive() idempotency + archived terminal violations (Confirmations D / E).

Covers TC-UT-RM-011 / 012 / 013 / 023. ``archive()`` always returns a new
instance (Confirmation D — idempotency means *result state matches*, not
*object identity*), and archived Rooms reject all mutating behaviors except
``archive`` itself (Confirmation E).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import RoomInvariantViolation
from bakufu.domain.value_objects import Role

from tests.factories.room import (
    make_agent_membership,
    make_archived_room,
    make_prompt_kit,
    make_room,
)


class TestArchive:
    """TC-UT-RM-011 / 012 / 023: archive() returns a new instance (idempotent)."""

    def test_archive_returns_archived_room(self) -> None:
        """TC-UT-RM-011: archive() yields a Room with archived=True."""
        room = make_room()
        archived = room.archive()
        assert archived.archived is True

    def test_archive_does_not_mutate_original(self) -> None:
        """TC-UT-RM-011: original Room.archived stays False after archive()."""
        room = make_room()
        room.archive()
        assert room.archived is False

    def test_archive_on_already_archived_returns_new_equal_instance(self) -> None:
        """TC-UT-RM-012: archive() on archived Room returns a *new* equal Room.

        Idempotency means **result state matches**, not **object identity**.
        ``model_validate`` rebuild always produces a fresh instance with a
        different ``id()`` but structurally equal attributes.
        """
        room = make_archived_room()
        again = room.archive()
        assert again.archived is True
        assert again == room
        assert again is not room

    def test_consecutive_archive_calls_remain_idempotent(self) -> None:
        """TC-UT-RM-023: archive() chained 3 times yields the same final state."""
        room = make_room()
        a1 = room.archive()
        a2 = a1.archive()
        a3 = a2.archive()
        assert a1.archived is True
        assert a2.archived is True
        assert a3.archived is True
        assert a1 == a2 == a3


class TestArchivedTerminalViolation:
    """TC-UT-RM-013: archived Rooms reject add_member / remove_member / update_prompt_kit."""

    def test_archived_add_member_raises_room_archived(self) -> None:
        """TC-UT-RM-013: add_member on archived Room raises room_archived."""
        room = make_archived_room()
        m = make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
        with pytest.raises(RoomInvariantViolation) as excinfo:
            room.add_member(m)
        assert excinfo.value.kind == "room_archived"

    def test_archived_remove_member_raises_room_archived(self) -> None:
        """TC-UT-RM-013: remove_member on archived Room raises room_archived."""
        m = make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
        room = make_archived_room(members=[m])
        with pytest.raises(RoomInvariantViolation) as excinfo:
            room.remove_member(m.agent_id, m.role)
        assert excinfo.value.kind == "room_archived"

    def test_archived_update_prompt_kit_raises_room_archived(self) -> None:
        """TC-UT-RM-013: update_prompt_kit on archived Room raises room_archived."""
        room = make_archived_room()
        new_kit = make_prompt_kit(prefix_markdown="# attempted")
        with pytest.raises(RoomInvariantViolation) as excinfo:
            room.update_prompt_kit(new_kit)
        assert excinfo.value.kind == "room_archived"
