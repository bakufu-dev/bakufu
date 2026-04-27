"""Round-trip scenarios across Room + PromptKit + AgentMembership + Exception (TC-IT-RM-001 / 002).

The room feature is domain-only with zero external I/O, so "integration" here
means *aggregate-internal module integration*: chained behaviors over a
non-empty member list, with the original Room observed unchanged at each
step (frozen + pre-validate rebuild, Confirmation A).

These tests intentionally compose the production constructors / behaviors
directly — no mocks, no test-only back doors — and exercise the documented
acceptance criteria 1, 4, 7, 10, 11 in a single sequence.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import RoomInvariantViolation
from bakufu.domain.value_objects import Role

from tests.factories.room import (
    make_agent_membership,
    make_leader_membership,
    make_prompt_kit,
    make_room,
)


class TestRoomLifecycleRoundTrip:
    """TC-IT-RM-001: full Room lifecycle exercise across all behaviors."""

    def test_full_lifecycle_preserves_immutability(self) -> None:
        """TC-IT-RM-001: add → add → update → remove → archive sequence."""
        # Step 1: empty Room.
        room0 = make_room(members=[])
        assert room0.members == []
        assert room0.archived is False

        # Step 2: add a leader.
        leader = make_leader_membership(agent_id=uuid4())
        room1 = room0.add_member(leader)
        assert len(room1.members) == 1

        # Step 3: add a developer.
        developer = make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
        room2 = room1.add_member(developer)
        assert len(room2.members) == 2

        # Step 4: replace PromptKit.
        new_kit = make_prompt_kit(prefix_markdown="# V-Model Room policy\n\nbe rigorous")
        room3 = room2.update_prompt_kit(new_kit)
        assert "V-Model Room policy" in room3.prompt_kit.prefix_markdown

        # Step 5: remove the developer.
        room4 = room3.remove_member(developer.agent_id, developer.role)
        assert len(room4.members) == 1
        assert room4.members[0].agent_id == leader.agent_id

        # Step 6: archive.
        room5 = room4.archive()
        assert room5.archived is True

        # Frozen contract: each earlier Room stays unchanged across steps.
        assert room0.members == []
        assert len(room1.members) == 1
        assert len(room2.members) == 2
        assert "V-Model Room policy" not in room2.prompt_kit.prefix_markdown
        assert room4.archived is False


class TestAddMemberFailureThenSuccess:
    """TC-IT-RM-002: add_member fails on duplicate, succeeds on a different pair."""

    def test_failure_does_not_block_subsequent_success(self) -> None:
        """TC-IT-RM-002: pre-validate isolation lets the next add proceed cleanly."""
        leader = make_leader_membership(agent_id=uuid4())
        room = make_room(members=[leader])

        # First call: duplicate pair fails.
        with pytest.raises(RoomInvariantViolation) as excinfo:
            room.add_member(make_leader_membership(agent_id=leader.agent_id))
        assert excinfo.value.kind == "member_duplicate"

        # Original Room is unchanged.
        assert len(room.members) == 1

        # Second call: different pair succeeds.
        new_developer = make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
        new_room = room.add_member(new_developer)
        assert len(new_room.members) == 2
        # Pair set is what we expect.
        pairs = {(m.agent_id, m.role) for m in new_room.members}
        assert (leader.agent_id, Role.LEADER) in pairs
        assert (new_developer.agent_id, Role.DEVELOPER) in pairs
