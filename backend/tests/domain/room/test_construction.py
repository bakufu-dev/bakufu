"""Room construction + boundary value tests (TC-UT-RM-001 / 002 / 003 / 018).

Covers REQ-RM-001 (construction) + name / description boundary values + the
NFC + strip pipeline (Confirmation B). Each boundary value lives in its own
``Test*`` class so failures cluster by which length contract was violated.
"""

from __future__ import annotations

import pytest
from bakufu.domain.exceptions import RoomInvariantViolation

from tests.factories.room import make_room


class TestMinimalConstruction:
    """TC-UT-RM-001: zero members, empty PromptKit, archived=False default."""

    def test_default_room_has_no_members(self) -> None:
        """TC-UT-RM-001: factory default constructs with members=[]."""
        room = make_room()
        assert room.members == []

    def test_default_room_is_not_archived(self) -> None:
        """TC-UT-RM-001: factory default constructs with archived=False."""
        room = make_room()
        assert room.archived is False

    def test_default_prompt_kit_is_empty(self) -> None:
        """TC-UT-RM-001: factory default constructs with empty prefix_markdown."""
        room = make_room()
        assert room.prompt_kit.prefix_markdown == ""


class TestNameBoundary:
    """TC-UT-RM-002: name length boundary 0 / 1 / 80 / 81 + whitespace."""

    @pytest.mark.parametrize("length", [1, 80])
    def test_valid_lengths_succeed(self, length: int) -> None:
        """TC-UT-RM-002: name lengths 1 and 80 (after NFC + strip) succeed."""
        room = make_room(name="a" * length)
        assert len(room.name) == length

    def test_empty_name_raises_name_range(self) -> None:
        """TC-UT-RM-002: name length 0 raises name_range with detail.length=0."""
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(name="")
        assert excinfo.value.kind == "name_range"
        assert excinfo.value.detail.get("length") == 0

    def test_oversized_name_raises_name_range(self) -> None:
        """TC-UT-RM-002: name length 81 raises name_range with detail.length=81."""
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(name="a" * 81)
        assert excinfo.value.kind == "name_range"
        assert excinfo.value.detail.get("length") == 81

    def test_whitespace_only_name_raises_name_range(self) -> None:
        """TC-UT-RM-002: whitespace-only name (post-strip length=0) raises."""
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(name="   ")
        assert excinfo.value.kind == "name_range"


class TestDescriptionBoundary:
    """TC-UT-RM-003: description length boundary 0 / 500 / 501."""

    @pytest.mark.parametrize("length", [0, 500])
    def test_valid_lengths_succeed(self, length: int) -> None:
        """TC-UT-RM-003: description lengths 0 and 500 succeed."""
        room = make_room(description="a" * length)
        assert len(room.description) == length

    def test_oversized_description_raises_description_too_long(self) -> None:
        """TC-UT-RM-003: description length 501 raises description_too_long."""
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(description="a" * 501)
        assert excinfo.value.kind == "description_too_long"
        assert excinfo.value.detail.get("length") == 501


class TestNfcStripPipeline:
    """TC-UT-RM-018: name / description NFC + strip; PromptKit NFC only (Confirmation B)."""

    def test_name_strips_leading_and_trailing_whitespace(self) -> None:
        """TC-UT-RM-018: '  Vモデル開発室  ' is held as 'Vモデル開発室' after NFC + strip."""
        room = make_room(name="  Vモデル開発室  ")
        assert room.name == "Vモデル開発室"

    def test_description_strips_whitespace(self) -> None:
        """TC-UT-RM-018: description leading/trailing whitespace is stripped."""
        room = make_room(description="  hello  ")
        assert room.description == "hello"

    def test_name_nfc_normalization_unifies_decomposed_form(self) -> None:
        """TC-UT-RM-018: composed and decomposed forms collapse to the same NFC string."""
        # The decomposed form (NFD) of "ダ" splits to "タ" + combining dakuten.
        composed = "ダリオ"
        decomposed = "ダリオ"
        room_composed = make_room(name=composed)
        room_decomposed = make_room(name=decomposed)
        assert room_composed.name == room_decomposed.name

    def test_prompt_kit_preserves_leading_and_trailing_newlines(self) -> None:
        """TC-UT-RM-018: PromptKit applies NFC only — leading/trailing newlines kept.

        agent §確定 E / Room §確定 B: ``prefix_markdown`` is Markdown body
        text where leading/trailing newlines are semantically significant.
        ``strip()`` is *not* applied at the field validator.
        """
        from tests.factories.room import make_prompt_kit

        text = "\n# Heading\n\nbody\n\n"
        room = make_room()
        room2 = room.update_prompt_kit(make_prompt_kit(prefix_markdown=text))
        assert room2.prompt_kit.prefix_markdown == text
