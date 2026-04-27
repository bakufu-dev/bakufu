"""PromptKit Value Object tests (TC-UT-RM-019 / 024, Confirmations B / G).

PromptKit is a single-attribute frozen VO held to NFC normalization (no
strip — Markdown body retains leading/trailing whitespace) and a 10000-char
upper bound. Length violations surface as :class:`pydantic.ValidationError`
*not* :class:`RoomInvariantViolation` per Room §確定 I two-stage catch.
"""

from __future__ import annotations

import pytest
from bakufu.domain.room import PROMPT_KIT_PREFIX_MAX, PromptKit
from pydantic import ValidationError

from tests.factories.room import make_prompt_kit, make_room


class TestPromptKitBoundary:
    """TC-UT-RM-019: 0 / 10000 / 10001 + leading/trailing newline preservation."""

    @pytest.mark.parametrize("length", [0, PROMPT_KIT_PREFIX_MAX])
    def test_valid_lengths_succeed(self, length: int) -> None:
        """TC-UT-RM-019: prefix_markdown of length 0 and 10000 succeed."""
        kit = make_prompt_kit(prefix_markdown="a" * length)
        assert len(kit.prefix_markdown) == length

    def test_oversized_prefix_raises_validation_error(self) -> None:
        """TC-UT-RM-019: 10001 chars raises pydantic.ValidationError per §確定 I."""
        with pytest.raises(ValidationError) as excinfo:
            make_prompt_kit(prefix_markdown="a" * (PROMPT_KIT_PREFIX_MAX + 1))
        # Confirmation I freezes that PromptKit length errors do *not* travel
        # the RoomInvariantViolation path. The MSG-RM-007 wording is asserted
        # in test_msg_wording.py.
        assert "PromptKit.prefix_markdown" in str(excinfo.value)

    def test_prompt_kit_preserves_leading_and_trailing_newlines(self) -> None:
        """TC-UT-RM-019 + 018: PromptKit applies NFC only — newlines kept.

        Markdown semantics: ``\\n# Heading\\n\\nbody\\n\\n`` retains the
        wrapping newlines because the body's trailing whitespace is part of
        the prompt template.
        """
        text = "\n# Heading\n\nbody\n\n"
        kit = make_prompt_kit(prefix_markdown=text)
        assert kit.prefix_markdown == text


class TestPromptKitStructuralEquality:
    """TC-UT-RM-024: PromptKit / Room frozen → structural equality + hashable."""

    def test_two_prompt_kits_with_same_attrs_compare_equal(self) -> None:
        """TC-UT-RM-024: two PromptKits with identical prefix compare equal."""
        a = PromptKit(prefix_markdown="hello")
        b = PromptKit(prefix_markdown="hello")
        assert a == b

    def test_two_prompt_kits_with_same_attrs_hash_equal(self) -> None:
        """TC-UT-RM-024: structurally equal PromptKits share hash."""
        a = PromptKit(prefix_markdown="hello")
        b = PromptKit(prefix_markdown="hello")
        assert hash(a) == hash(b)

    def test_two_rooms_with_same_attrs_compare_equal(self) -> None:
        """TC-UT-RM-024: two Rooms with identical attributes compare equal."""
        from uuid import uuid4

        room_id = uuid4()
        workflow_id = uuid4()
        a = make_room(room_id=room_id, workflow_id=workflow_id)
        b = make_room(room_id=room_id, workflow_id=workflow_id)
        assert a == b
