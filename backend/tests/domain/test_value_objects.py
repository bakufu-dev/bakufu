"""Unit tests for the reference VOs (RoomRef / AgentRef) and Role enum.

Covers TC-UT-VO-001〜006 from ``docs/features/empire/test-design.md``. Tests
are grouped into ``Test*`` classes by VO surface so test reports cluster the
contracts together (e.g. all RoomRef name-bounds cases under
``TestRoomRefName``). Each test docstring carries the trace anchor (TC-ID).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.value_objects import AgentRef, Role, RoomRef
from pydantic import ValidationError

from tests.factories.empire import is_synthetic, make_agent_ref, make_room_ref


class TestRoomRefName:
    """RoomRef.name length contract (TC-UT-VO-001 / 002)."""

    @pytest.mark.parametrize("name_length", [1, 80])
    def test_accepts_boundary_length(self, name_length: int) -> None:
        """TC-UT-VO-001: RoomRef constructs with name lengths 1 and 80."""
        ref = make_room_ref(name="a" * name_length)
        assert len(ref.name) == name_length

    @pytest.mark.parametrize("invalid_name", ["", "a" * 81])
    def test_rejects_outside_boundary(self, invalid_name: str) -> None:
        """TC-UT-VO-002: RoomRef raises ValidationError for 0/81-char names."""
        with pytest.raises(ValidationError):
            RoomRef(room_id=uuid4(), name=invalid_name)


class TestAgentRefRole:
    """AgentRef.role enum contract (TC-UT-VO-003 / 005)."""

    @pytest.mark.parametrize("role", list(Role))
    def test_accepts_each_canonical_role(self, role: Role) -> None:
        """TC-UT-VO-003: AgentRef constructs for every Role with name length 40."""
        ref = make_agent_ref(name="a" * 40, role=role)
        assert ref.role is role

    def test_rejects_role_outside_enum(self) -> None:
        """TC-UT-VO-005: AgentRef raises ValidationError for unknown Role string."""
        with pytest.raises(ValidationError):
            AgentRef.model_validate(
                {"agent_id": str(uuid4()), "name": "x", "role": "UNKNOWN_ROLE"},
            )


class TestAgentRefName:
    """AgentRef.name length contract (TC-UT-VO-004)."""

    @pytest.mark.parametrize("invalid_name", ["", "a" * 41])
    def test_rejects_outside_boundary(self, invalid_name: str) -> None:
        """TC-UT-VO-004: AgentRef raises ValidationError for 0/41-char names."""
        with pytest.raises(ValidationError):
            AgentRef(agent_id=uuid4(), name=invalid_name, role=Role.DEVELOPER)


class TestStructuralEquality:
    """Frozen VOs use structural equality and hashing (TC-UT-VO-006)."""

    def test_two_roomrefs_with_identical_fields_compare_equal(self) -> None:
        """TC-UT-VO-006: RoomRef is structurally equal when all fields match."""
        rid = uuid4()
        a = RoomRef(room_id=rid, name="部屋", archived=False)
        b = RoomRef(room_id=rid, name="部屋", archived=False)
        assert a == b

    def test_two_roomrefs_with_identical_fields_share_hash(self) -> None:
        """TC-UT-VO-006: equal RoomRefs hash identically (frozen + structural)."""
        rid = uuid4()
        a = RoomRef(room_id=rid, name="部屋", archived=False)
        b = RoomRef(room_id=rid, name="部屋", archived=False)
        assert hash(a) == hash(b)

    def test_two_agentrefs_with_identical_fields_compare_equal(self) -> None:
        """TC-UT-VO-006: AgentRef is structurally equal when all fields match."""
        aid = uuid4()
        a = AgentRef(agent_id=aid, name="諸葛", role=Role.LEADER)
        b = AgentRef(agent_id=aid, name="諸葛", role=Role.LEADER)
        assert a == b


class TestFactoryRegistry:
    """Synthetic-vs-real bookkeeping via WeakValueDictionary (cross-cutting)."""

    def test_factory_built_room_ref_is_synthetic(self) -> None:
        """Factory-built RoomRef is registered in the synthetic registry."""
        ref = make_room_ref()
        assert is_synthetic(ref) is True

    def test_factory_built_agent_ref_is_synthetic(self) -> None:
        """Factory-built AgentRef is registered in the synthetic registry."""
        ref = make_agent_ref()
        assert is_synthetic(ref) is True

    def test_directly_constructed_room_ref_is_not_synthetic(self) -> None:
        """RoomRef built outside the factory is correctly *not* registered."""
        ref = RoomRef(room_id=uuid4(), name="raw")
        assert is_synthetic(ref) is False
