"""MSG-RM-001〜007 wording + Next: hint physical guarantee (TC-UT-RM-031〜037).

Each MSG follows a 2-line structure (Confirmation I, Norman R1):

    [FAIL] <failure fact>
    Next: <recommended next action>

The first line is asserted **exactly** so future i18n / refactoring cannot
silently drift the operator-visible failure fact. The second line is
asserted via substring on the leading ``Next:`` token *and* a topic phrase
so the design-time hint contract survives cosmetic edits while the
"hint exists" property is locked in by CI.

MSG-RM-007 travels the :class:`pydantic.ValidationError` path (PromptKit VO
construction) per Confirmation I two-stage catch — *not* the
:class:`RoomInvariantViolation` path. The test below pins that contract.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import RoomInvariantViolation
from bakufu.domain.room import MAX_MEMBERS, PROMPT_KIT_PREFIX_MAX, PromptKit
from bakufu.domain.value_objects import Role
from pydantic import ValidationError

from tests.factories.room import (
    make_agent_membership,
    make_archived_room,
    make_leader_membership,
    make_room,
)


class TestMsgRm001NameRange:
    """TC-UT-RM-031: MSG-RM-001 + Next: hint."""

    def test_failure_line_matches_exact_wording(self) -> None:
        """TC-UT-RM-031: failure line '[FAIL] Room name must be 1-80 ...' exact."""
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(name="a" * 81)
        assert excinfo.value.message.startswith("[FAIL] Room name must be 1-80 characters (got 81)")

    def test_next_hint_present(self) -> None:
        """TC-UT-RM-031: 'Next:' hint exists with NFC-normalized topic phrase."""
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(name="a" * 81)
        assert "Next:" in excinfo.value.message
        assert "1-80 NFC-normalized" in excinfo.value.message


class TestMsgRm002DescriptionTooLong:
    """TC-UT-RM-032: MSG-RM-002 + Next: hint."""

    def test_failure_line_matches_exact_wording(self) -> None:
        """TC-UT-RM-032: failure line '[FAIL] Room description must be 0-500 ...' exact."""
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(description="a" * 501)
        assert excinfo.value.message.startswith(
            "[FAIL] Room description must be 0-500 characters (got 501)"
        )

    def test_next_hint_routes_overflow_to_prompt_kit(self) -> None:
        """TC-UT-RM-032: 'Next:' hint mentions PromptKit.prefix_markdown overflow path."""
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(description="a" * 501)
        assert "Next:" in excinfo.value.message
        assert "PromptKit.prefix_markdown" in excinfo.value.message


class TestMsgRm003MemberDuplicate:
    """TC-UT-RM-033: MSG-RM-003 + Next: hint (different role suggestion)."""

    def test_failure_line_includes_pair_identifiers(self) -> None:
        """TC-UT-RM-033: '[FAIL] Duplicate member: agent_id=..., role=LEADER' format."""
        agent_id = uuid4()
        m1 = make_leader_membership(agent_id=agent_id)
        m2 = make_leader_membership(agent_id=agent_id)
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(members=[m1, m2])
        assert "[FAIL] Duplicate member" in excinfo.value.message
        assert f"agent_id={agent_id}" in excinfo.value.message
        assert "role=LEADER" in excinfo.value.message

    def test_next_hint_recommends_different_role(self) -> None:
        """TC-UT-RM-033: 'Next:' hint mentions different role (leader + reviewer)."""
        agent_id = uuid4()
        m1 = make_leader_membership(agent_id=agent_id)
        m2 = make_leader_membership(agent_id=agent_id)
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(members=[m1, m2])
        assert "Next:" in excinfo.value.message
        assert "different role" in excinfo.value.message


class TestMsgRm004CapacityExceeded:
    """TC-UT-RM-034: MSG-RM-004 + Next: hint (remove or split)."""

    def test_failure_line_matches_exact_wording(self) -> None:
        """TC-UT-RM-034: '[FAIL] Room members capacity exceeded (got 51, max 50)' exact."""
        members = [
            make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
            for _ in range(MAX_MEMBERS + 1)
        ]
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(members=members)
        assert excinfo.value.message.startswith(
            f"[FAIL] Room members capacity exceeded (got {MAX_MEMBERS + 1}, max {MAX_MEMBERS})"
        )

    def test_next_hint_routes_to_remove_or_split(self) -> None:
        """TC-UT-RM-034: 'Next:' hint suggests remove unused members or split work."""
        members = [
            make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
            for _ in range(MAX_MEMBERS + 1)
        ]
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(members=members)
        assert "Next:" in excinfo.value.message
        assert ("Remove unused members" in excinfo.value.message) or (
            "split the work" in excinfo.value.message
        )


class TestMsgRm005MemberNotFound:
    """TC-UT-RM-035: MSG-RM-005 + Next: hint."""

    def test_failure_line_matches_format(self) -> None:
        """TC-UT-RM-035: '[FAIL] Member not found: agent_id=..., role=DEVELOPER' format."""
        room = make_room(members=[])
        unknown = uuid4()
        with pytest.raises(RoomInvariantViolation) as excinfo:
            room.remove_member(unknown, Role.DEVELOPER)
        assert "[FAIL] Member not found" in excinfo.value.message
        assert f"agent_id={unknown}" in excinfo.value.message
        assert "role=DEVELOPER" in excinfo.value.message

    def test_next_hint_routes_to_get_members_endpoint(self) -> None:
        """TC-UT-RM-035: 'Next:' hint routes operator to GET /rooms or 'already removed'."""
        room = make_room(members=[])
        with pytest.raises(RoomInvariantViolation) as excinfo:
            room.remove_member(uuid4(), Role.DEVELOPER)
        assert "Next:" in excinfo.value.message
        assert ("GET /rooms/" in excinfo.value.message) or (
            "already removed" in excinfo.value.message
        )


class TestMsgRm006RoomArchived:
    """TC-UT-RM-036: MSG-RM-006 + Next: hint (Phase 2 unarchive)."""

    def test_failure_line_includes_room_id(self) -> None:
        """TC-UT-RM-036: '[FAIL] Cannot modify archived Room: room_id=...' format."""
        room_id = uuid4()
        room = make_archived_room(room_id=room_id)
        with pytest.raises(RoomInvariantViolation) as excinfo:
            room.add_member(make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER))
        assert "[FAIL] Cannot modify archived Room" in excinfo.value.message
        assert f"room_id={room_id}" in excinfo.value.message

    def test_next_hint_mentions_create_new_room_and_phase_2(self) -> None:
        """TC-UT-RM-036: 'Next:' hint advises creating a new Room and notes Phase 2."""
        room = make_archived_room()
        with pytest.raises(RoomInvariantViolation) as excinfo:
            room.add_member(make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER))
        assert "Next:" in excinfo.value.message
        assert "Create a new Room" in excinfo.value.message
        assert "Phase 2" in excinfo.value.message


class TestMsgRm007PromptKitTooLong:
    """TC-UT-RM-037: MSG-RM-007 via pydantic.ValidationError (Confirmation I).

    Length violations on PromptKit fail at VO construction with
    :class:`ValidationError` — *not* :class:`RoomInvariantViolation`. The
    aggregate's ``kind`` Literal intentionally omits ``prompt_kit_too_long``
    so the dead-code path is closed by construction (Norman R2 / §確定 I).
    """

    def test_failure_line_includes_get_length(self) -> None:
        """TC-UT-RM-037: ValidationError carries '[FAIL] PromptKit.prefix_markdown ...'."""
        with pytest.raises(ValidationError) as excinfo:
            PromptKit(prefix_markdown="a" * (PROMPT_KIT_PREFIX_MAX + 1))
        msg = str(excinfo.value)
        assert (
            f"[FAIL] PromptKit.prefix_markdown must be 0-{PROMPT_KIT_PREFIX_MAX} "
            f"characters (got {PROMPT_KIT_PREFIX_MAX + 1})"
        ) in msg

    def test_next_hint_mentions_phase_2_extensions(self) -> None:
        """TC-UT-RM-037: 'Next:' hint references Phase 2 sections / variables."""
        with pytest.raises(ValidationError) as excinfo:
            PromptKit(prefix_markdown="a" * (PROMPT_KIT_PREFIX_MAX + 1))
        msg = str(excinfo.value)
        assert "Next:" in msg
        # Phase 2 extension keywords from detailed-design.md §確定 I.
        assert "variables" in msg or "role_specific_prefix" in msg or "sections" in msg
