"""Module-level helper independence (Boy Scout twin-defense symmetry).

agent / room precedent: every aggregate-level invariant helper lives at
module scope so tests can ``import`` and invoke directly. Mirrors the
agent / room ``test_helpers_independence.py`` pattern. These tests
freeze the helper signatures and entry-point contract — the Aggregate
stays a thin dispatch over them, and a refactor that inlines a helper
back into the model_validator has to update this test file too.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.directive import (
    MAX_TEXT_LENGTH,
    MIN_TEXT_LENGTH,
    _validate_task_link_immutable,
    _validate_text_range,
)
from bakufu.domain.exceptions import DirectiveInvariantViolation


class TestValidateTextRange:
    """``_validate_text_range`` is a module-level pure function."""

    @pytest.mark.parametrize("length", [MIN_TEXT_LENGTH, MAX_TEXT_LENGTH])
    def test_valid_lengths_return_none(self, length: int) -> None:
        """Valid lengths return ``None`` without raising."""
        result = _validate_text_range("a" * length)
        assert result is None

    @pytest.mark.parametrize("length", [0, MAX_TEXT_LENGTH + 1])
    def test_invalid_lengths_raise_text_range(self, length: int) -> None:
        """Out-of-range lengths raise ``DirectiveInvariantViolation(kind='text_range')``."""
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            _validate_text_range("a" * length)
        assert excinfo.value.kind == "text_range"


class TestValidateTaskLinkImmutable:
    """``_validate_task_link_immutable`` is a module-level pure function (確定 C / D)."""

    def test_existing_none_passes(self) -> None:
        """Confirmation C: existing_task_id=None permits any attempted_task_id."""
        directive_id = uuid4()
        attempted = uuid4()
        # Returns ``None`` (no raise) when existing is None.
        result = _validate_task_link_immutable(
            directive_id=directive_id,
            existing_task_id=None,
            attempted_task_id=attempted,
        )
        assert result is None

    def test_existing_value_raises_on_different_attempt(self) -> None:
        """Confirmation C: existing → different new task_id raises."""
        directive_id = uuid4()
        existing = uuid4()
        attempted = uuid4()
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            _validate_task_link_immutable(
                directive_id=directive_id,
                existing_task_id=existing,
                attempted_task_id=attempted,
            )
        assert excinfo.value.kind == "task_already_linked"

    def test_existing_value_raises_on_identical_attempt(self) -> None:
        """Confirmation D: existing == attempted task_id still raises (no idempotency)."""
        directive_id = uuid4()
        same = uuid4()
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            _validate_task_link_immutable(
                directive_id=directive_id,
                existing_task_id=same,
                attempted_task_id=same,
            )
        assert excinfo.value.kind == "task_already_linked"
