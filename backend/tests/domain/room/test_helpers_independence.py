"""Module-level helper independence (Boy Scout twin-defense symmetry).

Steve PR #16 / Norman PR #16 approved: every aggregate-level invariant
helper lives at module scope so tests can ``import`` and invoke directly.
Mirrors the agent ``test_helpers_independence.py`` pattern. These tests
freeze the helper signatures and entry-point contract — the Aggregate stays
a thin dispatch over them, and a refactor that inlines a helper back into
the model_validator has to update this test file too.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import RoomInvariantViolation
from bakufu.domain.room import (
    MAX_DESCRIPTION_LENGTH,
    MAX_MEMBERS,
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
    _validate_description_length,
    _validate_member_capacity,
    _validate_member_unique,
    _validate_name_range,
)
from bakufu.domain.value_objects import Role

from tests.factories.room import make_agent_membership, make_leader_membership


class TestValidateNameRange:
    """``_validate_name_range`` is a module-level pure function."""

    @pytest.mark.parametrize("length", [MIN_NAME_LENGTH, MAX_NAME_LENGTH])
    def test_valid_lengths_return_none(self, length: int) -> None:
        """Valid lengths return ``None`` without raising."""
        result = _validate_name_range("a" * length)
        assert result is None

    @pytest.mark.parametrize("length", [0, MAX_NAME_LENGTH + 1])
    def test_invalid_lengths_raise_name_range(self, length: int) -> None:
        """Out-of-range lengths raise ``RoomInvariantViolation(kind='name_range')``."""
        with pytest.raises(RoomInvariantViolation) as excinfo:
            _validate_name_range("a" * length)
        assert excinfo.value.kind == "name_range"


class TestValidateDescriptionLength:
    """``_validate_description_length`` is a module-level pure function."""

    def test_valid_lengths_return_none(self) -> None:
        """0 and MAX_DESCRIPTION_LENGTH return ``None``."""
        assert _validate_description_length("") is None
        assert _validate_description_length("a" * MAX_DESCRIPTION_LENGTH) is None

    def test_oversized_raises_description_too_long(self) -> None:
        """501 chars raises ``description_too_long``."""
        with pytest.raises(RoomInvariantViolation) as excinfo:
            _validate_description_length("a" * (MAX_DESCRIPTION_LENGTH + 1))
        assert excinfo.value.kind == "description_too_long"


class TestValidateMemberUnique:
    """``_validate_member_unique`` is a module-level pure function (Confirmation F)."""

    def test_empty_members_returns_none(self) -> None:
        """An empty member list passes vacuously."""
        assert _validate_member_unique([]) is None

    def test_unique_pairs_pass(self) -> None:
        """Distinct ``(agent_id, role)`` pairs pass."""
        members = [
            make_leader_membership(agent_id=uuid4()),
            make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER),
        ]
        assert _validate_member_unique(members) is None

    def test_same_agent_different_role_passes(self) -> None:
        """Confirmation F: same agent_id under different roles is allowed."""
        agent_id = uuid4()
        members = [
            make_leader_membership(agent_id=agent_id),
            make_agent_membership(agent_id=agent_id, role=Role.REVIEWER),
        ]
        assert _validate_member_unique(members) is None

    def test_duplicate_pair_raises_member_duplicate(self) -> None:
        """Same ``(agent_id, role)`` raises ``member_duplicate``."""
        agent_id = uuid4()
        members = [
            make_leader_membership(agent_id=agent_id),
            make_leader_membership(agent_id=agent_id),
        ]
        with pytest.raises(RoomInvariantViolation) as excinfo:
            _validate_member_unique(members)
        assert excinfo.value.kind == "member_duplicate"


class TestValidateMemberCapacity:
    """``_validate_member_capacity`` is a module-level pure function (Confirmation C)."""

    def test_at_capacity_returns_none(self) -> None:
        """``MAX_MEMBERS`` entries pass."""
        members = [
            make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER) for _ in range(MAX_MEMBERS)
        ]
        assert _validate_member_capacity(members) is None

    def test_overflow_raises_capacity_exceeded(self) -> None:
        """``MAX_MEMBERS + 1`` raises ``capacity_exceeded``."""
        members = [
            make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
            for _ in range(MAX_MEMBERS + 1)
        ]
        with pytest.raises(RoomInvariantViolation) as excinfo:
            _validate_member_capacity(members)
        assert excinfo.value.kind == "capacity_exceeded"
