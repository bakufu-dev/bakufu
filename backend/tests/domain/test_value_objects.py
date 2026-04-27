"""Unit tests for the reference VOs (RoomRef / AgentRef) and Role enum.

Covers TC-UT-VO-001〜006 from ``docs/features/empire/test-design.md``.
Each test docstring carries the trace anchor (TC-ID) so failures map back to
the design document without ambiguity.

These tests focus on the VO contracts in isolation. Aggregate-level invariants
that span multiple VOs live in ``test_empire.py``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.value_objects import AgentRef, Role, RoomRef
from pydantic import ValidationError

from tests.factories.empire import is_synthetic, make_agent_ref, make_room_ref


# ---------------------------------------------------------------------------
# TC-UT-VO-001 — RoomRef accepts boundary-valid inputs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name_length", [1, 80])
def test_room_ref_accepts_name_at_boundary_lengths(name_length: int) -> None:
    """TC-UT-VO-001: RoomRef constructs with name lengths 1 and 80."""
    ref = make_room_ref(name="a" * name_length)
    assert len(ref.name) == name_length


# ---------------------------------------------------------------------------
# TC-UT-VO-002 — RoomRef rejects out-of-range names
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("invalid_name", ["", "a" * 81])
def test_room_ref_rejects_name_outside_boundaries(invalid_name: str) -> None:
    """TC-UT-VO-002: RoomRef raises ValidationError for 0/81-char names."""
    with pytest.raises(ValidationError):
        RoomRef(room_id=uuid4(), name=invalid_name)


# ---------------------------------------------------------------------------
# TC-UT-VO-003 — AgentRef accepts every Role enum value at upper-bound length
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", list(Role))
def test_agent_ref_accepts_each_role_with_boundary_name(role: Role) -> None:
    """TC-UT-VO-003: AgentRef constructs for every Role with name length 40."""
    ref = make_agent_ref(name="a" * 40, role=role)
    assert ref.role is role


# ---------------------------------------------------------------------------
# TC-UT-VO-004 — AgentRef rejects out-of-range names
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("invalid_name", ["", "a" * 41])
def test_agent_ref_rejects_name_outside_boundaries(invalid_name: str) -> None:
    """TC-UT-VO-004: AgentRef raises ValidationError for 0/41-char names."""
    with pytest.raises(ValidationError):
        AgentRef(agent_id=uuid4(), name=invalid_name, role=Role.DEVELOPER)


# ---------------------------------------------------------------------------
# TC-UT-VO-005 — AgentRef rejects unknown Role values
# ---------------------------------------------------------------------------
def test_agent_ref_rejects_role_outside_enum() -> None:
    """TC-UT-VO-005: AgentRef raises ValidationError for unknown Role string."""
    with pytest.raises(ValidationError):
        AgentRef.model_validate(
            {"agent_id": str(uuid4()), "name": "x", "role": "UNKNOWN_ROLE"},
        )


# ---------------------------------------------------------------------------
# TC-UT-VO-006 — Structural equality / hashability
# ---------------------------------------------------------------------------
def test_two_roomrefs_with_identical_fields_compare_equal() -> None:
    """TC-UT-VO-006: RoomRef is structurally equal when all fields match."""
    rid = uuid4()
    a = RoomRef(room_id=rid, name="部屋", archived=False)
    b = RoomRef(room_id=rid, name="部屋", archived=False)
    assert a == b


def test_two_roomrefs_with_identical_fields_share_hash() -> None:
    """TC-UT-VO-006: equal RoomRefs hash identically (frozen + structural)."""
    rid = uuid4()
    a = RoomRef(room_id=rid, name="部屋", archived=False)
    b = RoomRef(room_id=rid, name="部屋", archived=False)
    assert hash(a) == hash(b)


def test_two_agentrefs_with_identical_fields_compare_equal() -> None:
    """TC-UT-VO-006: AgentRef is structurally equal when all fields match."""
    aid = uuid4()
    a = AgentRef(agent_id=aid, name="諸葛", role=Role.LEADER)
    b = AgentRef(agent_id=aid, name="諸葛", role=Role.LEADER)
    assert a == b


# ---------------------------------------------------------------------------
# Factory-meta sanity (cross-cutting; not its own TC, supports the synthetic
# bookkeeping referenced by every other test).
# ---------------------------------------------------------------------------
def test_factory_marks_room_ref_as_synthetic() -> None:
    """Factory-built RoomRef is registered in the synthetic WeakValueDictionary."""
    ref = make_room_ref()
    assert is_synthetic(ref) is True


def test_factory_marks_agent_ref_as_synthetic() -> None:
    """Factory-built AgentRef is registered in the synthetic WeakValueDictionary."""
    ref = make_agent_ref()
    assert is_synthetic(ref) is True


def test_directly_constructed_room_ref_is_not_synthetic() -> None:
    """RoomRef built outside the factory is correctly *not* registered."""
    ref = RoomRef(room_id=uuid4(), name="raw")
    assert is_synthetic(ref) is False
