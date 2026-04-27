"""MSG-DR-001 / 002 wording + Next: hint physical guarantee
(TC-UT-DR-022 / 023).

Each MSG follows the 2-line structure (Confirmation F, room §確定 I
踏襲):

    [FAIL] <failure fact>
    Next: <recommended next action>

The first line is asserted **exactly** so future i18n / refactoring
cannot silently drift the operator-visible failure fact. The second
line is asserted via substring on the leading ``Next:`` token *and* a
topic phrase so the design-time hint contract survives cosmetic edits
while the "hint exists" property is locked in by CI.

MSG-DR-003 (type violation) travels the :class:`pydantic.ValidationError`
path; it is covered in ``test_construction.py``. MSG-DR-004 / 005
belong to the application layer (``DirectiveService.issue()``) — out of
scope for this aggregate test suite.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import DirectiveInvariantViolation

from tests.factories.directive import (
    make_directive,
    make_linked_directive,
)


class TestMsgDr001TextRange:
    """TC-UT-DR-022: MSG-DR-001 + Next: hint."""

    def test_failure_line_matches_exact_wording(self) -> None:
        """TC-UT-DR-022: '[FAIL] Directive text must be 1-10000 ...' exact prefix."""
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text="a" * 10_001)
        assert excinfo.value.message.startswith(
            "[FAIL] Directive text must be 1-10000 characters (got 10001)"
        )

    def test_next_hint_present_with_topic_phrase(self) -> None:
        """TC-UT-DR-022: 'Next:' hint exists with multi-directive / trim topic phrase."""
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text="a" * 10_001)
        message = excinfo.value.message
        assert "Next:" in message
        # Hint must mention either trimming or splitting into multiple
        # directives (Confirmation F's documented ``Next`` phrase).
        assert ("Trim" in message) or ("multiple directives" in message)


class TestMsgDr002TaskAlreadyLinked:
    """TC-UT-DR-023: MSG-DR-002 + Next: hint (issue a new Directive)."""

    def test_failure_line_includes_pair_identifiers(self) -> None:
        """TC-UT-DR-023: '[FAIL] Directive already has a linked Task: ...' format."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        new_task_id = uuid4()
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            directive.link_task(new_task_id)
        message = excinfo.value.message
        assert "[FAIL] Directive already has a linked Task" in message
        assert f"directive_id={directive.id}" in message
        assert f"existing_task_id={existing_task_id}" in message

    def test_next_hint_advises_new_directive_and_states_one_to_one(self) -> None:
        """TC-UT-DR-023: 'Next:' hint mentions issuing a new Directive + 1:1 design statement."""
        directive = make_linked_directive(task_id=uuid4())
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            directive.link_task(uuid4())
        message = excinfo.value.message
        assert "Next:" in message
        assert "Issue a new Directive" in message
        # Confirmation F's design statement: "one Directive maps to one Task by design".
        assert "one Directive maps to one Task" in message
