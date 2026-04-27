"""Directive construction + boundary value tests
(TC-UT-DR-001 / 002 / 003 / 004 / 014 / 015).

Covers REQ-DR-001 (construction) + ``text`` length boundary + NFC
normalization + the deliberately *non-stripping* contract +
constructor-path Repository hydration (§確定 C) + tz-aware enforcement.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.directive import Directive
from bakufu.domain.exceptions import DirectiveInvariantViolation
from pydantic import ValidationError

from tests.factories.directive import (
    make_directive,
    make_linked_directive,
)


class TestDefaultConstruction:
    """TC-UT-DR-001: factory default is a valid Directive with task_id=None."""

    def test_default_directive_has_no_task_link(self) -> None:
        """TC-UT-DR-001: factory default constructs with task_id=None."""
        directive = make_directive()
        assert directive.task_id is None

    def test_default_directive_has_tz_aware_created_at(self) -> None:
        """TC-UT-DR-001: factory default carries a tz-aware datetime."""
        directive = make_directive()
        assert directive.created_at.tzinfo is not None

    def test_default_directive_text_is_short_with_dollar_prefix(self) -> None:
        """TC-UT-DR-001: default text follows the application-layer ``$`` convention."""
        directive = make_directive()
        assert directive.text.startswith("$ ")


class TestTextBoundary:
    """TC-UT-DR-002: text length boundary 0 / 1 / 10000 / 10001 (確定 B)."""

    @pytest.mark.parametrize("length", [1, 10_000])
    def test_valid_lengths_succeed(self, length: int) -> None:
        """TC-UT-DR-002: text lengths 1 and 10000 succeed."""
        directive = make_directive(text="a" * length)
        assert len(directive.text) == length

    def test_empty_text_raises_text_range(self) -> None:
        """TC-UT-DR-002: text length 0 raises text_range with detail.length=0."""
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text="")
        assert excinfo.value.kind == "text_range"
        assert excinfo.value.detail.get("length") == 0

    def test_oversized_text_raises_text_range(self) -> None:
        """TC-UT-DR-002: text length 10001 raises text_range with detail.length=10001."""
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text="a" * 10_001)
        assert excinfo.value.kind == "text_range"
        assert excinfo.value.detail.get("length") == 10_001


class TestNfcNormalization:
    """TC-UT-DR-003: NFC normalization unifies composed and decomposed forms (確定 B)."""

    def test_composed_and_decomposed_forms_collapse(self) -> None:
        """TC-UT-DR-003: composed and decomposed forms produce the same NFC string."""
        composed = "ダリオ要件"
        decomposed = "ダリオ要件"
        d_composed = make_directive(text=composed)
        d_decomposed = make_directive(text=decomposed)
        assert d_composed.text == d_decomposed.text


class TestStripIsNotApplied:
    """TC-UT-DR-004: text is NFC-only, no strip — leading/trailing newlines kept."""

    def test_leading_and_trailing_newlines_are_preserved(self) -> None:
        """TC-UT-DR-004: '\\n# Directive\\n\\nbody\\n\\n' is held verbatim.

        CEO directives may rely on multi-paragraph structure; stripping
        would silently rewrite the intent. Confirmation B freezes this
        as the documented design choice.
        """
        text = "\n# Directive\n\nbody\n\n"
        directive = make_directive(text=text)
        assert directive.text == text


class TestRepositoryHydrationViaConstructor:
    """TC-UT-DR-014: constructor accepts ``task_id=existing TaskId`` (§確定 C)."""

    def test_directive_can_be_constructed_with_task_id(self) -> None:
        """TC-UT-DR-014: Repository-hydrated state ``task_id != None`` constructs cleanly."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        assert directive.task_id == existing_task_id


class TestCreatedAtMustBeTzAware:
    """TC-UT-DR-015: naive datetime raises pydantic.ValidationError (MSG-DR-003)."""

    def test_naive_datetime_is_rejected(self) -> None:
        """TC-UT-DR-015: ``created_at=datetime.utcnow()`` (naive) → ValidationError."""
        # Pydantic surfaces the ``_require_tz_aware`` ValueError as a
        # ``ValidationError`` when the assertion lives inside an
        # ``after`` validator.
        with pytest.raises(ValidationError):
            Directive(
                id=uuid4(),
                text="$ test",
                target_room_id=uuid4(),
                created_at=datetime(2026, 4, 27, 10, 0, 0),  # naive
                task_id=None,
            )

    def test_tz_aware_utc_datetime_succeeds(self) -> None:
        """TC-UT-DR-015 supplemental: tz-aware UTC datetime is the only allowed shape."""
        directive = make_directive(created_at=datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC))
        assert directive.created_at.tzinfo is not None
