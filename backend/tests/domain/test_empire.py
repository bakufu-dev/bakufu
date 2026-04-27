"""Unit + integration tests for the Empire aggregate root.

Covers TC-UT-EM-001〜023 and TC-IT-EM-001〜002 from
``docs/features/empire/test-design.md``. Tests are grouped into ``Test*``
classes by feature surface (construction, name boundaries, hire, capacity,
archive, pre-validate rollback, frozen contract, MSG wording, lifecycle
integration). Each test docstring carries the trace anchor (TC-ID, REQ-ID,
MSG-ID where applicable).

Integration scenarios live in this file rather than under ``integration/``
because the aggregate is pure domain (zero external I/O) — the test-design
intentionally consolidates "Aggregate-internal round-trip" cases here.
"""

from __future__ import annotations

import unicodedata
from uuid import uuid4

import pytest
from bakufu.domain.empire import MAX_AGENTS, MAX_ROOMS, Empire
from bakufu.domain.exceptions import EmpireInvariantViolation
from bakufu.domain.value_objects import AgentRef, Role, RoomRef
from pydantic import ValidationError

from tests.factories.empire import make_agent_ref, make_empire, make_room_ref

# ===========================================================================
# REQ-EM-001 — Construction & name normalization
# ===========================================================================


class TestEmpireConstruction:
    """Empire(id, name) initialization contract (TC-UT-EM-001)."""

    def test_minimal_empire_has_empty_rooms_and_agents(self) -> None:
        """TC-UT-EM-001: minimal Empire(id, name) returns rooms=[] / agents=[]."""
        empire = make_empire(name="山田の幕府")
        assert empire.rooms == [] and empire.agents == []

    def test_construction_preserves_input_name(self) -> None:
        """TC-UT-EM-001: Empire.name reflects input after NFC+strip pipeline."""
        empire = make_empire(name="山田の幕府")
        assert empire.name == "山田の幕府"


class TestEmpireNameBoundaries:
    """Empire.name length contract (TC-UT-EM-002, MSG-EM-001)."""

    @pytest.mark.parametrize("valid_length", [1, 80])
    def test_accepts_lower_and_upper_boundary(self, valid_length: int) -> None:
        """TC-UT-EM-002: 1-char and 80-char names construct successfully."""
        empire = make_empire(name="a" * valid_length)
        assert len(empire.name) == valid_length

    @pytest.mark.parametrize("invalid_name", ["", "a" * 81, "   "])
    def test_rejects_zero_eightyone_or_whitespace_only(self, invalid_name: str) -> None:
        """TC-UT-EM-002: 0-char / 81-char / whitespace-only names raise."""
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            make_empire(name=invalid_name)
        assert excinfo.value.kind == "name_range"


class TestEmpireNameNormalization:
    """NFC + strip pipeline (TC-UT-EM-003, Confirmation B)."""

    def test_decomposed_kana_is_normalized_to_nfc(self) -> None:
        """TC-UT-EM-003: decomposed kana with dakuten is normalized to NFC form."""
        # 'がが' has true decomposition: U+304C → U+304B U+3099 (kana + combining
        # voicing mark). Pure katakana like テスト has no decomposition, so
        # cannot demonstrate the NFC pipeline.
        composed = "がが"
        decomposed = unicodedata.normalize("NFD", composed)
        assert decomposed != composed  # sanity: input is actually decomposed
        empire = make_empire(name=decomposed)
        assert empire.name == composed

    def test_surrounding_whitespace_is_stripped(self) -> None:
        """TC-UT-EM-003: leading/trailing whitespace is stripped before storage."""
        empire = make_empire(name="  山田の幕府  ")
        assert empire.name == "山田の幕府"


# ===========================================================================
# REQ-EM-002 — hire_agent
# ===========================================================================


class TestHireAgent:
    """hire_agent contract (TC-UT-EM-004 / 005 / 006)."""

    def test_appends_new_agent_to_list(self) -> None:
        """TC-UT-EM-004: hire_agent returns a new Empire with the agent appended."""
        empire = make_empire()
        agent = make_agent_ref()
        updated = empire.hire_agent(agent)
        assert updated.agents == [agent]

    def test_does_not_mutate_original_aggregate(self) -> None:
        """TC-UT-EM-004: original Empire's agents stay empty after hire_agent."""
        empire = make_empire()
        empire.hire_agent(make_agent_ref())
        assert empire.agents == []

    def test_three_consecutive_distinct_hires_all_persist(self) -> None:
        """TC-UT-EM-005: chained hire_agent yields all three distinct agents."""
        empire = make_empire()
        a1, a2, a3 = make_agent_ref(), make_agent_ref(), make_agent_ref()
        final = empire.hire_agent(a1).hire_agent(a2).hire_agent(a3)
        assert {ref.agent_id for ref in final.agents} == {
            a1.agent_id,
            a2.agent_id,
            a3.agent_id,
        }

    def test_rejects_duplicate_agent_id(self) -> None:
        """TC-UT-EM-006: rehiring the same agent_id raises agent_duplicate."""
        empire = make_empire()
        agent = make_agent_ref()
        after_first_hire = empire.hire_agent(agent)
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            duplicate = AgentRef(agent_id=agent.agent_id, name="別名", role=Role.LEADER)
            after_first_hire.hire_agent(duplicate)
        assert excinfo.value.kind == "agent_duplicate"


class TestHireAgentCapacity:
    """hire_agent capacity boundary (TC-UT-EM-007, Confirmation C)."""

    def test_succeeds_at_max_agents(self) -> None:
        """TC-UT-EM-007: hiring up to MAX_AGENTS succeeds."""
        empire = make_empire()
        for _ in range(MAX_AGENTS):
            empire = empire.hire_agent(make_agent_ref())
        assert len(empire.agents) == MAX_AGENTS

    def test_overflow_raises_capacity_exceeded(self) -> None:
        """TC-UT-EM-007: hiring the (MAX_AGENTS+1)-th agent raises capacity_exceeded."""
        empire = make_empire()
        for _ in range(MAX_AGENTS):
            empire = empire.hire_agent(make_agent_ref())
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.hire_agent(make_agent_ref())
        assert excinfo.value.kind == "capacity_exceeded"


# ===========================================================================
# REQ-EM-003 — establish_room
# ===========================================================================


class TestEstablishRoom:
    """establish_room contract (TC-UT-EM-008 / 009)."""

    def test_appends_new_room_to_list(self) -> None:
        """TC-UT-EM-008: establish_room returns a new Empire with the room appended."""
        empire = make_empire()
        room = make_room_ref()
        updated = empire.establish_room(room)
        assert updated.rooms == [room]

    def test_does_not_mutate_original_aggregate(self) -> None:
        """TC-UT-EM-008: original Empire's rooms stay empty after establish_room."""
        empire = make_empire()
        empire.establish_room(make_room_ref())
        assert empire.rooms == []

    def test_rejects_duplicate_room_id(self) -> None:
        """TC-UT-EM-009: re-establishing the same room_id raises room_duplicate."""
        empire = make_empire()
        room = make_room_ref()
        after_first = empire.establish_room(room)
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            duplicate = RoomRef(room_id=room.room_id, name="別名")
            after_first.establish_room(duplicate)
        assert excinfo.value.kind == "room_duplicate"


class TestEstablishRoomCapacity:
    """establish_room capacity boundary (TC-UT-EM-010, Confirmation C)."""

    def test_succeeds_at_max_rooms(self) -> None:
        """TC-UT-EM-010: establishing up to MAX_ROOMS succeeds."""
        empire = make_empire()
        for _ in range(MAX_ROOMS):
            empire = empire.establish_room(make_room_ref())
        assert len(empire.rooms) == MAX_ROOMS

    def test_overflow_raises_capacity_exceeded(self) -> None:
        """TC-UT-EM-010: establishing the (MAX_ROOMS+1)-th room raises capacity_exceeded."""
        empire = make_empire()
        for _ in range(MAX_ROOMS):
            empire = empire.establish_room(make_room_ref())
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.establish_room(make_room_ref())
        assert excinfo.value.kind == "capacity_exceeded"


# ===========================================================================
# REQ-EM-004 — archive_room
# ===========================================================================


class TestArchiveRoom:
    """archive_room contract (TC-UT-EM-011 / 012 / 013)."""

    def test_marks_target_room_as_archived(self) -> None:
        """TC-UT-EM-011: archive_room flips archived=True on the matching RoomRef."""
        rooms = [make_room_ref(), make_room_ref(), make_room_ref()]
        empire = make_empire(rooms=rooms)
        target = rooms[1]
        updated = empire.archive_room(target.room_id)
        archived = next(r for r in updated.rooms if r.room_id == target.room_id)
        assert archived.archived is True

    def test_leaves_other_rooms_unchanged(self) -> None:
        """TC-UT-EM-011: rooms other than the target retain archived=False."""
        rooms = [make_room_ref(), make_room_ref(), make_room_ref()]
        empire = make_empire(rooms=rooms)
        target = rooms[1]
        updated = empire.archive_room(target.room_id)
        others = [r for r in updated.rooms if r.room_id != target.room_id]
        assert all(r.archived is False for r in others)

    def test_unknown_room_id_raises_room_not_found(self) -> None:
        """TC-UT-EM-012: archiving a non-existent room_id raises room_not_found."""
        empire = make_empire(rooms=[make_room_ref()])
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.archive_room(uuid4())
        assert excinfo.value.kind == "room_not_found"

    def test_does_not_physically_delete_target(self) -> None:
        """TC-UT-EM-013: archive_room preserves rooms list length (logical archive)."""
        rooms = [make_room_ref()]
        empire = make_empire(rooms=rooms)
        updated = empire.archive_room(rooms[0].room_id)
        assert len(updated.rooms) == 1


# ===========================================================================
# REQ-EM-005 — pre-validate rollback (Confirmation A)
# ===========================================================================


class TestPreValidateRollback:
    """Failed mutations leave the original Empire unchanged (TC-UT-EM-014〜016)."""

    def test_failed_hire_agent_keeps_original_empire(self) -> None:
        """TC-UT-EM-014: failed hire_agent does not mutate caller's Empire."""
        agent = make_agent_ref()
        empire = make_empire(agents=[agent])
        with pytest.raises(EmpireInvariantViolation):
            empire.hire_agent(AgentRef(agent_id=agent.agent_id, name="dup", role=Role.LEADER))
        assert empire.agents == [agent]

    def test_failed_establish_room_keeps_original_empire(self) -> None:
        """TC-UT-EM-015: failed establish_room does not mutate caller's Empire."""
        room = make_room_ref()
        empire = make_empire(rooms=[room])
        with pytest.raises(EmpireInvariantViolation):
            empire.establish_room(RoomRef(room_id=room.room_id, name="dup"))
        assert empire.rooms == [room]

    def test_failed_archive_room_keeps_archived_flags(self) -> None:
        """TC-UT-EM-016: failed archive_room preserves all archived flags."""
        room = make_room_ref()
        empire = make_empire(rooms=[room])
        with pytest.raises(EmpireInvariantViolation):
            empire.archive_room(uuid4())
        assert empire.rooms[0].archived is False


# ===========================================================================
# Frozen contract & extra='forbid' (REQ-EM-005)
# ===========================================================================


class TestFrozenContract:
    """frozen=True forbids attribute assignment (TC-UT-EM-017)."""

    def test_empire_rejects_attribute_assignment(self) -> None:
        """TC-UT-EM-017: Empire is frozen — direct attribute set raises."""
        empire = make_empire()
        with pytest.raises(ValidationError):
            empire.name = "改竄"  # type: ignore[misc]

    def test_room_ref_rejects_attribute_assignment(self) -> None:
        """TC-UT-EM-017: RoomRef is frozen — direct attribute set raises."""
        ref = make_room_ref()
        with pytest.raises(ValidationError):
            ref.archived = True  # type: ignore[misc]

    def test_agent_ref_rejects_attribute_assignment(self) -> None:
        """TC-UT-EM-017: AgentRef is frozen — direct attribute set raises."""
        ref = make_agent_ref()
        with pytest.raises(ValidationError):
            ref.role = Role.LEADER  # type: ignore[misc]


class TestExtraForbid:
    """extra='forbid' rejects unknown fields (TC-UT-EM-018)."""

    def test_model_validate_rejects_unknown_field(self) -> None:
        """TC-UT-EM-018: extra='forbid' rejects unknown fields at construction."""
        payload: dict[str, object] = {
            "id": str(uuid4()),
            "name": "ok",
            "rooms": [],
            "agents": [],
            "unknown_field": "should-be-rejected",
        }
        with pytest.raises(ValidationError):
            Empire.model_validate(payload)


# ===========================================================================
# MSG-EM-001〜005 — exact wording assertions
# ===========================================================================


class TestMessageWording:
    """Message strings match detailed-design §MSG exactly (TC-UT-EM-019〜023)."""

    def test_msg_em_001_for_oversized_name(self) -> None:
        """TC-UT-EM-019: MSG-EM-001 wording matches '[FAIL] Empire name ...'."""
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            make_empire(name="a" * 81)
        assert excinfo.value.message == "[FAIL] Empire name must be 1-80 characters (got 81)"

    def test_msg_em_001_for_whitespace_only_reports_post_strip_length(self) -> None:
        """TC-UT-EM-019: NFC+strip pipeline reports length=0 for whitespace-only input."""
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            make_empire(name="   ")
        assert excinfo.value.message == "[FAIL] Empire name must be 1-80 characters (got 0)"

    def test_msg_em_002_includes_duplicate_agent_id(self) -> None:
        """TC-UT-EM-020: MSG-EM-002 wording carries the offending agent_id."""
        agent = make_agent_ref()
        empire = make_empire(agents=[agent])
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.hire_agent(AgentRef(agent_id=agent.agent_id, name="x", role=Role.LEADER))
        assert excinfo.value.message == f"[FAIL] Agent already hired: agent_id={agent.agent_id}"

    def test_msg_em_003_includes_duplicate_room_id(self) -> None:
        """TC-UT-EM-021: MSG-EM-003 wording carries the offending room_id."""
        room = make_room_ref()
        empire = make_empire(rooms=[room])
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.establish_room(RoomRef(room_id=room.room_id, name="x"))
        assert excinfo.value.message == f"[FAIL] Room already established: room_id={room.room_id}"

    def test_msg_em_004_includes_missing_room_id(self) -> None:
        """TC-UT-EM-022: MSG-EM-004 wording carries the missing room_id."""
        empire = make_empire()
        unknown = uuid4()
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.archive_room(unknown)
        assert excinfo.value.message == f"[FAIL] Room not found in Empire: room_id={unknown}"

    def test_msg_em_005_uses_invariant_violation_prefix(self) -> None:
        """TC-UT-EM-023: MSG-EM-005 starts with '[FAIL] Empire invariant violation:'."""
        empire = make_empire()
        for _ in range(MAX_AGENTS):
            empire = empire.hire_agent(make_agent_ref())
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.hire_agent(make_agent_ref())
        assert excinfo.value.message.startswith("[FAIL] Empire invariant violation:")


# ===========================================================================
# Integration scenarios — Aggregate-internal round trip (TC-IT-EM-001 / 002)
# ===========================================================================


class TestEmpireLifecycleIntegration:
    """Aggregate-internal round-trip and resilience (TC-IT-EM-001 / 002)."""

    def test_full_lifecycle_hire_establish_archive_round_trip(self) -> None:
        """TC-IT-EM-001: Empire→hire→establish→archive yields expected final state."""
        empire = make_empire()
        agent = make_agent_ref()
        room = make_room_ref()
        after_hire = empire.hire_agent(agent)
        after_establish = after_hire.establish_room(room)
        after_archive = after_establish.archive_room(room.room_id)
        final_room = after_archive.rooms[0]
        assert (
            len(after_archive.agents) == 1
            and len(after_archive.rooms) == 1
            and final_room.archived is True
        )

    def test_full_lifecycle_keeps_intermediates_immutable(self) -> None:
        """TC-IT-EM-001: every intermediate Empire stays unmodified through the chain."""
        empire = make_empire()
        after_hire = empire.hire_agent(make_agent_ref())
        after_hire.establish_room(make_room_ref())  # discard return value
        assert empire.agents == [] and empire.rooms == [] and len(after_hire.rooms) == 0

    def test_failed_hire_does_not_block_subsequent_operations(self) -> None:
        """TC-IT-EM-002: a failed hire_agent leaves Empire ready for further changes."""
        agent = make_agent_ref()
        empire = make_empire(agents=[agent])

        # 1) Duplicate hire fails, original is untouched.
        with pytest.raises(EmpireInvariantViolation):
            empire.hire_agent(AgentRef(agent_id=agent.agent_id, name="x", role=Role.LEADER))

        # 2) establish_room then succeeds against the unchanged aggregate.
        new_room = make_room_ref()
        after_establish = empire.establish_room(new_room)

        # 3) archive_room then succeeds against that further-mutated aggregate.
        after_archive = after_establish.archive_room(new_room.room_id)
        final_room = after_archive.rooms[0]
        assert (
            len(empire.agents) == 1
            and len(after_establish.rooms) == 1
            and final_room.archived is True
        )
