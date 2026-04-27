"""Frozen + extra='forbid' contract tests + structural equality
(TC-UT-DR-008 / 020 / 021).

Pydantic v2 ``frozen=True`` rejects attribute assignment;
``extra='forbid'`` rejects unknown fields at construction; structural
equality returns True for two Directives with identical attribute
values. Same rule the agent / room / empire / workflow precedents
follow.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.directive import Directive
from pydantic import ValidationError

from tests.factories.directive import make_directive


class TestFrozenAssignmentRejected:
    """TC-UT-DR-020: direct attribute assignment raises ValidationError."""

    def test_assigning_text_raises(self) -> None:
        """TC-UT-DR-020: directive.text = ... raises ValidationError (frozen)."""
        directive = make_directive()
        with pytest.raises(ValidationError):
            directive.text = "X"  # type: ignore[misc] # frozen, must raise at runtime

    def test_assigning_task_id_raises(self) -> None:
        """TC-UT-DR-020: directive.task_id = ... raises ValidationError (frozen)."""
        directive = make_directive()
        with pytest.raises(ValidationError):
            directive.task_id = uuid4()  # type: ignore[misc] # frozen, must raise at runtime

    def test_assigning_target_room_id_raises(self) -> None:
        """TC-UT-DR-020: directive.target_room_id = ... raises ValidationError (frozen)."""
        directive = make_directive()
        with pytest.raises(ValidationError):
            directive.target_room_id = uuid4()  # type: ignore[misc] # frozen, must raise at runtime


class TestExtraForbidden:
    """TC-UT-DR-021: unknown fields rejected at construction."""

    def test_unknown_field_raises(self) -> None:
        """TC-UT-DR-021: Directive.model_validate({...,'unknown':'x'}) raises."""
        with pytest.raises(ValidationError):
            Directive.model_validate(
                {
                    "id": str(uuid4()),
                    "text": "$ test",
                    "target_room_id": str(uuid4()),
                    "created_at": datetime.now(UTC).isoformat(),
                    "task_id": None,
                    "unknown": "x",
                }
            )


class TestStructuralEquality:
    """TC-UT-DR-008: two Directives with same attribute values compare equal + share hash."""

    def test_identical_directives_compare_equal(self) -> None:
        """TC-UT-DR-008: equality is structural, not by identity."""
        directive_id = uuid4()
        target_room_id = uuid4()
        created_at = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)
        a = Directive(
            id=directive_id,
            text="$ test",
            target_room_id=target_room_id,
            created_at=created_at,
            task_id=None,
        )
        b = Directive(
            id=directive_id,
            text="$ test",
            target_room_id=target_room_id,
            created_at=created_at,
            task_id=None,
        )
        assert a == b

    def test_identical_directives_share_hash(self) -> None:
        """TC-UT-DR-008: structurally equal Directives hash to the same value."""
        directive_id = uuid4()
        target_room_id = uuid4()
        created_at = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)
        a = Directive(
            id=directive_id,
            text="$ test",
            target_room_id=target_room_id,
            created_at=created_at,
            task_id=None,
        )
        b = Directive(
            id=directive_id,
            text="$ test",
            target_room_id=target_room_id,
            created_at=created_at,
            task_id=None,
        )
        assert hash(a) == hash(b)

    def test_directives_with_different_task_id_compare_unequal(self) -> None:
        """TC-UT-DR-008: linked vs unlinked Directive must differ."""
        directive = make_directive()
        linked = directive.link_task(uuid4())
        assert directive != linked
