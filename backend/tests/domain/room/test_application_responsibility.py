"""Application-layer responsibility boundary tests (TC-UT-RM-027〜030).

Room §確定 R1-A / R1-D / R1-E freeze that **Aggregate-internal invariants
are structural only**: ``(agent_id, role)`` uniqueness, capacity, archived
terminal, name length, description length. Cross-aggregate concerns —
``name`` Empire-scoped uniqueness, ``workflow_id`` referential integrity,
``LEADER`` required-by-Workflow, Agent existence — live in
``RoomService`` / ``EmpireService`` because they require external
knowledge. These tests freeze that boundary so a future refactor cannot
silently push aggregate-level checks into the Room aggregate (the regression
direction Norman PR #16 / Steve PR #16 worked hard to keep clean for the
agent feature).
"""

from __future__ import annotations

from uuid import uuid4

from bakufu.domain.value_objects import Role

from tests.factories.room import (
    make_agent_membership,
    make_room,
)


class TestNameUniquenessNotEnforcedByAggregate:
    """TC-UT-RM-027: Aggregate constructs two Rooms with the same name."""

    def test_two_rooms_with_same_name_both_construct(self) -> None:
        """TC-UT-RM-027: Empire-scoped name uniqueness is RoomService responsibility.

        The aggregate has no Repository handle, so it can only enforce *local*
        invariants. Empire-scoped uniqueness is a Repository SELECT pattern
        in ``RoomService.create()``.
        """
        room_a = make_room(name="Vモデル開発室", room_id=uuid4())
        room_b = make_room(name="Vモデル開発室", room_id=uuid4())
        assert room_a.name == room_b.name
        assert room_a.id != room_b.id


class TestWorkflowReferentialIntegrityNotEnforcedByAggregate:
    """TC-UT-RM-028: any UUID is accepted as workflow_id at the aggregate level."""

    def test_arbitrary_workflow_id_constructs(self) -> None:
        """TC-UT-RM-028: Workflow existence is verified by RoomService, not Room."""
        # The UUID is arbitrary — no Workflow with this id exists. Aggregate
        # accepts because referential integrity is application-layer scope.
        room = make_room(workflow_id=uuid4())
        assert room.workflow_id is not None


class TestLeaderRequirementNotEnforcedByAggregate:
    """TC-UT-RM-029: Room with zero LEADER role members constructs (chat-room scenario)."""

    def test_room_without_leader_constructs(self) -> None:
        """TC-UT-RM-029: leader-required-by-Workflow is RoomService responsibility.

        Some Workflows (e.g. casual-chat or discussion-only flows) do not
        require a LEADER. The aggregate cannot read Workflow.required_role
        without a Repository, so it skips the check entirely. Same pattern
        Agent §確定 I uses for ``provider_kind`` MVP gating.
        """
        room = make_room(members=[])
        assert all(m.role != Role.LEADER for m in room.members)


class TestAgentExistenceNotEnforcedByAggregate:
    """TC-UT-RM-030: AgentMembership accepts any UUID as agent_id."""

    def test_room_with_unknown_agent_id_constructs(self) -> None:
        """TC-UT-RM-030: Agent existence is verified by RoomService.add_member().

        At the aggregate level, ``agent_id`` is a typed UUID slot. Whether it
        resolves to an actual Agent row is a Repository concern, not an
        invariant the aggregate can observe.
        """
        unknown_agent_id = uuid4()
        m = make_agent_membership(agent_id=unknown_agent_id, role=Role.DEVELOPER)
        room = make_room(members=[m])
        assert room.members[0].agent_id == unknown_agent_id
