"""Frozen + extra='forbid' contract tests (TC-UT-RM-025 / 026).

Pydantic v2 ``frozen=True`` rejects attribute assignment; ``extra='forbid'``
rejects unknown fields at construction. Both contracts are checked here so
future model_config tweaks cannot silently weaken them.
"""

from __future__ import annotations

import pytest
from bakufu.domain.room import PromptKit, Room
from pydantic import ValidationError

from tests.factories.room import make_prompt_kit, make_room


class TestFrozenAssignmentRejected:
    """TC-UT-RM-025: direct attribute assignment raises ValidationError."""

    def test_assigning_room_name_raises(self) -> None:
        """TC-UT-RM-025: room.name = ... raises ValidationError (frozen)."""
        room = make_room()
        with pytest.raises(ValidationError):
            room.name = "X"  # type: ignore[misc] # frozen, must raise at runtime

    def test_assigning_room_archived_raises(self) -> None:
        """TC-UT-RM-025: room.archived = True raises ValidationError (frozen)."""
        room = make_room()
        with pytest.raises(ValidationError):
            room.archived = True  # type: ignore[misc] # frozen, must raise at runtime

    def test_assigning_prompt_kit_attr_raises(self) -> None:
        """TC-UT-RM-025: prompt_kit.prefix_markdown = ... raises ValidationError."""
        kit = make_prompt_kit()
        with pytest.raises(ValidationError):
            kit.prefix_markdown = "# new"  # type: ignore[misc] # frozen, must raise at runtime


class TestExtraForbidden:
    """TC-UT-RM-026: unknown fields rejected at construction."""

    def test_unknown_field_on_room_raises(self) -> None:
        """TC-UT-RM-026: Room.model_validate({...,'unknown':'x'}) raises."""
        from uuid import uuid4

        with pytest.raises(ValidationError):
            Room.model_validate(
                {
                    "id": str(uuid4()),
                    "name": "test",
                    "description": "",
                    "workflow_id": str(uuid4()),
                    "members": [],
                    "prompt_kit": {"prefix_markdown": ""},
                    "archived": False,
                    "unknown": "x",
                }
            )

    def test_unknown_field_on_prompt_kit_raises(self) -> None:
        """TC-UT-RM-026: PromptKit.model_validate({'prefix_markdown': '', 'unknown': 1}) raises."""
        with pytest.raises(ValidationError):
            PromptKit.model_validate({"prefix_markdown": "", "unknown": 1})
