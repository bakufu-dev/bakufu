"""Mutator behaviors with pre-validate rebuild semantics (Confirmation A).

Covers TC-UT-RM-004 / 007 / 008 / 010 / 020 / 021 / 022. Each behavior
returns a *new* :class:`Room` instance and the original stays unchanged on
both success and failure paths — the test suite freezes that immutability
contract so future refactors that mutate-in-place are caught immediately.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import RoomInvariantViolation
from bakufu.domain.value_objects import Role

from tests.factories.room import (
    make_agent_membership,
    make_archived_room,
    make_leader_membership,
    make_prompt_kit,
    make_room,
)


class TestAddMember:
    """TC-UT-RM-004: add_member appends without mutating the original."""

    def test_add_member_appends_to_new_room(self) -> None:
        """TC-UT-RM-004: members count grows by 1 on the returned Room."""
        room = make_room(members=[])
        m = make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
        new_room = room.add_member(m)
        assert len(new_room.members) == 1
        assert new_room.members[0] == m

    def test_add_member_does_not_mutate_original(self) -> None:
        """TC-UT-RM-004: the original Room.members stays empty after add."""
        room = make_room(members=[])
        m = make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
        room.add_member(m)
        assert room.members == []


class TestRemoveMember:
    """TC-UT-RM-007 / 008: remove_member success + missing-pair Fail Fast."""

    def test_remove_member_drops_matching_pair(self) -> None:
        """TC-UT-RM-007: removing one of two members yields a 1-member Room."""
        agent_id = uuid4()
        m1 = make_leader_membership(agent_id=agent_id)
        m2 = make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
        room = make_room(members=[m1, m2])
        new_room = room.remove_member(m1.agent_id, m1.role)
        assert len(new_room.members) == 1
        assert new_room.members[0].agent_id == m2.agent_id

    def test_remove_unknown_pair_raises_member_not_found(self) -> None:
        """TC-UT-RM-008: remove_member with absent (agent_id, role) raises."""
        room = make_room(members=[])
        with pytest.raises(RoomInvariantViolation) as excinfo:
            room.remove_member(uuid4(), Role.DEVELOPER)
        assert excinfo.value.kind == "member_not_found"

    def test_remove_keeps_original_unchanged(self) -> None:
        """TC-UT-RM-007: the original Room.members stays at 2 after remove."""
        m1 = make_leader_membership(agent_id=uuid4())
        m2 = make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
        room = make_room(members=[m1, m2])
        room.remove_member(m1.agent_id, m1.role)
        assert len(room.members) == 2


class TestUpdatePromptKit:
    """TC-UT-RM-010: update_prompt_kit replaces without mutating the original."""

    def test_update_prompt_kit_replaces_on_new_instance(self) -> None:
        """TC-UT-RM-010: returned Room carries the new prefix_markdown."""
        room = make_room()
        new_kit = make_prompt_kit(prefix_markdown="# Updated")
        new_room = room.update_prompt_kit(new_kit)
        assert new_room.prompt_kit.prefix_markdown == "# Updated"

    def test_update_prompt_kit_does_not_mutate_original(self) -> None:
        """TC-UT-RM-010: the original Room.prompt_kit stays empty."""
        room = make_room()
        new_kit = make_prompt_kit(prefix_markdown="# Updated")
        room.update_prompt_kit(new_kit)
        assert room.prompt_kit.prefix_markdown == ""


class TestPreValidateRollback:
    """Confirmation A: failed mutators leave the original Room intact."""

    def test_add_member_failure_does_not_mutate_original(self) -> None:
        """TC-UT-RM-020: duplicate-pair add_member leaves room.members unchanged."""
        agent_id = uuid4()
        m = make_leader_membership(agent_id=agent_id)
        room = make_room(members=[m])
        dup = make_leader_membership(agent_id=agent_id)
        with pytest.raises(RoomInvariantViolation):
            room.add_member(dup)
        assert len(room.members) == 1
        assert room.members[0].agent_id == agent_id

    def test_remove_member_failure_does_not_mutate_original(self) -> None:
        """TC-UT-RM-021: missing-pair remove_member leaves room.members unchanged."""
        m = make_leader_membership(agent_id=uuid4())
        room = make_room(members=[m])
        with pytest.raises(RoomInvariantViolation):
            room.remove_member(uuid4(), Role.DEVELOPER)
        assert len(room.members) == 1
        assert room.members[0] == m

    def test_update_prompt_kit_failure_does_not_mutate_original(self) -> None:
        """TC-UT-RM-022: archived Room update fails; original prompt_kit unchanged."""
        original_kit = make_prompt_kit(prefix_markdown="# Original")
        room = make_archived_room(prompt_kit=original_kit)
        with pytest.raises(RoomInvariantViolation):
            room.update_prompt_kit(make_prompt_kit(prefix_markdown="# Changed"))
        assert room.prompt_kit.prefix_markdown == "# Original"
