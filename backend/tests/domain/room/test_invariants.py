"""Aggregate-level invariants (TC-UT-RM-005 / 006 / 009).

Covers REQ-RM-006 (invariants ①〜⑤). Each invariant lives in its own
``Test*`` class so failures cluster by which collection contract was violated.
``(agent_id, role)`` pair uniqueness (Confirmation F) is exercised with both
the duplicate-pair raise path and the **same agent + different role** allowed
path so the test suite freezes the design's responsibility boundary.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import RoomInvariantViolation
from bakufu.domain.room import MAX_MEMBERS
from bakufu.domain.value_objects import Role

from tests.factories.room import (
    make_agent_membership,
    make_leader_membership,
    make_room,
)


class TestMemberPairUniqueness:
    """TC-UT-RM-005: same (agent_id, role) twice raises member_duplicate."""

    def test_duplicate_pair_raises_member_duplicate(self) -> None:
        """TC-UT-RM-005: two memberships sharing (agent_id, role) raises."""
        agent_id = uuid4()
        m1 = make_agent_membership(agent_id=agent_id, role=Role.DEVELOPER)
        m2 = make_agent_membership(agent_id=agent_id, role=Role.DEVELOPER)
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(members=[m1, m2])
        assert excinfo.value.kind == "member_duplicate"
        assert excinfo.value.detail.get("agent_id") == str(agent_id)
        assert excinfo.value.detail.get("role") == Role.DEVELOPER.value


class TestSameAgentDifferentRoleAllowed:
    """TC-UT-RM-006 (Confirmation F): same agent_id under different roles is allowed."""

    def test_same_agent_two_roles_succeeds(self) -> None:
        """TC-UT-RM-006: leader + reviewer for same agent is a valid Room."""
        agent_id = uuid4()
        m_leader = make_leader_membership(agent_id=agent_id)
        m_reviewer = make_agent_membership(agent_id=agent_id, role=Role.REVIEWER)
        room = make_room(members=[m_leader, m_reviewer])
        assert len(room.members) == 2
        roles = {m.role for m in room.members}
        assert roles == {Role.LEADER, Role.REVIEWER}


class TestMemberCapacity:
    """TC-UT-RM-009: members ≤ MAX_MEMBERS (Confirmation C)."""

    def test_at_capacity_succeeds(self) -> None:
        """TC-UT-RM-009 boundary: exactly MAX_MEMBERS=50 succeeds."""
        members = [
            make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER) for _ in range(MAX_MEMBERS)
        ]
        room = make_room(members=members)
        assert len(room.members) == MAX_MEMBERS

    def test_overflow_raises_capacity_exceeded(self) -> None:
        """TC-UT-RM-009: MAX_MEMBERS+1 raises capacity_exceeded with count detail."""
        members = [
            make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
            for _ in range(MAX_MEMBERS + 1)
        ]
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(members=members)
        assert excinfo.value.kind == "capacity_exceeded"
        assert excinfo.value.detail.get("members_count") == MAX_MEMBERS + 1
        assert excinfo.value.detail.get("max_members") == MAX_MEMBERS
