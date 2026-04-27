"""``link_task`` behavior + uniqueness contract tests
(TC-UT-DR-005 / 006 / 016 / 017).

Confirmation C / D: ``link_task`` flips ``task_id`` from ``None`` to a
real value exactly once. Re-linking — *even with the same TaskId* — is
always a Fail Fast. The constructor path (Repository hydration) is
allowed to carry an existing ``task_id`` because that is a permanent
attribute value, not a transition.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import DirectiveInvariantViolation

from tests.factories.directive import (
    make_directive,
    make_linked_directive,
)


class TestLinkTaskHappyPath:
    """TC-UT-DR-005: link_task flips None → valid TaskId, returns new instance."""

    def test_link_task_returns_directive_with_task_id(self) -> None:
        """TC-UT-DR-005: returned Directive carries the new task_id."""
        directive = make_directive()
        task_id = uuid4()
        linked = directive.link_task(task_id)
        assert linked.task_id == task_id

    def test_link_task_does_not_mutate_original(self) -> None:
        """TC-UT-DR-005: original Directive.task_id stays None after link_task."""
        directive = make_directive()
        directive.link_task(uuid4())
        assert directive.task_id is None

    def test_linked_directive_preserves_other_attributes(self) -> None:
        """TC-UT-DR-005: only task_id changes; id / text / target_room_id / created_at survive."""
        directive = make_directive()
        new_task_id = uuid4()
        linked = directive.link_task(new_task_id)
        assert linked.id == directive.id
        assert linked.text == directive.text
        assert linked.target_room_id == directive.target_room_id
        assert linked.created_at == directive.created_at


class TestLinkTaskRejectsRelink:
    """TC-UT-DR-006: link_task on an already-linked Directive raises (§確定 C)."""

    def test_relink_with_different_task_id_raises(self) -> None:
        """TC-UT-DR-006: existing → new task_id raises ``task_already_linked``."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        new_task_id = uuid4()
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            directive.link_task(new_task_id)
        assert excinfo.value.kind == "task_already_linked"

    def test_relink_detail_includes_pair_identifiers(self) -> None:
        """TC-UT-DR-006: detail dict carries directive_id / existing_task_id / attempted_task_id."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        new_task_id = uuid4()
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            directive.link_task(new_task_id)
        detail = excinfo.value.detail
        assert detail.get("directive_id") == str(directive.id)
        assert detail.get("existing_task_id") == str(existing_task_id)
        assert detail.get("attempted_task_id") == str(new_task_id)


class TestLinkTaskNoIdempotency:
    """TC-UT-DR-016: same TaskId re-link still raises (§確定 D — no idempotency)."""

    def test_relink_with_identical_task_id_still_raises(self) -> None:
        """TC-UT-DR-016: re-linking with the *same* task_id is still a Fail Fast."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        # Confirmation D freezes "1 link only, second call always fails"
        # — the simpler contract avoids special cases in the validator.
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            directive.link_task(existing_task_id)
        assert excinfo.value.kind == "task_already_linked"


class TestPreValidateRollback:
    """TC-UT-DR-017: failed link_task leaves the original Directive intact (§確定 A)."""

    def test_link_task_failure_does_not_mutate_original(self) -> None:
        """TC-UT-DR-017: original Directive.task_id stays unchanged after a failed re-link."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        with pytest.raises(DirectiveInvariantViolation):
            directive.link_task(uuid4())
        # The original instance still references the original task_id.
        assert directive.task_id == existing_task_id

    def test_failed_relink_can_be_repeated_without_progress(self) -> None:
        """TC-UT-DR-017: state damage does not accumulate across repeated failures."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        # Three different attempted task_ids — each must fail and the
        # Directive must remain identifiable as "linked to the original".
        for _ in range(3):
            with pytest.raises(DirectiveInvariantViolation):
                directive.link_task(uuid4())
        assert directive.task_id == existing_task_id
